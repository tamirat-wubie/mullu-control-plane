"""Purpose: verify world-state integration bridge and dashboard surfacing.
Governance scope: world-state plane integration tests only.
Dependencies: world-state engine, world-state bridge, dashboard engine, contracts.
Invariants: bridge methods are stateless; dashboard snapshot includes world-state.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.dashboard import WorldStateSummary
from mcoi_runtime.contracts.world_state import (
    ConflictSet,
    ContradictionRecord,
    ContradictionStrategy,
    DeltaKind,
    DerivedFact,
    EntityRelation,
    ExpectedState,
    ResolutionRecord,
    StateConfidenceEnvelope,
    StateEntity,
    WorldStateDelta,
    WorldStateSnapshot,
)
from mcoi_runtime.core.dashboard import DashboardEngine
from mcoi_runtime.core.world_state import WorldStateEngine
from mcoi_runtime.core.world_state_integration import WorldStateBridge


_CLOCK = "2026-03-20T00:00:00+00:00"
_CLOCK_FN = lambda: _CLOCK  # noqa: E731


def _engine() -> WorldStateEngine:
    return WorldStateEngine(clock=_CLOCK_FN)


def _entity(eid: str = "e-1", confidence: float = 0.8, **extra: object) -> StateEntity:
    return StateEntity(
        entity_id=eid, entity_type="service",
        attributes={"status": "running", **extra},
        evidence_ids=("ev-1",), confidence=confidence,
        created_at=_CLOCK,
    )


def _relation(rid: str = "r-1", src: str = "e-1", tgt: str = "e-2") -> EntityRelation:
    return EntityRelation(
        relation_id=rid, source_entity_id=src, target_entity_id=tgt,
        relation_type="depends_on", evidence_ids=("ev-1",), confidence=0.9,
    )


def _contradiction(
    cid: str = "c-1", eid: str = "e-1", attr: str = "status",
    strategy: ContradictionStrategy = ContradictionStrategy.ESCALATE,
) -> ContradictionRecord:
    return ContradictionRecord(
        contradiction_id=cid, entity_id=eid, attribute=attr,
        conflicting_evidence_ids=("ev-1", "ev-2"),
        strategy=strategy, resolved=False,
    )


def _expected_state(
    xid: str = "exp-1", eid: str = "e-1", val: object = "running",
) -> ExpectedState:
    return ExpectedState(
        expectation_id=xid, entity_id=eid, attribute="status",
        expected_value=val, basis="workflow", confidence=0.9,
        expected_by=_CLOCK, created_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# WorldStateBridge.take_snapshot
# ---------------------------------------------------------------------------

class TestTakeSnapshot:
    def test_empty(self) -> None:
        eng = _engine()
        snap = WorldStateBridge.take_snapshot(eng)
        assert isinstance(snap, WorldStateSnapshot)
        assert snap.entity_count == 0

    def test_with_entities(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        snap = WorldStateBridge.take_snapshot(eng, "s-1")
        assert snap.snapshot_id == "s-1"
        assert snap.entity_count == 2


# ---------------------------------------------------------------------------
# WorldStateBridge.check_all_expectations / detect_violations
# ---------------------------------------------------------------------------

class TestExpectationChecks:
    def test_all_match(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "running"))
        results = WorldStateBridge.check_all_expectations(eng)
        assert len(results) == 1
        assert results[0][2] is True  # matches

    def test_detect_violations_empty_when_all_match(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "running"))
        violations = WorldStateBridge.detect_violations(eng)
        assert violations == ()

    def test_detect_violations_found(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "stopped"))
        violations = WorldStateBridge.detect_violations(eng)
        assert len(violations) == 1
        assert violations[0][0].expectation_id == "exp-1"

    def test_multiple_expectations(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "running"))   # match
        eng.add_expected_state(_expected_state("exp-2", "e-2", "stopped"))   # violation
        results = WorldStateBridge.check_all_expectations(eng)
        assert len(results) == 2
        violations = WorldStateBridge.detect_violations(eng)
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# WorldStateBridge.group_all_conflicts
# ---------------------------------------------------------------------------

class TestGroupAllConflicts:
    def test_no_conflicts(self) -> None:
        eng = _engine()
        assert WorldStateBridge.group_all_conflicts(eng) == ()

    def test_groups_returned(self) -> None:
        eng = _engine()
        eng.record_contradiction(_contradiction("c-1", "e-1"))
        eng.record_contradiction(_contradiction("c-2", "e-2"))
        sets = WorldStateBridge.group_all_conflicts(eng)
        assert len(sets) == 2


# ---------------------------------------------------------------------------
# WorldStateBridge.compute_snapshot_deltas
# ---------------------------------------------------------------------------

class TestComputeSnapshotDeltas:
    def test_no_change(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        snap = WorldStateBridge.take_snapshot(eng, "s-1")
        deltas = WorldStateBridge.compute_snapshot_deltas(eng, snap, snap)
        assert deltas == ()

    def test_entity_added_delta(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        snap1 = WorldStateBridge.take_snapshot(eng, "s-1")
        eng.add_entity(_entity("e-2"))
        snap2 = WorldStateBridge.take_snapshot(eng, "s-2")
        deltas = WorldStateBridge.compute_snapshot_deltas(eng, snap1, snap2)
        assert any(d.kind == DeltaKind.ENTITY_ADDED for d in deltas)


# ---------------------------------------------------------------------------
# WorldStateBridge.entity_confidence_envelopes
# ---------------------------------------------------------------------------

class TestEntityConfidenceEnvelopes:
    def test_single_entity(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1", confidence=0.9))
        envs = WorldStateBridge.entity_confidence_envelopes(eng, ("e-1",), "status")
        assert len(envs) == 1
        assert isinstance(envs[0], StateConfidenceEnvelope)

    def test_multiple_entities(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        envs = WorldStateBridge.entity_confidence_envelopes(eng, ("e-1", "e-2"), "status")
        assert len(envs) == 2


# ---------------------------------------------------------------------------
# WorldStateBridge.full_health_assessment
# ---------------------------------------------------------------------------

class TestFullHealthAssessment:
    def test_healthy(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "running"))
        result = WorldStateBridge.full_health_assessment(eng)
        assert result["recommendation"] == "healthy"
        assert result["violation_count"] == 0

    def test_drift_detected(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "stopped"))
        result = WorldStateBridge.full_health_assessment(eng)
        assert result["recommendation"] == "drift_detected"
        assert result["violation_count"] == 1

    def test_conflicts_pending(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.record_contradiction(_contradiction("c-1", "e-1"))
        result = WorldStateBridge.full_health_assessment(eng)
        assert result["recommendation"] == "conflicts_pending"

    def test_investigate(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "stopped"))
        eng.record_contradiction(_contradiction("c-1", "e-1"))
        result = WorldStateBridge.full_health_assessment(eng)
        assert result["recommendation"] == "investigate"


# ---------------------------------------------------------------------------
# DashboardEngine.build_world_state_summary
# ---------------------------------------------------------------------------

class TestBuildWorldStateSummary:
    def _dashboard(self) -> DashboardEngine:
        return DashboardEngine(clock=_CLOCK_FN)

    def _snap(self, eng: WorldStateEngine | None = None) -> WorldStateSnapshot:
        if eng is None:
            eng = _engine()
            eng.add_entity(_entity("e-1"))
            eng.add_entity(_entity("e-2"))
        return eng.assemble_snapshot("snap-1")

    def test_basic_summary(self) -> None:
        dash = self._dashboard()
        snap = self._snap()
        summary = dash.build_world_state_summary(snap)
        assert isinstance(summary, WorldStateSummary)
        assert summary.entity_count == 2
        assert summary.overall_confidence == snap.overall_confidence

    def test_with_violations(self) -> None:
        dash = self._dashboard()
        snap = self._snap()
        summary = dash.build_world_state_summary(
            snap, violation_count=3, recommendation="drift_detected",
        )
        assert summary.violation_count == 3
        assert summary.recommendation == "drift_detected"

    def test_with_conflict_sets(self) -> None:
        dash = self._dashboard()
        snap = self._snap()
        summary = dash.build_world_state_summary(
            snap, conflict_set_count=2, recommendation="conflicts_pending",
        )
        assert summary.conflict_set_count == 2

    def test_empty_snapshot(self) -> None:
        dash = self._dashboard()
        eng = _engine()
        snap = eng.assemble_snapshot("snap-empty")
        summary = dash.build_world_state_summary(snap)
        assert summary.entity_count == 0
        assert "empty" in summary.confidence_display

    def test_summary_id_deterministic(self) -> None:
        dash = self._dashboard()
        snap = self._snap()
        s1 = dash.build_world_state_summary(snap)
        s2 = dash.build_world_state_summary(snap)
        assert s1.summary_id == s2.summary_id


# ---------------------------------------------------------------------------
# DashboardSnapshot with world_state
# ---------------------------------------------------------------------------

class TestDashboardSnapshotWithWorldState:
    def test_snapshot_without_world_state(self) -> None:
        dash = DashboardEngine(clock=_CLOCK_FN)
        snap = dash.snapshot(
            outcomes=(), adjustments=(), routing_outcomes=(),
            preferences={}, provider_ids=(), health_scores={},
            learned_adjustments={}, total_decisions=0,
            total_routing_decisions=0,
        )
        assert snap.world_state is None

    def test_snapshot_with_world_state(self) -> None:
        dash = DashboardEngine(clock=_CLOCK_FN)
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        ws_snap = eng.assemble_snapshot("ws-1")
        ws_summary = dash.build_world_state_summary(ws_snap)

        snap = dash.snapshot(
            outcomes=(), adjustments=(), routing_outcomes=(),
            preferences={}, provider_ids=(), health_scores={},
            learned_adjustments={}, total_decisions=0,
            total_routing_decisions=0,
            world_state_summary=ws_summary,
        )
        assert snap.world_state is not None
        assert snap.world_state.entity_count == 1


# ---------------------------------------------------------------------------
# Golden Scenario: full cross-plane lifecycle via bridge
# ---------------------------------------------------------------------------

class TestGoldenCrossPlane:
    def test_full_lifecycle(self) -> None:
        eng = _engine()
        dash = DashboardEngine(clock=_CLOCK_FN)

        # 1. Populate world state
        eng.add_entity(_entity("api", confidence=0.9))
        eng.add_entity(_entity("db", confidence=0.6))
        eng.add_relation(_relation("r-1", "api", "db"))

        # 2. Add expectations
        eng.add_expected_state(_expected_state("exp-api", "api", "running"))
        eng.add_expected_state(_expected_state("exp-db", "db", "stopped"))  # will violate

        # 3. Add contradiction
        eng.record_contradiction(_contradiction("c-db", "db", "status"))

        # 4. Bridge: snapshot
        snap1 = WorldStateBridge.take_snapshot(eng, "s-1")
        assert snap1.entity_count == 2

        # 5. Bridge: check violations
        violations = WorldStateBridge.detect_violations(eng)
        assert len(violations) == 1
        assert violations[0][0].entity_id == "db"

        # 6. Bridge: group conflicts
        conflict_sets = WorldStateBridge.group_all_conflicts(eng)
        assert len(conflict_sets) == 1

        # 7. Bridge: full health assessment
        health = WorldStateBridge.full_health_assessment(eng)
        assert health["recommendation"] == "investigate"

        # 8. Bridge: confidence envelopes
        envs = WorldStateBridge.entity_confidence_envelopes(eng, ("api", "db"), "status")
        assert len(envs) == 2

        # 9. Dashboard surfacing
        ws_summary = dash.build_world_state_summary(
            health["snapshot"],
            conflict_set_count=len(conflict_sets),
            violation_count=health["violation_count"],
            recommendation=health["recommendation"],
        )
        assert ws_summary.violation_count == 1
        assert ws_summary.conflict_set_count == 1
        assert ws_summary.recommendation == "investigate"

        # 10. Add a new entity, take second snapshot, compute deltas
        eng.add_entity(_entity("cache", confidence=0.95))
        snap2 = WorldStateBridge.take_snapshot(eng, "s-2")
        deltas = WorldStateBridge.compute_snapshot_deltas(eng, snap1, snap2)
        assert any(d.kind == DeltaKind.ENTITY_ADDED and d.target_id == "cache" for d in deltas)

        # 11. Full dashboard snapshot with world-state
        dash_snap = dash.snapshot(
            outcomes=(), adjustments=(), routing_outcomes=(),
            preferences={}, provider_ids=(), health_scores={},
            learned_adjustments={}, total_decisions=0,
            total_routing_decisions=0,
            world_state_summary=ws_summary,
        )
        assert dash_snap.world_state is not None
        assert dash_snap.world_state.recommendation == "investigate"
