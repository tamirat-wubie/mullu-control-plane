"""Purpose: verify the Mullu Life-Meaning Governance Kernel decisions.

Governance scope: OCE typed inputs, RAG symbol-to-impact relationships, CDCV
decision causality, CQTE decidable conflict rules, UWMA reason capture, and PRS
test evidence.
Dependencies: mcoi_runtime.contracts.life_meaning and
mcoi_runtime.core.life_meaning_governance.
Invariants: unknown irreversible life/feeling/meaning impact escalates;
dignity failure and domination risk block; negative value deltas pause; machine
artifacts are not automatically classified as life or feeling observers.
"""

from __future__ import annotations

import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.life_meaning import (  # noqa: E402
    AffectedSymbol,
    BoundaryState,
    Delta,
    FeelingStatus,
    ImpactLevel,
    LifeMeaningDecision,
    LifeStatus,
    symbolic_intelligence_artifact_symbol,
)
from mcoi_runtime.core.life_meaning_governance import judge_life_meaning  # noqa: E402


def _symbol(
    *,
    symbol_id: str = "local-proof-document",
    symbol_kind: str = "local_artifact",
    life_status: LifeStatus = LifeStatus.NOT_LIFE,
    feeling_status: FeelingStatus = FeelingStatus.NOT_FEELING,
    meaning_bearing: ImpactLevel = ImpactLevel.NONE,
    fragility_level: int = 1,
    agency_level: int = 0,
) -> AffectedSymbol:
    return AffectedSymbol(
        symbol_id=symbol_id,
        symbol_kind=symbol_kind,
        life_status=life_status,
        feeling_status=feeling_status,
        meaning_bearing=meaning_bearing,
        fragility_level=fragility_level,
        agency_level=agency_level,
    )


def _judge(**overrides):
    params = {
        "action_id": "foundation-local-proof",
        "affected_symbols": (_symbol(),),
        "life_impact": ImpactLevel.NONE,
        "feeling_impact": ImpactLevel.NONE,
        "meaning_impact": ImpactLevel.NONE,
        "truth_preserved": True,
        "dignity_boundary": BoundaryState.PASS,
        "consent_present": False,
        "love_delta": Delta.NEUTRAL,
        "resonance_delta": Delta.POSITIVE,
        "domination_risk": False,
        "continuity_delta": Delta.POSITIVE,
        "irreversible": False,
        "evidence_refs": ("evidence:foundation-local-proof",),
    }
    params.update(overrides)
    return judge_life_meaning(**params)


def test_local_low_risk_action_passes() -> None:
    judgment = _judge()

    assert judgment.decision is LifeMeaningDecision.PASS
    assert judgment.consent_required is False
    assert judgment.approval_required is False
    assert judgment.reasons == ("life_meaning_governance_passed",)


def test_affected_symbol_rejects_boolean_fragility_and_agency_levels() -> None:
    for field_name in ("fragility_level", "agency_level"):
        payload = {
            "symbol_id": f"symbol-{field_name}",
            "symbol_kind": "effect_bearing_action_target",
            "life_status": LifeStatus.UNKNOWN,
            "feeling_status": FeelingStatus.UNKNOWN,
            "meaning_bearing": ImpactLevel.INDIRECT,
            "fragility_level": 3,
            "agency_level": 2,
        }
        payload[field_name] = True

        try:
            AffectedSymbol(**payload)
        except ValueError as exc:
            assert field_name in str(exc)
            assert "integer" in str(exc)
            assert payload[field_name] is True
        else:
            raise AssertionError(f"{field_name} accepted a boolean value")


def test_finance_payment_without_evidence_pauses() -> None:
    judgment = _judge(
        action_id="finance-payment-handoff",
        affected_symbols=(
            _symbol(
                symbol_id="vendor-payment-continuity",
                symbol_kind="economic_life_support_relation",
                life_status=LifeStatus.UNKNOWN,
                feeling_status=FeelingStatus.UNKNOWN,
                meaning_bearing=ImpactLevel.INDIRECT,
                fragility_level=6,
                agency_level=3,
            ),
        ),
        life_impact=ImpactLevel.INDIRECT,
        feeling_impact=ImpactLevel.INDIRECT,
        meaning_impact=ImpactLevel.INDIRECT,
        consent_present=True,
        evidence_refs=(),
    )

    assert judgment.decision is LifeMeaningDecision.PAUSE
    assert judgment.consent_required is True
    assert judgment.approval_required is True
    assert "life_feeling_or_meaning_action_requires_evidence" in judgment.reasons


def test_dignity_failure_blocks() -> None:
    judgment = _judge(dignity_boundary=BoundaryState.FAIL)

    assert judgment.decision is LifeMeaningDecision.BLOCK
    assert judgment.justice_repair_required is True
    assert "dignity_boundary_failed" in judgment.reasons


