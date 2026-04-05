"""Purpose: deterministic bounded arithmetic evaluation for utility tools.
Governance scope: expression parsing and numeric evaluation only.
Dependencies: Python AST and math primitives.
Invariants:
  - Only literal numeric arithmetic is permitted.
  - Function calls, attribute access, and names are rejected.
  - Expression size and exponent growth are bounded.
  - Results are finite and remain within safe numeric limits.
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Callable


class SafeArithmeticError(ValueError):
    """Raised when an arithmetic expression violates evaluator constraints."""


_MAX_EXPRESSION_LENGTH = 256
_MAX_NODE_COUNT = 64
_MAX_ABS_LITERAL = 10**12
_MAX_ABS_RESULT = 10**18
_MAX_ABS_EXPONENT = 12

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _validate_numeric(value: object, *, label: str, limit: int) -> int | float:
    """Validate that a value is a bounded numeric scalar."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SafeArithmeticError("numeric value must be a scalar")
    if isinstance(value, float) and not math.isfinite(value):
        raise SafeArithmeticError("numeric value must be finite")
    if abs(value) > limit:
        raise SafeArithmeticError("numeric value exceeds safe bounds")
    return value


def _evaluate_node(node: ast.AST) -> int | float:
    """Evaluate a restricted arithmetic AST node."""
    if isinstance(node, ast.Constant):
        return _validate_numeric(node.value, label="literal", limit=_MAX_ABS_LITERAL)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPERATORS:
            raise SafeArithmeticError("unary operator is not allowed")
        operand = _evaluate_node(node.operand)
        return _validate_numeric(
            _UNARY_OPERATORS[op_type](operand),
            label="result",
            limit=_MAX_ABS_RESULT,
        )

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINARY_OPERATORS:
            raise SafeArithmeticError("binary operator is not allowed")
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if op_type is ast.Pow:
            _validate_numeric(right, label="exponent", limit=_MAX_ABS_EXPONENT)
        try:
            value = _BINARY_OPERATORS[op_type](left, right)
        except ZeroDivisionError as exc:
            raise SafeArithmeticError("division by zero") from exc
        return _validate_numeric(value, label="result", limit=_MAX_ABS_RESULT)

    raise SafeArithmeticError("unsupported expression")


def evaluate_expression(expression: str) -> int | float:
    """Evaluate a bounded arithmetic expression."""
    if not isinstance(expression, str):
        raise SafeArithmeticError("expression must be a string")
    normalized = expression.strip()
    if not normalized:
        raise SafeArithmeticError("expression is empty")
    if len(normalized) > _MAX_EXPRESSION_LENGTH:
        raise SafeArithmeticError("expression exceeds maximum length")

    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise SafeArithmeticError("expression syntax is invalid") from exc

    if len(tuple(ast.walk(tree))) > _MAX_NODE_COUNT:
        raise SafeArithmeticError("expression is too complex")

    result = _evaluate_node(tree.body)
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result
