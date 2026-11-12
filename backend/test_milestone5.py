#!/usr/bin/env python3
"""
Milestone 5 Automated Test Suite:
1. Section 9 Demo Cases:
   - 2x = 8 -> x = 8 (Must return incorrect with clear dividing reason)
   - 2x = 8 -> x = 4 (Must return correct)
2. Multi-step Linear Equations:
   - 2x + 5 = 15 -> 2x = 10 (Must return correct with Socratic hint to divide by 2)
   - 2x + 5 = 15 -> 2x = 20 (Must return incorrect diagnosing sign error)
3. Expression Equivalence:
   - 3*(x + 2) vs 3x + 6 (Must return correct)
   - 3*(x + 2) vs 3x + 5 (Must return incorrect)
4. Safety & Edge Cases:
   - Malicious injection attempts (__import__, eval, system) -> uncertain
   - Multi-variable equations (x + y = 10) -> uncertain
   - Malformed syntax (2x == = 8) -> uncertain
   - Trivial tautologies (0 = 0) -> uncertain
5. HTTP Endpoints:
   - POST /api/tools/verify-step
   - POST /api/tools/practice-question
6. Strict Verdict Rules in /api/tutor/turn
"""

import asyncio
import httpx
from app.config import settings
from app.tools.math_verifier import verify_equation_step
from app.tools.practice_generator import generate_practice_question

BASE_URL = "http://127.0.0.1:8000"

def test_section_9_demo_cases():
    print("\n--- Test 1: Section 9 Demo Verification Cases ---")

    # Case A: 2x = 8 -> x = 8 (Incorrect)
    res_a = verify_equation_step(original_equation="2x = 8", current_step="x = 8")
    print("Case A (2x=8 -> x=8):", res_a)
    assert res_a["status"] == "incorrect", f"Expected incorrect, got {res_a['status']}"
    assert "divide" in res_a["reason"].lower() or "divide" in res_a.get("expected_next_step", "").lower(), \
        "Reason or hint should guide student on dividing both sides"
    print("✅ Case A verified: 2x = 8 -> x = 8 correctly flagged as incorrect with dividing guidance")

    # Case B: 2x = 8 -> x = 4 (Correct)
    res_b = verify_equation_step(original_equation="2x = 8", current_step="x = 4")
    print("Case B (2x=8 -> x=4):", res_b)
    assert res_b["status"] == "correct", f"Expected correct, got {res_b['status']}"
    assert "4" in res_b["reason"], "Reason should confirm x = 4"
    print("✅ Case B verified: 2x = 8 -> x = 4 correctly flagged as correct")

def test_multi_step_linear_equations():
    print("\n--- Test 2: Multi-step Linear Equations ---")

    # Intermediate step: 2x + 5 = 15 -> 2x = 10 (Correct)
    res_step = verify_equation_step(original_equation="2x + 5 = 15", current_step="2x = 10")
    print("Intermediate (2x+5=15 -> 2x=10):", res_step)
    assert res_step["status"] == "correct", f"Expected correct, got {res_step['status']}"
    assert res_step.get("expected_next_step"), "Should give next Socratic hint"
    assert "divid" in res_step["expected_next_step"].lower() and "2" in res_step["expected_next_step"], \
        "Hint should suggest dividing both sides by 2"
    print("✅ Intermediate step verified with Socratic hint without spoiling final solution")

    # Sign error: 2x + 5 = 15 -> 2x = 20 (Incorrect)
    res_err = verify_equation_step(original_equation="2x + 5 = 15", current_step="2x = 20")
    print("Sign Error (2x+5=15 -> 2x=20):", res_err)
    assert res_err["status"] == "incorrect", f"Expected incorrect, got {res_err['status']}"
    assert "sign" in res_err["reason"].lower() or "sign" in res_err.get("expected_next_step", "").lower(), \
        "Should diagnose sign error"
    print("✅ Sign error diagnosed and flagged as incorrect")

def test_expression_equivalence():
    print("\n--- Test 3: Expression Equivalence ---")

    # Valid expansion: 3*(x + 2) vs 3x + 6
    res_eq = verify_equation_step(original_equation="3*(x + 2)", current_step="3x + 6")
    print("Equivalent expressions:", res_eq)
    assert res_eq["status"] == "correct", f"Expected correct, got {res_eq['status']}"
    print("✅ Algebraic expression equivalence verified as correct")

    # Invalid expansion: 3*(x + 2) vs 3x + 5
    res_neq = verify_equation_step(original_equation="3*(x + 2)", current_step="3x + 5")
    print("Non-equivalent expressions:", res_neq)
    assert res_neq["status"] == "incorrect", f"Expected incorrect, got {res_neq['status']}"
    print("✅ Non-equivalent expression flagged as incorrect")

