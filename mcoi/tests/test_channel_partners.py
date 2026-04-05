"""Phase 145 — Channel / Partner Distribution Tests."""
import pytest
from mcoi_runtime.pilot.channel_partners import (
    PARTNER_TYPES, ENABLEMENT_ASSETS, CERTIFICATIONS,
    PartnerEngine, PartnerRecord, PartnerEconomics,
)

class TestPartnerTypes:
    def test_5_types(self):
        assert len(PARTNER_TYPES) == 5

    def test_revenue_shares(self):
        assert PARTNER_TYPES["referral"].revenue_share_pct == 10.0
        assert PARTNER_TYPES["managed_service"].revenue_share_pct == 40.0

    def test_capabilities(self):
        assert not PARTNER_TYPES["referral"].can_sell
        assert PARTNER_TYPES["reseller"].can_sell
        assert PARTNER_TYPES["implementation"].can_deploy
        assert PARTNER_TYPES["managed_service"].can_support

class TestEnablement:
    def test_8_assets(self):
        assert len(ENABLEMENT_ASSETS) == 8

class TestCertification:
    def test_4_levels(self):
        assert len(CERTIFICATIONS) == 4

    def test_progressive(self):
        assert "demo_certified" in CERTIFICATIONS["implementation_certified"].requirements

class TestPartnerEngine:
    def test_onboard(self):
        engine = PartnerEngine()
        p = engine.onboard_partner("p1", "Acme Consulting", "implementation", "demo_certified")
        assert p.company_name == "Acme Consulting"
        assert engine.partner_count == 1

    def test_certify(self):
        engine = PartnerEngine()
        engine.onboard_partner("p1", "Acme", "implementation")
        p = engine.certify_partner("p1", "implementation_certified")
        assert p.certification_level == "implementation_certified"

    def test_deal_tracking(self):
        engine = PartnerEngine()
        engine.onboard_partner("p1", "Acme", "reseller")
        econ = engine.record_deal("p1", 2500.0, closed=True)
        assert econ.deals_sourced == 1
        assert econ.deals_closed == 1
        assert econ.referral_fees_earned == 500.0  # 20% of 2500

    def test_quality_tiers(self):
        engine = PartnerEngine()
        engine.onboard_partner("p1", "Gold Co", "implementation")
        engine.update_quality("p1", 9.0)
        assert engine._partners["p1"].status == "gold"

        engine.onboard_partner("p2", "Prob Co", "referral")
        engine.update_quality("p2", 2.0)
        assert engine._partners["p2"].status == "probation"

    def test_dashboard(self):
        engine = PartnerEngine()
        engine.onboard_partner("p1", "A", "reseller")
        engine.onboard_partner("p2", "B", "implementation")
        engine.record_deal("p1", 5000.0, True)
        engine.update_quality("p1", 8.5)
        d = engine.dashboard()
        assert d["total_partners"] == 2
        assert d["gold"] == 1
        assert d["total_revenue_influenced"] == 5000.0

    def test_duplicate_onboard_message_is_bounded(self):
        engine = PartnerEngine()
        engine.onboard_partner("partner-secret", "Acme Secret", "implementation")
        with pytest.raises(ValueError) as exc_info:
            engine.onboard_partner("partner-secret", "Acme Secret", "implementation")
        message = str(exc_info.value)
        assert message == "partner already exists"
        assert "partner-secret" not in message
        assert "Acme Secret" not in message

    def test_unknown_partner_message_is_bounded(self):
        engine = PartnerEngine()
        with pytest.raises(ValueError) as exc_info:
            engine.record_deal("partner-missing", 1000.0, closed=True)
        message = str(exc_info.value)
        assert message == "unknown partner"
        assert "partner-missing" not in message
        assert ":" not in message

class TestGoldenProof:
    def test_full_partner_lifecycle(self):
        engine = PartnerEngine()

        # 1. Onboard partner
        p = engine.onboard_partner("partner-1", "TechConsult Inc", "implementation", "none")
        assert p.active

        # 2. Certify
        p = engine.certify_partner("partner-1", "implementation_certified")
        assert p.certification_level == "implementation_certified"

        # 3. Partner runs demo (enablement assets exist)
        assert len(ENABLEMENT_ASSETS) == 8

        # 4. Partner closes deal
        econ = engine.record_deal("partner-1", 4500.0, closed=True)
        assert econ.referral_fees_earned == 1350.0  # 30% implementation share

        # 5. Quality measured
        engine.update_quality("partner-1", 8.0)
        assert engine._partners["partner-1"].status == "gold"

        # 6. Dashboard usable
        d = engine.dashboard()
        assert d["total_partners"] == 1
        assert d["gold"] == 1
        assert d["total_revenue_influenced"] == 4500.0
        assert d["total_partner_earnings"] == 1350.0
