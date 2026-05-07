"""Purpose: retention evaluation and pruning logic.
Governance scope: retention lifecycle management only.
Dependencies: retention contracts, invariant helpers.
Invariants:
  - Compliance-held artifacts MUST NOT be pruned.
  - Referenced artifacts MUST NOT be pruned.
  - Pruning is deterministic for identical inputs.
  - Results are fully auditable.
"""

from __future__ import annotations

from mcoi_runtime.contracts.retention import (
    ArtifactClass,
    PruneCandidate,
    PruneResult,
    PruneStatus,
    RetentionPolicy,
    RetentionStatus,
)
from .invariants import RuntimeCoreInvariantError


class RetentionEvaluator:
    """Evaluates artifacts against retention policies and produces prune decisions.

    Does NOT perform actual deletion — only produces typed decisions.
    Actual pruning is the caller's responsibility.
    """

    def __init__(self) -> None:
        self._policies: dict[ArtifactClass, RetentionPolicy] = {}

    def set_policy(self, policy: RetentionPolicy) -> None:
        if not isinstance(policy, RetentionPolicy):
            raise RuntimeCoreInvariantError("policy must be a RetentionPolicy instance")
        self._policies[policy.artifact_class] = policy

    def get_policy(self, artifact_class: ArtifactClass) -> RetentionPolicy | None:
        return self._policies.get(artifact_class)

    def evaluate(self, candidates: tuple[PruneCandidate, ...]) -> RetentionStatus:
        """Evaluate all candidates against their artifact class policies.

        Returns a RetentionStatus with per-artifact decisions.
        """
        results: list[PruneResult] = []
        pruned = 0
        skipped = 0
        failed = 0

        # Group by artifact class for count-based pruning
        class_groups: dict[ArtifactClass, list[PruneCandidate]] = {}
        for c in candidates:
            class_groups.setdefault(c.artifact_class, []).append(c)

        for candidate in candidates:
            result = self._evaluate_one(candidate, class_groups)
            results.append(result)
            if result.status is PruneStatus.PRUNED:
                pruned += 1
            elif result.status is PruneStatus.FAILED:
                failed += 1
            else:
                skipped += 1

        return RetentionStatus(
            evaluated_count=len(candidates),
            pruned_count=pruned,
            skipped_count=skipped,
            failed_count=failed,
            results=tuple(results),
        )

    def _evaluate_one(
        self,
        candidate: PruneCandidate,
        class_groups: dict[ArtifactClass, list[PruneCandidate]],
    ) -> PruneResult:
        # Compliance hold — never prune
        if candidate.compliance_hold:
            return PruneResult(
                artifact_id=candidate.artifact_id,
                status=PruneStatus.SKIPPED_COMPLIANCE,
                reason="artifact under compliance hold",
            )

        # Referenced — never prune
        if candidate.is_referenced:
            return PruneResult(
                artifact_id=candidate.artifact_id,
                status=PruneStatus.SKIPPED_REFERENCED,
                reason="artifact is referenced by other artifacts",
            )

        policy = self._policies.get(candidate.artifact_class)
        if policy is None:
            return PruneResult(
                artifact_id=candidate.artifact_id,
                status=PruneStatus.SKIPPED_COMPLIANCE,
                reason="no retention policy",
            )

        # Policy-level compliance hold
        if policy.compliance_hold:
            return PruneResult(
                artifact_id=candidate.artifact_id,
                status=PruneStatus.SKIPPED_COMPLIANCE,
                reason="policy has compliance hold enabled",
            )

        # Age-based pruning
        if policy.max_age_days > 0 and candidate.age_days > policy.max_age_days:
            return PruneResult(
                artifact_id=candidate.artifact_id,
                status=PruneStatus.PRUNED,
                reason="age exceeds retention limit",
            )

        # Count-based pruning (prune oldest beyond max_count)
        if policy.max_count > 0:
            group = class_groups.get(candidate.artifact_class, [])
            # Sort by age descending (oldest first) for deterministic pruning
            sorted_group = sorted(group, key=lambda c: -c.age_days)
            # Find index of this candidate
            excess = len(sorted_group) - policy.max_count
            if excess > 0:
                prune_ids = {c.artifact_id for c in sorted_group[:excess]}
                if candidate.artifact_id in prune_ids:
                    return PruneResult(
                        artifact_id=candidate.artifact_id,
                        status=PruneStatus.PRUNED,
                        reason="count exceeds retention limit",
                    )

        # Within retention bounds — keep
        return PruneResult(
            artifact_id=candidate.artifact_id,
            status=PruneStatus.SKIPPED_REFERENCED,
            reason="within retention bounds",
        )
