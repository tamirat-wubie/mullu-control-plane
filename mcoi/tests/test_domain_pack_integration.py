"""Integration tests for DomainPackIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.domain_pack import (
    DomainExtractionRule,
    DomainMemoryRule,
    DomainPackDescriptor,
    DomainPackStatus,
    DomainRoutingRule,
    DomainRuleKind,
    DomainSimulationProfile,
    DomainUtilityProfile,
    DomainBenchmarkProfile,
    DomainEscalationProfile,
    DomainVocabularyEntry,
    PackScope,
)
from mcoi_runtime.core.domain_pack import DomainPackEngine
from mcoi_runtime.core.domain_pack_integration import DomainPackIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

NOW = "2026-03-20T12:00:00+00:00"


def _build():
    pe = DomainPackEngine()
    es = EventSpineEngine()
    me = MemoryMeshEngine()
    integ = DomainPackIntegration(
        pack_engine=pe, event_spine=es, memory_engine=me,
    )
    return pe, es, me, integ


def _add_active_pack(pe, pack_id="pk-1", domain_name="test",
                     scope=PackScope.GLOBAL, scope_ref_id=""):
    pe.register_pack(DomainPackDescriptor(
        pack_id=pack_id, domain_name=domain_name,
        version="1.0.0", scope=scope, scope_ref_id=scope_ref_id,
        created_at=NOW,
    ))
    pe.activate_pack(pack_id)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid(self):
        _, _, _, integ = _build()
        assert integ is not None

    def test_bad_pack_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="pack_engine"):
            DomainPackIntegration(
                pack_engine="bad",
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
            )

    def test_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            DomainPackIntegration(
                pack_engine=DomainPackEngine(),
                event_spine="bad",
                memory_engine=MemoryMeshEngine(),
            )

    def test_bad_memory_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            DomainPackIntegration(
                pack_engine=DomainPackEngine(),
                event_spine=EventSpineEngine(),
                memory_engine="bad",
            )


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


class TestScopeResolution:
    def test_resolve_for_goal(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        res = integ.resolve_for_goal("goal-1")
        assert res.scope == PackScope.GOAL
        assert "pk-1" in res.resolved_pack_ids

    def test_resolve_for_workflow(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        res = integ.resolve_for_workflow("wf-1")
        assert res.scope == PackScope.WORKFLOW

    def test_resolve_for_function(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        res = integ.resolve_for_function("fn-1")
        assert res.scope == PackScope.FUNCTION

    def test_resolve_for_team(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        res = integ.resolve_for_team("team-1")
        assert res.scope == PackScope.TEAM


# ---------------------------------------------------------------------------
# Application methods
# ---------------------------------------------------------------------------


class TestApplicationMethods:
    def test_apply_to_commitment_extraction(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_extraction_rule(DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            created_at=NOW,
        ))
        pe.add_vocabulary_entry(DomainVocabularyEntry(
            entry_id="v-1", pack_id="pk-1",
            term="deploy", canonical_form="deployment",
            created_at=NOW,
        ))
        result = integ.apply_to_commitment_extraction(PackScope.GLOBAL)
        assert len(result["extraction_rules"]) == 1
        assert len(result["vocabulary"]) == 1
        assert result["event"] is not None

    def test_apply_to_artifact_ingestion(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        result = integ.apply_to_artifact_ingestion(PackScope.GLOBAL)
        assert "ingestion_rules" in result
        assert result["event"] is not None

    def test_apply_to_contact_routing(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_routing_rule(DomainRoutingRule(
            rule_id="rr-1", pack_id="pk-1",
            target_role="ops", created_at=NOW,
        ))
        result = integ.apply_to_contact_routing(PackScope.GLOBAL)
        assert len(result["routing_rules"]) == 1
        assert result["event"] is not None

    def test_apply_to_memory_mesh(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_memory_rule(DomainMemoryRule(
            rule_id="mr-1", pack_id="pk-1",
            memory_type="observation", created_at=NOW,
        ))
        result = integ.apply_to_memory_mesh(PackScope.GLOBAL)
        assert len(result["memory_rules"]) == 1

    def test_apply_to_simulation(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_simulation_profile(DomainSimulationProfile(
            profile_id="sp-1", pack_id="pk-1", created_at=NOW,
        ))
        result = integ.apply_to_simulation(PackScope.GLOBAL)
        assert result["simulation_profile"] is not None

    def test_apply_to_utility(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_utility_profile(DomainUtilityProfile(
            profile_id="up-1", pack_id="pk-1", created_at=NOW,
        ))
        result = integ.apply_to_utility(PackScope.GLOBAL)
        assert result["utility_profile"] is not None

    def test_apply_to_governance(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_extraction_rule(DomainExtractionRule(
            rule_id="r-gov-1", pack_id="pk-1",
            pattern=r"\brequires approval\b", commitment_type="approval",
            created_at=NOW,
        ))
        result = integ.apply_to_governance(PackScope.GLOBAL)
        assert len(result["governance_rules"]) == 1

    def test_apply_to_benchmarking(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        pe.add_benchmark_profile(DomainBenchmarkProfile(
            profile_id="bp-1", pack_id="pk-1",
            suite_ids=("s1",),
            adversarial_categories=("cat1",),
            created_at=NOW,
        ))
        result = integ.apply_to_benchmarking(PackScope.GLOBAL)
        assert result["benchmark_profile"] is not None
        assert result["event"].payload["suite_count"] == 1


# ---------------------------------------------------------------------------
# Memory integration
# ---------------------------------------------------------------------------


class TestMemoryIntegration:
    def test_remember_pack_activation(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        result = integ.remember_pack_activation("pk-1", "initial activation")
        assert result["memory"] is not None
        assert "domain_pack" in result["memory"].tags
        assert result["event"] is not None

    def test_remember_with_tags(self):
        pe, es, me, integ = _build()
        _add_active_pack(pe)
        result = integ.remember_pack_activation(
            "pk-1", tags=("deploy",),
        )
        assert "deploy" in result["memory"].tags
