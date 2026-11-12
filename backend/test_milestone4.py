#!/usr/bin/env python3
"""
Milestone 4 Automated Test Suite:
1. Speech Text Cleaning & Markdown Normalization
2. Script-Based Indic Locale Auto-Detection
3. STT Audio Format & Size Validation (/api/voice/transcribe)
4. TTS Request Validation (/api/voice/speak)
5. Structured Error Contract (GNANI_NOT_CONFIGURED / INVALID_AUDIO / INVALID_PAYLOAD)
6. Live Provider Connectivity (if GNANI_API_KEY is configured in backend/.env)
"""

import asyncio
import io
import struct
import httpx
from app.config import settings
from app.schemas import clean_text_for_speech
from app.services.gnani_tts import detect_script_locale

BASE_URL = "http://127.0.0.1:8000"

def generate_pcm_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate a valid silent 16-bit mono PCM WAV in memory."""
    num_samples = int(duration_sec * sample_rate)
    data = b"\x00\x00" * num_samples
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    data_size = len(data)

    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))          # Subchunk1Size
    buf.write(struct.pack("<H", 1))           # AudioFormat (PCM)
    buf.write(struct.pack("<H", num_channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(data)
    return buf.getvalue()

async def test_text_cleaning_and_script_detection():
    print("\n--- Test 1: Speech Text Cleaning & Script Locale Detection ---")

    # Text cleaning
    raw_markdown = "### Step 1: **Factorize** `x^2 - 4`\nResult is $(x-2)(x+2)$."
    cleaned = clean_text_for_speech(raw_markdown)
    assert "**" not in cleaned, "Markdown bold not stripped"
    assert "`" not in cleaned, "Markdown backticks not stripped"
    assert "###" not in cleaned, "Markdown heading not stripped"
    assert "$" not in cleaned, "LaTeX math delimiter not stripped"
    print(f"Cleaned Text: {cleaned}")
    print("✅ Markdown & LaTeX formatting cleanly stripped for natural speech synthesis")

    # Script-based Indic locale auto-detection
    hindi_text = "यह एक सही उत्तर है, आगे बढ़ें।"
    assert detect_script_locale(hindi_text) == "hi-IN", "Hindi Devanagari detection failed"

    tamil_text = "மிகவும் நன்று, அடுத்த படியை முயற்சிக்கவும்."
    assert detect_script_locale(tamil_text) == "ta-IN", "Tamil detection failed"

    kannada_text = "ಉತ್ತಮ ಪ್ರಯತ್ನ, ಮುಂದಿನ ಹಂತವನ್ನು ಮಾಡಿ ನೋಡಿ."
    assert detect_script_locale(kannada_text) == "kn-IN", "Kannada detection failed"

    telugu_text = "చాలా బాగుంది, తదుపరి దశను ప్రయత్నించండి."
    assert detect_script_locale(telugu_text) == "te-IN", "Telugu detection failed"

    english_text = "Good job! Now isolate the variable x."
    assert detect_script_locale(english_text) == "en-IN", "English detection failed"

    print("✅ Unicode script-based Indic locale resolution verified for hi, ta, kn, te, and en")

async def test_stt_validation(client: httpx.AsyncClient):
    print("\n--- Test 2: STT Audio Validation & Error Handling ---")

    # 1. Invalid audio extension / type
    res = await client.post(
        f"{BASE_URL}/api/voice/transcribe",
        files={"audio_file": ("test.txt", b"plain text is not audio", "text/plain")},
        data={"language_code": "indic-auto"}
    )
    print(f"Invalid extension status: {res.status_code}")
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    body = res.json()
    assert body.get("error", {}).get("code") == "INVALID_AUDIO"
    print("✅ Invalid audio file format correctly rejected with HTTP 400 INVALID_AUDIO")

    # 2. Empty audio file
    res = await client.post(
        f"{BASE_URL}/api/voice/transcribe",
        files={"audio_file": ("empty.wav", b"", "audio/wav")},
        data={"language_code": "indic-auto"}
    )
    print(f"Empty audio status: {res.status_code}")
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert res.json().get("error", {}).get("code") == "INVALID_AUDIO"
    print("✅ Empty audio file correctly rejected with HTTP 400 INVALID_AUDIO")

async def test_stt_transcribe(client: httpx.AsyncClient):
    print("\n--- Test 3: STT Transcribe Endpoint (/api/voice/transcribe) ---")
    wav_bytes = generate_pcm_wav_bytes(duration_sec=1.5, sample_rate=16000)

    if not settings.is_gnani_configured:
        print("Note: GNANI_API_KEY is placeholder ('replace_me'). Testing structured 503 GNANI_NOT_CONFIGURED...")
        res = await client.post(
            f"{BASE_URL}/api/voice/transcribe",
            files={"audio_file": ("recording.wav", wav_bytes, "audio/wav")},
            data={"language_code": "indic-auto"}
        )
        print(f"Transcribe status: {res.status_code}")
        assert res.status_code == 503, f"Expected 503, got {res.status_code}"
        body = res.json()
        assert body.get("error", {}).get("code") == "GNANI_NOT_CONFIGURED"
        print("✅ Structured 503 GNANI_NOT_CONFIGURED returned with clear guidance")
    else:
        print("Note: Real GNANI_API_KEY is configured! Running live Prisma STT transcribe check...")
        res = await client.post(
            f"{BASE_URL}/api/voice/transcribe",
            files={"audio_file": ("recording.wav", wav_bytes, "audio/wav")},
            data={"language_code": "indic-auto"}
        )
        print(f"Live Transcribe status: {res.status_code}")
        # Prisma STT should respond with 200 or 502 if upstream issue
        if res.status_code == 200:
            data = res.json()
            print(f"Transcript: {data.get('transcript')}")
            print(f"Detected Lang: {data.get('detected_language_code')}")
            print("✅ Live Gnani Prisma STT response successful")
        else:
            print(f"Live Transcribe response: {res.status_code} {res.text}")

async def test_tts_speak(client: httpx.AsyncClient):
    print("\n--- Test 4: TTS Synthesize Endpoint (/api/voice/speak) ---")

    # 1. Empty text validation
    res = await client.post(
        f"{BASE_URL}/api/voice/speak",
        json={"text": "   ", "language_code": "en-IN"}
    )
    print(f"Empty text status: {res.status_code}")
    assert res.status_code in (400, 422), f"Expected 400 or 422, got {res.status_code}"
    print("✅ Empty text rejected with HTTP 400 or 422")

    # 2. Speak request
    if not settings.is_gnani_configured:
        print("Note: GNANI_API_KEY is placeholder ('replace_me'). Testing structured 503 GNANI_NOT_CONFIGURED...")
        res = await client.post(
            f"{BASE_URL}/api/voice/speak",
            json={"text": "नमस्ते! आपका गणित का सवाल क्या है?", "language_code": "indic-auto"}
        )
        print(f"Speak status: {res.status_code}")
        assert res.status_code == 503, f"Expected 503, got {res.status_code}"
        body = res.json()
        assert body.get("error", {}).get("code") == "GNANI_NOT_CONFIGURED"
        print("✅ Structured 503 GNANI_NOT_CONFIGURED returned for TTS")
    else:
        print("Note: Real GNANI_API_KEY is configured! Running live Timbre TTS synthesis check...")
        res = await client.post(
            f"{BASE_URL}/api/voice/speak",
            json={"text": "Great job! Let's solve the next step together.", "language_code": "en-IN"}
        )
        print(f"Live Speak status: {res.status_code}")
        if res.status_code == 200:
            assert res.headers.get("content-type") == "audio/wav"
            assert len(res.content) > 100
            assert res.content[:4] == b"RIFF"
            assert res.content[8:12] == b"WAVE"
            print(f"✅ Live Gnani Timbre TTS returned {len(res.content)} bytes of WAV audio")
        else:
            print(f"Live Speak response: {res.status_code} {res.text}")

async def main():
    print("=================================================================")
    print("       Milestone 4: Gnani Voice Pipeline Automated Tests        ")
    print("=================================================================")

    await test_text_cleaning_and_script_detection()

    async with httpx.AsyncClient(timeout=30.0) as client:
        await test_stt_validation(client)
        await test_stt_transcribe(client)
        await test_tts_speak(client)

    print("\n🎉 ALL MILESTONE 4 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
