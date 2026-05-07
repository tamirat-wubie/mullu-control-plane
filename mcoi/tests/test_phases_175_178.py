"""Tests for Phases 175-178."""
import pytest

from mcoi_runtime.pilot.engine_adoption import (
    ENGINE_ADOPTION_TIERS,
    AdoptionTracker,
    REGIONAL_ONBOARDING_PLANS,
    RegionalPartnerOnboardingPlan,
    InternationalPartnerPipeline,
)
from mcoi_runtime.pilot.advanced_autonomy import (
    SWARM_CONFIGS,
    SwarmConfig,
    SwarmAction,
    AgentSwarmOrchestrator,
    GOVERNANCE_PROPERTIES,
    GovernanceProof,
    GovernanceVerifier,
)


# ── Phase 175 — EngineBase Adoption ──

class TestEngineAdoptionTiers:
    def test_all_tiers_present(self):
        assert set(ENGINE_ADOPTION_TIERS.keys()) == {"tier_1_critical", "tier_2_important", "tier_3_standard", "tier_4_foundational"}

    def test_tier_1_contains_critical_engines(self):
        t1 = ENGINE_ADOPTION_TIERS["tier_1_critical"]
        for engine in ("billing_runtime", "settlement_runtime", "constitutional_governance"):
            assert engine in t1

    def test_no_duplicate_engines_across_tiers(self):
        all_engines = [e for tier in ENGINE_ADOPTION_TIERS.values() for e in tier]
        assert len(all_engines) == len(set(all_engines))


class TestAdoptionTracker:
    def test_adopt_and_summary(self):
        t = AdoptionTracker()
        t.add_pending("billing_runtime")
        t.add_pending("llm_runtime")
        assert t.adoption_rate == 0.0
        t.adopt("billing_runtime")
        assert t.adoption_rate == 0.5
        s = t.summary()
        assert s["adopted"] == 1 and s["pending"] == 1

    def test_adopt_removes_from_pending(self):
        t = AdoptionTracker()
        t.add_pending("x")
        t.adopt("x")
        assert "x" not in t.pending and "x" in t.adopted

    def test_empty_tracker_rate_zero(self):
        assert AdoptionTracker().adoption_rate == 0.0


# ── Phase 176 — International Partner Onboarding ──

class TestRegionalOnboardingPlans:
    def test_all_regions_defined(self):
        assert set(REGIONAL_ONBOARDING_PLANS.keys()) == {"us", "eu", "uk", "sg", "ae"}

    def test_eu_requires_local_support(self):
        assert REGIONAL_ONBOARDING_PLANS["eu"].local_support_required is True

    def test_us_no_local_support(self):
        assert REGIONAL_ONBOARDING_PLANS["us"].local_support_required is False


class TestInternationalPartnerPipeline:
    def test_add_and_onboard(self):
        p = InternationalPartnerPipeline()
        p.add_partner_prospect("eu", "Acme", "consulting")
        p.add_partner_prospect("eu", "Beta", "integration")
        p.onboard_partner("eu", "Acme")
        assert p.onboarded_count() == 1
        assert p.by_region() == {"eu": 2}

    def test_summary(self):
        p = InternationalPartnerPipeline()
        p.add_partner_prospect("us", "X", "cap")
        s = p.summary()
        assert s["regions"] == 1 and s["total_prospects"] == 1 and s["onboarded"] == 0


# ── Phase 177 — Agent Swarm ──

class TestAgentSwarmOrchestrator:
    def test_register_and_cap(self):
        orch = AgentSwarmOrchestrator(SWARM_CONFIGS["conservative"])
        assert orch.register_agent("a1")
        assert orch.register_agent("a2")
        assert orch.register_agent("a3")
        assert not orch.register_agent("a4")  # cap = 3

    def test_propose_approve_deny(self):
        orch = AgentSwarmOrchestrator(SWARM_CONFIGS["standard"])
        orch.register_agent("a1")
        act = orch.propose_action("act1", "a1", "target_x")
        assert act.status == "proposed"
        orch.approve_and_execute("act1")
        assert act.status == "completed"
        act2 = orch.propose_action("act2", "a1", "target_y")
        orch.deny_action("act2")
        assert act2.status == "denied"

    def test_unknown_agent_raises(self):
        orch = AgentSwarmOrchestrator(SWARM_CONFIGS["standard"])
        with pytest.raises(ValueError) as exc_info:
            orch.propose_action("x", "ghost", "t")
        message = str(exc_info.value)
        assert message == "unknown agent"
        assert "ghost" not in message

    def test_unknown_action_message_is_bounded(self):
        orch = AgentSwarmOrchestrator(SWARM_CONFIGS["standard"])
        orch.register_agent("a1")
        with pytest.raises(ValueError) as exc_info:
            orch.approve_and_execute("act-secret")
        message = str(exc_info.value)
        assert message == "unknown action"
        assert "act-secret" not in message

    def test_summary(self):
        orch = AgentSwarmOrchestrator(SWARM_CONFIGS["advanced"])
        orch.register_agent("a1")
        orch.propose_action("a1_act", "a1", "t")
        orch.approve_and_execute("a1_act")
        s = orch.summary()
        assert s["agents"] == 1 and s["completed"] == 1 and s["config"] == "peer"


# ── Phase 178 — Formal Governance Verification ──

class TestGovernanceVerifier:
    def test_verify_all(self):
        v = GovernanceVerifier()
        proofs = v.verify_all()
        assert len(proofs) == len(GOVERNANCE_PROPERTIES)
        assert v.all_proven

    def test_single_verify(self):
        v = GovernanceVerifier()
        p = v.verify_property("p0", GOVERNANCE_PROPERTIES[0])
        assert p.proven and p.method == "invariant_check"

    def test_summary(self):
        v = GovernanceVerifier()
        v.verify_all()
        s = v.summary()
        assert s["total_proofs"] == 8 and s["all_proven"] and s["properties_defined"] == 8
