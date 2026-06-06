"""Tests for Symbolic Simulation Engine contracts.

Purpose: prove pre-action simulation envelopes preserve governed lifecycle invariants.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS contract validation.
Dependencies: mcoi_runtime.contracts.symbolic_simulation_engine and simulation primitives.
Invariants: branches, outcomes, comparison, verdict, decision, and execution gate are linked.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.simulation import (
    ConsequenceEstimate,
    ObligationProjection,
    RiskEstimate,
    RiskLevel,
    SimulationComparison,
    SimulationOption,
    SimulationOutcome,
    SimulationRequest,
    SimulationVerdict,
    VerdictType,
)
from mcoi_runtime.contracts.symbolic_simulation_engine import (
    SymbolicSimulationBranch,
    SymbolicSimulationDecision,
    SymbolicSimulationDecisionKind,
    SymbolicSimulationEngineRun,
    SymbolicSimulationExecutionGate,
    SymbolicSimulationGateStatus,
)


TS = "2026-06-06T10:00:00+00:00"


def _request(**overrides: object) -> SimulationRequest:
    values = {
        "request_id": "sim-request-001",
        "context_type": "uao_action",
        "context_id": "action-send-message-001",
        "description": "Compare message send against escalation before execution.",
        "options": (
            SimulationOption(
                option_id="option-send",
                label="Send governed message",
                risk_level=RiskLevel.LOW,
                estimated_cost=0.1,
                estimated_duration_seconds=3.0,
                success_probability=0.91,
            ),
            SimulationOption(
                option_id="option-escalate",
                label="Escalate to operator",
                risk_level=RiskLevel.MINIMAL,
                estimated_cost=0.0,
                estimated_duration_seconds=30.0,
                success_probability=0.99,
            ),
        ),
    }
    values.update(overrides)
    return SimulationRequest(**values)


def _outcome(option_id: str, outcome_id: str, risk_level: RiskLevel) -> SimulationOutcome:
    return SimulationOutcome(
        outcome_id=outcome_id,
        option_id=option_id,
        consequence=ConsequenceEstimate(
            estimate_id=f"consequence-{option_id}",
            option_id=option_id,
            affected_node_ids=("state://message",),
            new_edges_count=1,
            new_obligations_count=0,
            blocked_nodes_count=0,
            unblocked_nodes_count=1,
        ),
        risk=RiskEstimate(
            estimate_id=f"risk-{option_id}",
            option_id=option_id,
            risk_level=risk_level,
            incident_probability=0.04,
            review_burden=1,
            provider_exposure_count=0,
            verification_difficulty="bounded",
            rationale="local policy and receipt evidence available",
        ),
        obligation_projection=ObligationProjection(
            projection_id=f"obligation-{option_id}",
            option_id=option_id,
            new_obligations=("receipt://simulation-verification",),
            fulfilled_obligations=(),
            deadline_pressure=0,
        ),
        simulated_at=TS,
    )


def _run(**overrides: object) -> SymbolicSimulationEngineRun:
    request = _request()
    outcomes = (
        _outcome("option-send", "outcome-send", RiskLevel.LOW),
        _outcome("option-escalate", "outcome-escalate", RiskLevel.MINIMAL),
    )
    comparison = SimulationComparison(
        comparison_id="comparison-001",
        request_id="sim-request-001",
        ranked_option_ids=("option-send", "option-escalate"),
        scores={"option-send": 0.88, "option-escalate": 0.76},
        top_risk_level=RiskLevel.LOW,
        review_burden=0.2,
    )
    verdict = SimulationVerdict(
        verdict_id="verdict-001",
        comparison_id="comparison-001",
        verdict_type=VerdictType.PROCEED_WITH_CAUTION,
        recommended_option_id="option-send",
        confidence=0.87,
        reasons=("lowest bounded risk with receipt evidence",),
    )
    decision = SymbolicSimulationDecision(
        decision_id="decision-001",
        comparison_id="comparison-001",
        verdict_id="verdict-001",
        selected_option_id="option-send",
        decision_kind=SymbolicSimulationDecisionKind.EXECUTE,
        rationale_refs=("verdict-001", "comparison-001"),
        receipt_refs=("receipt://sse/decision-001",),
        decided_at=TS,
    )
    values = {
        "run_id": "sse-run-001",
        "version": "sse.v1",
        "generated_at": TS,
        "action_ref": "uao://action/send-message-001",
        "action_snapshot_ref": "snapshot://action/send-message-001/pre",
        "request": request,
        "branches": (
            SymbolicSimulationBranch(
                branch_id="branch-send",
                option_id="option-send",
                outcome_id="outcome-send",
                predicted_state_refs=("state://message/sent",),
                evidence_refs=("receipt://simulation/outcome-send",),
                risk_level=RiskLevel.LOW,
                confidence=0.88,
                metadata={"rank": 1},
            ),
            SymbolicSimulationBranch(
                branch_id="branch-escalate",
                option_id="option-escalate",
                outcome_id="outcome-escalate",
                predicted_state_refs=("state://message/escalated",),
                evidence_refs=("receipt://simulation/outcome-escalate",),
                risk_level=RiskLevel.MINIMAL,
                confidence=0.76,
                metadata={"rank": 2},
            ),
        ),
        "outcomes": outcomes,
        "comparison": comparison,
        "verdict": verdict,
        "decision": decision,
        "execution_gate": SymbolicSimulationExecutionGate(
            gate_id="gate-001",
            decision_id="decision-001",
            gate_status=SymbolicSimulationGateStatus.ALLOW,
            can_execute=True,
            required_approval_refs=(),
            evidence_refs=("receipt://sse/decision-001", "receipt://uao/preflight-001"),
            evaluated_at=TS,
        ),
        "receipt_refs": ("receipt://sse/run-001", "receipt://uao/preflight-001"),
        "metadata": {"foundation_mode": True, "sequence": "action_simulate_compare_decide_execute_gate"},
    }
    values.update(overrides)
    return SymbolicSimulationEngineRun(**values)


def test_symbolic_simulation_engine_run_round_trips_to_json_dict() -> None:
    run = _run()
    payload = run.to_json_dict()

    assert payload["run_id"] == "sse-run-001"
    assert payload["branches"][0]["risk_level"] == "low"
    assert payload["decision"]["decision_kind"] == "execute"
    assert payload["execution_gate"]["gate_status"] == "allow"


def test_symbolic_simulation_engine_rejects_branch_dangling_outcome() -> None:
    bad_branch = SymbolicSimulationBranch(
        branch_id="branch-missing",
        option_id="option-send",
        outcome_id="outcome-missing",
        predicted_state_refs=("state://missing",),
        evidence_refs=("receipt://missing",),
        risk_level=RiskLevel.LOW,
        confidence=0.5,
    )

    with pytest.raises(ValueError, match="outcome_id"):
        _run(branches=(bad_branch,))


def test_symbolic_simulation_engine_rejects_comparison_request_mismatch() -> None:
    bad_comparison = SimulationComparison(
        comparison_id="comparison-001",
        request_id="wrong-request",
        ranked_option_ids=("option-send", "option-escalate"),
        scores={"option-send": 0.88, "option-escalate": 0.76},
        top_risk_level=RiskLevel.LOW,
        review_burden=0.2,
    )

    with pytest.raises(ValueError, match="comparison request_id"):
        _run(comparison=bad_comparison)


def test_symbolic_simulation_engine_rejects_execute_without_allow_gate() -> None:
    with pytest.raises(ValueError, match="gate_status allow"):
        SymbolicSimulationExecutionGate(
            gate_id="gate-bad",
            decision_id="decision-001",
            gate_status=SymbolicSimulationGateStatus.ALLOW,
            can_execute=False,
            required_approval_refs=(),
            evidence_refs=("receipt://sse/decision-001",),
            evaluated_at=TS,
        )


def test_symbolic_simulation_engine_rejects_non_execute_can_execute_gate() -> None:
    defer_decision = SymbolicSimulationDecision(
        decision_id="decision-001",
        comparison_id="comparison-001",
        verdict_id="verdict-001",
        selected_option_id="option-send",
        decision_kind=SymbolicSimulationDecisionKind.DEFER,
        rationale_refs=("verdict-001",),
        receipt_refs=("receipt://sse/decision-001",),
        decided_at=TS,
    )

    with pytest.raises(ValueError, match="only execute decisions"):
        _run(decision=defer_decision)
