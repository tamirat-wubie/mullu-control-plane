"""Purpose: verify the universal action kernel composes governed runtime planes.
Governance scope: goal, world-state, plan, simulation, capability admission,
    governed dispatch, terminal closure, learning admission, and app facade.
Dependencies: universal_action_kernel, governed_execution, governed_dispatcher,
    world_state, simulation, and governed capability fabric.
Invariants:
  - Dispatch requires world support, accepted capability admission, and
    non-blocking simulation.
  - Blocked paths do not call execution adapters.
  - Completed paths carry terminal closure and learning admission.
"""

from __future__ import annotations

import json
import importlib.util
import copy
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from gateway.command_spine import (
    CommandLedger,
    CommandState,
    InMemoryCommandLedgerStore,
)
from gateway.audit_trace_verifier import _recompute_event_hash
from mcoi_runtime.app.governed_execution import (
    _recomputed_universal_action_proof_hash,
    build_universal_operator_kernel,
    universal_command_dispatch as _app_universal_command_dispatch,
    universal_command_orchestration_record_view,
    universal_command_proof_view,
    universal_operator_dispatch as _app_universal_operator_dispatch,
)
from mcoi_runtime.contracts.execution import (
    EffectRecord,
    ExecutionMode,
    ExecutionOutcome,
    ExecutionResult,
)
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityAuthorityPolicy,
    CapabilityCertificationStatus,
    CapabilityRecoveryPlan,
    CapabilityRegistryEntry,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)
from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.meta_reasoning import (
    HealthStatus,
    OperatingSubstrateSelfModelProjection,
    SelfModelCapabilityProjection,
    SubsystemHealth,
)
from mcoi_runtime.contracts.simulation import RiskLevel, VerdictType
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.contracts.terminal_closure import (
    TerminalClosureCertificate,
    TerminalClosureDisposition,
)
from mcoi_runtime.contracts.whqr import WHQRDocument, WHQRNode, WHRole

WHQR_CANONICAL_HASH = "sha256:" + ("a" * 64)
WHQR_SEMANTICS_HASH = "sha256:" + ("b" * 64)
WHQR_REPLAY_REF = f"whqr://replay/{WHQR_CANONICAL_HASH}"
from mcoi_runtime.contracts.world_state import (
    ContradictionRecord,
    ContradictionStrategy,
)
from mcoi_runtime.core.closure_learning import ClosureLearningAdmissionGate
from mcoi_runtime.core.command_capability_admission import (
    CommandCapabilityAdmissionGate,
)
from mcoi_runtime.core.dispatcher import DispatchRequest, Dispatcher
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry
from mcoi_runtime.core.governed_dispatcher import GovernedDispatcher
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.simulation import SimulationEngine
from mcoi_runtime.core.system_stabilization import EquilibriumEngine
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.core.universal_action_kernel import (
    UniversalActionKernel,
    UniversalActionRequest,
    build_universal_action_orchestration_record,
)
from mcoi_runtime.core.world_state import WorldStateEngine


NOW = "2026-05-06T12:00:00+00:00"
REQUIRED_ROLE = "customer_ops_manager"
APPROVAL_REFS = ("approval-1",)
APPROVAL_ACTOR_IDS = ("manager-1",)
REPO_ROOT = Path(__file__).resolve().parents[2]
FABRIC_FIXTURE_DIR = (
    REPO_ROOT / "integration" / "governed_capability_fabric" / "fixtures"
)
UAO_VALIDATOR_PATH = (
    REPO_ROOT / "scripts" / "validate_universal_action_orchestration.py"
)
UAO_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_action_orchestration.schema.json"
VALID_TEMPLATE = {
    "template_id": "tpl-universal-1",
    "action_type": "shell_command",
    "command_argv": ("echo", "{msg}"),
    "required_parameters": ("msg",),
}


def _clock() -> str:
    return NOW


def _certificate_with_metadata(
    certificate: TerminalClosureCertificate,
    metadata: dict[str, str],
) -> TerminalClosureCertificate:
    return TerminalClosureCertificate(
        certificate_id=certificate.certificate_id,
        command_id=certificate.command_id,
        execution_id=certificate.execution_id,
        disposition=certificate.disposition,
        verification_result_id=certificate.verification_result_id,
        effect_reconciliation_id=certificate.effect_reconciliation_id,
        evidence_refs=certificate.evidence_refs,
        closed_at=certificate.closed_at,
        response_closure_ref=certificate.response_closure_ref,
        memory_entry_id=certificate.memory_entry_id,
        compensation_outcome_id=certificate.compensation_outcome_id,
        accepted_risk_id=certificate.accepted_risk_id,
        case_id=certificate.case_id,
        graph_refs=certificate.graph_refs,
        metadata=metadata,
    )


def _whqr_replay_metadata() -> dict[str, str]:
    document = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    return {
        "whqr_canonical_json": document.canonical_json(),
        "whqr_canonical_hash": document.canonical_hash(),
        "whqr_semantics_hash": document.semantics_hash,
        "whqr_version": document.whqr_version,
    }


def _replace_command_event_with_recomputed_hash(event, **changes):
    tampered = replace(event, **changes)
    event_hash = _recompute_event_hash(tampered)
    return replace(tampered, event_hash=event_hash, event_id=f"evt-{event_hash[:16]}")


def _rebind_orchestration_record_to_proof_hash(
    record: dict,
    proof_hash: str,
) -> None:
    record["orchestration_id"] = stable_identifier(
        "universal-action-orchestration",
        {
            "action_id": record["action_id"],
            "proof_hash": proof_hash,
            "trace_ref": record["trace_ref"],
        },
    )
    delta_ref = stable_identifier(
        "universal-action-delta",
        {
            "action_id": record["action_id"],
            "proof_hash": proof_hash,
            "closure_state": record["closure_state"],
        },
    )
    record["lineage"]["delta_ref"] = delta_ref
    for delta in (
        record["lineage"]["accepted_deltas"] + record["lineage"]["rejected_deltas"]
    ):
        delta["delta_id"] = delta_ref


@dataclass
class FakeExecutor:
    calls: int = 0
    last_request: ExecutionRequest | None = None
    effect_names: tuple[str, ...] = (
        "customer_address_updated",
        "crm_audit_record_created",
    )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.last_request = request
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=tuple(
                EffectRecord(name=effect_name, details={"argv": list(request.argv)})
                for effect_name in self.effect_names
            ),
            assumed_effects=(),
            started_at=NOW,
            finished_at=NOW,
            metadata={"adapter": "fake"},
        )


def universal_operator_dispatch(*args, **kwargs):
    kwargs.setdefault("approval_refs", APPROVAL_REFS)
    kwargs.setdefault("approval_actor_ids", APPROVAL_ACTOR_IDS)
    return _app_universal_operator_dispatch(*args, **kwargs)


def universal_command_dispatch(*args, **kwargs):
    kwargs.setdefault("approval_refs", APPROVAL_REFS)
    kwargs.setdefault("approval_actor_ids", APPROVAL_ACTOR_IDS)
    return _app_universal_command_dispatch(*args, **kwargs)


