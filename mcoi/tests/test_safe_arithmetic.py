"""Purpose: comprehensive boundary tests for the safe arithmetic evaluator.
Governance scope: arithmetic security boundary tests only.
Dependencies: safe_arithmetic module.
Invariants: only literal numeric arithmetic; bounded expressions; bounded results.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.safe_arithmetic import SafeArithmeticError, evaluate_expression


# --- Happy path ---


@pytest.mark.parametrize("expr,expected", [
    ("2 + 3", 5),
    ("10 - 4", 6),
    ("3 * 7", 21),
    ("15 / 4", 3.75),
    ("15 // 4", 3),
    ("17 % 5", 2),
    ("2 ** 10", 1024),
    ("-42", -42),
    ("+7", 7),
    ("(2 + 3) * 4", 20),
    ("0", 0),
    ("1.5 + 2.5", 4.0),
])
def test_valid_expressions(expr: str, expected: int | float) -> None:
    assert evaluate_expression(expr) == expected


# --- Security: rejected constructs ---


@pytest.mark.parametrize("expr", [
    "__import__('os')",
    "eval('1+1')",
    "open('/etc/passwd')",
    "os.system('ls')",
    "lambda: 1",
    "[1, 2, 3]",
    "{'a': 1}",
    "x + 1",
    "print(1)",
])
def test_rejects_unsafe_expressions(expr: str) -> None:
    with pytest.raises(SafeArithmeticError):
        evaluate_expression(expr)


# --- Boundary: expression length ---


def test_rejects_expression_exceeding_max_length() -> None:
    long_expr = "1 + " * 100  # 400 chars, exceeds 256
    with pytest.raises(SafeArithmeticError, match="exceeds maximum length"):
        evaluate_expression(long_expr)


def test_accepts_expression_within_length() -> None:
    # Short expression well within limits
    expr = "1 + 2 + 3 + 4 + 5"
    result = evaluate_expression(expr)
    assert result == 15


# --- Boundary: node count ---


def test_rejects_deeply_nested_expression() -> None:
    # More than 64 AST nodes
    expr = "(" * 35 + "1" + "+1)" * 35  # Many nested nodes
    with pytest.raises(SafeArithmeticError):
        evaluate_expression(expr)


# --- Boundary: literal bounds ---


def test_rejects_literal_exceeding_max() -> None:
    with pytest.raises(SafeArithmeticError, match="exceeds safe bounds"):
        evaluate_expression("999999999999999")  # > 10**12


def test_accepts_literal_at_boundary() -> None:
    result = evaluate_expression("999999999999")  # 10**12 - 1
    assert result == 999999999999


# --- Boundary: exponent bounds ---


def test_rejects_large_exponent() -> None:
    with pytest.raises(SafeArithmeticError, match="exceeds safe bounds"):
        evaluate_expression("2 ** 100")  # exponent > 12


def test_accepts_exponent_at_boundary() -> None:
    result = evaluate_expression("2 ** 12")
    assert result == 4096


# --- Boundary: result bounds ---


def test_rejects_result_exceeding_max() -> None:
    # 10**12 * 10**12 = 10**24 > 10**18
    with pytest.raises(SafeArithmeticError):
        evaluate_expression("999999999999 * 999999999999")


# --- Edge cases ---


def test_empty_expression() -> None:
    with pytest.raises(SafeArithmeticError):
        evaluate_expression("")


def test_whitespace_only() -> None:
    with pytest.raises(SafeArithmeticError):
        evaluate_expression("   ")


def test_division_by_zero() -> None:
    with pytest.raises(SafeArithmeticError):
        evaluate_expression("1 / 0")


def test_float_division_by_zero() -> None:
    with pytest.raises(SafeArithmeticError):
        evaluate_expression("1.0 / 0.0")


def test_modulo_by_zero() -> None:
    with pytest.raises(SafeArithmeticError):
        evaluate_expression("5 % 0")


def test_negative_result() -> None:
    assert evaluate_expression("-5 * 3") == -15


def test_nested_parentheses() -> None:
    assert evaluate_expression("((((1 + 2))))") == 3


def test_decimal_precision() -> None:
    result = evaluate_expression("0.1 + 0.2")
    assert abs(result - 0.3) < 1e-10
