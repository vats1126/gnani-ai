#!/usr/bin/env python3
"""
Automated Test Suite for Milestone 8:
Unified Two-Layer Whiteboard & PDF Integration, Natural Multilingual TTS,
Mathematical Speech Normalization, and PCM-to-WAV Packaging.
"""

import asyncio
import base64
import io
import os
import sys
import wave
from pathlib import Path
from unittest.mock import patch, AsyncMock
import httpx
from PIL import Image, ImageDraw

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import settings
from app.schemas import TutorTurnRequest, TutorTurnResponse, SpeakRequest
from app.services.gnani_tts import (
    verbalize_math_for_speech,
    pcm_to_wav,
    synthesize_speech,
    clear_tts_cache,
    get_cached_tts,
    _TTS_CACHE,
)
from app.main import app


def test_math_verbalization_multilingual():
    print("\n--- Test 1: Mathematical Speech Normalization & Verbalization ---")

    # 1.1 English (en-IN)
    en_res = verbalize_math_for_speech("2x + 5 = 15\nSolve step-by-step", "en-IN")
    print(f"  en-IN normalized: {en_res}")
    assert "equals" in en_res, f"Expected 'equals' in en-IN, got '{en_res}'"
    assert "plus" in en_res, f"Expected 'plus' in en-IN, got '{en_res}'"
    assert "2 x" in en_res, f"Expected space between coefficient and variable '2 x', got '{en_res}'"
    assert "step-by-step" in en_res, f"Expected hyphenated word 'step-by-step' preserved, got '{en_res}'"
    print("  ✅ en-IN: equation, operators, and hyphen disambiguation verified")

    # 1.2 Hindi (hi-IN)
    hi_res = verbalize_math_for_speech("2x + 5 = 15", "hi-IN")
    print(f"  hi-IN normalized: {hi_res}")
    assert "बराबर" in hi_res, f"Expected 'बराबर' in hi-IN, got '{hi_res}'"
    assert "प्लस" in hi_res, f"Expected 'प्लस' in hi-IN, got '{hi_res}'"
    print("  ✅ hi-IN: localized operators (बराबर, प्लस) verified")

    # 1.3 Kannada (kn-IN)
    kn_res = verbalize_math_for_speech("2x + 5 = 15", "kn-IN")
    print(f"  kn-IN normalized: {kn_res}")
    assert "ಸಮ" in kn_res, f"Expected 'ಸಮ' in kn-IN, got '{kn_res}'"
    assert "ಪ್ಲಸ್" in kn_res, f"Expected 'ಪ್ಲಸ್' in kn-IN, got '{kn_res}'"
    print("  ✅ kn-IN: localized operators (ಸಮ, ಪ್ಲಸ್) verified")

    # 1.4 Powers, Fractions, and Roots
    pwr_en = verbalize_math_for_speech("x^2 = 9 and \\frac{1}{2} + \\sqrt{16} = 5", "en-IN")
    print(f"  Powers/Fractions/Roots normalized: {pwr_en}")
    assert "squared" in pwr_en, f"Expected 'squared' for x^2, got '{pwr_en}'"
    assert "divided by" in pwr_en, f"Expected 'divided by' for \\frac, got '{pwr_en}'"
    assert "square root of" in pwr_en, f"Expected 'square root of' for \\sqrt, got '{pwr_en}'"
    print("  ✅ Advanced math (squared, fraction over/divided by, square root) verified")

    # 1.5 Markdown & LaTeX Delimiter Stripping & 1-4 Sentences
    raw_explanation = """
    # Solution Guide
    * Step 1: Let us isolate $2x$ by subtracting 5 from both sides.
    * Step 2: Now we get $$2x = 10$$.
    * Step 3: Divide both sides by 2 to get $x = 5$.
    * Step 4: Check work: \\[2(5) + 5 = 15\\], which matches!
    * Step 5: This extra sentence should be trimmed because spoken feedback is limited to 1-4 sentences.
    """
    clean_speech = verbalize_math_for_speech(raw_explanation, "en-IN")
    print(f"  Cleansed speech: {clean_speech}")
    assert "#" not in clean_speech, "Markdown headers '#' should be stripped"
    assert "*" not in clean_speech, "Bullet symbols '*' should be stripped"
    assert "$" not in clean_speech, "LaTeX math delimiters '$' should be stripped"
    assert "\\[" not in clean_speech and "\\]" not in clean_speech, "LaTeX brackets should be stripped"

    # Verify sentence count constraint (1-4 sentences)
    sentence_count = len([s for s in clean_speech.split(".") if s.strip()])
    assert 1 <= sentence_count <= 4, f"Expected 1 to 4 conversational sentences, got {sentence_count}"
    print(f"  ✅ Cleansing and conversational sentence limit ({sentence_count} sentences) verified")

    # 1.6 Edge Cases: Decimals, Bracketed Division, and Parenthesized Exponents (Milestone 8 Iteration 2)
    # Decimal preservation: ensures decimal points are not split into sentence boundaries and Step 3 is preserved
    dec_res = verbalize_math_for_speech("Step 1: 0.5x = 2.5. Step 2: x = 5.0. Step 3: Check answer.", "en-IN")
    print(f"  Decimal preservation normalized: {dec_res}")
    assert "0.5 x" in dec_res, f"Expected '0.5 x' preserved without premature period splitting, got '{dec_res}'"
    assert "Step 3" in dec_res, f"Expected 'Step 3' not to be dropped by 4-sentence limit, got '{dec_res}'"

    # Bracketed division: ensures division following or preceding brackets verbalizes '/'
    bracket_div_res = verbalize_math_for_speech("((x + 1) * 2) / 3 = 4", "en-IN")
    print(f"  Bracketed division normalized: {bracket_div_res}")
    assert "/" not in bracket_div_res, f"Raw '/' should not remain in '{bracket_div_res}'"
    assert "divided by" in bracket_div_res, f"Expected 'divided by' for bracketed division, got '{bracket_div_res}'"

    # Parenthesized exponent: ensures exponent with parens and operators verbalizes power without orphan caret
    paren_exp_res = verbalize_math_for_speech("x^(2+n) = 16", "en-IN")
    print(f"  Parenthesized exponent normalized: {paren_exp_res}")
    assert "^" not in paren_exp_res, f"Orphan '^' should not remain in '{paren_exp_res}'"
    assert "power" in paren_exp_res, f"Expected 'power' for parenthesized exponent, got '{paren_exp_res}'"
    print("  ✅ Iteration 2 Edge Cases: decimals, bracketed division, and parenthesized exponents verified")

    # 1.7 Edge Cases: Parenthesized Bases in Powers (Milestone 8 Iteration 3)
    paren_base_pow_res = verbalize_math_for_speech("(a+b)^(n-1)", "en-IN")
    print(f"  Parenthesized base with parenthesized exponent normalized: {paren_base_pow_res}")
    assert "^" not in paren_base_pow_res, f"Raw '^' should not remain in '{paren_base_pow_res}'"
    assert "power" in paren_base_pow_res, f"Expected 'power' for parenthesized base power, got '{paren_base_pow_res}'"

    paren_base_sq_res = verbalize_math_for_speech("(x+1)^2 = 9", "en-IN")
    print(f"  Parenthesized base squared normalized: {paren_base_sq_res}")
    assert "^" not in paren_base_sq_res, f"Raw '^' should not remain in '{paren_base_sq_res}'"
    assert "squared" in paren_base_sq_res, f"Expected 'squared' for parenthesized base squared, got '{paren_base_sq_res}'"
    assert "equals" in paren_base_sq_res, f"Expected 'equals' in '{paren_base_sq_res}'"
    print("  ✅ Iteration 3 Edge Cases: parenthesized bases in powers verified")


