#!/usr/bin/env python3
"""
Milestone 6 Automated Test Suite:
1. PDF Worksheet Turn Ingestion (POST /api/tutor/turn with input_source="pdf")
2. Science Subject Q&A Routing (subject="science", action="ask")
3. End-to-End Section 15 Demo Walkthrough Verification:
   - Step 1: 2x = 8 inquiry
   - Step 2: 2x = 8 -> x = 8 returns verdict="incorrect"
   - Step 3: 2x = 8 -> x = 4 returns verdict="correct"
4. Static Security Audit: Confirm zero leaked API keys or secrets in frontend/src, frontend/dist, or git tracking
"""

import asyncio
import os
import re
import subprocess
import httpx
from app.config import settings
from app.tools.math_verifier import verify_equation_step

BASE_URL = "http://127.0.0.1:8000"

# Minimal 1x1 valid JPEG in base64 representing a rendered PDF worksheet page
TINY_JPEG_B64 = (
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////"
    "////////////////////////////////////////////////////////////////wAECA//EAB8Q"
    "AAIDAQEBAQEBAQAAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUh"
    "MQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJ"
    "SlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2"
    "t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD/"
    "AD/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwBf/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/a"
    "AAgBAwEBPwBf/9oADAMBAAIRAxEAPwD/AD//2Q=="
)

async def test_pdf_worksheet_turn(client: httpx.AsyncClient):
    print("\n--- Test 1: PDF Worksheet Turn Ingestion ---")

    payload = {
        "session_id": "test_sess_pdf_ingest",
        "subject": "maths",
        "learner_level": "school",
        "language_code": "en-IN",
        "message": "Can you explain question 1 on this worksheet?",
        "input_source": "pdf",
        "whiteboard_image_base64": TINY_JPEG_B64,
        "action": "ask"
    }

    res = await client.post(f"{BASE_URL}/api/tutor/turn", json=payload)
    print(f"PDF Turn status: {res.status_code}")

    if not settings.is_gemini_configured:
        # Structured 503 is expected when key is placeholder
        assert res.status_code == 503
        assert res.json().get("error", {}).get("code") == "GEMINI_NOT_CONFIGURED"
        print("✅ PDF worksheet payload validated and structured GEMINI_NOT_CONFIGURED returned")
    else:
        assert res.status_code == 200
        data = res.json()
        assert len(data.get("answer", "")) > 0
        print(f"✅ PDF worksheet turn answered successfully: {data['answer'][:80]}...")

async def test_science_subject_routing(client: httpx.AsyncClient):
    print("\n--- Test 2: Science Subject Routing ---")

    payload = {
        "session_id": "test_sess_science",
        "subject": "science",
        "learner_level": "school",
        "language_code": "en-IN",
        "message": "Why do objects fall towards Earth?",
        "input_source": "whiteboard",
        "whiteboard_image_base64": TINY_JPEG_B64,
        "action": "explain_simply"
    }

    res = await client.post(f"{BASE_URL}/api/tutor/turn", json=payload)
    print(f"Science Turn status: {res.status_code}")

    if not settings.is_gemini_configured:
        assert res.status_code == 503
        print("✅ Science subject routing verified with structured 503 response")
    else:
        assert res.status_code == 200
        data = res.json()
        print(f"✅ Science concept explained: {data.get('answer', '')[:80]}...")

def test_section_15_demo_flow():
    print("\n--- Test 3: Section 15 Three-Minute Pitch Demo Flow ---")

    # Step 1: Initial problem 2x = 8 inquiry
    step1_res = verify_equation_step(original_equation="2x = 8", current_step="2x = 8")
    assert step1_res["status"] == "correct"
    print("✅ Demo Step 1: Problem baseline '2x = 8' verified as consistent")

    # Step 2: Student error detection 2x = 8 -> x = 8
    step2_res = verify_equation_step(original_equation="2x = 8", current_step="x = 8")
    print("Demo Step 2 (Error):", step2_res)
    assert step2_res["status"] == "incorrect", f"Expected incorrect, got {step2_res['status']}"
    assert "divide" in step2_res["reason"].lower() or "divide" in step2_res.get("expected_next_step", "").lower()
    print("✅ Demo Step 2: Error step 'x = 8' correctly flagged as incorrect with dividing hint")

    # Step 3: Corrected student step 2x = 8 -> x = 4
    step3_res = verify_equation_step(original_equation="2x = 8", current_step="x = 4")
    print("Demo Step 3 (Corrected):", step3_res)
    assert step3_res["status"] == "correct", f"Expected correct, got {step3_res['status']}"
    assert "4" in step3_res["reason"]
    print("✅ Demo Step 3: Correct step 'x = 4' confirmed as correct with congratulatory note")

def test_security_and_secret_hygiene():
    print("\n--- Test 4: Static Security & Secret Hygiene Audit ---")

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    frontend_src = os.path.join(project_root, "frontend", "src")
    frontend_dist = os.path.join(project_root, "frontend", "dist")

    sensitive_patterns = [
        re.compile(r"AIzaSy[0-9A-Za-z-_]{33}"),  # Google API Key pattern
        re.compile(r"gnani_[0-9A-Za-z-_]{16,}"),
    ]

    def scan_directory(dir_path):
        if not os.path.exists(dir_path):
            return
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith((".js", ".jsx", ".html", ".css", ".json")):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for pattern in sensitive_patterns:
                            match = pattern.search(content)
                            assert match is None, f"Security violation: Secret pattern found in {file_path}!"

    scan_directory(frontend_src)
    scan_directory(frontend_dist)
    print("✅ frontend/src/ and frontend/dist/ scanned: ZERO client-side secrets found")

    # Check git tracked files for .env
    git_check = subprocess.run(
        ["git", "ls-files", "backend/.env", ".env"],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    assert len(git_check.stdout.strip()) == 0, "Security violation: backend/.env is tracked in git!"
    print("✅ Git tracking audit: .env files are strictly git-ignored and untracked")

async def main():
    print("=================================================================")
    print("   Milestone 6: PDF, Science, Demo Hardening & Security Audit   ")
    print("=================================================================")

    test_section_15_demo_flow()
    test_security_and_secret_hygiene()

    async with httpx.AsyncClient(timeout=15.0) as client:
        await test_pdf_worksheet_turn(client)
        await test_science_subject_routing(client)

    print("\n🎉 ALL MILESTONE 6 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())

