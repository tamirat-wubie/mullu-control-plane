"""Gateway policy studio tests.

Purpose: verify operator policy simulation and bounded bypass probes.
Governance scope: approval simulation, stale evidence, business hours,
tenant boundary, self-approval denial, side-effect blocking, and schema anchor.
Dependencies: gateway.policy_studio and schemas/policy_studio_session.schema.json.
Invariants:
  - High-risk side effects require approval before allowance.
  - Self-approval cannot authorize high-risk side effects.
  - Stale evidence and outside-hours cases escalate deterministically.
  - Studio sessions are read-only and hash-bound.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.policy_studio import (
    PolicyBypassCounterexample,
    PolicyRule,
    PolicyRuleEffect,
    PolicyScenario,
    PolicySimulation,
    PolicyScenarioVerdict,
    PolicySimulator,
    PolicyStudio,
    PolicyProbeStatus,
    policy_studio_session_to_json_dict,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "policy_studio_session.schema.json"


def test_policy_simulator_escalates_high_value_refund_without_approval() -> None:
    simulation = PolicySimulator().simulate(
        policy_id="support-refund-policy",
        rules=_rules(),
        scenario=PolicyScenario(
            scenario_id="scenario-refund-750",
            tenant_id="tenant-a",
            actor_id="support-agent",
            actor_role="support_agent",
            action="refund_customer",
            amount=750,
            requested_at="2026-05-05T14:00:00Z",
            evidence_fresh=True,
        ),
    )

    assert simulation.verdict == PolicyScenarioVerdict.ESCALATE
    assert "approval_required" in simulation.reasons
    assert simulation.required_approvals == ("support_manager",)
    assert simulation.side_effects_allowed is False
    assert simulation.metadata["simulation_is_read_only"] is True


def test_policy_simulator_denies_self_approval_for_side_effect() -> None:
    simulation = PolicySimulator().simulate(
        policy_id="support-refund-policy",
        rules=_rules(),
        scenario=PolicyScenario(
            scenario_id="scenario-self-approved",
            tenant_id="tenant-a",
            actor_id="support-agent-1",
            actor_role="support_agent",
            action="refund_customer",
            amount=750,
            requested_at="2026-05-05T14:00:00Z",
            evidence_fresh=True,
            approval_ref="approval://case-001",
            approver_id="support-agent-1",
            approver_role="support_manager",
        ),
    )

    assert simulation.verdict == PolicyScenarioVerdict.DENY
    assert "self_approval_forbidden" in simulation.reasons
    assert simulation.side_effects_allowed is False
    assert "amount_requires_manager_approval" not in simulation.reasons


def test_policy_simulator_escalates_stale_evidence_and_outside_hours() -> None:
    simulation = PolicySimulator().simulate(
        policy_id="support-refund-policy",
        rules=_rules(),
        scenario=PolicyScenario(
            scenario_id="scenario-stale-after-hours",
            tenant_id="tenant-a",
            actor_id="support-agent-2",
            actor_role="support_agent",
            action="refund_customer",
            amount=750,
            requested_at="2026-05-05T22:00:00Z",
            evidence_fresh=False,
            approval_ref="approval://case-002",
            approver_id="manager-1",
            approver_role="support_manager",
            evidence_refs=("evidence://stale-refund",),
        ),
    )

    assert simulation.verdict == PolicyScenarioVerdict.ESCALATE
    assert "evidence_stale" in simulation.reasons
    assert "outside_business_hours" in simulation.reasons
    assert simulation.side_effects_allowed is False
    assert simulation.evidence_refs == ("evidence://stale-refund",)


def test_policy_simulator_denies_cross_tenant_resource_access() -> None:
    simulation = PolicySimulator().simulate(
        policy_id="support-refund-policy",
        rules=_rules(),
        scenario=PolicyScenario(
            scenario_id="scenario-cross-tenant",
            tenant_id="tenant-a",
            actor_id="support-agent-3",
            actor_role="support_agent",
            action="refund_customer",
            amount=250,
            requested_at="2026-05-05T14:00:00Z",
            tenant_matches_resource=False,
            approval_ref="approval://case-003",
            approver_id="manager-1",
            approver_role="support_manager",
        ),
    )

    assert simulation.verdict == PolicyScenarioVerdict.DENY
    assert "tenant_boundary_denied" in simulation.reasons
    assert simulation.side_effects_allowed is False
    assert simulation.matched_rule_ids


def test_policy_studio_probe_report_is_proved_when_side_effects_are_blocked() -> None:
    session = PolicyStudio().run_session(
        session_id="policy-studio-001",
        policy_id="support-refund-policy",
        rules=_rules(),
        scenarios=(
            PolicyScenario(
                scenario_id="scenario-refund-750",
                tenant_id="tenant-a",
                actor_id="support-agent",
                actor_role="support_agent",
                action="refund_customer",
                amount=750,
                requested_at="2026-05-05T14:00:00Z",
                evidence_fresh=True,
            ),
            PolicyScenario(
                scenario_id="scenario-approved-refund",
                tenant_id="tenant-a",
                actor_id="support-agent",
                actor_role="support_agent",
                action="refund_customer",
                amount=750,
                requested_at="2026-05-05T14:00:00Z",
                evidence_fresh=True,
                approval_ref="approval://case-004",
                approver_id="manager-1",
                approver_role="support_manager",
            ),
        ),
    )

    assert session.probe_report.status == PolicyProbeStatus.PROVED
    assert session.probe_report.counterexample_count == 0
    assert len(session.simulations) == 2
    assert session.rules[0].rule_hash
    assert session.session_hash


def test_policy_studio_schema_exposes_session_contract() -> None:
    session = PolicyStudio().run_session(
        session_id="policy-studio-001",
        policy_id="support-refund-policy",
        rules=_rules(),
        scenarios=(
            PolicyScenario(
                scenario_id="scenario-refund-750",
                tenant_id="tenant-a",
                actor_id="support-agent",
                actor_role="support_agent",
                action="refund_customer",
                amount=750,
                requested_at="2026-05-05T14:00:00Z",
            ),
        ),
    )
    payload = policy_studio_session_to_json_dict(session)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:policy-studio-session:1"
    assert schema["$defs"]["rule"]["properties"]["tenant_match_required"]["const"] is True
    assert schema["properties"]["metadata"]["properties"]["policy_studio_is_read_only"]["const"] is True
    assert payload["probe_report"]["metadata"]["policy_weakening_allowed"] is False


def test_policy_studio_evidence_refs_reject_structured_values() -> None:
    try:
        PolicyScenario(
            scenario_id="scenario-structured-evidence",
            tenant_id="tenant-a",
            actor_id="support-agent",
            actor_role="support_agent",
            action="refund_customer",
            requested_at="2026-05-05T14:00:00Z",
            evidence_refs=({"proof": "evidence://refund"},),
        )
    except ValueError as exc:
        scenario_error = str(exc)
    else:
        scenario_error = ""

    try:
        PolicySimulation(
            simulation_id="simulation-structured-evidence",
            policy_id="support-refund-policy",
            scenario_id="scenario-structured-evidence",
            verdict=PolicyScenarioVerdict.ESCALATE,
            reasons=("approval_required",),
            matched_rule_ids=("refund-manager-approval",),
            required_approvals=("support_manager",),
            side_effects_allowed=False,
            evidence_refs=(["evidence://refund"],),
        )
    except ValueError as exc:
        simulation_error = str(exc)
    else:
        simulation_error = ""

    try:
        PolicyBypassCounterexample(
            probe_id="probe-structured-evidence",
            scenario_id="scenario-structured-evidence",
            reason="unsafe_allow",
            simulation_id="simulation-structured-evidence",
            evidence_refs=({"proof": "evidence://refund"},),
        )
    except ValueError as exc:
        counterexample_error = str(exc)
    else:
        counterexample_error = ""

    assert scenario_error == "evidence_refs_invalid"
    assert simulation_error == "evidence_refs_invalid"
    assert counterexample_error == "evidence_refs_invalid"


def _rules() -> tuple[PolicyRule, ...]:
    return (
        PolicyRule(
            rule_id="refund-manager-approval",
            description="Refunds of 500 or more require manager approval.",
            effect=PolicyRuleEffect.REQUIRE_APPROVAL,
            action="refund_customer",
            min_amount=500,
            required_approval_role="support_manager",
        ),
        PolicyRule(
            rule_id="refund-fresh-evidence",
            description="Refunds require fresh evidence.",
            effect=PolicyRuleEffect.ESCALATE,
            action="refund_customer",
            requires_fresh_evidence=True,
        ),
        PolicyRule(
            rule_id="refund-business-hours",
            description="Refunds outside business hours require review.",
            effect=PolicyRuleEffect.ESCALATE,
            action="refund_customer",
            business_hours_only=True,
        ),
    )
