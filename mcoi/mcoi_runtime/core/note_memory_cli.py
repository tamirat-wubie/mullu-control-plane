"""CLI adapter for governed note memory mesh operations.

Purpose: expose note capture, episode capsule capture, retrieval, expiry,
rejected-delta recording, promotion queueing, MemoryAnchor promotion, event
listing, dashboard snapshots, and index rebuild over governed JSON envelopes.
Governance scope: command-line boundary only; redaction, ProofState gates,
append-only persistence, retrieval guards, and Phi_gov receipt checks remain
owned by note_memory_mesh.py.
Dependencies: argparse, dataclasses, json, pathlib, and note memory mesh.
Invariants: commands do not bypass note governance, retrievals emit read-only
receipts, and rejected operations return nonzero status with explicit causal
context.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
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


def build_parser() -> argparse.ArgumentParser:
    """Build the governed note memory CLI parser."""

    parser = argparse.ArgumentParser(prog="mcoi-notes", description="Governed note memory mesh commands")
    parser.add_argument("--note-store", required=True, help="Directory for append-only note memory mesh storage")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="Capture one governed note event")
    capture_parser.add_argument("--kind", required=True, choices=[kind.value for kind in NoteKind])
    capture_parser.add_argument("--scope", required=True, choices=[scope.value for scope in NoteScope])
    capture_parser.add_argument("--summary", required=True, help="Bounded note summary")
    capture_parser.add_argument("--source-ref", required=True, help="Causal source reference")
    capture_parser.add_argument("--proof-state", required=True, choices=[state.value for state in ProofState])
    capture_parser.add_argument("--trust-zone", required=True, choices=[zone.value for zone in TrustZone])
    capture_parser.add_argument("--expires-at", help="Required for temporary note kinds")
    capture_parser.add_argument("--note-id", default="", help="Optional caller-provided note id")
    capture_parser.add_argument("--action", choices=[action.value for action in NoteAction], default=NoteAction.CREATE.value)
    capture_parser.add_argument("--evidence-ref", action="append", help="Evidence reference")
    capture_parser.add_argument("--relation-ref", action="append", help="Related note id or event id")
    capture_parser.add_argument("--retrieval-receipt-ref", action="append", help="Retrieval receipt that influenced this note")
    capture_parser.add_argument("--claim-key", default="", help="Optional deterministic contradiction claim key")
    capture_parser.add_argument("--claim-value", default="", help="Optional deterministic contradiction claim value")

    episode_parser = subparsers.add_parser("capture-episode", help="Capture one structured post-episode capsule")
    episode_parser.add_argument("--goal", required=True, help="Episode goal summary")
    episode_parser.add_argument("--scope", required=True, choices=[scope.value for scope in NoteScope])
    episode_parser.add_argument("--proof-state", required=True, choices=[state.value for state in ProofState])
    episode_parser.add_argument("--trust-zone", required=True, choices=[zone.value for zone in TrustZone])
    episode_parser.add_argument("--episode-id", default="", help="Optional bounded episode id")
    episode_parser.add_argument("--constraint", action="append", help="Bounded episode constraint")
    episode_parser.add_argument("--decision", action="append", help="Bounded episode decision")
    episode_parser.add_argument("--changed-file", action="append", help="Changed file witness")
    episode_parser.add_argument("--verification-ref", action="append", help="Verification command or witness")
    episode_parser.add_argument("--open-risk", action="append", help="Open risk witness")
    episode_parser.add_argument("--evidence-ref", action="append", help="Evidence reference")
    episode_parser.add_argument("--relation-ref", action="append", help="Related note id or event id")

    reject_parser = subparsers.add_parser("record-rejected-delta", help="Record durable negative evidence")
    reject_parser.add_argument("--summary", required=True, help="Rejected delta summary")
    reject_parser.add_argument("--source-ref", required=True, help="Causal source reference")
    reject_parser.add_argument("--scope", choices=[scope.value for scope in NoteScope], default=NoteScope.TASK.value)
    reject_parser.add_argument("--evidence-ref", action="append", help="Evidence reference")

    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve guard-approved notes")
    retrieve_parser.add_argument("query", help="Whitespace-separated query terms")
    retrieve_parser.add_argument("--scope", choices=[scope.value for scope in NoteScope])
    retrieve_parser.add_argument("--allowed-trust-zone", action="append", choices=[zone.value for zone in TrustZone])
    retrieve_parser.add_argument("--allowed-proof-state", action="append", choices=[state.value for state in ProofState])
    retrieve_parser.add_argument("--include-hypotheses", action="store_true", help="Allow Unknown notes for sensing guidance")
    retrieve_parser.add_argument("--now", help="Override retrieval clock timestamp")

    expire_parser = subparsers.add_parser("expire", help="Expire temporary notes past TTL")
    expire_parser.add_argument("--now", help="Override expiry clock timestamp")

    queue_parser = subparsers.add_parser("queue-promotion", help="Queue a promotable note for Phi_gov review")
    queue_parser.add_argument("note_id", help="Source note id")

    promote_parser = subparsers.add_parser("promote", help="Promote a note to MemoryAnchor using a Phi_gov receipt")
    promote_parser.add_argument("--note-id", required=True, help="Source note id")
    promote_parser.add_argument("--receipt", required=True, help="Inline receipt JSON object or path")

    dashboard_parser = subparsers.add_parser("dashboard", help="Return a read-only operator dashboard snapshot")
    dashboard_parser.add_argument("--limit", type=int, default=25, help="Maximum rows per dashboard section")
    dashboard_parser.add_argument("--now", help="Override dashboard clock timestamp")

    subparsers.add_parser("rebuild-index", help="Validate note event logs and rebuild projection fitness")
    subparsers.add_parser("list-events", help="List persisted note memory events")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one note memory CLI command and print a governed JSON envelope."""

    parser = build_parser()
    args = parser.parse_args(argv)
    mesh = NoteMemoryMesh(Path(args.note_store))
    if args.command == "capture":
        event = mesh.capture_note(_draft_from_args(args))
        envelope = _envelope(True, "captured", {"event": event.to_dict()})
    elif args.command == "capture-episode":
        event = mesh.capture_episode_capsule(_episode_draft_from_args(args))
        envelope = _envelope(True, "episode_capsule_captured", {"event": event.to_dict()})
    elif args.command == "record-rejected-delta":
        event = mesh.record_rejected_delta(
            content_summary=args.summary,
            source_ref=args.source_ref,
            scope=NoteScope(args.scope),
            evidence_refs=tuple(args.evidence_ref or ()),
        )
        envelope = _envelope(True, "rejected_delta_recorded", {"event": event.to_dict()})
    elif args.command == "retrieve":
        result = mesh.retrieve_notes_with_receipt(args.query, _retrieval_guard_from_args(args))
        envelope = _envelope(
            True,
            "retrieved",
            {
                "count": len(result.notes),
                "notes": [_jsonable(note) for note in result.notes],
                "receipt": _jsonable(result.receipt),
            },
        )
    elif args.command == "expire":
        report = mesh.expire_temporary_notes(args.now)
        envelope = _envelope(True, "expired", {"report": _jsonable(report)})
    elif args.command == "queue-promotion":
        promotion_id = mesh.queue_promotion(args.note_id)
        envelope = _envelope(True, "promotion_queued", {"promotion_id": promotion_id})
    elif args.command == "promote":
        receipt = _promotion_receipt_from_mapping(_load_json_object(args.receipt))
        event = mesh.promote_memory_anchor(args.note_id, receipt)
        envelope = _envelope(True, "promoted", {"event": event.to_dict(), "receipt": receipt.to_dict()})
    elif args.command == "dashboard":
        envelope = _envelope(True, "dashboard_snapshot", mesh.dashboard_snapshot(now=args.now, limit=args.limit))
    elif args.command == "rebuild-index":
        envelope = _envelope(True, "rebuilt", {"report": _jsonable(mesh.rebuild_index_from_events())})
    elif args.command == "list-events":
        events = mesh.list_events(skip_invalid=False)
        envelope = _envelope(True, "listed", {"count": len(events), "events": [event.to_dict() for event in events]})
    else:
        parser.error(f"unknown command: {args.command}")
    print(json.dumps(envelope, sort_keys=True, separators=(",", ":")))
    return 0 if envelope["ok"] else 1


