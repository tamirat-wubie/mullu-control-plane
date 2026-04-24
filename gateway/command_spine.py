"""Gateway Command Spine - immutable command causality ledger.

Purpose: Provides the gateway's canonical command envelope and event ledger
    so ingress, approval, dispatch, verification, audit, and response are
    transitions of one governed command.
Governance scope: gateway command lifecycle only.
Dependencies: standard-library hashing, JSON serialization, dataclasses.
Invariants:
  - Command payloads are addressed by canonical SHA-256 hashes.
  - Every state transition appends a hash-linked event.
  - Command identity is stable across approval wait/resume.
  - Event records are immutable witnesses for replay and audit promotion.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Callable
from uuid import uuid4

_log = logging.getLogger(__name__)


class CommandState(StrEnum):
    """Governed command lifecycle states."""

    RECEIVED = "received"
    NORMALIZED = "normalized"
    TENANT_BOUND = "tenant_bound"
    INTENT_COMPILED = "intent_compiled"
    CAPABILITY_BOUND = "capability_bound"
    GOVERNED_ACTION_BOUND = "governed_action_bound"
    EFFECT_PREDICTED = "effect_predicted"
    POLICY_EVALUATED = "policy_evaluated"
    PENDING_APPROVAL = "pending_approval"
    DENIED = "denied"
    ALLOWED = "allowed"
    APPROVED = "approved"
    BUDGET_RESERVED = "budget_reserved"
    EFFECT_PLANNED = "effect_planned"
    FRACTURE_TESTED = "fracture_tested"
    SIMULATED = "simulated"
    SIMULATION_BLOCKED = "simulation_blocked"
    PENDING_EFFECT_APPROVAL = "pending_effect_approval"
    DISPATCHED = "dispatched"
    EFFECT_OBSERVED = "effect_observed"
    OBSERVED = "observed"
    VERIFIED = "verified"
    RECONCILED = "reconciled"
    COMMITTED = "committed"
    REQUIRES_REVIEW = "requires_review"
    COMPENSATED = "compensated"
    RESPONDED = "responded"
    ANCHORED = "anchored"


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    """Canonical unit of governed gateway action."""

    command_id: str
    tenant_id: str
    actor_id: str
    source: str
    conversation_id: str
    idempotency_key: str
    intent: str
    payload_hash: str
    redacted_payload: dict[str, Any]
    state: CommandState
    policy_version: str
    trace_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class CommandEvent:
    """Hash-linked witness for a command state transition."""

    event_id: str
    command_id: str
    tenant_id: str
    actor_id: str
    source_channel: str
    idempotency_key: str
    previous_state: CommandState
    next_state: CommandState
    policy_version: str
    risk_tier: str = ""
    budget_decision: str = ""
    approval_id: str = ""
    tool_name: str = ""
    input_hash: str = ""
    output_hash: str = ""
    trace_id: str = ""
    prev_event_hash: str = ""
    event_hash: str = ""
    timestamp: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandLease:
    """Worker lease over one ready command."""

    command_id: str
    worker_id: str
    leased_at: str
    lease_expires_at: str


@dataclass(frozen=True, slots=True)
class CommandAnchor:
    """Signed anchor for a command event batch."""

    anchor_id: str
    from_event_hash: str
    to_event_hash: str
    event_count: int
    merkle_root: str
    signature: str
    signature_key_id: str
    anchored_at: str


@dataclass(frozen=True, slots=True)
class CommandAnchorProof:
    """Exportable proof for a signed command event anchor."""

    anchor: CommandAnchor
    event_hashes: tuple[str, ...]
    proof_hash: str
    exported_at: str


@dataclass(frozen=True, slots=True)
class AnchorVerification:
    """Verification result for an exported anchor proof."""

    valid: bool
    reason: str
    anchor_id: str = ""


@dataclass(frozen=True, slots=True)
class TypedIntent:
    """Deterministic intent contract derived from gateway payload."""

    schema_name: str
    name: str
    params: dict[str, Any]
    source_text_hash: str
    payload_hash: str


@dataclass(frozen=True, slots=True)
class CapabilityPassport:
    """Governance manifest for one executable gateway capability."""

    capability: str
    version: str
    risk_tier: str
    input_schema: str
    output_schema: str
    authority_required: tuple[str, ...]
    requires: tuple[str, ...]
    mutates_world: bool
    external_system: str
    rollback_type: str
    rollback_capability: str = ""
    compensation_capability: str = ""
    proof_required_fields: tuple[str, ...] = ()
    declared_effects: tuple[str, ...] = ()
    forbidden_effects: tuple[str, ...] = ()
    evidence_required: tuple[str, ...] = ()
    graph_projection: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GovernedAction:
    """Bound meaning, capability, authority, recovery, and lifecycle state."""

    command_id: str
    tenant_id: str
    actor_id: str
    typed_intent: dict[str, Any]
    intent_schema: str
    intent_hash: str
    capability: str
    capability_version: str
    capability_passport_hash: str
    risk_tier: str
    authority_required: tuple[str, ...]
    approval_id: str | None
    predicted_effect_hash: str | None
    rollback_plan_hash: str | None
    state: str


@dataclass(frozen=True, slots=True)
class EffectPrediction:
    """Predicted world effects before command dispatch."""

    command_id: str
    capability: str
    expected_mutations: tuple[str, ...]
    expected_external_calls: tuple[str, ...]
    expected_receipts: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    risk_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """Rollback or compensation contract for a predicted effect."""

    command_id: str
    capability: str
    recovery_type: str
    recovery_capabilities: tuple[str, ...]
    requires_higher_approval: bool
    operator_review_required: bool
    proof_required_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffectObservation:
    """Observed world effects after command dispatch."""

    command_id: str
    actual_mutations: tuple[str, ...]
    actual_external_calls: tuple[str, ...]
    actual_receipts: tuple[str, ...]
    mismatch: bool = False
    mismatch_reason: str = ""


@dataclass(frozen=True, slots=True)
class EffectReconciliation:
    """Comparison between predicted and observed effects."""

    command_id: str
    predicted_effect_hash: str
    observed_effect_hash: str
    reconciled: bool
    mismatch_reason: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Evidence reference backing an operational claim."""

    evidence_id: str
    command_id: str
    evidence_type: str
    ref: str
    ref_hash: str
    verified: bool


@dataclass(frozen=True, slots=True)
class Claim:
    """Operational claim bound to evidence references."""

    claim_id: str
    command_id: str
    text: str
    evidence_refs: tuple[str, ...]
    confidence: float
    verified: bool


@dataclass(frozen=True, slots=True)
class ResponseEvidenceClosure:
    """Proof that a success response is backed by reconciled observed effects."""

    command_id: str
    claim_id: str
    reconciliation_hash: str
    evidence_refs: tuple[str, ...]
    evidence_hash: str
    closed_at: str


@dataclass(frozen=True, slots=True)
class FractureResult:
    """Result of contradiction checks before high-risk dispatch."""

    command_id: str
    passed: bool
    checks: tuple[str, ...]
    fractures: tuple[str, ...]
    result_hash: str


class CommandLedgerStore:
    """Persistence contract for command envelopes and transition events."""

    def save_command(self, command: CommandEnvelope) -> None:
        """Persist the latest command envelope state."""
        raise NotImplementedError

    def load_command(self, command_id: str) -> CommandEnvelope | None:
        """Load one command envelope by ID."""
        raise NotImplementedError

    def append_event(self, event: CommandEvent) -> None:
        """Append one command transition event."""
        raise NotImplementedError

    def events_for(self, command_id: str) -> list[CommandEvent]:
        """Load transition events for one command."""
        raise NotImplementedError

    def latest_event_hash(self) -> str:
        """Return the latest global event hash for hash-chain continuation."""
        return ""

    def claim_ready_commands(
        self,
        *,
        worker_id: str,
        states: tuple[CommandState, ...],
        leased_at: str,
        lease_expires_at: str,
        limit: int,
    ) -> list[CommandEnvelope]:
        """Atomically lease commands that are ready for worker dispatch."""
        raise NotImplementedError

    def release_command(self, command_id: str, worker_id: str) -> None:
        """Release one worker lease after dispatch completes or aborts."""
        raise NotImplementedError

    def unanchored_events(self) -> list[CommandEvent]:
        """Return command events that are not covered by the latest anchor."""
        raise NotImplementedError

    def append_anchor(self, anchor: CommandAnchor) -> None:
        """Persist one signed command-event anchor."""
        raise NotImplementedError

    def list_anchors(self, limit: int = 50) -> list[CommandAnchor]:
        """Return recent anchors, newest first."""
        return []

    def status(self) -> dict[str, Any]:
        """Return persistence health details."""
        return {"backend": "unknown"}


