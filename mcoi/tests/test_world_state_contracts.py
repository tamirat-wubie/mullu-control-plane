"""Tests for mcoi_runtime.contracts.world_state — Phase 31 world-state contract types.

Covers: DerivedFact, ExpectedState, ConflictSet, ResolutionRecord,
        StateConfidenceEnvelope, WorldStateDelta, WorldStateSnapshot, DeltaKind.
"""

from __future__ import annotations

import pytest

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

_TS = "2026-03-20T00:00:00Z"


# --- helpers ----------------------------------------------------------------


def _entity(eid: str = "e-1") -> StateEntity:
    return StateEntity(
        entity_id=eid,
        entity_type="file",
        attributes={"path": "/tmp/test"},
        evidence_ids=("ev-1",),
        confidence=0.9,
        created_at=_TS,
    )


def _relation() -> EntityRelation:
    return EntityRelation(
        relation_id="r-1",
        source_entity_id="e-1",
        target_entity_id="e-2",
        relation_type="depends_on",
        evidence_ids=("ev-1",),
        confidence=0.8,
    )


def _contradiction(cid: str = "c-1") -> ContradictionRecord:
    return ContradictionRecord(
        contradiction_id=cid,
        entity_id="e-1",
        attribute="status",
        conflicting_evidence_ids=("ev-1", "ev-2"),
        strategy=ContradictionStrategy.ESCALATE,
        resolved=False,
    )


# ---------------------------------------------------------------------------
# DeltaKind
# ---------------------------------------------------------------------------


class TestDeltaKind:
    def test_all_members(self) -> None:
        expected = {
            "ENTITY_ADDED", "ENTITY_REMOVED", "ENTITY_MODIFIED",
            "RELATION_ADDED", "RELATION_REMOVED", "FACT_DERIVED",
            "EXPECTATION_MET", "EXPECTATION_VIOLATED",
        }
        assert {m.name for m in DeltaKind} == expected

    def test_values_are_strings(self) -> None:
        for m in DeltaKind:
            assert isinstance(m.value, str)


# ---------------------------------------------------------------------------
# DerivedFact
# ---------------------------------------------------------------------------


class TestDerivedFact:
    def test_valid_construction(self) -> None:
        f = DerivedFact(
            fact_id="df-1",
            entity_id="e-1",
            attribute="health",
            derived_value="healthy",
            source_entity_ids=("e-2", "e-3"),
            derivation_rule="majority_vote",
            confidence=0.85,
            derived_at=_TS,
        )
        assert f.fact_id == "df-1"
        assert f.confidence == 0.85

    def test_empty_fact_id_raises(self) -> None:
        with pytest.raises(ValueError, match="fact_id"):
            DerivedFact(
                fact_id="",
                entity_id="e-1",
                attribute="health",
                derived_value="healthy",
                source_entity_ids=("e-2",),
                derivation_rule="rule",
                confidence=0.5,
                derived_at=_TS,
            )

    def test_empty_source_entity_ids_raises(self) -> None:
        with pytest.raises(ValueError, match="source_entity_ids"):
            DerivedFact(
                fact_id="df-1",
                entity_id="e-1",
                attribute="health",
                derived_value="healthy",
                source_entity_ids=(),
                derivation_rule="rule",
                confidence=0.5,
                derived_at=_TS,
            )

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            DerivedFact(
                fact_id="df-1",
                entity_id="e-1",
                attribute="health",
                derived_value="healthy",
                source_entity_ids=("e-2",),
                derivation_rule="rule",
                confidence=1.5,
                derived_at=_TS,
            )

    def test_frozen(self) -> None:
        f = DerivedFact(
            fact_id="df-1",
            entity_id="e-1",
            attribute="health",
            derived_value="healthy",
            source_entity_ids=("e-2",),
            derivation_rule="rule",
            confidence=0.5,
            derived_at=_TS,
        )
        with pytest.raises(AttributeError):
            f.confidence = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ExpectedState
