"""Phase 154 — Sovereign Partner Scale-Out Tests."""
import pytest
from mcoi_runtime.pilot.sovereign_partners import (
    SOVEREIGN_PARTNER_TYPES, SovereignPartnerType,
    SOVEREIGN_CERTIFICATIONS, SovereignCertification,
    SOVEREIGN_DEPLOYMENT_PLAYBOOKS,
    SovereignPartnerRecord, SovereignPartnerReference, SovereignPartnerPipeline,
    SovereignPartnerEconomics, CLEARANCE_PREMIUM, DEPLOYMENT_PREMIUM,
    golden_proof_sovereign_partners,
)


# ---------------------------------------------------------------------------
# 154A — Partner Types
# ---------------------------------------------------------------------------
class TestSovereignPartnerTypes:
    def test_five_types(self):
        assert len(SOVEREIGN_PARTNER_TYPES) == 5

    def test_strategic_full_capability(self):
        s = SOVEREIGN_PARTNER_TYPES["strategic_sovereign"]
        assert s.can_sell
        assert s.can_deploy_sovereign
        assert s.can_support_sovereign
        assert s.clearance_required == "top_secret"

    def test_referral_no_deploy(self):
        r = SOVEREIGN_PARTNER_TYPES["referral_sovereign"]
        assert not r.can_deploy_sovereign
        assert not r.can_support_sovereign
        assert r.clearance_required == "none"


# ---------------------------------------------------------------------------
# 154B — Certifications
# ---------------------------------------------------------------------------
class TestSovereignCertifications:
    def test_five_levels(self):
        assert len(SOVEREIGN_CERTIFICATIONS) == 5

    def test_bundle_cert_has_sovereign_overlay(self):
        bc = SOVEREIGN_CERTIFICATIONS["sovereign_bundle_certified"]
        assert "sovereign_audit_export" in bc.sovereign_overlay
        assert len(bc.sovereign_overlay) >= 3

    def test_aware_is_entry_level(self):
        a = SOVEREIGN_CERTIFICATIONS["sovereign_aware"]
        assert "data_residency_training" in a.requirements


# ---------------------------------------------------------------------------
# 154C — Playbooks
# ---------------------------------------------------------------------------
class TestSovereignPlaybooks:
    def test_five_playbooks(self):
        assert len(SOVEREIGN_DEPLOYMENT_PLAYBOOKS) == 5

    def test_each_has_min_7_steps(self):
        for key, pb in SOVEREIGN_DEPLOYMENT_PLAYBOOKS.items():
            assert len(pb["steps"]) >= 7, f"{key} has fewer than 7 steps"

    def test_air_gapped_longest(self):
        ag = SOVEREIGN_DEPLOYMENT_PLAYBOOKS["air_gapped"]
        assert ag["estimated_days"] >= 45
        assert ag["partner_clearance_min"] == "top_secret"


# ---------------------------------------------------------------------------
# 154D — Pipeline & References
# ---------------------------------------------------------------------------
class TestSovereignPipeline:
    def test_onboard_and_certify(self):
        pipeline = SovereignPartnerPipeline()
        rec = SovereignPartnerRecord(
            "sp-001", "SecureGov LLC", "implementation_sovereign",
            "sovereign_demo_certified", "secret",
        )
        pipeline.onboard(rec)
        assert pipeline.partner_count == 1
        updated = pipeline.certify("sp-001", "sovereign_implementation_certified")
        assert updated.certification_level == "sovereign_implementation_certified"

    def test_duplicate_onboard_raises(self):
        pipeline = SovereignPartnerPipeline()
        rec = SovereignPartnerRecord(
            "sp-dup", "Dup Corp", "referral_sovereign",
            "sovereign_aware", "none",
        )
        pipeline.onboard(rec)
        with pytest.raises(ValueError):
            pipeline.onboard(rec)

    def test_reference_increments_count(self):
        pipeline = SovereignPartnerPipeline()
        rec = SovereignPartnerRecord(
            "sp-002", "RefCo", "managed_sovereign",
            "sovereign_support_certified", "secret", True, 7.0, 0,
        )
        pipeline.onboard(rec)
        ref = SovereignPartnerReference(
            "ref-100", "sp-002", "Agency X", "defense", "restricted_network", True,
        )
        pipeline.add_reference(ref)
        assert pipeline.get_partner("sp-002").references_delivered == 1
        assert len(pipeline.references_for_partner("sp-002")) == 1

    def test_gold_status(self):
        pipeline = SovereignPartnerPipeline()
        rec = SovereignPartnerRecord(
            "sp-gold", "GoldCo", "strategic_sovereign",
            "sovereign_bundle_certified", "top_secret", True, 9.0,
        )
        pipeline.onboard(rec)
        assert len(pipeline.gold_partners()) == 1


# ---------------------------------------------------------------------------
# 154E — Economics
# ---------------------------------------------------------------------------
class TestSovereignEconomics:
    def test_basic_payout(self):
        econ = SovereignPartnerEconomics("sp-e1", "managed_sovereign", "secret")
        payout = econ.record_deal(100_000, "sovereign_cloud", closed=True)
        expected = round(100_000 * 0.40 * 1.30 * 1.0, 2)
        assert payout == expected
        assert econ.deals_closed == 1

    def test_no_payout_when_not_closed(self):
        econ = SovereignPartnerEconomics("sp-e2", "reseller_sovereign", "confidential")
        payout = econ.record_deal(50_000, "on_prem", closed=False)
        assert payout == 0.0
        assert econ.deals_sourced == 1
        assert econ.deals_closed == 0

    def test_premium_stacking(self):
        econ = SovereignPartnerEconomics("sp-e3", "strategic_sovereign", "top_secret")
        payout = econ.record_deal(200_000, "air_gapped", closed=True)
        expected = round(200_000 * 0.35 * 1.50 * 1.50, 2)
        assert payout == expected
        assert econ.partner_earnings == payout

    def test_close_rate(self):
        econ = SovereignPartnerEconomics("sp-e4", "implementation_sovereign", "secret")
        econ.record_deal(10_000, "sovereign_cloud", closed=True)
        econ.record_deal(10_000, "sovereign_cloud", closed=False)
        assert econ.close_rate == 0.5


# ---------------------------------------------------------------------------
# 154F — Golden Proof
# ---------------------------------------------------------------------------
class TestGoldenProof:
    def test_golden_proof_passes(self):
        result = golden_proof_sovereign_partners()
        assert result["status"] == "PASS"
        assert len(result["steps"]) == 6
        assert result["subsections"] == ("154A", "154B", "154C", "154D", "154E", "154F")
