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
from scripts.validate_universal_symbol_adapter_receipt_persistence_policy import (
    DEFAULT_POLICY_PATH as DEFAULT_PERSISTENCE_POLICY_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_PERSISTENCE_SCHEMA_PATH,
    UniversalSymbolAdapterReceiptPersistencePolicyError,
    validate_universal_symbol_adapter_receipt_persistence_policy,
)
from scripts.validate_universal_symbol_append_audit_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_APPEND_AUDIT_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_APPEND_AUDIT_WITNESS_PATH,
    UniversalSymbolAppendAuditWitnessError,
    validate_universal_symbol_append_audit_witness,
)
from scripts.validate_universal_symbol_receipt_store_authority_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_RECEIPT_STORE_AUTHORITY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_RECEIPT_STORE_AUTHORITY_WITNESS_PATH,
    UniversalSymbolReceiptStoreAuthorityWitnessError,
    validate_universal_symbol_receipt_store_authority_witness,
)
from scripts.validate_universal_symbol_runtime_admission_policy import (
    DEFAULT_POLICY_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_RUNTIME_ADMISSION_SCHEMA_PATH,
    UniversalSymbolRuntimeAdmissionPolicyError,
    validate_universal_symbol_runtime_admission_policy,
)


def _write_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "symbol.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def _write_policy_case(tmp_path: Path, value: dict[str, object]) -> Path:
    case_path = tmp_path / "policy.json"
    case_path.write_text(json.dumps(value), encoding="utf-8")
    return case_path


def test_foundation_universal_symbol_kernel_validates() -> None:
    report = validate_universal_symbol_kernel()
    assert report["valid"] is True
    assert report["symbol_version"] == "universal_symbol.v1"
    assert report["authority_denial_count"] == 9
    assert report["evidence_ref_count"] == 29


def test_foundation_universal_symbol_runtime_admission_policy_validates() -> None:
    report = validate_universal_symbol_runtime_admission_policy()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["admission_decision"] == "blocked"
    assert report["authority_denial_count"] == 9
    assert report["skill_admission_count"] == 4
    assert report["evidence_ref_count"] == 16


def test_foundation_universal_symbol_adapter_receipt_persistence_policy_validates() -> None:
    report = validate_universal_symbol_adapter_receipt_persistence_policy()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["persistence_decision"] == "blocked_pending_receipt_store_authority"
    assert report["authority_denial_count"] == 9
    assert report["projection_source_count"] == 4
    assert report["evidence_ref_count"] == 17


def test_foundation_universal_symbol_receipt_store_authority_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_authority_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["authority_decision"] == "blocked_pending_append_audit_and_store_authority"
    assert report["authority_denial_count"] == 10
    assert report["authority_requirement_count"] == 7
    assert report["append_precondition_count"] == 7
    assert report["evidence_ref_count"] == 15


def test_foundation_universal_symbol_append_audit_witness_validates() -> None:
    report = validate_universal_symbol_append_audit_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["append_audit_decision"] == "blocked_pending_writer_registration_and_replay_evidence"
    assert report["authority_denial_count"] == 10
    assert report["audit_requirement_count"] == 8
    assert report["evidence_ref_count"] == 14


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


def test_runtime_admission_policy_rejects_live_dispatch_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["authority_denials"]["live_dispatch_enabled"] = True
    with pytest.raises(UniversalSymbolRuntimeAdmissionPolicyError, match="live_dispatch_enabled"):
        validate_universal_symbol_runtime_admission_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RUNTIME_ADMISSION_SCHEMA_PATH,
        )


def test_runtime_admission_policy_rejects_receipt_append_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["receipt_policy"]["append_allowed"] = True
    with pytest.raises(UniversalSymbolRuntimeAdmissionPolicyError, match="append_allowed"):
        validate_universal_symbol_runtime_admission_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RUNTIME_ADMISSION_SCHEMA_PATH,
        )


def test_runtime_admission_policy_rejects_skill_admission_upgrade(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["skill_admission_matrix"][0]["admission_state"] = "admitted"
    with pytest.raises(UniversalSymbolRuntimeAdmissionPolicyError, match="schema validation failed"):
        validate_universal_symbol_runtime_admission_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RUNTIME_ADMISSION_SCHEMA_PATH,
        )


def test_runtime_admission_policy_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolRuntimeAdmissionPolicyError, match="evidence_ref_count drift"):
        validate_universal_symbol_runtime_admission_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RUNTIME_ADMISSION_SCHEMA_PATH,
        )