def test_universal_action_kernel_dispatches_after_all_certificates_pass() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(_action_request())

    assert result.blocked is False
    assert result.dispatched is True
    assert result.life_meaning_judgment is not None
    assert result.life_meaning_judgment.decision == "pass"
    assert result.goal_certificate.goal.goal_id == "goal-1"
    assert result.world_certificate.allows_execution is True
    assert result.plan_certificate is not None
    assert (
        result.plan_certificate.plan.state_hash
        == result.world_certificate.snapshot.state_hash
    )
    assert result.simulation_certificate is not None
    assert result.simulation_certificate.verdict.verdict_type is VerdictType.PROCEED
    assert result.capability_decision is not None
    assert result.capability_decision.capability_id == "shell_command"
    assert result.intent_certificate is not None
    assert result.intent_certificate.intent_schema == "mullu.intent_ir.v1"
    assert result.intent_certificate.typed_intent.intent_name == "shell_command"
    assert result.intent_certificate.intent_hash.startswith("typed-intent-")
    assert result.governed_action is not None
    assert result.governed_action.typed_intent.intent_name == "shell_command"
    assert (
        result.governed_action.metadata["intent_compilation_certificate"]
        == result.intent_certificate.certificate_id
    )
    passport = result.governed_action.capability_passport
    assert passport.capability_id == "shell_command"
    assert (
        passport.input_schema_ref
        == "schemas/customer_ops/update_customer_address.input.schema.json"
    )
    assert (
        passport.output_schema_ref
        == "schemas/customer_ops/update_customer_address.output.schema.json"
    )
    assert passport.approval_chain == ("customer_ops_manager",)
    assert passport.separation_of_duty is True
    assert passport.execution_plane == "connector_worker"
    assert passport.network_allowlist == ("crm.internal.mullusi.com",)
    assert passport.secret_scope == "tenant:customer_ops:crm"
    assert passport.terminal_certificate_required is True
    assert passport.review_required_on_failure is True
    assert passport.budget_class == "customer_ops_mutation"
    assert passport.max_estimated_cost == 0.25
    assert result.effect_prediction_certificate is not None
    effect_plan = result.effect_prediction_certificate.plan
    assert effect_plan.command_id == "intent-1"
    assert effect_plan.capability_id == "shell_command"
    assert tuple(effect.name for effect in effect_plan.expected_effects) == (
        "customer_address_updated",
        "crm_audit_record_created",
    )
    assert effect_plan.forbidden_effects == (
        "billing_account_modified",
        "unrelated_customer_modified",
    )
    assert effect_plan.rollback_plan_id == "crm.restore_customer_address"
    assert (
        effect_plan.compensation_plan_id
        == "customer_ops.notify_address_update_review"
    )
    assert result.recovery_plan_certificate is not None
    assert result.recovery_plan_certificate.effect_plan_id == effect_plan.effect_plan_id
    assert result.recovery_plan_certificate.recovery_kind == "rollback_and_compensation"
    assert (
        result.recovery_plan_certificate.rollback_plan_id
        == "crm.restore_customer_address"
    )
    assert (
        result.recovery_plan_certificate.compensation_plan_id
        == "customer_ops.notify_address_update_review"
    )
    assert result.governed_action.authority_proof.actor_roles == (REQUIRED_ROLE,)
    assert result.governed_action.authority_proof.approval_chain == (REQUIRED_ROLE,)
    assert result.governed_action.authority_proof.approval_refs == ("approval-1",)
    assert result.governed_action.authority_proof.approval_actor_ids == ("manager-1",)
    assert result.governed_action.authority_proof.separation_of_duty is True
    assert result.terminal_certificate is not None
    assert (
        result.terminal_certificate.disposition is TerminalClosureDisposition.COMMITTED
    )
    assert result.learning_decision is not None
    assert result.learning_decision.status is LearningAdmissionStatus.ADMIT
    assert executor.calls == 1
    assert result.action_envelope["actor"] == "actor-1"
    assert result.action_envelope["tenant"] == "tenant-1"
    assert result.action_envelope["intent"] == "intent-1"
    assert result.action_envelope["target"] == "shell_command"
    assert result.action_envelope["source"].startswith(
        "action://universal-action-source-"
    )
    assert result.action_envelope["risk"] == "low"
    assert result.action_envelope["approval_ref"] == "approval-1"
    assert "approval_refs" not in result.action_envelope
    assert result.action_envelope["capability_refs"] == ("shell_command",)
    assert result.trace_ref.startswith("causal-decision-trace-")
    assert result.admission_receipt_ref.startswith(
        "universal-action-admission-receipt-"
    )
    assert result.execution_receipt_ref.startswith(
        "universal-action-execution-receipt-"
    )
    assert result.closure_state == "closed_allowed"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_request_normalizes_legacy_reality_mode_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(intent_id="intent-real-alias", mode="reality")

    result = kernel.run(request)

    assert request.mode == "real"
    assert result.blocked is True
    assert result.block_reason == "promotion_boundary: not promoted to reality"
    assert result.dispatch_result is not None
    assert result.dispatch_result.ledger_hash != ""
    assert executor.calls == 0


def test_universal_action_request_blocks_shadow_mode_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(intent_id="intent-shadow-mode", mode=ExecutionMode.SHADOW)

    result = kernel.run(request)

    assert request.mode == "shadow"
    assert result.blocked is True
    assert result.block_reason == "promotion_boundary: not promoted to reality"
    assert result.dispatch_result is not None
    assert result.dispatch_result.gates_failed[-1].reason == "mode=simulation, requested=shadow"
    assert result.dispatch_result.ledger_hash != ""
    assert executor.calls == 0


def test_universal_action_result_exports_valid_allowed_uao_record() -> None:
    kernel, _executor = _kernel_with_capability()
    request = _action_request()

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record["uao_schema_version"] == "uao.v1"
    assert record["decision"]["status"] == "allow"
    assert record["execution_receipt_ref"] == result.execution_receipt_ref
    assert record["recovery_plan"]["available"] is True
    assert record["recovery_plan"]["recovery_kind"] == "rollback_and_compensation"
    assert record["recovery_plan"]["recovery_plan_ref"]
    assert record["recovery_plan"]["certificate_ref"]
    assert record["closure"]["whqr_replay_binding"] is None
    assert record["claim_ledger"]["ledger_ref"].startswith("claim-ledger://")
    assert record["claim_ledger"]["unverified_claim_ids"] == []
    assert record["fracture_report"]["report_ref"].startswith("fracture-report://")
    assert record["fracture_report"]["status"] == "passed"
    assert record["fracture_report"]["blocking_check_ids"] == []
    assert record["life_meaning_judgment"]["judgment_id"].startswith(
        "life-meaning:"
    )
    assert record["life_meaning_judgment"] == result.life_meaning_judgment.as_dict()
    assert record["life_meaning_judgment"]["action_id"] == result.action_id
    assert record["life_meaning_judgment"]["decision"] == "pass"
    assert record["life_meaning_judgment"]["truth_preserved"] is True
    assert record["life_meaning_judgment"]["dignity_boundary"] == "pass"
    assert record["life_meaning_judgment"]["domination_risk"] is False
    assert record["life_meaning_judgment"]["consent_required"] is True
    assert record["life_meaning_judgment"]["consent_present"] is True
    assert record["life_meaning_judgment"]["evidence_refs"]
    assert record["life_continuity_judgment"]["judgment_ref"].startswith(
        "life-continuity://"
    )
    assert record["life_continuity_judgment"]["conflict_law_ref"] == (
        "doctrine://life-continuity-conflict-law/v1"
    )
    assert record["life_continuity_judgment"]["decision"] == "pass"
    assert record["life_continuity_judgment"]["truth_preserved"] is True
    assert record["life_continuity_judgment"]["dignity_boundary"] == "pass"
    assert record["life_continuity_judgment"]["domination_risk"] is False
    assert record["life_continuity_judgment"]["meaning_impact"] == record[
        "life_meaning_judgment"
    ]["meaning_impact"]
    assert (
        record["life_continuity_judgment"]["meaning_continuity_delta"]
        == record["life_meaning_judgment"]["continuity_delta"]
    )
    assert _pipeline_stage(record, "fracture")["stage_order"] < _pipeline_stage(
        record, "execution"
    )["stage_order"]
    assert {claim["claim_type"] for claim in record["claim_ledger"]["claims"]} >= {
        "decision",
        "execution",
        "reconciliation",
        "closure",
        "recovery",
    }
    assert all(
        claim["verified"] and claim["evidence_refs"]
        for claim in record["claim_ledger"]["claims"]
    )
    _assert_memory_constitution(record, learning_allowed=True)
    assert record["raw_reasoning_included"] is False
    assert record["lineage"]["accepted_deltas"]
    assert record["lineage"]["rejected_deltas"] == []
    assert any(ref.startswith("world-state://snapshot/") for ref in record["input_refs"])


