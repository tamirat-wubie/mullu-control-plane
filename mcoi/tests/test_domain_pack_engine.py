"""Engine-level tests for DomainPackEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.domain_pack import (
    DomainBenchmarkProfile,
    DomainEscalationProfile,
    DomainExtractionRule,
    DomainMemoryRule,
    DomainPackDescriptor,
    DomainPackStatus,
    DomainRoutingRule,
    DomainRuleKind,
    DomainSimulationProfile,
    DomainUtilityProfile,
    DomainVocabularyEntry,
    PackScope,
)
from mcoi_runtime.core.domain_pack import DomainPackEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


def _make_pack(pack_id="pk-1", domain_name="test", version="1.0.0",
               status=DomainPackStatus.DRAFT, scope=PackScope.GLOBAL,
               scope_ref_id="", **kw):
    return DomainPackDescriptor(
        pack_id=pack_id, domain_name=domain_name, version=version,
        status=status, scope=scope, scope_ref_id=scope_ref_id,
        created_at=NOW, **kw,
    )


def _make_engine_with_pack(pack_id="pk-1", activate=True, **kw):
    engine = DomainPackEngine()
    engine.register_pack(_make_pack(pack_id=pack_id, **kw))
    if activate:
        engine.activate_pack(pack_id)
    return engine


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register(self):
        engine = DomainPackEngine()
        pack = engine.register_pack(_make_pack())
        assert pack.pack_id == "pk-1"
        assert engine.pack_count == 1

    def test_duplicate_rejected(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack())
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.register_pack(_make_pack())
        assert str(exc_info.value) == "pack already registered"
        assert "pk-1" not in str(exc_info.value)

    def test_invalid_descriptor(self):
        engine = DomainPackEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="DomainPackDescriptor"):
            engine.register_pack("bad")

    def test_get_pack(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack())
        assert engine.get_pack("pk-1").pack_id == "pk-1"

    def test_get_missing_pack(self):
        engine = DomainPackEngine()
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.get_pack("missing")
        assert str(exc_info.value) == "pack not found"
        assert "missing" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Activation lifecycle
# ---------------------------------------------------------------------------


class TestActivation:
    def test_activate_draft(self):
        engine = _make_engine_with_pack(activate=False)
        activation = engine.activate_pack("pk-1")
        assert activation.new_status == DomainPackStatus.ACTIVE
        assert engine.get_pack("pk-1").status == DomainPackStatus.ACTIVE

    def test_activate_disabled(self):
        engine = _make_engine_with_pack(activate=True)
        engine.disable_pack("pk-1")
        engine.activate_pack("pk-1")
        assert engine.get_pack("pk-1").status == DomainPackStatus.ACTIVE

    def test_activate_already_active(self):
        engine = _make_engine_with_pack(activate=True)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.activate_pack("pk-1")
        assert str(exc_info.value) == "pack already active"
        assert "pk-1" not in str(exc_info.value)

    def test_activate_deprecated(self):
        engine = _make_engine_with_pack(activate=True)
        engine.deprecate_pack("pk-1")
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.activate_pack("pk-1")
        assert str(exc_info.value) == "deprecated pack cannot be activated"
        assert "pk-1" not in str(exc_info.value)

    def test_deprecate(self):
        engine = _make_engine_with_pack(activate=True)
        activation = engine.deprecate_pack("pk-1")
        assert activation.new_status == DomainPackStatus.DEPRECATED
        assert engine.get_pack("pk-1").status == DomainPackStatus.DEPRECATED

    def test_deprecate_non_active(self):
        engine = _make_engine_with_pack(activate=False)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.deprecate_pack("pk-1")
        assert str(exc_info.value) == "pack must be active before deprecation"
        assert "draft" not in str(exc_info.value).lower()

    def test_disable(self):
        engine = _make_engine_with_pack(activate=True)
        activation = engine.disable_pack("pk-1")
        assert activation.new_status == DomainPackStatus.DISABLED

    def test_disable_non_active(self):
        engine = _make_engine_with_pack(activate=False)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.disable_pack("pk-1")
        assert str(exc_info.value) == "pack must be active before disable"
        assert "draft" not in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class TestListing:
    def test_list_all(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1"))
        engine.register_pack(_make_pack("pk-2", domain_name="other"))
        assert len(engine.list_packs()) == 2

    def test_list_by_domain(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1", domain_name="alpha"))
        engine.register_pack(_make_pack("pk-2", domain_name="beta"))
        assert len(engine.list_packs(domain_name="alpha")) == 1

    def test_list_by_status(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1"))
        engine.register_pack(_make_pack("pk-2", domain_name="other"))
        engine.activate_pack("pk-1")
        assert len(engine.list_packs(status=DomainPackStatus.ACTIVE)) == 1

    def test_list_active(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1"))
        engine.register_pack(_make_pack("pk-2", domain_name="other"))
        engine.activate_pack("pk-1")
        assert len(engine.list_active_packs()) == 1

    def test_active_pack_count(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1"))
        engine.register_pack(_make_pack("pk-2", domain_name="other"))
        assert engine.active_pack_count == 0
        engine.activate_pack("pk-1")
        assert engine.active_pack_count == 1


# ---------------------------------------------------------------------------
# Rule/profile registration
# ---------------------------------------------------------------------------


class TestRuleRegistration:
    def test_add_extraction_rule(self):
        engine = _make_engine_with_pack()
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            created_at=NOW,
        ))
        assert engine.extraction_rule_count == 1

    def test_extraction_rule_requires_pack(self):
        engine = DomainPackEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.add_extraction_rule(DomainExtractionRule(
                rule_id="r-1", pack_id="missing",
                pattern=r"\bdeploy\b", commitment_type="delivery",
                created_at=NOW,
            ))

    def test_duplicate_extraction_rule(self):
        engine = _make_engine_with_pack()
        rule = DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            created_at=NOW,
        )
        engine.add_extraction_rule(rule)
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            engine.add_extraction_rule(rule)
        assert str(exc_info.value) == "duplicate extraction rule"
        assert "r-1" not in str(exc_info.value)

    def test_add_routing_rule(self):
        engine = _make_engine_with_pack()
        engine.add_routing_rule(DomainRoutingRule(
            rule_id="rr-1", pack_id="pk-1",
            target_role="ops", created_at=NOW,
        ))
        assert engine.routing_rule_count == 1

    def test_add_memory_rule(self):
        engine = _make_engine_with_pack()
        engine.add_memory_rule(DomainMemoryRule(
            rule_id="mr-1", pack_id="pk-1",
            memory_type="observation", created_at=NOW,
        ))

    def test_add_simulation_profile(self):
        engine = _make_engine_with_pack()
        engine.add_simulation_profile(DomainSimulationProfile(
            profile_id="sp-1", pack_id="pk-1", created_at=NOW,
        ))

    def test_add_utility_profile(self):
        engine = _make_engine_with_pack()
        engine.add_utility_profile(DomainUtilityProfile(
            profile_id="up-1", pack_id="pk-1", created_at=NOW,
        ))

    def test_add_benchmark_profile(self):
        engine = _make_engine_with_pack()
        engine.add_benchmark_profile(DomainBenchmarkProfile(
            profile_id="bp-1", pack_id="pk-1", created_at=NOW,
        ))

    def test_add_escalation_profile(self):
        engine = _make_engine_with_pack()
        engine.add_escalation_profile(DomainEscalationProfile(
            profile_id="ep-1", pack_id="pk-1",
            escalation_roles=("oncall",), created_at=NOW,
        ))

    def test_add_vocabulary(self):
        engine = _make_engine_with_pack()
        engine.add_vocabulary_entry(DomainVocabularyEntry(
            entry_id="v-1", pack_id="pk-1",
            term="deploy", canonical_form="deployment",
            created_at=NOW,
        ))
        vocab = engine.get_vocabulary_for_pack("pk-1")
        assert len(vocab) == 1

    def test_invalid_rule_type(self):
        engine = _make_engine_with_pack()
        with pytest.raises(RuntimeCoreInvariantError):
            engine.add_extraction_rule("not a rule")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class TestResolution:
    def test_resolve_empty(self):
        engine = DomainPackEngine()
        res = engine.resolve_for_scope(PackScope.GLOBAL)
        assert len(res.resolved_pack_ids) == 0

    def test_resolve_active_only(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1"))
        engine.register_pack(_make_pack("pk-2", domain_name="other"))
        engine.activate_pack("pk-1")
        res = engine.resolve_for_scope(PackScope.GLOBAL)
        assert "pk-1" in res.resolved_pack_ids
        assert "pk-2" not in res.resolved_pack_ids

    def test_narrower_scope_beats_broader(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-global", scope=PackScope.GLOBAL))
        engine.register_pack(_make_pack("pk-team", domain_name="other", scope=PackScope.TEAM))
        engine.activate_pack("pk-global")
        engine.activate_pack("pk-team")
        res = engine.resolve_for_scope(PackScope.TEAM)
        ids = list(res.resolved_pack_ids)
        # Team-scoped should come first (higher specificity)
        assert ids.index("pk-team") < ids.index("pk-global")

    def test_scope_filtering(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-goal", scope=PackScope.GOAL))
        engine.activate_pack("pk-goal")
        # GOAL-scoped pack should NOT appear for GLOBAL resolution
        res = engine.resolve_for_scope(PackScope.GLOBAL)
        assert "pk-goal" not in res.resolved_pack_ids

    def test_exact_scope_ref_preferred(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1", scope=PackScope.TEAM, scope_ref_id="team-a"))
        engine.register_pack(_make_pack("pk-2", domain_name="other", scope=PackScope.TEAM, scope_ref_id="team-b"))
        engine.activate_pack("pk-1")
        engine.activate_pack("pk-2")
        res = engine.resolve_for_scope(PackScope.TEAM, "team-a")
        ids = list(res.resolved_pack_ids)
        # pk-1 should come first (exact scope_ref match)
        assert ids[0] == "pk-1"

    def test_resolve_extraction_rules(self):
        engine = _make_engine_with_pack()
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            priority=10, created_at=NOW,
        ))
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id="r-2", pack_id="pk-1",
            pattern=r"\brollback\b", commitment_type="escalation",
            priority=20, created_at=NOW,
        ))
        rules = engine.resolve_extraction_rules(PackScope.GLOBAL)
        assert len(rules) == 2
        # Higher priority first
        assert rules[0].priority >= rules[1].priority

    def test_resolve_routing_rules(self):
        engine = _make_engine_with_pack()
        engine.add_routing_rule(DomainRoutingRule(
            rule_id="rr-1", pack_id="pk-1",
            target_role="ops", created_at=NOW,
        ))
        rules = engine.resolve_routing_rules(PackScope.GLOBAL)
        assert len(rules) == 1

    def test_resolve_memory_rules(self):
        engine = _make_engine_with_pack()
        engine.add_memory_rule(DomainMemoryRule(
            rule_id="mr-1", pack_id="pk-1",
            memory_type="observation", created_at=NOW,
        ))
        rules = engine.resolve_memory_rules(PackScope.GLOBAL)
        assert len(rules) == 1

    def test_resolve_simulation_profile(self):
        engine = _make_engine_with_pack()
        engine.add_simulation_profile(DomainSimulationProfile(
            profile_id="sp-1", pack_id="pk-1", created_at=NOW,
        ))
        profile = engine.resolve_simulation_profile(PackScope.GLOBAL)
        assert profile is not None
        assert profile.profile_id == "sp-1"

    def test_resolve_simulation_profile_none(self):
        engine = _make_engine_with_pack()
        assert engine.resolve_simulation_profile(PackScope.GLOBAL) is None

    def test_resolve_utility_profile(self):
        engine = _make_engine_with_pack()
        engine.add_utility_profile(DomainUtilityProfile(
            profile_id="up-1", pack_id="pk-1", created_at=NOW,
        ))
        assert engine.resolve_utility_profile(PackScope.GLOBAL) is not None

    def test_resolve_benchmark_profile(self):
        engine = _make_engine_with_pack()
        engine.add_benchmark_profile(DomainBenchmarkProfile(
            profile_id="bp-1", pack_id="pk-1", created_at=NOW,
        ))
        assert engine.resolve_benchmark_profile(PackScope.GLOBAL) is not None

    def test_resolve_escalation_profile(self):
        engine = _make_engine_with_pack()
        engine.add_escalation_profile(DomainEscalationProfile(
            profile_id="ep-1", pack_id="pk-1",
            escalation_roles=("oncall",), created_at=NOW,
        ))
        assert engine.resolve_escalation_profile(PackScope.GLOBAL) is not None

    def test_deprecated_pack_excluded_from_resolution(self):
        engine = _make_engine_with_pack()
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            created_at=NOW,
        ))
        engine.deprecate_pack("pk-1")
        rules = engine.resolve_extraction_rules(PackScope.GLOBAL)
        assert len(rules) == 0


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestConflicts:
    def test_same_domain_same_scope_conflicts(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1", domain_name="shared"))
        engine.register_pack(_make_pack("pk-2", domain_name="shared", version="2.0.0"))
        engine.activate_pack("pk-1")
        engine.activate_pack("pk-2")
        res = engine.resolve_for_scope(PackScope.GLOBAL)
        assert len(res.conflict_ids) >= 1
        assert engine.conflict_count >= 1

    def test_different_domains_no_conflict(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1", domain_name="alpha"))
        engine.register_pack(_make_pack("pk-2", domain_name="beta"))
        engine.activate_pack("pk-1")
        engine.activate_pack("pk-2")
        res = engine.resolve_for_scope(PackScope.GLOBAL)
        assert len(res.conflict_ids) == 0

    def test_find_conflicts(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1", domain_name="shared"))
        engine.register_pack(_make_pack("pk-2", domain_name="shared", version="2.0.0"))
        engine.activate_pack("pk-1")
        engine.activate_pack("pk-2")
        engine.resolve_for_scope(PackScope.GLOBAL)
        conflicts = engine.find_conflicts()
        assert len(conflicts) >= 1
        assert conflicts[0].description == "Conflicting domain pack rules"
        assert "pk-1" not in conflicts[0].description
        assert "pk-2" not in conflicts[0].description

    def test_find_conflicts_by_scope(self):
        engine = DomainPackEngine()
        engine.register_pack(_make_pack("pk-1", domain_name="shared"))
        engine.register_pack(_make_pack("pk-2", domain_name="shared", version="2.0.0"))
        engine.activate_pack("pk-1")
        engine.activate_pack("pk-2")
        engine.resolve_for_scope(PackScope.GLOBAL)
        assert len(engine.find_conflicts(scope=PackScope.GLOBAL)) >= 1
        assert len(engine.find_conflicts(scope=PackScope.GOAL)) == 0


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------


class TestRetrievalHelpers:
    def test_get_extraction_rules_for_pack(self):
        engine = _make_engine_with_pack()
        engine.add_extraction_rule(DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            created_at=NOW,
        ))
        rules = engine.get_extraction_rules_for_pack("pk-1")
        assert len(rules) == 1

    def test_get_routing_rules_for_pack(self):
        engine = _make_engine_with_pack()
        engine.add_routing_rule(DomainRoutingRule(
            rule_id="rr-1", pack_id="pk-1",
            target_role="ops", created_at=NOW,
        ))
        rules = engine.get_routing_rules_for_pack("pk-1")
        assert len(rules) == 1


# ---------------------------------------------------------------------------
# State hash
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_deterministic(self):
        e1 = DomainPackEngine()
        e2 = DomainPackEngine()
        assert e1.state_hash() == e2.state_hash()

    def test_changes_on_register(self):
        engine = DomainPackEngine()
        h1 = engine.state_hash()
        engine.register_pack(_make_pack())
        h2 = engine.state_hash()
        assert h1 != h2

    def test_length(self):
        engine = DomainPackEngine()
        assert len(engine.state_hash()) == 64
