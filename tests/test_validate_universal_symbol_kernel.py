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
from scripts.validate_universal_symbol_receipt_store_writer_registration_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_WRITER_REGISTRATION_WITNESS_PATH,
    UniversalSymbolReceiptStoreWriterRegistrationWitnessError,
    validate_universal_symbol_receipt_store_writer_registration_witness,
)
from scripts.validate_universal_symbol_receipt_store_writer_identity_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_WRITER_IDENTITY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_WRITER_IDENTITY_WITNESS_PATH,
    UniversalSymbolReceiptStoreWriterIdentityWitnessError,
    validate_universal_symbol_receipt_store_writer_identity_witness,
)
from scripts.validate_universal_symbol_receipt_store_operator_approval_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH,
    UniversalSymbolReceiptStoreOperatorApprovalWitnessError,
    validate_universal_symbol_receipt_store_operator_approval_witness,
)
from scripts.validate_universal_symbol_receipt_store_operator_identity_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_OPERATOR_IDENTITY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_OPERATOR_IDENTITY_WITNESS_PATH,
    UniversalSymbolReceiptStoreOperatorIdentityWitnessError,
    validate_universal_symbol_receipt_store_operator_identity_witness,
)
from scripts.validate_universal_symbol_receipt_store_operator_approval_decision_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_OPERATOR_APPROVAL_DECISION_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_OPERATOR_APPROVAL_DECISION_WITNESS_PATH,
    UniversalSymbolReceiptStoreOperatorApprovalDecisionWitnessError,
    validate_universal_symbol_receipt_store_operator_approval_decision_witness,
)
from scripts.validate_universal_symbol_receipt_store_reapproval_revocation_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_REAPPROVAL_REVOCATION_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_REAPPROVAL_REVOCATION_WITNESS_PATH,
    UniversalSymbolReceiptStoreReapprovalRevocationWitnessError,
    validate_universal_symbol_receipt_store_reapproval_revocation_witness,
)
from scripts.validate_universal_symbol_receipt_store_tenant_scope_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_TENANT_SCOPE_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_TENANT_SCOPE_WITNESS_PATH,
    UniversalSymbolReceiptStoreTenantScopeWitnessError,
    validate_universal_symbol_receipt_store_tenant_scope_witness,
)
from scripts.validate_universal_symbol_receipt_store_writer_duty_scope_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_WRITER_DUTY_SCOPE_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH,
    UniversalSymbolReceiptStoreWriterDutyScopeWitnessError,
    validate_universal_symbol_receipt_store_writer_duty_scope_witness,
)
from scripts.validate_universal_symbol_receipt_store_path_confinement_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_PATH_CONFINEMENT_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_PATH_CONFINEMENT_WITNESS_PATH,
    UniversalSymbolReceiptStorePathConfinementWitnessError,
    validate_universal_symbol_receipt_store_path_confinement_witness,
)
from scripts.validate_universal_symbol_receipt_store_write_path_idempotency_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_WRITE_PATH_IDEMPOTENCY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_WRITE_PATH_IDEMPOTENCY_WITNESS_PATH,
    UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError,
    validate_universal_symbol_receipt_store_write_path_idempotency_witness,
)
from scripts.validate_universal_symbol_receipt_store_durability_replay_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_DURABILITY_REPLAY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_DURABILITY_REPLAY_WITNESS_PATH,
    UniversalSymbolReceiptStoreDurabilityReplayWitnessError,
    validate_universal_symbol_receipt_store_durability_replay_witness,
)
from scripts.validate_universal_symbol_receipt_store_recovery_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_RECOVERY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_RECOVERY_WITNESS_PATH,
    UniversalSymbolReceiptStoreRecoveryWitnessError,
    validate_universal_symbol_receipt_store_recovery_witness,
)
from scripts.validate_universal_symbol_receipt_store_write_path_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_WRITE_PATH_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_WRITE_PATH_WITNESS_PATH,
    UniversalSymbolReceiptStoreWritePathWitnessError,
    validate_universal_symbol_receipt_store_write_path_witness,
)
from scripts.validate_universal_symbol_receipt_store_path_custody_witness import (
    DEFAULT_SCHEMA_PATH as DEFAULT_PATH_CUSTODY_SCHEMA_PATH,
    DEFAULT_WITNESS_PATH as DEFAULT_PATH_CUSTODY_WITNESS_PATH,
    UniversalSymbolReceiptStorePathCustodyWitnessError,
    validate_universal_symbol_receipt_store_path_custody_witness,
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
    assert report["evidence_ref_count"] == 71


def test_foundation_universal_symbol_runtime_admission_policy_validates() -> None:
    report = validate_universal_symbol_runtime_admission_policy()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["admission_decision"] == "blocked"
    assert report["authority_denial_count"] == 9
    assert report["skill_admission_count"] == 4
    assert report["evidence_ref_count"] == 28


def test_foundation_universal_symbol_adapter_receipt_persistence_policy_validates() -> None:
    report = validate_universal_symbol_adapter_receipt_persistence_policy()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["persistence_decision"] == "blocked_pending_receipt_store_authority"
    assert report["authority_denial_count"] == 9
    assert report["projection_source_count"] == 4
    assert report["evidence_ref_count"] == 29


def test_foundation_universal_symbol_receipt_store_authority_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_authority_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["authority_decision"] == "blocked_pending_append_audit_and_store_authority"
    assert report["authority_denial_count"] == 10
    assert report["authority_requirement_count"] == 7
    assert report["append_precondition_count"] == 7
    assert report["evidence_ref_count"] == 33


def test_foundation_universal_symbol_append_audit_witness_validates() -> None:
    report = validate_universal_symbol_append_audit_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["append_audit_decision"] == "blocked_pending_writer_registration_and_replay_evidence"
    assert report["authority_denial_count"] == 10
    assert report["audit_requirement_count"] == 8
    assert report["evidence_ref_count"] == 32


def test_foundation_universal_symbol_receipt_store_writer_registration_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_writer_registration_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["writer_registration_decision"] == "blocked_pending_write_path_and_operator_authority"
    assert report["authority_denial_count"] == 10
    assert report["writer_requirement_count"] == 8
    assert report["evidence_ref_count"] == 31


def test_foundation_universal_symbol_receipt_store_writer_identity_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_writer_identity_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["writer_identity_decision"] == "blocked_pending_operator_tenant_scope_and_recovery_evidence"
    assert report["authority_denial_count"] == 10
    assert report["identity_requirement_count"] == 8
    assert report["evidence_ref_count"] == 31


def test_foundation_universal_symbol_receipt_store_operator_approval_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_operator_approval_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["operator_approval_decision"]
        == "blocked_pending_live_operator_decision_tenant_scope_and_reapproval_evidence"
    )
    assert report["authority_denial_count"] == 11
    assert report["approval_requirement_count"] == 8
    assert report["evidence_ref_count"] == 32