def test_universal_action_record_binds_whqr_replay_metadata_in_closure_receipt() -> None:
    kernel, _executor = _kernel_with_capability()
    request = _action_request(intent_id="intent-whqr-replay-binding")
    result = kernel.run(request)
    assert result.terminal_certificate is not None
    metadata = {**dict(result.terminal_certificate.metadata), **_whqr_replay_metadata()}
    whqr_certificate = _certificate_with_metadata(result.terminal_certificate, metadata)
    result = replace(result, terminal_certificate=whqr_certificate)

    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)
    binding = record["closure"]["whqr_replay_binding"]
    closure_receipt = next(
        receipt for receipt in record["receipts"] if receipt["kind"] == "closure"
    )

    assert validation_errors == []
    assert binding["replay_ref"] == f"whqr://replay/{metadata['whqr_canonical_hash']}"
    assert binding["canonical_hash"] == metadata["whqr_canonical_hash"]
    assert binding["semantics_hash"] == metadata["whqr_semantics_hash"]
    assert binding["version"] == metadata["whqr_version"]
    assert closure_receipt["confirms"] == stable_identifier(
        "universal-action-closure-confirmation",
        {
            "closure_state": record["closure_state"],
            "reconciliation_ref": record["closure"]["reconciliation_ref"],
            "memory_ref": record["closure"]["memory_ref"],
            "whqr_replay_ref": binding["replay_ref"],
            "whqr_canonical_hash": binding["canonical_hash"],
            "whqr_semantics_hash": binding["semantics_hash"],
            "whqr_version": binding["version"],
        },
    )


def test_universal_action_record_rejects_tampered_whqr_replay_metadata() -> None:
    kernel, _executor = _kernel_with_capability()
    request = _action_request(intent_id="intent-whqr-replay-tamper")
    result = kernel.run(request)
    assert result.terminal_certificate is not None
    metadata = {**dict(result.terminal_certificate.metadata), **_whqr_replay_metadata()}
    metadata["whqr_canonical_json"] = metadata["whqr_canonical_json"].replace(
        "payment_request",
        "delete_file",
    )
    whqr_certificate = _certificate_with_metadata(result.terminal_certificate, metadata)
    result = replace(result, terminal_certificate=whqr_certificate)

    with pytest.raises(
        RuntimeCoreInvariantError,
        match="UAO closure WHQR replay document is invalid",
    ):
        build_universal_action_orchestration_record(request=request, result=result)


def test_universal_action_record_rejects_malformed_life_meaning_evidence_refs() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(
        intent_id="intent-life-meaning-bad-evidence",
        metadata={"life_meaning_judgment": {"evidence_refs": ["trace://valid", 7]}},
    )

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        kernel.run(request)

    assert "life_meaning_judgment.evidence_refs" in str(exc_info.value)
    assert "non-empty strings" in str(exc_info.value)
    assert executor.calls == 0


def test_universal_action_record_rejects_boolean_life_meaning_symbol_levels() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(
        intent_id="intent-life-meaning-bool-level",
        metadata={
            "life_meaning_judgment": {
                "affected_symbols": [
                    {
                        "symbol_id": "symbol-bool-level",
                        "symbol_kind": "effect_bearing_action_target",
                        "life_status": "unknown",
                        "feeling_status": "unknown",
                        "meaning_bearing": "indirect",
                        "fragility_level": True,
                        "agency_level": 2,
                    }
                ]
            }
        },
    )

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        kernel.run(request)

    assert "fragility_level must be an integer in [0,10]" in str(exc_info.value)
    assert executor.calls == 0


def test_universal_action_kernel_pauses_life_meaning_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(
        intent_id="intent-life-meaning-pause",
        metadata={"life_meaning_judgment": {"love_delta": "negative"}},
    )

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert result.blocked is True
    assert result.dispatched is False
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.block_reason == "life_meaning_judgment_pause"
    assert result.life_meaning_judgment is not None
    assert result.life_meaning_judgment.decision == "pause"
    assert "love_delta_negative" in result.life_meaning_judgment.reasons
    assert result.execution_receipt_ref is None
    assert result.closure_state == "closed_deferred"
    assert record["decision"]["status"] == "defer"
    assert record["decision"]["execution_allowed"] is False
    assert record["life_meaning_judgment"] == result.life_meaning_judgment.as_dict()


def test_universal_action_kernel_blocks_life_meaning_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(
        intent_id="intent-life-meaning-block",
        metadata={"life_meaning_judgment": {"dignity_boundary": "fail"}},
    )

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert result.blocked is True
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.block_reason == "life_meaning_judgment_block"
    assert result.life_meaning_judgment is not None
    assert result.life_meaning_judgment.decision == "block"
    assert "dignity_boundary_failed" in result.life_meaning_judgment.reasons
    assert result.closure_state == "closed_blocked"
    assert record["decision"]["status"] == "block"
    assert record["lineage"]["accepted_deltas"] == []
    assert record["lineage"]["rejected_deltas"]


def test_universal_action_kernel_escalates_life_meaning_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(
        intent_id="intent-life-meaning-escalate",
        metadata={"life_meaning_judgment": {"irreversible": True}},
    )

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert result.blocked is True
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.block_reason == "life_meaning_judgment_escalate"
    assert result.life_meaning_judgment is not None
    assert result.life_meaning_judgment.decision == "escalate"
    assert (
        "unknown_life_feeling_or_meaning_status_with_irreversible_action"
        in result.life_meaning_judgment.reasons
    )
    assert result.closure_state == "closed_escalated"
    assert record["decision"]["status"] == "escalate"
    assert record["decision"]["solver_outcome"] == "AwaitingEvidence"


def test_universal_action_record_binds_operating_substrate_projection_evidence() -> None:
    kernel, _executor = _kernel_with_capability()
    projection = _operating_substrate_projection()
    request = _action_request(
        intent_id="intent-operating-substrate-allow",
        operating_substrate_projection=projection,
        require_operating_substrate_projection=True,
    )

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)
    evidence_guard = _guard(record, "evidence_sufficient")

    assert validation_errors == []
    assert result.blocked is False
    assert result.operating_substrate_certificate is not None
    assert result.operating_substrate_certificate.allows_execution is True
    assert result.operating_substrate_certificate.projection == projection
    assert f"operating-substrate://projection/{projection.projection_id}" in record["input_refs"]
    assert f"operating-substrate://projection/{projection.projection_id}" in evidence_guard["evidence_refs"]
    assert "proof://operating-substrate" in evidence_guard["evidence_refs"]


def test_universal_action_kernel_blocks_when_required_self_model_evidence_missing() -> None:
    kernel, executor = _kernel_with_capability()
    request = _action_request(
        intent_id="intent-operating-substrate-missing",
        require_operating_substrate_projection=True,
    )

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)
    evidence_guard = _guard(record, "evidence_sufficient")

    assert validation_errors == []
    assert result.blocked is True
    assert result.block_reason == "operating_substrate_self_model_missing"
    assert result.operating_substrate_certificate is not None
    assert result.operating_substrate_certificate.allows_execution is False
    assert result.governed_action is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert record["decision"]["solver_outcome"] == "AwaitingEvidence"
    assert record["decision"]["next_action"] == "collect_operating_substrate_evidence"
    assert evidence_guard["proof_state"] == "Unknown"
    assert "operating-substrate://projection/missing" in evidence_guard["evidence_refs"]


def test_universal_action_kernel_blocks_degraded_self_model_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()
    projection = _operating_substrate_projection(
        status=HealthStatus.DEGRADED,
        solver_outcome=SolverOutcome.SOLVED_UNVERIFIED,
    )
    request = _action_request(
        intent_id="intent-operating-substrate-degraded",
        operating_substrate_projection=projection,
        require_operating_substrate_projection=True,
    )

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)
    evidence_guard = _guard(record, "evidence_sufficient")

    assert validation_errors == []
    assert result.blocked is True
    assert result.block_reason == "operating_substrate_self_model_rejected"
    assert result.operating_substrate_certificate is not None
    assert result.operating_substrate_certificate.allows_execution is False
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert record["decision"]["solver_outcome"] == "GovernanceBlocked"
    assert evidence_guard["proof_state"] == "Fail"
    assert "operating-substrate://status/degraded" in evidence_guard["evidence_refs"]


def test_universal_action_kernel_escalates_effect_prediction_mismatch() -> None:
    kernel, executor = _kernel_with_capability(
        effect_names=("customer_address_updated", "billing_account_modified")
    )
    request = _action_request(intent_id="intent-effect-mismatch")

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert result.blocked is False
    assert result.dispatched is True
    assert result.effect_prediction_certificate is not None
    assert result.terminal_certificate is not None
    assert (
        result.terminal_certificate.disposition
        is TerminalClosureDisposition.REQUIRES_REVIEW
    )
    assert result.learning_decision is None
    assert executor.calls == 1
    assert result.closure_state == "closed_escalated"
    assert record["decision"]["status"] == "escalate"
    assert record["decision"]["reason_code"] == "effect_reconciliation_mismatch"
    assert record["reconciliation"]["status"] == "mismatched"
    assert record["memory_update"]["learning_allowed"] is False
    assert record["lineage"]["accepted_deltas"] == []
    assert record["lineage"]["rejected_deltas"]


