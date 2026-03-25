"""Purpose: decision learning integration bridge — connects decision learning to utility and knowledge.
Governance scope: decision learning invocation for post-decision feedback cycles.
Dependencies: decision learning engine, utility engine, learning engine, utility contracts,
    decision learning contracts, simulation contracts.
Invariants:
  - Bridge methods are stateless static helpers (except where engine state is updated).
  - Each method composes existing engine calls.
  - No graph mutation. No side effects beyond engine-internal learning state.
  - Learning never bypasses policy, approval, or review rules.
  - All adjustments are bounded and auditable.
"""

from __future__ import annotations

from .invariants import stable_identifier
from mcoi_runtime.contracts.decision_learning import (
    DecisionAdjustment,
    DecisionOutcomeRecord,
    OutcomeQuality,
    PreferenceSignal,
    ProviderPreference,
    TradeoffOutcome,
    UtilityLearningRecord,
)
from mcoi_runtime.contracts.simulation import SimulationOption
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    TradeoffDirection,
    TradeoffRecord,
    UtilityProfile,
)
from .decision_learning import DecisionLearningEngine
from .learning import LearningEngine
from .utility import UtilityEngine


class DecisionLearningBridge:
    """Bridges decision learning with the utility and knowledge subsystems.

    Provides convenience methods for:
    - Running a full feedback cycle after a decision completes
    - Applying learned adjustments to a UtilityProfile for future decisions
    - Propagating decision outcomes to the knowledge learning engine
    - Surfacing provider preferences for cost routing
    """

    @staticmethod
    def feedback_after_decision(
        decision_engine: DecisionLearningEngine,
        comparison: DecisionComparison,
        chosen_option: SimulationOption,
        profile: UtilityProfile,
        tradeoff: TradeoffRecord,
        *,
        quality: OutcomeQuality,
        actual_cost: float,
        actual_duration_seconds: float,
        success_observed: bool,
        notes: str,
        alternative_better: bool = False,
    ) -> UtilityLearningRecord:
        """Run a full feedback cycle after a decision has been executed.

        Orchestrates outcome recording, signal generation, adjustment
        computation, and tradeoff assessment in one call.
        """
        return decision_engine.full_learning_cycle(
            comparison=comparison,
            chosen_option=chosen_option,
            profile=profile,
            tradeoff=tradeoff,
            quality=quality,
            actual_cost=actual_cost,
            actual_duration_seconds=actual_duration_seconds,
            success_observed=success_observed,
            notes=notes,
            alternative_better=alternative_better,
        )

    @staticmethod
    def apply_learned_weights(
        decision_engine: DecisionLearningEngine,
        profile: UtilityProfile,
        clock_now: str,
    ) -> UtilityProfile:
        """Create an updated UtilityProfile with learned weight adjustments applied.

        Reads the cumulative factor adjustments from the learning engine and
        produces a new profile with updated factor weights, preserving the
        original profile's structure and identity.

        Returns the original profile unchanged if no adjustments exist.
        """
        adjustments = decision_engine.get_learned_factor_adjustments()
        if not adjustments:
            return profile

        updated_factors: list[DecisionFactor] = []
        any_changed = False

        for factor in profile.factors:
            kind_str = factor.kind.value
            delta = adjustments.get(kind_str, 0.0)
            if delta == 0.0:
                updated_factors.append(factor)
                continue

            new_weight = max(0.0, min(1.0, factor.weight + delta))
            if new_weight != factor.weight:
                any_changed = True
            updated_factors.append(DecisionFactor(
                factor_id=factor.factor_id,
                kind=factor.kind,
                weight=new_weight,
                value=factor.value,
                label=factor.label,
            ))

        if not any_changed:
            return profile

        # Check total weight is still > 0
        total_weight = sum(f.weight for f in updated_factors)
        if total_weight <= 0.0:
            return profile  # Refuse to create a zero-weight profile


        new_profile_id = stable_identifier("profile-learned", {
            "base_profile_id": profile.profile_id,
            "created_at": clock_now,
        })

        return UtilityProfile(
            profile_id=new_profile_id,
            context_type=profile.context_type,
            context_id=profile.context_id,
            factors=tuple(updated_factors),
            tradeoff_direction=profile.tradeoff_direction,
            created_at=clock_now,
        )

    @staticmethod
    def propagate_to_knowledge_learning(
        learning_engine: LearningEngine,
        outcome: DecisionOutcomeRecord,
        knowledge_id: str,
    ) -> None:
        """Propagate a decision outcome to the knowledge learning engine.

        Updates confidence in the knowledge artifact based on decision success,
        and records a lesson from the decision experience.
        """
        weight = 0.1 if outcome.quality in (OutcomeQuality.SUCCESS, OutcomeQuality.FAILURE) else 0.05
        success = outcome.quality == OutcomeQuality.SUCCESS

        learning_engine.update_confidence(
            knowledge_id=knowledge_id,
            outcome_success=success,
            weight=weight,
        )

        learning_engine.record_lesson(
            source_id=outcome.outcome_id,
            context=f"decision for {outcome.comparison_id}",
            action=f"chose option {outcome.chosen_option_id}",
            outcome=outcome.quality.value,
            lesson=outcome.notes,
        )

    @staticmethod
    def get_preferred_providers(
        decision_engine: DecisionLearningEngine,
        context_type: str,
        provider_ids: tuple[str, ...],
        *,
        min_samples: int = 3,
    ) -> tuple[tuple[str, float], ...]:
        """Get providers ranked by learned preference for a context.

        Returns a tuple of (provider_id, score) sorted by score descending,
        filtered to providers with at least min_samples observations.
        """
        results: list[tuple[str, float]] = []
        for pid in provider_ids:
            pref = decision_engine.get_provider_preference(pid, context_type)
            if pref is not None and pref.sample_count >= min_samples:
                results.append((pid, pref.score))
        results.sort(key=lambda t: (-t[1], t[0]))
        return tuple(results)
