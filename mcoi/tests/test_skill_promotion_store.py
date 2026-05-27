"""Tests for governed skill promotion evidence receipt persistence.

Purpose: verify promotion receipts persist deterministically and replay safely.
Governance scope: skill lifecycle promotion evidence store.
Dependencies: skill promotion contracts, skill registry, and persistence store.
Invariants:
  - Duplicate matching receipts are idempotent.
  - Duplicate mismatched receipts fail closed.
  - File-backed receipts round-trip after restart.
  - Restore rejects malformed replay chains before mutation.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    SkillClass,
    SkillDescriptor,
    SkillLifecycle,
    SkillPromotionDecision,
    SkillPromotionEvidence,
    TrustClass,
    VerificationStrength,
)
from mcoi_runtime.core.skills import SkillRegistry
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.persistence.skill_promotion_store import (
    FileSkillPromotionStore,
    SkillPromotionStore,
)


FIXED_CLOCK = "2026-05-27T16:00:00+00:00"


def _receipt(
    *,
    evidence_id: str = "promotion-evidence-1",
    skill_id: str = "skill.promote",
    target_lifecycle: SkillLifecycle = SkillLifecycle.PROVISIONAL,
    execution_record_ids: tuple[str, ...] = ("record-1",),
    evidence_refs: tuple[str, ...] = ("execution-1",),
    verification_ids: tuple[str, ...] = (),
    reason: str = "successful_execution_evidence",
) -> SkillPromotionEvidence:
    return SkillPromotionEvidence(
        evidence_id=evidence_id,
        skill_id=skill_id,
        target_lifecycle=target_lifecycle,
        execution_record_ids=execution_record_ids,
        evidence_refs=evidence_refs,
        verification_ids=verification_ids,
        created_at=FIXED_CLOCK,
        reason=reason,
    )


def _registry_with_skill(
    *,
    skill_id: str = "skill.promote",
    lifecycle: SkillLifecycle = SkillLifecycle.CANDIDATE,
) -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        SkillDescriptor(
            skill_id=skill_id,
            name="Promotion candidate",
            skill_class=SkillClass.PRIMITIVE,
            effect_class=EffectClass.INTERNAL_PURE,
            determinism_class=DeterminismClass.DETERMINISTIC,
            trust_class=TrustClass.TRUSTED_INTERNAL,
            verification_strength=VerificationStrength.STRONG,
            lifecycle=lifecycle,
        )
    )
    return registry


def test_memory_store_appends_filters_and_deduplicates_receipts() -> None:
    store = SkillPromotionStore()
    first = _receipt()
    second = _receipt(
        evidence_id="promotion-evidence-2",
        skill_id="skill.other",
        target_lifecycle=SkillLifecycle.VERIFIED,
        verification_ids=("verification-2",),
    )

    assert store.append_receipt(first) is first
    assert store.append_receipt(first) is first
    assert store.append_receipt(second) is second
    assert store.get_receipt(first.evidence_id) is first
    assert store.list_receipts(skill_id="skill.promote") == (first,)
    assert store.list_receipts(target_lifecycle=SkillLifecycle.VERIFIED) == (second,)
    assert store.list_receipts(limit=1) == (second,)
    assert store.summary()["receipt_count"] == 2


def test_duplicate_receipt_id_with_different_payload_fails_closed() -> None:
    store = SkillPromotionStore()
    first = _receipt()
    forged = _receipt(evidence_id=first.evidence_id, evidence_refs=("execution-forged",))

    store.append_receipt(first)

    with pytest.raises(PersistenceError, match="evidence id collision"):
        store.append_receipt(forged)
    assert store.list_receipts() == (first,)
    assert store.summary()["receipt_count"] == 1


def test_append_receipts_rejects_batch_collision_without_partial_mutation() -> None:
    store = SkillPromotionStore()
    first = _receipt()
    forged = _receipt(evidence_id=first.evidence_id, evidence_refs=("execution-forged",))

    with pytest.raises(PersistenceError, match="evidence id collision"):
        store.append_receipts((first, forged))

    assert store.list_receipts() == ()
    assert store.get_receipt(first.evidence_id) is None
    assert store.summary()["receipt_count"] == 0


def test_list_receipts_rejects_invalid_filters_with_bounded_errors() -> None:
    store = SkillPromotionStore()
    receipt = _receipt()
    store.append_receipt(receipt)

    with pytest.raises(PersistenceError, match="target_lifecycle"):
        store.list_receipts(target_lifecycle="rogue")
    with pytest.raises(PersistenceError, match="limit"):
        store.list_receipts(limit=0)

    assert store.summary()["receipt_count"] == 1
    assert store.list_receipts(skill_id="skill.promote") == (receipt,)


def test_append_decision_persists_only_approved_promotion_evidence() -> None:
    store = SkillPromotionStore()
    receipt = _receipt()
    approved = SkillPromotionDecision(
        skill_id=receipt.skill_id,
        from_lifecycle=SkillLifecycle.CANDIDATE,
        target_lifecycle=receipt.target_lifecycle,
        approved=True,
        reason=receipt.reason,
        evidence=receipt,
    )
    rejected = SkillPromotionDecision(
        skill_id=receipt.skill_id,
        from_lifecycle=SkillLifecycle.CANDIDATE,
        target_lifecycle=SkillLifecycle.PROVISIONAL,
        approved=False,
        reason="execution_evidence_missing",
    )

    assert store.append_decision(rejected) is None
    assert store.append_decision(approved) is receipt
    assert store.list_receipts() == (receipt,)
    assert store.summary()["by_lifecycle"][SkillLifecycle.PROVISIONAL.value] == 1


def test_file_store_round_trips_promotion_receipts(tmp_path) -> None:
    path = tmp_path / "skill_promotion_receipts.json"
    store = FileSkillPromotionStore(path)
    first = _receipt()
    second = _receipt(
        evidence_id="promotion-evidence-2",
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.VERIFIED,
        verification_ids=("verification-2",),
    )

    store.append_receipt(first)
    store.append_receipt(second)
    reloaded = FileSkillPromotionStore(path)

    assert reloaded.list_receipts() == (first, second)
    assert reloaded.get_receipt("promotion-evidence-2") == second
    assert reloaded.summary()["receipt_count"] == 2
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == "skill-promotion-store.v1"


def test_file_store_rejects_batch_collision_without_partial_memory_or_file_write(tmp_path) -> None:
    path = tmp_path / "skill_promotion_receipts.json"
    store = FileSkillPromotionStore(path)
    first = _receipt()
    forged = _receipt(evidence_id=first.evidence_id, evidence_refs=("execution-forged",))

    with pytest.raises(PersistenceError, match="evidence id collision"):
        store.append_receipts((first, forged))

    assert store.list_receipts() == ()
    assert store.summary()["receipt_count"] == 0
    assert not path.exists()


def test_file_store_rejects_malformed_promotion_receipt_payload(tmp_path) -> None:
    path = tmp_path / "skill_promotion_receipts.json"
    path.write_text(
        json.dumps(
            {
                "version": "skill-promotion-store.v1",
                "receipts": [{"evidence_id": "incomplete"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CorruptedDataError, match="invalid skill promotion evidence"):
        FileSkillPromotionStore(path)
    assert path.exists()
    assert "incomplete" in path.read_text(encoding="utf-8")


def test_restore_registry_state_replays_receipts_after_prevalidation() -> None:
    store = SkillPromotionStore()
    provisional = _receipt()
    verified = _receipt(
        evidence_id="promotion-evidence-verified",
        target_lifecycle=SkillLifecycle.VERIFIED,
        execution_record_ids=("record-2",),
        evidence_refs=("execution-2", "verification-2"),
        verification_ids=("verification-2",),
        reason="verified_execution_evidence",
    )
    registry = _registry_with_skill()

    store.append_receipts((provisional, verified))
    state = store.restore_registry_state(registry)

    assert registry.get("skill.promote").lifecycle is SkillLifecycle.VERIFIED
    assert state.receipts == (provisional, verified)
    assert state.restored_skill_ids == ("skill.promote",)


def test_restore_registry_state_rejects_invalid_chain_without_mutation() -> None:
    store = SkillPromotionStore()
    invalid = _receipt(
        evidence_id="promotion-evidence-invalid",
        target_lifecycle=SkillLifecycle.VERIFIED,
        verification_ids=("verification-1",),
    )
    registry = _registry_with_skill()

    store.append_receipt(invalid)

    with pytest.raises(PersistenceError, match="restore transition invalid"):
        store.restore_registry_state(registry)
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.CANDIDATE
    assert store.list_receipts() == (invalid,)


def test_restore_registry_state_rejects_verified_receipt_without_verification_evidence() -> None:
    store = SkillPromotionStore()
    provisional = _receipt()
    invalid_verified = _receipt(
        evidence_id="promotion-evidence-invalid-verified",
        target_lifecycle=SkillLifecycle.VERIFIED,
        execution_record_ids=("record-2",),
        evidence_refs=("execution-2",),
    )
    registry = _registry_with_skill()

    store.append_receipts((provisional, invalid_verified))

    with pytest.raises(CorruptedDataError, match="verification evidence"):
        store.restore_registry_state(registry)
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.CANDIDATE
    assert store.summary()["receipt_count"] == 2
