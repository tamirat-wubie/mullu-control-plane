"""Purpose: edge case tests for world-state integration bridge.
Governance scope: world-state plane edge cases and boundary conditions.
Dependencies: world-state engine, bridge, contracts.
Invariants: bridge methods handle empty inputs and boundary conditions correctly.
"""

from __future__ import annotations

from mcoi_runtime.contracts.world_state import (
    ContradictionRecord,
    ContradictionStrategy,
    DeltaKind,
    EntityRelation,
    ExpectedState,
    StateEntity,
)
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


# --- compute_snapshot_deltas edge cases ---


class TestComputeSnapshotDeltaEdgeCases:
    def test_entity_removed_delta(self) -> None:
        """Removing an entity between snapshots produces ENTITY_REMOVED delta."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        snap1 = WorldStateBridge.take_snapshot(eng)

        eng2 = _engine()
        eng2.add_entity(_entity("e-1"))
        snap2 = WorldStateBridge.take_snapshot(eng2)

        deltas = WorldStateBridge.compute_snapshot_deltas(eng, snap1, snap2)
        removed = [d for d in deltas if d.kind == DeltaKind.ENTITY_REMOVED]
        assert len(removed) == 1
        assert removed[0].target_id == "e-2"

    def test_entity_modified_delta(self) -> None:
        """Changing entity attributes between snapshots produces ENTITY_MODIFIED delta."""
        eng = _engine()
        eng.add_entity(_entity("e-1", status="running"))
        snap1 = WorldStateBridge.take_snapshot(eng)

        eng2 = _engine()
        eng2.add_entity(_entity("e-1", status="stopped"))
        snap2 = WorldStateBridge.take_snapshot(eng2)

        deltas = WorldStateBridge.compute_snapshot_deltas(eng, snap1, snap2)
        modified = [d for d in deltas if d.kind == DeltaKind.ENTITY_MODIFIED]
        assert len(modified) == 1
        assert modified[0].target_id == "e-1"

    def test_identical_snapshots_produce_no_deltas(self) -> None:
        """Comparing a snapshot to itself produces zero deltas."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        snap = WorldStateBridge.take_snapshot(eng)

        deltas = WorldStateBridge.compute_snapshot_deltas(eng, snap, snap)
        assert deltas == ()


# --- entity_confidence_envelopes edge cases ---


class TestConfidenceEnvelopeEdgeCases:
    def test_empty_entity_ids(self) -> None:
        """Empty entity_ids produces no envelopes."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        envelopes = WorldStateBridge.entity_confidence_envelopes(eng, (), "status")
        assert envelopes == ()

    def test_entity_with_contradiction_has_wider_bounds(self) -> None:
        """Contradictions widen the confidence interval."""
        eng = _engine()
        eng.add_entity(_entity("e-1", confidence=0.8))
        env_clean = WorldStateBridge.entity_confidence_envelopes(eng, ("e-1",), "status")

        eng.record_contradiction(_contradiction("ctr-1", "e-1", "status"))
        env_with_contradiction = WorldStateBridge.entity_confidence_envelopes(eng, ("e-1",), "status")

        clean_width = env_clean[0].upper_bound - env_clean[0].lower_bound
        contradiction_width = env_with_contradiction[0].upper_bound - env_with_contradiction[0].lower_bound
        assert contradiction_width >= clean_width


# --- full_health_assessment edge cases ---


class TestFullHealthAssessmentEdgeCases:
    def test_empty_engine_is_healthy(self) -> None:
        """Empty engine reports healthy with zero counts."""
        eng = _engine()
        health = WorldStateBridge.full_health_assessment(eng)
        assert health["recommendation"] == "healthy"
        assert health["violation_count"] == 0

    def test_single_violation_shows_drift(self) -> None:
        """One expectation violation triggers drift_detected."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "stopped"))

        health = WorldStateBridge.full_health_assessment(eng)
        assert health["violation_count"] >= 1
        assert health["recommendation"] in ("drift_detected", "investigate")

    def test_conflicts_pending_recommendation(self) -> None:
        """Unresolved contradictions trigger conflicts_pending."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.record_contradiction(_contradiction("ctr-1", "e-1", "status"))

        health = WorldStateBridge.full_health_assessment(eng)
        assert len(health["conflict_sets"]) >= 1
        assert health["recommendation"] in ("conflicts_pending", "investigate")


# --- detect_violations edge cases ---


class TestDetectViolationsEdgeCases:
    def test_no_expectations_means_no_violations(self) -> None:
        """With no expected states, violations are always empty."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        violations = WorldStateBridge.detect_violations(eng)
        assert violations == ()

    def test_matching_expectation_is_not_violation(self) -> None:
        """A matching expected state is not a violation."""
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-match", "e-1", "running"))

        violations = WorldStateBridge.detect_violations(eng)
        assert violations == ()

    def test_missing_entity_is_violation(self) -> None:
        """An expectation for a non-existent entity is a violation."""
        eng = _engine()
        eng.add_expected_state(_expected_state("exp-missing", "e-nonexistent", "running"))

        violations = WorldStateBridge.detect_violations(eng)
        assert len(violations) >= 1
