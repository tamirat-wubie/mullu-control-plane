"""Purpose: append-only internal evidence store for nested-mind observation flow.
Governance scope: runtime-local nested-mind evidence persistence only; no public schema.
Dependencies: nested-mind runtime contracts and deterministic JSON serialization.
Invariants:
  - Records are append-only and duplicate identifiers are rejected.
  - Raw bearer tokens and raw response bodies are forbidden.
  - Payload storage is limited to typed contract JSON and bounded hashes.
  - Queries are read-only projections by mind_id or Mullu receipt hash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from mcoi_runtime.contracts._base import ContractRecord
from mcoi_runtime.contracts.nested_mind_observation_reconciliation import (
    NestedMindObservationReconciliationReport,
    NestedMindObservationReconciliationStatus,
)
from mcoi_runtime.contracts.nested_mind_observation_submission import (
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
)
from mcoi_runtime.contracts.nested_mind_receipts import (
    NestedMindCommitWitness,
    NestedMindCommitWitnessStatus,
    NestedMindReceiptBridgeReport,
    NestedMindReceiptBridgeStatus,
)

from ._serialization import loads_strict_json
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError

_RECORD_TYPES = {
    "plan",
    "submission_report",
    "commit_witness",
    "bridge_report",
    "reconciliation_report",
}
_ENTRY_FIELDS = {
    "record_type",
    "record_id",
    "mind_id",
    "mullu_receipt_hash",
    "payload",
}
_PAYLOAD_ID_FIELDS = {
    "plan": "plan_id",
    "submission_report": "report_id",
    "commit_witness": "witness_id",
    "bridge_report": "report_id",
    "reconciliation_report": "report_id",
}
_FORBIDDEN_KEY_FRAGMENTS = (
    "bearer",
    "authorization",
    "access_token",
    "refresh_token",
    "raw_response_body",
    "response_body",
    "raw_body",
)


@dataclass(frozen=True, slots=True)
class NestedMindEvidenceEntry:
    record_type: str
    record_id: str
    mind_id: str
    mullu_receipt_hash: str | None
    payload: Mapping[str, Any]


class NestedMindEvidenceStore:
    """Append-only JSONL store for nested-mind observation evidence."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path")
        self._path = path
        self._entries: list[NestedMindEvidenceEntry] = []
        self._ids: set[str] = set()
        self._load_existing()

    def record_plan(self, plan: NestedMindObservationProposalPlan) -> None:
        self._append("plan", plan.plan_id, plan.mind_id, plan.mullu_receipt_hash, plan)

    def record_submission_report(self, report: NestedMindObservationSubmissionReport) -> None:
        self._append(
            "submission_report",
            report.report_id,
            report.mind_id,
            None,
            report,
        )

    def record_commit_witness(self, witness: NestedMindCommitWitness) -> None:
        self._append(
            "commit_witness",
            witness.witness_id,
            witness.mind_id,
            witness.mullu_receipt_hash,
            witness,
        )

    def record_bridge_report(self, report: NestedMindReceiptBridgeReport) -> None:
        self._append("bridge_report", report.report_id, report.mind_id, None, report)

    def record_reconciliation_report(self, report: NestedMindObservationReconciliationReport) -> None:
        self._append("reconciliation_report", report.report_id, report.mind_id, None, report)

    def list_by_mind_id(self, mind_id: str) -> tuple[NestedMindEvidenceEntry, ...]:
        return tuple(entry for entry in self._entries if entry.mind_id == mind_id)

    def list_all(self) -> tuple[NestedMindEvidenceEntry, ...]:
        return tuple(self._entries)

    def list_by_mullu_receipt_hash(self, mullu_receipt_hash: str) -> tuple[NestedMindEvidenceEntry, ...]:
        return tuple(
            entry for entry in self._entries if entry.mullu_receipt_hash == mullu_receipt_hash
        )

    def _append(
        self,
        record_type: str,
        record_id: str,
        mind_id: str,
        mullu_receipt_hash: str | None,
        record: ContractRecord,
    ) -> None:
        if record_type not in _RECORD_TYPES:
            raise PersistenceError("unsupported nested-mind evidence record type")
        if record_id in self._ids:
            raise PersistenceWriteError("nested-mind evidence record already exists")
        payload = record.to_json_dict()
        _reject_forbidden_payload_on_write(payload)
        entry = NestedMindEvidenceEntry(
            record_type=record_type,
            record_id=record_id,
            mind_id=mind_id,
            mullu_receipt_hash=mullu_receipt_hash,
            payload=payload,
        )
        line = _entry_to_json(entry)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
                stream.write("\n")
        except OSError as exc:
            raise PersistenceWriteError("nested-mind evidence append failed") from exc
        self._entries.append(entry)
        self._ids.add(record_id)

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CorruptedDataError("nested-mind evidence store read failed") from exc
        for line in lines:
            if not line.strip():
                continue
            try:
                raw = loads_strict_json(line)
            except (CorruptedDataError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise CorruptedDataError("invalid nested-mind evidence entry") from exc
            if not isinstance(raw, dict):
                raise CorruptedDataError("nested-mind evidence entry must be an object")
            entry = _entry_from_raw(raw)
            if entry.record_id in self._ids:
                raise CorruptedDataError("duplicate nested-mind evidence id in store")
            _reject_forbidden_payload_on_read(entry.payload)
            self._entries.append(entry)
            self._ids.add(entry.record_id)


def _entry_to_json(entry: NestedMindEvidenceEntry) -> str:
    return json.dumps(
        {
            "record_type": entry.record_type,
            "record_id": entry.record_id,
            "mind_id": entry.mind_id,
            "mullu_receipt_hash": entry.mullu_receipt_hash,
            "payload": entry.payload,
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _entry_from_raw(raw: Mapping[str, Any]) -> NestedMindEvidenceEntry:
    if set(raw) - _ENTRY_FIELDS:
        raise CorruptedDataError("nested-mind evidence entry has unexpected fields")
    record_type = raw.get("record_type")
    record_id = raw.get("record_id")
    mind_id = raw.get("mind_id")
    payload = raw.get("payload")
    mullu_receipt_hash = raw.get("mullu_receipt_hash")
    if record_type not in _RECORD_TYPES:
        raise CorruptedDataError("unsupported nested-mind evidence record type")
    if not isinstance(record_id, str) or not record_id:
        raise CorruptedDataError("nested-mind evidence record_id required")
    if not isinstance(mind_id, str) or not mind_id:
        raise CorruptedDataError("nested-mind evidence mind_id required")
    if mullu_receipt_hash is not None and not isinstance(mullu_receipt_hash, str):
        raise CorruptedDataError("nested-mind evidence mullu_receipt_hash must be text")
    if not isinstance(payload, Mapping):
        raise CorruptedDataError("nested-mind evidence payload must be object")
    payload_id = payload.get(_PAYLOAD_ID_FIELDS[str(record_type)])
    if payload_id != record_id:
        raise CorruptedDataError("nested-mind evidence record_id payload mismatch")
    if payload.get("mind_id") != mind_id:
        raise CorruptedDataError("nested-mind evidence mind_id payload mismatch")
    if payload.get("mullu_receipt_hash") != mullu_receipt_hash:
        raise CorruptedDataError("nested-mind evidence mullu_receipt_hash payload mismatch")
    validated_payload = _validate_payload_contract(str(record_type), payload)
    return NestedMindEvidenceEntry(
        record_type=record_type,
        record_id=record_id,
        mind_id=mind_id,
        mullu_receipt_hash=mullu_receipt_hash,
        payload=validated_payload,
    )


def _validate_payload_contract(record_type: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        payload_dict = dict(payload)
        if record_type == "plan":
            payload_dict["status"] = NestedMindObservationProposalPlanStatus(
                str(payload_dict["status"])
            )
            return NestedMindObservationProposalPlan(**payload_dict).to_json_dict()
        if record_type == "submission_report":
            payload_dict["status"] = NestedMindObservationSubmissionStatus(
                str(payload_dict["status"])
            )
            return NestedMindObservationSubmissionReport(**payload_dict).to_json_dict()
        if record_type == "commit_witness":
            payload_dict["status"] = NestedMindCommitWitnessStatus(str(payload_dict["status"]))
            return NestedMindCommitWitness(**payload_dict).to_json_dict()
        if record_type == "bridge_report":
            payload_dict["status"] = NestedMindReceiptBridgeStatus(str(payload_dict["status"]))
            return NestedMindReceiptBridgeReport(**payload_dict).to_json_dict()
        if record_type == "reconciliation_report":
            payload_dict["status"] = NestedMindObservationReconciliationStatus(
                str(payload_dict["status"])
            )
            return NestedMindObservationReconciliationReport(**payload_dict).to_json_dict()
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError("nested-mind evidence payload contract invalid") from exc
    raise CorruptedDataError("unsupported nested-mind evidence record type")


def _reject_forbidden_payload_on_write(value: Any) -> None:
    _reject_forbidden_payload(
        value,
        error=PersistenceWriteError("nested-mind evidence contains forbidden sensitive field"),
    )


def _reject_forbidden_payload_on_read(value: Any) -> None:
    _reject_forbidden_payload(
        value,
        error=CorruptedDataError("nested-mind evidence contains forbidden sensitive field"),
    )


def _reject_forbidden_payload(value: Any, *, error: Exception) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in _FORBIDDEN_KEY_FRAGMENTS):
                raise error
            _reject_forbidden_payload(item, error=error)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _reject_forbidden_payload(item, error=error)
