"""Purpose: verify canonical MAF runtime fixtures round-trip through MCOI contracts.
Governance scope: cross-runtime fixture conformance for mirrored MAF/MCOI domain contracts.
Dependencies: shared integration fixtures and MCOI contract modules.
Invariants: canonical payload witnesses preserve field meaning and exact JSON-safe rendering across runtimes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.function import FunctionType, ServiceFunctionTemplate
from mcoi_runtime.contracts.goal import GoalPlan, GoalPriority, GoalDescriptor, SubGoal, SubGoalStatus
from mcoi_runtime.contracts.job import JobDescriptor, JobPriority
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationRecord,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.roles import RoleDescriptor
from mcoi_runtime.contracts.simulation import RiskLevel, SimulationComparison
from mcoi_runtime.contracts.supervisor import (
    LivelockStrategy,
    SupervisorDecision,
    SupervisorPhase,
    SupervisorTick,
    TickOutcome,
)


FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "maf_runtime"


def _load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _build_event_record(payload: dict) -> EventRecord:
    return EventRecord(
        event_id=payload["event_id"],
        event_type=EventType(payload["event_type"]),
        source=EventSource(payload["source"]),
        correlation_id=payload["correlation_id"],
        payload=payload["payload"],
        emitted_at=payload["emitted_at"],
    )


def _build_supervisor_tick(payload: dict) -> SupervisorTick:
    return SupervisorTick(
        tick_id=payload["tick_id"],
        tick_number=payload["tick_number"],
        phase_sequence=tuple(SupervisorPhase(value) for value in payload["phase_sequence"]),
        events_polled=payload["events_polled"],
        obligations_evaluated=payload["obligations_evaluated"],
        deadlines_checked=payload["deadlines_checked"],
        reactions_fired=payload["reactions_fired"],
        decisions=tuple(
            SupervisorDecision(
                decision_id=decision["decision_id"],
                action_type=decision["action_type"],
                target_id=decision["target_id"],
                reason=decision["reason"],
                governance_approved=decision["governance_approved"],
                decided_at=decision["decided_at"],
                metadata=decision.get("metadata", {}),
            )
            for decision in payload["decisions"]
        ),
        outcome=TickOutcome(payload["outcome"]),
        errors=tuple(payload.get("errors", [])),
        started_at=payload["started_at"],
        completed_at=payload["completed_at"],
        duration_ms=payload["duration_ms"],
    )


def _build_simulation_comparison(payload: dict) -> SimulationComparison:
    return SimulationComparison(
        comparison_id=payload["comparison_id"],
        request_id=payload["request_id"],
        ranked_option_ids=tuple(payload["ranked_option_ids"]),
        scores=payload["scores"],
        top_risk_level=RiskLevel(payload["top_risk_level"]),
        review_burden=payload["review_burden"],
    )


def _build_job_descriptor(payload: dict) -> JobDescriptor:
    return JobDescriptor(
        job_id=payload["job_id"],
        name=payload["name"],
        description=payload["description"],
        priority=JobPriority(payload["priority"]),
        created_at=payload["created_at"],
        goal_id=payload.get("goal_id"),
        workflow_id=payload.get("workflow_id"),
        deadline=payload.get("deadline"),
        sla_target_minutes=payload.get("sla_target_minutes"),
        metadata=payload.get("metadata", {}),
    )


def _build_goal_plan(payload: dict) -> GoalPlan:
    return GoalPlan(
        plan_id=payload["plan_id"],
        goal_id=payload["goal_id"],
        sub_goals=tuple(
            SubGoal(
                sub_goal_id=sub_goal["sub_goal_id"],
                goal_id=sub_goal["goal_id"],
                description=sub_goal["description"],
                status=SubGoalStatus(sub_goal["status"]),
                skill_id=sub_goal.get("skill_id"),
                workflow_id=sub_goal.get("workflow_id"),
                predecessors=tuple(sub_goal.get("predecessors", [])),
            )
            for sub_goal in payload["sub_goals"]
        ),
        created_at=payload["created_at"],
        version=payload["version"],
    )


def _build_obligation_record(payload: dict) -> ObligationRecord:
    return ObligationRecord(
        obligation_id=payload["obligation_id"],
        trigger=ObligationTrigger(payload["trigger"]),
        trigger_ref_id=payload["trigger_ref_id"],
        state=ObligationState(payload["state"]),
        owner=ObligationOwner(**payload["owner"]),
        deadline=ObligationDeadline(**payload["deadline"]),
        description=payload["description"],
        correlation_id=payload["correlation_id"],
        metadata=payload["metadata"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
    )


def _build_service_function_template(payload: dict) -> ServiceFunctionTemplate:
    return ServiceFunctionTemplate(
        function_id=payload["function_id"],
        name=payload["name"],
        function_type=FunctionType(payload["function_type"]),
        description=payload["description"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_role_descriptor(payload: dict) -> RoleDescriptor:
    return RoleDescriptor(
        role_id=payload["role_id"],
        name=payload["name"],
        description=payload["description"],
        required_skills=tuple(payload["required_skills"]),
        approval_required=payload["approval_required"],
        max_concurrent_per_worker=payload["max_concurrent_per_worker"],
        metadata=payload["metadata"],
    )


@pytest.mark.parametrize(
    ("fixture_name", "builder"),
    [
        ("event_record.json", _build_event_record),
        ("supervisor_tick.json", _build_supervisor_tick),
        ("simulation_comparison.json", _build_simulation_comparison),
        ("job_descriptor.json", _build_job_descriptor),
        ("goal_plan.json", _build_goal_plan),
        ("obligation_record.json", _build_obligation_record),
        ("service_function_template.json", _build_service_function_template),
        ("role_descriptor.json", _build_role_descriptor),
    ],
)
def test_maf_runtime_fixture_round_trips_exactly_through_mcoi_contracts(
    fixture_name: str,
    builder,
) -> None:
    fixture_payload = _load_fixture(fixture_name)
    contract = builder(fixture_payload)

    rendered = contract.to_json_dict()

    assert isinstance(rendered, dict)
    assert rendered == fixture_payload
    assert json.loads(contract.to_json()) == fixture_payload