def test_universal_action_kernel_blocks_missing_authority_before_plan() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(
        _action_request(
            intent_id="intent-authority-block",
            metadata={"actor_roles": ("support_viewer",)},
        )
    )

    assert result.blocked is True
    assert result.block_reason == "governed_action_admission_rejected"
    assert result.capability_decision is not None
    assert result.governed_action is None
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.admission_receipt_ref.startswith(
        "universal-action-admission-receipt-"
    )
    assert result.execution_receipt_ref is None


def test_universal_action_kernel_blocks_world_mutation_without_recovery_path() -> None:
    kernel, executor = _kernel_with_capability(
        recovery_plan=CapabilityRecoveryPlan(
            rollback_capability="",
            compensation_capability="",
            review_required_on_failure=True,
        )
    )
    request = _action_request(intent_id="intent-missing-recovery")

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(
        request=request,
        result=result,
    )
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert result.blocked is True
    assert result.block_reason == "recovery_plan_missing"
    assert result.recovery_plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert record["decision"]["status"] == "block"
    assert record["decision"]["reason_code"] == "recovery_plan_missing"
    assert record["recovery_plan"]["available"] is False
    assert record["recovery_plan"]["recovery_kind"] == "none"
    assert record["fracture_report"]["status"] == "failed"
    assert any(
        check["check_type"] == "missing_recovery" and check["blocking"]
        for check in record["fracture_report"]["checks"]
    )
    assert _pipeline_stage(record, "fracture")["status"] == "blocked"
    assert record["claim_ledger"]["claims"]
    assert record["claim_ledger"]["unverified_claim_ids"] == []
    assert all(
        claim["verified"] and claim["evidence_refs"]
        for claim in record["claim_ledger"]["claims"]
    )
    _assert_memory_constitution(record, learning_allowed=False)
    assert any(
        guard["guard"] == "recovery_available" and guard["verdict"] == "blocked"
        for guard in record["admission_guards"]
    )
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_missing_approval_before_plan() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(
        _action_request(
            intent_id="intent-approval-block",
            metadata={"approval_refs": (), "approval_actor_ids": ()},
        )
    )

    assert result.blocked is True
    assert result.block_reason == "governed_action_admission_rejected"
    assert result.capability_decision is not None
    assert result.governed_action is None
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_self_approval_before_plan() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(
        _action_request(
            intent_id="intent-self-approval-block",
            metadata={
                "approval_refs": ("approval-self",),
                "approval_actor_ids": ("actor-1",),
            },
        )
    )

    assert result.blocked is True
    assert result.block_reason == "governed_action_admission_rejected"
    assert result.capability_decision is not None
    assert result.governed_action is None
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_unattributed_sod_approval_refs_before_plan() -> (
    None
):
    authority_policy = CapabilityAuthorityPolicy(
        required_roles=(REQUIRED_ROLE,),
        approval_chain=(REQUIRED_ROLE, "security_reviewer"),
        separation_of_duty=True,
    )
    kernel, executor = _kernel_with_capability(authority_policy=authority_policy)

    result = kernel.run(
        _action_request(
            intent_id="intent-unattributed-approval-block",
            metadata={
                "approval_refs": ("approval-1", "approval-2"),
                "approval_actor_ids": ("manager-1",),
            },
        )
    )

    assert result.blocked is True
    assert result.block_reason == "governed_action_admission_rejected"
    assert result.capability_decision is not None
    assert result.governed_action is None
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_open_world_contradictions_before_dispatch() -> (
    None
):
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, executor = _kernel_with_capability(world_state=world_state)

    result = kernel.run(_action_request(intent_id="intent-world-block"))

    assert result.blocked is True
    assert result.block_reason == "open_world_contradictions"
    assert result.world_certificate.allows_execution is False
    assert len(result.world_certificate.snapshot.unresolved_contradictions) == 1
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_result_exports_valid_blocked_uao_record() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, _executor = _kernel_with_capability(world_state=world_state)
    request = _action_request(intent_id="intent-world-block-record")

    result = kernel.run(request)
    record = build_universal_action_orchestration_record(request=request, result=result)
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record["decision"]["status"] == "block"
    assert record["execution_receipt_ref"] is None
    assert record["closure_state"] == "closed_blocked"
    assert record["memory_update"]["learning_allowed"] is False
    assert record["lineage"]["accepted_deltas"] == []
    assert record["lineage"]["rejected_deltas"]


def test_universal_action_kernel_blocks_uninstalled_capability_before_plan() -> None:
    kernel, executor = _kernel_without_capability()

    result = kernel.run(_action_request(intent_id="intent-capability-block"))

    assert result.blocked is True
    assert result.block_reason == "capability_admission_rejected"
    assert result.intent_certificate is not None
    assert result.intent_certificate.typed_intent.intent_name == "shell_command"
    assert result.capability_decision is not None
    assert (
        result.capability_decision.reason == "no installed capability for typed intent"
    )
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_uncompiled_intent_before_capability() -> None:
    kernel, executor = _kernel_with_capability()
    mismatched_template = dict(VALID_TEMPLATE)
    mismatched_template["action_type"] = "document_write"

    result = kernel.run(
        _action_request(
            intent_id="intent-ir-block",
            dispatch_request=DispatchRequest(
                goal_id="goal-ir-block",
                route="shell_command",
                template=mismatched_template,
                bindings={"msg": "hello"},
            ),
        )
    )

    assert result.blocked is True
    assert result.block_reason == "intent_compilation_rejected"
    assert result.intent_certificate is None
    assert result.capability_decision is None
    assert result.governed_action is None
    assert result.plan_certificate is None
    assert result.dispatch_result is None
    assert executor.calls == 0


def test_universal_action_kernel_blocks_escalating_simulation_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(
        _action_request(intent_id="intent-sim-block", risk_level=RiskLevel.HIGH)
    )

    assert result.blocked is True
    assert result.block_reason == "simulation_escalate"
    assert result.plan_certificate is not None
    assert result.simulation_certificate is not None
    assert result.simulation_certificate.verdict.verdict_type is VerdictType.ESCALATE
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.action_envelope["risk"] == "H3"
    assert result.closure_state == "closed_blocked"
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_action_kernel_blocks_approval_required_simulation_before_dispatch() -> None:
    kernel, executor = _kernel_with_capability()

    result = kernel.run(
        _action_request(
            intent_id="intent-sim-approval-block",
            success_probability=0.55,
        )
    )

    assert result.blocked is True
    assert result.block_reason == "simulation_approval_required"
    assert result.plan_certificate is not None
    assert result.simulation_certificate is not None
    assert (
        result.simulation_certificate.verdict.verdict_type
        is VerdictType.APPROVAL_REQUIRED
    )
    assert result.governed_action is not None
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert result.closure_state == "closed_blocked"
    assert result.execution_receipt_ref is None
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_operator_dispatch_exposes_kernel_entry_point() -> None:
    kernel, executor = _kernel_with_capability()

    result = universal_operator_dispatch(
        kernel,
        _dispatch_request(),
        actor_id="operator-1",
        tenant_id="tenant-1",
        intent_id="intent-operator-entry",
        objective="Exercise the app-layer universal action entry point.",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )

    assert result.blocked is False
    assert result.dispatched is True
    assert (
        result.goal_certificate.goal.description
        == "Exercise the app-layer universal action entry point."
    )
    assert result.terminal_certificate is not None
    assert result.learning_decision is not None
    assert executor.calls == 1
    assert result.proof_hash.startswith("universal-action-proof-")


def test_universal_operator_dispatch_derives_objective_and_intent_when_absent() -> None:
    kernel, executor = _kernel_with_capability()

    result = universal_operator_dispatch(
        kernel,
        _dispatch_request(goal_id="goal-auto"),
        actor_id="operator-auto",
        tenant_id="tenant-1",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )

    assert result.blocked is False
    assert result.goal_certificate.goal.goal_id == "goal-auto"
    assert (
        result.goal_certificate.goal.description
        == "Execute shell_command for goal goal-auto"
    )
    assert result.capability_decision is not None
    assert result.capability_decision.intent_name == "shell_command"
    assert executor.calls == 1
    assert result.dispatch_result is not None
    assert result.dispatch_result.ledger_hash


