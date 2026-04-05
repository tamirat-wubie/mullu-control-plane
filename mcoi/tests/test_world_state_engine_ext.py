"""Purpose: verify world-state engine extensions — snapshot assembly, delta computation,
conflict grouping, expected-vs-actual comparison, derived facts, resolutions, confidence envelopes.
Governance scope: world-state plane tests only.
Dependencies: world-state contracts, world-state engine.
Invariants: snapshots immutable; deltas computed not fabricated; conflicts grouped by entity.
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
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.world_state import WorldStateEngine


_CLOCK = "2026-03-20T00:00:00+00:00"
_CLOCK_FN = lambda: _CLOCK  # noqa: E731


def _engine() -> WorldStateEngine:
    return WorldStateEngine(clock=_CLOCK_FN)


def _entity(entity_id: str = "e-1", confidence: float = 0.8, **attrs: object) -> StateEntity:
    return StateEntity(
        entity_id=entity_id,
        entity_type="service",
        attributes={"status": "running", **attrs},
        evidence_ids=("ev-1",),
        confidence=confidence,
        created_at=_CLOCK,
    )


def _relation(
    rid: str = "r-1", src: str = "e-1", tgt: str = "e-2",
    rtype: str = "depends_on",
) -> EntityRelation:
    return EntityRelation(
        relation_id=rid,
        source_entity_id=src,
        target_entity_id=tgt,
        relation_type=rtype,
        evidence_ids=("ev-1",),
        confidence=0.9,
    )


def _contradiction(
    cid: str = "c-1", entity_id: str = "e-1", attribute: str = "status",
    strategy: ContradictionStrategy = ContradictionStrategy.ESCALATE,
) -> ContradictionRecord:
    return ContradictionRecord(
        contradiction_id=cid,
        entity_id=entity_id,
        attribute=attribute,
        conflicting_evidence_ids=("ev-1", "ev-2"),
        strategy=strategy,
        resolved=False,
    )


def _derived_fact(
    fact_id: str = "df-1", entity_id: str = "e-1",
) -> DerivedFact:
    return DerivedFact(
        fact_id=fact_id,
        entity_id=entity_id,
        attribute="health_score",
        derived_value=0.85,
        source_entity_ids=("e-1",),
        derivation_rule="avg_confidence",
        confidence=0.85,
        derived_at=_CLOCK,
    )


def _expected_state(
    eid: str = "exp-1", entity_id: str = "e-1",
    expected_value: object = "running",
) -> ExpectedState:
    return ExpectedState(
        expectation_id=eid,
        entity_id=entity_id,
        attribute="status",
        expected_value=expected_value,
        basis="workflow-plan",
        confidence=0.9,
        expected_by=_CLOCK,
        created_at=_CLOCK,
    )


def _resolution(
    rid: str = "res-1", contradiction_id: str = "c-1",
) -> ResolutionRecord:
    return ResolutionRecord(
        resolution_id=rid,
        contradiction_id=contradiction_id,
        resolved_value="running",
        strategy_used=ContradictionStrategy.PREFER_LATEST,
        resolver_id="auto-resolver",
        confidence=0.85,
        resolved_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# Clock injection
# ---------------------------------------------------------------------------

class TestClockInjection:
    def test_clock_used_in_snapshot(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        snap = eng.assemble_snapshot("s-1")
        assert snap.captured_at == _CLOCK

    def test_default_clock_produces_iso(self) -> None:
        eng = WorldStateEngine()  # default clock
        eng.add_entity(_entity())
        snap = eng.assemble_snapshot("s-1")
        assert "T" in snap.captured_at  # ISO format


# ---------------------------------------------------------------------------
# Derived Facts
# ---------------------------------------------------------------------------

class TestDerivedFacts:
    def test_add_and_list(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        eng.add_derived_fact(_derived_fact())
        assert eng.derived_fact_count == 1
        assert len(eng.list_derived_facts()) == 1

    def test_list_by_entity(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        eng.add_derived_fact(_derived_fact("df-1", "e-1"))
        eng.add_derived_fact(_derived_fact("df-2", "e-2"))
        assert len(eng.list_derived_facts(entity_id="e-1")) == 1

    def test_duplicate_rejected(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        eng.add_derived_fact(_derived_fact())
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.add_derived_fact(_derived_fact())

    def test_source_entity_must_exist(self) -> None:
        eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="source entity not found"):
            eng.add_derived_fact(_derived_fact())


# ---------------------------------------------------------------------------
# Resolutions
# ---------------------------------------------------------------------------

class TestResolutions:
    def test_record_and_list(self) -> None:
        eng = _engine()
        eng.record_contradiction(_contradiction())
        eng.record_resolution(_resolution())
        assert eng.resolution_count == 1
        assert len(eng.list_resolutions()) == 1

    def test_duplicate_rejected(self) -> None:
        eng = _engine()
        eng.record_contradiction(_contradiction())
        eng.record_resolution(_resolution())
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.record_resolution(_resolution())

    def test_contradiction_must_exist(self) -> None:
        eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="contradiction not found"):
            eng.record_resolution(_resolution())


# ---------------------------------------------------------------------------
# Expected States
# ---------------------------------------------------------------------------

class TestExpectedStates:
    def test_add_and_list(self) -> None:
        eng = _engine()
        eng.add_expected_state(_expected_state())
        assert eng.expected_state_count == 1
        assert len(eng.list_expected_states()) == 1

    def test_list_by_entity(self) -> None:
        eng = _engine()
        eng.add_expected_state(_expected_state("exp-1", "e-1"))
        eng.add_expected_state(_expected_state("exp-2", "e-2"))
        assert len(eng.list_expected_states(entity_id="e-1")) == 1

    def test_duplicate_rejected(self) -> None:
        eng = _engine()
        eng.add_expected_state(_expected_state())
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.add_expected_state(_expected_state())


# ---------------------------------------------------------------------------
# Expected vs Actual Comparison
# ---------------------------------------------------------------------------

class TestExpectedVsActual:
    def test_match(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "running"))
        expected, actual_repr, matches = eng.compare_expected_vs_actual("exp-1")
        assert matches is True
        assert actual_repr == "running"

    def test_mismatch(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1", "stopped"))
        expected, actual_repr, matches = eng.compare_expected_vs_actual("exp-1")
        assert matches is False
        assert actual_repr == "running"

    def test_missing_entity(self) -> None:
        eng = _engine()
        eng.add_expected_state(_expected_state("exp-1", "e-missing"))
        expected, actual_repr, matches = eng.compare_expected_vs_actual("exp-1")
        assert matches is False
        assert actual_repr == "<missing>"

    def test_missing_attribute(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        exp = ExpectedState(
            expectation_id="exp-1", entity_id="e-1",
            attribute="nonexistent", expected_value="foo",
            basis="test", confidence=0.9,
            expected_by=_CLOCK, created_at=_CLOCK,
        )
        eng.add_expected_state(exp)
        _, actual_repr, matches = eng.compare_expected_vs_actual("exp-1")
        assert matches is False
        assert actual_repr == "<missing>"

    def test_unknown_expectation_raises(self) -> None:
        eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.compare_expected_vs_actual("exp-missing")


# ---------------------------------------------------------------------------
# Conflict Grouping
# ---------------------------------------------------------------------------

class TestConflictGrouping:
    def test_empty_returns_empty(self) -> None:
        eng = _engine()
        assert eng.group_conflicts() == ()

    def test_groups_by_entity(self) -> None:
        eng = _engine()
        eng.record_contradiction(_contradiction("c-1", "e-1"))
        eng.record_contradiction(_contradiction("c-2", "e-1"))
        eng.record_contradiction(_contradiction("c-3", "e-2"))
        sets = eng.group_conflicts()
        assert len(sets) == 2
        e1_set = [s for s in sets if s.entity_id == "e-1"][0]
        assert len(e1_set.contradictions) == 2

    def test_escalate_strategy_wins(self) -> None:
        eng = _engine()
        eng.record_contradiction(_contradiction("c-1", "e-1", strategy=ContradictionStrategy.PREFER_LATEST))
        eng.record_contradiction(_contradiction("c-2", "e-1", strategy=ContradictionStrategy.ESCALATE))
        sets = eng.group_conflicts()
        assert sets[0].overall_strategy == ContradictionStrategy.ESCALATE

    def test_manual_strategy_when_no_escalate(self) -> None:
        eng = _engine()
        eng.record_contradiction(_contradiction("c-1", "e-1", strategy=ContradictionStrategy.MANUAL))
        eng.record_contradiction(_contradiction("c-2", "e-1", strategy=ContradictionStrategy.PREFER_LATEST))
        sets = eng.group_conflicts()
        assert sets[0].overall_strategy == ContradictionStrategy.MANUAL

    def test_resolved_contradictions_excluded(self) -> None:
        eng = _engine()
        resolved = ContradictionRecord(
            contradiction_id="c-1", entity_id="e-1", attribute="status",
            conflicting_evidence_ids=("ev-1", "ev-2"),
            strategy=ContradictionStrategy.PREFER_LATEST, resolved=True,
        )
        eng.record_contradiction(resolved)
        assert eng.group_conflicts() == ()


# ---------------------------------------------------------------------------
# Confidence Envelopes
# ---------------------------------------------------------------------------

class TestConfidenceEnvelope:
    def test_basic_envelope(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1", confidence=0.8))
        env = eng.compute_confidence_envelope("e-1", "status")
        assert isinstance(env, StateConfidenceEnvelope)
        assert env.point_estimate == 0.8
        assert env.lower_bound <= env.point_estimate <= env.upper_bound
        assert env.evidence_count == 1

    def test_contradiction_widens_bounds(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1", confidence=0.8))
        env_clean = eng.compute_confidence_envelope("e-1", "status")
        eng.record_contradiction(_contradiction("c-1", "e-1", "status"))
        env_dirty = eng.compute_confidence_envelope("e-1", "status")
        assert env_dirty.lower_bound < env_clean.lower_bound

    def test_missing_entity_raises(self) -> None:
        eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="entity not found"):
            eng.compute_confidence_envelope("e-missing", "status")


# ---------------------------------------------------------------------------
# Snapshot Assembly
# ---------------------------------------------------------------------------

class TestSnapshotAssembly:
    def test_empty_snapshot(self) -> None:
        eng = _engine()
        snap = eng.assemble_snapshot("s-1")
        assert isinstance(snap, WorldStateSnapshot)
        assert snap.entity_count == 0
        assert snap.overall_confidence == 0.0

    def test_snapshot_captures_all_state(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        eng.add_relation(_relation("r-1", "e-1", "e-2"))
        eng.add_derived_fact(_derived_fact("df-1", "e-1"))
        eng.record_contradiction(_contradiction("c-1", "e-1"))
        eng.add_expected_state(_expected_state("exp-1", "e-1"))

        snap = eng.assemble_snapshot("s-1")
        assert snap.entity_count == 2
        assert snap.relation_count == 1
        assert len(snap.derived_facts) == 1
        assert len(snap.unresolved_contradictions) == 1
        assert len(snap.expected_states) == 1
        assert snap.captured_at == _CLOCK

    def test_snapshot_overall_confidence(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1", confidence=0.8))
        eng.add_entity(_entity("e-2", confidence=0.6))
        snap = eng.assemble_snapshot("s-1")
        assert snap.overall_confidence == 0.7

    def test_snapshot_auto_id(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        snap = eng.assemble_snapshot()
        assert snap.snapshot_id.startswith("wss-")

    def test_snapshot_hash_populated(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        snap = eng.assemble_snapshot("s-1")
        assert len(snap.state_hash) == 64

    def test_snapshot_frozen(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        snap = eng.assemble_snapshot("s-1")
        with pytest.raises(AttributeError):
            snap.entity_count = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Delta Computation
# ---------------------------------------------------------------------------

class TestDeltaComputation:
    def test_no_changes_no_deltas(self) -> None:
        eng = _engine()
        eng.add_entity(_entity())
        snap = eng.assemble_snapshot("s-1")
        deltas = eng.compute_deltas(snap, snap)
        assert deltas == ()

    def test_entity_added(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        snap1 = eng.assemble_snapshot("s-1")
        eng.add_entity(_entity("e-2"))
        snap2 = eng.assemble_snapshot("s-2")
        deltas = eng.compute_deltas(snap1, snap2)
        added = [d for d in deltas if d.kind == DeltaKind.ENTITY_ADDED]
        assert len(added) == 1
        assert added[0].target_id == "e-2"

    def test_entity_removed(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        snap1 = eng.assemble_snapshot("s-1")
        # Build a second engine without e-2
        eng2 = _engine()
        eng2.add_entity(_entity("e-1"))
        snap2 = eng2.assemble_snapshot("s-2")
        deltas = eng.compute_deltas(snap1, snap2)
        removed = [d for d in deltas if d.kind == DeltaKind.ENTITY_REMOVED]
        assert len(removed) == 1
        assert removed[0].target_id == "e-2"

    def test_entity_modified(self) -> None:
        eng1 = _engine()
        eng1.add_entity(_entity("e-1"))
        snap1 = eng1.assemble_snapshot("s-1")

        eng2 = _engine()
        eng2.add_entity(StateEntity(
            entity_id="e-1", entity_type="service",
            attributes={"status": "stopped"},
            evidence_ids=("ev-1",), confidence=0.8,
            created_at=_CLOCK,
        ))
        snap2 = eng2.assemble_snapshot("s-2")

        deltas = eng1.compute_deltas(snap1, snap2)
        modified = [d for d in deltas if d.kind == DeltaKind.ENTITY_MODIFIED]
        assert len(modified) == 1

    def test_relation_added(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        eng.add_entity(_entity("e-2"))
        snap1 = eng.assemble_snapshot("s-1")
        eng.add_relation(_relation("r-1", "e-1", "e-2"))
        snap2 = eng.assemble_snapshot("s-2")
        deltas = eng.compute_deltas(snap1, snap2)
        rel_added = [d for d in deltas if d.kind == DeltaKind.RELATION_ADDED]
        assert len(rel_added) == 1

    def test_fact_derived_delta(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        snap1 = eng.assemble_snapshot("s-1")
        eng.add_derived_fact(_derived_fact("df-1", "e-1"))
        snap2 = eng.assemble_snapshot("s-2")
        deltas = eng.compute_deltas(snap1, snap2)
        fact_deltas = [d for d in deltas if d.kind == DeltaKind.FACT_DERIVED]
        assert len(fact_deltas) == 1

    def test_delta_ids_deterministic(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("e-1"))
        snap1 = eng.assemble_snapshot("s-1")
        eng.add_entity(_entity("e-2"))
        snap2 = eng.assemble_snapshot("s-2")
        deltas_a = eng.compute_deltas(snap1, snap2)
        deltas_b = eng.compute_deltas(snap1, snap2)
        assert deltas_a == deltas_b


# ---------------------------------------------------------------------------
# Golden Scenario: cross-plane state merge + contradiction + expected-vs-actual
# ---------------------------------------------------------------------------

class TestGoldenScenario:
    def test_full_world_state_lifecycle(self) -> None:
        eng = _engine()

        # Step 1: Add entities
        eng.add_entity(_entity("svc-api", confidence=0.9))
        eng.add_entity(_entity("svc-db", confidence=0.7))
        eng.add_relation(_relation("r-1", "svc-api", "svc-db"))

        # Step 2: Derive a fact
        eng.add_derived_fact(DerivedFact(
            fact_id="df-health",
            entity_id="svc-api",
            attribute="system_health",
            derived_value="degraded",
            source_entity_ids=("svc-api", "svc-db"),
            derivation_rule="min_dependency_confidence",
            confidence=0.7,
            derived_at=_CLOCK,
        ))

        # Step 3: Record expectation + contradiction
        eng.add_expected_state(_expected_state("exp-1", "svc-api", "running"))
        eng.record_contradiction(_contradiction("c-1", "svc-api", "status"))

        # Step 4: Take snapshot
        snap1 = eng.assemble_snapshot("s-lifecycle-1")
        assert snap1.entity_count == 2
        assert snap1.relation_count == 1
        assert len(snap1.derived_facts) == 1
        assert len(snap1.unresolved_contradictions) == 1

        # Step 5: Expected vs actual (matches, entity has status=running)
        _, actual, matches = eng.compare_expected_vs_actual("exp-1")
        assert matches is True

        # Step 6: Group conflicts
        conflict_sets = eng.group_conflicts()
        assert len(conflict_sets) == 1
        assert conflict_sets[0].entity_id == "svc-api"

        # Step 7: Resolve contradiction
        eng.record_resolution(ResolutionRecord(
            resolution_id="res-1",
            contradiction_id="c-1",
            resolved_value="running",
            strategy_used=ContradictionStrategy.PREFER_LATEST,
            resolver_id="auto-resolver",
            confidence=0.85,
            resolved_at=_CLOCK,
        ))
        assert eng.resolution_count == 1

        # Step 8: Confidence envelope
        env = eng.compute_confidence_envelope("svc-api", "status")
        assert env.entity_id == "svc-api"

        # Step 9: Second snapshot + deltas
        eng.add_entity(_entity("svc-cache", confidence=0.95))
        snap2 = eng.assemble_snapshot("s-lifecycle-2")
        deltas = eng.compute_deltas(snap1, snap2)
        assert any(d.kind == DeltaKind.ENTITY_ADDED and d.target_id == "svc-cache" for d in deltas)


class TestBoundedWorldStateContracts:
    def test_derived_resolution_and_expectation_errors_are_bounded(self) -> None:
        eng = _engine()
        eng.add_entity(_entity("entity-secret"))
        eng.record_contradiction(_contradiction("contradiction-secret", "entity-secret"))
        eng.add_derived_fact(DerivedFact(
            fact_id="fact-secret",
            entity_id="entity-secret",
            attribute="health_score",
            derived_value=0.85,
            source_entity_ids=("entity-secret",),
            derivation_rule="avg_confidence",
            confidence=0.85,
            derived_at=_CLOCK,
        ))
        eng.record_resolution(_resolution("resolution-secret", "contradiction-secret"))
        eng.add_expected_state(_expected_state("expectation-secret", "entity-secret"))

        with pytest.raises(RuntimeCoreInvariantError) as duplicate_contradiction:
            eng.record_contradiction(_contradiction("contradiction-secret", "entity-secret"))
        with pytest.raises(RuntimeCoreInvariantError) as duplicate_fact:
            eng.add_derived_fact(_derived_fact("fact-secret", "entity-secret"))
        with pytest.raises(RuntimeCoreInvariantError) as duplicate_resolution:
            eng.record_resolution(_resolution("resolution-secret", "contradiction-secret"))
        with pytest.raises(RuntimeCoreInvariantError) as duplicate_expectation:
            eng.add_expected_state(_expected_state("expectation-secret", "entity-secret"))

        assert str(duplicate_contradiction.value) == "contradiction already recorded"
        assert str(duplicate_fact.value) == "derived fact already exists"
        assert str(duplicate_resolution.value) == "resolution already exists"
        assert str(duplicate_expectation.value) == "expected state already exists"
        assert "contradiction-secret" not in str(duplicate_contradiction.value)
        assert "fact-secret" not in str(duplicate_fact.value)
        assert "resolution-secret" not in str(duplicate_resolution.value)
        assert "expectation-secret" not in str(duplicate_expectation.value)

    def test_missing_reference_errors_are_bounded(self) -> None:
        eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError) as missing_source:
            eng.add_derived_fact(_derived_fact("fact-secret", "entity-secret"))
        with pytest.raises(RuntimeCoreInvariantError) as missing_contradiction:
            eng.record_resolution(_resolution("resolution-secret", "contradiction-secret"))
        with pytest.raises(RuntimeCoreInvariantError) as missing_entity:
            eng.compute_confidence_envelope("entity-secret", "status")

        assert str(missing_source.value) == "source entity not found"
        assert str(missing_contradiction.value) == "contradiction not found"
        assert str(missing_entity.value) == "entity not found"
        assert "entity-secret" not in str(missing_source.value)
        assert "contradiction-secret" not in str(missing_contradiction.value)
        assert "entity-secret" not in str(missing_entity.value)

    def test_delta_descriptions_are_bounded(self) -> None:
        eng1 = _engine()
        eng1.add_entity(_entity("entity-secret"))
        snap1 = eng1.assemble_snapshot("snap-1")

        eng2 = _engine()
        eng2.add_entity(StateEntity(
            entity_id="entity-secret",
            entity_type="service",
            attributes={"status": "changed"},
            evidence_ids=("ev-1",),
            confidence=0.8,
            created_at=_CLOCK,
        ))
        eng2.add_entity(_entity("entity-added-secret"))
        eng2.add_relation(_relation("relation-added-secret", "entity-secret", "entity-added-secret"))
        eng2.add_derived_fact(DerivedFact(
            fact_id="fact-added-secret",
            entity_id="entity-secret",
            attribute="health_score",
            derived_value=0.85,
            source_entity_ids=("entity-secret",),
            derivation_rule="avg_confidence",
            confidence=0.85,
            derived_at=_CLOCK,
        ))
        snap2 = eng2.assemble_snapshot("snap-2")

        deltas = eng1.compute_deltas(snap1, snap2)
        descriptions = {delta.kind: delta.description for delta in deltas}

        assert descriptions[DeltaKind.ENTITY_ADDED] == "entity added"
        assert descriptions[DeltaKind.ENTITY_MODIFIED] == "entity modified"
        assert descriptions[DeltaKind.RELATION_ADDED] == "relation added"
        assert descriptions[DeltaKind.FACT_DERIVED] == "fact derived"

        for delta in deltas:
            assert "entity-added-secret" not in delta.description
            assert "relation-added-secret" not in delta.description
            assert "fact-added-secret" not in delta.description