def test_foundation_universal_symbol_receipt_store_operator_identity_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_operator_identity_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["operator_identity_decision"]
        == "blocked_pending_live_identity_binding_tenant_scope_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 13
    assert report["identity_requirement_count"] == 8
    assert report["evidence_ref_count"] == 13


def test_foundation_universal_symbol_receipt_store_operator_approval_decision_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_operator_approval_decision_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["approval_decision"]
        == "blocked_pending_live_operator_identity_scope_reapproval_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 12
    assert report["decision_requirement_count"] == 8
    assert report["evidence_ref_count"] == 16


def test_foundation_universal_symbol_receipt_store_reapproval_revocation_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_reapproval_revocation_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["reapproval_revocation_decision"]
        == "blocked_pending_approval_decision_grant_expiry_revocation_replacement_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 13
    assert report["lifecycle_requirement_count"] == 8
    assert report["evidence_ref_count"] == 16


def test_foundation_universal_symbol_receipt_store_tenant_scope_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_tenant_scope_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["tenant_scope_decision"]
        == "blocked_pending_tenant_actor_binding_partition_and_isolation_evidence"
    )
    assert report["authority_denial_count"] == 12
    assert report["tenant_requirement_count"] == 8
    assert report["evidence_ref_count"] == 28


def test_foundation_universal_symbol_receipt_store_writer_duty_scope_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_writer_duty_scope_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["writer_duty_scope_decision"]
        == "blocked_pending_writer_role_action_bounds_and_separation_evidence"
    )
    assert report["authority_denial_count"] == 13
    assert report["duty_requirement_count"] == 8
    assert report["evidence_ref_count"] == 30


