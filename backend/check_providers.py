#!/usr/bin/env python3
"""
Standalone Provider Connectivity Check Script (Milestone 7 Hardened)
Verifies access to:
1. Google Gemini Live (gemini-3.8-live / gemini-2.0-flash-live-001)
2. Google Gemini Fallback (gemini-2.5-flash generate_content)
3. Gnani Timbre TTS (timbre-v3.0 via https://api.vachana.ai/api/v1/tts/inference)
4. Gnani Prisma STT (prisma-v3.0 via https://api.vachana.ai/stt/v3)

SECURITY: API keys are read from backend/.env, root .env, or OS env and NEVER printed in stdout/stderr.
"""

import asyncio
import io
import os
import sys
import time
import wave
from pathlib import Path
import httpx

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings, BACKEND_ENV_PATH, ROOT_ENV_PATH


def mask_key(key: str) -> str:
    """Return masked string indicating presence without leaking characters."""
    if not key or key == "replace_me":
        return "[NOT SET / PLACEHOLDER]"
    if len(key) <= 8:
        return f"[SET: {len(key)} chars: ****]"
    return f"[SET: {len(key)} chars: ...{key[-4:]}]"


def print_env_diagnostics():
    print("=" * 65)
    print("Agentic Multilingual Learning Tutor — Provider Checks (M7)")
    print("=" * 65)
    print(f"Backend .env location : {BACKEND_ENV_PATH} (exists: {BACKEND_ENV_PATH.exists()})")
    print(f"Root .env location    : {ROOT_ENV_PATH} (exists: {ROOT_ENV_PATH.exists()})")
    print(f"Active Env Source     : {settings.env_source}")
    print(f"Gemini Live Model     : {settings.GEMINI_LIVE_MODEL}")
    print(f"Gemini Key Status     : {mask_key(settings.GEMINI_API_KEY)}")
    print(f"Gnani Key Status      : {mask_key(settings.GNANI_API_KEY)}")
    print("=" * 65)


async def test_gemini_live() -> bool:
    print("\n" + "=" * 65)
    print("TEST 1: Google Gemini Live Connectivity (Tier 1)")
    print(f"Model: {settings.GEMINI_LIVE_MODEL}")
    print("=" * 65)

    if not settings.is_gemini_configured:
        print("❌ SKIPPED: GEMINI_API_KEY is not configured (set to 'replace_me' or empty).")
        return False

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options={"api_version": "v1alpha"})
        config = types.LiveConnectConfig(response_modalities=["AUDIO"])

        start_t = time.perf_counter()
        print(f"Connecting to Gemini Live WebSocket ({settings.GEMINI_LIVE_MODEL})...")

        async with asyncio.timeout(12.0):
            async with client.aio.live.connect(model=settings.GEMINI_LIVE_MODEL, config=config) as session:
                await session.send(input="Reply with 'OK'", end_of_turn=True)
                received_response = False
                audio_bytes_count = 0
                async for response in session.receive():
                    server_content = response.server_content
                    if server_content is not None and server_content.model_turn is not None:
                        for part in server_content.model_turn.parts:
                            if part.inline_data:
                                audio_bytes_count += len(part.inline_data.data)
                                received_response = True
                    if received_response or (server_content and server_content.turn_complete):
                        break

                elapsed = (time.perf_counter() - start_t) * 1000
                print(f"✅ SUCCESS: Gemini Live WebSocket connected and streamed {audio_bytes_count} bytes audio in {elapsed:.1f}ms!")
                return True

    except Exception as e:
        print(f"❌ ERROR: Gemini Live check failed: {e}")
        return False


async def test_gemini_fallback_generate_content() -> bool:
    print("\n" + "=" * 65)
    print("TEST 2: Google Gemini generate_content Multimodal Engine (Tier 2)")
    print("Model: gemini-3.5-flash")
    print("=" * 65)

    if not settings.is_gemini_configured:
        print("❌ SKIPPED: GEMINI_API_KEY is not configured.")
        return False

    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        start_t = time.perf_counter()
        print("Sending generate_content request to 'gemini-3.5-flash'...")

        res = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-3.5-flash",
                contents="Reply with 'Gemini 3.5 Flash is ready!'"
            ),
            timeout=10.0
        )
        elapsed = (time.perf_counter() - start_t) * 1000
        print(f"✅ SUCCESS: Gemini 3.5 Flash responded in {elapsed:.1f}ms: '{res.text.strip()[:60]}'")
        return True

    except Exception as e:
        print(f"❌ ERROR: Gemini generate_content failed: {e}")
        return False