# ---------------------------------------------------------------------------


class TestExpectedState:
    def test_valid_construction(self) -> None:
        e = ExpectedState(
            expectation_id="exp-1",
            entity_id="e-1",
            attribute="status",
            expected_value="completed",
            basis="workflow-123 completion",
            confidence=0.7,
            expected_by=_TS,
            created_at=_TS,
        )
        assert e.expectation_id == "exp-1"
        assert e.expected_value == "completed"

    def test_empty_basis_raises(self) -> None:
        with pytest.raises(ValueError, match="basis"):
            ExpectedState(
                expectation_id="exp-1",
                entity_id="e-1",
                attribute="status",
                expected_value="completed",
                basis="",
                confidence=0.5,
                expected_by=_TS,
                created_at=_TS,
            )

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            ExpectedState(
                expectation_id="exp-1",
                entity_id="e-1",
                attribute="status",
                expected_value="completed",
                basis="wf-1",
                confidence=-0.1,
                expected_by=_TS,
                created_at=_TS,
            )

    def test_frozen(self) -> None:
        e = ExpectedState(
            expectation_id="exp-1",
            entity_id="e-1",
            attribute="status",
            expected_value="completed",
            basis="wf-1",
            confidence=0.5,
            expected_by=_TS,
            created_at=_TS,
        )
        with pytest.raises(AttributeError):
            e.confidence = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConflictSet
# ---------------------------------------------------------------------------


class TestConflictSet:
    def test_valid_construction(self) -> None:
        cs = ConflictSet(
            conflict_set_id="cs-1",
            entity_id="e-1",
            contradictions=(_contradiction(),),
            overall_strategy=ContradictionStrategy.ESCALATE,
            created_at=_TS,
        )
        assert cs.conflict_set_id == "cs-1"
        assert len(cs.contradictions) == 1

    def test_empty_contradictions_raises(self) -> None:
        with pytest.raises(ValueError, match="contradictions"):
            ConflictSet(
                conflict_set_id="cs-1",
                entity_id="e-1",
                contradictions=(),
                overall_strategy=ContradictionStrategy.ESCALATE,
                created_at=_TS,
            )

    def test_invalid_contradiction_type_raises(self) -> None:
        with pytest.raises(ValueError, match="contradiction"):
            ConflictSet(
                conflict_set_id="cs-1",
                entity_id="e-1",
                contradictions=("not-a-contradiction",),  # type: ignore[arg-type]
                overall_strategy=ContradictionStrategy.ESCALATE,
                created_at=_TS,
            )

    def test_invalid_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="overall_strategy"):
            ConflictSet(
                conflict_set_id="cs-1",
                entity_id="e-1",
                contradictions=(_contradiction(),),
                overall_strategy="bad",  # type: ignore[arg-type]
                created_at=_TS,
            )


# ---------------------------------------------------------------------------
# ResolutionRecord
# ---------------------------------------------------------------------------


class TestResolutionRecord:
    def test_valid_construction(self) -> None:
        r = ResolutionRecord(
            resolution_id="res-1",
            contradiction_id="c-1",
            resolved_value="active",
            strategy_used=ContradictionStrategy.PREFER_LATEST,
            resolver_id="operator-1",
            confidence=0.8,
            resolved_at=_TS,
        )
        assert r.resolution_id == "res-1"
        assert r.strategy_used == ContradictionStrategy.PREFER_LATEST

    def test_empty_resolver_id_raises(self) -> None:
        with pytest.raises(ValueError, match="resolver_id"):
            ResolutionRecord(
                resolution_id="res-1",
                contradiction_id="c-1",
                resolved_value="active",
                strategy_used=ContradictionStrategy.MANUAL,
                resolver_id="",
                confidence=0.5,
                resolved_at=_TS,
            )

    def test_invalid_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_used"):
            ResolutionRecord(
                resolution_id="res-1",
                contradiction_id="c-1",
                resolved_value="active",
                strategy_used="bad",  # type: ignore[arg-type]
                resolver_id="operator-1",
                confidence=0.5,
                resolved_at=_TS,
            )

    def test_frozen(self) -> None:
        r = ResolutionRecord(
            resolution_id="res-1",
            contradiction_id="c-1",
            resolved_value="active",
            strategy_used=ContradictionStrategy.MANUAL,
            resolver_id="op-1",
            confidence=0.5,
            resolved_at=_TS,
        )
        with pytest.raises(AttributeError):
            r.confidence = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StateConfidenceEnvelope
