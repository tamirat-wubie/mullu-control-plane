"""Governed note and memory mesh.

Purpose: capture temporary notes, execution traces, decisions, episode capsules,
rejected deltas, and promoted memory anchors as bounded symbolic evidence.
Governance scope: Phi_gov promotion gating, ProofState discipline, secret
redaction, append-only lineage, retrieval guard checks, deterministic
claim-contradiction detection, and Mfidel atomicity.
Dependencies: standard-library JSONL persistence, file locking, and runtime
invariant helpers.
Invariants: durable writes are append-only, secrets are redacted before
persistence, MemoryAnchor writes require accepted governance receipts, and
temporary notes cannot influence execution after expiry or contradiction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Callable, Iterable, Mapping, Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


class ProofState(StrEnum):
    """Allowed note proof states."""

    PASS = "Pass"
    FAIL = "Fail"
    UNKNOWN = "Unknown"
    BUDGET_UNKNOWN = "BudgetUnknown"


class NoteKind(StrEnum):
    """Governed note kinds."""

    EPHEMERAL_SCRATCH = "EphemeralScratch"
    WORKING_NOTE = "WorkingNote"
    EPISODE_CAPSULE = "EpisodeCapsule"
    EXECUTION_TRACE = "ExecutionTrace"
    DECISION_RECORD = "DecisionRecord"
    REJECTED_DELTA = "RejectedDelta"
    MEMORY_ANCHOR = "MemoryAnchor"


class NoteAction(StrEnum):
    """Append-only event actions for note lifecycle transitions."""

    CREATE = "create"
    APPEND = "append"
    SUPERSEDE = "supersede"
    CONTRADICT = "contradict"
    EXPIRE = "expire"
    PROMOTE = "promote"
    REJECT = "reject"


class NoteScope(StrEnum):
    """Allowed note influence scopes."""

    TASK = "task"
    MODULE = "module"
    REPOSITORY = "repository"
    PLATFORM = "platform"


class TrustZone(StrEnum):
    """Trust boundaries for note source and retrieval."""

    LOCAL = "local"
    WORKSPACE = "workspace"
    EXTERNAL = "external"
    SENSITIVE = "sensitive"


class PhiGovStatus(StrEnum):
    """Governance status for promotion receipts."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


_TEMPORARY_KINDS = {NoteKind.EPHEMERAL_SCRATCH, NoteKind.WORKING_NOTE}
_PROMOTABLE_KINDS = {NoteKind.WORKING_NOTE, NoteKind.EPISODE_CAPSULE, NoteKind.DECISION_RECORD}
_DURABLE_NON_PROMOTABLE_KINDS = {NoteKind.EXECUTION_TRACE, NoteKind.REJECTED_DELTA}
_DASHBOARD_ACTIVE_KINDS = {
    NoteKind.EPHEMERAL_SCRATCH,
    NoteKind.WORKING_NOTE,
    NoteKind.EPISODE_CAPSULE,
    NoteKind.EXECUTION_TRACE,
    NoteKind.DECISION_RECORD,
    NoteKind.MEMORY_ANCHOR,
}
_DASHBOARD_TERMINAL_ACTIONS = {NoteAction.REJECT, NoteAction.CONTRADICT, NoteAction.EXPIRE}
_CONTRADICTION_DETECTION_ACTIONS = {NoteAction.CREATE, NoteAction.APPEND, NoteAction.SUPERSEDE}
_MAX_EPISODE_FIELD_LENGTH = 512
_MAX_EPISODE_ITEMS = 50
_MAX_RETRIEVAL_QUERY_LENGTH = 256
_REDACTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    (
        "credential_url",
        re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s]+@[^/\s]+[^\s]*", re.IGNORECASE),
    ),
    (
        "api_key",
        re.compile(
            r"\b(api[_-]?key|token|oauth[_-]?token|secret|password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s,;]+",
            re.IGNORECASE,
        ),
    ),
    (
        "verification_link",
        re.compile(r"https?://[^\s]+(?:verify|verification|reset|recovery)[^\s]+", re.IGNORECASE),
    ),
    (
        "recovery_code",
        re.compile(r"\b(recovery[_ -]?code|backup[_ -]?code)\s*[:=]\s*['\"]?[A-Za-z0-9-]{6,}", re.IGNORECASE),
    ),
)
_MFIDEL_BLOCK_PATTERNS = (
    "split fidel",
    "decompose fidel",
    "decompose amharic",
    "consonant + vowel",
    "consonant-vowel",
    "root letter",
    "unicode decomposition",
    "unicode normalization",
    "normalize amharic",
)
_MFIDEL_REJECTION_CONTEXT = ("reject", "rejected", "block", "blocked", "no ", "never ", "violation")
_SYMBOL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise RuntimeCoreInvariantError(f"invalid iso timestamp: {value}") from exc