def test_foundation_universal_symbol_receipt_store_path_confinement_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_path_confinement_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["path_confinement_decision"]
        == "blocked_pending_root_namespace_traversal_symlink_partition_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 11
    assert report["confinement_requirement_count"] == 8
    assert report["evidence_ref_count"] == 28


def test_foundation_universal_symbol_receipt_store_write_path_idempotency_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_write_path_idempotency_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["idempotency_decision"]
        == "blocked_pending_key_derivation_digest_replay_and_collision_evidence"
    )
    assert report["authority_denial_count"] == 11
    assert report["idempotency_requirement_count"] == 8
    assert report["evidence_ref_count"] == 29


def test_foundation_universal_symbol_receipt_store_durability_replay_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_durability_replay_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["durability_replay_decision"]
        == "blocked_pending_ordered_replay_digest_crash_window_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 11
    assert report["durability_replay_requirement_count"] == 8
    assert report["evidence_ref_count"] == 28


def test_foundation_universal_symbol_receipt_store_recovery_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_recovery_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert (
        report["recovery_decision"]
        == "blocked_pending_recovery_plan_snapshot_rollback_compensation_and_audit_evidence"
    )
    assert report["authority_denial_count"] == 13
    assert report["recovery_requirement_count"] == 8
    assert report["evidence_ref_count"] == 27


def test_foundation_universal_symbol_receipt_store_path_custody_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_path_custody_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["path_custody_decision"] == "blocked_pending_confinement_idempotency_replay_and_recovery_evidence"
    assert report["authority_denial_count"] == 10
    assert report["custody_requirement_count"] == 8
    assert report["evidence_ref_count"] == 36


def test_foundation_universal_symbol_receipt_store_write_path_witness_validates() -> None:
    report = validate_universal_symbol_receipt_store_write_path_witness()
    assert report["valid"] is True
    assert report["solver_outcome"] == "AwaitingEvidence"
    assert report["write_path_decision"] == "blocked_pending_writer_registration_replay_and_operator_authority"
    assert report["authority_denial_count"] == 10
    assert report["write_path_requirement_count"] == 10
    assert report["evidence_ref_count"] == 39


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


def test_writer_registration_witness_rejects_append_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_registration_is_not_append_authority"] = False
    changed["authority_denials"]["receipt_store_append_performed"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="append authority"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_registration_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_requirements"] = changed["writer_requirements"][1:]
    changed["contract_summary"]["writer_requirement_count"] = len(changed["writer_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="writer-identity-witness"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_registration_witness_rejects_writer_identity_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_scope_constraints"]["writer_identity_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="writer_identity_required"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_registration_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_registration_witness_rejects_writer_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_registration_is_not_append_authority"] = False
    changed["authority_denials"]["receipt_store_writer_registered"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="writer registration"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_registration_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_registration_witness_rejects_scope_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_REGISTRATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_scope_constraints"]["operator_approval_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreWriterRegistrationWitnessError, match="operator_approval_required"):
        validate_universal_symbol_receipt_store_writer_registration_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_REGISTRATION_SCHEMA_PATH,
        )


def test_writer_identity_witness_rejects_registration_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_identity_witness_is_not_registration_authority"] = False
    changed["authority_denials"]["receipt_store_writer_identity_registered"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWriterIdentityWitnessError, match="registration authority"):
        validate_universal_symbol_receipt_store_writer_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_IDENTITY_SCHEMA_PATH,
        )


