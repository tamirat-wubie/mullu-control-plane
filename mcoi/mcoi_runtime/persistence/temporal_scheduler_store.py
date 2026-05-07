"""Purpose: persistent storage for temporal scheduler state and run receipts.
Governance scope: scheduled temporal action snapshots and scheduler receipt
    persistence only.
Dependencies: temporal scheduler contracts and persistence errors.
Invariants:
  - Duplicate schedule ids overwrite only the current action snapshot.
  - Duplicate receipt ids are idempotent when payloads match.
  - File persistence writes deterministic JSON atomically.
  - Load fails closed on malformed temporal scheduler payloads.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from mcoi_runtime.contracts.temporal_runtime import (
    TemporalActionRequest,
    TemporalRiskLevel,
)
from mcoi_runtime.core.temporal_scheduler import (
    ScheduledActionState,
    ScheduledTemporalAction,
    ScheduleDecisionVerdict,
    TemporalRunReceipt,
)

from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


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
            _bounded_store_error("temporal scheduler store write failed", exc),
        ) from exc


def _action_request_to_json(action: TemporalActionRequest) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "tenant_id": action.tenant_id,
        "actor_id": action.actor_id,
        "action_type": action.action_type,
        "risk": action.risk.value,
        "requested_at": action.requested_at,
        "execute_at": action.execute_at,
        "not_before": action.not_before,
        "expires_at": action.expires_at,
        "approval_expires_at": action.approval_expires_at,
        "evidence_fresh_until": action.evidence_fresh_until,
        "retry_after": action.retry_after,
        "max_attempts": action.max_attempts,
        "attempt_count": action.attempt_count,
        "metadata": dict(action.metadata),
    }


def _action_request_from_json(raw: dict[str, Any]) -> TemporalActionRequest:
    if not isinstance(raw, dict):
        raise CorruptedDataError("temporal action request must be an object")
    try:
        return TemporalActionRequest(
            action_id=raw["action_id"],
            tenant_id=raw["tenant_id"],
            actor_id=raw["actor_id"],
            action_type=raw["action_type"],
            risk=TemporalRiskLevel(raw.get("risk", TemporalRiskLevel.LOW.value)),
            requested_at=raw["requested_at"],
            execute_at=raw.get("execute_at", ""),
            not_before=raw.get("not_before", ""),
            expires_at=raw.get("expires_at", ""),
            approval_expires_at=raw.get("approval_expires_at", ""),
            evidence_fresh_until=raw.get("evidence_fresh_until", ""),
            retry_after=raw.get("retry_after", ""),
            max_attempts=int(raw.get("max_attempts", 0)),
            attempt_count=int(raw.get("attempt_count", 0)),
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid temporal action request", exc),
        ) from exc


def _scheduled_action_to_json(action: ScheduledTemporalAction) -> dict[str, Any]:
    return {
        "schedule_id": action.schedule_id,
        "tenant_id": action.tenant_id,
        "action": _action_request_to_json(action.action),
        "execute_at": action.execute_at,
        "state": action.state.value,
        "handler_name": action.handler_name,
        "created_at": action.created_at,
        "updated_at": action.updated_at,
        "metadata": dict(action.metadata),
    }


def _scheduled_action_from_json(raw: dict[str, Any]) -> ScheduledTemporalAction:
    if not isinstance(raw, dict):
        raise CorruptedDataError("scheduled temporal action must be an object")
    try:
        return ScheduledTemporalAction(
            schedule_id=raw["schedule_id"],
            tenant_id=raw["tenant_id"],
            action=_action_request_from_json(raw["action"]),
            execute_at=raw["execute_at"],
            state=ScheduledActionState(raw.get("state", ScheduledActionState.PENDING.value)),
            handler_name=raw.get("handler_name", ""),
            created_at=raw.get("created_at", ""),
            updated_at=raw.get("updated_at", ""),
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid scheduled temporal action", exc),
        ) from exc


def _receipt_to_json(receipt: TemporalRunReceipt) -> dict[str, Any]:
    return {
        "receipt_id": receipt.receipt_id,
        "schedule_id": receipt.schedule_id,
        "tenant_id": receipt.tenant_id,
        "verdict": receipt.verdict.value,
        "reason": receipt.reason,
        "evaluated_at": receipt.evaluated_at,
        "worker_id": receipt.worker_id,
        "temporal_decision_id": receipt.temporal_decision_id,
        "temporal_verdict": receipt.temporal_verdict,
        "metadata": dict(receipt.metadata),
    }


def _receipt_from_json(raw: dict[str, Any]) -> TemporalRunReceipt:
    if not isinstance(raw, dict):
        raise CorruptedDataError("temporal run receipt must be an object")
    try:
        return TemporalRunReceipt(
            receipt_id=raw["receipt_id"],
            schedule_id=raw["schedule_id"],
            tenant_id=raw["tenant_id"],
            verdict=ScheduleDecisionVerdict(raw["verdict"]),
            reason=raw["reason"],
            evaluated_at=raw["evaluated_at"],
            worker_id=raw.get("worker_id", ""),
            temporal_decision_id=raw.get("temporal_decision_id", ""),
            temporal_verdict=raw.get("temporal_verdict", ""),
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid temporal run receipt", exc),
        ) from exc


class TemporalSchedulerStore:
    """In-memory store for scheduled temporal actions and receipts."""

    def __init__(self) -> None:
        self._actions: dict[str, ScheduledTemporalAction] = {}
        self._receipts: list[TemporalRunReceipt] = []
        self._receipt_by_id: dict[str, TemporalRunReceipt] = {}

    def save_action(self, action: ScheduledTemporalAction) -> ScheduledTemporalAction:
        if not isinstance(action, ScheduledTemporalAction):
            raise PersistenceError("action must be a ScheduledTemporalAction")
        self._actions[action.schedule_id] = action
        return action

    def save_actions(
        self,
        actions: Iterable[ScheduledTemporalAction],
    ) -> tuple[ScheduledTemporalAction, ...]:
        saved: list[ScheduledTemporalAction] = []
        for action in actions:
            saved.append(self.save_action(action))
        return tuple(saved)

    def get_action(self, schedule_id: str) -> ScheduledTemporalAction | None:
        return self._actions.get(schedule_id)

    def list_actions(
        self,
        *,
        tenant_id: str = "",
        state: ScheduledActionState | str | None = None,
    ) -> tuple[ScheduledTemporalAction, ...]:
        state_filter = ScheduledActionState(state) if state is not None else None
        return tuple(
            action
            for action in sorted(self._actions.values(), key=lambda item: item.schedule_id)
            if (not tenant_id or action.tenant_id == tenant_id)
            and (state_filter is None or action.state is state_filter)
        )

    def append_receipt(self, receipt: TemporalRunReceipt) -> TemporalRunReceipt:
        if not isinstance(receipt, TemporalRunReceipt):
            raise PersistenceError("receipt must be a TemporalRunReceipt")
        existing = self._receipt_by_id.get(receipt.receipt_id)
        if existing is not None:
            if _receipt_to_json(existing) != _receipt_to_json(receipt):
                raise PersistenceError("temporal receipt id collision")
            return existing
        self._receipts.append(receipt)
        self._receipt_by_id[receipt.receipt_id] = receipt
        return receipt

    def append_receipts(
        self,
        receipts: Iterable[TemporalRunReceipt],
    ) -> tuple[TemporalRunReceipt, ...]:
        appended: list[TemporalRunReceipt] = []
        for receipt in receipts:
            appended.append(self.append_receipt(receipt))
        return tuple(appended)

    def list_receipts(
        self,
        *,
        schedule_id: str = "",
        limit: int | None = None,
    ) -> tuple[TemporalRunReceipt, ...]:
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        receipts = [
            receipt
            for receipt in self._receipts
            if not schedule_id or receipt.schedule_id == schedule_id
        ]
        if limit is not None:
            receipts = receipts[-limit:]
        return tuple(receipts)

    def summary(self) -> dict[str, Any]:
        by_state = {state.value: 0 for state in ScheduledActionState}
        by_verdict = {verdict.value: 0 for verdict in ScheduleDecisionVerdict}
        for action in self._actions.values():
            by_state[action.state.value] += 1
        for receipt in self._receipts:
            by_verdict[receipt.verdict.value] += 1
        return {
            "action_count": len(self._actions),
            "receipt_count": len(self._receipts),
            "by_state": by_state,
            "by_verdict": by_verdict,
            "governed": True,
        }


class FileTemporalSchedulerStore(TemporalSchedulerStore):
    """JSON-file backed temporal scheduler store."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def save_action(self, action: ScheduledTemporalAction) -> ScheduledTemporalAction:
        saved = super().save_action(action)
        self._persist()
        return saved

    def save_actions(
        self,
        actions: Iterable[ScheduledTemporalAction],
    ) -> tuple[ScheduledTemporalAction, ...]:
        saved: list[ScheduledTemporalAction] = []
        changed = False
        for action in actions:
            before = self._actions.get(action.schedule_id)
            saved.append(super().save_action(action))
            changed = changed or before != action
        if changed:
            self._persist()
        return tuple(saved)

    def append_receipt(self, receipt: TemporalRunReceipt) -> TemporalRunReceipt:
        before_count = len(self._receipts)
        appended = super().append_receipt(receipt)
        if len(self._receipts) != before_count:
            self._persist()
        return appended

    def append_receipts(
        self,
        receipts: Iterable[TemporalRunReceipt],
    ) -> tuple[TemporalRunReceipt, ...]:
        appended: list[TemporalRunReceipt] = []
        changed = False
        for receipt in receipts:
            before_count = len(self._receipts)
            appended.append(super().append_receipt(receipt))
            changed = changed or len(self._receipts) != before_count
        if changed:
            self._persist()
        return tuple(appended)

    def _persist(self) -> None:
        payload = {
            "actions": [
                _scheduled_action_to_json(action)
                for action in sorted(self._actions.values(), key=lambda item: item.schedule_id)
            ],
            "receipts": [
                _receipt_to_json(receipt)
                for receipt in self._receipts
            ],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed temporal scheduler store file", exc),
            ) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("temporal scheduler store payload must be an object")
        actions_raw = raw.get("actions", [])
        receipts_raw = raw.get("receipts", [])
        if not isinstance(actions_raw, list):
            raise CorruptedDataError("temporal scheduler actions must be a list")
        if not isinstance(receipts_raw, list):
            raise CorruptedDataError("temporal scheduler receipts must be a list")
        for item in actions_raw:
            super().save_action(_scheduled_action_from_json(item))
        for item in receipts_raw:
            super().append_receipt(_receipt_from_json(item))
