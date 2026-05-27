"""Tests for operator-facing skill promotion receipt read models.

Purpose: verify persisted skill promotion evidence is visible without mutation.
Governance scope: operator read-only promotion receipt inspection.
Dependencies: operator loop, promotion store, view model, and console renderer.
Invariants:
  - Read model does not require or perform registry mutation.
  - Missing receipt storage is reported as a bounded structured error.
  - Filters and limits are deterministic.
  - Console output exposes counts and identifiers without raw persistence errors.
"""

from __future__ import annotations

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.console import render_skill_promotion_receipts
from mcoi_runtime.app.operator_loop import OperatorLoop
from mcoi_runtime.app.skill_promotion_read_models import SkillPromotionReceiptReadRequest
from mcoi_runtime.app.view_models import SkillPromotionReceiptReadView
from mcoi_runtime.contracts.skill import SkillLifecycle, SkillPromotionEvidence
from mcoi_runtime.persistence.skill_promotion_store import SkillPromotionStore


FIXED_CLOCK = "2026-05-27T16:00:00+00:00"


def _receipt(
    *,
    evidence_id: str,
    skill_id: str = "skill.promote",
    target_lifecycle: SkillLifecycle = SkillLifecycle.PROVISIONAL,
) -> SkillPromotionEvidence:
    return SkillPromotionEvidence(
        evidence_id=evidence_id,
        skill_id=skill_id,
        target_lifecycle=target_lifecycle,
        execution_record_ids=(f"{evidence_id}-record",),
        evidence_refs=(f"{evidence_id}-execution",),
        verification_ids=(
            (f"{evidence_id}-verification",)
            if target_lifecycle is not SkillLifecycle.PROVISIONAL
            else ()
        ),
        created_at=FIXED_CLOCK,
        reason="successful_execution_evidence",
    )


def test_read_model_reports_missing_store_as_bounded_error() -> None:
    loop = OperatorLoop(runtime=bootstrap_runtime(clock=lambda: FIXED_CLOCK))

    report = loop.read_skill_promotion_receipts(
        SkillPromotionReceiptReadRequest(
            request_id="read-missing-store",
            subject_id="operator-1",
        )
    )
    view = SkillPromotionReceiptReadView.from_report(report)
    rendered = render_skill_promotion_receipts(view)

    assert report.store_configured is False
    assert report.receipt_count == 0
    assert report.errors[0].error_code == "skill_promotion_store_missing"
    assert "skill promotion receipt store is not configured" in rendered


def test_read_model_filters_limits_and_renders_receipts() -> None:
    store = SkillPromotionStore()
    store.append_receipts(
        (
            _receipt(evidence_id="promotion-evidence-1"),
            _receipt(
                evidence_id="promotion-evidence-2",
                target_lifecycle=SkillLifecycle.VERIFIED,
            ),
            _receipt(evidence_id="promotion-evidence-other", skill_id="skill.other"),
        )
    )
    loop = OperatorLoop(
        runtime=bootstrap_runtime(
            clock=lambda: FIXED_CLOCK,
            skill_promotion_store=store,
        )
    )

    report = loop.read_skill_promotion_receipts(
        SkillPromotionReceiptReadRequest(
            request_id="read-promotions",
            subject_id="operator-1",
            skill_id="skill.promote",
            limit=1,
        )
    )
    view = SkillPromotionReceiptReadView.from_report(report)
    rendered = render_skill_promotion_receipts(view)

    assert report.store_configured is True
    assert report.receipt_count == 1
    assert report.receipts[0].evidence_id == "promotion-evidence-2"
    assert view.receipts[0].target_lifecycle == "verified"
    assert "promotion-evidence-2" in rendered
    assert "promotion-evidence-other" not in rendered
