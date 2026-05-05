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

from mcoi_runtime.contracts.event import (
    EventCorrelation,
    EventEnvelope,
    EventReaction,
    EventRecord,
    EventSource,
    EventSubscription,
    EventType,
    EventWindow,
)
from mcoi_runtime.contracts.function import (
    CommunicationStyle,
    FunctionMetricsSnapshot,
    FunctionOutcomeRecord,
    FunctionPolicyBinding,
    FunctionQueueProfile,
    FunctionSlaProfile,
    FunctionType,
    ServiceFunctionTemplate,
)
from mcoi_runtime.contracts.goal import GoalPlan, GoalPriority, GoalDescriptor, SubGoal, SubGoalStatus
from mcoi_runtime.contracts.job import JobDescriptor, JobPriority
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationRecord,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.roles import (
    AssignmentDecision,
    AssignmentPolicy,
    AssignmentStrategy,
    HandoffReason,
    HandoffRecord,
    RoleDescriptor,
    TeamQueueState,
    WorkerCapacity,
    WorkerProfile,
    WorkerStatus,
    WorkloadSnapshot,
)
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
from mcoi_runtime.contracts.supervisor import (
    LivelockStrategy,
    LivelockRecord,
    RuntimeHeartbeat,
    CheckpointStatus,
    SupervisorCheckpoint,
    SupervisorDecision,
    SupervisorHealth,
    SupervisorPhase,
    SupervisorPolicy,
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


def _build_event_envelope(payload: dict) -> EventEnvelope:
    return EventEnvelope(
        envelope_id=payload["envelope_id"],
        event=_build_event_record(payload["event"]),
        target_subsystems=tuple(payload["target_subsystems"]),
        priority=payload["priority"],
        delivered=payload["delivered"],
        delivered_at=payload["delivered_at"],
    )


def _build_event_subscription(payload: dict) -> EventSubscription:
    return EventSubscription(
        subscription_id=payload["subscription_id"],
        event_type=EventType(payload["event_type"]),
        subscriber_id=payload["subscriber_id"],
        reaction_id=payload["reaction_id"],
        filter_source=EventSource(payload["filter_source"]),
        active=payload["active"],
        created_at=payload["created_at"],
    )


def _build_event_reaction(payload: dict) -> EventReaction:
    return EventReaction(
        reaction_id=payload["reaction_id"],
        event_id=payload["event_id"],
        subscription_id=payload["subscription_id"],
        action_taken=payload["action_taken"],
        result=payload["result"],
        reacted_at=payload["reacted_at"],
    )


def _build_event_window(payload: dict) -> EventWindow:
    return EventWindow(
        window_id=payload["window_id"],
        correlation_id=payload["correlation_id"],
        window_start=payload["window_start"],
        window_end=payload["window_end"],
        event_count=payload["event_count"],
    )


def _build_event_correlation(payload: dict) -> EventCorrelation:
    return EventCorrelation(
        correlation_id=payload["correlation_id"],
        event_ids=tuple(payload["event_ids"]),
        root_event_id=payload["root_event_id"],
        description=payload["description"],
        created_at=payload["created_at"],
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


def _build_simulation_option(payload: dict) -> SimulationOption:
    return SimulationOption(
        option_id=payload["option_id"],
        label=payload["label"],
        risk_level=RiskLevel(payload["risk_level"]),
        estimated_cost=payload["estimated_cost"],
        estimated_duration_seconds=payload["estimated_duration_seconds"],
        success_probability=payload["success_probability"],
    )


def _build_simulation_request(payload: dict) -> SimulationRequest:
    return SimulationRequest(
        request_id=payload["request_id"],
        context_type=payload["context_type"],
        context_id=payload["context_id"],
        description=payload["description"],
        options=tuple(_build_simulation_option(option) for option in payload["options"]),
    )


def _build_simulation_outcome(payload: dict) -> SimulationOutcome:
    return SimulationOutcome(
        outcome_id=payload["outcome_id"],
        option_id=payload["option_id"],
        consequence=ConsequenceEstimate(**payload["consequence"]),
        risk=RiskEstimate(
            estimate_id=payload["risk"]["estimate_id"],
            option_id=payload["risk"]["option_id"],
            risk_level=RiskLevel(payload["risk"]["risk_level"]),
            incident_probability=payload["risk"]["incident_probability"],
            review_burden=payload["risk"]["review_burden"],
            provider_exposure_count=payload["risk"]["provider_exposure_count"],
            verification_difficulty=payload["risk"]["verification_difficulty"],
            rationale=payload["risk"]["rationale"],
        ),
        obligation_projection=ObligationProjection(**payload["obligation_projection"]),
        simulated_at=payload["simulated_at"],
    )


def _build_simulation_verdict(payload: dict) -> SimulationVerdict:
    return SimulationVerdict(
        verdict_id=payload["verdict_id"],
        comparison_id=payload["comparison_id"],
        verdict_type=VerdictType(payload["verdict_type"]),
        recommended_option_id=payload["recommended_option_id"],
        confidence=payload["confidence"],
        reasons=tuple(payload["reasons"]),
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


def _build_function_policy_binding(payload: dict) -> FunctionPolicyBinding:
    return FunctionPolicyBinding(
        binding_id=payload["binding_id"],
        function_id=payload["function_id"],
        policy_pack_id=payload["policy_pack_id"],
        autonomy_mode=payload["autonomy_mode"],
        review_required=payload["review_required"],
        deployment_profile_id=payload["deployment_profile_id"],
    )


def _build_function_sla_profile(payload: dict) -> FunctionSlaProfile:
    return FunctionSlaProfile(
        function_id=payload["function_id"],
        target_completion_minutes=payload["target_completion_minutes"],
        approval_latency_minutes=payload["approval_latency_minutes"],
        escalation_threshold_minutes=payload["escalation_threshold_minutes"],
    )


def _build_function_queue_profile(payload: dict) -> FunctionQueueProfile:
    return FunctionQueueProfile(
        function_id=payload["function_id"],
        team_id=payload["team_id"],
        default_role_id=payload["default_role_id"],
        communication_style=CommunicationStyle(payload["communication_style"]),
        max_concurrent_jobs=payload["max_concurrent_jobs"],
        escalation_chain_id=payload["escalation_chain_id"],
    )


def _build_assignment_policy(payload: dict) -> AssignmentPolicy:
    return AssignmentPolicy(
        policy_id=payload["policy_id"],
        role_id=payload["role_id"],
        strategy=AssignmentStrategy(payload["strategy"]),
        fallback_team_id=payload["fallback_team_id"],
        escalation_chain_id=payload["escalation_chain_id"],
    )


def _build_worker_capacity(payload: dict) -> WorkerCapacity:
    return WorkerCapacity(
        worker_id=payload["worker_id"],
        max_concurrent=payload["max_concurrent"],
        current_load=payload["current_load"],
        available_slots=payload["available_slots"],
        updated_at=payload["updated_at"],
    )


def _build_team_queue_state(payload: dict) -> TeamQueueState:
    return TeamQueueState(
        team_id=payload["team_id"],
        queued_jobs=payload["queued_jobs"],
        assigned_jobs=payload["assigned_jobs"],
        waiting_jobs=payload["waiting_jobs"],
        overloaded_workers=payload["overloaded_workers"],
        captured_at=payload["captured_at"],
    )


def _build_worker_profile(payload: dict) -> WorkerProfile:
    return WorkerProfile(
        worker_id=payload["worker_id"],
        name=payload["name"],
        roles=tuple(payload["roles"]),
        max_concurrent_jobs=payload["max_concurrent_jobs"],
        status=WorkerStatus(payload["status"]),
        metadata=payload["metadata"],
    )


def _build_assignment_decision(payload: dict) -> AssignmentDecision:
    return AssignmentDecision(
        decision_id=payload["decision_id"],
        job_id=payload["job_id"],
        worker_id=payload["worker_id"],
        role_id=payload["role_id"],
        reason=payload["reason"],
        decided_at=payload["decided_at"],
    )


def _build_handoff_record(payload: dict) -> HandoffRecord:
    return HandoffRecord(
        handoff_id=payload["handoff_id"],
        job_id=payload["job_id"],
        from_worker_id=payload["from_worker_id"],
        to_worker_id=payload["to_worker_id"],
        reason=HandoffReason(payload["reason"]),
        thread_id=payload["thread_id"],
        handoff_at=payload["handoff_at"],
    )


def _build_workload_snapshot(payload: dict) -> WorkloadSnapshot:
    return WorkloadSnapshot(
        snapshot_id=payload["snapshot_id"],
        team_id=payload["team_id"],
        worker_capacities=tuple(_build_worker_capacity(entry) for entry in payload["worker_capacities"]),
        captured_at=payload["captured_at"],
    )


def _build_function_outcome_record(payload: dict) -> FunctionOutcomeRecord:
    return FunctionOutcomeRecord(
        outcome_id=payload["outcome_id"],
        function_id=payload["function_id"],
        job_id=payload["job_id"],
        completed=payload["completed"],
        completion_minutes=payload["completion_minutes"],
        escalated=payload["escalated"],
        drift_detected=payload["drift_detected"],
        recorded_at=payload["recorded_at"],
    )


def _build_function_metrics_snapshot(payload: dict) -> FunctionMetricsSnapshot:
    return FunctionMetricsSnapshot(
        function_id=payload["function_id"],
        period_start=payload["period_start"],
        period_end=payload["period_end"],
        total_jobs=payload["total_jobs"],
        completed_jobs=payload["completed_jobs"],
        failed_jobs=payload["failed_jobs"],
        avg_completion_minutes=payload["avg_completion_minutes"],
        escalation_count=payload["escalation_count"],
        drift_count=payload["drift_count"],
        captured_at=payload["captured_at"],
    )


def _build_supervisor_policy(payload: dict) -> SupervisorPolicy:
    return SupervisorPolicy(
        policy_id=payload["policy_id"],
        tick_interval_ms=payload["tick_interval_ms"],
        max_events_per_tick=payload["max_events_per_tick"],
        max_actions_per_tick=payload["max_actions_per_tick"],
        backpressure_threshold=payload["backpressure_threshold"],
        livelock_repeat_threshold=payload["livelock_repeat_threshold"],
        livelock_strategy=LivelockStrategy(payload["livelock_strategy"]),
        heartbeat_every_n_ticks=payload["heartbeat_every_n_ticks"],
        checkpoint_every_n_ticks=payload["checkpoint_every_n_ticks"],
        max_consecutive_errors=payload["max_consecutive_errors"],
        created_at=payload["created_at"],
    )


def _build_supervisor_health(payload: dict) -> SupervisorHealth:
    return SupervisorHealth(
        health_id=payload["health_id"],
        tick_number=payload["tick_number"],
        phase=SupervisorPhase(payload["phase"]),
        consecutive_errors=payload["consecutive_errors"],
        consecutive_idle_ticks=payload["consecutive_idle_ticks"],
        backpressure_active=payload["backpressure_active"],
        livelock_detected=payload["livelock_detected"],
        open_obligations=payload["open_obligations"],
        pending_events=payload["pending_events"],
        overall_confidence=payload["overall_confidence"],
        assessed_at=payload["assessed_at"],
    )


def _build_runtime_heartbeat(payload: dict) -> RuntimeHeartbeat:
    return RuntimeHeartbeat(
        heartbeat_id=payload["heartbeat_id"],
        tick_number=payload["tick_number"],
        phase=SupervisorPhase(payload["phase"]),
        outcome_of_last_tick=TickOutcome(payload["outcome_of_last_tick"]),
        open_obligations=payload["open_obligations"],
        pending_events=payload["pending_events"],
        uptime_ticks=payload["uptime_ticks"],
        emitted_at=payload["emitted_at"],
    )


def _build_supervisor_checkpoint(payload: dict) -> SupervisorCheckpoint:
    return SupervisorCheckpoint(
        checkpoint_id=payload["checkpoint_id"],
        tick_number=payload["tick_number"],
        phase=SupervisorPhase(payload["phase"]),
        status=CheckpointStatus(payload["status"]),
        open_obligation_ids=tuple(payload["open_obligation_ids"]),
        pending_event_count=payload["pending_event_count"],
        consecutive_errors=payload["consecutive_errors"],
        consecutive_idle_ticks=payload["consecutive_idle_ticks"],
        recent_tick_outcomes=tuple(TickOutcome(value) for value in payload["recent_tick_outcomes"]),
        state_hash=payload["state_hash"],
        created_at=payload["created_at"],
    )


def _build_livelock_record(payload: dict) -> LivelockRecord:
    return LivelockRecord(
        livelock_id=payload["livelock_id"],
        tick_number=payload["tick_number"],
        repeated_pattern=payload["repeated_pattern"],
        repeat_count=payload["repeat_count"],
        strategy_applied=LivelockStrategy(payload["strategy_applied"]),
        resolved=payload["resolved"],
        detected_at=payload["detected_at"],
        resolution_detail=payload["resolution_detail"],
    )


@pytest.mark.parametrize(
    ("fixture_name", "builder"),
    [
        ("event_correlation.json", _build_event_correlation),
        ("event_envelope.json", _build_event_envelope),
        ("event_record.json", _build_event_record),
        ("event_reaction.json", _build_event_reaction),
        ("event_subscription.json", _build_event_subscription),
        ("event_window.json", _build_event_window),
        ("supervisor_tick.json", _build_supervisor_tick),
        ("simulation_comparison.json", _build_simulation_comparison),
        ("job_descriptor.json", _build_job_descriptor),
        ("goal_plan.json", _build_goal_plan),
        ("obligation_record.json", _build_obligation_record),
        ("service_function_template.json", _build_service_function_template),
        ("role_descriptor.json", _build_role_descriptor),
        ("function_policy_binding.json", _build_function_policy_binding),
        ("function_sla_profile.json", _build_function_sla_profile),
        ("function_queue_profile.json", _build_function_queue_profile),
        ("assignment_policy.json", _build_assignment_policy),
        ("worker_capacity.json", _build_worker_capacity),
        ("team_queue_state.json", _build_team_queue_state),
        ("worker_profile.json", _build_worker_profile),
        ("assignment_decision.json", _build_assignment_decision),
        ("handoff_record.json", _build_handoff_record),
        ("workload_snapshot.json", _build_workload_snapshot),
        ("function_outcome_record.json", _build_function_outcome_record),
        ("function_metrics_snapshot.json", _build_function_metrics_snapshot),
        ("simulation_option.json", _build_simulation_option),
        ("simulation_request.json", _build_simulation_request),
        ("simulation_outcome.json", _build_simulation_outcome),
        ("simulation_verdict.json", _build_simulation_verdict),
        ("supervisor_policy.json", _build_supervisor_policy),
        ("supervisor_health.json", _build_supervisor_health),
        ("runtime_heartbeat.json", _build_runtime_heartbeat),
        ("supervisor_checkpoint.json", _build_supervisor_checkpoint),
        ("livelock_record.json", _build_livelock_record),
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