def test_pcm_to_wav_header():
    print("\n--- Test 2: PCM to RIFF WAV Audio Packing & Structural Integrity ---")

    # 2.1 Standard 24kHz mono 16-bit PCM (1 second = 24000 samples * 2 bytes = 48000 bytes)
    sample_rate_24k = 24000
    pcm_24k = b"\x10\x00" * sample_rate_24k
    wav_24k = pcm_to_wav(pcm_24k, sample_rate=sample_rate_24k, num_channels=1, sampwidth=2)

    # Magic byte verification
    assert wav_24k.startswith(b"RIFF"), "WAV bytes must start with b'RIFF'"
    assert wav_24k[8:12] == b"WAVE", "Byte 8-12 must be b'WAVE'"
    assert b"fmt " in wav_24k, "Must contain 'fmt ' subchunk"
    assert b"data" in wav_24k, "Must contain 'data' subchunk"

    # Structural audio inspection via standard library wave module
    with wave.open(io.BytesIO(wav_24k), "rb") as wf:
        assert wf.getnchannels() == 1, f"Expected 1 channel, got {wf.getnchannels()}"
        assert wf.getframerate() == 24000, f"Expected 24000 Hz, got {wf.getframerate()}"
        assert wf.getsampwidth() == 2, f"Expected 2 bytes per sample (16-bit), got {wf.getsampwidth()}"
        assert wf.getnframes() == sample_rate_24k, f"Expected {sample_rate_24k} frames, got {wf.getnframes()}"
        frames = wf.readframes(sample_rate_24k)
        assert frames == pcm_24k, "Frame audio bytes must exactly match input PCM bytes"
    print("  ✅ 24kHz mono 16-bit RIFF WAV validated with python standard wave module")

    # 2.2 48kHz mono 16-bit PCM (Gnani Timbre audio rate)
    pcm_48k = b"\x20\x00" * 48000
    wav_48k = pcm_to_wav(pcm_48k, sample_rate=48000, num_channels=1, sampwidth=2)
    with wave.open(io.BytesIO(wav_48k), "rb") as wf:
        assert wf.getframerate() == 48000
        assert wf.getnframes() == 48000
    print("  ✅ 48kHz mono 16-bit RIFF WAV validated")

    # 2.3 Empty PCM edge case (must produce valid 44-byte RIFF header without crashing)
    empty_wav = pcm_to_wav(b"", sample_rate=24000, num_channels=1, sampwidth=2)
    assert len(empty_wav) == 44, f"Empty PCM WAV must be 44 header bytes, got {len(empty_wav)}"
    with wave.open(io.BytesIO(empty_wav), "rb") as wf:
        assert wf.getnframes() == 0
    print("  ✅ Empty PCM edge case correctly produced valid 44-byte playable header")