# ---------------------------------------------------------------------------


class TestStateConfidenceEnvelope:
    def test_valid_construction(self) -> None:
        e = StateConfidenceEnvelope(
            envelope_id="sce-1",
            entity_id="e-1",
            attribute="status",
            point_estimate=0.8,
            lower_bound=0.6,
            upper_bound=0.95,
            evidence_count=5,
            assessed_at=_TS,
        )
        assert e.point_estimate == 0.8

    def test_lower_exceeds_point_raises(self) -> None:
        with pytest.raises(ValueError, match="lower_bound.*point_estimate"):
            StateConfidenceEnvelope(
                envelope_id="sce-1",
                entity_id="e-1",
                attribute="status",
                point_estimate=0.5,
                lower_bound=0.6,
                upper_bound=0.9,
                evidence_count=3,
                assessed_at=_TS,
            )

    def test_point_exceeds_upper_raises(self) -> None:
        with pytest.raises(ValueError, match="point_estimate.*upper_bound"):
            StateConfidenceEnvelope(
                envelope_id="sce-1",
                entity_id="e-1",
                attribute="status",
                point_estimate=0.95,
                lower_bound=0.5,
                upper_bound=0.9,
                evidence_count=3,
                assessed_at=_TS,
            )

    def test_boundary_equality_allowed(self) -> None:
        e = StateConfidenceEnvelope(
            envelope_id="sce-1",
            entity_id="e-1",
            attribute="status",
            point_estimate=0.5,
            lower_bound=0.5,
            upper_bound=0.5,
            evidence_count=1,
            assessed_at=_TS,
        )
        assert e.lower_bound == e.point_estimate == e.upper_bound

    def test_negative_evidence_count_raises(self) -> None:
        with pytest.raises(ValueError, match="evidence_count"):
            StateConfidenceEnvelope(
                envelope_id="sce-1",
                entity_id="e-1",
                attribute="status",
                point_estimate=0.5,
                lower_bound=0.3,
                upper_bound=0.7,
                evidence_count=-1,
                assessed_at=_TS,
            )

    def test_frozen(self) -> None:
        e = StateConfidenceEnvelope(
            envelope_id="sce-1",
            entity_id="e-1",
            attribute="status",
            point_estimate=0.5,
            lower_bound=0.3,
            upper_bound=0.7,
            evidence_count=3,
            assessed_at=_TS,
        )
        with pytest.raises(AttributeError):
            e.point_estimate = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WorldStateDelta
# ---------------------------------------------------------------------------


class TestWorldStateDelta:
    def test_valid_construction(self) -> None:
        d = WorldStateDelta(
            delta_id="wsd-1",
            kind=DeltaKind.ENTITY_ADDED,
            target_id="e-1",
            description="Entity e-1 added",
            computed_at=_TS,
        )
        assert d.kind == DeltaKind.ENTITY_ADDED

    def test_empty_target_id_raises(self) -> None:
        with pytest.raises(ValueError, match="target_id"):
            WorldStateDelta(
                delta_id="wsd-1",
                kind=DeltaKind.ENTITY_ADDED,
                target_id="",
                description="desc",
                computed_at=_TS,
            )

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            WorldStateDelta(
                delta_id="wsd-1",
                kind="bad",  # type: ignore[arg-type]
                target_id="e-1",
                description="desc",
                computed_at=_TS,
            )

    def test_with_previous_and_new_values(self) -> None:
        d = WorldStateDelta(
            delta_id="wsd-2",
            kind=DeltaKind.ENTITY_MODIFIED,
            target_id="e-1",
            description="status changed",
            previous_value="active",
            new_value="completed",
            computed_at=_TS,
        )
        assert d.previous_value == "active"
        assert d.new_value == "completed"


