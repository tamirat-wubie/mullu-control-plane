"""Gateway economic intelligence tests.

Purpose: verify governed utility routing, control preservation, blocked-route
    evidence, review handling, and public snapshot schema behavior.
Governance scope: economic routing, tenant bounds, policy preservation, cost
    scoring, review escalation, and manifest-ready public contracts.
Dependencies: gateway.economic_intelligence and economic intelligence schema.
Invariants:
  - The engine selects only admitted candidates.
  - Lower-cost blocked candidates cannot bypass policy or authority controls.
  - Non-positive utility requires review when strict utility is requested.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.economic_intelligence import (
    EconomicActionCandidate,
    EconomicIntelligenceEngine,
    EconomicIntelligenceSnapshot,
    EconomicRiskTier,
    EconomicVerdict,
    UtilityWeights,
    economic_intelligence_snapshot_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "economic_intelligence_snapshot.schema.json"


def test_selects_highest_utility_admitted_candidate() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(_candidate("candidate-fast", expected_value="70.00", latency_cost="2.00"))
    engine.register_candidate(_candidate("candidate-rich", expected_value="95.00", latency_cost="8.00"))

    decision = engine.route(tenant_id="tenant-a", candidate_ids=("candidate-fast", "candidate-rich"))

    assert decision.verdict is EconomicVerdict.SELECT
    assert decision.selected_candidate_id == "candidate-rich"
    assert decision.reason == "highest_admitted_utility"
    assert decision.utility_score == Decimal("81.00")
    assert decision.blocked_candidate_ids == ()
    assert decision.decision_hash


def test_cheaper_blocked_candidate_cannot_bypass_controls() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(_candidate("candidate-safe", expected_value="40.00", model_cost="10.00"))
    engine.register_candidate(
        _candidate(
            "candidate-cheap",
            expected_value="1000.00",
            model_cost="0.00",
            policy_verdict="deny",
            control_admitted=False,
        )
    )

    decision = engine.route(tenant_id="tenant-a", candidate_ids=("candidate-safe", "candidate-cheap"))
    snapshot = engine.snapshot()

    assert decision.verdict is EconomicVerdict.SELECT
    assert decision.selected_candidate_id == "candidate-safe"
    assert decision.blocked_candidate_ids == ("candidate-cheap",)
    assert decision.blocked_reasons == ("control_not_admitted",)
    assert snapshot.blocked_candidate_count == 1
    assert snapshot.policy_override_allowed is False


def test_tenant_mismatch_and_authority_review_fail_closed() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(_candidate("candidate-foreign", tenant_id="tenant-b"))
    engine.register_candidate(_candidate("candidate-review", authority_verdict="review"))

    decision = engine.route(tenant_id="tenant-a", candidate_ids=("candidate-foreign", "candidate-review"))

    assert decision.verdict is EconomicVerdict.DENY
    assert decision.selected_candidate_id is None
    assert decision.reason == "no_admitted_candidate"
    assert decision.blocked_candidate_ids == ("candidate-foreign", "candidate-review")
    assert decision.blocked_reasons == ("tenant_mismatch", "authority_not_allowed")


def test_non_positive_utility_requires_review_when_strict() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(
        _candidate(
            "candidate-loss",
            expected_value="5.00",
            model_cost="3.00",
            tool_cost="3.00",
            risk_cost="3.00",
        )
    )

    decision = engine.route(tenant_id="tenant-a", candidate_ids=("candidate-loss",))

    assert decision.verdict is EconomicVerdict.REVIEW
    assert decision.selected_candidate_id is None
    assert decision.reason == "positive_utility_not_proven"
    assert decision.utility_score == Decimal("-7.00")
    assert decision.metadata["best_candidate_id"] == "candidate-loss"


def test_custom_weights_change_selected_route_without_control_override() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(_candidate("candidate-low-risk", expected_value="80.00", risk_cost="2.00"))
    engine.register_candidate(
        _candidate(
            "candidate-high-risk",
            expected_value="100.00",
            risk_cost="8.00",
            risk_tier=EconomicRiskTier.HIGH,
        )
    )

    decision = engine.route(
        tenant_id="tenant-a",
        candidate_ids=("candidate-low-risk", "candidate-high-risk"),
        weights=UtilityWeights(risk_cost_weight=Decimal("3.00")),
    )

    assert decision.verdict is EconomicVerdict.SELECT
    assert decision.selected_candidate_id == "candidate-low-risk"
    assert decision.metadata["policy_override_allowed"] is False
    assert decision.metadata["weights"]["risk_cost_weight"] == "3.00"


def test_economic_intelligence_snapshot_schema_exposes_operator_contract() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(_candidate("candidate-safe"))
    decision = engine.route(tenant_id="tenant-a", candidate_ids=("candidate-safe",))
    snapshot = engine.snapshot()
    payload = economic_intelligence_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:economic-intelligence-snapshot:1"
    assert "critical" in schema["$defs"]["risk_tier"]["enum"]
    assert payload["policy_override_allowed"] is False
    assert payload["selected_count"] == 1
    assert payload["decisions"][0]["decision_id"] == decision.decision_id
    assert snapshot.snapshot_hash


def test_snapshot_rejects_inconsistent_count_witnesses() -> None:
    engine = EconomicIntelligenceEngine()
    engine.register_candidate(_candidate("candidate-safe"))
    engine.route(tenant_id="tenant-a", candidate_ids=("candidate-safe",))
    snapshot = engine.snapshot()

    with pytest.raises(ValueError, match="selected_count_mismatch"):
        EconomicIntelligenceSnapshot(
            snapshot_id="bad-selected-count",
            candidates=snapshot.candidates,
            decisions=snapshot.decisions,
            selected_count=0,
            review_count=snapshot.review_count,
            denied_count=snapshot.denied_count,
            blocked_candidate_count=snapshot.blocked_candidate_count,
            policy_override_allowed=False,
        )
    with pytest.raises(ValueError, match="review_count_mismatch"):
        EconomicIntelligenceSnapshot(
            snapshot_id="bad-review-count",
            candidates=snapshot.candidates,
            decisions=snapshot.decisions,
            selected_count=snapshot.selected_count,
            review_count=1,
            denied_count=snapshot.denied_count,
            blocked_candidate_count=snapshot.blocked_candidate_count,
            policy_override_allowed=False,
        )
    with pytest.raises(ValueError, match="blocked_candidate_count_mismatch"):
        EconomicIntelligenceSnapshot(
            snapshot_id="bad-blocked-count",
            candidates=snapshot.candidates,
            decisions=snapshot.decisions,
            selected_count=snapshot.selected_count,
            review_count=snapshot.review_count,
            denied_count=snapshot.denied_count,
            blocked_candidate_count=1,
            policy_override_allowed=False,
        )


def test_negative_utility_terms_are_rejected() -> None:
    with pytest.raises(ValueError, match="model_cost_usd_non_negative"):
        _candidate("candidate-invalid", model_cost="-1.00")


def _candidate(
    candidate_id: str,
    *,
    tenant_id: str = "tenant-a",
    expected_value: str = "50.00",
    model_cost: str = "2.00",
    tool_cost: str = "1.00",
    latency_cost: str = "1.00",
    risk_cost: str = "1.00",
    human_review_cost: str = "1.00",
    failure_compensation_cost: str = "1.00",
    risk_tier: EconomicRiskTier = EconomicRiskTier.LOW,
    policy_verdict: str = "allow",
    authority_verdict: str = "allow",
    budget_verdict: str = "allow",
    control_admitted: bool = True,
) -> EconomicActionCandidate:
    return EconomicActionCandidate(
        candidate_id=candidate_id,
        tenant_id=tenant_id,
        action_ref=f"action:{candidate_id}",
        capability_ref="capability:rag.query",
        policy_verdict=policy_verdict,
        authority_verdict=authority_verdict,
        budget_verdict=budget_verdict,
        evidence_refs=(f"evidence:{candidate_id}",),
        expected_value_usd=Decimal(expected_value),
        model_cost_usd=Decimal(model_cost),
        tool_cost_usd=Decimal(tool_cost),
        latency_cost_usd=Decimal(latency_cost),
        risk_cost_usd=Decimal(risk_cost),
        human_review_cost_usd=Decimal(human_review_cost),
        failure_compensation_cost_usd=Decimal(failure_compensation_cost),
        risk_tier=risk_tier,
        control_admitted=control_admitted,
    )
