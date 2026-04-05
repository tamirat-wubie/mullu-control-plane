"""Integration tests for AdversarialOperationsBridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.fault_injection import (
    FaultSeverity,
    FaultSpec,
    FaultTargetKind,
    FaultType,
    InjectionMode,
)
from mcoi_runtime.core.adversarial_operations import AdversarialOperationsBridge
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.fault_injection import FaultInjectionEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

NOW = "2026-03-20T12:00:00+00:00"


def _build():
    fe = FaultInjectionEngine()
    es = EventSpineEngine()
    me = MemoryMeshEngine()
    bridge = AdversarialOperationsBridge(
        fault_engine=fe, event_spine=es, memory_engine=me,
    )
    return fe, es, me, bridge


def _add_spec(fe, spec_id="fs-1", target=FaultTargetKind.PROVIDER,
              repeat=3, mode=InjectionMode.REPEATED):
    fe.register_spec(FaultSpec(
        spec_id=spec_id, fault_type=FaultType.FAILURE,
        target_kind=target, severity=FaultSeverity.MEDIUM,
        injection_mode=mode, repeat_count=repeat,
        created_at=NOW,
    ))


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid(self):
        _, _, _, bridge = _build()
        assert bridge is not None

    def test_bad_fault_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="fault_engine"):
            AdversarialOperationsBridge(
                fault_engine="bad",
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
            )

    def test_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            AdversarialOperationsBridge(
                fault_engine=FaultInjectionEngine(),
                event_spine="bad",
                memory_engine=MemoryMeshEngine(),
            )

    def test_bad_memory_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            AdversarialOperationsBridge(
                fault_engine=FaultInjectionEngine(),
                event_spine=EventSpineEngine(),
                memory_engine="bad",
            )


# ---------------------------------------------------------------------------
# Targeted injection
# ---------------------------------------------------------------------------


class TestTargetedInjection:
    def test_inject_into_supervisor(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.SUPERVISOR)
        result = bridge.inject_into_supervisor_tick(tick=0)
        assert len(result["records"]) == 1
        assert result["event"] is not None

    def test_inject_into_provider(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.PROVIDER)
        result = bridge.inject_into_provider_routing(tick=0)
        assert len(result["records"]) == 1

    def test_inject_into_communication(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.COMMUNICATION)
        result = bridge.inject_into_communication_surface(tick=0)
        assert len(result["records"]) == 1

    def test_inject_into_artifact(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.ARTIFACT_INGESTION)
        result = bridge.inject_into_artifact_ingestion(tick=0)
        assert len(result["records"]) == 1

    def test_inject_into_checkpoint(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.CHECKPOINT)
        result = bridge.inject_into_checkpoint_restore(tick=0)
        assert len(result["records"]) == 1

    def test_inject_into_obligation(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.OBLIGATION_RUNTIME)
        result = bridge.inject_into_obligation_runtime(tick=0)
        assert len(result["records"]) == 1

    def test_inject_into_reaction(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.REACTION)
        result = bridge.inject_into_reaction_engine(tick=0)
        assert len(result["records"]) == 1

    def test_inject_into_domain_pack(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.DOMAIN_PACK)
        result = bridge.inject_into_domain_pack_resolution(tick=0)
        assert len(result["records"]) == 1

    def test_no_matching_specs(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, target=FaultTargetKind.PROVIDER)
        result = bridge.inject_into_supervisor_tick(tick=0)
        assert len(result["records"]) == 0


# ---------------------------------------------------------------------------
# Campaign orchestration
# ---------------------------------------------------------------------------


class TestCampaignOrchestration:
    def test_run_campaign(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, repeat=5)
        result = bridge.run_fault_campaign(
            "test-campaign", ("fs-1",), tick_count=5,
        )
        assert result["session"] is not None
        assert len(result["records"]) == 5  # repeat_count=5, tick_count=5
        assert result["event"].payload["action"] == "fault_campaign_executed"

    def test_evaluate_campaign(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, repeat=3)
        result = bridge.run_fault_campaign(
            "test-campaign", ("fs-1",), tick_count=5,
        )
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].passed is True
        assert eval_result["outcome"].score == 1.0
        assert eval_result["memory"] is not None
        assert "adversarial" in eval_result["memory"].tags
        assert eval_result["memory"].title == "Adversarial campaign outcome"
        assert result["session"].name not in eval_result["memory"].title
        assert eval_result["event"] is not None

    def test_evaluate_failed_campaign(self):
        fe, es, me, bridge = _build()
        _add_spec(fe, repeat=3)
        result = bridge.run_fault_campaign(
            "fail-campaign", ("fs-1",), tick_count=5,
        )
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
            all_recovered=False,
            all_consistent=False,
        )
        assert eval_result["outcome"].passed is False
        assert eval_result["outcome"].state_consistent is False


# ---------------------------------------------------------------------------
# Recovery assessment
# ---------------------------------------------------------------------------


class TestRecoveryAssessment:
    def test_assess_and_record(self):
        fe, es, me, bridge = _build()
        _add_spec(fe)
        record = fe.inject("fs-1", tick=0)
        result = bridge.assess_and_record(
            record.record_id, recovered=True,
            recovery_method="rollback",
        )
        assert result["assessment"].recovered is True
        assert result["event"] is not None


# ---------------------------------------------------------------------------
# Preset campaigns
# ---------------------------------------------------------------------------


class TestPresetCampaigns:
    def test_provider_storm(self):
        fe, es, me, bridge = _build()
        result = bridge.run_provider_storm_campaign(tick_count=5)
        assert result["session"].name == "provider-storm"
        assert len(result["records"]) >= 1

    def test_event_flood(self):
        fe, es, me, bridge = _build()
        result = bridge.run_event_flood_campaign(tick_count=5)
        assert result["session"].name == "event-flood"

    def test_checkpoint_corruption(self):
        fe, es, me, bridge = _build()
        result = bridge.run_checkpoint_corruption_campaign()
        assert result["session"].name == "checkpoint-corruption"

    def test_communication_failure(self):
        fe, es, me, bridge = _build()
        result = bridge.run_communication_failure_campaign(tick_count=5)
        assert result["session"].name == "communication-failure"

    def test_governance_conflict(self):
        fe, es, me, bridge = _build()
        result = bridge.run_governance_conflict_campaign()
        assert result["session"].name == "governance-conflict"