def test_writer_identity_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["identity_requirements"] = changed["identity_requirements"][1:]
    changed["contract_summary"]["identity_requirement_count"] = len(changed["identity_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreWriterIdentityWitnessError, match="unique-writer-identity"):
        validate_universal_symbol_receipt_store_writer_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_IDENTITY_SCHEMA_PATH,
        )


def test_writer_identity_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["identity_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreWriterIdentityWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_writer_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_IDENTITY_SCHEMA_PATH,
        )


def test_writer_identity_witness_rejects_identity_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["identity_constraints"]["unique_writer_identity_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreWriterIdentityWitnessError, match="unique_writer_identity_required"):
        validate_universal_symbol_receipt_store_writer_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_IDENTITY_SCHEMA_PATH,
        )


def test_writer_identity_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreWriterIdentityWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_writer_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_IDENTITY_SCHEMA_PATH,
        )


def test_operator_approval_witness_rejects_approval_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["operator_approval_witness_is_not_approval_authority"] = False
    changed["authority_denials"]["receipt_store_operator_approval_recorded"] = True
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalWitnessError, match="approval authority"):
        validate_universal_symbol_receipt_store_operator_approval_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
        )


def test_operator_approval_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["approval_requirements"] = changed["approval_requirements"][1:]
    changed["contract_summary"]["approval_requirement_count"] = len(changed["approval_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalWitnessError, match="operator-identity"):
        validate_universal_symbol_receipt_store_operator_approval_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
        )


def test_operator_approval_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["approval_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_operator_approval_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
        )


def test_operator_approval_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["approval_constraints"]["explicit_approval_decision_required"] = False
    with pytest.raises(
        UniversalSymbolReceiptStoreOperatorApprovalWitnessError,
        match="explicit_approval_decision_required",
    ):
        validate_universal_symbol_receipt_store_operator_approval_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
        )


def test_operator_approval_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_operator_approval_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
        )


def test_operator_identity_witness_rejects_identity_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["operator_identity_witness_is_not_identity_authority"] = False
    changed["authority_denials"]["receipt_store_operator_identity_bound"] = True
    with pytest.raises(UniversalSymbolReceiptStoreOperatorIdentityWitnessError, match="identity authority"):
        validate_universal_symbol_receipt_store_operator_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_IDENTITY_SCHEMA_PATH,
        )


def test_operator_identity_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["identity_requirements"] = changed["identity_requirements"][1:]
    changed["contract_summary"]["identity_requirement_count"] = len(changed["identity_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreOperatorIdentityWitnessError, match="live-operator-subject"):
        validate_universal_symbol_receipt_store_operator_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_IDENTITY_SCHEMA_PATH,
        )


def test_operator_identity_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["identity_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreOperatorIdentityWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_operator_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_IDENTITY_SCHEMA_PATH,
        )


def test_operator_identity_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["identity_constraints"]["session_authentication_required"] = False
    with pytest.raises(
        UniversalSymbolReceiptStoreOperatorIdentityWitnessError,
        match="session_authentication_required",
    ):
        validate_universal_symbol_receipt_store_operator_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_IDENTITY_SCHEMA_PATH,
        )


def test_operator_identity_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_IDENTITY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreOperatorIdentityWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_operator_identity_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_IDENTITY_SCHEMA_PATH,
        )


def test_operator_approval_decision_witness_rejects_decision_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_DECISION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["approval_decision_witness_is_not_decision_authority"] = False
    changed["authority_denials"]["receipt_store_approval_decision_recorded"] = True
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalDecisionWitnessError, match="decision authority"):
        validate_universal_symbol_receipt_store_operator_approval_decision_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_DECISION_SCHEMA_PATH,
        )


def test_operator_approval_decision_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_DECISION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["decision_requirements"] = changed["decision_requirements"][1:]
    changed["contract_summary"]["decision_requirement_count"] = len(changed["decision_requirements"])
    with pytest.raises(
        UniversalSymbolReceiptStoreOperatorApprovalDecisionWitnessError,
        match="operator-identity-witness",
    ):
        validate_universal_symbol_receipt_store_operator_approval_decision_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_DECISION_SCHEMA_PATH,
        )


