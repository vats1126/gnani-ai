import logging
import re
from typing import Dict, Any, Optional, Set
import sympy
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

logger = logging.getLogger(__name__)

# Strict character allowlist for math expressions
ALLOWED_PATTERN = re.compile(r"^[0-9a-zA-Z_+\-*/^=().,\s]+$")

# Prohibited keywords to block any injection attempt
FORBIDDEN_TOKENS = [
    "__", "import", "eval", "exec", "lambda", "system",
    "os.", "sys.", "open", "builtins", "getattr", "setattr"
]

# Safe transformations for sympy parsing
TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# Safe global dictionary disabling arbitrary functions and builtins
SAFE_GLOBALS = {
    "Symbol": sympy.Symbol,
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "Rational": sympy.Rational,
}

ALLOWED_VARIABLE_NAMES = {"x", "y", "z", "a", "b", "c", "n", "t"}

def _sanitize_input(text: str) -> Optional[str]:
    """
    Sanitizes math input strings.
    Replaces unicode math symbols, normalizes operators, and validates against allowlist.
    Returns normalized string, or None if invalid or unsafe.
    """
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()
    if len(cleaned) == 0 or len(cleaned) > 120:
        return None

    # Replace unicode math symbols
    cleaned = cleaned.replace("−", "-").replace("×", "*").replace("÷", "/")
    # Normalize double equals (==) to single (=)
    cleaned = re.sub(r"==+", "=", cleaned)

    # Check allowlist
    if not ALLOWED_PATTERN.match(cleaned):
        return None

    # Check forbidden tokens
    lower_cleaned = cleaned.lower()
    for tok in FORBIDDEN_TOKENS:
        if tok in lower_cleaned:
            return None

    return cleaned

def _safe_parse_expr(expr_str: str, allowed_vars: Set[str]) -> sympy.Expr:
    """
    Safely parses an expression using sympy_parser with strict symbol checks.
    """
    parsed = parse_expr(
        expr_str,
        transformations=TRANSFORMATIONS,
        global_dict=SAFE_GLOBALS,
        evaluate=True
    )

    # Enforce allowed symbols
    for sym in parsed.free_symbols:
        if sym.name.lower() not in allowed_vars:
            raise ValueError(f"Unsupported variable '{sym.name}'. Single-letter variables supported.")

    return parsed

def _diagnose_algebraic_mistake(
    eq_b: sympy.Eq,
    eq_c: sympy.Eq,
    target_var: sympy.Symbol,
    sol_b: Any,
    sol_c: Any
) -> Dict[str, str]:
    """
    Analyzes common algebraic mistakes when an equation step is incorrect.
    """
    try:
        poly_b = sympy.Poly(eq_b.lhs - eq_b.rhs, target_var)
        poly_c = sympy.Poly(eq_c.lhs - eq_c.rhs, target_var)

        if poly_b.degree() == 1 and poly_c.degree() == 1:
            coeffs_b = poly_b.all_coeffs()  # [a, c] for a*x + c = 0
            coeffs_c = poly_c.all_coeffs()

            a_b, c_b = coeffs_b[0], coeffs_b[1]
            a_c, c_c = coeffs_c[0], coeffs_c[1]

            # Case 1: Divided/multiplied only one side (e.g. 2x = 8 -> x = 8)
            if c_b == c_c and a_b != a_c:
                factor = a_b / a_c
                return {
                    "reason": f"In '{eq_b.lhs} = {eq_b.rhs}', you adjusted the coefficient of {target_var.name} by a factor of {factor}, but did not apply the same operation to the other side.",
                    "hint": f"Remember the golden rule of algebra: whatever operation you do to one side of the equals sign, you must do to the other side as well. Divide both sides by {a_b}."
                }

            # Case 2: Sign error moving constant across '=' (e.g. 2x + 5 = 15 -> 2x = 20)
            if a_b == a_c and c_b != c_c:
                return {
                    "reason": "It looks like there was a sign error when moving a constant term across the equals sign.",
                    "hint": "Remember that adding a term on one side becomes subtracting on the other side. Check your signs when moving numbers."
                }

        sol_b_val = list(sol_b)[0] if hasattr(sol_b, '__iter__') and len(sol_b) == 1 else sol_b
        sol_c_val = list(sol_c)[0] if hasattr(sol_c, '__iter__') and len(sol_c) == 1 else sol_c

        return {
            "reason": f"This step is mathematically incorrect. The solution changed from {sol_b_val} to {sol_c_val}.",
            "hint": "Review the arithmetic or algebraic operation you performed on both sides of the equation."
        }
    except Exception:
        return {
            "reason": "This step does not logically follow from the previous equation.",
            "hint": "Double-check your calculations on both sides of the equals sign."
        }

