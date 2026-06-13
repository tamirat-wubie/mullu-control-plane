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
    CapabilityImprovementPortfolio,
    CapabilityWeaknessDiagnosis,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "capability_upgrade_plan.schema.json"
PORTFOLIO_SCHEMA_PATH = ROOT / "schemas" / "capability_improvement_portfolio.schema.json"


def test_upgrade_candidates_are_promotion_blocked() -> None:
    plan = AutonomousCapabilityUpgradeLoop().propose(_signal())
    eval_types = {item.eval_type for item in plan.candidate.evals}

    assert plan.activation_blocked is True
    assert plan.operator_review_required is True
    assert plan.candidate.promotion_blocked is True
    assert plan.candidate.change_command_ref.startswith("change-command:")
    assert plan.candidate.change_certificate_ref.startswith("change-certificate:")
    assert {"regression", "replay_determinism", "tenant_boundary", "provider_failure"}.issubset(eval_types)
    assert "maturity_below_live_read" in plan.diagnosis.weakness_codes


def test_critical_governance_changes_require_second_approval() -> None:
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


def test_capability_upgrade_plan_schema_valid() -> None:
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


def test_capability_upgrade_evidence_refs_reject_structured_values() -> None:
    try:
        _signal(evidence_refs=({"proof": "capability_health:email-send"},))
    except ValueError as exc:
        signal_error = str(exc)
    else:
        signal_error = ""

    try:
        CapabilityWeaknessDiagnosis(
            diagnosis_id="diagnosis-structured-evidence",
            capability_id="email.send.with_approval",
            weakness_codes=("maturity_below_live_read",),
            severity="high",
            recommended_change_classes=("capability",),
            evidence_refs=(["capability_health:email-send"],),
        )
    except ValueError as exc:
        diagnosis_error = str(exc)
    else:
        diagnosis_error = ""

    assert signal_error == "evidence_refs_invalid"
    assert diagnosis_error == "evidence_refs_invalid"


def test_systemic_weaknesses_are_ranked() -> None:
    portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
        (
            _signal(
                capability_id="email.send",
                success_rate=0.86,
                failure_count=7,
                mean_latency_ms=7100,
                evidence_refs=("capability_health:email-send",),
            ),
            _signal(
                capability_id="browser.inspect",
                success_rate=0.96,
                failure_count=1,
                mean_latency_ms=7300,
                evidence_refs=("capability_health:browser-inspect",),
            ),
            _signal(
                capability_id="support.read",
                maturity_level="C5",
                success_rate=0.995,
                failure_count=0,
                mean_latency_ms=200,
                blocker_codes=(),
                evidence_refs=("capability_health:support-read",),
            ),
        ),
        generated_at="2026-05-15T12:00:00+00:00",
        requested_change_classes_by_capability={"email.send": ("policy", "authority_rules")},
    )

    assert portfolio.activation_blocked is True
    assert portfolio.operator_review_required is True
    assert portfolio.prioritized_capability_ids[0] == "email.send"
    assert "latency_above_threshold" in portfolio.systemic_weakness_codes
    assert "portfolio_activation_blocked" in portfolio.blocked_reasons
    assert all(plan.activation_blocked for plan in portfolio.plans)
    assert portfolio.metadata["direct_registry_mutation_allowed"] is False
    assert portfolio.portfolio_id.startswith("capability-improvement-portfolio-")


def test_capability_improvement_portfolios_are_activation_blocked() -> None:
    portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
        (_signal(),),
        generated_at="2026-05-15T12:00:00+00:00",
    )

    assert portfolio.activation_blocked is True
    assert portfolio.operator_review_required is True
    assert all(plan.activation_blocked for plan in portfolio.plans)
    assert all(plan.candidate.promotion_blocked for plan in portfolio.plans)
    assert "portfolio_activation_blocked" in portfolio.blocked_reasons


def test_capability_improvement_portfolio_schema_valid() -> None:
    portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
        (_signal(),),
        generated_at="2026-05-15T12:00:00+00:00",
    )
    errors = _validate_schema_instance(_load_schema(PORTFOLIO_SCHEMA_PATH), portfolio.to_json_dict())

    assert errors == []
    assert portfolio.metadata["portfolio_is_not_execution"] is True
    assert portfolio.metadata["autonomous_direct_deploy_allowed"] is False
    assert portfolio.metadata["observed_signal_count"] == 1
    assert portfolio.portfolio_hash