def test_operator_approval_decision_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_DECISION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["decision_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalDecisionWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_operator_approval_decision_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_DECISION_SCHEMA_PATH,
        )


def test_operator_approval_decision_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_DECISION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["decision_constraints"]["explicit_decision_value_required"] = False
    with pytest.raises(
        UniversalSymbolReceiptStoreOperatorApprovalDecisionWitnessError,
        match="explicit_decision_value_required",
    ):
        validate_universal_symbol_receipt_store_operator_approval_decision_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_DECISION_SCHEMA_PATH,
        )


def test_operator_approval_decision_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_DECISION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(
        UniversalSymbolReceiptStoreOperatorApprovalDecisionWitnessError,
        match="evidence_ref_count drift",
    ):
        validate_universal_symbol_receipt_store_operator_approval_decision_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_DECISION_SCHEMA_PATH,
        )


def test_reapproval_revocation_witness_rejects_lifecycle_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_REAPPROVAL_REVOCATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["reapproval_revocation_witness_is_not_lifecycle_authority"] = False
    changed["authority_denials"]["receipt_store_revocation_recorded"] = True
    with pytest.raises(UniversalSymbolReceiptStoreReapprovalRevocationWitnessError, match="lifecycle authority"):
        validate_universal_symbol_receipt_store_reapproval_revocation_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_REAPPROVAL_REVOCATION_SCHEMA_PATH,
        )


def test_reapproval_revocation_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_REAPPROVAL_REVOCATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["lifecycle_requirements"] = changed["lifecycle_requirements"][1:]
    changed["contract_summary"]["lifecycle_requirement_count"] = len(changed["lifecycle_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreReapprovalRevocationWitnessError, match="approval-decision-witness"):
        validate_universal_symbol_receipt_store_reapproval_revocation_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_REAPPROVAL_REVOCATION_SCHEMA_PATH,
        )


def test_reapproval_revocation_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_REAPPROVAL_REVOCATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["lifecycle_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreReapprovalRevocationWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_reapproval_revocation_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_REAPPROVAL_REVOCATION_SCHEMA_PATH,
        )


def test_reapproval_revocation_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_REAPPROVAL_REVOCATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["lifecycle_constraints"]["reapproval_window_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreReapprovalRevocationWitnessError, match="reapproval_window_required"):
        validate_universal_symbol_receipt_store_reapproval_revocation_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_REAPPROVAL_REVOCATION_SCHEMA_PATH,
        )


def test_reapproval_revocation_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_REAPPROVAL_REVOCATION_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreReapprovalRevocationWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_reapproval_revocation_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_REAPPROVAL_REVOCATION_SCHEMA_PATH,
        )


def test_tenant_scope_witness_rejects_tenant_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_TENANT_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["tenant_scope_witness_is_not_tenant_authority"] = False
    changed["authority_denials"]["receipt_store_tenant_scope_bound"] = True
    with pytest.raises(UniversalSymbolReceiptStoreTenantScopeWitnessError, match="tenant authority"):
        validate_universal_symbol_receipt_store_tenant_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_TENANT_SCOPE_SCHEMA_PATH,
        )


def test_tenant_scope_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_TENANT_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["tenant_requirements"] = changed["tenant_requirements"][1:]
    changed["contract_summary"]["tenant_requirement_count"] = len(changed["tenant_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreTenantScopeWitnessError, match="tenant-identity"):
        validate_universal_symbol_receipt_store_tenant_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_TENANT_SCOPE_SCHEMA_PATH,
        )


def test_tenant_scope_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_TENANT_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["tenant_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreTenantScopeWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_tenant_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_TENANT_SCOPE_SCHEMA_PATH,
        )


def test_tenant_scope_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_TENANT_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["tenant_scope_constraints"]["tenant_actor_binding_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreTenantScopeWitnessError, match="tenant_actor_binding_required"):
        validate_universal_symbol_receipt_store_tenant_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_TENANT_SCOPE_SCHEMA_PATH,
        )


def test_tenant_scope_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_TENANT_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreTenantScopeWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_tenant_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_TENANT_SCOPE_SCHEMA_PATH,
        )


