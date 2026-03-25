"""Purpose: multi-factor utility scoring engine for rational action selection.
Governance scope: utility scoring, resource feasibility, and policy-based verdicts only.
No execution, no network, no mutation.
Dependencies: utility contracts, simulation contracts, core invariants.
Invariants:
  - Scoring is deterministic for the same inputs.
  - All scores and weights are bounded [0.0, 1.0].
  - No IO. No side effects. No mutation of external state.
  - Pure orchestration over immutable contract types.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.simulation import (
    RiskLevel,
    SimulationOption,
    SimulationVerdict,
)
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    DecisionPolicy,
    OptionUtility,
    ResourceBudget,
    ResourceType,
    TradeoffDirection,
    TradeoffRecord,
    UtilityProfile,
    UtilityVerdict,
)
from .invariants import stable_identifier


# --- Risk-level scoring map ---

_RISK_SCORE: dict[RiskLevel, float] = {
    RiskLevel.MINIMAL: 1.0,
    RiskLevel.LOW: 0.8,
    RiskLevel.MODERATE: 0.6,
    RiskLevel.HIGH: 0.3,
    RiskLevel.CRITICAL: 0.0,
}

# Risk severity ordering (mirrors simulation engine)
_RISK_SEVERITY: dict[RiskLevel, int] = {
    RiskLevel.MINIMAL: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}

# Normalization denominators for factor scoring
_COST_NORMALIZATION = 10_000.0  # cost in currency units → [0,1] via 1 - cost/N
_TIME_NORMALIZATION_SECONDS = 86_400.0  # duration in seconds → [0,1] via 1 - dur/N

_TRADEOFF_BONUS = 0.1


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _factor_contribution(
    factor: DecisionFactor,
    option: SimulationOption,
) -> float:
    """Compute the raw contribution of a single factor for a given option."""
    kind = factor.kind

    if kind == DecisionFactorKind.RISK:
        return _RISK_SCORE.get(option.risk_level, 0.5) * factor.value

    if kind == DecisionFactorKind.CONFIDENCE:
        return option.success_probability * factor.value

    if kind == DecisionFactorKind.COST:
        return max(0.0, 1.0 - option.estimated_cost / _COST_NORMALIZATION) * factor.value

    if kind == DecisionFactorKind.TIME:
        return max(0.0, 1.0 - option.estimated_duration_seconds / _TIME_NORMALIZATION_SECONDS) * factor.value

    # DEADLINE_PRESSURE, PROVIDER_HEALTH, OBLIGATION, CUSTOM
    return factor.value


def _tradeoff_bonus(
    direction: TradeoffDirection,
    contributions: dict[str, float],
    factors: tuple[DecisionFactor, ...],
    option: SimulationOption,
) -> float:
    """Compute the tradeoff direction bonus for an option."""
    if direction == TradeoffDirection.BALANCED:
        return 0.0

    if direction == TradeoffDirection.FAVOR_SPEED:
        # Bonus for options with high TIME contribution
        for f in factors:
            if f.kind == DecisionFactorKind.TIME:
                time_contrib = contributions.get(f.factor_id, 0.0)
                if time_contrib >= 0.5:
                    return _TRADEOFF_BONUS
        return 0.0

    if direction == TradeoffDirection.FAVOR_COST:
        # Bonus for cost-efficient options
        for f in factors:
            if f.kind == DecisionFactorKind.COST:
                cost_contrib = contributions.get(f.factor_id, 0.0)
                if cost_contrib >= 0.5:
                    return _TRADEOFF_BONUS
        return 0.0

    if direction == TradeoffDirection.FAVOR_SAFETY:
        # Bonus for low-risk options
        severity = _RISK_SEVERITY.get(option.risk_level, 2)
        if severity <= _RISK_SEVERITY[RiskLevel.LOW]:
            return _TRADEOFF_BONUS
        return 0.0

    return 0.0


class UtilityEngine:
    """Multi-factor utility scoring engine for rational action selection.

    Combines simulation results, resource budgets, decision factors, and
    policies to produce utility-ranked decisions with tradeoff explanations.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    @property
    def clock(self) -> Callable[[], str]:
        """Public accessor for the injected clock."""
        return self._clock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_options(
        self,
        profile: UtilityProfile,
        options: tuple[SimulationOption, ...],
    ) -> tuple[OptionUtility, ...]:
        """Score and rank options against a utility profile.

        For each option, computes raw and weighted scores from the profile's
        decision factors, applies tradeoff direction bonuses, and returns
        options sorted by weighted_score descending (tiebreak on option_id).
        """
        if not options:
            return ()

        factors = profile.factors
        # Collect intermediate scores before building validated contracts
        intermediates: list[tuple[str, float, float, dict[str, float]]] = []

        for option in options:
            contributions: dict[str, float] = {}
            for factor in factors:
                contributions[factor.factor_id] = _factor_contribution(factor, option)

            # Raw score: average of contributions
            num_factors = len(factors)
            raw_score = sum(contributions.values()) / num_factors if num_factors else 0.0

            # Weighted score: weighted average
            total_weight = sum(f.weight for f in factors)
            if total_weight > 0.0:
                weighted_score = sum(
                    f.weight * contributions[f.factor_id] for f in factors
                ) / total_weight
            else:
                weighted_score = raw_score

            # Apply tradeoff direction bonus
            bonus = _tradeoff_bonus(
                profile.tradeoff_direction, contributions, factors, option,
            )
            raw_score = _clamp(raw_score + bonus)
            weighted_score = _clamp(weighted_score + bonus)

            intermediates.append((option.option_id, raw_score, weighted_score, contributions))

        # Sort by weighted_score desc, tiebreak on option_id asc
        intermediates.sort(key=lambda t: (-t[2], t[0]))

        # Build ranked OptionUtility contracts (rank starts at 1)
        ranked: list[OptionUtility] = []
        for idx, (oid, raw, weighted, contribs) in enumerate(intermediates, start=1):
            ranked.append(OptionUtility(
                option_id=oid,
                raw_score=raw,
                weighted_score=weighted,
                factor_contributions=contribs,
                rank=idx,
            ))

        return tuple(ranked)

    def compare_options(
        self,
        profile: UtilityProfile,
        options: tuple[SimulationOption, ...],
    ) -> DecisionComparison:
        """Score options and build a DecisionComparison with spread."""
        if not options:
            raise ValueError("compare_options requires at least one option")

        scored = self.score_options(profile, options)
        best_score = scored[0].weighted_score
        worst_score = scored[-1].weighted_score
        spread = best_score - worst_score

        now = self._clock()
        comparison_id = stable_identifier("util-cmp", {
            "profile_id": profile.profile_id,
            "option_count": str(len(options)),
            "created_at": now,
        })

        return DecisionComparison(
            comparison_id=comparison_id,
            profile_id=profile.profile_id,
            option_utilities=scored,
            best_option_id=scored[0].option_id,
            spread=spread,
            decided_at=now,
        )

    def check_resource_feasibility(
        self,
        budgets: tuple[ResourceBudget, ...],
        estimated_cost: float,
    ) -> tuple[bool, tuple[str, ...]]:
        """Check whether estimated cost fits within BUDGET-type resources.

        Returns:
            A tuple of (feasible, reasons) where reasons lists any constraints
            that would be violated.
        """
        feasible = True
        reasons: list[str] = []

        for budget in budgets:
            if budget.resource_type != ResourceType.BUDGET:
                continue
            remaining = budget.total - budget.consumed - budget.reserved
            if estimated_cost > remaining:
                feasible = False
                reasons.append(
                    f"resource {budget.resource_id}: estimated cost {estimated_cost:.2f} "
                    f"exceeds remaining budget {remaining:.2f} "
                    f"(total={budget.total:.2f}, consumed={budget.consumed:.2f}, "
                    f"reserved={budget.reserved:.2f})"
                )

        return feasible, tuple(reasons)

    def apply_policy(
        self,
        comparison: DecisionComparison,
        policy: DecisionPolicy,
        simulation_verdict: SimulationVerdict | None = None,
        *,
        best_option_cost: float | None = None,
    ) -> UtilityVerdict:
        """Apply a decision policy to a comparison to produce a verdict.

        Checks minimum confidence, risk tolerance, and cost constraints.

        Args:
            best_option_cost: If provided, the estimated cost of the best option
                is checked against ``policy.max_cost``.
        """
        best = comparison.option_utilities[0]
        approved = True
        reasons: list[str] = []

        # Check minimum confidence
        if best.weighted_score < policy.min_confidence:
            approved = False
            reasons.append(
                f"best option score {best.weighted_score:.2f} "
                f"below min_confidence {policy.min_confidence:.2f}"
            )

        # Check risk from simulation verdict
        if simulation_verdict is not None:
            # Use confidence as risk proxy: low confidence = high risk
            risk_proxy = 1.0 - simulation_verdict.confidence
            if risk_proxy > policy.max_risk_tolerance:
                approved = False
                reasons.append(
                    f"risk proxy {risk_proxy:.2f} exceeds "
                    f"max_risk_tolerance {policy.max_risk_tolerance:.2f} "
                    f"— human review required"
                )

        # Check cost constraint
        if best_option_cost is not None and best_option_cost > policy.max_cost:
            approved = False
            reasons.append(
                f"estimated cost {best_option_cost:.2f} exceeds "
                f"max_cost {policy.max_cost:.2f}"
            )

        if approved and not reasons:
            if simulation_verdict is not None:
                reasons.append("all policy constraints satisfied")
            else:
                reasons.append("all evaluated policy constraints satisfied (no simulation verdict provided)")

        confidence = _clamp(best.weighted_score)

        now = self._clock()
        verdict_id = stable_identifier("util-verdict", {
            "comparison_id": comparison.comparison_id,
            "policy_id": policy.policy_id,
            "created_at": now,
        })

        return UtilityVerdict(
            verdict_id=verdict_id,
            comparison_id=comparison.comparison_id,
            policy_id=policy.policy_id,
            approved=approved,
            recommended_option_id=best.option_id,
            confidence=confidence,
            reasons=tuple(reasons),
            decided_at=now,
        )

    def full_utility_analysis(
        self,
        profile: UtilityProfile,
        options: tuple[SimulationOption, ...],
        policy: DecisionPolicy,
        simulation_verdict: SimulationVerdict | None = None,
        budgets: tuple[ResourceBudget, ...] | None = None,
    ) -> tuple[DecisionComparison, UtilityVerdict, TradeoffRecord]:
        """Orchestrate a complete utility analysis.

        Runs scoring, comparison, optional resource feasibility check, and
        policy application, then produces a tradeoff record explaining the
        final decision.

        Returns:
            A tuple of (comparison, verdict, tradeoff_record).
        """
        if not options:
            raise ValueError("full_utility_analysis requires at least one option")

        # Step 1: compare options
        comparison = self.compare_options(profile, options)

        # Look up the best option's SimulationOption for cost info
        best_sim_option = next(
            (o for o in options if o.option_id == comparison.best_option_id), None,
        )
        best_cost: float | None = (
            best_sim_option.estimated_cost if best_sim_option is not None else None
        )

        # Step 2: resource feasibility (if budgets provided)
        feasibility_reasons: list[str] = []
        if budgets is not None and best_sim_option is not None:
            feasible, budget_reasons = self.check_resource_feasibility(
                budgets, best_sim_option.estimated_cost,
            )
            feasibility_reasons.extend(budget_reasons)

        # Step 3: apply policy (pass cost of best option for max_cost check)
        verdict = self.apply_policy(
            comparison, policy, simulation_verdict,
            best_option_cost=best_cost,
        )

        # If budget infeasible, override approval
        if feasibility_reasons:
            verdict = UtilityVerdict(
                verdict_id=verdict.verdict_id,
                comparison_id=verdict.comparison_id,
                policy_id=verdict.policy_id,
                approved=False,
                recommended_option_id=verdict.recommended_option_id,
                confidence=verdict.confidence,
                reasons=verdict.reasons + tuple(feasibility_reasons),
                decided_at=verdict.decided_at,
            )

        # Step 4: build tradeoff record
        chosen_id = comparison.best_option_id
        rejected_ids = tuple(
            u.option_id for u in comparison.option_utilities
            if u.option_id != chosen_id
        )

        rationale_parts: list[str] = [
            f"chose {chosen_id} with weighted score "
            f"{comparison.option_utilities[0].weighted_score:.3f}",
        ]
        if comparison.spread > 0.0:
            rationale_parts.append(
                f"spread over alternatives: {comparison.spread:.3f}"
            )
        if feasibility_reasons:
            rationale_parts.append(
                f"budget concerns: {'; '.join(feasibility_reasons)}"
            )
        if not verdict.approved:
            rationale_parts.append("verdict: not approved — see reasons")
        else:
            rationale_parts.append("verdict: approved")

        now = self._clock()
        tradeoff_id = stable_identifier("util-tradeoff", {
            "comparison_id": comparison.comparison_id,
            "chosen_option_id": chosen_id,
            "created_at": now,
        })

        tradeoff = TradeoffRecord(
            tradeoff_id=tradeoff_id,
            comparison_id=comparison.comparison_id,
            chosen_option_id=chosen_id,
            rejected_option_ids=rejected_ids,
            tradeoff_direction=profile.tradeoff_direction,
            rationale="; ".join(rationale_parts),
            recorded_at=now,
        )

        return comparison, verdict, tradeoff
