"""Purpose: persistent storage for finance approval packet pilot state.
Governance scope: invoice cases, policy decisions, approval receipts, and
effect receipts for governed finance packet read models and proof export.
Dependencies: finance approval packet contracts and persistence errors.
Invariants:
  - Case ids overwrite only the current case snapshot.
  - Receipt ids are idempotent only when payloads match.
  - File persistence writes deterministic JSON atomically.
  - Malformed payloads fail closed before exposing partial state.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.finance_approval_packet import (
    ApprovalStatus,
    EffectReceiptType,
    FinanceApprovalReceipt,
    FinanceEffectReceipt,
    FinancePacketRisk,
    FinancePacketState,
    FinancePolicyDecision,
    FinancePolicyVerdict,
    InvoiceCase,
    InvoiceMoney,
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
        raise PersistenceWriteError(_bounded_store_error("finance approval store write failed", exc)) from exc


def _case_to_json(case: InvoiceCase) -> dict[str, Any]:
    return case.to_json_dict()


def _case_from_json(raw: dict[str, Any]) -> InvoiceCase:
    if not isinstance(raw, dict):
        raise CorruptedDataError("finance packet case must be an object")
    try:
        amount = raw["amount"]
        return InvoiceCase(
            case_id=raw["case_id"],
            tenant_id=raw["tenant_id"],
            actor_id=raw["actor_id"],
            vendor_id=raw["vendor_id"],
            invoice_id=raw["invoice_id"],
            amount=InvoiceMoney(currency=amount["currency"], minor_units=int(amount["minor_units"])),
            source_evidence_ref=raw["source_evidence_ref"],
            state=FinancePacketState(raw["state"]),
            risk=FinancePacketRisk(raw["risk"]),
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
            policy_decision_refs=tuple(raw.get("policy_decision_refs", [])),
            approval_refs=tuple(raw.get("approval_refs", [])),
            effect_refs=tuple(raw.get("effect_refs", [])),
            closure_certificate_id=raw.get("closure_certificate_id"),
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid finance packet case", exc)) from exc


def _decision_from_json(raw: dict[str, Any]) -> FinancePolicyDecision:
    if not isinstance(raw, dict):
        raise CorruptedDataError("finance policy decision must be an object")
    try:
        return FinancePolicyDecision(
            decision_id=raw["decision_id"],
            case_id=raw["case_id"],
            tenant_id=raw["tenant_id"],
            verdict=FinancePolicyVerdict(raw["verdict"]),
            reasons=tuple(raw["reasons"]),
            required_controls=tuple(raw.get("required_controls", [])),
            evidence_refs=tuple(raw.get("evidence_refs", [])),
            created_at=raw["created_at"],
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid finance policy decision", exc)) from exc


def _approval_from_json(raw: dict[str, Any]) -> FinanceApprovalReceipt:
    if not isinstance(raw, dict):
        raise CorruptedDataError("finance approval receipt must be an object")
    try:
        return FinanceApprovalReceipt(
            approval_id=raw["approval_id"],
            case_id=raw["case_id"],
            tenant_id=raw["tenant_id"],
            approver_id=raw["approver_id"],
            approver_role=raw["approver_role"],
            status=ApprovalStatus(raw["status"]),
            decided_at=raw["decided_at"],
            evidence_refs=tuple(raw.get("evidence_refs", [])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid finance approval receipt", exc)) from exc


def _effect_from_json(raw: dict[str, Any]) -> FinanceEffectReceipt:
    if not isinstance(raw, dict):
        raise CorruptedDataError("finance effect receipt must be an object")
    try:
        return FinanceEffectReceipt(
            effect_id=raw["effect_id"],
            case_id=raw["case_id"],
            tenant_id=raw["tenant_id"],
            effect_type=EffectReceiptType(raw["effect_type"]),
            capability_id=raw["capability_id"],
            dispatched_at=raw["dispatched_at"],
            evidence_refs=tuple(raw["evidence_refs"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid finance effect receipt", exc)) from exc


class FinanceApprovalPacketStore:
    """In-memory store for finance approval packet pilot state."""

    def __init__(self) -> None:
        self._cases: dict[str, InvoiceCase] = {}
        self._decisions: dict[str, FinancePolicyDecision] = {}
        self._approvals: dict[str, FinanceApprovalReceipt] = {}
        self._effects: dict[str, FinanceEffectReceipt] = {}

    def save_case(self, case: InvoiceCase) -> InvoiceCase:
        if not isinstance(case, InvoiceCase):
            raise PersistenceError("case must be an InvoiceCase")
        self._cases[case.case_id] = case
        return case

    def get_case(self, case_id: str) -> InvoiceCase | None:
        return self._cases.get(case_id)

    def list_cases(
        self,
        *,
        tenant_id: str = "",
        state: FinancePacketState | str | None = None,
    ) -> tuple[InvoiceCase, ...]:
        state_filter = FinancePacketState(state) if state is not None else None
        return tuple(
            case
            for case in sorted(self._cases.values(), key=lambda item: item.case_id)
            if (not tenant_id or case.tenant_id == tenant_id)
            and (state_filter is None or case.state is state_filter)
        )

    def append_decision(self, decision: FinancePolicyDecision) -> FinancePolicyDecision:
        if not isinstance(decision, FinancePolicyDecision):
            raise PersistenceError("decision must be a FinancePolicyDecision")
        existing = self._decisions.get(decision.decision_id)
        if existing is not None:
            if existing.to_json_dict() != decision.to_json_dict():
                raise PersistenceError("finance policy decision id collision")
            return existing
        self._decisions[decision.decision_id] = decision
        return decision

    def append_approval(self, approval: FinanceApprovalReceipt) -> FinanceApprovalReceipt:
        if not isinstance(approval, FinanceApprovalReceipt):
            raise PersistenceError("approval must be a FinanceApprovalReceipt")
        existing = self._approvals.get(approval.approval_id)
        if existing is not None:
            if existing.to_json_dict() != approval.to_json_dict():
                raise PersistenceError("finance approval id collision")
            return existing
        self._approvals[approval.approval_id] = approval
        return approval

    def append_effect(self, effect: FinanceEffectReceipt) -> FinanceEffectReceipt:
        if not isinstance(effect, FinanceEffectReceipt):
            raise PersistenceError("effect must be a FinanceEffectReceipt")
        existing = self._effects.get(effect.effect_id)
        if existing is not None:
            if existing.to_json_dict() != effect.to_json_dict():
                raise PersistenceError("finance effect id collision")
            return existing
        self._effects[effect.effect_id] = effect
        return effect

    def list_decisions(self, *, case_id: str = "") -> tuple[FinancePolicyDecision, ...]:
        return tuple(
            decision
            for decision in sorted(self._decisions.values(), key=lambda item: item.decision_id)
            if not case_id or decision.case_id == case_id
        )

    def list_approvals(self, *, case_id: str = "") -> tuple[FinanceApprovalReceipt, ...]:
        return tuple(
            approval
            for approval in sorted(self._approvals.values(), key=lambda item: item.approval_id)
            if not case_id or approval.case_id == case_id
        )

    def list_effects(self, *, case_id: str = "") -> tuple[FinanceEffectReceipt, ...]:
        return tuple(
            effect
            for effect in sorted(self._effects.values(), key=lambda item: item.effect_id)
            if not case_id or effect.case_id == case_id
        )

    def summary(self) -> dict[str, Any]:
        by_state = {state.value: 0 for state in FinancePacketState}
        for case in self._cases.values():
            by_state[case.state.value] += 1
        return {
            "case_count": len(self._cases),
            "decision_count": len(self._decisions),
            "approval_count": len(self._approvals),
            "effect_count": len(self._effects),
            "by_state": by_state,
            "governed": True,
        }


class FileFinanceApprovalPacketStore(FinanceApprovalPacketStore):
    """JSON-file backed finance approval packet store."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def save_case(self, case: InvoiceCase) -> InvoiceCase:
        saved = super().save_case(case)
        self._persist()
        return saved

    def append_decision(self, decision: FinancePolicyDecision) -> FinancePolicyDecision:
        before = len(self._decisions)
        appended = super().append_decision(decision)
        if len(self._decisions) != before:
            self._persist()
        return appended

    def append_approval(self, approval: FinanceApprovalReceipt) -> FinanceApprovalReceipt:
        before = len(self._approvals)
        appended = super().append_approval(approval)
        if len(self._approvals) != before:
            self._persist()
        return appended

    def append_effect(self, effect: FinanceEffectReceipt) -> FinanceEffectReceipt:
        before = len(self._effects)
        appended = super().append_effect(effect)
        if len(self._effects) != before:
            self._persist()
        return appended

    def _persist(self) -> None:
        payload = {
            "cases": [_case_to_json(case) for case in sorted(self._cases.values(), key=lambda item: item.case_id)],
            "decisions": [
                decision.to_json_dict()
                for decision in sorted(self._decisions.values(), key=lambda item: item.decision_id)
            ],
            "approvals": [
                approval.to_json_dict()
                for approval in sorted(self._approvals.values(), key=lambda item: item.approval_id)
            ],
            "effects": [
                effect.to_json_dict()
                for effect in sorted(self._effects.values(), key=lambda item: item.effect_id)
            ],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed finance approval store file", exc)) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("finance approval store payload must be an object")
        for key in ("cases", "decisions", "approvals", "effects"):
            if not isinstance(raw.get(key, []), list):
                raise CorruptedDataError(f"finance approval {key} must be a list")
        for item in raw.get("cases", []):
            super().save_case(_case_from_json(item))
        for item in raw.get("decisions", []):
            super().append_decision(_decision_from_json(item))
        for item in raw.get("approvals", []):
            super().append_approval(_approval_from_json(item))
        for item in raw.get("effects", []):
            super().append_effect(_effect_from_json(item))