class InMemoryCommandLedgerStore(CommandLedgerStore):
    """In-memory command ledger store for local development and tests."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandEnvelope] = {}
        self._events: list[CommandEvent] = []
        self._leases: dict[str, CommandLease] = {}
        self._anchors: list[CommandAnchor] = []

    def save_command(self, command: CommandEnvelope) -> None:
        self._commands[command.command_id] = command

    def load_command(self, command_id: str) -> CommandEnvelope | None:
        return self._commands.get(command_id)

    def append_event(self, event: CommandEvent) -> None:
        self._events.append(event)

    def events_for(self, command_id: str) -> list[CommandEvent]:
        return [event for event in self._events if event.command_id == command_id]

    def latest_event_hash(self) -> str:
        if not self._events:
            return ""
        return self._events[-1].event_hash

    def claim_ready_commands(
        self,
        *,
        worker_id: str,
        states: tuple[CommandState, ...],
        leased_at: str,
        lease_expires_at: str,
        limit: int,
    ) -> list[CommandEnvelope]:
        if limit < 1:
            return []
        claimed: list[CommandEnvelope] = []
        for command in sorted(self._commands.values(), key=lambda item: item.created_at):
            if len(claimed) >= limit:
                break
            if command.state not in states:
                continue
            lease = self._leases.get(command.command_id)
            if lease is not None and lease.lease_expires_at > leased_at:
                continue
            self._leases[command.command_id] = CommandLease(
                command_id=command.command_id,
                worker_id=worker_id,
                leased_at=leased_at,
                lease_expires_at=lease_expires_at,
            )
            claimed.append(command)
        return claimed

    def release_command(self, command_id: str, worker_id: str) -> None:
        lease = self._leases.get(command_id)
        if lease is not None and lease.worker_id == worker_id:
            self._leases.pop(command_id, None)

    def unanchored_events(self) -> list[CommandEvent]:
        if not self._anchors:
            return list(self._events)
        latest_hash = self._anchors[-1].to_event_hash
        for index, event in enumerate(self._events):
            if event.event_hash == latest_hash:
                return self._events[index + 1:]
        return list(self._events)

    def append_anchor(self, anchor: CommandAnchor) -> None:
        self._anchors.append(anchor)

    def list_anchors(self, limit: int = 50) -> list[CommandAnchor]:
        return list(reversed(self._anchors[-limit:]))

    def status(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "commands": len(self._commands),
            "events": len(self._events),
            "active_leases": len(self._leases),
            "anchors": len(self._anchors),
            "available": True,
        }


class PostgresCommandLedgerStore(CommandLedgerStore):
    """PostgreSQL command ledger store.

    Persists command state and append-only command events. If psycopg2 or the
    database is unavailable, writes fail closed into the in-process ledger
    cache while status exposes the unavailable durable backend.
    """

    _MIGRATION = """
    CREATE TABLE IF NOT EXISTS gateway_commands (
        command_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        source TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        intent TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        redacted_payload JSONB NOT NULL DEFAULT '{}',
        state TEXT NOT NULL,
        policy_version TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_commands_tenant
        ON gateway_commands(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_commands_state
        ON gateway_commands(state);
    CREATE INDEX IF NOT EXISTS idx_gateway_commands_idempotency
        ON gateway_commands(idempotency_key);

    CREATE TABLE IF NOT EXISTS gateway_command_events (
        event_id TEXT PRIMARY KEY,
        command_id TEXT NOT NULL REFERENCES gateway_commands(command_id),
        tenant_id TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        source_channel TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        previous_state TEXT NOT NULL,
        next_state TEXT NOT NULL,
        policy_version TEXT NOT NULL,
        risk_tier TEXT NOT NULL DEFAULT '',
        budget_decision TEXT NOT NULL DEFAULT '',
        approval_id TEXT NOT NULL DEFAULT '',
        tool_name TEXT NOT NULL DEFAULT '',
        input_hash TEXT NOT NULL DEFAULT '',
        output_hash TEXT NOT NULL DEFAULT '',
        trace_id TEXT NOT NULL,
        prev_event_hash TEXT NOT NULL DEFAULT '',
        event_hash TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        detail JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_events_command
        ON gateway_command_events(command_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_events_tenant
        ON gateway_command_events(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_events_state
        ON gateway_command_events(next_state);

    CREATE TABLE IF NOT EXISTS gateway_command_locks (
        command_id TEXT PRIMARY KEY REFERENCES gateway_commands(command_id),
        worker_id TEXT NOT NULL,
        leased_at TEXT NOT NULL,
        lease_expires_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_locks_expiry
        ON gateway_command_locks(lease_expires_at);

    CREATE TABLE IF NOT EXISTS gateway_command_anchors (
        anchor_id TEXT PRIMARY KEY,
        from_event_hash TEXT NOT NULL,
        to_event_hash TEXT NOT NULL,
        event_count INTEGER NOT NULL,
        merkle_root TEXT NOT NULL,
        signature TEXT NOT NULL,
        signature_key_id TEXT NOT NULL,
        anchored_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_anchors_time
        ON gateway_command_anchors(anchored_at);
    """

    def __init__(
        self,
        connection_string: str = "postgresql://localhost:5432/mullu",
        *,
        auto_migrate: bool = True,
    ) -> None:
        self._connection_string = connection_string
        self._conn: Any | None = None
        self._lock = threading.Lock()
        self._available = False
        try:
            import psycopg2  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False

        if self._available:
            try:
                self._connect()
                if auto_migrate:
                    self._run_migration()
            except Exception as exc:
                _log.warning("command ledger postgres bootstrap failed (%s)", type(exc).__name__)
                self._conn = None

    def _connect(self) -> None:
        import psycopg2
        self._conn = psycopg2.connect(self._connection_string)
        self._conn.autocommit = False

    def _run_migration(self) -> None:
        if self._conn is None:
            return
        with self._conn.cursor() as cur:
            cur.execute(self._MIGRATION)
            self._conn.commit()

    def _safe_execute(self, operation: Callable[[], Any]) -> Any:
        if self._conn is None:
            return None
        try:
            return operation()
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception:
                pass
            _log.warning("command ledger postgres operation failed (%s)", type(exc).__name__)
            return None

    def save_command(self, command: CommandEnvelope) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_commands "
                        "(command_id, tenant_id, actor_id, source, conversation_id, "
                        "idempotency_key, intent, payload_hash, redacted_payload, state, "
                        "policy_version, trace_id, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (command_id) DO UPDATE SET "
                        "tenant_id = EXCLUDED.tenant_id, "
                        "actor_id = EXCLUDED.actor_id, "
                        "source = EXCLUDED.source, "
                        "conversation_id = EXCLUDED.conversation_id, "
                        "idempotency_key = EXCLUDED.idempotency_key, "
                        "intent = EXCLUDED.intent, "
                        "payload_hash = EXCLUDED.payload_hash, "
                        "redacted_payload = EXCLUDED.redacted_payload, "
                        "state = EXCLUDED.state, "
                        "policy_version = EXCLUDED.policy_version, "
                        "trace_id = EXCLUDED.trace_id, "
                        "updated_at = EXCLUDED.updated_at",
                        (
                            command.command_id, command.tenant_id, command.actor_id,
                            command.source, command.conversation_id, command.idempotency_key,
                            command.intent, command.payload_hash,
                            json.dumps(command.redacted_payload, sort_keys=True, default=str),
                            command.state.value, command.policy_version, command.trace_id,
                            command.created_at, datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def load_command(self, command_id: str) -> CommandEnvelope | None:
        def _read() -> CommandEnvelope | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT command_id, tenant_id, actor_id, source, conversation_id, "
                        "idempotency_key, intent, payload_hash, redacted_payload, state, "
                        "policy_version, trace_id, created_at "
                        "FROM gateway_commands WHERE command_id = %s",
                        (command_id,),
                    )
                    row = cur.fetchone()
            if row is None:
                return None
            payload = row[8]
            if isinstance(payload, str):
                payload = json.loads(payload)
            return CommandEnvelope(
                command_id=row[0],
                tenant_id=row[1],
                actor_id=row[2],
                source=row[3],
                conversation_id=row[4],
                idempotency_key=row[5],
                intent=row[6],
                payload_hash=row[7],
                redacted_payload=dict(payload),
                state=CommandState(row[9]),
                policy_version=row[10],
                trace_id=row[11],
                created_at=row[12],
            )

        result = self._safe_execute(_read)
        return result if isinstance(result, CommandEnvelope) else None

    def append_event(self, event: CommandEvent) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_command_events "
                        "(event_id, command_id, tenant_id, actor_id, source_channel, "
                        "idempotency_key, previous_state, next_state, policy_version, "
                        "risk_tier, budget_decision, approval_id, tool_name, input_hash, "
                        "output_hash, trace_id, prev_event_hash, event_hash, timestamp, detail) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (event_id) DO NOTHING",
                        (
                            event.event_id, event.command_id, event.tenant_id,
                            event.actor_id, event.source_channel, event.idempotency_key,
                            event.previous_state.value, event.next_state.value,
                            event.policy_version, event.risk_tier, event.budget_decision,
                            event.approval_id, event.tool_name, event.input_hash,
                            event.output_hash, event.trace_id, event.prev_event_hash,
                            event.event_hash, event.timestamp,
                            json.dumps(event.detail, sort_keys=True, default=str),
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def events_for(self, command_id: str) -> list[CommandEvent]:
        def _read() -> list[CommandEvent]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT event_id, command_id, tenant_id, actor_id, source_channel, "
                        "idempotency_key, previous_state, next_state, policy_version, risk_tier, "
                        "budget_decision, approval_id, tool_name, input_hash, output_hash, "
                        "trace_id, prev_event_hash, event_hash, timestamp, detail "
                        "FROM gateway_command_events WHERE command_id = %s ORDER BY timestamp",
                        (command_id,),
                    )
                    rows = cur.fetchall()
            events: list[CommandEvent] = []
            for row in rows:
                detail = row[19]
                if isinstance(detail, str):
                    detail = json.loads(detail)
                events.append(CommandEvent(
                    event_id=row[0],
                    command_id=row[1],
                    tenant_id=row[2],
                    actor_id=row[3],
                    source_channel=row[4],
                    idempotency_key=row[5],
                    previous_state=CommandState(row[6]),
                    next_state=CommandState(row[7]),
                    policy_version=row[8],
                    risk_tier=row[9],
                    budget_decision=row[10],
                    approval_id=row[11],
                    tool_name=row[12],
                    input_hash=row[13],
                    output_hash=row[14],
                    trace_id=row[15],
                    prev_event_hash=row[16],
                    event_hash=row[17],
                    timestamp=row[18],
                    detail=dict(detail),
                ))
            return events

        result = self._safe_execute(_read)
        return result if isinstance(result, list) else []

    def status(self) -> dict[str, Any]:
        return {
            "backend": "postgresql",
            "available": self._conn is not None,
            "driver_available": self._available,
        }

    def claim_ready_commands(
        self,
        *,
        worker_id: str,
        states: tuple[CommandState, ...],
        leased_at: str,
        lease_expires_at: str,
        limit: int,
    ) -> list[CommandEnvelope]:
        if limit < 1 or not states:
            return []

        def _claim() -> list[CommandEnvelope]:
            claimed: list[CommandEnvelope] = []
            state_values = tuple(state.value for state in states)
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT command_id, tenant_id, actor_id, source, conversation_id, "
                        "idempotency_key, intent, payload_hash, redacted_payload, state, "
                        "policy_version, trace_id, created_at "
                        "FROM gateway_commands c "
                        "WHERE c.state = ANY(%s) "
                        "AND NOT EXISTS ("
                        "  SELECT 1 FROM gateway_command_locks l "
                        "  WHERE l.command_id = c.command_id AND l.lease_expires_at > %s"
                        ") "
                        "ORDER BY c.created_at ASC LIMIT %s",
                        (list(state_values), leased_at, limit),
                    )
                    rows = cur.fetchall()
                    for row in rows:
                        cur.execute(
                            "INSERT INTO gateway_command_locks "
                            "(command_id, worker_id, leased_at, lease_expires_at) "
                            "VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (command_id) DO UPDATE SET "
                            "worker_id = EXCLUDED.worker_id, "
                            "leased_at = EXCLUDED.leased_at, "
                            "lease_expires_at = EXCLUDED.lease_expires_at "
                            "WHERE gateway_command_locks.lease_expires_at <= %s",
                            (row[0], worker_id, leased_at, lease_expires_at, leased_at),
                        )
                        if cur.rowcount < 1:
                            continue
                        payload = row[8]
                        if isinstance(payload, str):
                            payload = json.loads(payload)
                        claimed.append(CommandEnvelope(
                            command_id=row[0],
                            tenant_id=row[1],
                            actor_id=row[2],
                            source=row[3],
                            conversation_id=row[4],
                            idempotency_key=row[5],
                            intent=row[6],
                            payload_hash=row[7],
                            redacted_payload=dict(payload),
                            state=CommandState(row[9]),
                            policy_version=row[10],
                            trace_id=row[11],
                            created_at=row[12],
                        ))
                    self._conn.commit()
            return claimed

        result = self._safe_execute(_claim)
        return result if isinstance(result, list) else []

    def release_command(self, command_id: str, worker_id: str) -> None:
        def _release() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM gateway_command_locks "
                        "WHERE command_id = %s AND worker_id = %s",
                        (command_id, worker_id),
                    )
                    self._conn.commit()

        self._safe_execute(_release)

    def unanchored_events(self) -> list[CommandEvent]:
        def _read() -> list[CommandEvent]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT to_event_hash FROM gateway_command_anchors ORDER BY anchored_at DESC LIMIT 1")
                    anchor_row = cur.fetchone()
                    latest_anchor_hash = anchor_row[0] if anchor_row is not None else ""
                    if latest_anchor_hash:
                        cur.execute(
                            "SELECT timestamp FROM gateway_command_events WHERE event_hash = %s LIMIT 1",
                            (latest_anchor_hash,),
                        )
                        event_row = cur.fetchone()
                        if event_row is None:
                            latest_anchor_hash = ""
                    if latest_anchor_hash:
                        cur.execute(
                            "SELECT event_id, command_id, tenant_id, actor_id, source_channel, "
                            "idempotency_key, previous_state, next_state, policy_version, risk_tier, "
                            "budget_decision, approval_id, tool_name, input_hash, output_hash, "
                            "trace_id, prev_event_hash, event_hash, timestamp, detail "
                            "FROM gateway_command_events WHERE timestamp > ("
                            "  SELECT timestamp FROM gateway_command_events WHERE event_hash = %s LIMIT 1"
                            ") ORDER BY timestamp, event_id",
                            (latest_anchor_hash,),
                        )
                    else:
                        cur.execute(
                            "SELECT event_id, command_id, tenant_id, actor_id, source_channel, "
                            "idempotency_key, previous_state, next_state, policy_version, risk_tier, "
                            "budget_decision, approval_id, tool_name, input_hash, output_hash, "
                            "trace_id, prev_event_hash, event_hash, timestamp, detail "
                            "FROM gateway_command_events ORDER BY timestamp, event_id"
                        )
                    rows = cur.fetchall()
            return [self._row_to_event(row) for row in rows]

        result = self._safe_execute(_read)
        return result if isinstance(result, list) else []

    def append_anchor(self, anchor: CommandAnchor) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_command_anchors "
                        "(anchor_id, from_event_hash, to_event_hash, event_count, merkle_root, "
                        "signature, signature_key_id, anchored_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (anchor_id) DO NOTHING",
                        (
                            anchor.anchor_id, anchor.from_event_hash, anchor.to_event_hash,
                            anchor.event_count, anchor.merkle_root, anchor.signature,
                            anchor.signature_key_id, anchor.anchored_at,
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def list_anchors(self, limit: int = 50) -> list[CommandAnchor]:
        def _read() -> list[CommandAnchor]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT anchor_id, from_event_hash, to_event_hash, event_count, "
                        "merkle_root, signature, signature_key_id, anchored_at "
                        "FROM gateway_command_anchors ORDER BY anchored_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cur.fetchall()
            return [
                CommandAnchor(
                    anchor_id=row[0],
                    from_event_hash=row[1],
                    to_event_hash=row[2],
                    event_count=int(row[3]),
                    merkle_root=row[4],
                    signature=row[5],
                    signature_key_id=row[6],
                    anchored_at=row[7],
                )
                for row in rows
            ]

        result = self._safe_execute(_read)
        return result if isinstance(result, list) else []

    def latest_event_hash(self) -> str:
        def _read() -> str:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT event_hash FROM gateway_command_events "
                        "ORDER BY timestamp DESC, event_id DESC LIMIT 1"
                    )
                    row = cur.fetchone()
            return row[0] if row is not None else ""

        result = self._safe_execute(_read)
        return result if isinstance(result, str) else ""

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _row_to_event(self, row: Any) -> CommandEvent:
        detail = row[19]
        if isinstance(detail, str):
            detail = json.loads(detail)
        return CommandEvent(
            event_id=row[0],
            command_id=row[1],
            tenant_id=row[2],
            actor_id=row[3],
            source_channel=row[4],
            idempotency_key=row[5],
            previous_state=CommandState(row[6]),
            next_state=CommandState(row[7]),
            policy_version=row[8],
            risk_tier=row[9],
            budget_decision=row[10],
            approval_id=row[11],
            tool_name=row[12],
            input_hash=row[13],
            output_hash=row[14],
            trace_id=row[15],
            prev_event_hash=row[16],
            event_hash=row[17],
            timestamp=row[18],
            detail=dict(detail),
        )


def canonical_hash(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _compute_merkle_root(hashes: list[str]) -> str:
    """Compute a deterministic binary Merkle root for event hashes."""
    if not hashes:
        return hashlib.sha256(b"empty").hexdigest()
    if len(hashes) == 1:
        return hashes[0]
    level = [hashlib.sha256(item.encode()).digest() for item in hashes]
    while len(level) > 1:
        next_level: list[bytes] = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1] if index + 1 < len(level) else left
            next_level.append(hashlib.sha256(left + right).digest())
        level = next_level
    return level[0].hex()


def _anchor_signature_payload(anchor: CommandAnchor) -> str:
    """Return canonical payload signed for a command anchor."""
    return canonical_hash({
        "from_event_hash": anchor.from_event_hash,
        "to_event_hash": anchor.to_event_hash,
        "event_count": anchor.event_count,
        "merkle_root": anchor.merkle_root,
        "signature_key_id": anchor.signature_key_id,
        "anchored_at": anchor.anchored_at,
    })


def _anchor_signature(anchor: CommandAnchor, *, signing_secret: str) -> str:
    """Return HMAC signature for an anchor payload."""
    return hmac.new(
        signing_secret.encode(),
        _anchor_signature_payload(anchor).encode(),
        hashlib.sha256,
    ).hexdigest()


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the gateway-safe command payload.

    The gateway does not own the full PII scanner. This placeholder preserves
    structure and leaves semantic redaction to the governed session layer.
    """
    return dict(payload)


_CAPABILITY_PASSPORTS: dict[str, CapabilityPassport] = {
    "llm_completion": CapabilityPassport(
        capability="llm_completion",
        version="1",
        risk_tier="low",
        input_schema="TextCompletionIntent.v1",
        output_schema="GatewayResponse.v1",
        authority_required=("tenant_member",),
        requires=("tenant_bound", "governed_session"),
        mutates_world=False,
        external_system="model_provider",
        rollback_type="irreversible",
        compensation_capability="create_correction_response",
        proof_required_fields=("command_id", "trace_id", "output_hash"),
        declared_effects=("response_emitted",),
        forbidden_effects=("unauthorized_state_mutation",),
        evidence_required=("command_id", "trace_id", "output_hash"),
        graph_projection={
            "nodes": ("command", "provider_action", "verification"),
            "edges": ("verified_by", "produced"),
        },
    ),
    "financial.balance_check": CapabilityPassport(
        capability="financial.balance_check",
        version="1",
        risk_tier="low",
        input_schema="FinancialBalanceIntent.v1",
        output_schema="FinancialBalanceReceipt.v1",
        authority_required=("financial_viewer",),
        requires=("tenant_bound", "provider_scope", "read_only"),
        mutates_world=False,
        external_system="financial_provider",
        rollback_type="irreversible",
        proof_required_fields=("command_id", "provider_receipt_hash"),
        declared_effects=("balance_snapshot_read", "provider_receipt_received"),
        forbidden_effects=("account_state_mutation", "budget_mutation"),
        evidence_required=("command_id", "provider_receipt_hash"),
        graph_projection={
            "nodes": ("command", "provider_action", "verification"),
            "edges": ("verified_by", "produced"),
        },
    ),
    "financial.transaction_history": CapabilityPassport(
        capability="financial.transaction_history",
        version="1",
        risk_tier="low",
        input_schema="FinancialHistoryIntent.v1",
        output_schema="FinancialHistoryReceipt.v1",
        authority_required=("financial_viewer",),
        requires=("tenant_bound", "provider_scope", "read_only"),
        mutates_world=False,
        external_system="financial_provider",
        rollback_type="irreversible",
        proof_required_fields=("command_id", "provider_receipt_hash"),
        declared_effects=("transaction_history_read", "provider_receipt_received"),
        forbidden_effects=("account_state_mutation", "budget_mutation"),
        evidence_required=("command_id", "provider_receipt_hash"),
        graph_projection={
            "nodes": ("command", "provider_action", "verification"),
            "edges": ("verified_by", "produced"),
        },
    ),
    "financial.spending_insights": CapabilityPassport(
        capability="financial.spending_insights",
        version="1",
        risk_tier="low",
        input_schema="FinancialInsightsIntent.v1",
        output_schema="FinancialInsightsReceipt.v1",
        authority_required=("financial_viewer",),
        requires=("tenant_bound", "provider_scope", "read_only"),
        mutates_world=False,
        external_system="financial_provider",
        rollback_type="irreversible",
        proof_required_fields=("command_id", "provider_receipt_hash"),
        declared_effects=("spending_insights_read", "provider_receipt_received"),
        forbidden_effects=("account_state_mutation", "budget_mutation"),
        evidence_required=("command_id", "provider_receipt_hash"),
        graph_projection={
            "nodes": ("command", "provider_action", "verification"),
            "edges": ("verified_by", "produced"),
        },
    ),
    "financial.send_payment": CapabilityPassport(
        capability="financial.send_payment",
        version="1",
        risk_tier="high",
        input_schema="PaymentIntent.v1",
        output_schema="PaymentReceipt.v1",
        authority_required=("financial_admin",),
        requires=("tenant_bound", "budget_reserved", "approval:high_risk", "idempotency_key"),
        mutates_world=True,
        external_system="payment_provider",
        rollback_type="compensatable",
        compensation_capability="financial.refund",
        proof_required_fields=("transaction_id", "amount", "currency", "recipient_hash", "ledger_hash"),
        declared_effects=(
            "payment_provider_request_created",
            "payment_receipt_received",
            "ledger_entry_created",
            "tenant_budget_decremented",
        ),
        forbidden_effects=(
            "duplicate_payment",
            "amount_mismatch",
            "recipient_mismatch",
            "unapproved_budget_mutation",
        ),
        evidence_required=("transaction_id", "amount", "currency", "recipient_hash", "ledger_hash"),
        graph_projection={
            "nodes": ("command", "approval", "provider_action", "verification", "evidence"),
            "edges": ("decided_by", "verified_by", "produced"),
        },
    ),
    "financial.refund": CapabilityPassport(
        capability="financial.refund",
        version="1",
        risk_tier="high",
        input_schema="RefundIntent.v1",
        output_schema="RefundReceipt.v1",
        authority_required=("financial_admin",),
        requires=("tenant_bound", "approval:high_risk", "idempotency_key"),
        mutates_world=True,
        external_system="payment_provider",
        rollback_type="compensatable",
        compensation_capability="create_financial_incident",
        proof_required_fields=("refund_id", "transaction_id", "ledger_hash"),
        declared_effects=(
            "refund_provider_request_created",
            "refund_receipt_received",
            "ledger_entry_created",
        ),
        forbidden_effects=("duplicate_refund", "amount_mismatch", "unapproved_budget_mutation"),
        evidence_required=("refund_id", "transaction_id", "ledger_hash"),
        graph_projection={
            "nodes": ("command", "approval", "provider_action", "verification", "evidence"),
            "edges": ("decided_by", "verified_by", "produced"),
        },
    ),
}


def compile_typed_intent(command: CommandEnvelope) -> TypedIntent:
    """Compile a command payload into a typed intent contract."""
    skill_intent = command.redacted_payload.get("skill_intent")
    if isinstance(skill_intent, dict):
        skill = skill_intent.get("skill")
        action = skill_intent.get("action")
        params = skill_intent.get("params", {})
        if not isinstance(skill, str) or not skill:
            raise ValueError("skill intent requires skill")
        if not isinstance(action, str) or not action:
            raise ValueError("skill intent requires action")
        if not isinstance(params, dict):
            raise ValueError("skill intent params must be an object")
        name = f"{skill}.{action}"
        schema_name = f"{skill}.{action}.intent.v1"
        typed_params = dict(params)
    else:
        name = "llm_completion"
        schema_name = "llm_completion.intent.v1"
        typed_params = {"body_hash": canonical_hash({"body": str(command.redacted_payload.get("body", ""))})}

    return TypedIntent(
        schema_name=schema_name,
        name=name,
        params=typed_params,
        source_text_hash=canonical_hash({"body": str(command.redacted_payload.get("body", ""))}),
        payload_hash=command.payload_hash,
    )


def capability_passport_for(intent_name: str) -> CapabilityPassport:
    """Return the capability passport for a compiled intent."""
    passport = _CAPABILITY_PASSPORTS.get(intent_name)
    if passport is None:
        raise ValueError(f"missing capability passport for intent: {intent_name}")
    return passport


def _require_passport_effect_contract(passport: CapabilityPassport) -> None:
    """Fail closed when an effect-bearing passport lacks assurance semantics."""
    requires_effect_contract = passport.mutates_world or passport.risk_tier == "high"
    if not requires_effect_contract:
        return
    if not passport.declared_effects:
        raise ValueError("effect-bearing capability requires declared effects")
    if not passport.forbidden_effects:
        raise ValueError("effect-bearing capability requires forbidden effects")
    evidence_required = passport.evidence_required or passport.proof_required_fields
    if not evidence_required:
        raise ValueError("effect-bearing capability requires evidence")
    projected_nodes = tuple(passport.graph_projection.get("nodes", ()))
    projected_edges = tuple(passport.graph_projection.get("edges", ()))
    if not projected_nodes or not projected_edges:
        raise ValueError("effect-bearing capability requires graph projection")


def build_governed_action(
    command: CommandEnvelope,
    typed_intent: TypedIntent,
    passport: CapabilityPassport,
    *,
    approval_id: str | None = None,
    predicted_effect_hash: str | None = None,
    rollback_plan_hash: str | None = None,
    state: str = CommandState.GOVERNED_ACTION_BOUND.value,
) -> GovernedAction:
    """Bind typed meaning and capability authority into one governed unit."""
    if typed_intent.name != passport.capability:
        raise ValueError("typed intent and capability passport mismatch")
    _require_passport_effect_contract(passport)
    if passport.mutates_world and not passport.proof_required_fields:
        raise ValueError("mutating capability requires proof fields")
    if passport.rollback_type not in {"reversible", "compensatable", "irreversible"}:
        raise ValueError("rollback_type is invalid")
    if passport.mutates_world and passport.rollback_type == "irreversible" and not passport.compensation_capability:
        raise ValueError("mutating irreversible capability requires compensation")
    if passport.mutates_world and passport.rollback_type == "reversible" and not passport.rollback_capability:
        raise ValueError("mutating reversible capability requires rollback capability")
    if passport.mutates_world and passport.rollback_type == "compensatable" and not passport.compensation_capability:
        raise ValueError("mutating compensatable capability requires compensation capability")

    typed_intent_payload = asdict(typed_intent)
    passport_payload = asdict(passport)
    return GovernedAction(
        command_id=command.command_id,
        tenant_id=command.tenant_id,
        actor_id=command.actor_id,
        typed_intent=typed_intent_payload,
        intent_schema=typed_intent.schema_name,
        intent_hash=canonical_hash(typed_intent_payload),
        capability=passport.capability,
        capability_version=passport.version,
        capability_passport_hash=canonical_hash(passport_payload),
        risk_tier=passport.risk_tier,
        authority_required=passport.authority_required,
        approval_id=approval_id,
        predicted_effect_hash=predicted_effect_hash,
        rollback_plan_hash=rollback_plan_hash,
        state=state,
    )


def predict_effects(action: GovernedAction, passport: CapabilityPassport) -> EffectPrediction:
    """Predict expected mutations, calls, receipts, and recovery path."""
    declared_mutating_effects = tuple(
        effect for effect in passport.declared_effects
        if "read" not in effect and "response" not in effect
    )
    expected_mutations: tuple[str, ...] = ()
    if passport.mutates_world:
        expected_mutations = tuple(dict.fromkeys((
            f"{action.tenant_id}:ledger_entry",
            f"{action.tenant_id}:capability_effect:{passport.capability}",
            *declared_mutating_effects,
        )))

    expected_external_calls: tuple[str, ...] = ()
    if passport.external_system:
        expected_external_calls = (passport.external_system,)

    rollback_plan: tuple[str, ...] = ()
    if passport.rollback_type == "reversible" and passport.rollback_capability:
        rollback_plan = (passport.rollback_capability,)
    elif passport.compensation_capability:
        rollback_plan = (passport.compensation_capability,)

    risk_notes = (
        f"risk_tier:{passport.risk_tier}",
        f"rollback_type:{passport.rollback_type}",
    )
    return EffectPrediction(
        command_id=action.command_id,
        capability=action.capability,
        expected_mutations=expected_mutations,
        expected_external_calls=expected_external_calls,
        expected_receipts=passport.evidence_required or passport.proof_required_fields,
        rollback_plan=rollback_plan,
        risk_notes=risk_notes,
    )


def build_recovery_plan(
    action: GovernedAction,
    passport: CapabilityPassport,
    prediction: EffectPrediction,
) -> RecoveryPlan:
    """Build the rollback or compensation contract for a command."""
    recovery_capabilities = prediction.rollback_plan
    requires_higher_approval = bool(passport.mutates_world and not recovery_capabilities)
    operator_review_required = requires_higher_approval or passport.rollback_type == "irreversible"
    if passport.mutates_world and not recovery_capabilities:
        raise ValueError("mutating capability requires rollback or compensation plan")
    return RecoveryPlan(
        command_id=action.command_id,
        capability=action.capability,
        recovery_type=passport.rollback_type,
        recovery_capabilities=recovery_capabilities,
        requires_higher_approval=requires_higher_approval,
        operator_review_required=operator_review_required,
        proof_required_fields=passport.evidence_required or passport.proof_required_fields,
    )


def build_effect_plan_payload(
    action: GovernedAction,
    prediction: EffectPrediction,
    passport: CapabilityPassport,
    *,
    effect_plan_id: str,
    created_at: str,
) -> dict[str, Any]:
    """Build an EffectPlan-compatible JSON payload for command-event anchoring."""
    expected_effects: list[dict[str, Any]] = []
    seen_effect_ids: set[str] = set()
    for effect in passport.declared_effects:
        seen_effect_ids.add(effect)
        expected_effects.append({
            "effect_id": effect,
            "name": effect,
            "target_ref": f"command:{action.command_id}:effect:{effect}",
            "required": True,
            "verification_method": "declared_effect",
            "expected_value": None,
        })
    for mutation in prediction.expected_mutations:
        if mutation in seen_effect_ids:
            continue
        seen_effect_ids.add(mutation)
        expected_effects.append({
            "effect_id": mutation,
            "name": mutation,
            "target_ref": mutation,
            "required": True,
            "verification_method": "mutation_receipt",
            "expected_value": None,
        })
    for receipt in prediction.expected_receipts:
        if receipt in seen_effect_ids:
            continue
        seen_effect_ids.add(receipt)
        expected_effects.append({
            "effect_id": receipt,
            "name": receipt,
            "target_ref": f"{action.command_id}:receipt:{receipt}",
            "required": True,
            "verification_method": "receipt_field",
            "expected_value": None,
        })
    if not expected_effects:
        expected_effects.append({
            "effect_id": "response_emitted",
            "name": "response_emitted",
            "target_ref": f"command:{action.command_id}",
            "required": True,
            "verification_method": "output_hash",
            "expected_value": None,
        })
    if passport.forbidden_effects:
        forbidden_effects = passport.forbidden_effects
    elif passport.mutates_world:
        forbidden_effects = (
            "duplicate_dispatch",
            "unapproved_budget_mutation",
            "recipient_mismatch",
            "amount_mismatch",
        )
    else:
        forbidden_effects = ("unauthorized_state_mutation",)
    projected_nodes = tuple(passport.graph_projection.get("nodes", ()))
    projected_edges = tuple(passport.graph_projection.get("edges", ()))
    return {
        "effect_plan_id": effect_plan_id,
        "command_id": action.command_id,
        "tenant_id": action.tenant_id,
        "capability_id": action.capability,
        "expected_effects": expected_effects,
        "forbidden_effects": list(forbidden_effects),
        "rollback_plan_id": passport.rollback_capability or None,
        "compensation_plan_id": passport.compensation_capability or None,
        "graph_node_refs": [
            f"command:{action.command_id}",
            f"capability:{action.capability}",
            f"effect_plan:{effect_plan_id}",
            *(f"projected:{node}" for node in projected_nodes),
        ],
        "graph_edge_refs": [
            "command depends_on capability",
            "command produced effect_plan",
            *(f"projected:{edge}" for edge in projected_edges),
        ],
        "created_at": created_at,
    }


def observe_effects(
    prediction: EffectPrediction,
    *,
    output_hash: str,
    output: dict[str, Any],
) -> EffectObservation:
    """Build an observed effect contract from dispatch output."""
    output_receipts = tuple(str(key) for key in sorted(output))
    actual_receipts = tuple(dict.fromkeys((
        "command_id",
        "trace_id",
        "output_hash",
        *output_receipts,
        *(prediction.expected_receipts if not prediction.expected_mutations else ()),
    )))
    actual_mutations = prediction.expected_mutations if "error" not in output else ()
    actual_external_calls = prediction.expected_external_calls
    return EffectObservation(
        command_id=prediction.command_id,
        actual_mutations=actual_mutations,
        actual_external_calls=actual_external_calls,
        actual_receipts=actual_receipts,
    )


def build_observed_effect_payloads(observation: EffectObservation, *, observed_at: str) -> list[dict[str, Any]]:
    """Build ObservedEffect-compatible JSON payloads from a command observation."""
    effects: list[dict[str, Any]] = []
    for mutation in observation.actual_mutations:
        effects.append({
            "effect_id": mutation,
            "name": mutation,
            "source": "command_output",
            "observed_value": mutation,
            "evidence_ref": f"mutation:{observation.command_id}:{mutation}",
            "observed_at": observed_at,
        })
    for receipt in observation.actual_receipts:
        effects.append({
            "effect_id": receipt,
            "name": receipt,
            "source": "command_output",
            "observed_value": receipt,
            "evidence_ref": f"receipt:{observation.command_id}:{receipt}",
            "observed_at": observed_at,
        })
    return effects


def build_effect_verification_payload(
    reconciliation: EffectReconciliation,
    *,
    verification_id: str,
    execution_id: str,
    observed_effects: list[dict[str, Any]],
    closed_at: str,
) -> dict[str, Any]:
    """Build verification-result compatible payload for effect assurance."""
    status = "pass" if reconciliation.reconciled else "fail"
    return {
        "verification_id": verification_id,
        "execution_id": execution_id,
        "status": status,
        "checks": [{
            "name": "effect_reconciliation",
            "status": status,
            "details": {
                "mismatch_reason": reconciliation.mismatch_reason,
                "predicted_effect_hash": reconciliation.predicted_effect_hash,
                "observed_effect_hash": reconciliation.observed_effect_hash,
            },
        }],
        "evidence": [
            {
                "description": f"Observed effect {effect['name']}",
                "uri": str(effect["evidence_ref"]),
                "details": {
                    "effect_id": effect["effect_id"],
                    "source": effect["source"],
                    "observed_at": effect["observed_at"],
                },
            }
            for effect in observed_effects
        ] or [{
            "description": "No observed effects available",
            "uri": f"command:{execution_id}",
            "details": {"mismatch_reason": reconciliation.mismatch_reason},
        }],
        "closed_at": closed_at,
        "metadata": {"command_id": reconciliation.command_id},
        "extensions": {},
    }


def build_effect_assurance_reconciliation_payload(
    reconciliation: EffectReconciliation,
    *,
    reconciliation_id: str,
    effect_plan_id: str,
    verification_result_id: str,
    decided_at: str,
) -> dict[str, Any]:
    """Build EffectReconciliation-compatible JSON payload from command reconciliation."""
    status = "match" if reconciliation.reconciled else "mismatch"
    return {
        "reconciliation_id": reconciliation_id,
        "command_id": reconciliation.command_id,
        "effect_plan_id": effect_plan_id,
        "status": status,
        "matched_effects": ["effect_prediction"] if reconciliation.reconciled else [],
        "missing_effects": [] if reconciliation.reconciled else [reconciliation.mismatch_reason],
        "unexpected_effects": [],
        "verification_result_id": verification_result_id,
        "case_id": None if reconciliation.reconciled else f"case-{reconciliation.command_id}",
        "decided_at": decided_at,
    }


def reconcile_effects(
    prediction: EffectPrediction,
    observation: EffectObservation,
    *,
    predicted_effect_hash: str,
    observed_effect_hash: str,
) -> EffectReconciliation:
    """Compare predicted and observed effects."""
    missing_external_calls = tuple(
        call for call in prediction.expected_external_calls
        if call not in observation.actual_external_calls
    )
    missing_receipts = tuple(
        receipt for receipt in prediction.expected_receipts
        if receipt not in observation.actual_receipts
    )
    if observation.mismatch:
        return EffectReconciliation(
            command_id=prediction.command_id,
            predicted_effect_hash=predicted_effect_hash,
            observed_effect_hash=observed_effect_hash,
            reconciled=False,
            mismatch_reason=observation.mismatch_reason or "effect_observation_mismatch",
        )
    if missing_external_calls:
        return EffectReconciliation(
            command_id=prediction.command_id,
            predicted_effect_hash=predicted_effect_hash,
            observed_effect_hash=observed_effect_hash,
            reconciled=False,
            mismatch_reason=f"missing_external_calls:{','.join(missing_external_calls)}",
        )
    if missing_receipts:
        return EffectReconciliation(
            command_id=prediction.command_id,
            predicted_effect_hash=predicted_effect_hash,
            observed_effect_hash=observed_effect_hash,
            reconciled=False,
            mismatch_reason=f"missing_receipts:{','.join(missing_receipts)}",
        )
    return EffectReconciliation(
        command_id=prediction.command_id,
        predicted_effect_hash=predicted_effect_hash,
        observed_effect_hash=observed_effect_hash,
        reconciled=True,
    )


class CommandLedger:
    """In-memory command ledger with hash-linked transition events."""

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        policy_version: str = "gateway-policy-v1",
        store: CommandLedgerStore | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._policy_version = policy_version
        self._commands: dict[str, CommandEnvelope] = {}
        self._events: list[CommandEvent] = []
        self._governed_actions: dict[str, GovernedAction] = {}
        self._effect_predictions: dict[str, EffectPrediction] = {}
        self._recovery_plans: dict[str, RecoveryPlan] = {}
        self._effect_observations: dict[str, EffectObservation] = {}
        self._effect_reconciliations: dict[str, EffectReconciliation] = {}
        self._claims: dict[str, list[Claim]] = {}
        self._evidence_records: dict[str, list[EvidenceRecord]] = {}
        self._fracture_results: dict[str, FractureResult] = {}
        self._store = store or InMemoryCommandLedgerStore()
        self._last_event_hash = self._store.latest_event_hash()

    def create_command(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        source: str,
        conversation_id: str,
        idempotency_key: str,
        intent: str,
        payload: dict[str, Any],
    ) -> CommandEnvelope:
        """Create a command and append its RECEIVED witness event."""
        now = self._clock()
        command_id = f"cmd-{uuid4().hex}"
        payload_hash = canonical_hash(payload)
        command = CommandEnvelope(
            command_id=command_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            source=source,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            intent=intent,
            payload_hash=payload_hash,
            redacted_payload=redact_payload(payload),
            state=CommandState.RECEIVED,
            policy_version=self._policy_version,
            trace_id=f"trc-{uuid4().hex}",
            created_at=now,
        )
        self._commands[command_id] = command
        self._store.save_command(command)
        self._append_event(
            command,
            previous_state=CommandState.RECEIVED,
            next_state=CommandState.RECEIVED,
            input_hash=payload_hash,
            detail={"cause": "gateway_ingress"},
        )
        return command

    def get(self, command_id: str) -> CommandEnvelope | None:
        """Return the current command envelope."""
        command = self._commands.get(command_id)
        if command is not None:
            return command
        command = self._store.load_command(command_id)
        if command is not None:
            self._commands[command_id] = command
        return command

    def bind_governed_action(self, command_id: str) -> GovernedAction:
        """Compile intent, bind capability passport, and witness the action."""
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")

        typed_intent = compile_typed_intent(command)
        self.transition(
            command.command_id,
            CommandState.INTENT_COMPILED,
            detail={
                "cause": "typed_intent_compiled",
                "intent_name": typed_intent.name,
                "intent_hash": canonical_hash(asdict(typed_intent)),
            },
        )
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")

        passport = capability_passport_for(typed_intent.name)
        self.transition(
            command.command_id,
            CommandState.CAPABILITY_BOUND,
            risk_tier=passport.risk_tier,
            detail={
                "cause": "capability_passport_bound",
                "capability": passport.capability,
                "capability_version": passport.version,
                "capability_passport_hash": canonical_hash(asdict(passport)),
                "authority_required": list(passport.authority_required),
            },
        )
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")

        action = build_governed_action(command, typed_intent, passport)
        self._governed_actions[command_id] = action
        self.transition(
            command.command_id,
            CommandState.GOVERNED_ACTION_BOUND,
            risk_tier=action.risk_tier,
            detail={
                "cause": "governed_action_bound",
                "governed_action": asdict(action),
            },
        )
        return self.bind_effect_prediction(command.command_id, passport=passport)

    def bind_effect_prediction(
        self,
        command_id: str,
        *,
        passport: CapabilityPassport | None = None,
    ) -> GovernedAction:
        """Predict command effects and bind the prediction hash to the action."""
        action = self.governed_action_for(command_id)
        if action is None:
            raise KeyError(f"missing governed action for command_id: {command_id}")
        capability_passport = passport or capability_passport_for(action.capability)
        prediction = predict_effects(action, capability_passport)
        prediction_payload = asdict(prediction)
        prediction_hash = canonical_hash(prediction_payload)
        rollback_plan_hash = canonical_hash({"rollback_plan": prediction.rollback_plan})
        updated_action = GovernedAction(
            command_id=action.command_id,
            tenant_id=action.tenant_id,
            actor_id=action.actor_id,
            typed_intent=action.typed_intent,
            intent_schema=action.intent_schema,
            intent_hash=action.intent_hash,
            capability=action.capability,
            capability_version=action.capability_version,
            capability_passport_hash=action.capability_passport_hash,
            risk_tier=action.risk_tier,
            authority_required=action.authority_required,
            approval_id=action.approval_id,
            predicted_effect_hash=prediction_hash,
            rollback_plan_hash=rollback_plan_hash,
            state=CommandState.EFFECT_PREDICTED.value,
        )
        self._effect_predictions[command_id] = prediction
        self._governed_actions[command_id] = updated_action
        self.transition(
            command_id,
            CommandState.EFFECT_PREDICTED,
            risk_tier=updated_action.risk_tier,
            detail={
                "cause": "effect_prediction_bound",
                "effect_prediction": prediction_payload,
                "predicted_effect_hash": prediction_hash,
                "rollback_plan_hash": rollback_plan_hash,
                "governed_action": asdict(updated_action),
            },
        )
        return self.bind_recovery_plan(command_id, passport=capability_passport, prediction=prediction)

    def bind_recovery_plan(
        self,
        command_id: str,
        *,
        passport: CapabilityPassport | None = None,
        prediction: EffectPrediction | None = None,
    ) -> GovernedAction:
        """Bind rollback or compensation plan to a governed action."""
        action = self.governed_action_for(command_id)
        if action is None:
            raise KeyError(f"missing governed action for command_id: {command_id}")
        effect_prediction = prediction or self.effect_prediction_for(command_id)
        if effect_prediction is None:
            raise ValueError("effect prediction is required before recovery planning")
        capability_passport = passport or capability_passport_for(action.capability)
        recovery_plan = build_recovery_plan(action, capability_passport, effect_prediction)
        recovery_plan_hash = canonical_hash(asdict(recovery_plan))
        updated_action = GovernedAction(
            command_id=action.command_id,
            tenant_id=action.tenant_id,
            actor_id=action.actor_id,
            typed_intent=action.typed_intent,
            intent_schema=action.intent_schema,
            intent_hash=action.intent_hash,
            capability=action.capability,
            capability_version=action.capability_version,
            capability_passport_hash=action.capability_passport_hash,
            risk_tier=action.risk_tier,
            authority_required=action.authority_required,
            approval_id=action.approval_id,
            predicted_effect_hash=action.predicted_effect_hash,
            rollback_plan_hash=recovery_plan_hash,
            state=CommandState.EFFECT_PLANNED.value,
        )
        self._recovery_plans[command_id] = recovery_plan
        self._governed_actions[command_id] = updated_action
        effect_plan_id = f"effect-plan-{canonical_hash({
            'command_id': command_id,
            'predicted_effect_hash': action.predicted_effect_hash or '',
        })[:12]}"
        effect_plan = build_effect_plan_payload(
            updated_action,
            effect_prediction,
            capability_passport,
            effect_plan_id=effect_plan_id,
            created_at=self._clock(),
        )
        self.transition(
            command_id,
            CommandState.EFFECT_PLANNED,
            risk_tier=updated_action.risk_tier,
            detail={
                "cause": "recovery_plan_bound",
                "effect_plan": effect_plan,
                "effect_plan_hash": canonical_hash(effect_plan),
                "recovery_plan": asdict(recovery_plan),
                "rollback_plan_hash": recovery_plan_hash,
                "governed_action": asdict(updated_action),
            },
        )
        return updated_action

    def governed_action_for(self, command_id: str) -> GovernedAction | None:
        """Return the bound governed action for a command when available."""
        action = self._governed_actions.get(command_id)
        if action is not None:
            return action
        events = self.events_for(command_id)
        for event in reversed(events):
            raw_action = event.detail.get("governed_action")
            if not isinstance(raw_action, dict):
                continue
            try:
                action = GovernedAction(
                    command_id=str(raw_action["command_id"]),
                    tenant_id=str(raw_action["tenant_id"]),
                    actor_id=str(raw_action["actor_id"]),
                    typed_intent=dict(raw_action["typed_intent"]),
                    intent_schema=str(raw_action["intent_schema"]),
                    intent_hash=str(raw_action["intent_hash"]),
                    capability=str(raw_action["capability"]),
                    capability_version=str(raw_action["capability_version"]),
                    capability_passport_hash=str(raw_action["capability_passport_hash"]),
                    risk_tier=str(raw_action["risk_tier"]),
                    authority_required=tuple(raw_action["authority_required"]),
                    approval_id=raw_action.get("approval_id"),
                    predicted_effect_hash=raw_action.get("predicted_effect_hash"),
                    rollback_plan_hash=raw_action.get("rollback_plan_hash"),
                    state=str(raw_action["state"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._governed_actions[command_id] = action
            return action
        return None

    def recovery_plan_for(self, command_id: str) -> RecoveryPlan | None:
        """Return the rollback or compensation plan for a command."""
        plan = self._recovery_plans.get(command_id)
        if plan is not None:
            return plan
        events = self.events_for(command_id)
        for event in reversed(events):
            raw_plan = event.detail.get("recovery_plan")
            if not isinstance(raw_plan, dict):
                continue
            try:
                plan = RecoveryPlan(
                    command_id=str(raw_plan["command_id"]),
                    capability=str(raw_plan["capability"]),
                    recovery_type=str(raw_plan["recovery_type"]),
                    recovery_capabilities=tuple(raw_plan["recovery_capabilities"]),
                    requires_higher_approval=bool(raw_plan["requires_higher_approval"]),
                    operator_review_required=bool(raw_plan["operator_review_required"]),
                    proof_required_fields=tuple(raw_plan["proof_required_fields"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._recovery_plans[command_id] = plan
            return plan
        return None

    def effect_prediction_for(self, command_id: str) -> EffectPrediction | None:
        """Return the predicted effect contract for a command when available."""
        prediction = self._effect_predictions.get(command_id)
        if prediction is not None:
            return prediction
        events = self.events_for(command_id)
        for event in reversed(events):
            raw_prediction = event.detail.get("effect_prediction")
            if not isinstance(raw_prediction, dict):
                continue
            try:
                prediction = EffectPrediction(
                    command_id=str(raw_prediction["command_id"]),
                    capability=str(raw_prediction["capability"]),
                    expected_mutations=tuple(raw_prediction["expected_mutations"]),
                    expected_external_calls=tuple(raw_prediction["expected_external_calls"]),
                    expected_receipts=tuple(raw_prediction["expected_receipts"]),
                    rollback_plan=tuple(raw_prediction["rollback_plan"]),
                    risk_notes=tuple(raw_prediction["risk_notes"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._effect_predictions[command_id] = prediction
            return prediction
        return None

    def observe_and_reconcile_effect(
        self,
        command_id: str,
        *,
        output: dict[str, Any],
    ) -> EffectReconciliation:
        """Observe dispatch effects and reconcile them against prediction."""
        action = self.governed_action_for(command_id)
        prediction = self.effect_prediction_for(command_id)
        if action is None:
            raise KeyError(f"missing governed action for command_id: {command_id}")
        if prediction is None or not action.predicted_effect_hash:
            raise ValueError("effect prediction is required before observation")
        output_hash = canonical_hash(output)
        observation = observe_effects(prediction, output_hash=output_hash, output=output)
        observation_hash = canonical_hash(asdict(observation))
        reconciliation = reconcile_effects(
            prediction,
            observation,
            predicted_effect_hash=action.predicted_effect_hash,
            observed_effect_hash=observation_hash,
        )
        observed_at = self._clock()
        observed_effects = build_observed_effect_payloads(observation, observed_at=observed_at)
        verification_closed_at = self._clock()
        verification_id = f"effect-verification-{canonical_hash({
            'command_id': command_id,
            'observed_effect_hash': observation_hash,
            'closed_at': verification_closed_at,
        })[:12]}"
        verification_payload = build_effect_verification_payload(
            reconciliation,
            verification_id=verification_id,
            execution_id=command_id,
            observed_effects=observed_effects,
            closed_at=verification_closed_at,
        )
        effect_plan_id = f"effect-plan-{canonical_hash({
            'command_id': command_id,
            'predicted_effect_hash': action.predicted_effect_hash,
        })[:12]}"
        reconciliation_decided_at = self._clock()
        effect_assurance_reconciliation = build_effect_assurance_reconciliation_payload(
            reconciliation,
            reconciliation_id=f"effect-reconciliation-{canonical_hash({
                'command_id': command_id,
                'observed_effect_hash': observation_hash,
                'decided_at': reconciliation_decided_at,
            })[:12]}",
            effect_plan_id=effect_plan_id,
            verification_result_id=verification_id,
            decided_at=reconciliation_decided_at,
        )
        self._effect_observations[command_id] = observation
        self._effect_reconciliations[command_id] = reconciliation
        self.transition(
            command_id,
            CommandState.EFFECT_OBSERVED,
            risk_tier=action.risk_tier,
            output=asdict(observation),
            detail={
                "cause": "effect_observed",
                "effect_observation": asdict(observation),
                "observed_effects": observed_effects,
                "observed_effect_hash": observation_hash,
            },
        )
        next_state = CommandState.RECONCILED if reconciliation.reconciled else CommandState.REQUIRES_REVIEW
        self.transition(
            command_id,
            next_state,
            risk_tier=action.risk_tier,
            detail={
                "cause": "effect_reconciled" if reconciliation.reconciled else "effect_reconciliation_failed",
                "effect_reconciliation": asdict(reconciliation),
                "effect_verification": verification_payload,
                "effect_assurance_reconciliation": effect_assurance_reconciliation,
            },
        )
        return reconciliation

    def effect_reconciliation_for(self, command_id: str) -> EffectReconciliation | None:
        """Return the latest effect reconciliation for a command."""
        reconciliation = self._effect_reconciliations.get(command_id)
        if reconciliation is not None:
            return reconciliation
        events = self.events_for(command_id)
        for event in reversed(events):
            raw_reconciliation = event.detail.get("effect_reconciliation")
            if not isinstance(raw_reconciliation, dict):
                continue
            try:
                reconciliation = EffectReconciliation(
                    command_id=str(raw_reconciliation["command_id"]),
                    predicted_effect_hash=str(raw_reconciliation["predicted_effect_hash"]),
                    observed_effect_hash=str(raw_reconciliation["observed_effect_hash"]),
                    reconciled=bool(raw_reconciliation["reconciled"]),
                    mismatch_reason=str(raw_reconciliation.get("mismatch_reason", "")),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._effect_reconciliations[command_id] = reconciliation
            return reconciliation
        return None

    def record_operational_claim(
        self,
        command_id: str,
        *,
        text: str,
        verified: bool,
        confidence: float = 1.0,
    ) -> Claim:
        """Record one evidence-backed operational claim."""
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        if not text:
            raise ValueError("claim text is required")
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("claim confidence must be between 0 and 1")

        evidence_records = self._build_evidence_records(command_id, verified=verified)
        evidence_refs = tuple(record.evidence_id for record in evidence_records)
        claim_hash = canonical_hash({
            "command_id": command_id,
            "text": text,
            "evidence_refs": evidence_refs,
            "verified": verified,
            "confidence": confidence,
        })
        claim = Claim(
            claim_id=f"claim-{claim_hash[:16]}",
            command_id=command_id,
            text=text,
            evidence_refs=evidence_refs,
            confidence=confidence,
            verified=verified,
        )
        self._evidence_records.setdefault(command_id, []).extend(evidence_records)
        self._claims.setdefault(command_id, []).append(claim)
        self.transition(
            command_id,
            command.state,
            output=asdict(claim),
            detail={
                "cause": "evidence_claim_recorded",
                "claim": asdict(claim),
                "evidence": [asdict(record) for record in evidence_records],
            },
        )
        return claim

    def claims_for(self, command_id: str) -> list[Claim]:
        """Return recorded claims for one command."""
        claims = self._claims.get(command_id)
        if claims:
            return list(claims)
        loaded: list[Claim] = []
        for event in self.events_for(command_id):
            raw_claim = event.detail.get("claim")
            if not isinstance(raw_claim, dict):
                continue
            try:
                loaded.append(Claim(
                    claim_id=str(raw_claim["claim_id"]),
                    command_id=str(raw_claim["command_id"]),
                    text=str(raw_claim["text"]),
                    evidence_refs=tuple(raw_claim["evidence_refs"]),
                    confidence=float(raw_claim["confidence"]),
                    verified=bool(raw_claim["verified"]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        if loaded:
            self._claims[command_id] = loaded
        return loaded

    def evidence_for(self, command_id: str) -> list[EvidenceRecord]:
        """Return recorded evidence for one command."""
        records = self._evidence_records.get(command_id)
        if records:
            return list(records)
        loaded: list[EvidenceRecord] = []
        for event in self.events_for(command_id):
            raw_records = event.detail.get("evidence")
            if not isinstance(raw_records, list):
                continue
            for raw_record in raw_records:
                if not isinstance(raw_record, dict):
                    continue
                try:
                    loaded.append(EvidenceRecord(
                        evidence_id=str(raw_record["evidence_id"]),
                        command_id=str(raw_record["command_id"]),
                        evidence_type=str(raw_record["evidence_type"]),
                        ref=str(raw_record["ref"]),
                        ref_hash=str(raw_record["ref_hash"]),
                        verified=bool(raw_record["verified"]),
                    ))
                except (KeyError, TypeError, ValueError):
                    continue
        if loaded:
            self._evidence_records[command_id] = loaded
        return loaded

    def close_success_response_evidence(
        self,
        command_id: str,
        *,
        claim_id: str,
    ) -> ResponseEvidenceClosure:
        """Prove a successful response is backed by reconciled evidence."""
        reconciliation = self.effect_reconciliation_for(command_id)
        if reconciliation is None or not reconciliation.reconciled:
            raise ValueError("response requires reconciled observed effects")
        claims = self.claims_for(command_id)
        claim = next((candidate for candidate in claims if candidate.claim_id == claim_id), None)
        if claim is None:
            raise ValueError("response requires evidence-backed claim")
        if not claim.verified:
            raise ValueError("success response requires verified claim")
        if not claim.evidence_refs:
            raise ValueError("success response requires evidence refs")
        evidence_by_id = {
            record.evidence_id: record
            for record in self.evidence_for(command_id)
        }
        missing_refs = tuple(
            evidence_ref for evidence_ref in claim.evidence_refs
            if evidence_ref not in evidence_by_id
        )
        if missing_refs:
            raise ValueError("success response evidence refs must resolve")
        unverified_refs = tuple(
            evidence_ref for evidence_ref in claim.evidence_refs
            if not evidence_by_id[evidence_ref].verified
        )
        if unverified_refs:
            raise ValueError("success response evidence refs must be verified")
        reconciliation_hash = canonical_hash(asdict(reconciliation))
        evidence_payload = [
            asdict(evidence_by_id[evidence_ref])
            for evidence_ref in claim.evidence_refs
        ]
        closure = ResponseEvidenceClosure(
            command_id=command_id,
            claim_id=claim.claim_id,
            reconciliation_hash=reconciliation_hash,
            evidence_refs=claim.evidence_refs,
            evidence_hash=canonical_hash(evidence_payload),
            closed_at=self._clock(),
        )
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        self.transition(
            command_id,
            command.state,
            output=asdict(closure),
            detail={
                "cause": "response_evidence_closed",
                "response_evidence_closure": asdict(closure),
            },
        )
        return closure

    def fracture_test(self, command_id: str) -> FractureResult:
        """Run bounded contradiction checks before high-risk dispatch."""
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        action = self.governed_action_for(command_id)
        prediction = self.effect_prediction_for(command_id)
        recovery_plan = self.recovery_plan_for(command_id)
        events = self.events_for(command_id)
        checks = (
            "governed_action_present",
            "capability_passport_present",
            "effect_prediction_present",
            "recovery_plan_present",
            "approval_present_for_high_risk",
            "duplicate_dispatch_absent",
            "prompt_injection_absent",
        )
        fractures: list[str] = []
        if action is None:
            fractures.append("missing_governed_action")
        else:
            try:
                capability_passport_for(action.capability)
            except ValueError:
                fractures.append("missing_capability_passport")
            if action.risk_tier == "high" and not any(event.next_state == CommandState.APPROVED for event in events):
                fractures.append("missing_high_risk_approval")
        if prediction is None:
            fractures.append("missing_effect_prediction")
        if action is not None and action.risk_tier == "high" and recovery_plan is None:
            fractures.append("missing_recovery_plan")
        if any(event.next_state == CommandState.DISPATCHED for event in events):
            fractures.append("duplicate_dispatch")
        body = str(command.redacted_payload.get("body", "")).lower()
        if "ignore previous" in body or "bypass governance" in body or "disable policy" in body:
            fractures.append("prompt_injection_marker")

        result_payload = {
            "command_id": command_id,
            "checks": checks,
            "fractures": tuple(fractures),
        }
        result = FractureResult(
            command_id=command_id,
            passed=not fractures,
            checks=checks,
            fractures=tuple(fractures),
            result_hash=canonical_hash(result_payload),
        )
        self._fracture_results[command_id] = result
        self.transition(
            command_id,
            CommandState.FRACTURE_TESTED if result.passed else CommandState.REQUIRES_REVIEW,
            risk_tier=action.risk_tier if action is not None else "",
            detail={
                "cause": "fracture_tested" if result.passed else "fracture_failed",
                "fracture_result": asdict(result),
            },
        )
        return result

    def fracture_result_for(self, command_id: str) -> FractureResult | None:
        """Return the latest fracture result for a command."""
        result = self._fracture_results.get(command_id)
        if result is not None:
            return result
        for event in reversed(self.events_for(command_id)):
            raw_result = event.detail.get("fracture_result")
            if not isinstance(raw_result, dict):
                continue
            try:
                result = FractureResult(
                    command_id=str(raw_result["command_id"]),
                    passed=bool(raw_result["passed"]),
                    checks=tuple(raw_result["checks"]),
                    fractures=tuple(raw_result["fractures"]),
                    result_hash=str(raw_result["result_hash"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._fracture_results[command_id] = result
            return result
        return None

    def _build_evidence_records(self, command_id: str, *, verified: bool) -> list[EvidenceRecord]:
        """Build canonical evidence records from command witnesses."""
        command = self.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        refs: list[tuple[str, str]] = [
            ("payload_hash", command.payload_hash),
        ]
        action = self.governed_action_for(command_id)
        if action is not None:
            refs.extend([
                ("intent_hash", action.intent_hash),
                ("capability_passport_hash", action.capability_passport_hash),
            ])
            if action.predicted_effect_hash:
                refs.append(("predicted_effect_hash", action.predicted_effect_hash))
            if action.rollback_plan_hash:
                refs.append(("rollback_plan_hash", action.rollback_plan_hash))
        reconciliation = self.effect_reconciliation_for(command_id)
        if reconciliation is not None:
            refs.extend([
                ("observed_effect_hash", reconciliation.observed_effect_hash),
                ("effect_reconciliation", canonical_hash(asdict(reconciliation))),
            ])
        events = self.events_for(command_id)
        if events:
            refs.append(("latest_event_hash", events[-1].event_hash))

        records: list[EvidenceRecord] = []
        for evidence_type, ref in refs:
            evidence_hash = canonical_hash({
                "command_id": command_id,
                "evidence_type": evidence_type,
                "ref": ref,
            })
            records.append(EvidenceRecord(
                evidence_id=f"evidence-{evidence_hash[:16]}",
                command_id=command_id,
                evidence_type=evidence_type,
                ref=ref,
                ref_hash=evidence_hash,
                verified=verified,
            ))
        return records

    def transition(
        self,
        command_id: str,
        next_state: CommandState,
        *,
        risk_tier: str = "",
        budget_decision: str = "",
        approval_id: str = "",
        tool_name: str = "",
        output: dict[str, Any] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> CommandEnvelope:
        """Move a command to a new state and append a transition witness."""
        current = self._commands.get(command_id)
        if current is None:
            raise KeyError(f"unknown command_id: {command_id}")
        updated = CommandEnvelope(
            command_id=current.command_id,
            tenant_id=current.tenant_id,
            actor_id=current.actor_id,
            source=current.source,
            conversation_id=current.conversation_id,
            idempotency_key=current.idempotency_key,
            intent=current.intent,
            payload_hash=current.payload_hash,
            redacted_payload=current.redacted_payload,
            state=next_state,
            policy_version=current.policy_version,
            trace_id=current.trace_id,
            created_at=current.created_at,
        )
        self._commands[command_id] = updated
        self._store.save_command(updated)
        output_hash = canonical_hash(output) if output is not None else ""
        self._append_event(
            updated,
            previous_state=current.state,
            next_state=next_state,
            risk_tier=risk_tier,
            budget_decision=budget_decision,
            approval_id=approval_id,
            tool_name=tool_name,
            input_hash=current.payload_hash,
            output_hash=output_hash,
            detail=detail or {},
        )
        return updated

    def events_for(self, command_id: str) -> list[CommandEvent]:
        """Return transition witnesses for one command."""
        events = [event for event in self._events if event.command_id == command_id]
        if events:
            return events
        return self._store.events_for(command_id)

    def summary(self) -> dict[str, Any]:
        """Return ledger counters for health/status surfaces."""
        state_counts: dict[str, int] = {}
        for command in self._commands.values():
            state_counts[command.state.value] = state_counts.get(command.state.value, 0) + 1
        return {
            "commands": len(self._commands),
            "events": len(self._events),
            "governed_actions": len(self._governed_actions),
            "effect_predictions": len(self._effect_predictions),
            "recovery_plans": len(self._recovery_plans),
            "effect_observations": len(self._effect_observations),
            "effect_reconciliations": len(self._effect_reconciliations),
            "claims": sum(len(claims) for claims in self._claims.values()),
            "evidence_records": sum(len(records) for records in self._evidence_records.values()),
            "fracture_results": len(self._fracture_results),
            "states": state_counts,
            "last_event_hash": self._last_event_hash,
            "anchors": len(self._store.list_anchors(limit=10)),
            "store": self._store.status(),
        }

    def claim_ready_commands(
        self,
        *,
        worker_id: str,
        states: tuple[CommandState, ...] = (CommandState.ALLOWED, CommandState.APPROVED),
        lease_seconds: int = 300,
        limit: int = 10,
    ) -> list[CommandEnvelope]:
        """Lease ready commands for worker dispatch."""
        if not worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if limit < 1:
            return []
        leased_at = self._clock()
        lease_expires_at = self._lease_expiry(leased_at, lease_seconds)
        claimed = self._store.claim_ready_commands(
            worker_id=worker_id,
            states=states,
            leased_at=leased_at,
            lease_expires_at=lease_expires_at,
            limit=limit,
        )
        for command in claimed:
            self._commands[command.command_id] = command
        return claimed

    def release_command(self, command_id: str, worker_id: str) -> None:
        """Release a command lease held by a worker."""
        self._store.release_command(command_id, worker_id)

    def _lease_expiry(self, leased_at: str, lease_seconds: int) -> str:
        """Calculate lease expiry from an ISO timestamp."""
        try:
            parsed = datetime.fromisoformat(leased_at)
        except ValueError:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (parsed + timedelta(seconds=lease_seconds)).isoformat()

    def _append_event(
        self,
        command: CommandEnvelope,
        *,
        previous_state: CommandState,
        next_state: CommandState,
        risk_tier: str = "",
        budget_decision: str = "",
        approval_id: str = "",
        tool_name: str = "",
        input_hash: str = "",
        output_hash: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        timestamp = self._clock()
        event_seed = {
            "command_id": command.command_id,
            "previous_state": previous_state.value,
            "next_state": next_state.value,
            "policy_version": command.policy_version,
            "risk_tier": risk_tier,
            "budget_decision": budget_decision,
            "approval_id": approval_id,
            "tool_name": tool_name,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "trace_id": command.trace_id,
            "prev_event_hash": self._last_event_hash,
            "timestamp": timestamp,
            "detail": detail or {},
        }
        event_hash = canonical_hash(event_seed)
        event = CommandEvent(
            event_id=f"evt-{event_hash[:16]}",
            command_id=command.command_id,
            tenant_id=command.tenant_id,
            actor_id=command.actor_id,
            source_channel=command.source,
            idempotency_key=command.idempotency_key,
            previous_state=previous_state,
            next_state=next_state,
            policy_version=command.policy_version,
            risk_tier=risk_tier,
            budget_decision=budget_decision,
            approval_id=approval_id,
            tool_name=tool_name,
            input_hash=input_hash,
            output_hash=output_hash,
            trace_id=command.trace_id,
            prev_event_hash=self._last_event_hash,
            event_hash=event_hash,
            timestamp=timestamp,
            detail=detail or {},
        )
        self._events.append(event)
        self._store.append_event(event)
        self._last_event_hash = event_hash

    def anchor_unanchored_events(
        self,
        *,
        signing_secret: str,
        signature_key_id: str = "local",
    ) -> CommandAnchor | None:
        """Sign and persist an anchor for currently unanchored command events."""
        if not signing_secret:
            raise ValueError("signing_secret is required")
        events = self._store.unanchored_events()
        if not events:
            return None
        event_hashes = [event.event_hash for event in events]
        merkle_root = _compute_merkle_root(event_hashes)
        anchored_at = self._clock()
        unsigned_anchor = CommandAnchor(
            anchor_id=f"cmd-anchor-{merkle_root[:16]}",
            from_event_hash=event_hashes[0],
            to_event_hash=event_hashes[-1],
            event_count=len(event_hashes),
            merkle_root=merkle_root,
            signature="",
            signature_key_id=signature_key_id,
            anchored_at=anchored_at,
        )
        anchor = CommandAnchor(
            anchor_id=unsigned_anchor.anchor_id,
            from_event_hash=unsigned_anchor.from_event_hash,
            to_event_hash=unsigned_anchor.to_event_hash,
            event_count=unsigned_anchor.event_count,
            merkle_root=unsigned_anchor.merkle_root,
            signature=_anchor_signature(unsigned_anchor, signing_secret=signing_secret),
            signature_key_id=unsigned_anchor.signature_key_id,
            anchored_at=unsigned_anchor.anchored_at,
        )
        self._store.append_anchor(anchor)
        for event in events:
            command = self.get(event.command_id)
            if command is not None and command.state == CommandState.RESPONDED:
                self.transition(command.command_id, CommandState.ANCHORED, detail={"anchor_id": anchor.anchor_id})
        return anchor

    def list_anchors(self, limit: int = 50) -> list[CommandAnchor]:
        """Return recent signed command-event anchors."""
        return self._store.list_anchors(limit=limit)

    def export_anchor_proof(self, anchor_id: str) -> CommandAnchorProof | None:
        """Return exportable proof for one persisted anchor."""
        anchor = next((item for item in self._store.list_anchors(limit=10_000) if item.anchor_id == anchor_id), None)
        if anchor is None:
            return None
        event_hashes: list[str] = []
        recording = False
        for event in self._events:
            if event.event_hash == anchor.from_event_hash:
                recording = True
            if recording:
                event_hashes.append(event.event_hash)
            if event.event_hash == anchor.to_event_hash:
                break
        if not event_hashes:
            for command in self._commands:
                for event in self._store.events_for(command):
                    if event.event_hash == anchor.from_event_hash:
                        recording = True
                    if recording:
                        event_hashes.append(event.event_hash)
                    if event.event_hash == anchor.to_event_hash:
                        break
        exported_at = self._clock()
        proof_hash = canonical_hash({
            "anchor": asdict(anchor),
            "event_hashes": tuple(event_hashes),
            "exported_at": exported_at,
        })
        return CommandAnchorProof(
            anchor=anchor,
            event_hashes=tuple(event_hashes),
            proof_hash=proof_hash,
            exported_at=exported_at,
        )

    def verify_anchor_proof(
        self,
        proof: CommandAnchorProof,
        *,
        signing_secret: str,
    ) -> AnchorVerification:
        """Verify an exported command anchor proof."""
        if not signing_secret:
            return AnchorVerification(False, "signing_secret_required", proof.anchor.anchor_id)
        if proof.anchor.event_count != len(proof.event_hashes):
            return AnchorVerification(False, "event_count_mismatch", proof.anchor.anchor_id)
        if not proof.event_hashes:
            return AnchorVerification(False, "event_hashes_required", proof.anchor.anchor_id)
        if proof.anchor.from_event_hash != proof.event_hashes[0]:
            return AnchorVerification(False, "from_event_hash_mismatch", proof.anchor.anchor_id)
        if proof.anchor.to_event_hash != proof.event_hashes[-1]:
            return AnchorVerification(False, "to_event_hash_mismatch", proof.anchor.anchor_id)
        if proof.anchor.merkle_root != _compute_merkle_root(list(proof.event_hashes)):
            return AnchorVerification(False, "merkle_root_mismatch", proof.anchor.anchor_id)
        expected_signature = _anchor_signature(
            CommandAnchor(
                anchor_id=proof.anchor.anchor_id,
                from_event_hash=proof.anchor.from_event_hash,
                to_event_hash=proof.anchor.to_event_hash,
                event_count=proof.anchor.event_count,
                merkle_root=proof.anchor.merkle_root,
                signature="",
                signature_key_id=proof.anchor.signature_key_id,
                anchored_at=proof.anchor.anchored_at,
            ),
            signing_secret=signing_secret,
        )
        if not hmac.compare_digest(expected_signature, proof.anchor.signature):
            return AnchorVerification(False, "signature_mismatch", proof.anchor.anchor_id)
        expected_proof_hash = canonical_hash({
            "anchor": asdict(proof.anchor),
            "event_hashes": tuple(proof.event_hashes),
            "exported_at": proof.exported_at,
        })
        if not hmac.compare_digest(expected_proof_hash, proof.proof_hash):
            return AnchorVerification(False, "proof_hash_mismatch", proof.anchor.anchor_id)
        return AnchorVerification(True, "verified", proof.anchor.anchor_id)


def build_command_ledger_from_env(
    *,
    clock: Callable[[], str] | None = None,
    policy_version: str = "gateway-policy-v1",
) -> CommandLedger:
    """Create a command ledger using the gateway persistence environment."""
    import os

    backend = os.environ.get("MULLU_COMMAND_LEDGER_BACKEND", "")
    if not backend:
        backend = os.environ.get("MULLU_DB_BACKEND", "memory")
    backend = backend.strip().lower()
    if backend == "postgresql":
        connection_string = os.environ.get("MULLU_COMMAND_LEDGER_DB_URL", "")
        if not connection_string:
            connection_string = os.environ.get("MULLU_DB_URL", "")
        store: CommandLedgerStore = PostgresCommandLedgerStore(
            connection_string or "postgresql://localhost:5432/mullu"
        )
    elif backend == "memory":
        store = InMemoryCommandLedgerStore()
    else:
        raise ValueError("unsupported command ledger backend")
    return CommandLedger(clock=clock, policy_version=policy_version, store=store)