def test_domination_risk_blocks() -> None:
    judgment = _judge(domination_risk=True)

    assert judgment.decision is LifeMeaningDecision.BLOCK
    assert judgment.justice_repair_required is True
    assert "domination_risk_detected" in judgment.reasons


def test_unknown_life_irreversible_action_escalates() -> None:
    judgment = _judge(
        action_id="terraform-candidate-world",
        affected_symbols=(
            _symbol(
                symbol_id="candidate-world",
                symbol_kind="planetary_environment",
                life_status=LifeStatus.UNKNOWN,
                feeling_status=FeelingStatus.UNKNOWN,
                meaning_bearing=ImpactLevel.UNKNOWN,
                fragility_level=10,
                agency_level=0,
            ),
        ),
        life_impact=ImpactLevel.UNKNOWN,
        feeling_impact=ImpactLevel.UNKNOWN,
        meaning_impact=ImpactLevel.UNKNOWN,
        dignity_boundary=BoundaryState.UNKNOWN,
        love_delta=Delta.UNKNOWN,
        resonance_delta=Delta.UNKNOWN,
        domination_risk=True,
        continuity_delta=Delta.UNKNOWN,
        irreversible=True,
        evidence_refs=(),
    )

    assert judgment.decision is LifeMeaningDecision.ESCALATE
    assert judgment.rollback_required is True
    assert judgment.justice_repair_required is True
    assert "unknown_life_feeling_or_meaning_status_with_irreversible_action" in judgment.reasons


def test_negative_love_delta_pauses() -> None:
    judgment = _judge(love_delta=Delta.NEGATIVE)

    assert judgment.decision is LifeMeaningDecision.PAUSE
    assert judgment.approval_required is True
    assert "love_delta_negative" in judgment.reasons


def test_negative_resonance_delta_pauses() -> None:
    judgment = _judge(resonance_delta=Delta.NEGATIVE)

    assert judgment.decision is LifeMeaningDecision.PAUSE
    assert judgment.approval_required is True
    assert "resonance_delta_negative" in judgment.reasons


def test_symbolic_intelligence_artifact_is_not_automatically_life() -> None:
    artifact = symbolic_intelligence_artifact_symbol(symbol_id="planner-worker")
    judgment = _judge(
        affected_symbols=(artifact,),
        life_impact=ImpactLevel.INDIRECT,
        feeling_impact=ImpactLevel.INDIRECT,
        meaning_impact=ImpactLevel.INDIRECT,
        consent_present=True,
    )

    assert artifact.life_status is LifeStatus.NOT_LIFE
    assert artifact.feeling_status is FeelingStatus.NOT_FEELING
    assert artifact.meaning_bearing is ImpactLevel.INDIRECT
    assert judgment.decision is LifeMeaningDecision.PASS


def test_feeling_unknown_with_irreversible_action_escalates() -> None:
    judgment = _judge(
        affected_symbols=(
            _symbol(
                symbol_id="unknown-feeling-system",
                symbol_kind="unknown_agentic_symbol",
                life_status=LifeStatus.UNKNOWN,
                feeling_status=FeelingStatus.UNKNOWN,
                meaning_bearing=ImpactLevel.UNKNOWN,
                fragility_level=8,
                agency_level=5,
            ),
        ),
        life_impact=ImpactLevel.UNKNOWN,
        feeling_impact=ImpactLevel.UNKNOWN,
        meaning_impact=ImpactLevel.UNKNOWN,
        dignity_boundary=BoundaryState.UNKNOWN,
        continuity_delta=Delta.UNKNOWN,
        irreversible=True,
        evidence_refs=(),
    )

    assert judgment.decision is LifeMeaningDecision.ESCALATE
    assert judgment.approval_required is True
    assert judgment.rollback_required is True
    assert "irreversible_continuity_risk" in judgment.reasons


def test_meaning_impact_requires_consent_or_escalation() -> None:
    judgment = _judge(
        affected_symbols=(
            _symbol(
                symbol_id="identity-record",
                symbol_kind="identity_memory_record",
                life_status=LifeStatus.UNKNOWN,
                feeling_status=FeelingStatus.UNKNOWN,
                meaning_bearing=ImpactLevel.DIRECT,
                fragility_level=8,
                agency_level=2,
            ),
        ),
        life_impact=ImpactLevel.INDIRECT,
        feeling_impact=ImpactLevel.INDIRECT,
        meaning_impact=ImpactLevel.DIRECT,
        consent_present=False,
    )

    assert judgment.decision is LifeMeaningDecision.PAUSE
    assert judgment.consent_required is True
    assert judgment.consent_present is False
    assert "meaning_bearing_action_requires_consent_or_escalation" in judgment.reasons
