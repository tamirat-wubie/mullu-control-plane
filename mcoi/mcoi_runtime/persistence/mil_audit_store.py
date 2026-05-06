"""Purpose: persist MIL audit records with tamper-evident hash-chain anchoring.
Governance scope: MIL audit payload persistence and integrity validation only.
Dependencies: MIL contracts, static verifier reports, hash-chain store, serialization helpers.
Invariants: records are immutable; record content hashes must match chain entries; reads fail closed.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mcoi_runtime.contracts._base import ContractRecord, require_datetime_text, require_non_empty_text
from mcoi_runtime.contracts.integrity import HashChainEntry
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.contracts.replay import ReplayEffect, ReplayMode, ReplayRecord
from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.replay_engine import (
    EffectControl as CoreEffectControl,
    ReplayArtifact as CoreReplayArtifact,
    ReplayEffect as CoreReplayEffect,
    ReplayMode as CoreReplayMode,
    ReplayRecord as CoreReplayRecord,
)
from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.core.mil_static_verifier import MILStaticReport

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
    TraceNotFoundError,
)
from .hash_chain import HashChainStore, compute_content_hash
from .replay_store import ReplayStore
from .trace_store import TraceStore


@dataclass(frozen=True, slots=True)
class MILAuditRecord(ContractRecord):
    record_id: str
    program_id: str
    goal_id: str
    policy_decision_id: str
    execution_id: str
    verification_passed: bool
    verification_issue_codes: tuple[str, ...]
    instruction_trace: tuple[str, ...]
    program: MILProgram
    verification: MILStaticReport
    recorded_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "program_id", require_non_empty_text(self.program_id, "program_id"))
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        object.__setattr__(
            self,
            "policy_decision_id",
            require_non_empty_text(self.policy_decision_id, "policy_decision_id"),
        )
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.verification_passed, bool):
            raise ValueError("verification_passed must be a boolean")
        object.__setattr__(
            self,
            "verification_issue_codes",
            _freeze_text_tuple(self.verification_issue_codes, "verification_issue_codes"),
        )
        object.__setattr__(self, "instruction_trace", _freeze_text_tuple(self.instruction_trace, "instruction_trace"))
        if not isinstance(self.program, MILProgram):
            raise ValueError("program must be a MILProgram")
        if not isinstance(self.verification, MILStaticReport):
            raise ValueError("verification must be a MILStaticReport")
        object.__setattr__(self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at"))


@dataclass(frozen=True, slots=True)
class MILAuditAppendResult(ContractRecord):
    record: MILAuditRecord
    chain_entry: HashChainEntry

    def __post_init__(self) -> None:
        if not isinstance(self.record, MILAuditRecord):
            raise ValueError("record must be a MILAuditRecord")
        if not isinstance(self.chain_entry, HashChainEntry):
            raise ValueError("chain_entry must be a HashChainEntry")
        expected_hash = compute_content_hash(serialize_record(self.record))
        if self.chain_entry.content_hash != expected_hash:
            raise ValueError("chain_entry content hash does not match record")


@dataclass(frozen=True, slots=True)
class MILAuditReplayLookup(ContractRecord):
    record: MILAuditRecord
    replay_record: ReplayRecord
    chain_entry: HashChainEntry
    trace_entries: tuple[TraceEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.record, MILAuditRecord):
            raise ValueError("record must be a MILAuditRecord")
        if not isinstance(self.replay_record, ReplayRecord):
            raise ValueError("replay_record must be a ReplayRecord")
        if not isinstance(self.chain_entry, HashChainEntry):
            raise ValueError("chain_entry must be a HashChainEntry")
        for index, entry in enumerate(self.trace_entries):
            if not isinstance(entry, TraceEntry):
                raise ValueError(f"trace_entries[{index}] must be a TraceEntry")


@dataclass(frozen=True, slots=True)
class MILAuditTracePersistence(ContractRecord):
    record_id: str
    persisted_trace_ids: tuple[str, ...]
    replay_lookup: MILAuditReplayLookup

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(
            self,
            "persisted_trace_ids",
            _freeze_text_tuple(self.persisted_trace_ids, "persisted_trace_ids"),
        )
        if not isinstance(self.replay_lookup, MILAuditReplayLookup):
            raise ValueError("replay_lookup must be a MILAuditReplayLookup")


@dataclass(frozen=True, slots=True)
class MILAuditReplayPersistence(ContractRecord):
    record_id: str
    replay_id: str
    trace_ids: tuple[str, ...]
    replay_record: CoreReplayRecord

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "replay_id", require_non_empty_text(self.replay_id, "replay_id"))
        object.__setattr__(self, "trace_ids", _freeze_text_tuple(self.trace_ids, "trace_ids"))
        if not isinstance(self.replay_record, CoreReplayRecord):
            raise ValueError("replay_record must be a core ReplayRecord")


class MILAuditStore:
    """Append-only MIL audit payload store anchored to a HashChainStore."""

    def __init__(self, base_path: Path, *, chain_id: str = "mil-audit") -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        if not isinstance(chain_id, str) or not chain_id.strip():
            raise PersistenceError("chain_id must be a non-empty string")
        self._base_path = base_path
        self._records_path = base_path / "records"
        self._chain = HashChainStore(base_path / "chain", chain_id=chain_id)

    @property
    def chain(self) -> HashChainStore:
        return self._chain

    def _record_path(self, record_id: str) -> Path:
        return _safe_record_path(
            self._records_path,
            require_non_empty_text(record_id, "record_id"),
        )

    def append(
        self,
        *,
        program: MILProgram,
        verification: MILStaticReport,
        execution_id: str,
        instruction_trace: tuple[str, ...],
        recorded_at: str,
    ) -> MILAuditAppendResult:
        if not isinstance(program, MILProgram):
            raise PersistenceError("program must be a MILProgram")
        if not isinstance(verification, MILStaticReport):
            raise PersistenceError("verification must be a MILStaticReport")
        execution_id = require_non_empty_text(execution_id, "execution_id")
        recorded_at = require_datetime_text(recorded_at, "recorded_at")
        trace = _freeze_text_tuple(instruction_trace, "instruction_trace")
        record = MILAuditRecord(
            record_id=stable_identifier(
                "mil-audit-record",
                {
                    "program_id": program.program_id,
                    "execution_id": execution_id,
                    "recorded_at": recorded_at,
                    "trace": trace,
                },
            ),
            program_id=program.program_id,
            goal_id=program.goal_id,
            policy_decision_id=program.whqr_decision.decision_id,
            execution_id=execution_id,
            verification_passed=verification.passed,
            verification_issue_codes=tuple(issue.code for issue in verification.issues),
            instruction_trace=trace,
            program=program,
            verification=verification,
            recorded_at=recorded_at,
        )
        content = serialize_record(record)
        content_hash = compute_content_hash(content)
        record_path = self._record_path(record.record_id)
        if record_path.exists():
            raise PersistenceWriteError("MIL audit record already exists")
        chain_entry = self._chain.append(content_hash)
        _atomic_write_exclusive(record_path, content)
        return MILAuditAppendResult(record=record, chain_entry=chain_entry)

    def load(self, record_id: str) -> MILAuditRecord:
        path = self._record_path(record_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorruptedDataError("MIL audit record read failed") from exc
        try:
            return deserialize_record(raw, MILAuditRecord)
        except (CorruptedDataError, TypeError, ValueError) as exc:
            raise CorruptedDataError("invalid MIL audit record") from exc

    def validate_record(self, record_id: str) -> bool:
        record = self.load(record_id)
        content_hash = compute_content_hash(serialize_record(record))
        return any(entry.content_hash == content_hash for entry in self._chain.load_all())

    def replay_lookup(self, record_id: str) -> MILAuditReplayLookup:
        record = self.load(record_id)
        content_hash = compute_content_hash(serialize_record(record))
        chain_entry = self._chain_entry_for_content_hash(content_hash)
        if chain_entry is None:
            raise CorruptedDataError("MIL audit record is not anchored in hash chain")
        trace_entries = self._trace_entries(record, chain_entry)
        replay_record = ReplayRecord(
            replay_id=stable_identifier("mil-audit-replay", {"record_id": record.record_id}),
            trace_id=trace_entries[-1].trace_id,
            source_hash=chain_entry.chain_hash,
            approved_effects=(
                ReplayEffect(
                    effect_id=record.execution_id,
                    description="MIL governed execution retained for observation-only replay",
                    details={
                        "program_id": record.program_id,
                        "verification_passed": record.verification_passed,
                    },
                ),
            ),
            blocked_effects=(),
            mode=ReplayMode.OBSERVATION_ONLY,
            recorded_at=record.recorded_at,
            metadata={
                "record_id": record.record_id,
                "program_id": record.program_id,
                "goal_id": record.goal_id,
                "policy_decision_id": record.policy_decision_id,
                "chain_sequence": chain_entry.sequence_number,
            },
        )
        return MILAuditReplayLookup(
            record=record,
            replay_record=replay_record,
            chain_entry=chain_entry,
            trace_entries=trace_entries,
        )

    def persist_trace_spine(
        self,
        record_id: str,
        trace_store: TraceStore,
    ) -> MILAuditTracePersistence:
        if not isinstance(trace_store, TraceStore):
            raise PersistenceError("trace_store must be a TraceStore")
        lookup = self.replay_lookup(record_id)
        persisted_trace_ids: list[str] = []
        for entry in lookup.trace_entries:
            existing = _load_existing_trace(trace_store, entry.trace_id)
            if existing is None:
                trace_store.append(entry)
            elif existing != entry:
                raise PersistenceWriteError("MIL audit trace id collision")
            persisted_trace_ids.append(entry.trace_id)
        return MILAuditTracePersistence(
            record_id=lookup.record.record_id,
            persisted_trace_ids=tuple(persisted_trace_ids),
            replay_lookup=lookup,
        )

    def persist_replay_bundle(
        self,
        record_id: str,
        *,
        trace_store: TraceStore,
        replay_store: ReplayStore,
    ) -> MILAuditReplayPersistence:
        if not isinstance(replay_store, ReplayStore):
            raise PersistenceError("replay_store must be a ReplayStore")
        trace_projection = self.persist_trace_spine(record_id, trace_store)
        replay_record = _core_replay_record(trace_projection.replay_lookup)
        existing = _load_existing_replay(replay_store, replay_record.replay_id)
        if existing is None:
            replay_store.save(replay_record)
        elif existing != replay_record:
            raise PersistenceWriteError("MIL audit replay id collision")
        return MILAuditReplayPersistence(
            record_id=trace_projection.record_id,
            replay_id=replay_record.replay_id,
            trace_ids=trace_projection.persisted_trace_ids,
            replay_record=replay_record,
        )

    def _chain_entry_for_content_hash(self, content_hash: str) -> HashChainEntry | None:
        for entry in self._chain.load_all():
            if entry.content_hash == content_hash:
                return entry
        return None

    def _trace_entries(
        self,
        record: MILAuditRecord,
        chain_entry: HashChainEntry,
    ) -> tuple[TraceEntry, ...]:
        parent = None
        rows: list[TraceEntry] = []
        specs = (
            (
                "whqr_policy_decision",
                record.policy_decision_id,
                {"status": record.program.whqr_decision.status.value},
            ),
            (
                "policy_decision",
                record.policy_decision_id,
                {"subject_id": record.program.whqr_decision.subject_id},
            ),
            (
                "mil_program",
                record.program_id,
                {"instruction_count": len(record.program.instructions)},
            ),
            (
                "mil_static_verification",
                record.record_id,
                {
                    "passed": record.verification_passed,
                    "issue_codes": record.verification_issue_codes,
                },
            ),
            (
                "dispatch_execution",
                record.execution_id,
                {"instruction_trace": record.instruction_trace},
            ),
            (
                "mil_audit_record",
                record.record_id,
                {
                    "chain_sequence": chain_entry.sequence_number,
                    "chain_hash": chain_entry.chain_hash,
                },
            ),
        )
        for event_type, anchor, metadata in specs:
            trace_id = stable_identifier(
                "mil-audit-record-trace",
                {"event_type": event_type, "anchor": anchor, "parent": parent},
            )
            rows.append(
                TraceEntry(
                    trace_id=trace_id,
                    parent_trace_id=parent,
                    event_type=event_type,
                    subject_id=record.program.whqr_decision.subject_id,
                    goal_id=record.goal_id,
                    state_hash=f"mil-audit-record:{record.record_id}",
                    registry_hash=f"mil-audit-chain:{self._chain.chain_id}",
                    timestamp=record.recorded_at,
                    metadata={"anchor": anchor, **metadata},
                )
            )
            parent = trace_id
        return tuple(rows)


def _record_path_component(record_id: str) -> str:
    if "\0" in record_id or "/" in record_id or "\\" in record_id or ".." in record_id:
        raise PathTraversalError("record_id contains forbidden characters")
    return record_id


def _atomic_write_exclusive(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
        try:
            os.link(tmp_path, str(path))
        except FileExistsError as exc:
            raise PersistenceWriteError("MIL audit record already exists") from exc
    except OSError as exc:
        raise PersistenceWriteError("MIL audit record write failed") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    return tuple(require_non_empty_text(value, f"{field_name}[{index}]") for index, value in enumerate(values))


def _safe_record_path(records_path: Path, record_id: str) -> Path:
    candidate = (records_path / f"{_record_path_component(record_id)}.json").resolve()
    base = records_path.resolve()
    if not candidate.is_relative_to(base):
        raise PathTraversalError("record path escapes MIL audit store")
    return candidate


def _load_existing_trace(trace_store: TraceStore, trace_id: str) -> TraceEntry | None:
    try:
        return trace_store.load_trace(trace_id)
    except TraceNotFoundError:
        return None


def _load_existing_replay(replay_store: ReplayStore, replay_id: str) -> CoreReplayRecord | None:
    try:
        return replay_store.load(replay_id)
    except PersistenceError:
        return None


def _core_replay_record(lookup: MILAuditReplayLookup) -> CoreReplayRecord:
    terminal_trace = lookup.trace_entries[-1]
    artifact_id = stable_identifier("mil-audit-artifact", {"record_id": lookup.record.record_id})
    return CoreReplayRecord(
        replay_id=lookup.replay_record.replay_id,
        trace_id=terminal_trace.trace_id,
        source_hash=terminal_trace.state_hash,
        approved_effects=(
            CoreReplayEffect(
                effect_id=lookup.record.execution_id,
                control=CoreEffectControl.CONTROLLED,
                artifact_id=artifact_id,
            ),
        ),
        blocked_effects=(),
        mode=CoreReplayMode.OBSERVATION_ONLY,
        recorded_at=lookup.record.recorded_at,
        artifacts=(
            CoreReplayArtifact(
                artifact_id=artifact_id,
                payload_digest=lookup.chain_entry.chain_hash,
            ),
        ),
        state_hash=terminal_trace.state_hash,
        environment_digest=f"mil-audit-chain:{lookup.chain_entry.chain_hash}",
    )
