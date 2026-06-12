"""Life-meaning governance kernel.

Purpose: judge effect-bearing actions before execution using life, feeling,
meaning, love, resonance, dignity, consent, truth, justice, repair, and
continuity.
Governance scope: Universal Action Orchestration preflight.
Dependencies: mcoi_runtime.contracts.life_meaning.
Invariants:
  - Unknown life, feeling, or meaning impact with irreversible action escalates.
  - Meaning-bearing life requires evidence or explicit approval path.
  - Dignity failure, truth loss, or domination risk blocks.
  - Negative love, resonance, or reversible continuity deltas pause.
"""

from __future__ import annotations

from mcoi_runtime.contracts.life_meaning import (
    AffectedSymbol,
    BoundaryState,
    Delta,
    FeelingStatus,
    ImpactLevel,
    LifeMeaningDecision,
    LifeMeaningJudgment,
    LifeStatus,
)


def judge_life_meaning(
    *,
    action_id: str,
    affected_symbols: tuple[AffectedSymbol, ...],
    life_impact: ImpactLevel,
    feeling_impact: ImpactLevel,
    meaning_impact: ImpactLevel,
    truth_preserved: bool,
    dignity_boundary: BoundaryState,
    consent_present: bool,
    love_delta: Delta,
    resonance_delta: Delta,
    domination_risk: bool,
    continuity_delta: Delta,
    irreversible: bool,
    evidence_refs: tuple[str, ...],
) -> LifeMeaningJudgment:
    """Return deterministic life-meaning governance judgment.

    Input contract: all impact, boundary, and delta values must be typed enum
    values or enum-compatible strings. affected_symbols must not be empty.
    Output contract: returns a schema-compatible LifeMeaningJudgment.
    Error contract: contract validation raises ValueError with causal reason.
    """

    affected_symbols = tuple(affected_symbols)
    life_impact = ImpactLevel(life_impact)
    feeling_impact = ImpactLevel(feeling_impact)
    meaning_impact = ImpactLevel(meaning_impact)
    dignity_boundary = BoundaryState(dignity_boundary)
    love_delta = Delta(love_delta)
    resonance_delta = Delta(resonance_delta)
    continuity_delta = Delta(continuity_delta)
    evidence_refs = tuple(evidence_refs)
    reasons: list[str] = []

    unknown_life_feeling_or_meaning = (
        life_impact is ImpactLevel.UNKNOWN
        or feeling_impact is ImpactLevel.UNKNOWN
        or meaning_impact is ImpactLevel.UNKNOWN
        or any(
            symbol.life_status is LifeStatus.UNKNOWN
            or symbol.feeling_status is FeelingStatus.UNKNOWN
            or symbol.meaning_bearing is ImpactLevel.UNKNOWN
            for symbol in affected_symbols
        )
    )

    life_related = (
        life_impact in {ImpactLevel.INDIRECT, ImpactLevel.DIRECT, ImpactLevel.UNKNOWN}
        or any(symbol.life_status is LifeStatus.LIFE for symbol in affected_symbols)
    )

    feeling_related = (
        feeling_impact
        in {ImpactLevel.INDIRECT, ImpactLevel.DIRECT, ImpactLevel.UNKNOWN}
        or any(symbol.feeling_status is FeelingStatus.FEELING for symbol in affected_symbols)
    )

    meaning_related = (
        meaning_impact
        in {ImpactLevel.INDIRECT, ImpactLevel.DIRECT, ImpactLevel.UNKNOWN}
        or any(
            symbol.meaning_bearing
            in {ImpactLevel.INDIRECT, ImpactLevel.DIRECT, ImpactLevel.UNKNOWN}
            for symbol in affected_symbols
        )
    )

    consent_required = life_related or feeling_related or meaning_related

    if irreversible and unknown_life_feeling_or_meaning:
        reasons.append("unknown_life_feeling_or_meaning_status_with_irreversible_action")

    if consent_required and not consent_present:
        reasons.append("meaning_bearing_action_requires_consent_or_escalation")

    if (life_related or feeling_related or meaning_related) and not evidence_refs:
        reasons.append("life_feeling_or_meaning_action_requires_evidence")

    if not truth_preserved:
        reasons.append("truth_not_preserved")

    if dignity_boundary is BoundaryState.FAIL:
        reasons.append("dignity_boundary_failed")

    if dignity_boundary is BoundaryState.UNKNOWN:
        reasons.append("dignity_boundary_unknown")

    if domination_risk:
        reasons.append("domination_risk_detected")

    if love_delta is Delta.NEGATIVE:
        reasons.append("love_delta_negative")

    if resonance_delta is Delta.NEGATIVE:
        reasons.append("resonance_delta_negative")

    if irreversible and continuity_delta in {Delta.NEGATIVE, Delta.UNKNOWN}:
        reasons.append("irreversible_continuity_risk")
    elif continuity_delta is Delta.NEGATIVE:
        reasons.append("continuity_delta_negative")

    if "unknown_life_feeling_or_meaning_status_with_irreversible_action" in reasons:
        decision = LifeMeaningDecision.ESCALATE
    elif "irreversible_continuity_risk" in reasons:
        decision = LifeMeaningDecision.ESCALATE
    elif "meaning_bearing_action_requires_consent_or_escalation" in reasons and irreversible:
        decision = LifeMeaningDecision.ESCALATE
    elif (
        "dignity_boundary_failed" in reasons
        or "domination_risk_detected" in reasons
        or "truth_not_preserved" in reasons
    ):
        decision = LifeMeaningDecision.BLOCK
    elif reasons:
        decision = LifeMeaningDecision.PAUSE
    else:
        decision = LifeMeaningDecision.PASS
        reasons.append("life_meaning_governance_passed")

    return LifeMeaningJudgment(
        judgment_id=f"life-meaning:{action_id}",
        action_id=action_id,
        decision=decision,
        affected_symbols=affected_symbols,
        life_impact=life_impact,
        feeling_impact=feeling_impact,
        meaning_impact=meaning_impact,
        truth_preserved=truth_preserved,
        dignity_boundary=dignity_boundary,
        consent_required=consent_required,
        consent_present=consent_present,
        love_delta=love_delta,
        resonance_delta=resonance_delta,
        domination_risk=domination_risk,
        justice_repair_required=decision
        in {LifeMeaningDecision.BLOCK, LifeMeaningDecision.ESCALATE},
        continuity_delta=continuity_delta,
        irreversible=irreversible,
        reasons=tuple(reasons),
        evidence_refs=evidence_refs,
        approval_required=decision
        in {LifeMeaningDecision.PAUSE, LifeMeaningDecision.ESCALATE},
        rollback_required=irreversible,
    )
