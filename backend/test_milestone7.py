#!/usr/bin/env python3
"""
Automated Test Suite for Milestone 7: Production Hardening,
Rate-Limit Shield, Model Fallbacks, LRU Caching & Vercel Readiness.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import settings
from app.schemas import TutorTurnRequest, TutorTurnResponse
from app.services.session_manager import session_manager
from app.services.gemini_live import (
    execute_tutor_turn,
    is_rate_limit_error,
)
from app.services.gnani_tts import (
    synthesize_speech,
    clear_tts_cache,
    _TTS_CACHE,
)
from app.main import app


async def test_dynamic_config_and_health():
    print("\n--- Test 1: Dynamic .env Loading & Safe /api/health Diagnostics ---")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200, f"Expected 200 from /api/health, got {res.status_code}"
        data = res.json()
        assert data["ok"] is True
        assert "gemini_configured" in data
        assert "gnani_configured" in data
        assert data["gemini_model"] == "gemini-3.8-live"
        assert data["env_source"] in ("os_environ", "backend_env", "root_env", "unconfigured")
        print(f"✅ Initial /api/health response verified: {data}")

        # Test dynamic reload with temporary OS environment variable
        orig_key = os.environ.get("GEMINI_API_KEY")
        init_configured = settings.is_gemini_configured
        init_source = settings.env_source
        try:
            os.environ["GEMINI_API_KEY"] = "AIzaSyFakeKeyForTestingDynamicResolution123"
            settings.reload_settings()
            assert settings.is_gemini_configured is True
            assert settings.env_source == "os_environ"

            res2 = await client.get("/api/health")
            data2 = res2.json()
            assert data2["gemini_configured"] is True
            assert data2["env_source"] == "os_environ"
            print("✅ Dynamic reload verified: OS env variable reflected immediately in /api/health")
        finally:
            if orig_key is not None:
                os.environ["GEMINI_API_KEY"] = orig_key
            else:
                os.environ.pop("GEMINI_API_KEY", None)
            settings.reload_settings()
            assert settings.is_gemini_configured == init_configured
            assert settings.env_source == init_source
            print("✅ Teardown verified: Settings cleanly reverted to initial state")


async def test_stateless_history_hydration():
    print("\n--- Test 2: Stateless history Hydration Across Cold Sessions ---")
    cold_session_id = f"test_cold_{os.urandom(4).hex()}"

    # Verify session doesn't exist yet
    rec = await session_manager.get(cold_session_id)
    assert rec is None, "Session should not exist initially"

    # Send a request with history turns
    sample_history = [
        {"role": "student", "text": "2x = 8"},
        {"role": "tutor", "text": "What operation should you perform to isolate x?"},
        {"role": "student", "text": "Divide both sides by 2"}
    ]

    req = TutorTurnRequest(
        session_id=cold_session_id,
        subject="maths",
        learner_level="school",
        language_code="en-IN",
        message="x = 4",
        action="check_work",
        history=sample_history
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Request should hydrate history even if Gemini key is placeholder
        await client.post("/api/tutor/turn", json=req.model_dump())

        # Inspect session record
        hydrated_rec = await session_manager.get(cold_session_id)
        assert hydrated_rec is not None, "Session record should have been created"
        history_summary = hydrated_rec.get_history_summary()
        assert "2x = 8" in history_summary, "History turn 1 should be hydrated"
        assert "Divide both sides by 2" in history_summary, "History turn 3 should be hydrated"
        print(f"✅ Cold serverless session hydrated with {len(hydrated_rec.history)} turns: \n   {history_summary}")

    # Clean up test session
    await session_manager.close_session(cold_session_id)


async def test_tier3_emergency_rescue_on_429():
    print("\n--- Test 3: Gemini Tier 1 -> Tier 2 -> Tier 3 Rate-Limit (429) Fallback Rescue ---")
    sess_id = f"test_rescue_{os.urandom(4).hex()}"
    rec = await session_manager.get_or_create(sess_id, "maths", "en-IN")

    # Set mock key so config allows turn execution
    orig_key = os.environ.get("GEMINI_API_KEY")
    try:
        os.environ["GEMINI_API_KEY"] = "mock_key_for_tier3"
        settings.reload_settings()

        # 3A: Test rate limit error detection helper
        err_429 = Exception("429 Resource has been exhausted (e.g. check quota).")
        assert is_rate_limit_error(err_429) is True, "Should detect 429 error"

        # 3B: Student algebra error: 2x = 8 -> x = 8
        req_error = TutorTurnRequest(
            session_id=sess_id,
            subject="maths",
            message="2x = 8, x = 8",
            action="check_work",
            language_code="en-IN"
        )

        with patch("app.services.gemini_live._execute_tier1_live", side_effect=Exception("429 Quota Exceeded")):
            with patch("app.services.gemini_live._execute_tier2_generate_content", side_effect=Exception("429 Resource Exhausted")):
                resp = await execute_tutor_turn(req_error, rec)

                assert resp.fallback_mode is True, "Should flag fallback_mode=True"
                assert resp.verdict == "incorrect", f"Expected verdict 'incorrect', got {resp.verdict}"
                assert "adjusted the coefficient" in resp.steps[0] or "adjusted" in resp.answer, "Should diagnose dividing error"
                print(f"✅ 429 Rescue for Error Step: verdict={resp.verdict}, fallback_mode={resp.fallback_mode}")
                print(f"   Socratic Answer: {resp.answer[:80]}...")

        # 3C: Student corrected step: 2x = 8 -> x = 4
        req_correct = TutorTurnRequest(
            session_id=sess_id,
            subject="maths",
            message="2x = 8, x = 4",
            action="check_work",
            language_code="hi-IN"
        )

        with patch("app.services.gemini_live._execute_tier1_live", side_effect=Exception("429 Quota Exceeded")):
            with patch("app.services.gemini_live._execute_tier2_generate_content", side_effect=Exception("429 Resource Exhausted")):
                resp2 = await execute_tutor_turn(req_correct, rec)

                assert resp2.fallback_mode is True, "Should flag fallback_mode=True"
                assert resp2.verdict == "correct", f"Expected verdict 'correct', got {resp2.verdict}"
                print(f"✅ 429 Rescue for Correct Step (Hindi): verdict={resp2.verdict}, fallback_mode={resp2.fallback_mode}")
                print(f"   Localized Answer: {resp2.answer}")

        # 3D: Science subject rescue
        req_science = TutorTurnRequest(
            session_id=sess_id,
            subject="science",
            message="What is the difference between mass and weight?",
            action="ask",
            language_code="en-IN"
        )

        with patch("app.services.gemini_live._execute_tier1_live", side_effect=Exception("WebSocket Closed")):
            with patch("app.services.gemini_live._execute_tier2_generate_content", side_effect=Exception("429 Too Many Requests")):
                resp3 = await execute_tutor_turn(req_science, rec)

                assert resp3.fallback_mode is True
                assert "mass is the amount of matter" in resp3.answer.lower()
                print(f"✅ 429 Rescue for Science: fallback_mode={resp3.fallback_mode}")
                print(f"   Answer: {resp3.answer[:80]}...")

    finally:
        if orig_key is not None:
            os.environ["GEMINI_API_KEY"] = orig_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)
        settings.reload_settings()
        await session_manager.close_session(sess_id)


async def test_gnani_tts_lru_caching():
    print("\n--- Test 4: Gnani Timbre TTS In-Memory LRU Caching ---")
    clear_tts_cache()
    assert len(_TTS_CACHE) == 0, "Cache should be empty after clear"

    orig_key = os.environ.get("GNANI_API_KEY")
    try:
        os.environ["GNANI_API_KEY"] = "fake_gnani_key_for_cache_test"
        settings.reload_settings()

        fake_wav = b"RIFF" + b"\x24\x00\x00\x00WAVEfmt " + b"\x00" * 32 + b"data" + b"\x04\x00\x00\x00" + b"\x01\x02\x03\x04"

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_wav

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # 1. First call: Cache miss -> makes HTTP post
            wav1 = await synthesize_speech("Solve for x: 2x = 8", "en-IN")
            assert wav1 == fake_wav
            assert mock_post.call_count == 1, "First call should invoke upstream HTTP API"
            assert len(_TTS_CACHE) == 1, "Cache should contain 1 item"
            print(f"✅ Call 1 (Cache Miss): Upstream HTTP API invoked once. Cache size: {len(_TTS_CACHE)}")

            # 2. Second identical call: Cache hit -> 0 HTTP calls
            wav2 = await synthesize_speech("Solve for x: 2x = 8", "en-IN")
            assert wav2 == fake_wav
            assert mock_post.call_count == 1, "Second call MUST hit cache without calling upstream API"
            print("✅ Call 2 (Cache Hit): Returned cached WAV bytes without calling upstream API")

            # 3. Different text: Cache miss -> makes second HTTP post
            wav3 = await synthesize_speech("Step 2: Divide both sides by 2", "en-IN")
            assert wav3 == fake_wav
            assert mock_post.call_count == 2, "Different text should invoke upstream API"
            assert len(_TTS_CACHE) == 2, "Cache should contain 2 items"
            print(f"✅ Call 3 (Different text): Upstream API invoked. Cache size: {len(_TTS_CACHE)}")

    finally:
        if orig_key is not None:
            os.environ["GNANI_API_KEY"] = orig_key
        else:
            os.environ.pop("GNANI_API_KEY", None)
        settings.reload_settings()
        clear_tts_cache()


async def test_vercel_entrypoint():
    print("\n--- Test 5: Vercel Entrypoint (api/index.py) Import & Routing ---")
    import api.index

    assert hasattr(api.index, "app"), "api/index.py must expose 'app'"
    vercel_app = api.index.app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=vercel_app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        print(f"✅ Vercel serverless entrypoint verified: /api/health returned 200 OK: {data}")


async def main():
    print("=" * 65)
    print("      Milestone 7: Production Hardening & Fallback Verification    ")
    print("=" * 65)

    await test_dynamic_config_and_health()
    await test_stateless_history_hydration()
    await test_tier3_emergency_rescue_on_429()
    await test_gnani_tts_lru_caching()
    await test_vercel_entrypoint()

    print("\n" + "=" * 65)
    print("🎉 ALL MILESTONE 7 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
