#!/usr/bin/env python3
"""Reject dynamic outward-facing contract strings in mcoi_runtime.

This guard scans ``mcoi/mcoi_runtime`` for dynamic string interpolation used in
public-facing fields such as ``message``, ``detail``, ``reason``, ``title``,
``description``, ``rationale``, ``attempted_action``, and
``suggested_action``.

The goal is narrow: prevent new reflective leakage of ids, labels, statuses,
timestamps, thresholds, or caller-supplied values from re-entering outward-
facing runtime and contract surfaces.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOT = REPO_ROOT / "mcoi" / "mcoi_runtime"
OUTWARD_FACING_FIELDS = frozenset({
    "attempted_action",
    "description",
    "detail",
    "message",
    "rationale",
    "reason",
    "suggested_action",
    "title",
})


@dataclass(frozen=True)
class Violation:
    """A dynamic outward-facing contract string."""

    path: Path
    line: int
    field: str
    context: str
    expression: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _is_dynamic_string_expr(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"format", "join"}:
            return True
        return False
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mod):
            return True
        if isinstance(node.op, ast.Add):
            return (
                _is_dynamic_string_expr(node.left)
                or _is_dynamic_string_expr(node.right)
                or (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str))
                or (isinstance(node.right, ast.Constant) and isinstance(node.right.value, str))
            )
        return False
    if isinstance(node, ast.IfExp):
        return _is_dynamic_string_expr(node.body) or _is_dynamic_string_expr(node.orelse)
    return False


def _context_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        try:
            return ast.unparse(node.func)
        except Exception:
            return type(node.func).__name__
    return "<dict>"


def scan_source(source: str, display_path: Path) -> list[Violation]:
    """Return dynamic outward-facing contract strings in one source blob."""
    tree = ast.parse(source, filename=str(display_path))
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            context = _context_name(node)
            for keyword in node.keywords:
                if keyword.arg not in OUTWARD_FACING_FIELDS:
                    continue
                if not _is_dynamic_string_expr(keyword.value):
                    continue
                expression = ast.get_source_segment(source, keyword.value) or "<dynamic>"
                violations.append(Violation(
                    path=display_path,
                    line=keyword.value.lineno,
                    field=keyword.arg,
                    context=context,
                    expression=expression.strip(),
                ))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or key.value not in OUTWARD_FACING_FIELDS:
                    continue
                if not _is_dynamic_string_expr(value):
                    continue
                expression = ast.get_source_segment(source, value) or "<dynamic>"
                violations.append(Violation(
                    path=display_path,
                    line=value.lineno,
                    field=str(key.value),
                    context="<dict>",
                    expression=expression.strip(),
                ))
    return violations


def scan_path(path: Path) -> list[Violation]:
    return scan_source(_read_text(path), path)


def iter_python_sources(root: Path) -> Iterable[Path]:
    yield from sorted(root.rglob("*.py"))


def main() -> int:
    all_violations: list[Violation] = []
    for path in iter_python_sources(TARGET_ROOT):
        rel_path = path.relative_to(REPO_ROOT)
        all_violations.extend(scan_source(_read_text(path), rel_path))

    if all_violations:
        for violation in all_violations:
            print(
                f"{violation.path}:{violation.line}: "
                f"{violation.field} uses dynamic string in {violation.context}: "
                f"{violation.expression}"
            )
        print(f"TOTAL={len(all_violations)}")
        return 1

    print("TOTAL=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
