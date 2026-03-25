"""Phase 152 — Sovereign / Public-Sector Market Entry Tests."""
import pytest
from mcoi_runtime.pilot.sovereign_market import (
    SovereignTargetAccount, SovereignTargetEngine,
    PROCUREMENT_PACKAGE,
    SovereignPartnerProfile, SOVEREIGN_PARTNER_REQUIREMENTS,
    SovereignReferenceAccount, SovereignReferenceProgram,
    SOVEREIGN_PILOT_MOTION,
    golden_proof_sovereign_market,
)


class TestTargetEngine:
    def test_composite_score_range(self):
        a = SovereignTargetAccount("a1", "Agency A", "civilian", 8, 7, 6, 3, 9, 8)
        assert 0 <= a.composite_score <= 10

    def test_tier_assignment(self):
        high = SovereignTargetAccount("a1", "A", "defense", 9, 9, 9, 1, 9, 9)
        low = SovereignTargetAccount("a2", "B", "civilian", 2, 2, 2, 9, 2, 2)
        assert high.tier == "tier_1"
        assert low.tier == "tier_3"

    def test_engine_rank_order(self):
        eng = SovereignTargetEngine()
        a1 = SovereignTargetAccount("a1", "A", "defense", 9, 9, 9, 1, 9, 9)
        a2 = SovereignTargetAccount("a2", "B", "civilian", 3, 3, 3, 8, 3, 3)
        eng.add_account(a2)
        eng.add_account(a1)
        ranked = eng.rank()
        assert ranked[0].account_id == "a1"

    def test_by_sector(self):
        eng = SovereignTargetEngine()
        eng.add_account(SovereignTargetAccount("a1", "A", "defense"))
        eng.add_account(SovereignTargetAccount("a2", "B", "health"))
        eng.add_account(SovereignTargetAccount("a3", "C", "defense"))
        assert len(eng.by_sector("defense")) == 2

    def test_tier_1_filter(self):
        eng = SovereignTargetEngine()
        eng.add_account(SovereignTargetAccount("a1", "A", "defense", 9, 9, 9, 1, 9, 9))
        eng.add_account(SovereignTargetAccount("a2", "B", "civilian", 1, 1, 1, 9, 1, 1))
        assert len(eng.tier_1_accounts()) == 1


class TestProcurement:
    def test_8_artifacts(self):
        assert len(PROCUREMENT_PACKAGE) == 8

    def test_each_has_title_and_sections(self):
        for key, artifact in PROCUREMENT_PACKAGE.items():
            assert artifact["title"], f"{key} missing title"
            assert len(artifact["sections"]) >= 4, f"{key} has fewer than 4 sections"

    def test_required_artifacts_present(self):
        required = ("security_matrix", "residency_statement", "audit_package", "pilot_checklist")
        for name in required:
            assert name in PROCUREMENT_PACKAGE


class TestPartner:
    def test_can_deploy_restricted(self):
        p = SovereignPartnerProfile("p1", "GovCo", True, "secret", ("sovereign_cloud", "on_prem"))
        assert p.can_deploy_restricted

    def test_cannot_deploy_restricted_without_clearance(self):
        p = SovereignPartnerProfile("p2", "SmallCo", True, "confidential", ("sovereign_cloud",))
        assert not p.can_deploy_restricted

    def test_3_partner_tiers(self):
        assert len(SOVEREIGN_PARTNER_REQUIREMENTS) == 3
        assert "basic_sovereign" in SOVEREIGN_PARTNER_REQUIREMENTS
        assert "strategic_sovereign" in SOVEREIGN_PARTNER_REQUIREMENTS


class TestReference:
    def test_maturity_champion(self):
        a = SovereignReferenceAccount("r1", "Agency", "defense", "sov-cloud", "trust-std", rollout_milestones=6, reference_ready=True)
        assert a.maturity == "champion"

    def test_maturity_early(self):
        a = SovereignReferenceAccount("r2", "Agency", "civilian", "sov-cloud", "trust-std")
        assert a.maturity == "early"

    def test_program_summary(self):
        prog = SovereignReferenceProgram()
        prog.add_account(SovereignReferenceAccount("r1", "A", "defense", "p1", "t1", rollout_milestones=6, time_to_approval_days=30, reference_ready=True))
        prog.add_account(SovereignReferenceAccount("r2", "B", "health", "p1", "t1", rollout_milestones=2, time_to_approval_days=60))
        s = prog.summary()
        assert s["total_accounts"] == 2
        assert s["reference_ready"] == 1
        assert s["champions"] == 1
        assert s["avg_approval_days"] == 45


class TestPilotMotion:
    def test_8_steps(self):
        assert len(SOVEREIGN_PILOT_MOTION) == 8

    def test_step_names(self):
        names = tuple(s["name"] for s in SOVEREIGN_PILOT_MOTION)
        assert names == ("qualify", "profile", "package", "deploy", "validate", "workflow", "metrics", "promote")

    def test_all_have_description(self):
        for step in SOVEREIGN_PILOT_MOTION:
            assert step["description"]
            assert step["step"] >= 1


class TestGoldenProof:
    def test_golden_proof_passes(self):
        result = golden_proof_sovereign_market()
        assert result["status"] == "PASS"

    def test_golden_proof_subsections(self):
        result = golden_proof_sovereign_market()
        assert len(result["subsections"]) == 6
        assert "152A" in result["subsections"]
        assert "152F" in result["subsections"]