def _generate_socratic_hint(eq: sympy.Eq, target_var: sympy.Symbol) -> str:
    """
    Generates a Socratic hint for a valid intermediate step without spoiling the final answer.
    """
    try:
        poly = sympy.Poly(eq.lhs - eq.rhs, target_var)
        if poly.degree() == 1:
            a, c = poly.all_coeffs()[0], poly.all_coeffs()[1]
            if a != 1:
                return f"Now isolate the variable '{target_var.name}' by dividing both sides by {a}."
            if c != 0:
                op = "subtract" if c > 0 else "add"
                return f"Now {op} {abs(c)} on both sides to get the variable by itself."
    except Exception:
        pass
    return f"Keep going! What is the next operation to isolate '{target_var.name}'?"

def verify_equation_step(
    original_equation: str,
    previous_step: str = "",
    current_step: str = "",
    variable: str = "x"
) -> Dict[str, Any]:
    """
    Deterministically verifies an algebraic equation step using SymPy CAS.

    Args:
        original_equation: The starting problem equation (e.g. "2x = 8" or "2x + 5 = 15")
        previous_step: The intermediate step directly preceding current_step (optional)
        current_step: The student's newly submitted equation step to verify (e.g. "x = 4" or "x = 8")
        variable: The primary variable being solved for (default "x")

    Returns:
        dict: {
            "status": "correct" | "incorrect" | "uncertain",
            "reason": str,
            "expected_next_step": Optional[str]
        }
    """
    baseline_raw = (previous_step or original_equation or "").strip()
    current_raw = (current_step or "").strip()

    baseline_str = _sanitize_input(baseline_raw)
    current_str = _sanitize_input(current_raw)

    if not baseline_str or not current_str:
        return {
            "status": "uncertain",
            "reason": "Expression is empty, exceeds 120 characters, or contains disallowed characters.",
            "expected_next_step": None
        }

    allowed_vars = set(ALLOWED_VARIABLE_NAMES)
    if variable:
        allowed_vars.add(variable.strip().lower())

    has_eq_baseline = "=" in baseline_str
    has_eq_current = "=" in current_str

    # Case 1: Both are equations containing '='
    if has_eq_baseline and has_eq_current:
        parts_b = baseline_str.split("=")
        parts_c = current_str.split("=")

        if len(parts_b) != 2 or len(parts_c) != 2:
            return {
                "status": "uncertain",
                "reason": "Equations must contain exactly one '=' equals sign.",
                "expected_next_step": None
            }

        try:
            lhs_b = _safe_parse_expr(parts_b[0], allowed_vars)
            rhs_b = _safe_parse_expr(parts_b[1], allowed_vars)
            lhs_c = _safe_parse_expr(parts_c[0], allowed_vars)
            rhs_c = _safe_parse_expr(parts_c[1], allowed_vars)
        except Exception as e:
            return {
                "status": "uncertain",
                "reason": f"Could not parse equation: {str(e)}",
                "expected_next_step": None
            }

        eq_b = sympy.Eq(lhs_b, rhs_b, evaluate=False)
        eq_c = sympy.Eq(lhs_c, rhs_c, evaluate=False)

        # Collect free symbols across both equations
        symbols = (lhs_b.free_symbols | rhs_b.free_symbols | lhs_c.free_symbols | rhs_c.free_symbols)

        # Subcase 1A: Pure arithmetic equality (no variables, e.g. 5 + 3 = 8)
        if len(symbols) == 0:
            diff_b = sympy.simplify(lhs_b - rhs_b)
            diff_c = sympy.simplify(lhs_c - rhs_c)
            if diff_b == 0 and diff_c == 0:
                return {
                    "status": "correct",
                    "reason": "Arithmetic equation is valid and both sides are equal.",
                    "expected_next_step": None
                }
            else:
                return {
                    "status": "incorrect",
                    "reason": "Arithmetic calculation is incorrect (the left and right sides are not equal).",
                    "expected_next_step": None
                }

        # Subcase 1B: Multi-variable equation (not supported in single-variable linear verifier)
        if len(symbols) > 1:
            var_names = ", ".join(sorted([s.name for s in symbols]))
            return {
                "status": "uncertain",
                "reason": f"Equation contains multiple variables ({var_names}). Only single-variable linear equations are supported.",
                "expected_next_step": None
            }

        target_var = list(symbols)[0]

        # Check for degenerate trivial tautologies like 0 = 0 or x = x
        diff_c = sympy.simplify(lhs_c - rhs_c)
        diff_b = sympy.simplify(lhs_b - rhs_b)

        if diff_c == 0 and diff_b != 0:
            return {
                "status": "uncertain",
                "reason": f"The step simplifies to a trivial identity (like 0 = 0 or {target_var.name} = {target_var.name}) and loses the specific solution.",
                "expected_next_step": f"Keep the variable '{target_var.name}' on one side to solve the equation."
            }

        # Solve both equations using SymPy CAS
        try:
            sol_b = sympy.solveset(eq_b, target_var, domain=sympy.S.Complexes)
            sol_c = sympy.solveset(eq_c, target_var, domain=sympy.S.Complexes)
        except Exception as e:
            return {
                "status": "uncertain",
                "reason": f"Algebraic solver encountered non-standard equation structure: {str(e)}",
                "expected_next_step": None
            }

        # Check for unsolvable or condition sets
        if isinstance(sol_b, sympy.ConditionSet) or isinstance(sol_c, sympy.ConditionSet):
            return {
                "status": "uncertain",
                "reason": "Equation structure is beyond the scope of the standard linear solver.",
                "expected_next_step": None
            }

        if sol_b == sympy.EmptySet:
            return {
                "status": "uncertain",
                "reason": "The baseline equation has no solution in the complex numbers.",
                "expected_next_step": None
            }

        # Comparison of solution sets
        if sol_b == sol_c:
            # Check if variable is fully isolated in current step (e.g. x = 4 or 4 = x)
            is_isolated = (
                (lhs_c == target_var and rhs_c.is_number) or
                (rhs_c == target_var and lhs_c.is_number)
            )

            if is_isolated:
                val = list(sol_c)[0] if len(sol_c) == 1 else sol_c
                return {
                    "status": "correct",
                    "reason": f"Step is correct! The variable '{target_var.name}' is isolated and solved: {target_var.name} = {val}.",
                    "expected_next_step": "Great job! Would you like to practice another problem or try a new equation?"
                }
            else:
                socratic_hint = _generate_socratic_hint(eq_c, target_var)
                return {
                    "status": "correct",
                    "reason": "Valid algebraic step! Both sides maintain mathematical equality.",
                    "expected_next_step": socratic_hint
                }
        else:
            mistake = _diagnose_algebraic_mistake(eq_b, eq_c, target_var, sol_b, sol_c)
            return {
                "status": "incorrect",
                "reason": mistake["reason"],
                "expected_next_step": mistake["hint"]
            }

    # Case 2: Neither has '=' (pure expression equivalence, e.g. 3*(x + 2) vs 3x + 6)
    elif not has_eq_baseline and not has_eq_current:
        try:
            expr_b = _safe_parse_expr(baseline_str, allowed_vars)
            expr_c = _safe_parse_expr(current_str, allowed_vars)
        except Exception as e:
            return {
                "status": "uncertain",
                "reason": f"Could not parse expression: {str(e)}",
                "expected_next_step": None
            }

        diff = sympy.simplify(expr_b - expr_c)
        if diff == 0:
            return {
                "status": "correct",
                "reason": "The expressions are algebraically equivalent.",
                "expected_next_step": None
            }
        else:
            return {
                "status": "incorrect",
                "reason": "The expressions are not equivalent.",
                "expected_next_step": "Check terms and signs when expanding or factoring."
            }

    # Case 3: One contains '=' and the other does not
    else:
        return {
            "status": "uncertain",
            "reason": "Cannot compare an equation with an algebraic expression.",
            "expected_next_step": None
        }