def test_writer_duty_scope_witness_rejects_duty_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["writer_duty_scope_witness_is_not_duty_authority"] = False
    changed["authority_denials"]["receipt_store_writer_duty_scope_bound"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWriterDutyScopeWitnessError, match="duty authority"):
        validate_universal_symbol_receipt_store_writer_duty_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_DUTY_SCOPE_SCHEMA_PATH,
        )


def test_writer_duty_scope_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["duty_requirements"] = changed["duty_requirements"][1:]
    changed["contract_summary"]["duty_requirement_count"] = len(changed["duty_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreWriterDutyScopeWitnessError, match="writer-role-identity"):
        validate_universal_symbol_receipt_store_writer_duty_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_DUTY_SCOPE_SCHEMA_PATH,
        )


def test_writer_duty_scope_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["duty_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreWriterDutyScopeWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_writer_duty_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_DUTY_SCOPE_SCHEMA_PATH,
        )


def test_writer_duty_scope_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["duty_scope_constraints"]["separation_of_duties_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreWriterDutyScopeWitnessError, match="separation_of_duties_required"):
        validate_universal_symbol_receipt_store_writer_duty_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_DUTY_SCOPE_SCHEMA_PATH,
        )


def test_writer_duty_scope_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITER_DUTY_SCOPE_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreWriterDutyScopeWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_writer_duty_scope_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITER_DUTY_SCOPE_SCHEMA_PATH,
        )


def test_path_confinement_witness_rejects_path_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CONFINEMENT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["path_confinement_witness_is_not_path_authority"] = False
    changed["authority_denials"]["receipt_store_path_confinement_bound"] = True
    with pytest.raises(UniversalSymbolReceiptStorePathConfinementWitnessError, match="path authority"):
        validate_universal_symbol_receipt_store_path_confinement_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CONFINEMENT_SCHEMA_PATH,
        )


def test_path_confinement_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CONFINEMENT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["confinement_requirements"] = changed["confinement_requirements"][1:]
    changed["contract_summary"]["confinement_requirement_count"] = len(changed["confinement_requirements"])
    with pytest.raises(UniversalSymbolReceiptStorePathConfinementWitnessError, match="canonical-root"):
        validate_universal_symbol_receipt_store_path_confinement_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CONFINEMENT_SCHEMA_PATH,
        )


def test_path_confinement_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CONFINEMENT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["confinement_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStorePathConfinementWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_path_confinement_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CONFINEMENT_SCHEMA_PATH,
        )


def test_path_confinement_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CONFINEMENT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["path_confinement_constraints"]["path_traversal_denial_required"] = False
    with pytest.raises(UniversalSymbolReceiptStorePathConfinementWitnessError, match="path_traversal_denial_required"):
        validate_universal_symbol_receipt_store_path_confinement_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CONFINEMENT_SCHEMA_PATH,
        )


def test_path_confinement_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CONFINEMENT_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStorePathConfinementWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_path_confinement_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CONFINEMENT_SCHEMA_PATH,
        )


def test_write_path_idempotency_witness_rejects_append_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_IDEMPOTENCY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["idempotency_witness_is_not_append_authority"] = False
    changed["authority_denials"]["receipt_store_append_performed"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError, match="append authority"):
        validate_universal_symbol_receipt_store_write_path_idempotency_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_IDEMPOTENCY_SCHEMA_PATH,
        )


def test_write_path_idempotency_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_IDEMPOTENCY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["idempotency_requirements"] = changed["idempotency_requirements"][1:]
    changed["contract_summary"]["idempotency_requirement_count"] = len(changed["idempotency_requirements"])
    with pytest.raises(
        UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError,
        match="deterministic-key-derivation",
    ):
        validate_universal_symbol_receipt_store_write_path_idempotency_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_IDEMPOTENCY_SCHEMA_PATH,
        )


