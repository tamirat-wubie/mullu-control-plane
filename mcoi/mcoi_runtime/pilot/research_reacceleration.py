"""Phase 159 — Research / Lab Re-acceleration: strengthen the pack."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# 159A — Expanded capabilities (original 10 + epistemic_integration + uncertainty_synthesis)
RESEARCH_V2_CAPABILITIES: tuple[str, ...] = (
    "research_intake",
    "hypothesis_tracking",
    "experiment_coordination",
    "evidence_retrieval",
    "literature_review",
    "peer_review_approval",
    "result_synthesis",
    "compliance_overlay",
    "research_dashboard",
    "research_copilot",
    "epistemic_integration",
    "uncertainty_synthesis",
)


# 159B — Maturity scoring
@dataclass
class ResearchMaturityScore:
    pilot_requests: int = 0
    positive_outcomes: int = 0
    margin_positive: bool = False
    demand_trend: str = "flat"  # "rising", "flat", "declining"


def evaluate_research_readiness(score: ResearchMaturityScore) -> str:
    """Return 'promote', 'extend_incubation', or 'sunset'."""
    if (
        score.pilot_requests >= 3
        and score.positive_outcomes >= 2
        and score.margin_positive
    ):
        return "promote"
    if score.pilot_requests >= 3 and score.positive_outcomes >= 1:
        return "extend_incubation"
    if score.demand_trend == "declining" and score.positive_outcomes == 0:
        return "sunset"
    return "extend_incubation"


# 159C — Strengthening roadmap
RESEARCH_STRENGTHENING_ROADMAP: tuple[str, ...] = (
    "experiment_ux_improvements",
    "evidence_synthesis_pipeline",
    "contradiction_handling",
    "epistemic_integration",
    "ontology_alignment",
    "reporting_enhancements",
)


# 159D — Demo V2 generator with richer data
class ResearchDemoV2Generator:
    """Creates a richer seeded demo for Research / Lab V2."""

    def generate(self, tenant_id: str = "rl-v2-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "research_lab_v2"}

        # Hypotheses
        hypotheses = [
            {"id": f"hyp-{i:03d}", "statement": stmt, "status": status}
            for i, (stmt, status) in enumerate([
                ("Compound X reduces inflammation by 40%", "under_test"),
                ("Protocol Y improves yield by 15%", "confirmed"),
                ("Reagent Z is contamination source", "refuted"),
                ("Temperature variance causes drift", "under_test"),
                ("New assay improves sensitivity 2x", "confirmed"),
            ])
        ]
        result["hypotheses"] = hypotheses

        # Experiments with results
        experiments = [
            {
                "id": f"exp-{i:03d}",
                "hypothesis_ref": f"hyp-{i:03d}",
                "title": title,
                "result": res,
                "confidence": conf,
            }
            for i, (title, res, conf) in enumerate([
                ("Phase III dosing trial", "positive", 0.92),
                ("Yield optimization batch A", "positive", 0.87),
                ("Contamination source isolation", "negative", 0.65),
                ("Thermal stability assay", "inconclusive", 0.51),
                ("Sensitivity comparison panel", "positive", 0.95),
            ])
        ]
        result["experiments"] = experiments

        # Contradicting findings
        contradictions = [
            {
                "id": f"contra-{i:03d}",
                "experiment_a": f"exp-{a:03d}",
                "experiment_b": f"exp-{b:03d}",
                "description": desc,
            }
            for i, (a, b, desc) in enumerate([
                (0, 3, "Dosing efficacy contradicted by thermal instability at higher temps"),
                (1, 2, "Yield improvement inconsistent with contamination findings"),
            ])
        ]
        result["contradictions"] = contradictions

        # Peer review items
        peer_reviews = [
            {"id": f"pr-{i:03d}", "experiment_ref": f"exp-{i:03d}", "reviewer": rev, "verdict": verdict}
            for i, (rev, verdict) in enumerate([
                ("Dr. A. Smith", "approved"),
                ("Dr. B. Jones", "approved"),
                ("Dr. C. Lee", "revision_requested"),
                ("Dr. D. Patel", "pending"),
                ("Dr. E. Kim", "approved"),
            ])
        ]
        result["peer_reviews"] = peer_reviews

        # Evidence synthesis
        synthesis = {
            "total_hypotheses": len(hypotheses),
            "confirmed": sum(1 for h in hypotheses if h["status"] == "confirmed"),
            "refuted": sum(1 for h in hypotheses if h["status"] == "refuted"),
            "under_test": sum(1 for h in hypotheses if h["status"] == "under_test"),
            "contradiction_count": len(contradictions),
            "mean_confidence": round(
                sum(e["confidence"] for e in experiments) / len(experiments), 3
            ),
        }
        result["evidence_synthesis"] = synthesis

        result["status"] = "demo_v2_ready"
        result["total_seeded"] = (
            len(hypotheses) + len(experiments) + len(contradictions)
            + len(peer_reviews)
        )
        return result


# 159E — Target list V2
RESEARCH_TARGET_LIST_V2: tuple[dict[str, Any], ...] = (
    {
        "id": "rl-v2-t1",
        "name": "Nextera Biotech R&D",
        "industry": "biotech",
        "sub_segment": "drug_discovery",
        "headcount": 45,
        "buyer": "VP Discovery Research",
        "champion": "Head of Computational Biology",
        "estimated_acv": 8500,
    },
    {
        "id": "rl-v2-t2",
        "name": "Meridian Pharma Ops",
        "industry": "pharma",
        "sub_segment": "clinical_operations",
        "headcount": 30,
        "buyer": "SVP Clinical Ops",
        "champion": "Director Clinical Data Mgmt",
        "estimated_acv": 7200,
    },
    {
        "id": "rl-v2-t3",
        "name": "Ironclad Industrial Testing",
        "industry": "industrial",
        "sub_segment": "materials_testing",
        "headcount": 20,
        "buyer": "Director QA/QC",
        "champion": "Lab Manager",
        "estimated_acv": 5500,
    },
    {
        "id": "rl-v2-t4",
        "name": "Pacific Academic Research Ops",
        "industry": "academic",
        "sub_segment": "research_administration",
        "headcount": 35,
        "buyer": "Dean of Research",
        "champion": "Research Ops Lead",
        "estimated_acv": 4800,
    },
    {
        "id": "rl-v2-t5",
        "name": "Trident CRO Services",
        "industry": "cro",
        "sub_segment": "contract_research",
        "headcount": 25,
        "buyer": "VP Client Programs",
        "champion": "Study Director",
        "estimated_acv": 6800,
    },
)