# ---------------------------------------------------------------------------
# WorldStateSnapshot
# ---------------------------------------------------------------------------


class TestWorldStateSnapshot:
    def test_valid_minimal_snapshot(self) -> None:
        s = WorldStateSnapshot(
            snapshot_id="wss-1",
            entities=(_entity(),),
            relations=(),
            derived_facts=(),
            unresolved_contradictions=(),
            expected_states=(),
            state_hash="abc123",
            entity_count=1,
            relation_count=0,
            overall_confidence=0.9,
            captured_at=_TS,
        )
        assert s.entity_count == 1
        assert s.overall_confidence == 0.9

    def test_empty_snapshot_id_raises(self) -> None:
        with pytest.raises(ValueError, match="snapshot_id"):
            WorldStateSnapshot(
                snapshot_id="",
                entities=(),
                relations=(),
                derived_facts=(),
                unresolved_contradictions=(),
                expected_states=(),
                state_hash="abc",
                entity_count=0,
                relation_count=0,
                overall_confidence=0.5,
                captured_at=_TS,
            )

    def test_invalid_entity_type_raises(self) -> None:
        with pytest.raises(ValueError, match="entity"):
            WorldStateSnapshot(
                snapshot_id="wss-1",
                entities=("not-an-entity",),  # type: ignore[arg-type]
                relations=(),
                derived_facts=(),
                unresolved_contradictions=(),
                expected_states=(),
                state_hash="abc",
                entity_count=0,
                relation_count=0,
                overall_confidence=0.5,
                captured_at=_TS,
            )

    def test_overall_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="overall_confidence"):
            WorldStateSnapshot(
                snapshot_id="wss-1",
                entities=(),
                relations=(),
                derived_facts=(),
                unresolved_contradictions=(),
                expected_states=(),
                state_hash="abc",
                entity_count=0,
                relation_count=0,
                overall_confidence=1.5,
                captured_at=_TS,
            )

    def test_frozen(self) -> None:
        s = WorldStateSnapshot(
            snapshot_id="wss-1",
            entities=(),
            relations=(),
            derived_facts=(),
            unresolved_contradictions=(),
            expected_states=(),
            state_hash="abc",
            entity_count=0,
            relation_count=0,
            overall_confidence=0.5,
            captured_at=_TS,
        )
        with pytest.raises(AttributeError):
            s.overall_confidence = 0.9  # type: ignore[misc]

    def test_full_snapshot_with_all_fields(self) -> None:
        fact = DerivedFact(
            fact_id="df-1",
            entity_id="e-1",
            attribute="derived_status",
            derived_value="healthy",
            source_entity_ids=("e-2",),
            derivation_rule="inference",
            confidence=0.8,
            derived_at=_TS,
        )
        expected = ExpectedState(
            expectation_id="exp-1",
            entity_id="e-1",
            attribute="status",
            expected_value="completed",
            basis="wf-1",
            confidence=0.7,
            expected_by=_TS,
            created_at=_TS,
        )
        s = WorldStateSnapshot(
            snapshot_id="wss-full",
            entities=(_entity("e-1"), _entity("e-2")),
            relations=(_relation(),),
            derived_facts=(fact,),
            unresolved_contradictions=(_contradiction(),),
            expected_states=(expected,),
            state_hash="hash123",
            entity_count=2,
            relation_count=1,
            overall_confidence=0.75,
            captured_at=_TS,
        )
        assert len(s.entities) == 2
        assert len(s.derived_facts) == 1
        assert len(s.unresolved_contradictions) == 1
        assert len(s.expected_states) == 1