def guarded_main(argv: Sequence[str] | None = None) -> int:
    """Run main while converting command errors into governed JSON."""

    try:
        return main(argv)
    except (OSError, RuntimeCoreInvariantError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps(_envelope(False, "rejected", {}, error=str(exc)), sort_keys=True, separators=(",", ":")))
        return 1


def _draft_from_args(args: argparse.Namespace) -> NoteMemoryDraft:
    return NoteMemoryDraft(
        kind=NoteKind(args.kind),
        action=NoteAction(args.action),
        scope=NoteScope(args.scope),
        content_summary=args.summary,
        source_ref=args.source_ref,
        proof_state=ProofState(args.proof_state),
        trust_zone=TrustZone(args.trust_zone),
        expires_at=args.expires_at,
        note_id=args.note_id,
        evidence_refs=tuple(args.evidence_ref or ()),
        relation_refs=tuple(args.relation_ref or ()),
        retrieval_receipt_refs=tuple(args.retrieval_receipt_ref or ()),
        claim_key=args.claim_key,
        claim_value=args.claim_value,
    )


def _episode_draft_from_args(args: argparse.Namespace) -> EpisodeCapsuleDraft:
    return EpisodeCapsuleDraft(
        goal=args.goal,
        scope=NoteScope(args.scope),
        proof_state=ProofState(args.proof_state),
        trust_zone=TrustZone(args.trust_zone),
        constraints=tuple(args.constraint or ()),
        decisions=tuple(args.decision or ()),
        changed_files=tuple(args.changed_file or ()),
        verification_refs=tuple(args.verification_ref or ()),
        open_risks=tuple(args.open_risk or ()),
        evidence_refs=tuple(args.evidence_ref or ()),
        relation_refs=tuple(args.relation_ref or ()),
        episode_id=args.episode_id,
    )