def test_write_path_idempotency_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_IDEMPOTENCY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["idempotency_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_write_path_idempotency_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_IDEMPOTENCY_SCHEMA_PATH,
        )


def test_write_path_idempotency_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_IDEMPOTENCY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["idempotency_constraints"]["replay_collision_check_required"] = False
    with pytest.raises(
        UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError,
        match="replay_collision_check_required",
    ):
        validate_universal_symbol_receipt_store_write_path_idempotency_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_IDEMPOTENCY_SCHEMA_PATH,
        )


def test_write_path_idempotency_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_IDEMPOTENCY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreWritePathIdempotencyWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_write_path_idempotency_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_IDEMPOTENCY_SCHEMA_PATH,
        )


def test_durability_replay_witness_rejects_append_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_DURABILITY_REPLAY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["durability_replay_witness_is_not_append_authority"] = False
    changed["authority_denials"]["receipt_store_durability_replay_bound"] = True
    with pytest.raises(UniversalSymbolReceiptStoreDurabilityReplayWitnessError, match="append authority"):
        validate_universal_symbol_receipt_store_durability_replay_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_DURABILITY_REPLAY_SCHEMA_PATH,
        )


def test_durability_replay_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_DURABILITY_REPLAY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["durability_replay_requirements"] = changed["durability_replay_requirements"][1:]
    changed["contract_summary"]["durability_replay_requirement_count"] = len(
        changed["durability_replay_requirements"]
    )
    with pytest.raises(UniversalSymbolReceiptStoreDurabilityReplayWitnessError, match="ordered-replay"):
        validate_universal_symbol_receipt_store_durability_replay_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_DURABILITY_REPLAY_SCHEMA_PATH,
        )


def test_durability_replay_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_DURABILITY_REPLAY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["durability_replay_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreDurabilityReplayWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_durability_replay_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_DURABILITY_REPLAY_SCHEMA_PATH,
        )


def test_durability_replay_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_DURABILITY_REPLAY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["durability_replay_constraints"]["append_sequence_required"] = False
    with pytest.raises(
        UniversalSymbolReceiptStoreDurabilityReplayWitnessError,
        match="append_sequence_required",
    ):
        validate_universal_symbol_receipt_store_durability_replay_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_DURABILITY_REPLAY_SCHEMA_PATH,
        )


def test_durability_replay_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_DURABILITY_REPLAY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreDurabilityReplayWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_durability_replay_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_DURABILITY_REPLAY_SCHEMA_PATH,
        )


def test_recovery_witness_rejects_execution_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECOVERY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["recovery_witness_is_not_execution_authority"] = False
    changed["authority_denials"]["recovery_execution_performed"] = True
    with pytest.raises(UniversalSymbolReceiptStoreRecoveryWitnessError, match="execution authority"):
        validate_universal_symbol_receipt_store_recovery_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECOVERY_SCHEMA_PATH,
        )


def test_recovery_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECOVERY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["recovery_requirements"] = changed["recovery_requirements"][1:]
    changed["contract_summary"]["recovery_requirement_count"] = len(changed["recovery_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreRecoveryWitnessError, match="recovery-plan"):
        validate_universal_symbol_receipt_store_recovery_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECOVERY_SCHEMA_PATH,
        )


def test_recovery_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECOVERY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["recovery_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreRecoveryWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_recovery_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECOVERY_SCHEMA_PATH,
        )


def test_recovery_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECOVERY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["recovery_constraints"]["rollback_plan_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreRecoveryWitnessError, match="rollback_plan_required"):
        validate_universal_symbol_receipt_store_recovery_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECOVERY_SCHEMA_PATH,
        )


def test_recovery_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_RECOVERY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreRecoveryWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_recovery_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_RECOVERY_SCHEMA_PATH,
        )