async def test_dual_tts_cascade_and_bypass():
    print("\n--- Test 3: Dual Cloud Neural TTS Cascade & Fallback Bypass ---")
    clear_tts_cache()

    # 3.1 Verify bypass_gnani=True triggers Gemini Audio fallback
    mock_pcm = b"\x00\x00" * 12000  # 0.5 sec at 24kHz
    mock_wav = pcm_to_wav(mock_pcm, sample_rate=24000, num_channels=1, sampwidth=2)

    with patch("app.services.gnani_tts.synthesize_gemini_audio", new=AsyncMock(return_value=mock_wav)) as mock_gemini:
        res_bytes = await synthesize_speech("Solve 2x = 8.", language_code="en-IN", bypass_gnani=True)
        assert res_bytes.startswith(b"RIFF"), "Synthesized speech must be valid RIFF WAV"
        assert mock_gemini.await_count == 1, "Gemini Audio TTS fallback should be invoked when bypass_gnani=True"
        print("  ✅ bypass_gnani=True bypassed Gnani and invoked Gemini Native Audio TTS")

        # 3.2 Test LRU Cache HIT
        cached_res = await synthesize_speech("Solve 2x = 8.", language_code="en-IN", bypass_gnani=True)
        assert cached_res == res_bytes, "Subsequent identical request must return cached bytes"
        assert mock_gemini.await_count == 1, "Cached call must NOT call Gemini API again"
        print("  ✅ TTS LRU cache HIT verified for secondary fallback")

    # 3.3 HTTP /api/voice/speak endpoint test via in-process ASGITransport
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Test validation error on empty text
        bad_req = await client.post("/api/voice/speak", json={"text": "   ", "language_code": "en-IN"})
        assert bad_req.status_code in (400, 422), f"Expected 400 or 422 for empty text, got {bad_req.status_code}"
        print(f"  ✅ /api/voice/speak correctly rejected empty text with HTTP {bad_req.status_code}")

        # Test valid speak request with mock fallback
        with patch("app.services.gnani_tts.synthesize_gemini_audio", new=AsyncMock(return_value=mock_wav)):
            speak_req = await client.post(
                "/api/voice/speak",
                json={
                    "text": "Great job! Your answer x = 4 is correct.",
                    "language_code": "en-IN",
                    "bypass_gnani": True,
                }
            )
            assert speak_req.status_code == 200, f"Expected 200 from /api/voice/speak, got {speak_req.status_code}"
            assert speak_req.headers["content-type"] == "audio/wav", "Content-Type must be audio/wav"
            assert speak_req.content.startswith(b"RIFF"), "Returned content must be valid RIFF WAV"
            print("  ✅ /api/voice/speak returned HTTP 200 with audio/wav RIFF stream")