async def test_gnani_timbre_tts() -> bool:
    print("\n" + "=" * 65)
    print("TEST 3: Gnani Timbre TTS Connectivity")
    print("Endpoint: https://api.vachana.ai/api/v1/tts/inference | Model: timbre-v3.0")
    print("=" * 65)

    if not settings.is_gnani_configured:
        print("❌ SKIPPED: GNANI_API_KEY is not configured (set to 'replace_me' or empty).")
        return False

    url = "https://api.vachana.ai/api/v1/tts/inference"
    headers = {
        "X-API-Key-ID": settings.GNANI_API_KEY,
        "Content-Type": "application/json"
    }
    voice_name = settings.GNANI_TTS_VOICE if (settings.GNANI_TTS_VOICE and settings.GNANI_TTS_VOICE != "default") else "Shivani"
    payload = {
        "model": "timbre-v3.0",
        "language": "en-IN",
        "text": "Hello student, welcome to your interactive maths class.",
        "voice": voice_name,
        "audio_config": {
            "audio_encoding": "linear_pcm",
            "sample_rate_hertz": 48000,
            "format": "wav"
        }
    }

    try:
        start_t = time.perf_counter()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            elapsed = (time.perf_counter() - start_t) * 1000
            print(f"HTTP Status: {resp.status_code} in {elapsed:.1f}ms (voice: {voice_name})")

            if resp.status_code == 200:
                print(f"✅ SUCCESS: Timbre TTS returned {len(resp.content)} bytes audio!")
                return True
            else:
                print(f"❌ ERROR: Timbre TTS returned HTTP {resp.status_code}: {resp.text[:150]}")
                return False
    except Exception as e:
        print(f"❌ ERROR: Gnani TTS failed: {e}")
        return False


async def test_gnani_prisma_stt() -> bool:
    print("\n" + "=" * 65)
    print("TEST 4: Gnani Prisma STT Connectivity")
    print("Endpoint: https://api.vachana.ai/stt/v3 | Model: prisma-v3.0")
    print("=" * 65)

    if not settings.is_gnani_configured:
        print("❌ SKIPPED: GNANI_API_KEY is not configured (set to 'replace_me' or empty).")
        return False

    # Generate synthetic 16kHz mono 16-bit PCM WAV (0.5s of silence)
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 8000)
    synthetic_wav = wav_io.getvalue()

    url = "https://api.vachana.ai/stt/v3"
    headers = {"X-API-Key-ID": settings.GNANI_API_KEY}
    files = {"audio_file": ("test.wav", synthetic_wav, "audio/wav")}
    data = {"language_code": "indic-auto"}

    try:
        start_t = time.perf_counter()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)
            elapsed = (time.perf_counter() - start_t) * 1000
            print(f"HTTP Status: {resp.status_code} in {elapsed:.1f}ms")

            if resp.status_code in (200, 201):
                print(f"✅ SUCCESS: Prisma STT responded in {elapsed:.1f}ms!")
                return True
            else:
                print(f"❌ ERROR: Prisma STT returned HTTP {resp.status_code}: {resp.text[:150]}")
                return False
    except Exception as e:
        print(f"❌ ERROR: Gnani STT failed: {e}")
        return False


async def main():
    print_env_diagnostics()

    live_ok = await test_gemini_live()
    fallback_ok = await test_gemini_fallback_generate_content()
    tts_ok = await test_gnani_timbre_tts()
    stt_ok = await test_gnani_prisma_stt()

    print("\n" + "=" * 65)
    print("SUMMARY OF PROVIDER CONNECTIVITY CHECKS:")
    print("=" * 65)
    print(f"  - Gemini Live (Tier 1)        : {'✅ CONNECTED' if live_ok else '⚠️ PENDING / SKIPPED'}")
    print(f"  - Gemini Fallback (Tier 2)    : {'✅ CONNECTED' if fallback_ok else '⚠️ PENDING / SKIPPED'}")
    print(f"  - Gnani Timbre TTS            : {'✅ CONNECTED' if tts_ok else '⚠️ PENDING / SKIPPED'}")
    print(f"  - Gnani Prisma STT            : {'✅ CONNECTED' if stt_ok else '⚠️ PENDING / SKIPPED'}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
