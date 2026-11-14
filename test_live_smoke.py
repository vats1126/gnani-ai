import io
import wave
import struct
import base64
import requests
import json
import sys

BASE_URL = "http://localhost:5173"
print(f"Running End-to-End Live Smoke Tests against {BASE_URL}...")

def create_dummy_jpeg_base64():
    # 1x1 white JPEG image base64
    # Valid minimal JPEG
    from PIL import Image
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def create_16k_mono_wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)      # Mono
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(16000)  # 16kHz
        # Write 0.5s of silence (8000 samples)
        samples = [0] * 8000
        raw = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(raw)
    return buf.getvalue()

results = {}

# Test (a): GET /api/health
print("\n--- TEST (a): GET /api/health ---")
try:
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.text}")
    assert r.status_code == 200, f"Expected HTTP 200, got {r.status_code}"
    results["a_health"] = "PASS"
except Exception as e:
    print(f"TEST (a) FAILED: {e}")
    results["a_health"] = f"FAIL: {e}"

# Test (b): POST /api/tools/verify-step
print("\n--- TEST (b): POST /api/tools/verify-step ---")
try:
    # Subtest 1: 2x = 8 -> x = 8 (incorrect)
    p1 = {
        "original_equation": "2x = 8",
        "current_step": "x = 8",
        "previous_step": "2x = 8",
        "variable": "x"
    }
    r1 = requests.post(f"{BASE_URL}/api/tools/verify-step", json=p1, timeout=10)
    print(f"Step 'x=8' Status Code: {r1.status_code}")
    data1 = r1.json()
    print(f"Step 'x=8' Response: {data1}")
    assert r1.status_code == 200
    assert data1["status"] == "incorrect", f"Expected 'incorrect', got {data1['status']}"

    # Subtest 2: 2x = 8 -> x = 4 (correct)
    p2 = {
        "original_equation": "2x = 8",
        "current_step": "x = 4",
        "previous_step": "2x = 8",
        "variable": "x"
    }
    r2 = requests.post(f"{BASE_URL}/api/tools/verify-step", json=p2, timeout=10)
    print(f"Step 'x=4' Status Code: {r2.status_code}")
    data2 = r2.json()
    print(f"Step 'x=4' Response: {data2}")
    assert r2.status_code == 200
    assert data2["status"] == "correct", f"Expected 'correct', got {data2['status']}"

    results["b_verify_step"] = "PASS"
except Exception as e:
    print(f"TEST (b) FAILED: {e}")
    results["b_verify_step"] = f"FAIL: {e}"

# Test (c): POST /api/tutor/turn (whiteboard and pdf)
print("\n--- TEST (c): POST /api/tutor/turn ---")
try:
    jpeg_b64 = create_dummy_jpeg_base64()

    # Subtest 1: input_source="whiteboard"
    p_wb = {
        "session_id": "test_e2e_session",
        "subject": "maths",
        "learner_level": "school",
        "language_code": "en-IN",
        "message": "Can you check my equation on the whiteboard?",
        "input_source": "whiteboard",
        "whiteboard_image_base64": jpeg_b64,
        "action": "check_work",
        "history": []
    }
    r_wb = requests.post(f"{BASE_URL}/api/tutor/turn", json=p_wb, timeout=30)
    print(f"Turn (whiteboard) Status Code: {r_wb.status_code}")
    print(f"Turn (whiteboard) Response: {r_wb.text[:300]}...")
    assert r_wb.status_code == 200, f"Expected 200, got {r_wb.status_code}"
    data_wb = r_wb.json()
    assert "answer" in data_wb, "Missing 'answer' field in response"

    # Subtest 2: input_source="pdf"
    p_pdf = {
        "session_id": "test_e2e_session",
        "subject": "maths",
        "learner_level": "school",
        "language_code": "en-IN",
        "message": "Explain question 1 on this worksheet.",
        "input_source": "pdf",
        "whiteboard_image_base64": jpeg_b64,
        "action": "ask",
        "history": []
    }
    r_pdf = requests.post(f"{BASE_URL}/api/tutor/turn", json=p_pdf, timeout=30)
    print(f"Turn (pdf) Status Code: {r_pdf.status_code}")
    print(f"Turn (pdf) Response: {r_pdf.text[:300]}...")
    assert r_pdf.status_code == 200, f"Expected 200, got {r_pdf.status_code}"
    data_pdf = r_pdf.json()
    assert "answer" in data_pdf, "Missing 'answer' field in response"

    results["c_tutor_turn"] = "PASS"
except Exception as e:
    print(f"TEST (c) FAILED: {e}")
    results["c_tutor_turn"] = f"FAIL: {e}"

# Test (d): POST /api/voice/speak
print("\n--- TEST (d): POST /api/voice/speak ---")
try:
    p_speak = {
        "text": "Hello, 2x equals 8, therefore x equals 4.",
        "language_code": "en-IN"
    }
    r_speak = requests.post(f"{BASE_URL}/api/voice/speak", json=p_speak, timeout=25)
    print(f"Speak Status Code: {r_speak.status_code}")
    content_type = r_speak.headers.get("content-type", "")
    print(f"Content-Type: {content_type}")
    if r_speak.status_code == 200:
        assert "audio/wav" in content_type or r_speak.content.startswith(b"RIFF"), "Expected WAV audio payload"
        print(f"Received {len(r_speak.content)} bytes of playable WAV audio!")
        results["d_voice_speak"] = "PASS (200 Audio WAV)"
    else:
        assert r_speak.status_code != 500, f"Server returned 500 internal error: {r_speak.text}"
        err = r_speak.json()
        print(f"Clean structured error response: {err}")
        assert "error" in err, "Expected clean structured error object"
        results["d_voice_speak"] = f"PASS ({r_speak.status_code} Structured Error)"
except Exception as e:
    print(f"TEST (d) FAILED: {e}")
    results["d_voice_speak"] = f"FAIL: {e}"

# Test (e): POST /api/voice/transcribe
print("\n--- TEST (e): POST /api/voice/transcribe ---")
try:
    wav_bytes = create_16k_mono_wav_bytes()
    files = {
        "audio_file": ("test_silence.wav", wav_bytes, "audio/wav")
    }
    data = {
        "language_code": "en-IN"
    }
    r_tr = requests.post(f"{BASE_URL}/api/voice/transcribe", files=files, data=data, timeout=25)
    print(f"Transcribe Status Code: {r_tr.status_code}")
    print(f"Transcribe Response: {r_tr.text[:300]}")
    assert r_tr.status_code != 500, f"Server returned 500 internal crash: {r_tr.text}"
    if r_tr.status_code in (200, 201):
        tr_data = r_tr.json()
        print(f"Transcript received: {tr_data}")
        results["e_voice_transcribe"] = "PASS (200 Transcript)"
    else:
        err = r_tr.json()
        print(f"Clean structured error response: {err}")
        assert "error" in err, "Expected clean structured error object"
        results["e_voice_transcribe"] = f"PASS ({r_tr.status_code} Structured Error)"
except Exception as e:
    print(f"TEST (e) FAILED: {e}")
    results["e_voice_transcribe"] = f"FAIL: {e}"

print("\n===============================")
print("SMOKE TEST SUMMARY:")
all_passed = True
for k, v in results.items():
    print(f"  {k}: {v}")
    if not v.startswith("PASS"):
        all_passed = False

if all_passed:
    print("\n✅ ALL 5 SMOKE TESTS PASSED!")
    sys.exit(0)
else:
    print("\n❌ SOME SMOKE TESTS FAILED!")
    sys.exit(1)
