"""Gateway autonomous test-generation tests.

Purpose: verify certified failure traces expand into permanent governed test
proposals without executing or activating them.
Governance scope: failure evidence admission, approval bypass expansion,
tenant-boundary cases, prompt-injection variants, sandbox scenarios, replay
fixtures, and schema compatibility.
Dependencies: gateway.autonomous_test_generation and public generation schema.
Invariants:
  - Failure traces without evidence are rejected.
  - High-risk failures generate governance and replay coverage.
  - Plans are activation-blocked and operator-review required.
"""

from __future__ import annotations

from pathlib import Path

from gateway.autonomous_test_generation import (
    AutonomousTestGenerationEngine,
    FailureTrace,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "autonomous_test_generation_plan.schema.json"


def test_approval_bypass_generates_permanent_governance_variants() -> None:
    plan = AutonomousTestGenerationEngine().generate(
        tenant_id="tenant-a",
        traces=(_trace(failure_type="approval_bypass", risk_tier="critical"),),
    )
    test_types = {case.test_type for case in plan.cases}
    mutations = {mutation for case in plan.cases for mutation in case.input_mutations}

    assert plan.activation_blocked is True
    assert plan.operator_review_required is True
    assert {"approval", "prompt_injection", "tenant_boundary", "temporal", "channel_variant", "replay_fixture"}.issubset(test_types)
    assert {"expired_approval", "wrong_tenant", "channel:slack", "channel:whatsapp"}.issubset(mutations)
    assert all(case.evidence_refs == ("trace:evidence:1",) for case in plan.cases)


def test_budget_failure_generates_budget_and_replay_cases() -> None:
    plan = AutonomousTestGenerationEngine().generate(
        tenant_id="tenant-a",
        traces=(_trace(failure_type="budget_exhaustion", risk_tier="high"),),
    )
    budget_cases = [case for case in plan.cases if case.test_type == "budget"]

    assert "budget" in plan.coverage_requirements
    assert budget_cases
    assert any("budget_gate" in case.required_controls for case in budget_cases)
    assert any(case.expected_outcome == "budget_denied" for case in budget_cases)
    assert plan.replay_library_refs


def test_sandbox_escape_generates_sandbox_scenario_and_policy_case() -> None:
    plan = AutonomousTestGenerationEngine().generate(
        tenant_id="tenant-a",
        traces=(_trace(failure_type="sandbox_escape", risk_tier="critical", capability_id="computer.command.run"),),
    )
    sandbox_cases = [case for case in plan.cases if case.sandbox_required]
    governance_cases = [case for case in plan.cases if case.test_type == "governance"]

    assert sandbox_cases
    assert governance_cases
    assert any(case.test_type == "sandbox_scenario" for case in sandbox_cases)
    assert any("sandbox" in case.required_controls for case in sandbox_cases)
    assert "sandbox_scenario" in plan.coverage_requirements


def test_autonomous_test_generation_plan_validates_against_schema() -> None:
    plan = AutonomousTestGenerationEngine().generate(
        tenant_id="tenant-a",
        traces=(_trace(failure_type="prompt_injection", risk_tier="high"),),
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), plan.to_json_dict())

    assert errors == []
    assert plan.plan_id.startswith("test-generation-plan-")
    assert plan.metadata["plan_is_not_execution"] is True
    assert plan.metadata["case_count"] == len(plan.cases)
    assert "prompt_injection" in plan.coverage_requirements


def test_failure_trace_requires_evidence_refs() -> None:
    try:
        _trace(evidence_refs=())
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "evidence_refs_required"
    assert FailureTrace is not None
    assert AutonomousTestGenerationEngine is not None


def _trace(**overrides: object) -> FailureTrace:
    payload = {
        "trace_id": "failure-trace-1",
        "tenant_id": "tenant-a",
        "command_id": "cmd-1",
        "capability_id": "payment.dispatch",
        "channel": "web",
        "action": "payment.dispatch",
        "failure_type": "approval_bypass",
        "failure_reason": "payment executed without fresh approval",
        "observed_at": "2026-05-05T12:00:00+00:00",
        "risk_tier": "critical",
        "evidence_refs": ("trace:evidence:1",),
        "actor_id": "actor-1",
    }
    payload.update(overrides)
    return FailureTrace(**payload)