def test_capability_improvement_portfolio_identity_sets_are_unique() -> None:
    plan = AutonomousCapabilityUpgradeLoop().propose(_signal())
    base = {
        "portfolio_id": "pending",
        "generated_at": "2026-05-15T12:00:00+00:00",
        "plans": (plan,),
        "prioritized_capability_ids": (plan.capability_id,),
        "systemic_weakness_codes": ("latency_above_threshold",),
        "blocked_reasons": ("portfolio_activation_blocked",),
        "operator_review_required": True,
        "activation_blocked": True,
    }

    priority_error = _portfolio_error(base | {"prioritized_capability_ids": (plan.capability_id, plan.capability_id)})
    systemic_error = _portfolio_error(
        base | {"systemic_weakness_codes": ("latency_above_threshold", "latency_above_threshold")}
    )
    blocked_error = _portfolio_error(
        base | {"blocked_reasons": ("portfolio_activation_blocked", "portfolio_activation_blocked")}
    )
    duplicate_plan_error = _portfolio_error(base | {"plans": (plan, plan)})
    payload = CapabilityImprovementPortfolio(**base).to_json_dict()
    payload["prioritized_capability_ids"] = [plan.capability_id, plan.capability_id]
    schema_errors = _validate_schema_instance(_load_schema(PORTFOLIO_SCHEMA_PATH), payload)

    assert priority_error == "portfolio_priority_must_be_unique"
    assert systemic_error == "portfolio_systemic_weakness_codes_must_be_unique"
    assert blocked_error == "portfolio_blocked_reasons_must_be_unique"
    assert duplicate_plan_error == "portfolio_plan_capabilities_must_be_unique"
    assert "$.prioritized_capability_ids: array items must be unique" in schema_errors


def test_capability_improvement_portfolio_rejects_invalid_inputs() -> None:
    loop = AutonomousCapabilityUpgradeLoop()
    try:
        loop.propose_portfolio((), generated_at="2026-05-15T12:00:00+00:00")
    except ValueError as exc:
        empty_error = str(exc)
    else:
        empty_error = ""

    try:
        loop.propose_portfolio(
            (
                _signal(capability_id="email.send", evidence_refs=("capability_health:email-send:1",)),
                _signal(capability_id="email.send", evidence_refs=("capability_health:email-send:2",)),
            ),
            generated_at="2026-05-15T12:00:00+00:00",
        )
    except ValueError as exc:
        duplicate_error = str(exc)
    else:
        duplicate_error = ""

    try:
        loop.propose_portfolio(
            (_signal(),),
            generated_at="2026-05-15T12:00:00+00:00",
            max_candidates=0,
        )
    except ValueError as exc:
        limit_error = str(exc)
    else:
        limit_error = ""

    assert empty_error == "portfolio_signals_required"
    assert duplicate_error == "duplicate_capability_signal"
    assert limit_error == "max_candidates_positive"


def test_capability_improvement_portfolio_keeps_highest_priority_slice() -> None:
    portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
        (
            _signal(capability_id="low.risk", success_rate=0.99, failure_count=0, mean_latency_ms=100),
            _signal(
                capability_id="critical.policy",
                blocker_codes=("approval_rule_gap",),
                evidence_refs=("capability_health:critical-policy",),
            ),
        ),
        generated_at="2026-05-15T12:00:00+00:00",
        requested_change_classes_by_capability={"critical.policy": ("policy",)},
        max_candidates=1,
    )
    payload = portfolio.to_json_dict()

    assert portfolio.prioritized_capability_ids == ("critical.policy",)
    assert portfolio.metadata["observed_signal_count"] == 2
    assert portfolio.metadata["selected_candidate_count"] == 1
    assert portfolio.plans[0].candidate.second_approval_required is True
    assert payload["plans"][0]["capability_id"] == "critical.policy"
    assert CapabilityImprovementPortfolio is not None


def _portfolio_error(payload: dict[str, object]) -> str:
    try:
        CapabilityImprovementPortfolio(**payload)
    except ValueError as exc:
        return str(exc)
    return ""


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
