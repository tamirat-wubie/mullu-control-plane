"""Witnesses for the reflective contract guard script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_guard_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "validate_reflective_contracts.py"
    spec = importlib.util.spec_from_file_location(
        "validate_reflective_contracts",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dynamic_keyword_message_is_flagged() -> None:
    guard = _load_guard_module()
    source = """
record = Problem(
    message=f"resource {resource_id} failed validation",
    detail="bounded detail",
)
"""
    violations = guard.scan_source(source, Path("sample.py"))
    assert len(violations) == 1
    assert violations[0].field == "message"
    assert violations[0].line == 3


def test_literal_keyword_message_is_allowed() -> None:
    guard = _load_guard_module()
    source = """
record = Problem(
    message="bounded validation failure",
    description="bounded description",
)
"""
    violations = guard.scan_source(source, Path("sample.py"))
    assert violations == []


def test_plain_content_assignment_is_out_of_scope() -> None:
    guard = _load_guard_module()
    source = """
content = f"{prefix}:{content_hash}"
record = Problem(title="bounded title")
"""
    violations = guard.scan_source(source, Path("sample.py"))
    assert violations == []


def test_dynamic_reason_dict_entry_is_flagged() -> None:
    guard = _load_guard_module()
    source = """
payload = {
    "reason": f"tenant {tenant_id} mismatch",
    "message": "bounded",
}
"""
    violations = guard.scan_source(source, Path("sample.py"))
    assert len(violations) == 1
    assert violations[0].field == "reason"
