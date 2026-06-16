from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_universal_symbol_kernel import (
    DEFAULT_SCHEMA_PATH,
    DEFAULT_SYMBOL_PATH,
    UniversalSymbolValidationError,
    validate_universal_symbol_kernel,
)


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "symbol.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def test_foundation_universal_symbol_kernel_validates() -> None:
    report = validate_universal_symbol_kernel()
    assert report["valid"] is True
    assert report["symbol_version"] == "universal_symbol.v1"
    assert report["authority_denial_count"] == 9


def test_rejects_connector_authority_drift(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_authority_boundary"]["connector_call_performed"] = True
    with pytest.raises(UniversalSymbolValidationError, match="connector_call_performed"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_terminal_closure_drift(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_proof"]["terminal_closure_ref"] = "closure://blocked"
    with pytest.raises(UniversalSymbolValidationError, match="terminal closure"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolValidationError, match="evidence_ref_count drift"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)