def test_path_custody_witness_rejects_write_path_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CUSTODY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["path_custody_witness_is_not_write_path_authority"] = False
    changed["authority_denials"]["receipt_store_path_custody_registered"] = True
    with pytest.raises(UniversalSymbolReceiptStorePathCustodyWitnessError, match="write-path authority"):
        validate_universal_symbol_receipt_store_path_custody_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CUSTODY_SCHEMA_PATH,
        )


def test_path_custody_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CUSTODY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["custody_requirements"] = changed["custody_requirements"][1:]
    changed["contract_summary"]["custody_requirement_count"] = len(changed["custody_requirements"])
    with pytest.raises(UniversalSymbolReceiptStorePathCustodyWitnessError, match="canonical-path-identity"):
        validate_universal_symbol_receipt_store_path_custody_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CUSTODY_SCHEMA_PATH,
        )


def test_path_custody_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CUSTODY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["custody_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStorePathCustodyWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_path_custody_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CUSTODY_SCHEMA_PATH,
        )


def test_path_custody_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CUSTODY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["custody_constraints"]["repository_relative_path_required"] = False
    with pytest.raises(UniversalSymbolReceiptStorePathCustodyWitnessError, match="repository_relative_path_required"):
        validate_universal_symbol_receipt_store_path_custody_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CUSTODY_SCHEMA_PATH,
        )


def test_path_custody_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_PATH_CUSTODY_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStorePathCustodyWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_path_custody_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_PATH_CUSTODY_SCHEMA_PATH,
        )


def test_write_path_witness_rejects_append_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["write_path_witness_is_not_append_authority"] = False
    changed["authority_denials"]["receipt_store_append_performed"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWritePathWitnessError, match="append authority"):
        validate_universal_symbol_receipt_store_write_path_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_SCHEMA_PATH,
        )


def test_write_path_witness_rejects_missing_requirement(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["write_path_requirements"] = changed["write_path_requirements"][1:]
    changed["contract_summary"]["write_path_requirement_count"] = len(changed["write_path_requirements"])
    with pytest.raises(UniversalSymbolReceiptStoreWritePathWitnessError, match="receipt-store-writer-registration"):
        validate_universal_symbol_receipt_store_write_path_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_SCHEMA_PATH,
        )


def test_write_path_witness_rejects_path_authority_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["authority_denials"]["receipt_store_write_path_registered"] = True
    with pytest.raises(UniversalSymbolReceiptStoreWritePathWitnessError, match="receipt_store_write_path_registered"):
        validate_universal_symbol_receipt_store_write_path_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_SCHEMA_PATH,
        )


def test_write_path_witness_rejects_missing_delta_reject(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["write_path_requirements"][0]["delta_reject_ref"] = "missing-delta"
    with pytest.raises(UniversalSymbolReceiptStoreWritePathWitnessError, match="delta_reject_ref"):
        validate_universal_symbol_receipt_store_write_path_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_SCHEMA_PATH,
        )


def test_write_path_witness_rejects_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["write_path_constraints"]["idempotency_key_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreWritePathWitnessError, match="idempotency_key_required"):
        validate_universal_symbol_receipt_store_write_path_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_SCHEMA_PATH,
        )


def test_write_path_witness_rejects_evidence_ref_count_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_WRITE_PATH_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["contract_summary"]["evidence_ref_count"] = 999
    with pytest.raises(UniversalSymbolReceiptStoreWritePathWitnessError, match="evidence_ref_count drift"):
        validate_universal_symbol_receipt_store_write_path_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_WRITE_PATH_SCHEMA_PATH,
        )


def test_operator_approval_witness_rejects_scope_constraint_drift(tmp_path: Path) -> None:
    witness = json.loads(DEFAULT_OPERATOR_APPROVAL_WITNESS_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(witness)
    changed["approval_constraints"]["approval_scope_required"] = False
    with pytest.raises(UniversalSymbolReceiptStoreOperatorApprovalWitnessError, match="approval_scope_required"):
        validate_universal_symbol_receipt_store_operator_approval_witness(
            _write_policy_case(tmp_path, changed),
            DEFAULT_OPERATOR_APPROVAL_SCHEMA_PATH,
        )