async def test_composite_pdf_tutor_turn():
    print("\n--- Test 4: In-Process /api/tutor/turn with Composite PDF + Ink Annotation ---")

    # Generate a realistic composite image: PDF worksheet page with student handwritten ink
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Layer 0: Simulated PDF worksheet text
    draw.rectangle([(40, 30), (760, 110)], fill=(245, 247, 250), outline=(226, 232, 240))
    draw.text((60, 45), "NCERT Mathematics Worksheet - Class 8", fill=(30, 41, 59))
    draw.text((60, 75), "Question 1: Solve for x:  2x + 5 = 15", fill=(15, 23, 42))

    # Layer 1: Simulated student ink annotation (blue pen)
    draw.line([(60, 180), (160, 180)], fill=(37, 99, 235), width=3)
    draw.text((60, 195), "Step 1: 2x = 15 - 5", fill=(37, 99, 235))
    draw.text((60, 225), "Step 2: 2x = 10", fill=(37, 99, 235))
    draw.text((60, 255), "Step 3: x = 5", fill=(37, 99, 235))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    composite_data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as client:
        turn_payload = {
            "session_id": "test_m8_composite_pdf_session",
            "subject": "maths",
            "learner_level": "school",
            "language_code": "en-IN",
            "message": "Can you check my working on question 1 of this worksheet?",
            "input_source": "pdf",
            "whiteboard_image_base64": composite_data_url,
            "action": "check_work",
        }

        res = await client.post("/api/tutor/turn", json=turn_payload)
        assert res.status_code == 200, f"Expected HTTP 200 from /api/tutor/turn, got {res.status_code}: {res.text}"

        data = res.json()
        assert data["session_id"] == "test_m8_composite_pdf_session"
        assert len(data["answer"]) > 0, "Expected non-empty tutor answer"
        assert data["verdict"] in ("correct", "incorrect", "partial", "uncertain", "not_applicable"), (
            f"Unexpected verdict: {data['verdict']}"
        )
        print(f"  ✅ /api/tutor/turn processed composite PDF+ink turn (verdict={data['verdict']}, answer={data['answer'][:60]}...)")


async def test_image_payload_validation():
    print("\n--- Test 5: Image Payload Security & Error Contracts ---")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 5.1 Corrupted base64 string
        corrupt_payload = {
            "session_id": "test_m8_corrupt",
            "subject": "maths",
            "message": "Check my work",
            "input_source": "whiteboard",
            "whiteboard_image_base64": "data:image/jpeg;base64,ThisIsNotValidBase64!@#$%",
            "action": "check_work",
        }
        res_corrupt = await client.post("/api/tutor/turn", json=corrupt_payload)
        assert res_corrupt.status_code == 400, f"Expected 400 for corrupt base64, got {res_corrupt.status_code}"
        err = res_corrupt.json()
        assert err["error"]["code"] == "INVALID_PAYLOAD"
        print("  ✅ Corrupted base64 rejected with HTTP 400 INVALID_PAYLOAD")

        # 5.2 Exceeding 4MB maximum payload size limit
        huge_payload = {
            "session_id": "test_m8_oversized",
            "subject": "maths",
            "message": "Check my work",
            "whiteboard_image_base64": "A" * (5 * 1024 * 1024),  # 5 MB string
        }
        res_huge = await client.post("/api/tutor/turn", json=huge_payload)
        assert res_huge.status_code in (400, 422), f"Expected 400/422 for oversized payload, got {res_huge.status_code}"
        print("  ✅ Oversized image payload (>4MB) safely rejected with HTTP 400/422")


async def main():
    print("=" * 65)
    print("  Milestone 8: Unified Canvas, Dual TTS & Speech Math Verifier  ")
    print("=" * 65)

    test_math_verbalization_multilingual()
    test_pcm_to_wav_header()
    await test_dual_tts_cascade_and_bypass()
    await test_composite_pdf_tutor_turn()
    await test_image_payload_validation()

    print("\n" + "=" * 65)
    print("🎉 ALL MILESTONE 8 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
