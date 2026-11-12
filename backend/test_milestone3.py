#!/usr/bin/env python3
"""
Milestone 3 Automated Test Suite:
1. Schema & Payload Validation
2. Base64 Image Decoding & Size Enforcement
3. Session Manager Concurrency & Locking
4. Structured Error Responses (GEMINI_NOT_CONFIGURED / INVALID_PAYLOAD)
5. Session Reset via /api/tutor/reset
6. Multi-turn Live Test (if real GEMINI_API_KEY is configured)
"""

import asyncio
import base64
import httpx
from app.config import settings

BASE_URL = "http://127.0.0.1:8000"

# Minimal 1x1 valid JPEG in base64
TINY_JPEG_B64 = (
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////"
    "////////////////////////////////////////////////////////////////wAECA//EAB8Q"
    "AAIDAQEBAQEBAQAAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUh"
    "MQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJ"
    "SlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2"
    "t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD/"
    "AD/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwBAgEBPwBf/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/a"
    "AAgBAwEBPwBf/9oADAMBAAIRAxEAPwD/AD//2Q=="
)

async def test_schemas_and_validation(client: httpx.AsyncClient):
    print("\n--- Test 1: Payload & Base64 Validation ---")

    # 1. Invalid base64 rejected with HTTP 400
    res = await client.post(
        f"{BASE_URL}/api/tutor/turn",
        json={
            "session_id": "test_sess_val",
            "subject": "maths",
            "message": "Check my work",
            "whiteboard_image_base64": "data:image/jpeg;base64,not_valid_b64!!!"
        }
    )
    print(f"Invalid base64 status: {res.status_code}")
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    body = res.json()
    assert body.get("error", {}).get("code") == "INVALID_PAYLOAD"
    print("✅ Invalid base64 correctly rejected with HTTP 400 INVALID_PAYLOAD")

    # 2. Oversized base64 (>4MB) rejected with HTTP 400 or 422
    oversized = "data:image/jpeg;base64," + ("A" * (4 * 1024 * 1024 + 100))
    res = await client.post(
        f"{BASE_URL}/api/tutor/turn",
        json={
            "session_id": "test_sess_oversize",
            "subject": "maths",
            "whiteboard_image_base64": oversized
        }
    )
    print(f"Oversized payload status: {res.status_code}")
    assert res.status_code in (400, 422), f"Expected 400 or 422, got {res.status_code}"
    print("✅ Oversized payload correctly rejected")

async def test_error_contract_or_live(client: httpx.AsyncClient):
    print("\n--- Test 2: Tutor Turn Handling ---")
    if not settings.is_gemini_configured:
        print("Note: GEMINI_API_KEY is placeholder ('replace_me'). Testing structured 503 GEMINI_NOT_CONFIGURED...")
        res = await client.post(
            f"{BASE_URL}/api/tutor/turn",
            json={
                "session_id": "test_sess_unconfigured",
                "subject": "maths",
                "message": "Solve 2x = 8",
                "whiteboard_image_base64": TINY_JPEG_B64,
                "action": "check_work"
            }
        )
        print(f"Turn status: {res.status_code}")
        assert res.status_code == 503, f"Expected 503, got {res.status_code}"
        body = res.json()
        assert body.get("error", {}).get("code") == "GEMINI_NOT_CONFIGURED"
        print("✅ Structured 503 GEMINI_NOT_CONFIGURED returned with clean user-facing error message")
    else:
        print("Note: Real GEMINI_API_KEY is configured! Running live two-turn test...")
        # Turn 1
        res1 = await client.post(
            f"{BASE_URL}/api/tutor/turn",
            json={
                "session_id": "live_test_sess",
                "subject": "maths",
                "message": "What is the first step to find x?",
                "whiteboard_image_base64": TINY_JPEG_B64,
                "action": "hint"
            }
        )
        print(f"Turn 1 status: {res1.status_code}")
        assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
        data1 = res1.json()
        print(f"Turn 1 Tutor Answer: {data1.get('answer', '')[:120]}...")

        # Turn 2 in same session
        res2 = await client.post(
            f"{BASE_URL}/api/tutor/turn",
            json={
                "session_id": "live_test_sess",
                "subject": "maths",
                "message": "Can you explain why we divide by 2?",
                "action": "explain_simply"
            }
        )
        print(f"Turn 2 status: {res2.status_code}")
        assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
        data2 = res2.json()
        print(f"Turn 2 Tutor Answer: {data2.get('answer', '')[:120]}...")
        print("✅ Multi-turn live session completed successfully!")

async def test_session_reset(client: httpx.AsyncClient):
    print("\n--- Test 3: Session Reset ---")
    res = await client.post(
        f"{BASE_URL}/api/tutor/reset",
        json={"session_id": "test_sess_reset"}
    )
    print(f"Reset status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    body = res.json()
    assert body.get("ok") is True
    assert body.get("session_id") == "test_sess_reset"
    print("✅ Session reset returned 200 OK")

async def test_session_manager_locking():
    print("\n--- Test 4: In-Memory Session Manager Concurrency & Locking ---")
    from app.services.session_manager import session_manager

    rec1 = await session_manager.get_or_create("lock_test_session")
    rec2 = await session_manager.get_or_create("lock_test_session")
    assert rec1 is rec2, "get_or_create must return identical session instance for same session_id"

    # Verify lock behavior
    assert not rec1.lock.locked()
    async with rec1.lock:
        assert rec2.lock.locked(), "Lock must be shared between session references"
    assert not rec1.lock.locked()

    # Verify history capping
    for i in range(15):
        rec1.append_turn("student", f"Question {i}")
        rec1.append_turn("tutor", f"Answer {i}")
    assert len(rec1.history) <= 10, f"History should be capped at 10, got {len(rec1.history)}"
    summary = rec1.get_history_summary()
    assert "Question 14" in summary
    print(f"✅ Session Manager locking and history capping verified (length: {len(rec1.history)})")

async def main():
    print("=" * 60)
    print("Milestone 3 Verification Test Suite")
    print("=" * 60)

    await test_session_manager_locking()

    async with httpx.AsyncClient(timeout=30.0) as client:
        await test_schemas_and_validation(client)
        await test_error_contract_or_live(client)
        await test_session_reset(client)

    print("\n" + "=" * 60)
    print("ALL MILESTONE 3 TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