def _retrieval_guard_from_args(args: argparse.Namespace) -> RetrievalGuard:
    allowed_trust_zones = (
        tuple(TrustZone(value) for value in args.allowed_trust_zone)
        if args.allowed_trust_zone
        else (TrustZone.LOCAL, TrustZone.WORKSPACE)
    )
    allowed_proof_states = (
        tuple(ProofState(value) for value in args.allowed_proof_state)
        if args.allowed_proof_state
        else (ProofState.PASS,)
    )
    return RetrievalGuard(
        allowed_trust_zones=allowed_trust_zones,
        allowed_proof_states=allowed_proof_states,
        scope=NoteScope(args.scope) if args.scope else None,
        now=args.now,
        include_hypotheses=bool(args.include_hypotheses),
    )


def _promotion_receipt_from_mapping(value: Mapping[str, Any]) -> PromotionReceipt:
    return PromotionReceipt(
        promotion_id=str(value["promotion_id"]),
        source_note_id=str(value["source_note_id"]),
        anchor_id=str(value["anchor_id"]),
        proof_state=ProofState(str(value["proof_state"])),
        evidence_refs=tuple(str(item) for item in value["evidence_refs"]),
        contradiction_scan=ProofState(str(value["contradiction_scan"])),
        phi_gov_status=PhiGovStatus(str(value["phi_gov_status"])),
        accepted_at=str(value["accepted_at"]),
        accepted_by=str(value["accepted_by"]),
        lineage_event_seq=int(value["lineage_event_seq"]),
    )


def _load_json_object(value: str) -> dict[str, Any]:
    """Load an inline JSON object or a JSON object from disk."""

    stripped = value.strip()
    if stripped.startswith("{"):
        raw = stripped
    else:
        candidate = Path(value)
        raw = candidate.read_text(encoding="utf-8") if candidate.exists() else value
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("JSON payload must be an object")
    return parsed


def _envelope(ok: bool, status: str, payload: Mapping[str, Any], *, error: str = "") -> dict[str, Any]:
    return {
        "governed": True,
        "ok": ok,
        "status": status,
        "payload": dict(payload),
        "error": error,
    }


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


if __name__ == "__main__":
    raise SystemExit(guarded_main())
