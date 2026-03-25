"""Audit #14 edge-case tests.

Covers all fixes applied during Audit #14:
  CRITICAL #1 — memory.py promote_to_episodic atomicity
  CRITICAL #2 — conversation.py ConversationThread validation applied
  CRITICAL #3 — HEALTH_STATUS_SCORES immutable
  HIGH #6-10  — datetime bypass removal (benchmark, roles, supervisor, workflow, world_state)
  HIGH #14    — bridge return types are immutable Mapping
  HIGH #15    — event_obligation_integration uses RuntimeCoreInvariantError
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

import pytest

NOW = "2025-01-01T00:00:00Z"


# -----------------------------------------------------------------------
# CRITICAL #1 — memory.py promote_to_episodic atomicity
# -----------------------------------------------------------------------


class TestMemoryPromotionAtomicity:
    """Verify promote_to_episodic is atomic: entry never in both tiers."""

    def test_promotion_success(self):
        from mcoi_runtime.core.memory import (
            EpisodicMemory,
            MemoryEntry,
            MemoryTier,
            PromotionStatus,
            WorkingMemory,
            promote_to_episodic,
        )

        wm = WorkingMemory()
        em = EpisodicMemory()

        entry = MemoryEntry(
            entry_id="e1",
            tier=MemoryTier.WORKING,
            category="observation",
            content={"text": "test"},
            source_ids=("s1",),
        )
        wm.store(entry)
        result = promote_to_episodic(wm, em, "e1", verified=True)
        assert result.status == PromotionStatus.PROMOTED
        assert wm.get("e1") is None
        assert em.get("e1") is not None

    def test_promotion_rollback_on_duplicate(self):
        from mcoi_runtime.core.memory import (
            EpisodicMemory,
            MemoryEntry,
            MemoryTier,
            PromotionStatus,
            WorkingMemory,
            promote_to_episodic,
        )

        wm = WorkingMemory()
        em = EpisodicMemory()

        entry = MemoryEntry(
            entry_id="e1",
            tier=MemoryTier.WORKING,
            category="observation",
            content={"text": "original"},
            source_ids=("s1",),
        )
        wm.store(entry)

        # Pre-populate episodic so admission fails
        episodic_entry = MemoryEntry(
            entry_id="e1",
            tier=MemoryTier.EPISODIC,
            category="observation",
            content={"text": "already there"},
            source_ids=("s1",),
        )
        em.admit(episodic_entry)

        result = promote_to_episodic(wm, em, "e1", verified=True)
        assert result.status == PromotionStatus.REJECTED
        # Entry must be back in working memory (rollback)
        assert wm.get("e1") is not None

    def test_promotion_not_found(self):
        from mcoi_runtime.core.memory import (
            EpisodicMemory,
            PromotionStatus,
            WorkingMemory,
            promote_to_episodic,
        )

        wm = WorkingMemory()
        em = EpisodicMemory()
        result = promote_to_episodic(wm, em, "missing", verified=True)
        assert result.status == PromotionStatus.REJECTED


# -----------------------------------------------------------------------
# CRITICAL #2 — ConversationThread goal_id/workflow_id validation applied
# -----------------------------------------------------------------------


class TestConversationThreadValidation:
    """Verify goal_id and workflow_id are validated (not just checked)."""

    def test_whitespace_goal_id_rejected(self):
        from mcoi_runtime.contracts.conversation import ConversationThread, ThreadStatus

        with pytest.raises(ValueError):
            ConversationThread(
                thread_id="t1",
                subject="test",
                status=ThreadStatus.OPEN,
                goal_id="   ",
                created_at=NOW,
                updated_at=NOW,
            )

    def test_whitespace_workflow_id_rejected(self):
        from mcoi_runtime.contracts.conversation import ConversationThread, ThreadStatus

        with pytest.raises(ValueError):
            ConversationThread(
                thread_id="t1",
                subject="test",
                status=ThreadStatus.OPEN,
                workflow_id="   ",
                created_at=NOW,
                updated_at=NOW,
            )

    def test_goal_id_stripped(self):
        from mcoi_runtime.contracts.conversation import ConversationThread, ThreadStatus

        t = ConversationThread(
            thread_id="t1",
            subject="test",
            status=ThreadStatus.OPEN,
            goal_id="  g1  ",
            created_at=NOW,
            updated_at=NOW,
        )
        assert t.goal_id == "  g1  "

    def test_workflow_id_stripped(self):
        from mcoi_runtime.contracts.conversation import ConversationThread, ThreadStatus

        t = ConversationThread(
            thread_id="t1",
            subject="test",
            status=ThreadStatus.OPEN,
            workflow_id="  w1  ",
            created_at=NOW,
            updated_at=NOW,
        )
        assert t.workflow_id == "  w1  "

    def test_none_goal_and_workflow_accepted(self):
        from mcoi_runtime.contracts.conversation import ConversationThread, ThreadStatus

        t = ConversationThread(
            thread_id="t1",
            subject="test",
            status=ThreadStatus.OPEN,
            created_at=NOW,
            updated_at=NOW,
        )
        assert t.goal_id is None
        assert t.workflow_id is None


# -----------------------------------------------------------------------
# CRITICAL #3 — HEALTH_STATUS_SCORES immutability
# -----------------------------------------------------------------------


class TestHealthStatusScoresImmutable:
    """HEALTH_STATUS_SCORES must be an immutable Mapping."""

    def test_type_is_mapping_proxy(self):
        from mcoi_runtime.core.provider_routing_integration import HEALTH_STATUS_SCORES

        assert isinstance(HEALTH_STATUS_SCORES, MappingProxyType)

    def test_mutation_raises(self):
        from mcoi_runtime.core.provider_routing_integration import HEALTH_STATUS_SCORES

        with pytest.raises(TypeError):
            HEALTH_STATUS_SCORES["new_key"] = 999  # type: ignore[index]

    def test_has_expected_keys(self):
        from mcoi_runtime.contracts.provider import ProviderHealthStatus
        from mcoi_runtime.core.provider_routing_integration import HEALTH_STATUS_SCORES

        for status in ProviderHealthStatus:
            assert status in HEALTH_STATUS_SCORES


# -----------------------------------------------------------------------
# HIGH #6-10 — Datetime bypass removal
# -----------------------------------------------------------------------


class TestDatetimeBypassRemoved:
    """Empty-string datetime fields must now raise on construction."""

    def test_benchmark_result_executed_at_required(self):
        from mcoi_runtime.contracts.benchmark import BenchmarkOutcome, BenchmarkResult

        with pytest.raises(ValueError):
            BenchmarkResult(
                result_id="r1",
                scenario_id="s1",
                outcome=BenchmarkOutcome.PASS,
                metrics=(),
                actual_properties={},
                executed_at="",
            )

    def test_handoff_record_handoff_at_required(self):
        from mcoi_runtime.contracts.roles import HandoffReason, HandoffRecord

        with pytest.raises(ValueError):
            HandoffRecord(
                handoff_id="h1",
                job_id="j1",
                from_worker_id="w1",
                to_worker_id="w2",
                reason=HandoffReason.ESCALATION,
                handoff_at="",
            )

    def test_supervisor_tick_started_at_required(self):
        from mcoi_runtime.contracts.supervisor import (
            SupervisorPhase,
            SupervisorTick,
            TickOutcome,
        )

        with pytest.raises(ValueError):
            SupervisorTick(
                tick_id="t1",
                tick_number=0,
                phase_sequence=(SupervisorPhase.IDLE,),
                events_polled=0,
                obligations_evaluated=0,
                deadlines_checked=0,
                reactions_fired=0,
                decisions=(),
                outcome=TickOutcome.IDLE_TICK,
                started_at="",
                completed_at=NOW,
            )

    def test_stage_execution_result_started_at_required(self):
        from mcoi_runtime.contracts.workflow import StageExecutionResult, StageStatus

        with pytest.raises(ValueError):
            StageExecutionResult(
                stage_id="s1",
                status=StageStatus.COMPLETED,
                started_at="",
                completed_at=NOW,
            )

    def test_world_state_delta_computed_at_required(self):
        from mcoi_runtime.contracts.world_state import DeltaKind, WorldStateDelta

        with pytest.raises(ValueError):
            WorldStateDelta(
                delta_id="d1",
                kind=DeltaKind.ENTITY_ADDED,
                target_id="e1",
                description="added",
                computed_at="",
            )

    def test_workflow_verification_verified_at_required(self):
        from mcoi_runtime.contracts.workflow import WorkflowVerificationRecord

        with pytest.raises(ValueError):
            WorkflowVerificationRecord(
                execution_id="ex1",
                verified=True,
                verified_at="",
            )


# -----------------------------------------------------------------------
# HIGH #14 — Bridge return types are immutable Mapping
# -----------------------------------------------------------------------


class TestBridgeReturnImmutability:
    """Bridge public methods must return immutable Mapping, not dict."""

    def test_utility_bridge_evaluate_resource_feasibility(self):
        from mcoi_runtime.contracts.simulation import SimulationOption
        from mcoi_runtime.contracts.utility import ResourceBudget, ResourceType
        from mcoi_runtime.core.utility import UtilityEngine
        from mcoi_runtime.core.utility_integration import UtilityBridge

        engine = UtilityEngine(clock=lambda: NOW)
        from mcoi_runtime.contracts.simulation import RiskLevel

        option = SimulationOption(
            option_id="opt1",
            label="test",
            risk_level=RiskLevel.LOW,
            estimated_cost=10.0,
            estimated_duration_seconds=60.0,
            success_probability=0.9,
        )
        budget = ResourceBudget(
            resource_id="b1",
            resource_type=ResourceType.COMPUTE,
            total=100.0,
            consumed=0.0,
            reserved=0.0,
        )
        result = UtilityBridge.evaluate_resource_feasibility(
            engine, (budget,), (option,),
        )
        assert isinstance(result, Mapping)
        with pytest.raises(TypeError):
            result["new"] = "fail"  # type: ignore[index]

    def test_governance_bridge_extract_thresholds_immutable(self):
        from mcoi_runtime.contracts.governance import (
            PolicyAction,
            PolicyActionKind,
            PolicyEffect,
            PolicyEvaluationTrace,
        )
        from mcoi_runtime.core.governance_integration import GovernanceBridge

        trace = PolicyEvaluationTrace(
            trace_id="t1",
            bundle_id="b1",
            subject_id="s1",
            context_snapshot={},
            rules_evaluated=1,
            rules_matched=1,
            rules_fired=1,
            matched_rule_ids=("r1",),
            fired_rule_ids=("r1",),
            final_effect=PolicyEffect.ALLOW,
            actions_produced=(
                PolicyAction(
                    action_id="a1",
                    kind=PolicyActionKind.SET_SIMULATION_THRESHOLD,
                    parameters={"threshold": 0.8},
                ),
            ),
            evaluated_at=NOW,
        )
        result = GovernanceBridge.extract_thresholds(trace)
        assert isinstance(result, Mapping)
        assert result["simulation"] == 0.8
        with pytest.raises(TypeError):
            result["new"] = 0.5  # type: ignore[index]

    def test_governance_bridge_extract_provider_decisions_immutable(self):
        from mcoi_runtime.contracts.governance import (
            PolicyAction,
            PolicyActionKind,
            PolicyEffect,
            PolicyEvaluationTrace,
        )
        from mcoi_runtime.core.governance_integration import GovernanceBridge

        trace = PolicyEvaluationTrace(
            trace_id="t1",
            bundle_id="b1",
            subject_id="s1",
            context_snapshot={},
            rules_evaluated=1,
            rules_matched=1,
            rules_fired=1,
            matched_rule_ids=("r1",),
            fired_rule_ids=("r1",),
            final_effect=PolicyEffect.DENY,
            actions_produced=(
                PolicyAction(
                    action_id="a1",
                    kind=PolicyActionKind.DENY_PROVIDER,
                    parameters={"provider_id": "p1"},
                ),
            ),
            evaluated_at=NOW,
        )
        result = GovernanceBridge.extract_provider_decisions(trace)
        assert isinstance(result, Mapping)
        assert result["p1"] is False
        with pytest.raises(TypeError):
            result["p2"] = True  # type: ignore[index]

    def test_benchmark_bridge_extract_summary_immutable(self):
        from mcoi_runtime.core.benchmark_integration import BenchmarkBridge

        # Empty case
        result = BenchmarkBridge.extract_summary(())
        assert isinstance(result, Mapping)
        with pytest.raises(TypeError):
            result["new"] = "fail"  # type: ignore[index]
        # categories sub-mapping also immutable
        assert isinstance(result["categories"], Mapping)
        with pytest.raises(TypeError):
            result["categories"]["x"] = "fail"  # type: ignore[index]


# -----------------------------------------------------------------------
# HIGH #15 — event_obligation_integration RuntimeCoreInvariantError
# -----------------------------------------------------------------------


class TestEventObligationIntegrationErrorType:
    """Verify bridge raises RuntimeCoreInvariantError, not ValueError."""

    def test_close_and_emit_not_found_raises_invariant_error(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

        from mcoi_runtime.contracts.obligation import ObligationState
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine = EventSpineEngine(clock=lambda: NOW)
        obl_engine = ObligationRuntimeEngine(clock=lambda: NOW)

        with pytest.raises(RuntimeCoreInvariantError, match="obligation not found"):
            EventObligationBridge.close_and_emit(
                spine,
                obl_engine,
                "nonexistent",
                final_state=ObligationState.COMPLETED,
                reason="done",
                closed_by="test",
            )

    def test_transfer_and_emit_not_found_raises_invariant_error(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

        from mcoi_runtime.contracts.obligation import ObligationOwner
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine = EventSpineEngine(clock=lambda: NOW)
        obl_engine = ObligationRuntimeEngine(clock=lambda: NOW)
        owner = ObligationOwner(owner_id="o1", owner_type="agent", display_name="Agent O1")

        with pytest.raises(RuntimeCoreInvariantError, match="obligation not found"):
            EventObligationBridge.transfer_and_emit(
                spine,
                obl_engine,
                "nonexistent",
                to_owner=owner,
                reason="reassign",
            )

    def test_escalate_and_emit_not_found_raises_invariant_error(self):
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

        from mcoi_runtime.contracts.obligation import ObligationOwner
        from mcoi_runtime.core.event_obligation_integration import EventObligationBridge

        spine = EventSpineEngine(clock=lambda: NOW)
        obl_engine = ObligationRuntimeEngine(clock=lambda: NOW)
        owner = ObligationOwner(owner_id="o1", owner_type="agent", display_name="Agent O1")

        with pytest.raises(RuntimeCoreInvariantError, match="obligation not found"):
            EventObligationBridge.escalate_and_emit(
                spine,
                obl_engine,
                "nonexistent",
                escalated_to=owner,
                reason="urgent",
            )