def test_adapter_receipt_persistence_policy_rejects_append_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_PERSISTENCE_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["authority_denials"]["receipt_store_append_performed"] = True
    with pytest.raises(UniversalSymbolAdapterReceiptPersistencePolicyError, match="receipt_store_append_performed"):
        validate_universal_symbol_adapter_receipt_persistence_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PERSISTENCE_SCHEMA_PATH,
        )


def test_adapter_receipt_persistence_policy_rejects_raw_payload_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_PERSISTENCE_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["candidate_receipt_policy"]["raw_payload_allowed"] = True
    with pytest.raises(UniversalSymbolAdapterReceiptPersistencePolicyError, match="raw_payload_allowed"):
        validate_universal_symbol_adapter_receipt_persistence_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PERSISTENCE_SCHEMA_PATH,
        )


def test_adapter_receipt_persistence_policy_rejects_projection_persistence_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_PERSISTENCE_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["admitted_projection_sources"][0]["persistence_allowed"] = True
    with pytest.raises(UniversalSymbolAdapterReceiptPersistencePolicyError, match="persistence_allowed"):
        validate_universal_symbol_adapter_receipt_persistence_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PERSISTENCE_SCHEMA_PATH,
        )


def test_adapter_receipt_persistence_policy_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    policy = json.loads(DEFAULT_PERSISTENCE_POLICY_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(policy)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolAdapterReceiptPersistencePolicyError, match="evidence_ref_count drift"):
        validate_universal_symbol_adapter_receipt_persistence_policy(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PERSISTENCE_SCHEMA_PATH,
        )


def test_receipt_store_authority_witness_rejects_authority_grant_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECEIPT_STORE_AUTHORITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["authority_is_granted"] = True
    changed["authority_denials"]["receipt_store_authority_granted"] = True
    changed["authority_denials"]["receipt_store_append_performed"] = True
    with pytest.raises(UniversalSymbolReceiptStoreAuthorityWitnessError, match="authority_is_granted"):
        validate_universal_symbol_receipt_store_authority_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECEIPT_STORE_AUTHORITY_SCHEMA_PATH,
        )


def test_receipt_store_authority_witness_rejects_append_precondition_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECEIPT_STORE_AUTHORITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["append_preconditions"][0]["append_decision"] = "append_allowed"
    changed["append_preconditions"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreAuthorityWitnessError, match="append_decision"):
        validate_universal_symbol_receipt_store_authority_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECEIPT_STORE_AUTHORITY_SCHEMA_PATH,
        )


def test_receipt_store_authority_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECEIPT_STORE_AUTHORITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["authority_requirements"] = changed["authority_requirements"][1:]
    changed["contract_summary"]["authority_requirement_count"] = len(changed["authority_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreAuthorityWitnessError, match="append-audit-witness"):
        validate_universal_symbol_receipt_store_authority_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECEIPT_STORE_AUTHORITY_SCHEMA_PATH,
        )


def test_receipt_store_authority_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECEIPT_STORE_AUTHORITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreAuthorityWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_authority_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECEIPT_STORE_AUTHORITY_SCHEMA_PATH,
        )


def test_append_audit_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_APPEND_AUDIT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["audit_requirements"] = changed["audit_requirements"][1:]
    changed["contract_summary"]["audit_requirement_count"] = len(changed["audit_requirements"])
    with pytest.raises(UniversalSymbolAppendAuditWitnessError, match="append-sequence-witness"):
        validate_universal_symbol_append_audit_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_APPEND_AUDIT_SCHEMA_PATH,
        )


def test_append_audit_witness_rejects_append_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_APPEND_AUDIT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["append_audit_is_not_append_authority"] = False
    changed["authority_denials"]["receipt_store_append_performed"] = True
    with pytest.raises(UniversalSymbolAppendAuditWitnessError, match="append audit"):
        validate_universal_symbol_append_audit_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_APPEND_AUDIT_SCHEMA_PATH,
        )


def test_append_audit_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_APPEND_AUDIT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["audit_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolAppendAuditWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_append_audit_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_APPEND_AUDIT_SCHEMA_PATH,
        )


def test_append_audit_witness_rejects_candidate_raw_payload_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_APPEND_AUDIT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["candidate_receipt_constraints"]["raw_payload_forbidden"] = False
    with pytest.raises(UniversalSymbolAppendAuditWitnessError, match="raw_payload_forbidden"):
        validate_universal_symbol_append_audit_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_APPEND_AUDIT_SCHEMA_PATH,
        )


def test_append_audit_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_APPEND_AUDIT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolAppendAuditWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_append_audit_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_APPEND_AUDIT_SCHEMA_PATH,
        )
