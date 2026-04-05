"""Golden scenario tests for domain pack subsystem.

7 scenarios covering end-to-end domain pack flows.
"""

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
from mcoi_runtime.core.domain_pack_integration import DomainPackIntegration
from mcoi_runtime.core.domain_packs_builtin import (
    register_all_builtin_packs,
    register_internal_ops_pack,
    register_software_delivery_pack,
    register_support_pack,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
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


# ---------------------------------------------------------------------------
# Scenario 1: software-delivery pack changes extraction of "deploy by 5pm"
#              into deployment obligation
# ---------------------------------------------------------------------------


class TestGolden1SoftwareDeliveryExtraction:
    def test_deploy_extraction_rules_from_pack(self):
        pe, es, me, integ = _build()
        register_software_delivery_pack(pe, activate=True)

        # Apply extraction rules
        result = integ.apply_to_commitment_extraction(PackScope.GLOBAL)

        # Extraction rules include deploy pattern
        rules = result["extraction_rules"]
        assert len(rules) >= 1
        deploy_rules = [r for r in rules if "deploy" in r.pattern]
        assert len(deploy_rules) >= 1

        # Vocabulary includes deploy
        vocab = result["vocabulary"]
        deploy_vocab = [v for v in vocab if v.term == "deploy"]
        assert len(deploy_vocab) >= 1
        assert deploy_vocab[0].canonical_form == "deployment"

        # Event emitted
        assert result["event"].payload["action"] == "domain_pack_extraction_applied"
        assert result["event"].payload["rule_count"] >= 6


# ---------------------------------------------------------------------------
# Scenario 2: support pack routes urgent issue to support escalation chain
# ---------------------------------------------------------------------------


class TestGolden2SupportEscalationRouting:
    def test_support_escalation_chain(self):
        pe, es, me, integ = _build()
        register_support_pack(pe, activate=True)

        # Apply contact routing
        result = integ.apply_to_contact_routing(PackScope.GLOBAL)

        # Routing rules include support queue
        rules = result["routing_rules"]
        support_routes = [r for r in rules if "support" in r.target_role
                         or "escalation" in r.target_role]
        assert len(support_routes) >= 1

        # Escalation profile exists
        assert result["escalation_profile"] is not None
        assert "support-lead" in result["escalation_profile"].escalation_roles

        # Event emitted
        assert result["event"].payload["has_escalation_profile"] is True


# ---------------------------------------------------------------------------
# Scenario 3: internal-ops pack requires approval where software pack
#              would only notify
# ---------------------------------------------------------------------------


class TestGolden3InternalOpsRequiresApproval:
    def test_internal_ops_governance_requires_approval(self):
        pe, es, me, integ = _build()
        register_internal_ops_pack(pe, activate=True)
        register_software_delivery_pack(pe, activate=True)

        # Internal ops governance rules
        ops_result = integ.apply_to_governance(PackScope.GLOBAL)
        ops_gov_rules = ops_result["governance_rules"]

        # Internal ops has approval rules
        approval_rules = [r for r in ops_gov_rules if r.commitment_type == "approval"]
        assert len(approval_rules) >= 1

        # Software delivery extraction rules — no approval-specific governance
        sw_rules = pe.get_extraction_rules_for_pack("pack-software-delivery")
        sw_approval_governance = [r for r in sw_rules if r.commitment_type == "approval"]
        # Software delivery pack doesn't have approval governance rules
        assert len(sw_approval_governance) == 0


# ---------------------------------------------------------------------------
# Scenario 4: two packs conflict on same scope and conflict is surfaced
#              deterministically
# ---------------------------------------------------------------------------


class TestGolden4TwoPacksConflict:
    def test_same_domain_conflict_surfaced(self):
        pe, es, me, integ = _build()

        # Register two packs with same domain_name
        pe.register_pack(DomainPackDescriptor(
            pack_id="pk-conflict-a", domain_name="shared-domain",
            version="1.0.0", scope=PackScope.GLOBAL, created_at=NOW,
        ))
        pe.register_pack(DomainPackDescriptor(
            pack_id="pk-conflict-b", domain_name="shared-domain",
            version="2.0.0", scope=PackScope.GLOBAL, created_at=NOW,
        ))
        pe.activate_pack("pk-conflict-a")
        pe.activate_pack("pk-conflict-b")

        # Resolve — should surface conflict
        resolution = pe.resolve_for_scope(PackScope.GLOBAL)
        assert len(resolution.conflict_ids) >= 1

        # Conflict is recorded
        conflicts = pe.find_conflicts()
        assert len(conflicts) >= 1
        conflict = conflicts[0]
        # Pack IDs are sorted for determinism
        assert conflict.pack_id_a < conflict.pack_id_b

        # Both packs still appear in resolution (conflict is surfaced, not hidden)
        assert "pk-conflict-a" in resolution.resolved_pack_ids
        assert "pk-conflict-b" in resolution.resolved_pack_ids


# ---------------------------------------------------------------------------
# Scenario 5: team-scoped pack overrides global pack cleanly
# ---------------------------------------------------------------------------


class TestGolden5TeamScopeOverridesGlobal:
    def test_team_scope_takes_precedence(self):
        pe, es, me, integ = _build()

        # Global pack with low-priority simulation
        pe.register_pack(DomainPackDescriptor(
            pack_id="pk-global", domain_name="delivery",
            version="1.0.0", scope=PackScope.GLOBAL, created_at=NOW,
        ))
        pe.activate_pack("pk-global")
        pe.add_simulation_profile(DomainSimulationProfile(
            profile_id="sim-global", pack_id="pk-global",
            risk_weights={"deploy": 0.3},
            default_risk_level="low",
            created_at=NOW,
        ))

        # Team-scoped pack with high-priority simulation
        pe.register_pack(DomainPackDescriptor(
            pack_id="pk-team", domain_name="delivery-team",
            version="1.0.0", scope=PackScope.TEAM,
            scope_ref_id="team-alpha", created_at=NOW,
        ))
        pe.activate_pack("pk-team")
        pe.add_simulation_profile(DomainSimulationProfile(
            profile_id="sim-team", pack_id="pk-team",
            risk_weights={"deploy": 0.9},
            default_risk_level="high",
            created_at=NOW,
        ))

        # Resolve at team scope — team profile should win
        profile = pe.resolve_simulation_profile(PackScope.TEAM, "team-alpha")
        assert profile is not None
        assert profile.profile_id == "sim-team"
        assert profile.default_risk_level == "high"
        assert profile.risk_weights["deploy"] == 0.9


# ---------------------------------------------------------------------------
# Scenario 6: deprecated pack stops affecting runtime resolution
# ---------------------------------------------------------------------------


class TestGolden6DeprecatedPackExcluded:
    def test_deprecated_pack_not_in_resolution(self):
        pe, es, me, integ = _build()
        register_software_delivery_pack(pe, activate=True)

        # Verify it resolves initially
        rules_before = pe.resolve_extraction_rules(PackScope.GLOBAL)
        assert len(rules_before) >= 6

        # Deprecate the pack
        pe.deprecate_pack("pack-software-delivery")
        assert pe.get_pack("pack-software-delivery").status == DomainPackStatus.DEPRECATED

        # Resolve again — deprecated pack should be excluded
        rules_after = pe.resolve_extraction_rules(PackScope.GLOBAL)
        assert len(rules_after) == 0

        # Active pack count dropped
        assert pe.active_pack_count == 0


# ---------------------------------------------------------------------------
# Scenario 7: benchmark profile changes adversarial suite selection by domain
# ---------------------------------------------------------------------------


class TestGolden7BenchmarkProfileByDomain:
    def test_domain_specific_benchmark_suite(self):
        pe, es, me, integ = _build()

        # Register support pack with benchmark profile
        register_support_pack(pe, activate=True)

        # Apply benchmarking
        result = integ.apply_to_benchmarking(PackScope.GLOBAL)
        profile = result["benchmark_profile"]
        assert profile is not None

        # Support-specific suites
        assert "response-time" in profile.suite_ids
        assert "resolution-quality" in profile.suite_ids

        # Support-specific adversarial categories
        assert "ambiguous-severity" in profile.adversarial_categories
        assert "sla-edge-cases" in profile.adversarial_categories

        # Thresholds are domain-specific
        assert profile.pass_thresholds["response_time_p95"] == 0.95
        assert profile.pass_thresholds["resolution_rate"] == 0.85

        # Event records the benchmark application
        assert result["event"].payload["suite_count"] == 2
        assert result["event"].payload["adversarial_count"] == 2


# ---------------------------------------------------------------------------
# Bonus: all 3 builtin packs register and activate cleanly
# ---------------------------------------------------------------------------


class TestBuiltinPacks:
    def test_register_all(self):
        pe = DomainPackEngine()
        packs = register_all_builtin_packs(pe)
        assert len(packs) == 3
        assert pe.pack_count == 3
        # All still DRAFT
        assert pe.active_pack_count == 0

    def test_register_all_and_activate(self):
        pe = DomainPackEngine()
        packs = register_all_builtin_packs(pe, activate=True)
        assert pe.active_pack_count == 3

    def test_software_delivery_has_rules(self):
        pe = DomainPackEngine()
        register_software_delivery_pack(pe, activate=True)
        assert pe.extraction_rule_count == 6
        assert pe.routing_rule_count == 4

    def test_support_has_rules(self):
        pe = DomainPackEngine()
        register_support_pack(pe, activate=True)
        assert pe.extraction_rule_count == 4
        assert pe.routing_rule_count == 2

    def test_internal_ops_has_rules(self):
        pe = DomainPackEngine()
        register_internal_ops_pack(pe, activate=True)
        # 4 base + 2 governance = 6
        assert pe.extraction_rule_count == 6
        assert pe.routing_rule_count == 4


class TestBuiltinDescriptionsAreBounded:
    def test_software_delivery_descriptions_redact_rule_values(self):
        pe = DomainPackEngine()
        register_software_delivery_pack(pe, activate=True)
        extraction_rules = pe.get_extraction_rules_for_pack("pack-software-delivery")
        routing_rules = pe.get_routing_rules_for_pack("pack-software-delivery")

        assert all(rule.description == "Software delivery extraction rule" for rule in extraction_rules)
        assert all(route.description == "Software delivery routing rule" for route in routing_rules)
        assert all("developer" not in route.description.lower() for route in routing_rules)
        assert all("ops" not in route.description.lower() for route in routing_rules)

    def test_support_descriptions_redact_rule_values(self):
        pe = DomainPackEngine()
        register_support_pack(pe, activate=True)
        extraction_rules = pe.get_extraction_rules_for_pack("pack-support-ticketing")
        routing_rules = pe.get_routing_rules_for_pack("pack-support-ticketing")
        memory_rules = pe.resolve_memory_rules(PackScope.GLOBAL)

        assert all(rule.description == "Support extraction rule" for rule in extraction_rules)
        assert all(route.description == "Support routing rule" for route in routing_rules)
        assert all(rule.description == "Support memory rule" for rule in memory_rules)
        assert all("customer" not in route.description.lower() for route in routing_rules)
        assert all("support-queue" not in route.description.lower() for route in routing_rules)

    def test_internal_ops_descriptions_redact_rule_values(self):
        pe = DomainPackEngine()
        register_internal_ops_pack(pe, activate=True)
        extraction_rules = pe.get_extraction_rules_for_pack("pack-internal-ops")
        routing_rules = pe.get_routing_rules_for_pack("pack-internal-ops")

        base_extraction_rules = [rule for rule in extraction_rules if rule.rule_id.startswith("iop-extr-") and not rule.rule_id.startswith("iop-extr-gov")]
        assert all(rule.description == "Internal ops extraction rule" for rule in base_extraction_rules)
        assert all(route.description == "Internal ops routing rule" for route in routing_rules)
        assert all("employee" not in route.description.lower() for route in routing_rules)
        assert all("manager" not in route.description.lower() for route in routing_rules)
