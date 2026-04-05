"""Focused bounded-contract tests for OntologyRuntimeEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.ontology_runtime import (
    ConceptKind,
    MappingDisposition,
)
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.ontology_runtime import OntologyRuntimeEngine


@pytest.fixture()
def engine() -> OntologyRuntimeEngine:
    return OntologyRuntimeEngine(EventSpineEngine(), clock=FixedClock())


class TestBoundedContracts:
    def test_duplicate_and_unknown_contracts_do_not_reflect_ids(
        self, engine: OntologyRuntimeEngine
    ) -> None:
        engine.register_concept("concept-secret", "t-1", "Alpha", ConceptKind.ENTITY, "canon")

        with pytest.raises(RuntimeCoreInvariantError) as dup_exc:
            engine.register_concept("concept-secret", "t-1", "Alpha", ConceptKind.ENTITY, "canon")
        dup_message = str(dup_exc.value)
        assert dup_message == "Duplicate concept_id"
        assert "concept-secret" not in dup_message
        assert "Duplicate concept_id" in dup_message

        with pytest.raises(RuntimeCoreInvariantError) as unknown_exc:
            engine.get_concept("concept-missing")
        unknown_message = str(unknown_exc.value)
        assert unknown_message == "Unknown concept_id"
        assert "concept-missing" not in unknown_message
        assert "Unknown concept_id" in unknown_message

    def test_terminal_and_ref_contracts_do_not_reflect_values(
        self, engine: OntologyRuntimeEngine
    ) -> None:
        engine.register_concept("concept-secret", "t-1", "Alpha", ConceptKind.ENTITY, "canon")
        engine.retire_concept("concept-secret")
        with pytest.raises(RuntimeCoreInvariantError) as terminal_exc:
            engine.deprecate_concept("concept-secret")
        terminal_message = str(terminal_exc.value)
        assert terminal_message == "Cannot transition concept from terminal state"
        assert "RETIRED" not in terminal_message
        assert "concept-secret" not in terminal_message

        with pytest.raises(RuntimeCoreInvariantError) as ref_exc:
            engine.register_relation("relation-secret", "t-1", "parent-missing", "child-missing", ConceptKind.ENTITY)
        ref_message = str(ref_exc.value)
        assert ref_message == "Unknown parent_ref concept"
        assert "parent-missing" not in ref_message
        assert "child-missing" not in ref_message

    def test_conflict_and_violation_reasons_are_bounded(
        self, engine: OntologyRuntimeEngine
    ) -> None:
        engine.register_concept("concept-a", "t-1", "Alpha", ConceptKind.ENTITY, "canon")
        engine.register_concept("concept-b", "t-1", "AlphaType", ConceptKind.ATTRIBUTE, "canon")
        conflicts = engine.detect_semantic_conflicts("t-1")
        assert conflicts[0].reason == "Concept canonical form kind mismatch"
        assert "'canon'" not in conflicts[0].reason
        assert "entity" not in conflicts[0].reason.lower()

        violations = engine.detect_ontology_violations("t-1")
        reasons = {violation.operation: violation.reason for violation in violations}
        assert reasons["unresolved_conflict"] == "Conflict unresolved"
        assert all("concept-a" not in reason for reason in reasons.values())
        assert all("concept-b" not in reason for reason in reasons.values())

    def test_mapping_violation_and_conflict_status_contracts_are_bounded(
        self, engine: OntologyRuntimeEngine
    ) -> None:
        engine.register_schema_mapping(
            "mapping-a", "t-1", "schema-source", "schema-target-a", MappingDisposition.EXACT, 3,
        )
        engine.register_schema_mapping(
            "mapping-b", "t-1", "schema-source", "schema-target-b", MappingDisposition.BROADER, 4,
        )
        conflicts = engine.detect_semantic_conflicts("t-1")
        mapping_conflict = next(conflict for conflict in conflicts if conflict.reason == "Mapping disposition conflict")
        assert mapping_conflict.reason == "Mapping disposition conflict"
        assert "schema-source" not in mapping_conflict.reason
        assert "partial" not in mapping_conflict.reason.lower()

        engine.resolve_conflict(mapping_conflict.conflict_id)
        with pytest.raises(RuntimeCoreInvariantError) as status_exc:
            engine.defer_conflict(mapping_conflict.conflict_id)
        status_message = str(status_exc.value)
        assert status_message == "Cannot transition conflict from current status"
        assert "RESOLVED" not in status_message
        assert mapping_conflict.conflict_id not in status_message
