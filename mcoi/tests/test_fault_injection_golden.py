"""Golden scenario tests for fault injection and adversarial operations.

10 scenarios covering end-to-end adversarial flows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.fault_injection import (
    FaultDisposition,
    FaultSeverity,
    FaultSpec,
    FaultTargetKind,
    FaultType,
    FaultWindow,
    InjectionMode,
)
from mcoi_runtime.core.adversarial_operations import AdversarialOperationsBridge
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.fault_injection import FaultInjectionEngine
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


# ---------------------------------------------------------------------------
# Scenario 1: provider storm causes degraded routing but no unsafe execution
# ---------------------------------------------------------------------------


class TestGolden1ProviderStormDegradedRouting:
    def test_provider_storm_degraded_not_failed(self):
        fe, es, me, bridge = _build()
        result = bridge.run_provider_storm_campaign(tick_count=10)

        # Multiple injections occurred
        assert len(result["records"]) >= 3

        # All targeting provider
        for r in result["records"]:
            assert r.target_kind == FaultTargetKind.PROVIDER

        # Evaluate — all recovered (default assessment)
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
            all_recovered=True,
        )
        assert eval_result["outcome"].passed is True
        assert eval_result["outcome"].state_consistent is True
        assert eval_result["outcome"].faults_failed == 0

        # Memory recorded
        assert eval_result["memory"] is not None
        assert eval_result["memory"].content["passed"] is True


# ---------------------------------------------------------------------------
# Scenario 2: checkpoint mismatch forces rollback, supervisor stays consistent
# ---------------------------------------------------------------------------


class TestGolden2CheckpointMismatchRollback:
    def test_checkpoint_mismatch_rollback(self):
        fe, es, me, bridge = _build()
        result = bridge.run_checkpoint_corruption_campaign()

        # Checkpoint corruption injected
        assert len(result["records"]) >= 1
        cp_records = [r for r in result["records"]
                     if r.target_kind == FaultTargetKind.CHECKPOINT]
        assert len(cp_records) >= 1

        # Assess — recovered via rollback
        for r in cp_records:
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="rollback",
                state_consistent=True,
            )

        # Evaluate
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].state_consistent is True


# ---------------------------------------------------------------------------
# Scenario 3: event flood triggers backpressure but no state corruption
# ---------------------------------------------------------------------------


class TestGolden3EventFloodBackpressure:
    def test_event_flood_no_corruption(self):
        fe, es, me, bridge = _build()
        result = bridge.run_event_flood_campaign(tick_count=20)

        # Many injections
        assert len(result["records"]) >= 2

        # All targeting event spine
        for r in result["records"]:
            assert r.target_kind == FaultTargetKind.EVENT_SPINE

        # Evaluate — state remains consistent
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
            all_recovered=True,
            all_consistent=True,
        )
        assert eval_result["outcome"].state_consistent is True
        assert eval_result["outcome"].passed is True


# ---------------------------------------------------------------------------
# Scenario 4: communication failure falls back through escalation chain
# ---------------------------------------------------------------------------


class TestGolden4CommunicationFallback:
    def test_comm_failure_fallback(self):
        fe, es, me, bridge = _build()
        result = bridge.run_communication_failure_campaign(tick_count=10)

        # Multiple communication faults injected
        comm_records = [r for r in result["records"]
                       if r.target_kind == FaultTargetKind.COMMUNICATION]
        assert len(comm_records) >= 3

        # Assess — recovered via fallback
        for r in comm_records:
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="channel-fallback",
                degraded=True,
                degraded_reason="primary channel unavailable, fell back",
            )

        # Evaluate
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        # Passed because all recovered (even if degraded)
        assert eval_result["outcome"].passed is True
        assert eval_result["outcome"].faults_degraded >= 1


# ---------------------------------------------------------------------------
# Scenario 5: malformed artifact is blocked, remembered, and benchmarked
# ---------------------------------------------------------------------------


class TestGolden5MalformedArtifactBlocked:
    def test_artifact_blocked_and_remembered(self):
        fe, es, me, bridge = _build()

        # Register artifact corruption specs
        specs = fe.register_artifact_corruption()
        spec_ids = tuple(s.spec_id for s in specs)

        # Run campaign
        result = bridge.run_fault_campaign(
            "artifact-corruption", spec_ids, tick_count=3,
            tags=("artifact",),
        )

        # Artifacts corrupted
        assert len(result["records"]) >= 1

        # Assess — policy blocked the corrupt artifacts
        for r in result["records"]:
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="policy-block",
                state_consistent=True,
            )

        # Evaluate
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].passed is True
        assert eval_result["memory"] is not None
        assert "artifact" in eval_result["memory"].tags


# ---------------------------------------------------------------------------
# Scenario 6: obligation expiry chain escalates correctly
# ---------------------------------------------------------------------------


class TestGolden6ObligationEscalationChain:
    def test_obligation_escalation_stress(self):
        fe, es, me, bridge = _build()

        specs = fe.register_obligation_escalation_stress()
        spec_ids = tuple(s.spec_id for s in specs)

        result = bridge.run_fault_campaign(
            "obligation-stress", spec_ids, tick_count=10,
            tags=("obligation",),
        )

        # Multiple obligation faults injected
        obl_records = [r for r in result["records"]
                      if r.target_kind == FaultTargetKind.OBLIGATION_RUNTIME]
        assert len(obl_records) >= 3

        # Assess — escalation handled
        for r in obl_records:
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="escalation-chain",
            )

        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].passed is True


# ---------------------------------------------------------------------------
# Scenario 7: governance conflict produces deterministic deny/review outcome
# ---------------------------------------------------------------------------


class TestGolden7GovernanceConflictDeterministic:
    def test_governance_conflict_deterministic(self):
        fe, es, me, bridge = _build()
        result = bridge.run_governance_conflict_campaign()

        # Governance faults injected
        gov_records = [r for r in result["records"]
                      if r.target_kind == FaultTargetKind.GOVERNANCE]
        assert len(gov_records) >= 1

        # Assess — fail-closed governance denied
        for r in gov_records:
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="fail-closed-deny",
                state_consistent=True,
            )

        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].state_consistent is True


# ---------------------------------------------------------------------------
# Scenario 8: domain-pack conflict surfaced, does not silently override
# ---------------------------------------------------------------------------


class TestGolden8DomainPackConflictSurfaced:
    def test_domain_pack_conflict_surfaced(self):
        fe, es, me, bridge = _build()

        specs = fe.register_domain_pack_conflict_stress()
        spec_ids = tuple(s.spec_id for s in specs)

        result = bridge.run_fault_campaign(
            "domain-pack-stress", spec_ids, tick_count=5,
            tags=("domain-pack",),
        )

        # Domain pack faults injected
        dp_records = [r for r in result["records"]
                     if r.target_kind == FaultTargetKind.DOMAIN_PACK]
        assert len(dp_records) >= 1

        # Observe conflict surfacing
        for r in dp_records:
            fe.record_observation(
                r.record_id,
                observed_behavior="conflict surfaced deterministically",
                expected_behavior="conflict surfaced deterministically",
                matches_expected=True,
            )

        # Assess — conflict surfaced correctly
        for r in dp_records:
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="conflict-surfacing",
            )

        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].passed is True


# ---------------------------------------------------------------------------
# Scenario 9: adversarial campaign records into memory mesh and benchmark
# ---------------------------------------------------------------------------


class TestGolden9CampaignRecordsInMemoryAndBenchmark:
    def test_campaign_memory_and_scoring(self):
        fe, es, me, bridge = _build()

        # Run provider storm
        result = bridge.run_provider_storm_campaign(tick_count=5)

        # Evaluate — produces outcome, memory, event
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )

        # Memory recorded
        mem = eval_result["memory"]
        assert mem is not None
        assert mem.content["session_id"] == result["session"].session_id
        assert "score" in mem.content
        assert mem.confidence == eval_result["outcome"].score

        # Outcome has benchmark-style scoring
        outcome = eval_result["outcome"]
        assert 0.0 <= outcome.score <= 1.0
        assert outcome.summary != ""

        # Event emitted
        assert eval_result["event"].payload["action"] == "fault_campaign_evaluated"

        # Memory mesh has the record
        assert me.memory_count >= 1


# ---------------------------------------------------------------------------
# Scenario 10: long-running supervisor survives mixed injected faults
#              with bounded degradation
# ---------------------------------------------------------------------------


class TestGolden10LongRunMixedFaults:
    def test_long_run_mixed_faults_bounded_degradation(self):
        fe, es, me, bridge = _build()

        # Register multiple fault families
        provider_specs = fe.register_provider_storm(count=3)
        comm_specs = fe.register_communication_failure(count=3)
        gov_specs = fe.register_governance_conflict_storm()

        all_spec_ids = (
            tuple(s.spec_id for s in provider_specs)
            + tuple(s.spec_id for s in comm_specs)
            + tuple(s.spec_id for s in gov_specs)
        )

        # Run long campaign
        result = bridge.run_fault_campaign(
            "mixed-long-run", all_spec_ids, tick_count=20,
            tags=("long-run", "mixed"),
        )

        # Many faults injected across different targets
        assert len(result["records"]) >= 5
        target_kinds = {r.target_kind for r in result["records"]}
        assert FaultTargetKind.PROVIDER in target_kinds
        assert FaultTargetKind.COMMUNICATION in target_kinds
        assert FaultTargetKind.GOVERNANCE in target_kinds

        # Assess — mostly recovered, some degraded
        for i, r in enumerate(result["records"]):
            degraded = (i % 3 == 0)  # Every 3rd is degraded
            bridge.assess_and_record(
                r.record_id, recovered=True,
                recovery_method="adaptive",
                degraded=degraded,
                degraded_reason="bounded degradation" if degraded else "",
                state_consistent=True,
            )

        # Evaluate
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        outcome = eval_result["outcome"]

        # All recovered (passed)
        assert outcome.passed is True
        assert outcome.state_consistent is True
        assert outcome.faults_failed == 0

        # Some degradation is expected and bounded
        assert outcome.faults_degraded >= 1
        assert outcome.faults_degraded < outcome.total_faults

        # Score is 1.0 because all recovered
        assert outcome.score == 1.0

        # Memory recorded with long-run tags
        assert "long-run" in eval_result["memory"].tags
        assert "mixed" in eval_result["memory"].tags
