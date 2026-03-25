"""Contract-level tests for domain_pack contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.domain_pack import (
    DomainBenchmarkProfile,
    DomainEscalationProfile,
    DomainExtractionRule,
    DomainMemoryRule,
    DomainPackActivation,
    DomainPackConflict,
    DomainPackDescriptor,
    DomainPackResolution,
    DomainPackStatus,
    DomainRoutingRule,
    DomainRuleKind,
    DomainSimulationProfile,
    DomainUtilityProfile,
    DomainVocabularyEntry,
    PackScope,
    scope_specificity,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_domain_pack_status_count(self):
        assert len(DomainPackStatus) == 4

    def test_domain_rule_kind_count(self):
        assert len(DomainRuleKind) == 10

    def test_pack_scope_count(self):
        assert len(PackScope) == 6

    def test_scope_specificity_order(self):
        assert scope_specificity(PackScope.GLOBAL) < scope_specificity(PackScope.DOMAIN)
        assert scope_specificity(PackScope.DOMAIN) < scope_specificity(PackScope.FUNCTION)
        assert scope_specificity(PackScope.FUNCTION) < scope_specificity(PackScope.TEAM)
        assert scope_specificity(PackScope.TEAM) < scope_specificity(PackScope.WORKFLOW)
        assert scope_specificity(PackScope.WORKFLOW) < scope_specificity(PackScope.GOAL)


# ---------------------------------------------------------------------------
# DomainPackDescriptor
# ---------------------------------------------------------------------------


class TestDomainPackDescriptor:
    def _make(self, **kw):
        defaults = dict(
            pack_id="pk-1",
            domain_name="test-domain",
            version="1.0.0",
            status=DomainPackStatus.DRAFT,
            scope=PackScope.GLOBAL,
            created_at=NOW,
        )
        defaults.update(kw)
        return DomainPackDescriptor(**defaults)

    def test_valid(self):
        d = self._make()
        assert d.pack_id == "pk-1"
        assert d.status == DomainPackStatus.DRAFT

    def test_empty_pack_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(pack_id="")

    def test_empty_domain_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(domain_name="")

    def test_empty_version_rejected(self):
        with pytest.raises(ValueError):
            self._make(version="")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            self._make(status="flying")

    def test_invalid_scope(self):
        with pytest.raises(ValueError):
            self._make(scope="cosmic")

    def test_tags_frozen(self):
        d = self._make(tags=["a", "b"])
        assert d.tags == ("a", "b")

    def test_metadata_frozen(self):
        d = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            d.metadata["new"] = "val"

    def test_frozen(self):
        d = self._make()
        with pytest.raises(AttributeError):
            d.pack_id = "new"

    def test_all_statuses(self):
        for s in DomainPackStatus:
            d = self._make(status=s)
            assert d.status == s

    def test_all_scopes(self):
        for s in PackScope:
            d = self._make(scope=s)
            assert d.scope == s

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["status"] == "draft"
        assert d["scope"] == "global"

    def test_updated_at_validated(self):
        d = self._make(updated_at=NOW)
        assert d.updated_at == NOW

    def test_updated_at_invalid(self):
        with pytest.raises(ValueError):
            self._make(updated_at="not-a-date")


# ---------------------------------------------------------------------------
# DomainVocabularyEntry
# ---------------------------------------------------------------------------


class TestDomainVocabularyEntry:
    def test_valid(self):
        e = DomainVocabularyEntry(
            entry_id="v-1", pack_id="pk-1",
            term="deploy", canonical_form="deployment",
            created_at=NOW,
        )
        assert e.canonical_form == "deployment"

    def test_empty_term_rejected(self):
        with pytest.raises(ValueError):
            DomainVocabularyEntry(
                entry_id="v-bad", pack_id="pk-1",
                term="", canonical_form="deployment",
                created_at=NOW,
            )

    def test_aliases_frozen(self):
        e = DomainVocabularyEntry(
            entry_id="v-2", pack_id="pk-1",
            term="deploy", canonical_form="deployment",
            aliases=["push", "ship"],
            created_at=NOW,
        )
        assert e.aliases == ("push", "ship")


# ---------------------------------------------------------------------------
# DomainExtractionRule
# ---------------------------------------------------------------------------


class TestDomainExtractionRule:
    def test_valid(self):
        r = DomainExtractionRule(
            rule_id="r-1", pack_id="pk-1",
            pattern=r"\bdeploy\b", commitment_type="delivery",
            priority=10, created_at=NOW,
        )
        assert r.priority == 10

    def test_empty_pattern_rejected(self):
        with pytest.raises(ValueError):
            DomainExtractionRule(
                rule_id="r-bad", pack_id="pk-1",
                pattern="", commitment_type="delivery",
                created_at=NOW,
            )

    def test_negative_priority_rejected(self):
        with pytest.raises(ValueError):
            DomainExtractionRule(
                rule_id="r-bad", pack_id="pk-1",
                pattern=r"\bdeploy\b", commitment_type="delivery",
                priority=-1, created_at=NOW,
            )


# ---------------------------------------------------------------------------
# DomainRoutingRule
# ---------------------------------------------------------------------------


class TestDomainRoutingRule:
    def test_valid(self):
        r = DomainRoutingRule(
            rule_id="rr-1", pack_id="pk-1",
            target_role="ops", priority=5,
            created_at=NOW,
        )
        assert r.target_role == "ops"

    def test_empty_target_rejected(self):
        with pytest.raises(ValueError):
            DomainRoutingRule(
                rule_id="rr-bad", pack_id="pk-1",
                target_role="", created_at=NOW,
            )


# ---------------------------------------------------------------------------
# DomainMemoryRule
# ---------------------------------------------------------------------------


class TestDomainMemoryRule:
    def test_valid(self):
        r = DomainMemoryRule(
            rule_id="mr-1", pack_id="pk-1",
            memory_type="observation", ttl_seconds=3600,
            created_at=NOW,
        )
        assert r.ttl_seconds == 3600

    def test_empty_memory_type_rejected(self):
        with pytest.raises(ValueError):
            DomainMemoryRule(
                rule_id="mr-bad", pack_id="pk-1",
                memory_type="", created_at=NOW,
            )


# ---------------------------------------------------------------------------
# DomainSimulationProfile
# ---------------------------------------------------------------------------


class TestDomainSimulationProfile:
    def test_valid(self):
        p = DomainSimulationProfile(
            profile_id="sp-1", pack_id="pk-1",
            risk_weights={"deploy": 0.8},
            created_at=NOW,
        )
        assert p.risk_weights["deploy"] == 0.8

    def test_risk_weights_frozen(self):
        p = DomainSimulationProfile(
            profile_id="sp-2", pack_id="pk-1",
            risk_weights={"deploy": 0.8},
            created_at=NOW,
        )
        with pytest.raises(TypeError):
            p.risk_weights["new"] = 0.5

    def test_scenario_templates_frozen(self):
        p = DomainSimulationProfile(
            profile_id="sp-3", pack_id="pk-1",
            scenario_templates=["a", "b"],
            created_at=NOW,
        )
        assert p.scenario_templates == ("a", "b")


# ---------------------------------------------------------------------------
# DomainUtilityProfile
# ---------------------------------------------------------------------------


class TestDomainUtilityProfile:
    def test_valid(self):
        p = DomainUtilityProfile(
            profile_id="up-1", pack_id="pk-1",
            bias_weights={"speed": 0.4, "safety": 0.6},
            created_at=NOW,
        )
        assert p.default_tradeoff_direction == "balanced"

    def test_bias_weights_frozen(self):
        p = DomainUtilityProfile(
            profile_id="up-2", pack_id="pk-1",
            bias_weights={"speed": 0.4},
            created_at=NOW,
        )
        with pytest.raises(TypeError):
            p.bias_weights["new"] = 0.5


# ---------------------------------------------------------------------------
# DomainBenchmarkProfile
# ---------------------------------------------------------------------------


class TestDomainBenchmarkProfile:
    def test_valid(self):
        p = DomainBenchmarkProfile(
            profile_id="bp-1", pack_id="pk-1",
            suite_ids=("s1", "s2"),
            adversarial_categories=("cat1",),
            pass_thresholds={"p95": 0.95},
            created_at=NOW,
        )
        assert len(p.suite_ids) == 2

    def test_pass_thresholds_frozen(self):
        p = DomainBenchmarkProfile(
            profile_id="bp-2", pack_id="pk-1",
            pass_thresholds={"p95": 0.95},
            created_at=NOW,
        )
        with pytest.raises(TypeError):
            p.pass_thresholds["new"] = 0.5


# ---------------------------------------------------------------------------
# DomainEscalationProfile
# ---------------------------------------------------------------------------


class TestDomainEscalationProfile:
    def test_valid(self):
        p = DomainEscalationProfile(
            profile_id="ep-1", pack_id="pk-1",
            escalation_roles=("oncall", "lead"),
            timeout_seconds=300,
            created_at=NOW,
        )
        assert len(p.escalation_roles) == 2

    def test_empty_roles_rejected(self):
        with pytest.raises(ValueError):
            DomainEscalationProfile(
                profile_id="ep-bad", pack_id="pk-1",
                escalation_roles=(),
                created_at=NOW,
            )

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValueError):
            DomainEscalationProfile(
                profile_id="ep-bad2", pack_id="pk-1",
                escalation_roles=("oncall",),
                timeout_seconds=0,
                created_at=NOW,
            )

    def test_frozen(self):
        p = DomainEscalationProfile(
            profile_id="ep-3", pack_id="pk-1",
            escalation_roles=("oncall",),
            created_at=NOW,
        )
        with pytest.raises(AttributeError):
            p.profile_id = "new"


# ---------------------------------------------------------------------------
# DomainPackActivation
# ---------------------------------------------------------------------------


class TestDomainPackActivation:
    def test_valid(self):
        a = DomainPackActivation(
            activation_id="act-1", pack_id="pk-1",
            previous_status=DomainPackStatus.DRAFT,
            new_status=DomainPackStatus.ACTIVE,
            activated_at=NOW,
        )
        assert a.new_status == DomainPackStatus.ACTIVE

    def test_empty_activation_id_rejected(self):
        with pytest.raises(ValueError):
            DomainPackActivation(
                activation_id="", pack_id="pk-1",
                activated_at=NOW,
            )


# ---------------------------------------------------------------------------
# DomainPackResolution
# ---------------------------------------------------------------------------


class TestDomainPackResolution:
    def test_valid(self):
        r = DomainPackResolution(
            resolution_id="res-1",
            resolved_pack_ids=("pk-1", "pk-2"),
            resolved_at=NOW,
        )
        assert len(r.resolved_pack_ids) == 2

    def test_empty_resolution_id_rejected(self):
        with pytest.raises(ValueError):
            DomainPackResolution(
                resolution_id="",
                resolved_at=NOW,
            )


# ---------------------------------------------------------------------------
# DomainPackConflict
# ---------------------------------------------------------------------------


class TestDomainPackConflict:
    def test_valid(self):
        c = DomainPackConflict(
            conflict_id="cf-1",
            pack_id_a="pk-1",
            pack_id_b="pk-2",
            detected_at=NOW,
        )
        assert c.pack_id_a == "pk-1"

    def test_same_pack_ids_rejected(self):
        with pytest.raises(ValueError):
            DomainPackConflict(
                conflict_id="cf-bad",
                pack_id_a="pk-1",
                pack_id_b="pk-1",
                detected_at=NOW,
            )

    def test_empty_pack_id_rejected(self):
        with pytest.raises(ValueError):
            DomainPackConflict(
                conflict_id="cf-bad2",
                pack_id_a="",
                pack_id_b="pk-2",
                detected_at=NOW,
            )