def test_build_universal_operator_kernel_composes_bootstrapped_runtime() -> None:
    executor = FakeExecutor()
    runtime = bootstrap_runtime(clock=_clock, executors={"shell_command": executor})
    kernel = build_universal_operator_kernel(
        runtime,
        capability_admission_gate=_capability_admission_gate(),
    )

    result = universal_operator_dispatch(
        kernel,
        _dispatch_request(),
        actor_id="operator-bootstrap",
        tenant_id="tenant-1",
        intent_id="intent-bootstrap-kernel",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )

    assert result.blocked is False
    assert result.dispatched is True
    assert result.terminal_certificate is not None
    assert result.learning_decision is not None
    assert executor.calls == 1
    assert result.proof_hash.startswith("universal-action-proof-")


def test_build_universal_operator_kernel_requires_runtime_dependencies() -> None:
    class MissingRuntime:
        pass

    try:
        build_universal_operator_kernel(
            MissingRuntime(),
            capability_admission_gate=_capability_admission_gate(),
        )
    except ValueError as exc:
        assert str(exc) == "runtime must expose world_state"
    else:
        raise AssertionError("missing runtime dependencies should fail closed")


def test_universal_command_dispatch_binds_command_spine_transitions() -> None:
    kernel, executor = _kernel_with_capability()
    ledger = CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-command",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    current = ledger.get(command.command_id)
    events = ledger.events_for(command.command_id)
    states = [event.next_state for event in events]

    assert result.blocked is False
    assert result.dispatched is True
    assert result.terminal_certificate is not None
    assert result.learning_decision is not None
    assert executor.calls == 1
    assert current is not None
    assert current.state is CommandState.LEARNING_DECIDED
    assert CommandState.GOVERNED_ACTION_BOUND in states
    assert CommandState.DISPATCHED in states
    assert CommandState.TERMINALLY_CERTIFIED in states
    assert CommandState.LEARNING_DECIDED in states
    dispatch_detail = next(
        event.detail
        for event in events
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    assert (
        dispatch_detail["universal_action"]["intent_certificate_id"]
        == result.intent_certificate.certificate_id
    )
    assert (
        dispatch_detail["universal_action"]["intent_hash"]
        == result.intent_certificate.intent_hash
    )
    assert (
        events[-1].detail["learning_admission_id"]
        == result.learning_decision.admission_id
    )
    assert events[-1].detail["proof_hash"] == result.proof_hash


def test_universal_command_proof_view_replays_persisted_success_events() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-view",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    proof = universal_command_proof_view(reloaded_ledger, command.command_id)

    assert proof is not None
    assert proof.command_id == command.command_id
    assert proof.blocked is False
    assert proof.action_envelope["actor"] == "actor-1"
    assert proof.action_envelope["tenant"] == "tenant-1"
    assert proof.trace_ref == result.trace_ref
    assert proof.admission_receipt_ref == result.admission_receipt_ref
    assert proof.execution_receipt_ref == result.execution_receipt_ref
    assert proof.life_meaning_judgment == result.life_meaning_judgment.as_dict()
    assert proof.life_meaning_judgment["decision"] == "pass"
    assert proof.closure_state == "closed_allowed"
    assert proof.whqr_replay_binding == {}
    assert proof.proof_hash == result.proof_hash
    assert proof.capability_id == "shell_command"
    assert proof.dispatch_ledger_hash == result.dispatch_result.ledger_hash
    assert proof.terminal_certificate_id == result.terminal_certificate.certificate_id
    assert proof.terminal_disposition == TerminalClosureDisposition.COMMITTED.value
    assert proof.learning_admission_id == result.learning_decision.admission_id
    assert proof.learning_status == LearningAdmissionStatus.ADMIT.value
    assert CommandState.DISPATCHED.value in proof.state_sequence
    assert CommandState.LEARNING_DECIDED.value in proof.state_sequence
    assert len(proof.event_hashes) >= 5


def test_universal_action_proof_hash_rejects_malformed_whqr_replay_binding() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-whqr-shape",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    malformed_detail = copy.deepcopy(valid_event_detail["universal_action"])
    malformed_detail["whqr_replay_binding"] = {
        "replay_ref": "whqr://replay/sha256:runtime-canonical",
        "canonical_hash": "runtime-canonical",
        "semantics_hash": "sha256:runtime-semantics",
        "version": "0.1.0",
    }

    proof_hash = _recomputed_universal_action_proof_hash(malformed_detail)

    assert proof_hash is None
    assert malformed_detail["whqr_replay_binding"]["canonical_hash"] == (
        "runtime-canonical"
    )
    assert malformed_detail["whqr_replay_binding"]["replay_ref"].startswith(
        "whqr://replay/sha256:"
    )


def test_universal_action_proof_hash_rejects_empty_whqr_digest_refs() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-whqr-empty-digest",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    malformed_detail = copy.deepcopy(valid_event_detail["universal_action"])
    malformed_detail["whqr_replay_binding"] = {
        "replay_ref": "whqr://replay/sha256:",
        "canonical_hash": "sha256:",
        "semantics_hash": "sha256:",
        "version": "0.1.0",
    }

    proof_hash = _recomputed_universal_action_proof_hash(malformed_detail)

    assert proof_hash is None
    assert malformed_detail["whqr_replay_binding"]["canonical_hash"] == "sha256:"
    assert malformed_detail["whqr_replay_binding"]["semantics_hash"] == "sha256:"


def test_universal_action_proof_hash_rejects_whitespace_whqr_digest_refs() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-whqr-whitespace-digest",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    malformed_detail = copy.deepcopy(valid_event_detail["universal_action"])
    malformed_detail["whqr_replay_binding"] = {
        "replay_ref": "whqr://replay/sha256:   ",
        "canonical_hash": "sha256:   ",
        "semantics_hash": "sha256:\t",
        "version": "0.1.0",
    }

    proof_hash = _recomputed_universal_action_proof_hash(malformed_detail)

    assert proof_hash is None
    assert malformed_detail["whqr_replay_binding"]["replay_ref"].endswith("   ")
    assert malformed_detail["whqr_replay_binding"]["semantics_hash"].endswith("\t")


def test_universal_action_proof_hash_rejects_nonhex_whqr_digest_refs() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-whqr-nonhex-digest",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    malformed_detail = copy.deepcopy(valid_event_detail["universal_action"])
    malformed_detail["whqr_replay_binding"] = {
        "replay_ref": "whqr://replay/sha256:" + ("g" * 64),
        "canonical_hash": "sha256:" + ("g" * 64),
        "semantics_hash": "sha256:" + ("A" * 64),
        "version": "0.1.0",
    }

    proof_hash = _recomputed_universal_action_proof_hash(malformed_detail)

    assert proof_hash is None
    assert malformed_detail["whqr_replay_binding"]["canonical_hash"].endswith("g" * 64)
    assert malformed_detail["whqr_replay_binding"]["semantics_hash"].endswith("A" * 64)


def test_universal_action_proof_hash_rejects_leading_zero_whqr_version() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-whqr-leading-zero-version",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    malformed_detail = copy.deepcopy(valid_event_detail["universal_action"])
    malformed_detail["whqr_replay_binding"] = {
        "replay_ref": WHQR_REPLAY_REF,
        "canonical_hash": WHQR_CANONICAL_HASH,
        "semantics_hash": WHQR_SEMANTICS_HASH,
        "version": "01.002.0003",
    }

    proof_hash = _recomputed_universal_action_proof_hash(malformed_detail)

    assert proof_hash is None
    assert malformed_detail["whqr_replay_binding"]["version"] == "01.002.0003"
    assert malformed_detail["whqr_replay_binding"]["canonical_hash"].startswith("sha256:")


def test_universal_action_proof_hash_rejects_non_ascii_decimal_whqr_version() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-whqr-non-ascii-version",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    malformed_detail = copy.deepcopy(valid_event_detail["universal_action"])
    malformed_detail["whqr_replay_binding"] = {
        "replay_ref": WHQR_REPLAY_REF,
        "canonical_hash": WHQR_CANONICAL_HASH,
        "semantics_hash": WHQR_SEMANTICS_HASH,
        "version": "\u0661.2.3",
    }

    proof_hash = _recomputed_universal_action_proof_hash(malformed_detail)

    assert proof_hash is None
    assert malformed_detail["whqr_replay_binding"]["version"] == "\u0661.2.3"
    assert malformed_detail["whqr_replay_binding"]["semantics_hash"].startswith("sha256:")


def test_universal_command_proof_view_rejects_malformed_whqr_replay_binding() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-view-whqr-shape",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    target_index = next(
        index
        for index, event in enumerate(store._events)
        if event.command_id == command.command_id
        and event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    tampered_detail = copy.deepcopy(store._events[target_index].detail)
    tampered_detail["universal_action"]["whqr_replay_binding"] = {
        "replay_ref": "whqr://replay/sha256:runtime-canonical",
        "canonical_hash": "runtime-canonical",
        "semantics_hash": "sha256:runtime-semantics",
        "version": "0.1.0",
    }
    store._events[target_index] = _replace_command_event_with_recomputed_hash(
        store._events[target_index],
        detail=tampered_detail,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    proof = universal_command_proof_view(reloaded_ledger, command.command_id)

    assert proof is None
    assert reloaded_ledger.get(command.command_id) is not None
    assert (
        _recompute_event_hash(store._events[target_index])
        == store._events[target_index].event_hash
    )


def test_universal_command_orchestration_record_replays_success_events() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-view",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record is not None
    assert record["action_id"] == result.action_id
    assert record["decision"]["status"] == "allow"
    assert record["execution_receipt_ref"] == result.execution_receipt_ref
    assert record["closure_state"] == "closed_allowed"
    assert (
        record["closure"]["reconciliation_ref"]
        == f"reconciliation://{result.action_id}"
    )
    assert (
        record["closure"]["memory_ref"]
        == f"memory://{result.terminal_certificate.memory_entry_id}"
    )
    assert record["closure"]["memory_ref"] == record["memory_update"]["memory_ref"]
    assert (
        record["closure"]["reconciliation_ref"]
        in _pipeline_stage(record, "reconciliation")["output_refs"]
    )
    assert (
        record["closure"]["memory_ref"]
        in _pipeline_stage(record, "memory")["output_refs"]
    )
    closure_receipt = next(
        receipt for receipt in record["receipts"] if receipt["kind"] == "closure"
    )
    assert closure_receipt["confirms"] == stable_identifier(
        "universal-action-closure-confirmation",
        {
            "closure_state": record["closure_state"],
            "reconciliation_ref": record["closure"]["reconciliation_ref"],
            "memory_ref": record["closure"]["memory_ref"],
        },
    )
    assert record["lineage"]["accepted_deltas"]


def test_universal_command_orchestration_record_replays_effect_mismatch_escalation() -> None:
    kernel, _executor = _kernel_with_capability(
        effect_names=("customer_address_updated", "billing_account_modified")
    )
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-effect-mismatch",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record is not None
    assert result.dispatched is True
    assert result.closure_state == "closed_escalated"
    assert record["action_id"] == result.action_id
    assert record["decision"]["status"] == "escalate"
    assert record["decision"]["reason_code"] == "effect_reconciliation_mismatch"
    assert record["execution_receipt_ref"] == result.execution_receipt_ref
    assert record["reconciliation"]["status"] == "mismatched"
    assert record["reconciliation"]["required_for_closure"] is True
    assert record["closure"]["reconciliation_ref"] == f"reconciliation://{result.action_id}"
    assert record["closure"]["memory_ref"] is None
    assert record["lineage"]["accepted_deltas"] == []
    assert record["lineage"]["rejected_deltas"]


def test_universal_command_orchestration_record_ignores_invalid_latest_event() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-invalid-latest",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_record = universal_command_orchestration_record_view(
        ledger, command.command_id
    )
    invalid_record = copy.deepcopy(valid_record)
    assert isinstance(invalid_record, dict)
    invalid_record["raw_reasoning_included"] = True
    invalid_record["chain_of_thought"] = "private reasoning must not replay"
    ledger.transition(
        command.command_id,
        CommandState.DISPATCHED,
        detail={
            "cause": "universal_action_kernel_dispatched",
            "universal_action_orchestration": invalid_record,
        },
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is not None
    assert replayed_record["action_id"] == result.action_id
    assert replayed_record["raw_reasoning_included"] is False
    assert replayed_record["orchestration_id"] == valid_record["orchestration_id"]
    assert "chain_of_thought" not in replayed_record


def test_universal_command_orchestration_record_ignores_receipt_spoof_event() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-receipt-spoof",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_record = universal_command_orchestration_record_view(
        ledger, command.command_id
    )
    invalid_record = copy.deepcopy(valid_record)
    assert isinstance(invalid_record, dict)
    for receipt in invalid_record["receipts"]:
        if receipt["kind"] == "admission":
            receipt["stage_id"] = "stage_trace"
    ledger.transition(
        command.command_id,
        CommandState.DISPATCHED,
        detail={
            "cause": "universal_action_kernel_dispatched",
            "universal_action_orchestration": invalid_record,
        },
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is not None
    assert replayed_record["action_id"] == result.action_id
    assert replayed_record["orchestration_id"] == valid_record["orchestration_id"]
    assert replayed_record["receipts"] != invalid_record["receipts"]


def test_universal_command_orchestration_record_ignores_proof_spoof_event() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-proof-spoof",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    valid_record = universal_command_orchestration_record_view(
        ledger, command.command_id
    )
    invalid_record = copy.deepcopy(valid_record)
    valid_event_detail = next(
        event.detail
        for event in ledger.events_for(command.command_id)
        if event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    assert isinstance(invalid_record, dict)
    invalid_record["orchestration_id"] = "universal-action-orchestration-spoofed"
    ledger.transition(
        command.command_id,
        CommandState.DISPATCHED,
        detail={
            "cause": "universal_action_kernel_dispatched",
            "universal_action": copy.deepcopy(valid_event_detail["universal_action"]),
            "universal_action_orchestration": invalid_record,
        },
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is not None
    assert replayed_record["action_id"] == result.action_id
    assert replayed_record["orchestration_id"] == valid_record["orchestration_id"]
    assert replayed_record["orchestration_id"] != invalid_record["orchestration_id"]


def test_universal_command_orchestration_record_rejects_rehashed_proof_spoof() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-proof-hash-spoof",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    target_index = next(
        index
        for index, event in enumerate(store._events)
        if event.command_id == command.command_id
        and event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    spoofed_proof_hash = "universal-action-proof-spoofed"
    tampered_detail = copy.deepcopy(store._events[target_index].detail)
    tampered_detail["universal_action"]["proof_hash"] = spoofed_proof_hash
    _rebind_orchestration_record_to_proof_hash(
        tampered_detail["universal_action_orchestration"],
        spoofed_proof_hash,
    )
    store._events[target_index] = _replace_command_event_with_recomputed_hash(
        store._events[target_index],
        detail=tampered_detail,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is None
    assert reloaded_ledger.get(command.command_id) is not None
    assert (
        _recompute_event_hash(store._events[target_index])
        == store._events[target_index].event_hash
    )


def test_universal_command_orchestration_record_rejects_closure_memory_ref_spoof() -> (
    None
):
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-closure-memory-spoof",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
    )
    target_index = next(
        index
        for index, event in enumerate(store._events)
        if event.command_id == command.command_id
        and event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    spoofed_memory_ref = "memory://spoofed-closure-memory"
    tampered_detail = copy.deepcopy(store._events[target_index].detail)
    record = tampered_detail["universal_action_orchestration"]
    record["memory_update"]["memory_ref"] = spoofed_memory_ref
    record["closure"]["memory_ref"] = spoofed_memory_ref
    _pipeline_stage(record, "memory")["output_refs"] = [spoofed_memory_ref]
    _pipeline_stage(record, "closure")["input_refs"] = [spoofed_memory_ref]
    for receipt in record["receipts"]:
        if receipt["kind"] == "closure":
            receipt["confirms"] = stable_identifier(
                "universal-action-closure-confirmation",
                {
                    "closure_state": record["closure_state"],
                    "reconciliation_ref": record["closure"]["reconciliation_ref"],
                    "memory_ref": spoofed_memory_ref,
                },
            )
    store._events[target_index] = _replace_command_event_with_recomputed_hash(
        store._events[target_index],
        detail=tampered_detail,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is None
    assert reloaded_ledger.get(command.command_id) is not None
    assert (
        _recompute_event_hash(store._events[target_index])
        == store._events[target_index].event_hash
    )


def test_universal_command_orchestration_record_rejects_event_hash_tamper() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-event-hash-tamper",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    target_index = next(
        index
        for index, event in enumerate(store._events)
        if event.command_id == command.command_id
        and event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    store._events[target_index] = replace(
        store._events[target_index], event_hash="0" * 64
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is None
    assert reloaded_ledger.get(command.command_id) is not None
    assert len(reloaded_ledger.events_for(command.command_id)) >= 2


def test_universal_command_orchestration_record_rejects_command_trace_tamper() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-trace-tamper",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    target_index = next(
        index
        for index, event in enumerate(store._events)
        if event.command_id == command.command_id
        and event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    store._events[target_index] = _replace_command_event_with_recomputed_hash(
        store._events[target_index],
        trace_id="trc-command-envelope-spoofed",
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is None
    assert reloaded_ledger.get(command.command_id).trace_id == command.trace_id
    assert (
        _recompute_event_hash(store._events[target_index])
        == store._events[target_index].event_hash
    )


def test_universal_command_orchestration_record_rejects_incomplete_pipeline() -> None:
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-incomplete-pipeline",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    target_index = next(
        index
        for index, event in enumerate(store._events)
        if event.command_id == command.command_id
        and event.detail.get("cause") == "universal_action_kernel_dispatched"
    )
    tampered_detail = copy.deepcopy(store._events[target_index].detail)
    tampered_record = tampered_detail["universal_action_orchestration"]
    tampered_record["pipeline_stages"] = [
        stage
        for stage in tampered_record["pipeline_stages"]
        if stage["stage_kind"] != "memory"
    ]
    store._events[target_index] = _replace_command_event_with_recomputed_hash(
        store._events[target_index],
        detail=tampered_detail,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is None
    assert reloaded_ledger.get(command.command_id) is not None
    assert (
        _recompute_event_hash(store._events[target_index])
        == store._events[target_index].event_hash
    )


def test_universal_command_orchestration_record_rejects_cross_command_candidate() -> (
    None
):
    kernel, _executor = _kernel_with_capability()
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    source_command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-source",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )
    target_command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-target",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )
    universal_command_dispatch(
        ledger,
        kernel,
        source_command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    source_record = universal_command_orchestration_record_view(
        ledger, source_command.command_id
    )
    assert source_record is not None

    ledger.transition(
        target_command.command_id,
        CommandState.DISPATCHED,
        detail={
            "cause": "universal_action_kernel_dispatched",
            "universal_action_orchestration": source_record,
        },
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, target_command.command_id
    )

    assert replayed_record is None
    assert reloaded_ledger.get(target_command.command_id) is not None
    assert len(reloaded_ledger.events_for(target_command.command_id)) == 2


def test_universal_command_orchestration_record_rejects_malformed_only_event() -> None:
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-malformed-only",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )
    ledger.transition(
        command.command_id,
        CommandState.DISPATCHED,
        detail={
            "cause": "universal_action_kernel_dispatched",
            "universal_action_orchestration": {
                "uao_schema_version": "uao.v1",
                "raw_reasoning_included": True,
                "chain_of_thought": "private reasoning must not replay",
            },
        },
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    replayed_record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )

    assert replayed_record is None
    assert len(reloaded_ledger.events_for(command.command_id)) == 2
    assert reloaded_ledger.get(command.command_id) is not None


def test_universal_command_dispatch_records_blocked_kernel_result() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, executor = _kernel_with_capability(world_state=world_state)
    ledger = CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-block",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    current = ledger.get(command.command_id)
    events = ledger.events_for(command.command_id)

    assert result.blocked is True
    assert result.block_reason == "open_world_contradictions"
    assert result.dispatch_result is None
    assert executor.calls == 0
    assert current is not None
    assert current.state is CommandState.REQUIRES_REVIEW
    assert events[-1].detail["cause"] == "universal_action_kernel_blocked"
    assert (
        events[-1].detail["universal_action"]["block_reason"]
        == "open_world_contradictions"
    )
    assert events[-1].detail["universal_action"]["proof_hash"] == result.proof_hash
    assert (
        events[-1].detail["universal_action_orchestration"]["decision"]["status"]
        == "block"
    )


def test_universal_command_proof_view_replays_blocked_result() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, _executor = _kernel_with_capability(world_state=world_state)
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-proof-block",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    proof = universal_command_proof_view(reloaded_ledger, command.command_id)

    assert proof is not None
    assert proof.blocked is True
    assert proof.block_reason == "open_world_contradictions"
    assert proof.action_envelope["tenant"] == "tenant-1"
    assert proof.trace_ref == result.trace_ref
    assert proof.admission_receipt_ref == result.admission_receipt_ref
    assert proof.execution_receipt_ref is None
    assert proof.life_meaning_judgment == result.life_meaning_judgment.as_dict()
    assert proof.life_meaning_judgment["decision"] == "pause"
    assert proof.closure_state == "closed_blocked"
    assert proof.proof_hash == result.proof_hash
    assert proof.dispatch_ledger_hash == ""
    assert proof.terminal_certificate_id == ""
    assert proof.learning_admission_id == ""
    assert CommandState.REQUIRES_REVIEW.value in proof.state_sequence
    assert CommandState.TERMINALLY_CERTIFIED.value not in proof.state_sequence
    assert len(proof.event_hashes) >= 4


def test_universal_command_orchestration_record_replays_blocked_events() -> None:
    world_state = WorldStateEngine(clock=_clock)
    world_state.record_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction-1",
            entity_id="vendor-1",
            attribute="bank_account",
            conflicting_evidence_ids=("evidence-a", "evidence-b"),
            strategy=ContradictionStrategy.ESCALATE,
            resolved=False,
        )
    )
    kernel, _executor = _kernel_with_capability(world_state=world_state)
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-universal-record-block",
        intent="llm_completion",
        payload={"body": "run shell command"},
    )

    result = universal_command_dispatch(
        ledger,
        kernel,
        command.command_id,
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
        dispatch_route="shell_command",
        actor_roles=(REQUIRED_ROLE,),
        approval_refs=APPROVAL_REFS,
        approval_actor_ids=APPROVAL_ACTOR_IDS,
    )
    reloaded_ledger = CommandLedger(clock=_clock, store=store)

    record = universal_command_orchestration_record_view(
        reloaded_ledger, command.command_id
    )
    validation_errors = _validate_uao_record(record)

    assert validation_errors == []
    assert record is not None
    assert record["action_id"] == result.action_id
    assert record["decision"]["status"] == "block"
    assert record["decision"]["reason_code"] == "open_world_contradictions"
    assert record["execution_receipt_ref"] is None
    assert record["lineage"]["rejected_deltas"]


def _kernel_with_capability(
    *,
    world_state: WorldStateEngine | None = None,
    authority_policy: CapabilityAuthorityPolicy | None = None,
    recovery_plan: CapabilityRecoveryPlan | None = None,
    effect_names: tuple[str, ...] | None = None,
) -> tuple[UniversalActionKernel, FakeExecutor]:
    return _kernel(
        gate=_capability_admission_gate(
            authority_policy=authority_policy,
            recovery_plan=recovery_plan,
        ),
        world_state=world_state,
        effect_names=effect_names,
    )


def _kernel_without_capability() -> tuple[UniversalActionKernel, FakeExecutor]:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = CommandCapabilityAdmissionGate(registry=registry, clock=_clock)
    return _kernel(gate=gate)


def _kernel(
    *,
    gate: CommandCapabilityAdmissionGate,
    world_state: WorldStateEngine | None = None,
    effect_names: tuple[str, ...] | None = None,
) -> tuple[UniversalActionKernel, FakeExecutor]:
    executor = FakeExecutor()
    if effect_names is not None:
        executor.effect_names = effect_names
    dispatcher = Dispatcher(
        template_validator=TemplateValidator(),
        executors={"shell_command": executor},
        clock=_clock,
    )
    equilibrium = EquilibriumEngine()
    equilibrium.register_agent("actor-1")
    governed = GovernedDispatcher(
        dispatcher,
        equilibrium=equilibrium,
        capability_admission=gate,
        clock=_clock,
    )
    graph = OperationalGraph(clock=_clock)
    simulator = SimulationEngine(graph=graph, clock=_clock)
    kernel = UniversalActionKernel(
        world_state=world_state or WorldStateEngine(clock=_clock),
        simulator=simulator,
        capability_admission=gate,
        governed_dispatcher=governed,
        terminal_closure=TerminalClosureCertifier(clock=_clock),
        learning_admission=ClosureLearningAdmissionGate(clock=_clock),
        clock=_clock,
    )
    return kernel, executor


def _action_request(
    *,
    intent_id: str = "intent-1",
    risk_level: RiskLevel = RiskLevel.LOW,
    success_probability: float = 0.9,
    mode: str = "simulation",
    dispatch_request: DispatchRequest | None = None,
    metadata: dict | None = None,
    operating_substrate_projection: OperatingSubstrateSelfModelProjection | None = None,
    require_operating_substrate_projection: bool = False,
) -> UniversalActionRequest:
    request_metadata = {
        "actor_roles": (REQUIRED_ROLE,),
        "approval_refs": APPROVAL_REFS,
        "approval_actor_ids": APPROVAL_ACTOR_IDS,
    }
    if require_operating_substrate_projection:
        request_metadata["require_operating_substrate_projection"] = True
    if metadata is not None:
        request_metadata.update(metadata)
    return UniversalActionRequest(
        actor_id="actor-1",
        tenant_id="tenant-1",
        intent_id=intent_id,
        objective="Run a bounded shell command through the universal action kernel.",
        dispatch_request=dispatch_request or _dispatch_request(),
        risk_level=risk_level,
        success_probability=success_probability,
        mode=mode,
        metadata=request_metadata,
        operating_substrate_projection=operating_substrate_projection,
    )


def _dispatch_request(goal_id: str = "goal-1") -> DispatchRequest:
    return DispatchRequest(
        goal_id=goal_id,
        route="shell_command",
        template=VALID_TEMPLATE,
        bindings={"msg": "hello"},
    )


def _operating_substrate_projection(
    *,
    capability_id: str = "shell_command",
    admitted: bool = True,
    status: HealthStatus = HealthStatus.HEALTHY,
    solver_outcome: SolverOutcome = SolverOutcome.SOLVED_VERIFIED,
    world_state_status: HealthStatus = HealthStatus.HEALTHY,
) -> OperatingSubstrateSelfModelProjection:
    capability = SelfModelCapabilityProjection(
        capability_id=capability_id,
        maturity="C4",
        risk="low",
        admitted=admitted,
        status=status,
        reason="manifest_admitted" if admitted else "manifest_rejected",
        evidence_refs=("proof://capability",),
    )
    return OperatingSubstrateSelfModelProjection(
        projection_id="os-projection-uao",
        captured_at=NOW,
        capabilities=(capability,),
        subsystem_health=(
            SubsystemHealth(
                subsystem="capability_fabric",
                status=HealthStatus.HEALTHY,
                details="manifest evidence available",
            ),
            SubsystemHealth(
                subsystem="universal_action_orchestration",
                status=HealthStatus.HEALTHY,
                details="UAO kernel available",
            ),
        ),
        world_state_status=world_state_status,
        evidence_refs=("proof://operating-substrate",),
        capability_count=1,
        admitted_capability_count=1 if admitted else 0,
        degraded_capability_count=1 if status is HealthStatus.DEGRADED else 0,
        unknown_capability_count=1 if status is HealthStatus.UNKNOWN else 0,
        solver_outcome=solver_outcome,
    )


def _guard(record: dict, guard_name: str) -> dict:
    guard = next(
        item for item in record["admission_guards"] if item["guard"] == guard_name
    )
    assert isinstance(guard, dict)
    return guard


def _capability_admission_gate(
    *,
    authority_policy: CapabilityAuthorityPolicy | None = None,
    recovery_plan: CapabilityRecoveryPlan | None = None,
) -> CommandCapabilityAdmissionGate:
    registry = GovernedCapabilityRegistry(clock=_clock)
    compiler = DomainCapsuleCompiler(clock=_clock)
    entry = _certified_entry(
        "shell_command",
        authority_policy=authority_policy,
        recovery_plan=recovery_plan,
    )
    capsule = _certified_capsule("shell_command")
    compilation = compiler.compile(capsule=capsule, registry_entries=(entry,))
    installation = registry.install(compilation, (entry,))
    assert installation.errors == ()
    return CommandCapabilityAdmissionGate(registry=registry, clock=_clock)


def _certified_entry(
    capability_id: str,
    *,
    authority_policy: CapabilityAuthorityPolicy | None = None,
    recovery_plan: CapabilityRecoveryPlan | None = None,
) -> CapabilityRegistryEntry:
    entry = CapabilityRegistryEntry.from_mapping(
        _fixture("capability_registry_entry.json")
    )
    return CapabilityRegistryEntry(
        capability_id=capability_id,
        domain=entry.domain,
        version=entry.version,
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        effect_model=entry.effect_model,
        evidence_model=entry.evidence_model,
        authority_policy=authority_policy or entry.authority_policy,
        isolation_profile=entry.isolation_profile,
        recovery_plan=recovery_plan or entry.recovery_plan,
        cost_model=entry.cost_model,
        obligation_model=entry.obligation_model,
        certification_status=CapabilityCertificationStatus.CERTIFIED,
        metadata=entry.metadata,
        extensions=entry.extensions,
    )


def _certified_capsule(capability_id: str) -> DomainCapsule:
    capsule = DomainCapsule.from_mapping(_fixture("domain_capsule.json"))
    return DomainCapsule(
        capsule_id=capsule.capsule_id,
        domain=capsule.domain,
        version=capsule.version,
        ontology_refs=capsule.ontology_refs,
        capability_refs=(capability_id,),
        policy_refs=capsule.policy_refs,
        evidence_rules=capsule.evidence_rules,
        approval_rules=capsule.approval_rules,
        recovery_rules=capsule.recovery_rules,
        test_fixture_refs=capsule.test_fixture_refs,
        read_model_refs=capsule.read_model_refs,
        operator_view_refs=capsule.operator_view_refs,
        owner_team=capsule.owner_team,
        certification_status=DomainCapsuleCertificationStatus.CERTIFIED,
        metadata=capsule.metadata,
        extensions=capsule.extensions,
    )


def _fixture(name: str) -> dict:
    with open(FABRIC_FIXTURE_DIR / name, encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def _validate_uao_record(record: dict) -> list[str]:
    schema = json.loads(UAO_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(record)
    spec = importlib.util.spec_from_file_location(
        "validate_universal_action_orchestration", UAO_VALIDATOR_PATH
    )
    assert spec is not None
    validator = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(validator)
    errors = validator.validate_orchestration(record)
    assert isinstance(errors, list)
    return errors


def _pipeline_stage(record: dict, stage_kind: str) -> dict:
    return next(
        stage for stage in record["pipeline_stages"] if stage["stage_kind"] == stage_kind
    )


def _assert_memory_constitution(record: dict, *, learning_allowed: bool) -> None:
    memory_update = record["memory_update"]
    constitution = memory_update["constitution"]

    assert constitution["constitution_ref"].startswith("memory-constitution://")
    assert constitution["owner_ref"] == f"tenant://{record['tenant_id']}"
    assert constitution["scope_ref"] == f"tenant://{record['tenant_id']}"
    assert 0 <= constitution["confidence"] <= 1
    assert not set(constitution["allowed_uses"]).intersection(
        constitution["forbidden_uses"]
    )
    if learning_allowed:
        assert memory_update["learning_allowed"] is True
        assert "learning" in constitution["allowed_uses"]
        assert "learning" not in constitution["forbidden_uses"]
    else:
        assert memory_update["learning_allowed"] is False
        assert "learning" in constitution["forbidden_uses"]
    if memory_update["status"] == "recorded":
        assert memory_update["memory_ref"] in constitution["source_refs"]
        assert constitution["evidence_refs"]
        assert constitution["last_verified_at"]
        assert constitution["mutation_history_refs"]
