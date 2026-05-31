"""Framework-neutral runtime API for governed note memory.

Purpose: expose note memory mesh operations through JSON-compatible request
and response envelopes for CLIs, HTTP adapters, and local control-plane wiring.
Governance scope: typed boundary validation, append-only note persistence,
retrieval guard enforcement, retrieval receipts, expiry, rejected-delta
evidence, and Phi_gov promotion receipt checks.
Dependencies: dataclasses, pathlib, runtime invariant helpers, and note memory
mesh primitives.
Invariants: every rejected request returns an explicit governed envelope,
lookup and retrieval do not mutate state, and MemoryAnchor writes route through
promotion receipts only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.note_memory_mesh import (
    EpisodeCapsuleDraft,
    NoteAction,
    NoteKind,
    NoteMemoryDraft,
    NoteMemoryMesh,
    NoteScope,
    PhiGovStatus,
    PromotionReceipt,
    ProofState,
    RetrievalGuard,
    TrustZone,
)


@dataclass(frozen=True)
class NoteMemoryEnvelope:
    """JSON-compatible governed note memory response envelope."""

    governed: bool
    ok: bool
    status: str
    payload: Mapping[str, Any]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible response."""

        return {
            "governed": self.governed,
            "ok": self.ok,
            "status": self.status,
            "payload": _jsonable(dict(self.payload)),
            "error": self.error,
        }


