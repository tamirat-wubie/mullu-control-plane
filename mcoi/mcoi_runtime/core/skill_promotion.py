"""Purpose: evidence-bound skill lifecycle promotion gate.
Governance scope: skill promotion decisions and registry transition admission only.
Dependencies: skill contracts, skill registry, and deterministic invariant helpers.
Invariants:
  - A lifecycle promotion requires successful execution evidence.
  - Verified and trusted promotions require verification evidence.
  - The gate never grants new capability authority; it only applies registry transitions.
  - Rejected promotion deltas return bounded reasons instead of mutating registry state.
"""

from __future__ import annotations

from collections.abc import Iterable

from mcoi_runtime.contracts.skill import (
    SkillExecutionRecord,
    SkillLifecycle,
    SkillOutcomeStatus,
    SkillPromotionDecision,
    SkillPromotionEvidence,
)
from mcoi_runtime.core.invariants import ensure_iso_timestamp, ensure_non_empty_text, stable_identifier
from mcoi_runtime.core.skills import SkillRegistry


_VERIFICATION_REQUIRED_TARGETS = frozenset({SkillLifecycle.VERIFIED, SkillLifecycle.TRUSTED})
_TRUSTED_MINIMUM_RECORD_COUNT = 2
_TRUSTED_MINIMUM_VERIFICATION_COUNT = 2
_PROMOTION_TRANSITIONS: dict[SkillLifecycle, frozenset[SkillLifecycle]] = {
    SkillLifecycle.CANDIDATE: frozenset({SkillLifecycle.PROVISIONAL}),
    SkillLifecycle.PROVISIONAL: frozenset({SkillLifecycle.VERIFIED}),
    SkillLifecycle.VERIFIED: frozenset({SkillLifecycle.TRUSTED}),
}


def promote_skill_with_evidence(
    registry: SkillRegistry,
    *,
    skill_id: str,
    target_lifecycle: SkillLifecycle,
    execution_records: tuple[SkillExecutionRecord, ...],
    created_at: str,
) -> SkillPromotionDecision:
    """Evaluate evidence and apply one registry lifecycle transition when approved."""
    decision = evaluate_skill_promotion(
        registry,
        skill_id=skill_id,
        target_lifecycle=target_lifecycle,
        execution_records=execution_records,
        created_at=created_at,
    )
    if decision.approved:
        registry.transition(skill_id, target_lifecycle)
    return decision


