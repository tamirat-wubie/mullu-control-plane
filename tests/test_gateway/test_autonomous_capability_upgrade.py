"""Gateway autonomous capability upgrade loop tests.

Purpose: verify capability-health signals become governed upgrade proposals
instead of direct registry mutations.
Governance scope: weakness diagnosis, eval generation, sandbox evidence,
ChangeCommand and ChangeCertificate gates, canary, terminal closure, learning
admission, approval requirements, and schema compatibility.
Dependencies: gateway.autonomous_capability_upgrade and public upgrade schema.
Invariants:
  - Upgrade candidates are promotion-blocked.
  - Critical governance changes require approval and second approval.
  - Plans are schema-valid proposal surfaces, not execution surfaces.
"""

from __future__ import annotations

from pathlib import Path

from gateway.autonomous_capability_upgrade import (
    AutonomousCapabilityUpgradeLoop,
    CapabilityHealthSignal,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "capability_upgrade_plan.schema.json"


def test_weak_capability_generates_blocked_upgrade_candidate() -> None:
    plan = AutonomousCapabilityUpgradeLoop().propose(_signal())
    eval_types = {item.eval_type for item in plan.candidate.evals}

    assert plan.activation_blocked is True
    assert plan.operator_review_required is True
    assert plan.candidate.promotion_blocked is True
    assert plan.candidate.change_command_ref.startswith("change-command:")
    assert plan.candidate.change_certificate_ref.startswith("change-certificate:")
    assert {"regression", "replay_determinism", "tenant_boundary", "provider_failure"}.issubset(eval_types)
    assert "maturity_below_live_read" in plan.diagnosis.weakness_codes


def test_policy_upgrade_is_critical_and_requires_second_approval() -> None:
    plan = AutonomousCapabilityUpgradeLoop().propose(
        _signal(capability_id="policy.mutate", blocker_codes=("approval_rule_gap",)),
        requested_change_classes=("policy", "authority_rules"),
    )
    eval_types = {item.eval_type for item in plan.candidate.evals}

    assert plan.diagnosis.severity == "critical"
    assert plan.candidate.authority_approval_required is True
    assert plan.candidate.second_approval_required is True
    assert "second_approval" in eval_types
    assert "policy_bypass" in eval_types
    assert "authority_approval_required" in plan.blocked_reasons
    assert "second_approval_required" in plan.blocked_reasons


def test_audit_proof_command_spine_changes_require_integrity_evals() -> None:
    plan = AutonomousCapabilityUpgradeLoop().propose(
        _signal(capability_id="proof.anchor", maturity_level="C5"),
        desired_maturity_level="C7",
        requested_change_classes=("audit", "proof", "command_spine"),
    )
    eval_types = {item.eval_type for item in plan.candidate.evals}

    assert plan.candidate.target_maturity_level == "C7"
    assert plan.diagnosis.severity == "critical"
    assert {"audit_integrity", "proof_integrity", "terminal_closure"}.issubset(eval_types)
    assert plan.candidate.metadata["terminal_closure_required"] is True
    assert plan.candidate.metadata["learning_admission_required"] is True


def test_capability_upgrade_plan_validates_against_schema() -> None:
    plan = AutonomousCapabilityUpgradeLoop().propose(_signal())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), plan.to_json_dict())

    assert errors == []
    assert plan.plan_id.startswith("capability-upgrade-plan-")
    assert plan.plan_hash
    assert plan.metadata["plan_is_not_execution"] is True
    assert plan.metadata["autonomous_direct_deploy_allowed"] is False


def test_health_signal_requires_evidence_refs() -> None:
    try:
        _signal(evidence_refs=())
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "evidence_refs_required"
    assert CapabilityHealthSignal is not None
    assert AutonomousCapabilityUpgradeLoop is not None


def _signal(**overrides: object) -> CapabilityHealthSignal:
    payload = {
        "capability_id": "email.send.with_approval",
        "observed_at": "2026-05-05T12:00:00+00:00",
        "maturity_level": "C3",
        "success_rate": 0.91,
        "failure_count": 3,
        "mean_latency_ms": 6200,
        "cost_per_success": 0.25,
        "open_incidents": 0,
        "blocker_codes": ("sandbox_receipt_missing",),
        "evidence_refs": ("capability_health:email-send",),
    }
    payload.update(overrides)
    return CapabilityHealthSignal(**payload)