def _tuple_text(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    result = tuple(str(value).strip() for value in values if str(value).strip())
    return result


def _bounded_text(value: str, field_name: str, *, max_length: int = _MAX_EPISODE_FIELD_LENGTH) -> str:
    text = str(value).strip()
    if not text:
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty")
    if len(text) > max_length:
        raise RuntimeCoreInvariantError(f"{field_name} exceeds {max_length} characters")
    return redact_sensitive_text(text)


def _bounded_text_tuple(values: Sequence[str] | None, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if len(values) > _MAX_EPISODE_ITEMS:
        raise RuntimeCoreInvariantError(f"{field_name} exceeds {_MAX_EPISODE_ITEMS} entries")
    return tuple(_bounded_text(value, field_name) for value in values if str(value).strip())


def _unique_text_tuple(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _validate_symbol_identifier(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty")
    if ".." in text or not _SYMBOL_IDENTIFIER_PATTERN.fullmatch(text):
        raise RuntimeCoreInvariantError(f"{field_name} must be a bounded symbolic identifier")
    return text


def _validate_retrieval_receipt_id(value: str, field_name: str = "retrieval_receipt_ref") -> str:
    text = _validate_symbol_identifier(str(value), field_name)
    if not text.startswith("note-retrieval-"):
        raise RuntimeCoreInvariantError(f"{field_name} must reference a note retrieval receipt")
    return text


def _validate_retrieval_receipt_refs(values: Iterable[str]) -> tuple[str, ...]:
    return _unique_text_tuple(_validate_retrieval_receipt_id(value) for value in values)


def _retrieval_filter_mode(*, retrieval_receipt_filter: str, retrieval_citing_note_filter: str) -> str:
    if retrieval_receipt_filter and retrieval_citing_note_filter:
        return "receipt_and_citing_note"
    if retrieval_receipt_filter:
        return "receipt"
    if retrieval_citing_note_filter:
        return "citing_note"
    return "unfiltered"


def _validate_optional_claim(claim_key: str, claim_value: str) -> tuple[str, str]:
    key = str(claim_key or "").strip()
    value = str(claim_value or "").strip()
    if not key and not value:
        return "", ""
    if not key or not value:
        raise RuntimeCoreInvariantError("claim_key and claim_value must be supplied together")
    _validate_symbol_identifier(key, "claim_key")
    return key, _bounded_text(value, "claim_value", max_length=256)


def _retrieval_query(query: str) -> tuple[str, tuple[str, ...]]:
    text = redact_sensitive_text(str(query).strip())
    if len(text) > _MAX_RETRIEVAL_QUERY_LENGTH:
        raise RuntimeCoreInvariantError(f"query exceeds {_MAX_RETRIEVAL_QUERY_LENGTH} characters")
    return text, tuple(term for term in text.lower().split() if term)


def _required_promotion_text(entry: Mapping[str, object], field_name: str) -> str:
    raw_value = entry.get(field_name)
    text = str(raw_value or "").strip()
    if not text:
        raise RuntimeCoreInvariantError(f"promotion queue entry missing {field_name}")
    return text


def _required_promotion_int(entry: Mapping[str, object], field_name: str) -> int:
    text = _required_promotion_text(entry, field_name)
    try:
        value = int(text)
    except ValueError as exc:
        raise RuntimeCoreInvariantError(f"promotion queue entry {field_name} must be an integer") from exc
    if value < 1:
        raise RuntimeCoreInvariantError(f"promotion queue entry {field_name} must be positive")
    return value


def _required_iso_promotion_text(entry: Mapping[str, object], field_name: str) -> str:
    text = _required_promotion_text(entry, field_name)
    _parse_iso(text)
    return text


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)


def _checksum_for_payload(payload: Mapping[str, object]) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def redact_sensitive_text(value: str) -> str:
    """Return text with known durable-secret patterns replaced by hash witnesses."""

    redacted = value
    for secret_kind, pattern in _REDACTION_PATTERNS:
        redacted = pattern.sub(lambda match: _redaction_marker(secret_kind, match.group(0)), redacted)
    return redacted


def _redaction_marker(secret_kind: str, secret_value: str) -> str:
    digest = sha256(secret_value.encode("utf-8")).hexdigest()[:12]
    return f"[REDACTED:{secret_kind}:{digest}]"


def _redact_sequence(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(redact_sensitive_text(value) for value in values)


def _mfidel_violation_detected(content_summary: str, kind: NoteKind) -> bool:
    lower_summary = content_summary.lower()
    if not any(pattern in lower_summary for pattern in _MFIDEL_BLOCK_PATTERNS):
        return False
    if kind == NoteKind.REJECTED_DELTA:
        return False
    return not any(marker in lower_summary for marker in _MFIDEL_REJECTION_CONTEXT)


@dataclass(frozen=True)
class PromotionReceipt:
    """Phi_gov receipt required before a note can become a MemoryAnchor."""

    promotion_id: str
    source_note_id: str
    anchor_id: str
    proof_state: ProofState
    evidence_refs: tuple[str, ...]
    contradiction_scan: ProofState
    phi_gov_status: PhiGovStatus
    accepted_at: str
    accepted_by: str
    lineage_event_seq: int

    def __post_init__(self) -> None:
        if self.proof_state != ProofState.PASS:
            raise RuntimeCoreInvariantError("promotion receipt proof_state must be Pass")
        if self.contradiction_scan != ProofState.PASS:
            raise RuntimeCoreInvariantError("promotion receipt contradiction_scan must be Pass")
        if self.phi_gov_status != PhiGovStatus.ACCEPTED:
            raise RuntimeCoreInvariantError("promotion receipt phi_gov_status must be accepted")
        if not self.evidence_refs:
            raise RuntimeCoreInvariantError("promotion receipt requires evidence_refs")
        for field_name in ("promotion_id", "source_note_id", "anchor_id", "accepted_at", "accepted_by"):
            if not str(getattr(self, field_name)).strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be non-empty")
        if self.lineage_event_seq < 0:
            raise RuntimeCoreInvariantError("lineage_event_seq must be non-negative")
        _validate_symbol_identifier(self.promotion_id, "promotion_id")
        _validate_symbol_identifier(self.source_note_id, "source_note_id")
        _validate_symbol_identifier(self.anchor_id, "anchor_id")
        _parse_iso(self.accepted_at)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-compatible receipt."""

        return {
            "promotion_id": self.promotion_id,
            "source_note_id": self.source_note_id,
            "anchor_id": self.anchor_id,
            "proof_state": self.proof_state.value,
            "evidence_refs": list(self.evidence_refs),
            "contradiction_scan": self.contradiction_scan.value,
            "phi_gov_status": self.phi_gov_status.value,
            "accepted_at": self.accepted_at,
            "accepted_by": self.accepted_by,
            "lineage_event_seq": self.lineage_event_seq,
        }


@dataclass(frozen=True)
class NoteMemoryEvent:
    """One append-only note memory event."""

    event_seq: int
    event_id: str
    note_id: str
    kind: NoteKind
    action: NoteAction
    scope: NoteScope
    content_summary: str
    source_ref: str
    proof_state: ProofState
    trust_zone: TrustZone
    created_at: str
    expires_at: str | None = None
    evidence_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    retrieval_receipt_refs: tuple[str, ...] = ()
    claim_key: str = ""
    claim_value: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        if self.event_seq < 0:
            raise RuntimeCoreInvariantError("event_seq must be non-negative")
        for field_name in ("event_id", "note_id", "content_summary", "source_ref", "created_at"):
            if not str(getattr(self, field_name)).strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be non-empty")
        _validate_symbol_identifier(self.event_id, "event_id")
        _validate_symbol_identifier(self.note_id, "note_id")
        _parse_iso(self.created_at)
        if self.expires_at is not None:
            expires_at = _parse_iso(self.expires_at)
            if expires_at <= _parse_iso(self.created_at):
                raise RuntimeCoreInvariantError("expires_at must be after created_at")
        if self.kind in _TEMPORARY_KINDS and self.expires_at is None:
            raise RuntimeCoreInvariantError(f"{self.kind.value} requires expires_at")
        if self.kind == NoteKind.MEMORY_ANCHOR and self.action != NoteAction.PROMOTE:
            raise RuntimeCoreInvariantError("MemoryAnchor can only be emitted through promote action")
        if self.action == NoteAction.PROMOTE and self.proof_state != ProofState.PASS:
            raise RuntimeCoreInvariantError("promote action requires ProofState Pass")
        if self.action in {NoteAction.SUPERSEDE, NoteAction.CONTRADICT} and not self.relation_refs:
            raise RuntimeCoreInvariantError(f"{self.action.value} action requires relation_refs")
        object.__setattr__(
            self,
            "retrieval_receipt_refs",
            _validate_retrieval_receipt_refs(self.retrieval_receipt_refs),
        )
        claim_key, claim_value = _validate_optional_claim(self.claim_key, self.claim_value)
        object.__setattr__(self, "claim_key", claim_key)
        object.__setattr__(self, "claim_value", claim_value)
        if _mfidel_violation_detected(self.content_summary, self.kind):
            raise RuntimeCoreInvariantError("Mfidel atomicity violation detected in note summary")
        if self.checksum and self.checksum != self.expected_checksum():
            raise RuntimeCoreInvariantError("note event checksum mismatch")

    def to_dict(self, *, include_checksum: bool = True) -> dict[str, object]:
        """Return a deterministic JSON-compatible event."""

        value: dict[str, object] = {
            "event_seq": self.event_seq,
            "event_id": self.event_id,
            "note_id": self.note_id,
            "kind": self.kind.value,
            "action": self.action.value,
            "scope": self.scope.value,
            "content_summary": self.content_summary,
            "source_ref": self.source_ref,
            "proof_state": self.proof_state.value,
            "trust_zone": self.trust_zone.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "evidence_refs": list(self.evidence_refs),
            "relation_refs": list(self.relation_refs),
        }
        if self.retrieval_receipt_refs:
            value["retrieval_receipt_refs"] = list(self.retrieval_receipt_refs)
        if self.claim_key and self.claim_value:
            value["claim_key"] = self.claim_key
            value["claim_value"] = self.claim_value
        if include_checksum:
            value["checksum"] = self.checksum
        return value

    def expected_checksum(self) -> str:
        """Return the expected checksum for the event excluding checksum itself."""

        return _checksum_for_payload(self.to_dict(include_checksum=False))

    def with_integrity(self) -> "NoteMemoryEvent":
        """Return the event with deterministic event id and checksum populated."""

        event_id = self.event_id
        if event_id == "pending":
            event_id = stable_identifier("note-event", self.to_dict(include_checksum=False))
        event = replace(self, event_id=event_id, checksum="")
        return replace(event, checksum=event.expected_checksum())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "NoteMemoryEvent":
        """Rehydrate a note event from JSON-compatible data."""

        return cls(
            event_seq=int(value["event_seq"]),
            event_id=str(value["event_id"]),
            note_id=str(value["note_id"]),
            kind=NoteKind(str(value["kind"])),
            action=NoteAction(str(value["action"])),
            scope=NoteScope(str(value["scope"])),
            content_summary=str(value["content_summary"]),
            source_ref=str(value["source_ref"]),
            proof_state=ProofState(str(value["proof_state"])),
            trust_zone=TrustZone(str(value["trust_zone"])),
            created_at=str(value["created_at"]),
            expires_at=str(value["expires_at"]) if value.get("expires_at") else None,
            evidence_refs=_tuple_text(value.get("evidence_refs") if isinstance(value.get("evidence_refs"), list) else ()),
            relation_refs=_tuple_text(value.get("relation_refs") if isinstance(value.get("relation_refs"), list) else ()),
            retrieval_receipt_refs=_tuple_text(
                value.get("retrieval_receipt_refs") if isinstance(value.get("retrieval_receipt_refs"), list) else ()
            ),
            claim_key=str(value.get("claim_key", "")),
            claim_value=str(value.get("claim_value", "")),
            checksum=str(value.get("checksum", "")),
        )


@dataclass(frozen=True)
class NoteMemoryDraft:
    """Input contract for creating a note memory event."""

    kind: NoteKind
    scope: NoteScope
    content_summary: str
    source_ref: str
    proof_state: ProofState
    trust_zone: TrustZone
    expires_at: str | None = None
    note_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    retrieval_receipt_refs: tuple[str, ...] = ()
    claim_key: str = ""
    claim_value: str = ""
    action: NoteAction = NoteAction.CREATE


@dataclass(frozen=True)
class EpisodeCapsuleDraft:
    """Structured post-episode note summary for governed memory routing."""

    goal: str
    scope: NoteScope
    proof_state: ProofState
    trust_zone: TrustZone
    constraints: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    verification_refs: tuple[str, ...] = ()
    open_risks: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    episode_id: str = ""


@dataclass(frozen=True)
class RetrievedNote:
    """Guard-approved note projection with influence score."""

    event: NoteMemoryEvent
    score: float
    guard_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalReceipt:
    """Deterministic read-only witness for one note retrieval operation."""

    receipt_id: str
    query: str
    query_terms: tuple[str, ...]
    guard_scope: str
    allowed_trust_zones: tuple[str, ...]
    allowed_proof_states: tuple[str, ...]
    include_hypotheses: bool
    assessed_at: str
    event_count: int
    materialized_note_count: int
    returned_count: int
    returned_note_ids: tuple[str, ...]
    returned_event_ids: tuple[str, ...]
    snapshot_hash: str
    proof_state: ProofState

    def __post_init__(self) -> None:
        _validate_retrieval_receipt_id(self.receipt_id, "receipt_id")


@dataclass(frozen=True)
class RetrievalResult:
    """Guard-approved notes plus their read-only retrieval receipt."""

    notes: tuple[RetrievedNote, ...]
    receipt: RetrievalReceipt


@dataclass(frozen=True)
class RetrievalGuard:
    """Policy checks that must pass before a note can influence execution."""

    allowed_trust_zones: tuple[TrustZone, ...] = (TrustZone.LOCAL, TrustZone.WORKSPACE)
    allowed_proof_states: tuple[ProofState, ...] = (ProofState.PASS,)
    scope: NoteScope | None = None
    now: str | None = None
    include_hypotheses: bool = False


@dataclass(frozen=True)
class IndexRebuildReport:
    """Receipt for rebuilding the materialized note index."""

    valid_events: int
    rejected_lines: int
    checksum_failures: int
    proof_state: ProofState


@dataclass(frozen=True)
class ExpiryReport:
    """Receipt for temporary-note expiry processing."""

    expired_count: int
    emitted_event_ids: tuple[str, ...]
    proof_state: ProofState


@dataclass(frozen=True)
class _MaterializedNote:
    latest: NoteMemoryEvent
    superseded: bool = False
    contradicted: bool = False
    expired: bool = False


class _WriteLock:
    """Small cross-process lock using an atomic lock file."""

    def __init__(self, lock_path: Path, *, clock: Callable[[], str], ttl_seconds: int = 30) -> None:
        self._lock_path = lock_path
        self._clock = clock
        self._ttl_seconds = ttl_seconds
        self._fd: int | None = None

    def __enter__(self) -> "_WriteLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._clear_expired_lock()
        try:
            self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "pid": os.getpid(),
                "created_at": self._clock(),
                "expires_at": (_parse_iso(self._clock()) + timedelta(seconds=self._ttl_seconds)).isoformat(),
            }
            os.write(self._fd, _canonical_json(payload).encode("utf-8"))
            os.fsync(self._fd)
        except FileExistsError as exc:
            raise RuntimeCoreInvariantError(f"note memory write lock conflict: {self._lock_path}") from exc
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self._lock_path.unlink()
        except FileNotFoundError:
            return

    def _clear_expired_lock(self) -> None:
        if not self._lock_path.exists():
            return
        try:
            payload = json.loads(self._lock_path.read_text(encoding="utf-8"))
            expires_at = _parse_iso(str(payload["expires_at"]))
        except (OSError, KeyError, TypeError, json.JSONDecodeError, RuntimeCoreInvariantError):
            return
        if expires_at < _parse_iso(self._clock()):
            self._lock_path.unlink(missing_ok=True)


class NoteMemoryMesh:
    """Dependency-free governed note memory store backed by append-only JSONL."""

    def __init__(self, root_path: str | Path, *, clock: Callable[[], str] | None = None) -> None:
        self.root_path = Path(root_path)
        self._clock = clock or _utc_now_iso

    def capture_note(self, draft: NoteMemoryDraft) -> NoteMemoryEvent:
        """Capture one redacted note event and append it to the lineage."""

        if draft.kind == NoteKind.MEMORY_ANCHOR:
            raise RuntimeCoreInvariantError("MemoryAnchor writes must use promote_memory_anchor")
        with _WriteLock(self.root_path / "write.lock", clock=self._clock):
            return self._capture_note_locked(draft)

    def capture_episode_capsule(self, draft: EpisodeCapsuleDraft) -> NoteMemoryEvent:
        """Capture one structured post-episode capsule and append its witness event."""

        with _WriteLock(self.root_path / "write.lock", clock=self._clock):
            capsule_payload = self._episode_capsule_payload(draft)
            capsule_event = self._draft_to_event(
                NoteMemoryDraft(
                    kind=NoteKind.EPISODE_CAPSULE,
                    scope=draft.scope,
                    content_summary=self._episode_capsule_summary(capsule_payload),
                    source_ref=f"episode:{capsule_payload['episode_id']}",
                    proof_state=draft.proof_state,
                    trust_zone=draft.trust_zone,
                    note_id=str(capsule_payload["episode_id"]),
                    evidence_refs=tuple(str(item) for item in capsule_payload["evidence_refs"]),
                    relation_refs=tuple(str(item) for item in capsule_payload["relation_refs"]),
                )
            )
            sequenced = self._sequence_event_locked(capsule_event)
            persisted_payload = {
                **capsule_payload,
                "event_id": sequenced.event_id,
                "event_seq": sequenced.event_seq,
                "created_at": sequenced.created_at,
            }
            capsule_path = self._write_episode_capsule_locked(persisted_payload)
            try:
                self._write_event_locked(sequenced)
            except OSError:
                capsule_path.unlink(missing_ok=True)
                raise
            return sequenced

    def record_rejected_delta(
        self,
        *,
        content_summary: str,
        source_ref: str,
        scope: NoteScope = NoteScope.TASK,
        evidence_refs: Sequence[str] | None = None,
    ) -> NoteMemoryEvent:
        """Record durable negative evidence for a rejected state transition."""

        return self.capture_note(
            NoteMemoryDraft(
                kind=NoteKind.REJECTED_DELTA,
                action=NoteAction.REJECT,
                scope=scope,
                content_summary=content_summary,
                source_ref=source_ref,
                proof_state=ProofState.FAIL,
                trust_zone=TrustZone.WORKSPACE,
                evidence_refs=_tuple_text(evidence_refs),
            )
        )

    def retrieve_notes(self, query: str, guard: RetrievalGuard | None = None) -> tuple[RetrievedNote, ...]:
        """Return guard-approved notes ranked by deterministic influence score."""

        return self.retrieve_notes_with_receipt(query, guard).notes

    def retrieve_notes_with_receipt(self, query: str, guard: RetrievalGuard | None = None) -> RetrievalResult:
        """Return guard-approved notes with a deterministic read-only receipt."""

        active_guard = guard or RetrievalGuard()
        now = _parse_iso(active_guard.now or self._clock())
        query_text, query_terms = _retrieval_query(query)
        events = self.list_events(skip_invalid=False)
        materialized = self._materialize(events)
        retrieved: list[RetrievedNote] = []
        for note_state in materialized.values():
            allowed, reasons = self._guard_note(note_state, active_guard, now)
            if not allowed:
                continue
            event = note_state.latest
            if query_terms and not all(term in event.content_summary.lower() for term in query_terms):
                continue
            retrieved.append(
                RetrievedNote(
                    event=event,
                    score=self._score_note(event, active_guard, now),
                    guard_reasons=tuple(reasons),
                )
            )
        notes = tuple(sorted(retrieved, key=lambda item: (-item.score, item.event.event_seq)))
        return RetrievalResult(
            notes=notes,
            receipt=self._retrieval_receipt(
                query=query_text,
                query_terms=query_terms,
                guard=active_guard,
                assessed_at=now.isoformat(),
                event_count=len(events),
                materialized_note_count=len(materialized),
                notes=notes,
            ),
        )

    def queue_promotion(self, note_id: str) -> str:
        """Queue a promotable note for later Phi_gov review."""

        with _WriteLock(self.root_path / "write.lock", clock=self._clock):
            note_state = self._note_state(note_id)
            event = note_state.latest
            if self._source_is_blocked_for_promotion(note_state):
                raise RuntimeCoreInvariantError("promotion queue source is blocked by materialized state")
            if event.kind not in _PROMOTABLE_KINDS:
                raise RuntimeCoreInvariantError(f"{event.kind.value} cannot be promoted")
            if event.proof_state != ProofState.PASS:
                raise RuntimeCoreInvariantError("promotion queue requires source ProofState Pass")
            if not event.evidence_refs:
                raise RuntimeCoreInvariantError("promotion queue requires evidence_refs")
            promotion_id = stable_identifier("note-promotion", {"note_id": note_id, "event_seq": event.event_seq})
            if not self._promotion_is_queued(promotion_id, note_id, event.event_seq):
                self._append_promotion(
                    {
                        "promotion_id": promotion_id,
                        "source_note_id": note_id,
                        "source_event_seq": event.event_seq,
                        "source_event_id": event.event_id,
                        "queued_at": self._clock(),
                    }
                )
            return promotion_id

    def promote_memory_anchor(self, note_id: str, receipt: PromotionReceipt) -> NoteMemoryEvent:
        """Promote a validated note into a MemoryAnchor after receipt checks."""

        with _WriteLock(self.root_path / "write.lock", clock=self._clock):
            source_state = self._note_state(note_id)
            source = source_state.latest
            if receipt.source_note_id != note_id:
                raise RuntimeCoreInvariantError("promotion receipt source_note_id mismatch")
            expected_promotion_id = stable_identifier("note-promotion", {"note_id": note_id, "event_seq": source.event_seq})
            if receipt.promotion_id != expected_promotion_id:
                raise RuntimeCoreInvariantError("promotion receipt id does not match source event")
            if receipt.lineage_event_seq != source.event_seq:
                raise RuntimeCoreInvariantError("promotion receipt lineage_event_seq mismatch")
            if not self._promotion_is_queued(receipt.promotion_id, note_id, source.event_seq):
                raise RuntimeCoreInvariantError("promotion receipt requires queued promotion")
            if source.kind not in _PROMOTABLE_KINDS:
                raise RuntimeCoreInvariantError(f"{source.kind.value} cannot be promoted")
            if source.proof_state != ProofState.PASS:
                raise RuntimeCoreInvariantError("memory anchor promotion requires source ProofState Pass")
            if not source.evidence_refs:
                raise RuntimeCoreInvariantError("memory anchor promotion requires source evidence_refs")
            if self._source_is_blocked_for_promotion(source_state):
                raise RuntimeCoreInvariantError("memory anchor promotion source is blocked by materialized state")
            anchor_path = self.root_path / "anchors" / f"{receipt.anchor_id}.json"
            if anchor_path.exists():
                raise RuntimeCoreInvariantError(f"memory anchor already exists: {receipt.anchor_id}")
            event = self._draft_to_event(
                NoteMemoryDraft(
                    kind=NoteKind.MEMORY_ANCHOR,
                    action=NoteAction.PROMOTE,
                    scope=source.scope,
                    content_summary=source.content_summary,
                    source_ref=f"promotion:{receipt.promotion_id}",
                    proof_state=ProofState.PASS,
                    trust_zone=source.trust_zone,
                    note_id=receipt.anchor_id,
                    evidence_refs=receipt.evidence_refs,
                    relation_refs=(note_id,),
                )
            )
            promoted = self._sequence_event_locked(event)
            self._write_anchor_receipt(promoted, receipt)
            try:
                self._write_event_locked(promoted)
            except OSError:
                anchor_path.unlink(missing_ok=True)
                raise
        return promoted

    def expire_temporary_notes(self, now: str | None = None) -> ExpiryReport:
        """Emit expiry events for unexpired temporary notes past their TTL."""

        current = _parse_iso(now or self._clock())
        emitted: list[str] = []
        materialized = self._materialize(self.list_events(skip_invalid=False))
        for note_state in materialized.values():
            event = note_state.latest
            if note_state.expired or event.kind not in _TEMPORARY_KINDS or event.expires_at is None:
                continue
            if _parse_iso(event.expires_at) <= current:
                expiry_event = self._draft_to_event(
                    NoteMemoryDraft(
                        kind=event.kind,
                        action=NoteAction.EXPIRE,
                        scope=event.scope,
                        content_summary=f"Expired temporary note {event.note_id}",
                        source_ref=f"expiry:{event.note_id}",
                        proof_state=ProofState.PASS,
                        trust_zone=event.trust_zone,
                        note_id=event.note_id,
                        expires_at=(current + timedelta(seconds=1)).isoformat(),
                        relation_refs=(event.event_id,),
                    )
                )
                emitted.append(self._append_event(expiry_event).event_id)
        return ExpiryReport(
            expired_count=len(emitted),
            emitted_event_ids=tuple(emitted),
            proof_state=ProofState.PASS,
        )

    def rebuild_index_from_events(self) -> IndexRebuildReport:
        """Validate event files and report rebuild fitness without mutating lineage."""

        valid_events = 0
        rejected_lines = 0
        checksum_failures = 0
        for event_path in self._event_paths():
            with event_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        payload = json.loads(stripped)
                        expected_checksum = str(payload.get("checksum", ""))
                        unchecked_payload = dict(payload)
                        unchecked_payload["checksum"] = ""
                        event = NoteMemoryEvent.from_dict(unchecked_payload)
                        if expected_checksum != event.expected_checksum():
                            checksum_failures += 1
                            continue
                        valid_events += 1
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError, RuntimeCoreInvariantError):
                        rejected_lines += 1
        proof_state = ProofState.PASS if rejected_lines == 0 and checksum_failures == 0 else ProofState.FAIL
        return IndexRebuildReport(
            valid_events=valid_events,
            rejected_lines=rejected_lines,
            checksum_failures=checksum_failures,
            proof_state=proof_state,
        )

    def list_events(self, *, skip_invalid: bool = False) -> tuple[NoteMemoryEvent, ...]:
        """Return persisted events in monotonic order."""

        events: list[NoteMemoryEvent] = []
        for event_path in self._event_paths():
            with event_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        events.append(NoteMemoryEvent.from_dict(json.loads(stripped)))
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError, RuntimeCoreInvariantError) as exc:
                        if skip_invalid:
                            continue
                        raise RuntimeCoreInvariantError(f"invalid note event at {event_path}:{line_number}") from exc
        return tuple(sorted(events, key=lambda event: event.event_seq))

    @property
    def event_count(self) -> int:
        """Return the number of valid persisted note events."""

        return len(self.list_events(skip_invalid=False))

    def dashboard_snapshot(
        self,
        *,
        now: str | None = None,
        limit: int = 25,
        retrieval_receipt_ref: str | None = None,
        retrieval_citing_note_ref: str | None = None,
    ) -> dict[str, object]:
        """Return a read-only operator snapshot for the note memory control surface."""

        if limit < 1 or limit > 100:
            raise RuntimeCoreInvariantError("dashboard limit must be between 1 and 100")
        retrieval_receipt_filter = (
            _validate_retrieval_receipt_id(retrieval_receipt_ref, "retrieval_receipt_ref")
            if retrieval_receipt_ref
            else ""
        )
        retrieval_citing_note_filter = (
            _validate_symbol_identifier(str(retrieval_citing_note_ref), "retrieval_citing_note_ref")
            if retrieval_citing_note_ref
            else ""
        )
        retrieval_filter_mode = _retrieval_filter_mode(
            retrieval_receipt_filter=retrieval_receipt_filter,
            retrieval_citing_note_filter=retrieval_citing_note_filter,
        )
        current = _parse_iso(now or self._clock())
        events = self.list_events(skip_invalid=False)
        materialized = self._materialize(events)
        active_notes: list[NoteMemoryEvent] = []
        expiring_notes: list[NoteMemoryEvent] = []
        for note_state in materialized.values():
            event = note_state.latest
            time_expired = event.expires_at is not None and _parse_iso(event.expires_at) <= current
            if note_state.expired or note_state.superseded or note_state.contradicted or time_expired:
                continue
            if event.kind not in _DASHBOARD_ACTIVE_KINDS or event.action in _DASHBOARD_TERMINAL_ACTIONS:
                continue
            active_notes.append(event)
            if event.kind in _TEMPORARY_KINDS and event.expires_at is not None:
                expiring_notes.append(event)

        recent_events = sorted(events, key=lambda event: event.event_seq, reverse=True)
        rejected_deltas = [
            event
            for event in recent_events
            if event.kind == NoteKind.REJECTED_DELTA or event.action == NoteAction.REJECT
        ]
        contradictions = [event for event in recent_events if event.action == NoteAction.CONTRADICT]
        memory_anchors = [event for event in recent_events if event.kind == NoteKind.MEMORY_ANCHOR]
        episode_capsules = [event for event in recent_events if event.kind == NoteKind.EPISODE_CAPSULE]
        retrieval_influence_rows = self._retrieval_influence_rows(recent_events)
        retrieval_influence = [
            row
            for row in retrieval_influence_rows
            if (not retrieval_receipt_filter or row["receipt_id"] == retrieval_receipt_filter)
            and (not retrieval_citing_note_filter or row["citing_note_id"] == retrieval_citing_note_filter)
        ]
        retrieval_receipts = self._retrieval_receipt_summary_rows(retrieval_influence)
        retrieval_receipts_total = self._retrieval_receipt_summary_rows(retrieval_influence_rows)
        pending_promotions = sorted(
            self._pending_promotions(),
            key=lambda entry: str(entry.get("queued_at", "")),
            reverse=True,
        )
        index_report = self.rebuild_index_from_events()
        assessed_at = current.isoformat()
        snapshot_body: dict[str, object] = {
            "status": "ready",
            "assessed_at": assessed_at,
            "filters": {
                "retrieval_receipt_ref": retrieval_receipt_filter,
                "retrieval_citing_note_ref": retrieval_citing_note_filter,
            },
            "summary": {
                "event_count": len(events),
                "active_note_count": len(active_notes),
                "rejected_delta_count": len(rejected_deltas),
                "expiring_note_count": len(expiring_notes),
                "pending_promotion_count": len(pending_promotions),
                "memory_anchor_count": len(memory_anchors),
                "episode_capsule_count": len(episode_capsules),
                "contradiction_count": len(contradictions),
                "retrieval_filter_active": bool(retrieval_receipt_filter or retrieval_citing_note_filter),
                "retrieval_filter_mode": retrieval_filter_mode,
                "retrieval_influence_count": len(retrieval_influence),
                "retrieval_influence_total_count": len(retrieval_influence_rows),
                "retrieval_influence_filtered_out_count": len(retrieval_influence_rows) - len(retrieval_influence),
                "retrieval_receipt_count": len(retrieval_receipts),
                "retrieval_receipt_total_count": len(retrieval_receipts_total),
                "retrieval_receipt_filtered_out_count": len(retrieval_receipts_total) - len(retrieval_receipts),
                "index_proof_state": index_report.proof_state.value,
            },
            "recent_notes": [
                self._event_dashboard_row(event)
                for event in sorted(active_notes, key=lambda item: item.event_seq, reverse=True)[:limit]
            ],
            "rejected_deltas": [self._event_dashboard_row(event) for event in rejected_deltas[:limit]],
            "expiring_notes": [
                self._event_dashboard_row(event)
                for event in sorted(expiring_notes, key=lambda item: str(item.expires_at or ""))[:limit]
            ],
            "pending_promotions": [
                self._promotion_dashboard_row(entry)
                for entry in pending_promotions[:limit]
            ],
            "memory_anchors": [self._event_dashboard_row(event) for event in memory_anchors[:limit]],
            "episode_capsules": [self._event_dashboard_row(event) for event in episode_capsules[:limit]],
            "contradictions": [self._event_dashboard_row(event) for event in contradictions[:limit]],
            "retrieval_receipts": retrieval_receipts[:limit],
            "retrieval_influence": retrieval_influence[:limit],
            "audit_events": [self._event_dashboard_row(event) for event in recent_events[:limit]],
            "index": {
                "valid_events": index_report.valid_events,
                "rejected_lines": index_report.rejected_lines,
                "checksum_failures": index_report.checksum_failures,
                "proof_state": index_report.proof_state.value,
            },
        }
        snapshot_hash = _checksum_for_payload(snapshot_body)
        return {
            "snapshot_id": stable_identifier("note-memory-dashboard", {"snapshot_hash": snapshot_hash}),
            "snapshot_hash": snapshot_hash,
            **snapshot_body,
        }

    def _event_dashboard_row(self, event: NoteMemoryEvent) -> dict[str, object]:
        """Return a bounded operator row for one note event."""

        row: dict[str, object] = {
            "event_seq": event.event_seq,
            "event_id": event.event_id,
            "note_id": event.note_id,
            "kind": event.kind.value,
            "action": event.action.value,
            "scope": event.scope.value,
            "content_summary": event.content_summary,
            "source_ref": event.source_ref,
            "proof_state": event.proof_state.value,
            "trust_zone": event.trust_zone.value,
            "created_at": event.created_at,
            "expires_at": event.expires_at,
            "evidence_refs": list(event.evidence_refs),
            "relation_refs": list(event.relation_refs),
        }
        if event.retrieval_receipt_refs:
            row["retrieval_receipt_refs"] = list(event.retrieval_receipt_refs)
        if event.claim_key and event.claim_value:
            row["claim_key"] = event.claim_key
            row["claim_value"] = event.claim_value
        return row

    def _retrieval_influence_rows(self, events: Sequence[NoteMemoryEvent]) -> list[dict[str, object]]:
        """Return receipt-to-note influence rows derived from append-only events."""

        rows: list[dict[str, object]] = []
        for event in events:
            for receipt_id in event.retrieval_receipt_refs:
                rows.append(
                    {
                        "receipt_id": receipt_id,
                        "citing_event_seq": event.event_seq,
                        "citing_event_id": event.event_id,
                        "citing_note_id": event.note_id,
                        "citing_kind": event.kind.value,
                        "citing_action": event.action.value,
                        "citing_scope": event.scope.value,
                        "citing_proof_state": event.proof_state.value,
                        "cited_at": event.created_at,
                        "source_ref": event.source_ref,
                    }
                )
        return rows

    def _retrieval_receipt_summary_rows(self, influence_rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
        """Return bounded per-receipt citation summaries for operator navigation."""

        grouped_rows: dict[str, list[dict[str, object]]] = {}
        for row in influence_rows:
            receipt_id = str(row.get("receipt_id", ""))
            if not receipt_id:
                continue
            grouped_rows.setdefault(receipt_id, []).append(row)

        summaries: list[dict[str, object]] = []
        for receipt_id, rows in grouped_rows.items():
            sorted_rows = sorted(rows, key=lambda row: int(row.get("citing_event_seq", 0)), reverse=True)
            latest = sorted_rows[0]
            earliest = sorted_rows[-1]
            citing_note_ids: list[str] = []
            for row in sorted_rows:
                note_id = str(row.get("citing_note_id", ""))
                if note_id and note_id not in citing_note_ids:
                    citing_note_ids.append(note_id)
            summaries.append(
                {
                    "receipt_id": receipt_id,
                    "citation_count": len(rows),
                    "citing_note_id_count": len(citing_note_ids),
                    "sample_citing_note_ids": citing_note_ids[:10],
                    "latest_citing_event_seq": int(latest.get("citing_event_seq", 0)),
                    "latest_cited_at": str(latest.get("cited_at", "")),
                    "earliest_cited_at": str(earliest.get("cited_at", "")),
                }
            )

        return sorted(
            summaries,
            key=lambda row: (
                -int(row.get("citation_count", 0)),
                -int(row.get("latest_citing_event_seq", 0)),
                str(row.get("receipt_id", "")),
            ),
        )

    def _retrieval_receipt(
        self,
        *,
        query: str,
        query_terms: tuple[str, ...],
        guard: RetrievalGuard,
        assessed_at: str,
        event_count: int,
        materialized_note_count: int,
        notes: Sequence[RetrievedNote],
    ) -> RetrievalReceipt:
        receipt_body = {
            "query": query,
            "query_terms": list(query_terms),
            "guard_scope": guard.scope.value if guard.scope is not None else "",
            "allowed_trust_zones": [zone.value for zone in guard.allowed_trust_zones],
            "allowed_proof_states": [state.value for state in guard.allowed_proof_states],
            "include_hypotheses": guard.include_hypotheses,
            "assessed_at": assessed_at,
            "event_count": event_count,
            "materialized_note_count": materialized_note_count,
            "returned_count": len(notes),
            "returned_note_ids": [note.event.note_id for note in notes],
            "returned_event_ids": [note.event.event_id for note in notes],
            "proof_state": ProofState.PASS.value,
        }
        snapshot_hash = _checksum_for_payload(receipt_body)
        return RetrievalReceipt(
            receipt_id=stable_identifier("note-retrieval", {"snapshot_hash": snapshot_hash}),
            query=query,
            query_terms=query_terms,
            guard_scope=guard.scope.value if guard.scope is not None else "",
            allowed_trust_zones=tuple(zone.value for zone in guard.allowed_trust_zones),
            allowed_proof_states=tuple(state.value for state in guard.allowed_proof_states),
            include_hypotheses=guard.include_hypotheses,
            assessed_at=assessed_at,
            event_count=event_count,
            materialized_note_count=materialized_note_count,
            returned_count=len(notes),
            returned_note_ids=tuple(note.event.note_id for note in notes),
            returned_event_ids=tuple(note.event.event_id for note in notes),
            snapshot_hash=snapshot_hash,
            proof_state=ProofState.PASS,
        )

    def _capture_note_locked(self, draft: NoteMemoryDraft) -> NoteMemoryEvent:
        event = self._draft_to_event(draft)
        prior_events = self.list_events(skip_invalid=False)
        sequenced = self._sequence_event_locked(event)
        self._write_event_locked(sequenced)
        for contradiction_event in self._claim_contradiction_events(sequenced, prior_events):
            self._write_event_locked(self._sequence_event_locked(contradiction_event))
        return sequenced

    def _claim_contradiction_events(
        self,
        event: NoteMemoryEvent,
        prior_events: Sequence[NoteMemoryEvent],
    ) -> tuple[NoteMemoryEvent, ...]:
        if (
            not event.claim_key
            or not event.claim_value
            or event.action not in _CONTRADICTION_DETECTION_ACTIONS
            or event.kind == NoteKind.REJECTED_DELTA
        ):
            return ()
        current = _parse_iso(event.created_at)
        materialized = self._materialize(prior_events)
        conflicts: list[NoteMemoryEvent] = []
        for note_state in materialized.values():
            prior = note_state.latest
            if prior.claim_key != event.claim_key or prior.claim_value == event.claim_value:
                continue
            if note_state.expired or note_state.superseded or note_state.contradicted:
                continue
            if prior.expires_at is not None and _parse_iso(prior.expires_at) <= current:
                continue
            if prior.kind == NoteKind.REJECTED_DELTA or prior.action in _DASHBOARD_TERMINAL_ACTIONS:
                continue
            conflicts.append(prior)
        if not conflicts:
            return ()
        conflict_refs = tuple(conflict.event_id for conflict in sorted(conflicts, key=lambda item: item.event_seq))
        contradiction_note_id = stable_identifier(
            "note-claim-contradiction",
            {
                "claim_key": event.claim_key,
                "event_id": event.event_id,
                "conflicts": ",".join(conflict_refs),
            },
        )
        evidence_refs = _unique_text_tuple(tuple(event.evidence_refs) + (event.event_id,))
        return (
            self._draft_to_event(
                NoteMemoryDraft(
                    kind=NoteKind.DECISION_RECORD,
                    action=NoteAction.CONTRADICT,
                    scope=event.scope,
                    content_summary=(
                        f"Detected contradiction for claim {event.claim_key}: "
                        f"new value {event.claim_value} conflicts with prior active note"
                    ),
                    source_ref=f"claim-contradiction:{event.event_id}",
                    proof_state=event.proof_state,
                    trust_zone=event.trust_zone,
                    note_id=contradiction_note_id,
                    evidence_refs=evidence_refs,
                    relation_refs=conflict_refs,
                    claim_key=event.claim_key,
                    claim_value=event.claim_value,
                )
            ),
        )

    def _episode_capsule_payload(self, draft: EpisodeCapsuleDraft) -> dict[str, object]:
        goal = _bounded_text(draft.goal, "goal")
        constraints = _bounded_text_tuple(draft.constraints, "constraints")
        decisions = _bounded_text_tuple(draft.decisions, "decisions")
        changed_files = _bounded_text_tuple(draft.changed_files, "changed_files")
        verification_refs = _bounded_text_tuple(draft.verification_refs, "verification_refs")
        open_risks = _bounded_text_tuple(draft.open_risks, "open_risks")
        evidence_refs = _bounded_text_tuple(draft.evidence_refs, "evidence_refs")
        relation_refs = _bounded_text_tuple(draft.relation_refs, "relation_refs")
        if draft.proof_state == ProofState.PASS and not verification_refs:
            raise RuntimeCoreInvariantError("EpisodeCapsule with ProofState Pass requires verification_refs")
        if not evidence_refs:
            raise RuntimeCoreInvariantError("EpisodeCapsule requires evidence_refs")
        episode_id = (
            _validate_symbol_identifier(draft.episode_id, "episode_id")
            if draft.episode_id.strip()
            else stable_identifier(
                "episode-capsule",
                {
                    "goal": goal,
                    "evidence_refs": ",".join(evidence_refs),
                    "verification_refs": ",".join(verification_refs),
                    "created_at": self._clock(),
                },
            )
        )
        return {
            "episode_id": episode_id,
            "goal": goal,
            "scope": draft.scope.value,
            "proof_state": draft.proof_state.value,
            "trust_zone": draft.trust_zone.value,
            "constraints": list(constraints),
            "decisions": list(decisions),
            "changed_files": list(changed_files),
            "verification_refs": list(verification_refs),
            "open_risks": list(open_risks),
            "evidence_refs": list(evidence_refs),
            "relation_refs": list(relation_refs),
        }

    def _episode_capsule_summary(self, payload: Mapping[str, object]) -> str:
        decisions = payload.get("decisions", [])
        verifications = payload.get("verification_refs", [])
        risks = payload.get("open_risks", [])
        return (
            f"Episode capsule {payload['episode_id']}: goal={payload['goal']}; "
            f"decisions={len(decisions) if isinstance(decisions, list) else 0}; "
            f"verification_refs={len(verifications) if isinstance(verifications, list) else 0}; "
            f"open_risks={len(risks) if isinstance(risks, list) else 0}"
        )

    def _write_episode_capsule_locked(self, payload: Mapping[str, object]) -> Path:
        episode_id = _validate_symbol_identifier(str(payload["episode_id"]), "episode_id")
        capsule_path = self.root_path / "episodes" / f"{episode_id}.json"
        capsule_path.parent.mkdir(parents=True, exist_ok=True)
        stored_payload = dict(payload)
        stored_payload["checksum"] = _checksum_for_payload(stored_payload)
        try:
            with capsule_path.open("x", encoding="utf-8") as handle:
                handle.write(_canonical_json(stored_payload))
                handle.write("\n")
        except FileExistsError as exc:
            raise RuntimeCoreInvariantError(f"episode capsule already exists: {episode_id}") from exc
        return capsule_path

    def _promotion_dashboard_row(self, entry: Mapping[str, object]) -> dict[str, object]:
        """Return a bounded operator row for one pending promotion entry."""

        promotion_id = _validate_symbol_identifier(
            _required_promotion_text(entry, "promotion_id"),
            "promotion_id",
        )
        source_note_id = _validate_symbol_identifier(
            _required_promotion_text(entry, "source_note_id"),
            "source_note_id",
        )
        source_event_seq = _required_promotion_int(entry, "source_event_seq")
        source_event_id = _validate_symbol_identifier(
            _required_promotion_text(entry, "source_event_id"),
            "source_event_id",
        )
        queued_at = _required_iso_promotion_text(entry, "queued_at")
        return {
            "promotion_id": promotion_id,
            "source_note_id": source_note_id,
            "source_event_seq": source_event_seq,
            "source_event_id": source_event_id,
            "queued_at": queued_at,
        }

    def _draft_to_event(self, draft: NoteMemoryDraft) -> NoteMemoryEvent:
        created_at = self._clock()
        redacted_summary = redact_sensitive_text(draft.content_summary.strip())
        redacted_source = redact_sensitive_text(draft.source_ref.strip())
        redacted_evidence = _redact_sequence(draft.evidence_refs)
        redacted_retrieval_receipts = _redact_sequence(draft.retrieval_receipt_refs)
        claim_key, claim_value = _validate_optional_claim(draft.claim_key, draft.claim_value)
        note_id = _validate_symbol_identifier(draft.note_id, "note_id") if draft.note_id.strip() else stable_identifier(
            "note",
            {
                "kind": draft.kind.value,
                "scope": draft.scope.value,
                "content_summary": redacted_summary,
                "source_ref": redacted_source,
                "created_at": created_at,
            },
        )
        return NoteMemoryEvent(
            event_seq=0,
            event_id="pending",
            note_id=note_id,
            kind=draft.kind,
            action=draft.action,
            scope=draft.scope,
            content_summary=redacted_summary,
            source_ref=redacted_source,
            proof_state=draft.proof_state,
            trust_zone=draft.trust_zone,
            created_at=created_at,
            expires_at=draft.expires_at,
            evidence_refs=redacted_evidence,
            relation_refs=_tuple_text(draft.relation_refs),
            retrieval_receipt_refs=redacted_retrieval_receipts,
            claim_key=claim_key,
            claim_value=claim_value,
        )

    def _append_event(self, event: NoteMemoryEvent) -> NoteMemoryEvent:
        with _WriteLock(self.root_path / "write.lock", clock=self._clock):
            return self._append_event_locked(event)

    def _append_event_locked(self, event: NoteMemoryEvent) -> NoteMemoryEvent:
        sequenced = self._sequence_event_locked(event)
        self._write_event_locked(sequenced)
        return sequenced

    def _sequence_event_locked(self, event: NoteMemoryEvent) -> NoteMemoryEvent:
        event_seq = self._next_event_seq()
        return replace(event, event_seq=event_seq).with_integrity()

    def _write_event_locked(self, sequenced: NoteMemoryEvent) -> None:
        self._event_path_for(sequenced.created_at).parent.mkdir(parents=True, exist_ok=True)
        event_path = self._event_path_for(sequenced.created_at)
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(sequenced.to_dict()))
            handle.write("\n")
        if sequenced.kind == NoteKind.REJECTED_DELTA:
            self._append_rejected_delta(sequenced)

    def _next_event_seq(self) -> int:
        events = self.list_events(skip_invalid=False)
        if not events:
            return 1
        return max(event.event_seq for event in events) + 1

    def _latest_note(self, note_id: str) -> NoteMemoryEvent:
        return self._note_state(note_id).latest

    def _note_state(self, note_id: str) -> _MaterializedNote:
        materialized = self._materialize(self.list_events(skip_invalid=False))
        note_state = materialized.get(note_id)
        if note_state is None:
            raise RuntimeCoreInvariantError(f"unknown note_id: {note_id}")
        return note_state

    def _materialize(self, events: Sequence[NoteMemoryEvent]) -> dict[str, _MaterializedNote]:
        notes: dict[str, _MaterializedNote] = {}
        event_to_note_id = {event.event_id: event.note_id for event in events}
        for event in events:
            prior = notes.get(event.note_id)
            current = _MaterializedNote(
                latest=event,
                superseded=prior.superseded if prior else False,
                contradicted=prior.contradicted if prior else False,
                expired=prior.expired if prior else False,
            )
            if event.action == NoteAction.EXPIRE:
                current = replace(current, expired=True)
            notes[event.note_id] = current
            if event.action == NoteAction.SUPERSEDE:
                for relation_ref in event.relation_refs:
                    self._mark_relation(notes, event_to_note_id, relation_ref, superseded=True)
            if event.action == NoteAction.CONTRADICT:
                for relation_ref in event.relation_refs:
                    self._mark_relation(notes, event_to_note_id, relation_ref, contradicted=True)
        return notes

    def _mark_relation(
        self,
        notes: dict[str, _MaterializedNote],
        event_to_note_id: Mapping[str, str],
        relation_ref: str,
        *,
        superseded: bool = False,
        contradicted: bool = False,
    ) -> None:
        related_note_id = relation_ref if relation_ref in notes else event_to_note_id.get(relation_ref)
        if related_note_id is None:
            return
        related = notes.get(related_note_id)
        if related is None:
            return
        notes[related_note_id] = replace(
            related,
            superseded=related.superseded or superseded,
            contradicted=related.contradicted or contradicted,
        )

    def _guard_note(
        self,
        note_state: _MaterializedNote,
        guard: RetrievalGuard,
        now: datetime,
    ) -> tuple[bool, list[str]]:
        event = note_state.latest
        reasons: list[str] = []
        if note_state.expired or (event.expires_at is not None and _parse_iso(event.expires_at) <= now):
            return False, ("expired",)
        if note_state.superseded:
            return False, ("superseded",)
        if note_state.contradicted:
            return False, ("contradicted",)
        if event.trust_zone not in guard.allowed_trust_zones:
            return False, ("trust_zone_blocked",)
        allowed_proof_states = set(guard.allowed_proof_states)
        if guard.include_hypotheses:
            allowed_proof_states.add(ProofState.UNKNOWN)
        if event.proof_state not in allowed_proof_states:
            return False, ("proof_state_blocked",)
        if guard.scope is not None and event.scope != guard.scope:
            return False, ("scope_mismatch",)
        reasons.append("retrieval_guard_passed")
        return True, reasons

    def _score_note(self, event: NoteMemoryEvent, guard: RetrievalGuard, now: datetime) -> float:
        proof_weight = {
            ProofState.PASS: 1.0,
            ProofState.UNKNOWN: 0.45,
            ProofState.BUDGET_UNKNOWN: 0.1,
            ProofState.FAIL: 0.0,
        }[event.proof_state]
        age_seconds = max((now - _parse_iso(event.created_at)).total_seconds(), 0.0)
        freshness_weight = max(0.0, 1.0 - min(age_seconds / (7 * 24 * 60 * 60), 1.0))
        scope_match = 1.0 if guard.scope is None or guard.scope == event.scope else 0.0
        source_trust = {
            TrustZone.LOCAL: 1.0,
            TrustZone.WORKSPACE: 0.85,
            TrustZone.EXTERNAL: 0.4,
            TrustZone.SENSITIVE: 0.2,
        }[event.trust_zone]
        relation_density = min((len(event.evidence_refs) + len(event.relation_refs)) / 5.0, 1.0)
        return (
            0.35 * proof_weight
            + 0.25 * freshness_weight
            + 0.20 * scope_match
            + 0.10 * source_trust
            + 0.10 * relation_density
        )

    def _source_is_blocked_for_promotion(self, note_state: _MaterializedNote) -> bool:
        event = note_state.latest
        is_time_expired = event.expires_at is not None and _parse_iso(event.expires_at) <= _parse_iso(self._clock())
        return note_state.contradicted or note_state.superseded or note_state.expired or is_time_expired

    def _promotion_is_queued(self, promotion_id: str, source_note_id: str, source_event_seq: int) -> bool:
        for entry in self._pending_promotions():
            try:
                entry_source_event_seq = int(entry.get("source_event_seq", -1))
            except (TypeError, ValueError) as exc:
                raise RuntimeCoreInvariantError("invalid promotion queue source_event_seq") from exc
            if (
                entry.get("promotion_id") == promotion_id
                and entry.get("source_note_id") == source_note_id
                and entry_source_event_seq == source_event_seq
            ):
                return True
        return False

    def _pending_promotions(self) -> tuple[Mapping[str, object], ...]:
        promotion_path = self.root_path / "promotions" / "pending.jsonl"
        if not promotion_path.exists():
            return ()
        entries: list[Mapping[str, object]] = []
        with promotion_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise RuntimeCoreInvariantError(
                        f"invalid promotion queue entry at {promotion_path}:{line_number}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise RuntimeCoreInvariantError(f"invalid promotion queue entry at {promotion_path}:{line_number}")
                entries.append(payload)
        return tuple(entries)

    def _append_promotion(self, payload: Mapping[str, object]) -> None:
        promotion_path = self.root_path / "promotions" / "pending.jsonl"
        promotion_path.parent.mkdir(parents=True, exist_ok=True)
        with promotion_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(payload))
            handle.write("\n")

    def _write_anchor_receipt(self, event: NoteMemoryEvent, receipt: PromotionReceipt) -> None:
        anchor_path = self.root_path / "anchors" / f"{event.note_id}.json"
        anchor_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"anchor_event": event.to_dict(), "promotion_receipt": receipt.to_dict()}
        try:
            with anchor_path.open("x", encoding="utf-8") as handle:
                handle.write(_canonical_json(payload))
                handle.write("\n")
        except FileExistsError as exc:
            raise RuntimeCoreInvariantError(f"memory anchor already exists: {event.note_id}") from exc

    def _append_rejected_delta(self, event: NoteMemoryEvent) -> None:
        rejected_path = self.root_path / "rejected-deltas" / self._daily_filename(event.created_at)
        rejected_path.parent.mkdir(parents=True, exist_ok=True)
        with rejected_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(event.to_dict()))
            handle.write("\n")

    def _event_paths(self) -> tuple[Path, ...]:
        event_root = self.root_path / "events"
        if not event_root.exists():
            return ()
        return tuple(sorted(path for path in event_root.glob("*.jsonl") if path.is_file()))

    def _event_path_for(self, created_at: str) -> Path:
        return self.root_path / "events" / self._daily_filename(created_at)

    def _daily_filename(self, created_at: str) -> str:
        return f"{_parse_iso(created_at).date().isoformat()}.jsonl"
