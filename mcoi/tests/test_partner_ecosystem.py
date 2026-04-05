"""Tests for Phase 163 — Partner Ecosystem / Channel Marketplace."""
import pytest
from mcoi_runtime.pilot.partner_ecosystem import (
    APPROVAL_REQUIREMENTS,
    CONTRIBUTION_KINDS,
    EcosystemMarketplace,
    PartnerContribution,
)


def _make(cid="c1", partner="p1", kind="connector_pack", name="Test Pack"):
    return PartnerContribution(cid, partner, kind, name)


class TestPartnerContribution:
    def test_valid_creation(self):
        c = _make()
        assert c.status == "submitted"
        assert c.quality_score == 0.0

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError, match="^invalid contribution kind$") as exc_info:
            PartnerContribution("c1", "p1", "bad_kind", "X")
        assert "bad_kind" not in str(exc_info.value)

    def test_invalid_quality_score(self):
        with pytest.raises(ValueError, match="quality_score"):
            PartnerContribution("c1", "p1", "connector_pack", "X", quality_score=11.0)

    def test_invalid_status_rejected_without_leaking_value(self):
        with pytest.raises(ValueError, match="^invalid contribution status$") as exc_info:
            PartnerContribution("c1", "p1", "connector_pack", "X", status="secret-status")
        assert "secret-status" not in str(exc_info.value)


class TestEcosystemMarketplace:
    def test_submit_and_approve(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("c1"))
        result = mp.approve("c1", 8.5)
        assert result.status == "approved"
        assert result.quality_score == 8.5

    def test_reject(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("c1"))
        result = mp.reject("c1", reason="poor docs")
        assert result.status == "rejected"

    def test_deprecate(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("c1"))
        mp.approve("c1", 9.0)
        result = mp.deprecate("c1")
        assert result.status == "deprecated"

    def test_quality_threshold_filter(self):
        mp = EcosystemMarketplace()
        for i, score in enumerate([6.0, 7.0, 8.5, 9.0]):
            mp.submit_contribution(_make(f"c{i}", kind="dashboard_kit", name=f"Kit {i}"))
            mp.approve(f"c{i}", score)
        high_quality = mp.quality_threshold_filter()  # default >= 7
        assert len(high_quality) == 3  # 7.0, 8.5, 9.0

    def test_by_kind_and_by_partner(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("c1", partner="p1", kind="connector_pack"))
        mp.submit_contribution(_make("c2", partner="p1", kind="dashboard_kit", name="Kit"))
        mp.submit_contribution(_make("c3", partner="p2", kind="connector_pack", name="Pack2"))
        assert len(mp.by_kind("connector_pack")) == 2
        assert len(mp.by_partner("p1")) == 2

    def test_summary(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("c1"))
        mp.submit_contribution(_make("c2", kind="dashboard_kit", name="Kit"))
        mp.approve("c1", 8.0)
        s = mp.summary()
        assert s["total"] == 2
        assert s["by_status"]["approved"] == 1
        assert s["by_status"]["submitted"] == 1

    def test_approval_requirements_cover_all_kinds(self):
        for kind in CONTRIBUTION_KINDS:
            assert kind in APPROVAL_REQUIREMENTS, f"Missing approval requirements for {kind}"


class TestBoundedPartnerEcosystemContracts:
    def test_registry_and_lookup_errors_are_bounded(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("contrib-secret"))

        with pytest.raises(ValueError, match="^duplicate contribution$") as exc_info:
            mp.submit_contribution(_make("contrib-secret"))
        assert "contrib-secret" not in str(exc_info.value)

        with pytest.raises(KeyError, match="^'unknown contribution'$") as exc_info:
            mp.approve("missing-secret", 8.0)
        assert "missing-secret" not in str(exc_info.value)

    def test_lifecycle_state_errors_are_bounded(self):
        mp = EcosystemMarketplace()
        mp.submit_contribution(_make("contrib-secret"))
        mp.approve("contrib-secret", 8.0)

        with pytest.raises(
            ValueError,
            match="^contribution must be submitted before rejection$",
        ) as exc_info:
            mp.reject("contrib-secret")
        assert "approved" not in str(exc_info.value)
        assert "contrib-secret" not in str(exc_info.value)

        with pytest.raises(
            ValueError,
            match="^contribution must be submitted before approval$",
        ) as exc_info:
            mp.approve("contrib-secret", 9.0)
        assert "approved" not in str(exc_info.value)

        rejected = EcosystemMarketplace()
        rejected.submit_contribution(_make("contrib-rejected"))
        rejected.reject("contrib-rejected")
        with pytest.raises(
            ValueError,
            match="^contribution must be approved before deprecation$",
        ) as exc_info:
            rejected.deprecate("contrib-rejected")
        assert "rejected" not in str(exc_info.value)