class NoteMemoryRuntime:
    """Runtime facade for governed note memory mesh operations."""

    def __init__(self, mesh: NoteMemoryMesh) -> None:
        self.mesh = mesh

    @classmethod
    def from_path(cls, path: str | Path) -> "NoteMemoryRuntime":
        """Create a runtime facade backed by a note memory store directory."""

        return cls(NoteMemoryMesh(Path(path)))

    def capture_note(self, request_body: Mapping[str, Any]) -> NoteMemoryEnvelope:
        """Validate and capture one governed note event."""

        try:
            event = self.mesh.capture_note(_draft_from_mapping(request_body))
            return _ok("captured", {"event": event.to_dict()})
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def record_rejected_delta(self, request_body: Mapping[str, Any]) -> NoteMemoryEnvelope:
        """Record a durable rejected-delta note."""

        try:
            event = self.mesh.record_rejected_delta(
                content_summary=_required_text(request_body, "content_summary", alias="summary"),
                source_ref=_required_text(request_body, "source_ref"),
                scope=NoteScope(str(request_body.get("scope", NoteScope.TASK.value))),
                evidence_refs=_text_tuple(request_body.get("evidence_refs")),
            )
            return _ok("rejected_delta_recorded", {"event": event.to_dict()})
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def capture_episode_capsule(self, request_body: Mapping[str, Any]) -> NoteMemoryEnvelope:
        """Capture one structured post-episode capsule."""

        try:
            event = self.mesh.capture_episode_capsule(_episode_capsule_from_mapping(request_body))
            return _ok("episode_capsule_captured", {"event": event.to_dict()})
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def retrieve_notes(self, request_body: Mapping[str, Any]) -> NoteMemoryEnvelope:
        """Retrieve guard-approved notes without mutating lineage."""

        try:
            query = _required_text(request_body, "query")
            result = self.mesh.retrieve_notes_with_receipt(query, _retrieval_guard_from_mapping(request_body))
            return _ok(
                "retrieved",
                {
                    "count": len(result.notes),
                    "notes": [_jsonable(note) for note in result.notes],
                    "receipt": _jsonable(result.receipt),
                },
            )
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def expire_temporary_notes(self, request_body: Mapping[str, Any] | None = None) -> NoteMemoryEnvelope:
        """Expire temporary notes whose TTL has passed."""

        try:
            body = request_body or {}
            report = self.mesh.expire_temporary_notes(_optional_text(body, "now"))
            return _ok("expired", {"report": _jsonable(report)})
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def queue_promotion(self, request_body: Mapping[str, Any]) -> NoteMemoryEnvelope:
        """Queue a source note for Phi_gov promotion review."""

        try:
            promotion_id = self.mesh.queue_promotion(_required_text(request_body, "note_id"))
            return _ok("promotion_queued", {"promotion_id": promotion_id})
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def promote_memory_anchor(self, request_body: Mapping[str, Any]) -> NoteMemoryEnvelope:
        """Promote a validated note into a MemoryAnchor."""

        try:
            note_id = _required_text(request_body, "note_id")
            receipt_body = request_body.get("receipt")
            if not isinstance(receipt_body, Mapping):
                raise ValueError("receipt must be an object")
            receipt = _promotion_receipt_from_mapping(receipt_body)
            event = self.mesh.promote_memory_anchor(note_id, receipt)
            return _ok("promoted", {"event": event.to_dict(), "receipt": receipt.to_dict()})
        except (KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def rebuild_index(self) -> NoteMemoryEnvelope:
        """Validate note event logs and report projection fitness."""

        try:
            return _ok("rebuilt", {"report": _jsonable(self.mesh.rebuild_index_from_events())})
        except (OSError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def list_events(self) -> NoteMemoryEnvelope:
        """List persisted note memory events in append order."""

        try:
            events = self.mesh.list_events(skip_invalid=False)
            return _ok("listed", {"count": len(events), "events": [event.to_dict() for event in events]})
        except (OSError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)

    def dashboard_snapshot(self, request_body: Mapping[str, Any] | None = None) -> NoteMemoryEnvelope:
        """Return a read-only operator dashboard snapshot for note memory."""

        try:
            body = request_body or {}
            limit = _optional_int(body, "limit", default=25)
            now = _optional_text(body, "now")
            retrieval_receipt_ref = _optional_text(body, "retrieval_receipt_ref")
            retrieval_citing_note_ref = _optional_text(body, "retrieval_citing_note_ref")
            return _ok(
                "dashboard_snapshot",
                self.mesh.dashboard_snapshot(
                    now=now,
                    limit=limit,
                    retrieval_receipt_ref=retrieval_receipt_ref,
                    retrieval_citing_note_ref=retrieval_citing_note_ref,
                ),
            )
        except (OSError, KeyError, TypeError, ValueError, RuntimeCoreInvariantError) as exc:
            return _rejected(exc)


def _draft_from_mapping(value: Mapping[str, Any]) -> NoteMemoryDraft:
    return NoteMemoryDraft(
        kind=NoteKind(_required_text(value, "kind")),
        action=NoteAction(str(value.get("action", NoteAction.CREATE.value))),
        scope=NoteScope(_required_text(value, "scope")),
        content_summary=_required_text(value, "content_summary", alias="summary"),
        source_ref=_required_text(value, "source_ref"),
        proof_state=ProofState(_required_text(value, "proof_state")),
        trust_zone=TrustZone(_required_text(value, "trust_zone")),
        expires_at=str(value["expires_at"]) if value.get("expires_at") else None,
        note_id=str(value.get("note_id", "")),
        evidence_refs=_text_tuple(value.get("evidence_refs")),
        relation_refs=_text_tuple(value.get("relation_refs")),
        retrieval_receipt_refs=_text_tuple(value.get("retrieval_receipt_refs")),
        claim_key=str(value.get("claim_key", "")),
        claim_value=str(value.get("claim_value", "")),
    )


def _episode_capsule_from_mapping(value: Mapping[str, Any]) -> EpisodeCapsuleDraft:
    return EpisodeCapsuleDraft(
        goal=_required_text(value, "goal"),
        scope=NoteScope(_required_text(value, "scope")),
        proof_state=ProofState(_required_text(value, "proof_state")),
        trust_zone=TrustZone(_required_text(value, "trust_zone")),
        constraints=_text_tuple(value.get("constraints")),
        decisions=_text_tuple(value.get("decisions")),
        changed_files=_text_tuple(value.get("changed_files")),
        verification_refs=_text_tuple(value.get("verification_refs")),
        open_risks=_text_tuple(value.get("open_risks")),
        evidence_refs=_text_tuple(value.get("evidence_refs")),
        relation_refs=_text_tuple(value.get("relation_refs")),
        episode_id=str(value.get("episode_id", "")),
    )


def _retrieval_guard_from_mapping(value: Mapping[str, Any]) -> RetrievalGuard:
    allowed_trust_zones = _enum_tuple(
        value.get("allowed_trust_zones"),
        TrustZone,
        default=(TrustZone.LOCAL, TrustZone.WORKSPACE),
    )
    allowed_proof_states = _enum_tuple(
        value.get("allowed_proof_states"),
        ProofState,
        default=(ProofState.PASS,),
    )
    return RetrievalGuard(
        allowed_trust_zones=allowed_trust_zones,
        allowed_proof_states=allowed_proof_states,
        scope=NoteScope(scope) if (scope := _optional_text(value, "scope")) else None,
        now=_optional_text(value, "now"),
        include_hypotheses=_optional_bool(value, "include_hypotheses", default=False),
    )


def _promotion_receipt_from_mapping(value: Mapping[str, Any]) -> PromotionReceipt:
    return PromotionReceipt(
        promotion_id=_required_text(value, "promotion_id"),
        source_note_id=_required_text(value, "source_note_id"),
        anchor_id=_required_text(value, "anchor_id"),
        proof_state=ProofState(_required_text(value, "proof_state")),
        evidence_refs=_text_tuple(value.get("evidence_refs")),
        contradiction_scan=ProofState(_required_text(value, "contradiction_scan")),
        phi_gov_status=PhiGovStatus(_required_text(value, "phi_gov_status")),
        accepted_at=_required_text(value, "accepted_at"),
        accepted_by=_required_text(value, "accepted_by"),
        lineage_event_seq=_required_int(value, "lineage_event_seq"),
    )


def _required_text(value: Mapping[str, Any], field_name: str, *, alias: str | None = None) -> str:
    if field_name in value:
        raw_value = value[field_name]
    elif alias is not None and alias in value:
        raw_value = value[alias]
    else:
        raise KeyError(f"missing field: {field_name}")
    text = str(raw_value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: Mapping[str, Any], field_name: str) -> str | None:
    raw_value = value.get(field_name)
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string")
    text = raw_value.strip()
    return text or None


def _optional_int(value: Mapping[str, Any], field_name: str, *, default: int) -> int:
    raw_value = value.get(field_name, default)
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return raw_value


def _required_int(value: Mapping[str, Any], field_name: str) -> int:
    if field_name not in value:
        raise KeyError(f"missing field: {field_name}")
    raw_value = value[field_name]
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return raw_value


def _optional_bool(value: Mapping[str, Any], field_name: str, *, default: bool) -> bool:
    raw_value = value.get(field_name, default)
    if not isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return raw_value


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("expected a string list")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _enum_tuple(value: Any, enum_type: type[Enum], *, default: tuple[Any, ...]) -> tuple[Any, ...]:
    if value is None:
        return default
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("expected an enum string list")
    return tuple(enum_type(str(item)) for item in value)


def _ok(status: str, payload: Mapping[str, Any]) -> NoteMemoryEnvelope:
    return NoteMemoryEnvelope(governed=True, ok=True, status=status, payload=payload)


def _rejected(exc: Exception) -> NoteMemoryEnvelope:
    return NoteMemoryEnvelope(governed=True, ok=False, status="rejected", payload={}, error=str(exc))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value