def evaluate_skill_promotion(
    registry: SkillRegistry,
    *,
    skill_id: str,
    target_lifecycle: SkillLifecycle,
    execution_records: tuple[SkillExecutionRecord, ...],
    created_at: str,
) -> SkillPromotionDecision:
    """Return a bounded promotion decision without mutating the registry."""
    ensure_non_empty_text("skill_id", skill_id)
    ensure_iso_timestamp("created_at", created_at)
    if not isinstance(target_lifecycle, SkillLifecycle):
        raise TypeError("target_lifecycle must be a SkillLifecycle value")
    if not isinstance(execution_records, tuple):
        raise TypeError("execution_records must be a tuple")

    descriptor = registry.get(skill_id)
    if descriptor is None:
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=SkillLifecycle.BLOCKED,
            target_lifecycle=target_lifecycle,
            reason="skill_not_found",
        )
    if target_lifecycle not in _PROMOTION_TRANSITIONS.get(descriptor.lifecycle, frozenset()):
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=descriptor.lifecycle,
            target_lifecycle=target_lifecycle,
            reason="invalid_lifecycle_transition",
        )

    matching_records = tuple(record for record in execution_records if record.skill_id == skill_id)
    if len(matching_records) != len(execution_records):
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=descriptor.lifecycle,
            target_lifecycle=target_lifecycle,
            reason="execution_record_skill_mismatch",
        )

    successful_records = tuple(
        record
        for record in matching_records
        if record.outcome.status is SkillOutcomeStatus.SUCCEEDED
    )
    if not successful_records:
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=descriptor.lifecycle,
            target_lifecycle=target_lifecycle,
            reason="successful_execution_missing",
        )

    execution_record_ids = tuple(record.record_id for record in successful_records)
    execution_evidence_refs = _execution_evidence_refs(successful_records)
    verification_ids = _verification_ids(successful_records)

    if not execution_evidence_refs:
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=descriptor.lifecycle,
            target_lifecycle=target_lifecycle,
            reason="execution_evidence_missing",
        )
    if target_lifecycle in _VERIFICATION_REQUIRED_TARGETS and not verification_ids:
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=descriptor.lifecycle,
            target_lifecycle=target_lifecycle,
            reason="verification_evidence_missing",
        )
    if (
        target_lifecycle is SkillLifecycle.TRUSTED
        and (
            len(successful_records) < _TRUSTED_MINIMUM_RECORD_COUNT
            or len(verification_ids) < _TRUSTED_MINIMUM_VERIFICATION_COUNT
        )
    ):
        return _rejected(
            skill_id=skill_id,
            from_lifecycle=descriptor.lifecycle,
            target_lifecycle=target_lifecycle,
            reason="trusted_repetition_evidence_missing",
        )

    evidence_reason = _promotion_reason(target_lifecycle)
    evidence = SkillPromotionEvidence(
        evidence_id=stable_identifier(
            "skill-promotion-evidence",
            {
                "skill_id": skill_id,
                "target_lifecycle": target_lifecycle.value,
                "execution_record_ids": execution_record_ids,
                "evidence_refs": execution_evidence_refs,
                "verification_ids": verification_ids,
                "created_at": created_at,
            },
        ),
        skill_id=skill_id,
        target_lifecycle=target_lifecycle,
        execution_record_ids=execution_record_ids,
        evidence_refs=execution_evidence_refs,
        verification_ids=verification_ids,
        created_at=created_at,
        reason=evidence_reason,
    )
    return SkillPromotionDecision(
        skill_id=skill_id,
        from_lifecycle=descriptor.lifecycle,
        target_lifecycle=target_lifecycle,
        approved=True,
        reason=evidence_reason,
        evidence=evidence,
    )


def _promotion_reason(target_lifecycle: SkillLifecycle) -> str:
    if target_lifecycle is SkillLifecycle.PROVISIONAL:
        return "successful_execution_evidence"
    if target_lifecycle is SkillLifecycle.VERIFIED:
        return "verified_execution_evidence"
    if target_lifecycle is SkillLifecycle.TRUSTED:
        return "repeated_verified_execution_evidence"
    return "promotion_evidence"


def _execution_evidence_refs(records: Iterable[SkillExecutionRecord]) -> tuple[str, ...]:
    refs: list[str] = []
    for record in records:
        refs.extend(
            ref
            for ref in (
                record.outcome.execution_id,
                record.outcome.verification_id,
                record.trace_id,
                record.replay_id,
                record.runbook_id,
            )
            if ref is not None
        )
        for step in record.outcome.step_outcomes:
            refs.extend(
                ref
                for ref in (
                    step.execution_id,
                    step.verification_id,
                )
                if ref is not None
            )
    return tuple(dict.fromkeys(refs))


def _verification_ids(records: Iterable[SkillExecutionRecord]) -> tuple[str, ...]:
    refs: list[str] = []
    for record in records:
        if record.outcome.verification_id is not None:
            refs.append(record.outcome.verification_id)
        for step in record.outcome.step_outcomes:
            if step.verification_id is not None:
                refs.append(step.verification_id)
    return tuple(dict.fromkeys(refs))


def _rejected(
    *,
    skill_id: str,
    from_lifecycle: SkillLifecycle,
    target_lifecycle: SkillLifecycle,
    reason: str,
) -> SkillPromotionDecision:
    return SkillPromotionDecision(
        skill_id=skill_id,
        from_lifecycle=from_lifecycle,
        target_lifecycle=target_lifecycle,
        approved=False,
        reason=reason,
    )
