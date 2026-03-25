"""Phase 159 — Research / Lab Re-acceleration Tests."""
import pytest
from mcoi_runtime.pilot.research_reacceleration import (
    RESEARCH_V2_CAPABILITIES,
    RESEARCH_STRENGTHENING_ROADMAP,
    RESEARCH_TARGET_LIST_V2,
    ResearchMaturityScore,
    evaluate_research_readiness,
    ResearchDemoV2Generator,
)


class TestCapabilities:
    def test_v2_has_12_capabilities(self):
        assert len(RESEARCH_V2_CAPABILITIES) == 12

    def test_original_10_present(self):
        for cap in (
            "research_intake", "hypothesis_tracking", "experiment_coordination",
            "evidence_retrieval", "literature_review", "peer_review_approval",
            "result_synthesis", "compliance_overlay", "research_dashboard",
            "research_copilot",
        ):
            assert cap in RESEARCH_V2_CAPABILITIES

    def test_new_capabilities_present(self):
        assert "epistemic_integration" in RESEARCH_V2_CAPABILITIES
        assert "uncertainty_synthesis" in RESEARCH_V2_CAPABILITIES


class TestMaturityScoring:
    def test_promote_when_strong(self):
        score = ResearchMaturityScore(
            pilot_requests=5, positive_outcomes=4,
            margin_positive=True, demand_trend="rising",
        )
        assert evaluate_research_readiness(score) == "promote"

    def test_extend_incubation_borderline(self):
        score = ResearchMaturityScore(
            pilot_requests=3, positive_outcomes=1,
            margin_positive=False, demand_trend="flat",
        )
        assert evaluate_research_readiness(score) == "extend_incubation"

    def test_sunset_declining_no_outcomes(self):
        score = ResearchMaturityScore(
            pilot_requests=1, positive_outcomes=0,
            margin_positive=False, demand_trend="declining",
        )
        assert evaluate_research_readiness(score) == "sunset"

    def test_extend_when_few_pilots(self):
        score = ResearchMaturityScore(
            pilot_requests=2, positive_outcomes=2,
            margin_positive=True, demand_trend="rising",
        )
        assert evaluate_research_readiness(score) == "extend_incubation"


class TestStrengtheningRoadmap:
    def test_roadmap_has_6_items(self):
        assert len(RESEARCH_STRENGTHENING_ROADMAP) == 6

    def test_roadmap_key_items(self):
        assert "evidence_synthesis_pipeline" in RESEARCH_STRENGTHENING_ROADMAP
        assert "contradiction_handling" in RESEARCH_STRENGTHENING_ROADMAP
        assert "epistemic_integration" in RESEARCH_STRENGTHENING_ROADMAP


class TestDemoV2Generator:
    def test_generate_produces_rich_data(self):
        gen = ResearchDemoV2Generator()
        result = gen.generate("rl-v2-test")
        assert result["status"] == "demo_v2_ready"
        assert len(result["hypotheses"]) == 5
        assert len(result["experiments"]) == 5
        assert len(result["contradictions"]) == 2
        assert len(result["peer_reviews"]) == 5
        assert result["total_seeded"] == 17

    def test_evidence_synthesis_summary(self):
        gen = ResearchDemoV2Generator()
        result = gen.generate()
        syn = result["evidence_synthesis"]
        assert syn["confirmed"] == 2
        assert syn["refuted"] == 1
        assert syn["under_test"] == 2
        assert syn["contradiction_count"] == 2
        assert 0 < syn["mean_confidence"] < 1


class TestTargetListV2:
    def test_5_targets(self):
        assert len(RESEARCH_TARGET_LIST_V2) == 5

    def test_diverse_industries(self):
        industries = {t["industry"] for t in RESEARCH_TARGET_LIST_V2}
        assert industries == {"biotech", "pharma", "industrial", "academic", "cro"}