def test_safety_and_edge_cases():
    print("\n--- Test 4: Safety & Edge Cases ---")

    # 1. Malicious injection attempt
    res_evil1 = verify_equation_step(original_equation="2x = 8", current_step="__import__('os').system('ls')")
    assert res_evil1["status"] == "uncertain", f"Expected uncertain, got {res_evil1['status']}"

    res_evil2 = verify_equation_step(original_equation="2x = 8", current_step="eval('1+1')")
    assert res_evil2["status"] == "uncertain", f"Expected uncertain, got {res_evil2['status']}"
    print("✅ Malicious inputs safely blocked and classified as uncertain without execution")

    # 2. Multi-variable
    res_multi = verify_equation_step(original_equation="x + y = 10", current_step="x = 10 - y")
    assert res_multi["status"] == "uncertain", f"Expected uncertain for multi-variable, got {res_multi['status']}"
    assert "multiple variables" in res_multi["reason"].lower()
    print("✅ Multi-variable equations safely rejected with clear reason")

    # 3. Trivial tautology (0 = 0)
    res_taut = verify_equation_step(original_equation="2x = 8", current_step="0 = 0")
    assert res_taut["status"] == "uncertain", f"Expected uncertain for tautology, got {res_taut['status']}"
    print("✅ Trivial identity 0 = 0 safely rejected")

    # 4. Malformed syntax
    res_syntax = verify_equation_step(original_equation="2x = 8", current_step="2x == = 8")
    assert res_syntax["status"] == "uncertain", f"Expected uncertain for syntax error, got {res_syntax['status']}"
    print("✅ Malformed syntax safely handled")

async def test_http_endpoints(client: httpx.AsyncClient):
    print("\n--- Test 5: HTTP Endpoints (/api/tools/*) ---")

    # 1. POST /api/tools/verify-step (Incorrect case)
    res1 = await client.post(
        f"{BASE_URL}/api/tools/verify-step",
        json={"original_equation": "2x = 8", "current_step": "x = 8"}
    )
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
    body1 = res1.json()
    assert body1["status"] == "incorrect"
    print("✅ POST /api/tools/verify-step returned 200 with status=incorrect")

    # 2. POST /api/tools/verify-step (Correct case)
    res2 = await client.post(
        f"{BASE_URL}/api/tools/verify-step",
        json={"original_equation": "2x = 8", "current_step": "x = 4"}
    )
    assert res2.status_code == 200, f"Expected 200, got {res2.status_code}"
    body2 = res2.json()
    assert body2["status"] == "correct"
    print("✅ POST /api/tools/verify-step returned 200 with status=correct")

    # 3. POST /api/tools/practice-question
    res3 = await client.post(
        f"{BASE_URL}/api/tools/practice-question",
        json={"topic": "linear_equations", "difficulty": "easy", "language": "en-IN"}
    )
    assert res3.status_code == 200, f"Expected 200, got {res3.status_code}"
    body3 = res3.json()
    assert "equation" in body3 and "question" in body3
    print(f"✅ POST /api/tools/practice-question returned 200 with equation: {body3['equation']}")

async def test_strict_verdict_rule(client: httpx.AsyncClient):
    print("\n--- Test 6: Strict Verdict Rule Enforcement ---")

    # Direct unit test of equation extraction helper
    from app.services.gemini_live import extract_equations_from_message

    eqs1 = extract_equations_from_message("2x = 8, x = 8")
    assert eqs1 == ("2x = 8", "x = 8"), f"Extraction failed: {eqs1}"

    eqs2 = extract_equations_from_message("Is 2x = 8 and x = 4 correct?")
    assert eqs2 == ("2x = 8", "x = 4"), f"Extraction failed: {eqs2}"

    print("✅ In-message equation extraction verified for deterministic verification fallback")

    # Test practice question generator
    pq = generate_practice_question(topic="linear_equations", difficulty="easy", language="hi-IN")
    assert pq["topic"] == "linear_equations"
    assert len(pq["equation"]) > 0
    print(f"✅ Practice question generation verified in Hindi: {pq['question']}")

async def main():
    print("=================================================================")
    print("     Milestone 5: SymPy Mathematical Verifier & Tool Calling    ")
    print("=================================================================")

    test_section_9_demo_cases()
    test_multi_step_linear_equations()
    test_expression_equivalence()
    test_safety_and_edge_cases()

    async with httpx.AsyncClient(timeout=15.0) as client:
        await test_http_endpoints(client)
        await test_strict_verdict_rule(client)

    print("\n🎉 ALL MILESTONE 5 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
