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
    assert report["evidence_ref_count"] == 10


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


def test_rejects_additional_property_schema_drift(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["silent_extra_field"] = True
    with pytest.raises(UniversalSymbolValidationError, match="schema validation failed"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_bad_symbol_kind_schema_drift(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_identity"]["symbol_kind"] = "runtime_magic"
    with pytest.raises(UniversalSymbolValidationError, match="schema validation failed"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_missing_evidence_file(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["evidence_refs"].append("docs/DOES_NOT_EXIST_UNIVERSAL_SYMBOL.md")
    changed["contract_summary"]["evidence_ref_count"] = len(changed["evidence_refs"])
    with pytest.raises(UniversalSymbolValidationError, match="evidence ref file missing"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_foundation_authority_refs(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_governance"]["authority_refs"].append("authority://runtime-symbol-dispatch")
    with pytest.raises(UniversalSymbolValidationError, match="authority refs"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_foundation_proof_state_upgrade(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_proof"]["proof_state"] = "proven"
    with pytest.raises(UniversalSymbolValidationError, match="proof_state"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_evidence_ref_outside_repository(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["evidence_refs"].append("../outside-universal-symbol-evidence.json")
    changed["contract_summary"]["evidence_ref_count"] = len(changed["evidence_refs"])
    with pytest.raises(UniversalSymbolValidationError, match="escapes repository"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_symbolizable_surface_count_drift(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["contract_summary"]["symbolizable_surface_count"] = 8
    with pytest.raises(UniversalSymbolValidationError, match="symbolizable_surface_count drift"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_blank_relation_ref(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_relations"]["peer_refs"].append("")
    with pytest.raises(UniversalSymbolValidationError, match="schema validation failed"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)


def test_rejects_blank_causal_trace_ref(tmp_path: Path) -> None:
    symbol = json.loads(DEFAULT_SYMBOL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(symbol)
    changed["symbol_causality"]["causal_trace_ref"] = ""
    with pytest.raises(UniversalSymbolValidationError, match="schema validation failed"):
        validate_universal_symbol_kernel(_write_case(tmp_path, changed), DEFAULT_SCHEMA_PATH)
