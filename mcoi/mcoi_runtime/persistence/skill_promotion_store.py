"""Purpose: persistent storage for governed skill promotion evidence receipts.
Governance scope: skill lifecycle promotion receipt persistence and replay only.
Dependencies: skill promotion contracts, skill registry, and persistence errors.
Invariants:
  - Duplicate evidence ids are idempotent when payloads match.
  - Duplicate evidence ids with different payloads fail closed.
  - File persistence writes deterministic JSON atomically.
  - Restore prevalidates the full replay chain before mutating the registry.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.skill import SkillLifecycle, SkillPromotionDecision, SkillPromotionEvidence
from mcoi_runtime.core.skills import SkillRegistry

from ._serialization import loads_strict_json
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


_RESTORE_TRANSITIONS: dict[SkillLifecycle, frozenset[SkillLifecycle]] = {
    SkillLifecycle.CANDIDATE: frozenset({SkillLifecycle.PROVISIONAL}),
    SkillLifecycle.PROVISIONAL: frozenset({SkillLifecycle.VERIFIED}),
    SkillLifecycle.VERIFIED: frozenset({SkillLifecycle.TRUSTED}),
}
_VERIFICATION_REQUIRED_TARGETS = frozenset({SkillLifecycle.VERIFIED, SkillLifecycle.TRUSTED})


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(
            _bounded_store_error("skill promotion store write failed", exc),
        ) from exc


def _evidence_to_json(evidence: SkillPromotionEvidence) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "skill_id": evidence.skill_id,
        "target_lifecycle": evidence.target_lifecycle.value,
        "execution_record_ids": list(evidence.execution_record_ids),
        "evidence_refs": list(evidence.evidence_refs),
        "created_at": evidence.created_at,
        "verification_ids": list(evidence.verification_ids),
        "reason": evidence.reason,
    }


def _evidence_from_json(raw: object) -> SkillPromotionEvidence:
    if not isinstance(raw, dict):
        raise CorruptedDataError("skill promotion evidence must be an object")
    try:
        return SkillPromotionEvidence(
            evidence_id=raw["evidence_id"],
            skill_id=raw["skill_id"],
            target_lifecycle=SkillLifecycle(raw["target_lifecycle"]),
            execution_record_ids=tuple(raw["execution_record_ids"]),
            evidence_refs=tuple(raw["evidence_refs"]),
            created_at=raw["created_at"],
            verification_ids=tuple(raw.get("verification_ids", ())),
            reason=raw["reason"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid skill promotion evidence", exc),
        ) from exc


class SkillPromotionStore:
    """In-memory store for governed skill promotion evidence receipts."""

    def __init__(self) -> None:
        self._receipts: list[SkillPromotionEvidence] = []
        self._receipt_by_id: dict[str, SkillPromotionEvidence] = {}

    def append_receipt(self, receipt: SkillPromotionEvidence) -> SkillPromotionEvidence:
        if not isinstance(receipt, SkillPromotionEvidence):
            raise PersistenceError("receipt must be a SkillPromotionEvidence")
        existing = self._receipt_by_id.get(receipt.evidence_id)
        if existing is not None:
            if _evidence_to_json(existing) != _evidence_to_json(receipt):
                raise PersistenceError("skill promotion evidence id collision")
            return existing
        self._receipts.append(receipt)
        self._receipt_by_id[receipt.evidence_id] = receipt
        return receipt

    def append_receipts(
        self,
        receipts: Iterable[SkillPromotionEvidence],
    ) -> tuple[SkillPromotionEvidence, ...]:
        appended, new_receipts = self._preview_receipt_appends(receipts)
        for receipt in new_receipts:
            self._append_receipt_unchecked(receipt)
        return appended

    def _preview_receipt_appends(
        self,
        receipts: Iterable[SkillPromotionEvidence],
    ) -> tuple[tuple[SkillPromotionEvidence, ...], tuple[SkillPromotionEvidence, ...]]:
        appended: list[SkillPromotionEvidence] = []
        new_receipts: list[SkillPromotionEvidence] = []
        preview_by_id = dict(self._receipt_by_id)
        for receipt in receipts:
            if not isinstance(receipt, SkillPromotionEvidence):
                raise PersistenceError("receipt must be a SkillPromotionEvidence")
            existing = preview_by_id.get(receipt.evidence_id)
            if existing is not None:
                if _evidence_to_json(existing) != _evidence_to_json(receipt):
                    raise PersistenceError("skill promotion evidence id collision")
                appended.append(existing)
                continue
            preview_by_id[receipt.evidence_id] = receipt
            appended.append(receipt)
            new_receipts.append(receipt)
        return tuple(appended), tuple(new_receipts)

    def _append_receipt_unchecked(self, receipt: SkillPromotionEvidence) -> None:
        self._receipts.append(receipt)
        self._receipt_by_id[receipt.evidence_id] = receipt

    def append_decision(self, decision: SkillPromotionDecision) -> SkillPromotionEvidence | None:
        if not isinstance(decision, SkillPromotionDecision):
            raise PersistenceError("decision must be a SkillPromotionDecision")
        if not decision.approved or decision.evidence is None:
            return None
        return self.append_receipt(decision.evidence)

    def get_receipt(self, evidence_id: str) -> SkillPromotionEvidence | None:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise PersistenceError("evidence_id must be a non-empty string")
        return self._receipt_by_id.get(evidence_id)

    def list_receipts(
        self,
        *,
        skill_id: str = "",
        target_lifecycle: SkillLifecycle | str | None = None,
        limit: int | None = None,
    ) -> tuple[SkillPromotionEvidence, ...]:
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        if not isinstance(skill_id, str):
            raise PersistenceError("skill_id must be a string")
        try:
            lifecycle_filter = SkillLifecycle(target_lifecycle) if target_lifecycle is not None else None
        except ValueError as exc:
            raise PersistenceError("target_lifecycle must be a SkillLifecycle value") from exc
        receipts = [
            receipt
            for receipt in self._receipts
            if (not skill_id or receipt.skill_id == skill_id)
            and (lifecycle_filter is None or receipt.target_lifecycle is lifecycle_filter)
        ]
        if limit is not None:
            receipts = receipts[-limit:]
        return tuple(receipts)

    def restore_registry_state(self, registry: SkillRegistry) -> "SkillPromotionRuntimeState":
        """Replay promotion receipts into a fresh skill registry after prevalidation."""
        if not isinstance(registry, SkillRegistry):
            raise PersistenceError("registry must be a SkillRegistry instance")
        simulated_lifecycles: dict[str, SkillLifecycle] = {}
        restored_skill_ids: list[str] = []

        for receipt in self._receipts:
            descriptor = registry.get(receipt.skill_id)
            if descriptor is None:
                raise PersistenceError("skill promotion receipt references missing skill")
            if receipt.target_lifecycle in _VERIFICATION_REQUIRED_TARGETS and not receipt.verification_ids:
                raise CorruptedDataError("skill promotion receipt missing verification evidence")
            current_lifecycle = simulated_lifecycles.get(receipt.skill_id, descriptor.lifecycle)
            allowed_targets = _RESTORE_TRANSITIONS.get(current_lifecycle, frozenset())
            if receipt.target_lifecycle not in allowed_targets:
                raise PersistenceError("skill promotion restore transition invalid")
            simulated_lifecycles[receipt.skill_id] = receipt.target_lifecycle
            restored_skill_ids.append(receipt.skill_id)

        for receipt in self._receipts:
            registry.transition(receipt.skill_id, receipt.target_lifecycle)

        return SkillPromotionRuntimeState(
            receipts=tuple(self._receipts),
            restored_skill_ids=tuple(dict.fromkeys(restored_skill_ids)),
        )

    def summary(self) -> dict[str, Any]:
        by_lifecycle = {lifecycle.value: 0 for lifecycle in SkillLifecycle}
        by_skill: dict[str, int] = {}
        for receipt in self._receipts:
            by_lifecycle[receipt.target_lifecycle.value] += 1
            by_skill[receipt.skill_id] = by_skill.get(receipt.skill_id, 0) + 1
        return {
            "receipt_count": len(self._receipts),
            "by_lifecycle": by_lifecycle,
            "by_skill": dict(sorted(by_skill.items())),
            "governed": True,
        }


class FileSkillPromotionStore(SkillPromotionStore):
    """JSON-file backed skill promotion evidence receipt store."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def append_receipt(self, receipt: SkillPromotionEvidence) -> SkillPromotionEvidence:
        before_count = len(self._receipts)
        appended = super().append_receipt(receipt)
        if len(self._receipts) != before_count:
            self._persist()
        return appended

    def append_receipts(
        self,
        receipts: Iterable[SkillPromotionEvidence],
    ) -> tuple[SkillPromotionEvidence, ...]:
        appended, new_receipts = self._preview_receipt_appends(receipts)
        for receipt in new_receipts:
            self._append_receipt_unchecked(receipt)
        if new_receipts:
            self._persist()
        return appended

    def _persist(self) -> None:
        payload = {
            "version": "skill-promotion-store.v1",
            "receipts": [
                _evidence_to_json(receipt)
                for receipt in self._receipts
            ],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = loads_strict_json(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed skill promotion store file", exc),
            ) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("skill promotion store payload must be an object")
        if raw.get("version") not in (None, "skill-promotion-store.v1"):
            raise CorruptedDataError("unsupported skill promotion store version")
        receipts_raw = raw.get("receipts", [])
        if not isinstance(receipts_raw, list):
            raise CorruptedDataError("skill promotion receipts must be a list")
        for item in receipts_raw:
            super().append_receipt(_evidence_from_json(item))


@dataclass(frozen=True, slots=True)
class SkillPromotionRuntimeState:
    """Explicit snapshot of restored skill promotion receipt state."""

    receipts: tuple[SkillPromotionEvidence, ...]
    restored_skill_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(receipt, SkillPromotionEvidence) for receipt in self.receipts):
            raise PersistenceError("receipts must contain SkillPromotionEvidence instances only")
        if any(not isinstance(skill_id, str) or not skill_id.strip() for skill_id in self.restored_skill_ids):
            raise PersistenceError("restored_skill_ids must contain non-empty strings only")
