"""Gateway Authority-Obligation Mesh - organizational responsibility governance.

Purpose: Binds commands, capabilities, approvals, closure certificates, and
    unresolved risk to accountable owners, approval chains, obligations, and
    escalation witnesses.
Governance scope: gateway organizational responsibility before dispatch and
    after terminal closure.
Dependencies: gateway command spine, notification engine contracts.
Invariants:
  - High-risk dispatch has an ownership binding before authority evaluation.
  - Approval chains are satisfied only by sufficient authorized approvers.
  - Separation of duty blocks requester self-approval when required.
  - Review, accepted-risk, and compensation closures create owned obligations.
  - Overdue obligations emit auditable escalation notifications.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Callable
from uuid import uuid4

from gateway.command_spine import (
    ClosureDisposition,
    CommandLedger,
    CommandState,
    TerminalClosureCertificate,
    canonical_hash,
)
from skills.enterprise.notifications import (
    NotificationEngine,
    NotificationPriority,
    NotificationType,
)

_log = logging.getLogger(__name__)


class ObligationStatus(StrEnum):
    """Lifecycle status for a required future governance action."""

    OPEN = "open"
    SATISFIED = "satisfied"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ApprovalChainStatus(StrEnum):
    """Lifecycle status for a multi-approver authority path."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    SATISFIED = "satisfied"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class TeamOwnership:
    """Accountable owner for one tenant resource reference."""

    tenant_id: str
    resource_ref: str
    owner_team: str
    primary_owner_id: str
    fallback_owner_id: str
    escalation_team: str


@dataclass(frozen=True, slots=True)
class EscalationPolicy:
    """Escalation target and timing contract for unresolved obligations."""

    policy_id: str
    tenant_id: str
    notify_after_seconds: int
    escalate_after_seconds: int
    incident_after_seconds: int
    fallback_owner_id: str
    escalation_team: str


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    """Authority path requirements for one capability and risk tier."""

    policy_id: str
    tenant_id: str
    capability: str
    risk_tier: str
    required_roles: tuple[str, ...]
    required_approver_count: int
    separation_of_duty: bool
    timeout_seconds: int
    escalation_policy_id: str


@dataclass(frozen=True, slots=True)
class ApprovalChain:
    """Concrete approval chain opened for one command."""

    chain_id: str
    command_id: str
    tenant_id: str
    policy_id: str
    required_roles: tuple[str, ...]
    required_approver_count: int
    approvals_received: tuple[str, ...]
    status: ApprovalChainStatus
    due_at: str


@dataclass(frozen=True, slots=True)
class Obligation:
    """Owned future action required by organizational governance."""

    obligation_id: str
    command_id: str
    tenant_id: str
    owner_id: str
    owner_team: str
    obligation_type: str
    due_at: str
    status: ObligationStatus
    evidence_required: tuple[str, ...]
    escalation_policy_id: str
    terminal_certificate_id: str = ""


@dataclass(frozen=True, slots=True)
class ResponsibilityWitness:
    """Runtime counts exposing unresolved organizational responsibility."""

    responsibility_debt_clear: bool
    pending_approval_chain_count: int
    overdue_approval_chain_count: int
    expired_approval_chain_count: int
    open_obligation_count: int
    overdue_obligation_count: int
    escalated_obligation_count: int
    active_accepted_risk_count: int
    active_compensation_review_count: int
    requires_review_count: int
    unowned_high_risk_capability_count: int


class AuthorityObligationMeshConfigurationError(ValueError):
    """Raised when mesh persistence violates deployment policy."""


class AuthorityObligationMeshStore:
    """Persistence contract for organizational responsibility records."""

    def save_ownership(self, ownership: TeamOwnership) -> None:
        """Persist an ownership binding."""
        raise NotImplementedError

    def load_ownership(self, tenant_id: str, resource_ref: str) -> TeamOwnership | None:
        """Load an ownership binding by tenant and resource."""
        raise NotImplementedError

    def list_ownership(self) -> tuple[TeamOwnership, ...]:
        """Return all ownership bindings."""
        raise NotImplementedError

    def save_approval_policy(self, policy: ApprovalPolicy) -> None:
        """Persist an approval policy."""
        raise NotImplementedError

    def load_approval_policy(self, tenant_id: str, capability: str, risk_tier: str) -> ApprovalPolicy | None:
        """Load an approval policy by tenant, capability, and risk tier."""
        raise NotImplementedError

    def list_approval_policies(self) -> tuple[ApprovalPolicy, ...]:
        """Return all approval policies."""
        raise NotImplementedError

    def save_escalation_policy(self, policy: EscalationPolicy) -> None:
        """Persist an escalation policy."""
        raise NotImplementedError

    def load_escalation_policy(self, tenant_id: str, policy_id: str) -> EscalationPolicy | None:
        """Load an escalation policy by tenant and policy ID."""
        raise NotImplementedError

    def list_escalation_policies(self) -> tuple[EscalationPolicy, ...]:
        """Return all escalation policies."""
        raise NotImplementedError

    def save_approval_chain(self, chain: ApprovalChain) -> None:
        """Persist an approval chain."""
        raise NotImplementedError

    def load_approval_chain(self, chain_id: str) -> ApprovalChain | None:
        """Load one approval chain by ID."""
        raise NotImplementedError

    def load_approval_chain_for_command(self, command_id: str) -> ApprovalChain | None:
        """Load the approval chain for one command."""
        raise NotImplementedError

    def list_approval_chains(self) -> tuple[ApprovalChain, ...]:
        """Return all approval chains."""
        raise NotImplementedError

    def save_obligation(self, obligation: Obligation) -> None:
        """Persist an obligation."""
        raise NotImplementedError

    def load_obligation(self, obligation_id: str) -> Obligation | None:
        """Load one obligation by ID."""
        raise NotImplementedError

    def list_obligations(self, command_id: str = "") -> tuple[Obligation, ...]:
        """Return obligations, optionally filtered by command."""
        raise NotImplementedError

    def append_escalation_event(self, event: dict[str, Any]) -> None:
        """Persist one escalation event."""
        raise NotImplementedError

    def list_escalation_events(self) -> tuple[dict[str, Any], ...]:
        """Return escalation events."""
        raise NotImplementedError

    def add_unowned_high_risk_capability(self, resource_ref: str) -> None:
        """Record a high-risk capability seen without explicit ownership."""
        raise NotImplementedError

    def list_unowned_high_risk_capabilities(self) -> tuple[str, ...]:
        """Return high-risk capability references seen without ownership."""
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        """Return store health details."""
        return {"backend": "unknown"}


class InMemoryAuthorityObligationMeshStore(AuthorityObligationMeshStore):
    """In-memory authority-obligation store for local runtime and tests."""

    def __init__(self) -> None:
        self._ownership: dict[tuple[str, str], TeamOwnership] = {}
        self._approval_policies: dict[tuple[str, str, str], ApprovalPolicy] = {}
        self._escalation_policies: dict[tuple[str, str], EscalationPolicy] = {}
        self._chains: dict[str, ApprovalChain] = {}
        self._command_chain: dict[str, str] = {}
        self._obligations: dict[str, Obligation] = {}
        self._command_obligations: dict[str, tuple[str, ...]] = {}
        self._escalation_events: list[dict[str, Any]] = []
        self._unowned_high_risk_capabilities: set[str] = set()

    def save_ownership(self, ownership: TeamOwnership) -> None:
        self._ownership[(ownership.tenant_id, ownership.resource_ref)] = ownership

    def load_ownership(self, tenant_id: str, resource_ref: str) -> TeamOwnership | None:
        return self._ownership.get((tenant_id, resource_ref))

    def list_ownership(self) -> tuple[TeamOwnership, ...]:
        return tuple(self._ownership.values())

    def save_approval_policy(self, policy: ApprovalPolicy) -> None:
        self._approval_policies[(policy.tenant_id, policy.capability, policy.risk_tier)] = policy

    def load_approval_policy(self, tenant_id: str, capability: str, risk_tier: str) -> ApprovalPolicy | None:
        return self._approval_policies.get((tenant_id, capability, risk_tier))

    def list_approval_policies(self) -> tuple[ApprovalPolicy, ...]:
        return tuple(self._approval_policies.values())

    def save_escalation_policy(self, policy: EscalationPolicy) -> None:
        self._escalation_policies[(policy.tenant_id, policy.policy_id)] = policy

    def load_escalation_policy(self, tenant_id: str, policy_id: str) -> EscalationPolicy | None:
        return self._escalation_policies.get((tenant_id, policy_id))

    def list_escalation_policies(self) -> tuple[EscalationPolicy, ...]:
        return tuple(self._escalation_policies.values())

    def save_approval_chain(self, chain: ApprovalChain) -> None:
        self._chains[chain.chain_id] = chain
        self._command_chain[chain.command_id] = chain.chain_id

    def load_approval_chain(self, chain_id: str) -> ApprovalChain | None:
        return self._chains.get(chain_id)

    def load_approval_chain_for_command(self, command_id: str) -> ApprovalChain | None:
        chain_id = self._command_chain.get(command_id)
        return self._chains.get(chain_id) if chain_id is not None else None

    def list_approval_chains(self) -> tuple[ApprovalChain, ...]:
        return tuple(self._chains.values())

    def save_obligation(self, obligation: Obligation) -> None:
        self._obligations[obligation.obligation_id] = obligation
        existing = self._command_obligations.get(obligation.command_id, ())
        if obligation.obligation_id not in existing:
            self._command_obligations[obligation.command_id] = tuple((*existing, obligation.obligation_id))

    def load_obligation(self, obligation_id: str) -> Obligation | None:
        return self._obligations.get(obligation_id)

    def list_obligations(self, command_id: str = "") -> tuple[Obligation, ...]:
        if not command_id:
            return tuple(self._obligations.values())
        return tuple(self._obligations[item] for item in self._command_obligations.get(command_id, ()))

    def append_escalation_event(self, event: dict[str, Any]) -> None:
        self._escalation_events.append(dict(event))

    def list_escalation_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(event) for event in self._escalation_events)

    def add_unowned_high_risk_capability(self, resource_ref: str) -> None:
        self._unowned_high_risk_capabilities.add(resource_ref)

    def list_unowned_high_risk_capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(self._unowned_high_risk_capabilities))

    def status(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "ownership_bindings": len(self._ownership),
            "approval_policies": len(self._approval_policies),
            "escalation_policies": len(self._escalation_policies),
            "approval_chains": len(self._chains),
            "obligations": len(self._obligations),
            "escalation_events": len(self._escalation_events),
            "unowned_high_risk_capabilities": len(self._unowned_high_risk_capabilities),
            "available": True,
        }


class PostgresAuthorityObligationMeshStore(AuthorityObligationMeshStore):
    """PostgreSQL authority-obligation mesh store for gateway deployments."""

    _MIGRATION = """
    CREATE TABLE IF NOT EXISTS gateway_team_ownership (
        tenant_id TEXT NOT NULL,
        resource_ref TEXT NOT NULL,
        owner_team TEXT NOT NULL,
        primary_owner_id TEXT NOT NULL,
        fallback_owner_id TEXT NOT NULL,
        escalation_team TEXT NOT NULL,
        PRIMARY KEY (tenant_id, resource_ref)
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_team_ownership_team
        ON gateway_team_ownership(owner_team);

    CREATE TABLE IF NOT EXISTS gateway_approval_policies (
        policy_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        capability TEXT NOT NULL,
        risk_tier TEXT NOT NULL,
        required_roles JSONB NOT NULL DEFAULT '[]',
        required_approver_count INTEGER NOT NULL,
        separation_of_duty BOOLEAN NOT NULL,
        timeout_seconds INTEGER NOT NULL,
        escalation_policy_id TEXT NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_gateway_approval_policy_key
        ON gateway_approval_policies(tenant_id, capability, risk_tier);

    CREATE TABLE IF NOT EXISTS gateway_escalation_policies (
        policy_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        notify_after_seconds INTEGER NOT NULL,
        escalate_after_seconds INTEGER NOT NULL,
        incident_after_seconds INTEGER NOT NULL,
        fallback_owner_id TEXT NOT NULL,
        escalation_team TEXT NOT NULL,
        PRIMARY KEY (tenant_id, policy_id)
    );

    CREATE TABLE IF NOT EXISTS gateway_approval_chains (
        chain_id TEXT PRIMARY KEY,
        command_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        policy_id TEXT NOT NULL,
        required_roles JSONB NOT NULL DEFAULT '[]',
        required_approver_count INTEGER NOT NULL,
        approvals_received JSONB NOT NULL DEFAULT '[]',
        status TEXT NOT NULL,
        due_at TEXT NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_gateway_approval_chain_command
        ON gateway_approval_chains(command_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_approval_chain_status
        ON gateway_approval_chains(status);

    CREATE TABLE IF NOT EXISTS gateway_obligations (
        obligation_id TEXT PRIMARY KEY,
        command_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        owner_team TEXT NOT NULL,
        obligation_type TEXT NOT NULL,
        due_at TEXT NOT NULL,
        status TEXT NOT NULL,
        evidence_required JSONB NOT NULL DEFAULT '[]',
        escalation_policy_id TEXT NOT NULL,
        terminal_certificate_id TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_obligations_command
        ON gateway_obligations(command_id);
    CREATE INDEX IF NOT EXISTS idx_gateway_obligations_status
        ON gateway_obligations(status);
    CREATE INDEX IF NOT EXISTS idx_gateway_obligations_due
        ON gateway_obligations(due_at);

    CREATE TABLE IF NOT EXISTS gateway_obligation_escalation_events (
        event_id TEXT PRIMARY KEY,
        obligation_id TEXT NOT NULL,
        command_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        owner_team TEXT NOT NULL,
        escalated_at TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_gateway_obligation_escalation_command
        ON gateway_obligation_escalation_events(command_id);

    CREATE TABLE IF NOT EXISTS gateway_unowned_high_risk_capabilities (
        resource_ref TEXT PRIMARY KEY
    );
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
        self._operation_failures = 0
        self._rollback_failures = 0
        self._close_failures = 0
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
                _log.warning("authority obligation mesh postgres bootstrap failed (%s)", type(exc).__name__)
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
            self._operation_failures += 1
            try:
                self._conn.rollback()
            except Exception as rollback_exc:
                self._rollback_failures += 1
                _log.warning(
                    "authority obligation mesh postgres rollback failed (%s)",
                    type(rollback_exc).__name__,
                )
            _log.warning("authority obligation mesh postgres operation failed (%s)", type(exc).__name__)
            return None

    def save_ownership(self, ownership: TeamOwnership) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_team_ownership "
                        "(tenant_id, resource_ref, owner_team, primary_owner_id, fallback_owner_id, escalation_team) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (tenant_id, resource_ref) DO UPDATE SET "
                        "owner_team = EXCLUDED.owner_team, "
                        "primary_owner_id = EXCLUDED.primary_owner_id, "
                        "fallback_owner_id = EXCLUDED.fallback_owner_id, "
                        "escalation_team = EXCLUDED.escalation_team",
                        (
                            ownership.tenant_id,
                            ownership.resource_ref,
                            ownership.owner_team,
                            ownership.primary_owner_id,
                            ownership.fallback_owner_id,
                            ownership.escalation_team,
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def load_ownership(self, tenant_id: str, resource_ref: str) -> TeamOwnership | None:
        def _read() -> TeamOwnership | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT tenant_id, resource_ref, owner_team, primary_owner_id, fallback_owner_id, "
                        "escalation_team FROM gateway_team_ownership "
                        "WHERE tenant_id = %s AND resource_ref = %s",
                        (tenant_id, resource_ref),
                    )
                    row = cur.fetchone()
            return self._row_to_ownership(row) if row is not None else None

        result = self._safe_execute(_read)
        return result if isinstance(result, TeamOwnership) else None

    def list_ownership(self) -> tuple[TeamOwnership, ...]:
        def _read() -> tuple[TeamOwnership, ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT tenant_id, resource_ref, owner_team, primary_owner_id, fallback_owner_id, "
                        "escalation_team FROM gateway_team_ownership ORDER BY tenant_id, resource_ref"
                    )
                    rows = cur.fetchall()
            return tuple(self._row_to_ownership(row) for row in rows)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def save_approval_policy(self, policy: ApprovalPolicy) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_approval_policies "
                        "(policy_id, tenant_id, capability, risk_tier, required_roles, required_approver_count, "
                        "separation_of_duty, timeout_seconds, escalation_policy_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (policy_id) DO UPDATE SET "
                        "tenant_id = EXCLUDED.tenant_id, "
                        "capability = EXCLUDED.capability, "
                        "risk_tier = EXCLUDED.risk_tier, "
                        "required_roles = EXCLUDED.required_roles, "
                        "required_approver_count = EXCLUDED.required_approver_count, "
                        "separation_of_duty = EXCLUDED.separation_of_duty, "
                        "timeout_seconds = EXCLUDED.timeout_seconds, "
                        "escalation_policy_id = EXCLUDED.escalation_policy_id",
                        (
                            policy.policy_id,
                            policy.tenant_id,
                            policy.capability,
                            policy.risk_tier,
                            json.dumps(policy.required_roles, sort_keys=True, default=str),
                            policy.required_approver_count,
                            policy.separation_of_duty,
                            policy.timeout_seconds,
                            policy.escalation_policy_id,
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def load_approval_policy(self, tenant_id: str, capability: str, risk_tier: str) -> ApprovalPolicy | None:
        def _read() -> ApprovalPolicy | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT policy_id, tenant_id, capability, risk_tier, required_roles, "
                        "required_approver_count, separation_of_duty, timeout_seconds, escalation_policy_id "
                        "FROM gateway_approval_policies "
                        "WHERE tenant_id = %s AND capability = %s AND risk_tier = %s",
                        (tenant_id, capability, risk_tier),
                    )
                    row = cur.fetchone()
            return self._row_to_approval_policy(row) if row is not None else None

        result = self._safe_execute(_read)
        return result if isinstance(result, ApprovalPolicy) else None

    def list_approval_policies(self) -> tuple[ApprovalPolicy, ...]:
        def _read() -> tuple[ApprovalPolicy, ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT policy_id, tenant_id, capability, risk_tier, required_roles, "
                        "required_approver_count, separation_of_duty, timeout_seconds, escalation_policy_id "
                        "FROM gateway_approval_policies ORDER BY tenant_id, capability, risk_tier"
                    )
                    rows = cur.fetchall()
            return tuple(self._row_to_approval_policy(row) for row in rows)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def save_escalation_policy(self, policy: EscalationPolicy) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_escalation_policies "
                        "(policy_id, tenant_id, notify_after_seconds, escalate_after_seconds, "
                        "incident_after_seconds, fallback_owner_id, escalation_team) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (tenant_id, policy_id) DO UPDATE SET "
                        "notify_after_seconds = EXCLUDED.notify_after_seconds, "
                        "escalate_after_seconds = EXCLUDED.escalate_after_seconds, "
                        "incident_after_seconds = EXCLUDED.incident_after_seconds, "
                        "fallback_owner_id = EXCLUDED.fallback_owner_id, "
                        "escalation_team = EXCLUDED.escalation_team",
                        (
                            policy.policy_id,
                            policy.tenant_id,
                            policy.notify_after_seconds,
                            policy.escalate_after_seconds,
                            policy.incident_after_seconds,
                            policy.fallback_owner_id,
                            policy.escalation_team,
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def load_escalation_policy(self, tenant_id: str, policy_id: str) -> EscalationPolicy | None:
        def _read() -> EscalationPolicy | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT policy_id, tenant_id, notify_after_seconds, escalate_after_seconds, "
                        "incident_after_seconds, fallback_owner_id, escalation_team "
                        "FROM gateway_escalation_policies WHERE tenant_id = %s AND policy_id = %s",
                        (tenant_id, policy_id),
                    )
                    row = cur.fetchone()
            return self._row_to_escalation_policy(row) if row is not None else None

        result = self._safe_execute(_read)
        return result if isinstance(result, EscalationPolicy) else None

    def list_escalation_policies(self) -> tuple[EscalationPolicy, ...]:
        def _read() -> tuple[EscalationPolicy, ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT policy_id, tenant_id, notify_after_seconds, escalate_after_seconds, "
                        "incident_after_seconds, fallback_owner_id, escalation_team "
                        "FROM gateway_escalation_policies ORDER BY tenant_id, policy_id"
                    )
                    rows = cur.fetchall()
            return tuple(self._row_to_escalation_policy(row) for row in rows)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def save_approval_chain(self, chain: ApprovalChain) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_approval_chains "
                        "(chain_id, command_id, tenant_id, policy_id, required_roles, required_approver_count, "
                        "approvals_received, status, due_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (chain_id) DO UPDATE SET "
                        "command_id = EXCLUDED.command_id, "
                        "tenant_id = EXCLUDED.tenant_id, "
                        "policy_id = EXCLUDED.policy_id, "
                        "required_roles = EXCLUDED.required_roles, "
                        "required_approver_count = EXCLUDED.required_approver_count, "
                        "approvals_received = EXCLUDED.approvals_received, "
                        "status = EXCLUDED.status, "
                        "due_at = EXCLUDED.due_at",
                        (
                            chain.chain_id,
                            chain.command_id,
                            chain.tenant_id,
                            chain.policy_id,
                            json.dumps(chain.required_roles, sort_keys=True, default=str),
                            chain.required_approver_count,
                            json.dumps(chain.approvals_received, sort_keys=True, default=str),
                            chain.status.value,
                            chain.due_at,
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def load_approval_chain(self, chain_id: str) -> ApprovalChain | None:
        def _read() -> ApprovalChain | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT chain_id, command_id, tenant_id, policy_id, required_roles, "
                        "required_approver_count, approvals_received, status, due_at "
                        "FROM gateway_approval_chains WHERE chain_id = %s",
                        (chain_id,),
                    )
                    row = cur.fetchone()
            return self._row_to_approval_chain(row) if row is not None else None

        result = self._safe_execute(_read)
        return result if isinstance(result, ApprovalChain) else None

    def load_approval_chain_for_command(self, command_id: str) -> ApprovalChain | None:
        def _read() -> ApprovalChain | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT chain_id, command_id, tenant_id, policy_id, required_roles, "
                        "required_approver_count, approvals_received, status, due_at "
                        "FROM gateway_approval_chains WHERE command_id = %s",
                        (command_id,),
                    )
                    row = cur.fetchone()
            return self._row_to_approval_chain(row) if row is not None else None

        result = self._safe_execute(_read)
        return result if isinstance(result, ApprovalChain) else None

    def list_approval_chains(self) -> tuple[ApprovalChain, ...]:
        def _read() -> tuple[ApprovalChain, ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT chain_id, command_id, tenant_id, policy_id, required_roles, "
                        "required_approver_count, approvals_received, status, due_at "
                        "FROM gateway_approval_chains ORDER BY tenant_id, command_id"
                    )
                    rows = cur.fetchall()
            return tuple(self._row_to_approval_chain(row) for row in rows)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def save_obligation(self, obligation: Obligation) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_obligations "
                        "(obligation_id, command_id, tenant_id, owner_id, owner_team, obligation_type, due_at, "
                        "status, evidence_required, escalation_policy_id, terminal_certificate_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (obligation_id) DO UPDATE SET "
                        "command_id = EXCLUDED.command_id, "
                        "tenant_id = EXCLUDED.tenant_id, "
                        "owner_id = EXCLUDED.owner_id, "
                        "owner_team = EXCLUDED.owner_team, "
                        "obligation_type = EXCLUDED.obligation_type, "
                        "due_at = EXCLUDED.due_at, "
                        "status = EXCLUDED.status, "
                        "evidence_required = EXCLUDED.evidence_required, "
                        "escalation_policy_id = EXCLUDED.escalation_policy_id, "
                        "terminal_certificate_id = EXCLUDED.terminal_certificate_id",
                        (
                            obligation.obligation_id,
                            obligation.command_id,
                            obligation.tenant_id,
                            obligation.owner_id,
                            obligation.owner_team,
                            obligation.obligation_type,
                            obligation.due_at,
                            obligation.status.value,
                            json.dumps(obligation.evidence_required, sort_keys=True, default=str),
                            obligation.escalation_policy_id,
                            obligation.terminal_certificate_id,
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def load_obligation(self, obligation_id: str) -> Obligation | None:
        def _read() -> Obligation | None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT obligation_id, command_id, tenant_id, owner_id, owner_team, obligation_type, "
                        "due_at, status, evidence_required, escalation_policy_id, terminal_certificate_id "
                        "FROM gateway_obligations WHERE obligation_id = %s",
                        (obligation_id,),
                    )
                    row = cur.fetchone()
            return self._row_to_obligation(row) if row is not None else None

        result = self._safe_execute(_read)
        return result if isinstance(result, Obligation) else None

    def list_obligations(self, command_id: str = "") -> tuple[Obligation, ...]:
        def _read() -> tuple[Obligation, ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    if command_id:
                        cur.execute(
                            "SELECT obligation_id, command_id, tenant_id, owner_id, owner_team, obligation_type, "
                            "due_at, status, evidence_required, escalation_policy_id, terminal_certificate_id "
                            "FROM gateway_obligations WHERE command_id = %s ORDER BY due_at, obligation_id",
                            (command_id,),
                        )
                    else:
                        cur.execute(
                            "SELECT obligation_id, command_id, tenant_id, owner_id, owner_team, obligation_type, "
                            "due_at, status, evidence_required, escalation_policy_id, terminal_certificate_id "
                            "FROM gateway_obligations ORDER BY tenant_id, due_at, obligation_id"
                        )
                    rows = cur.fetchall()
            return tuple(self._row_to_obligation(row) for row in rows)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def append_escalation_event(self, event: dict[str, Any]) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_obligation_escalation_events "
                        "(event_id, obligation_id, command_id, tenant_id, owner_id, owner_team, escalated_at, metadata) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (event_id) DO NOTHING",
                        (
                            str(event["event_id"]),
                            str(event["obligation_id"]),
                            str(event["command_id"]),
                            str(event["tenant_id"]),
                            str(event["owner_id"]),
                            str(event["owner_team"]),
                            str(event["escalated_at"]),
                            json.dumps(event, sort_keys=True, default=str),
                        ),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def list_escalation_events(self) -> tuple[dict[str, Any], ...]:
        def _read() -> tuple[dict[str, Any], ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT metadata FROM gateway_obligation_escalation_events "
                        "ORDER BY escalated_at, event_id"
                    )
                    rows = cur.fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                metadata = row[0]
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                events.append(dict(metadata))
            return tuple(events)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def add_unowned_high_risk_capability(self, resource_ref: str) -> None:
        def _write() -> None:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gateway_unowned_high_risk_capabilities (resource_ref) "
                        "VALUES (%s) ON CONFLICT (resource_ref) DO NOTHING",
                        (resource_ref,),
                    )
                    self._conn.commit()

        self._safe_execute(_write)

    def list_unowned_high_risk_capabilities(self) -> tuple[str, ...]:
        def _read() -> tuple[str, ...]:
            with self._lock:
                with self._conn.cursor() as cur:
                    cur.execute(
                        "SELECT resource_ref FROM gateway_unowned_high_risk_capabilities ORDER BY resource_ref"
                    )
                    rows = cur.fetchall()
            return tuple(str(row[0]) for row in rows)

        result = self._safe_execute(_read)
        return result if isinstance(result, tuple) else ()

    def status(self) -> dict[str, Any]:
        return {
            "backend": "postgresql",
            "persistent": True,
            "available": self._conn is not None,
            "driver_available": self._available,
            "operation_failures": self._operation_failures,
            "rollback_failures": self._rollback_failures,
            "close_failures": self._close_failures,
        }

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as exc:
                self._close_failures += 1
                _log.warning("authority obligation mesh postgres close failed (%s)", type(exc).__name__)
            self._conn = None

    def _row_to_ownership(self, row: Any) -> TeamOwnership:
        return TeamOwnership(
            tenant_id=row[0],
            resource_ref=row[1],
            owner_team=row[2],
            primary_owner_id=row[3],
            fallback_owner_id=row[4],
            escalation_team=row[5],
        )

    def _row_to_approval_policy(self, row: Any) -> ApprovalPolicy:
        required_roles = self._json_tuple(row[4])
        return ApprovalPolicy(
            policy_id=row[0],
            tenant_id=row[1],
            capability=row[2],
            risk_tier=row[3],
            required_roles=required_roles,
            required_approver_count=int(row[5]),
            separation_of_duty=bool(row[6]),
            timeout_seconds=int(row[7]),
            escalation_policy_id=row[8],
        )

    def _row_to_escalation_policy(self, row: Any) -> EscalationPolicy:
        return EscalationPolicy(
            policy_id=row[0],
            tenant_id=row[1],
            notify_after_seconds=int(row[2]),
            escalate_after_seconds=int(row[3]),
            incident_after_seconds=int(row[4]),
            fallback_owner_id=row[5],
            escalation_team=row[6],
        )

    def _row_to_approval_chain(self, row: Any) -> ApprovalChain:
        return ApprovalChain(
            chain_id=row[0],
            command_id=row[1],
            tenant_id=row[2],
            policy_id=row[3],
            required_roles=self._json_tuple(row[4]),
            required_approver_count=int(row[5]),
            approvals_received=self._json_tuple(row[6]),
            status=ApprovalChainStatus(row[7]),
            due_at=row[8],
        )

    def _row_to_obligation(self, row: Any) -> Obligation:
        return Obligation(
            obligation_id=row[0],
            command_id=row[1],
            tenant_id=row[2],
            owner_id=row[3],
            owner_team=row[4],
            obligation_type=row[5],
            due_at=row[6],
            status=ObligationStatus(row[7]),
            evidence_required=self._json_tuple(row[8]),
            escalation_policy_id=row[9],
            terminal_certificate_id=row[10],
        )

    def _json_tuple(self, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            value = json.loads(value)
        return tuple(str(item) for item in value)


class AuthorityObligationMesh:
    """Organizational responsibility mesh for gateway commands."""

    def __init__(
        self,
        *,
        commands: CommandLedger,
        notification_engine: NotificationEngine | None = None,
        clock: Callable[[], str] | None = None,
        store: AuthorityObligationMeshStore | None = None,
        strict_high_risk_ownership: bool = False,
    ) -> None:
        self._commands = commands
        self._notifications = notification_engine or NotificationEngine(clock=clock)
        self._clock = clock or commands._clock
        self._store = store or InMemoryAuthorityObligationMeshStore()
        self._strict_high_risk_ownership = strict_high_risk_ownership

    def register_ownership(self, ownership: TeamOwnership) -> None:
        """Register the accountable owner for one resource reference."""
        if not ownership.owner_team or not ownership.primary_owner_id:
            raise ValueError("ownership requires owner_team and primary_owner_id")
        self._store.save_ownership(ownership)

    def register_approval_policy(self, policy: ApprovalPolicy) -> None:
        """Register the approval policy for one tenant capability risk tier."""
        if policy.required_approver_count < 0:
            raise ValueError("required_approver_count must be non-negative")
        if policy.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._store.save_approval_policy(policy)

    def register_escalation_policy(self, policy: EscalationPolicy) -> None:
        """Register the escalation policy for one tenant responsibility path."""
        if min(policy.notify_after_seconds, policy.escalate_after_seconds, policy.incident_after_seconds) < 0:
            raise ValueError("escalation timings must be non-negative")
        if not policy.fallback_owner_id or not policy.escalation_team:
            raise ValueError("escalation policy requires fallback owner and escalation team")
        self._store.save_escalation_policy(policy)

    def prepare_authority(self, command_id: str) -> ApprovalChain:
        """Bind ownership and build the authority path before dispatch."""
        command = self._commands.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        action = self._commands.governed_action_for(command_id)
        if action is None:
            raise KeyError(f"missing governed action for command_id: {command_id}")

        ownership = self._resolve_ownership(
            tenant_id=command.tenant_id,
            resource_ref=action.capability,
            requester_id=command.actor_id,
            risk_tier=action.risk_tier,
        )
        self._commands.transition(
            command_id,
            CommandState.OWNERSHIP_BOUND,
            risk_tier=action.risk_tier,
            detail={"cause": "authority_obligation_ownership_bound", "ownership": asdict(ownership)},
        )

        policy = self._resolve_approval_policy(
            tenant_id=command.tenant_id,
            capability=action.capability,
            risk_tier=action.risk_tier,
            required_roles=action.authority_required,
        )
        chain = self._create_chain(command_id=command_id, policy=policy)
        self._commands.transition(
            command_id,
            CommandState.AUTHORITY_PATH_BUILT,
            risk_tier=action.risk_tier,
            detail={
                "cause": "authority_path_built",
                "approval_policy": asdict(policy),
                "approval_chain": asdict(chain),
            },
        )
        next_state = (
            CommandState.APPROVAL_CHAIN_PENDING
            if chain.status is ApprovalChainStatus.PENDING
            else CommandState.APPROVAL_CHAIN_SATISFIED
        )
        self._commands.transition(
            command_id,
            next_state,
            risk_tier=action.risk_tier,
            detail={"cause": "approval_chain_initialized", "approval_chain": asdict(chain)},
        )
        if chain.status is ApprovalChainStatus.PENDING:
            self._notify_approval_needed(command.tenant_id, chain, ownership)
        return chain

    def record_approval(
        self,
        *,
        command_id: str,
        approver_id: str,
        approver_roles: tuple[str, ...],
        approved: bool,
    ) -> ApprovalChain | None:
        """Record one resolver decision against the command approval chain."""
        chain = self._store.load_approval_chain_for_command(command_id)
        if chain is None:
            return None
        if chain.status not in {ApprovalChainStatus.PENDING, ApprovalChainStatus.SATISFIED}:
            return chain
        if not approved:
            updated = self._replace_chain(chain, status=ApprovalChainStatus.DENIED)
            self._transition_chain(command_id, updated)
            return updated
        command = self._commands.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        policy = self._policy_for_chain(chain)
        if policy.separation_of_duty and approver_id == command.actor_id:
            updated = self._replace_chain(chain, status=ApprovalChainStatus.PENDING)
            self._transition_chain(
                command_id,
                updated,
                detail={"rejected_approver": approver_id, "reason": "separation_of_duty"},
            )
            return updated
        missing_roles = tuple(role for role in chain.required_roles if role not in approver_roles)
        if missing_roles:
            updated = self._replace_chain(chain, status=ApprovalChainStatus.PENDING)
            self._transition_chain(
                command_id,
                updated,
                detail={"rejected_approver": approver_id, "missing_roles": missing_roles},
            )
            return updated
        approvals = tuple(dict.fromkeys((*chain.approvals_received, approver_id)))
        status = (
            ApprovalChainStatus.SATISFIED
            if len(approvals) >= chain.required_approver_count
            else ApprovalChainStatus.PENDING
        )
        updated = self._replace_chain(chain, approvals_received=approvals, status=status)
        self._transition_chain(command_id, updated)
        return updated

    def open_post_closure_obligations(
        self,
        *,
        command_id: str,
        certificate: TerminalClosureCertificate,
    ) -> tuple[Obligation, ...]:
        """Open obligations required by the terminal closure disposition."""
        command = self._commands.get(command_id)
        if command is None:
            raise KeyError(f"unknown command_id: {command_id}")
        action = self._commands.governed_action_for(command_id)
        resource_ref = action.capability if action is not None else command.intent
        obligations: tuple[Obligation, ...]
        if certificate.disposition is ClosureDisposition.ACCEPTED_RISK:
            ownership = self._store.load_ownership(command.tenant_id, resource_ref)
            if ownership is None:
                raise ValueError("accepted-risk closure requires explicit ownership binding")
            if not certificate.accepted_risk_id or not certificate.case_id:
                raise ValueError("accepted-risk closure requires accepted_risk_id and case_id")
            due_at = str(certificate.metadata.get("risk_expires_at", ""))
            if not due_at:
                raise ValueError("accepted-risk closure requires risk_expires_at")
            if self._parse_time(due_at) <= self._parse_time(self._clock()):
                raise ValueError("accepted-risk closure requires future risk_expires_at")
            obligations = (self._open_obligation(
                command_id=command_id,
                tenant_id=command.tenant_id,
                owner=ownership,
                obligation_type="accepted_risk_review",
                due_at=due_at,
                evidence_required=("review_decision", "risk_owner_attestation"),
                escalation_policy_id=self._escalation_policy_id_for(command.tenant_id, command_id),
                terminal_certificate_id=certificate.certificate_id,
            ),)
        elif certificate.disposition is ClosureDisposition.REQUIRES_REVIEW:
            ownership = self._resolve_ownership(
                tenant_id=command.tenant_id,
                resource_ref=resource_ref,
                requester_id=command.actor_id,
                risk_tier=action.risk_tier if action is not None else "medium",
            )
            obligations = (self._open_obligation(
                command_id=command_id,
                tenant_id=command.tenant_id,
                owner=ownership,
                obligation_type="case_review",
                due_at=self._future_iso(hours=24),
                evidence_required=("case_disposition",),
                escalation_policy_id=self._escalation_policy_id_for(command.tenant_id, command_id),
                terminal_certificate_id=certificate.certificate_id,
            ),)
        elif certificate.disposition is ClosureDisposition.COMPENSATED:
            ownership = self._store.load_ownership(command.tenant_id, resource_ref)
            if ownership is None:
                raise ValueError("compensated closure requires explicit ownership binding")
            if not certificate.compensation_outcome_id:
                raise ValueError("compensated closure requires compensation_outcome_id")
            if not str(certificate.metadata.get("compensation_reviewer_id", "")):
                raise ValueError("compensated closure requires compensation_reviewer_id")
            obligations = (self._open_obligation(
                command_id=command_id,
                tenant_id=command.tenant_id,
                owner=ownership,
                obligation_type="compensation_review",
                due_at=self._future_iso(hours=24),
                evidence_required=("compensation_receipt", "compensation_reviewer_attestation"),
                escalation_policy_id=self._escalation_policy_id_for(command.tenant_id, command_id),
                terminal_certificate_id=certificate.certificate_id,
            ),)
        else:
            obligations = ()

        self._commands.transition(
            command_id,
            CommandState.OBLIGATIONS_OPENED if obligations else CommandState.OBLIGATIONS_SATISFIED,
            detail={
                "cause": "post_closure_obligations_bound",
                "terminal_certificate_id": certificate.certificate_id,
                "obligations": [asdict(obligation) for obligation in obligations],
            },
        )
        return obligations

    def satisfy_obligation(self, obligation_id: str, *, evidence_refs: tuple[str, ...]) -> Obligation:
        """Mark an obligation satisfied when required evidence is present."""
        obligation = self._store.load_obligation(obligation_id)
        if obligation is None:
            raise KeyError(f"unknown obligation_id: {obligation_id}")
        if obligation.status not in {ObligationStatus.OPEN, ObligationStatus.ESCALATED}:
            raise ValueError("obligation must be open or escalated before satisfaction")
        if obligation.evidence_required and not evidence_refs:
            raise ValueError("obligation satisfaction requires evidence_refs")
        missing_evidence = self._missing_obligation_evidence(obligation, evidence_refs)
        if missing_evidence:
            raise ValueError(f"obligation satisfaction missing required evidence: {', '.join(missing_evidence)}")
        updated = self._replace_obligation(obligation, status=ObligationStatus.SATISFIED)
        self._commands.transition(
            updated.command_id,
            CommandState.OBLIGATIONS_SATISFIED,
            detail={
                "cause": "obligation_satisfied",
                "obligation": asdict(updated),
                "evidence_refs": evidence_refs,
            },
        )
        return updated

    def escalate_overdue(self) -> tuple[Obligation, ...]:
        """Escalate every overdue open obligation and notify its escalation route."""
        now = self._parse_time(self._clock())
        escalated: list[Obligation] = []
        for obligation in self._store.list_obligations():
            if obligation.status is not ObligationStatus.OPEN:
                continue
            due_at = self._parse_time(obligation.due_at)
            if due_at > now:
                continue
            updated = self._replace_obligation(obligation, status=ObligationStatus.ESCALATED)
            route = self._escalation_route(updated)
            event = {
                "event_id": f"obl-escalation-{uuid4().hex[:16]}",
                "obligation_id": updated.obligation_id,
                "command_id": updated.command_id,
                "tenant_id": updated.tenant_id,
                "owner_id": updated.owner_id,
                "owner_team": updated.owner_team,
                "escalation_policy_id": updated.escalation_policy_id,
                "fallback_owner_id": route["fallback_owner_id"],
                "escalation_team": route["escalation_team"],
                "escalated_at": self._clock(),
            }
            self._store.append_escalation_event(event)
            self._notifications.notify(
                tenant_id=updated.tenant_id,
                notification_type=NotificationType.CUSTOM,
                priority=NotificationPriority.CRITICAL,
                title="Obligation overdue",
                body=f"Obligation {updated.obligation_id} is overdue for command {updated.command_id}.",
                metadata=event,
            )
            self._commands.transition(
                updated.command_id,
                CommandState.OBLIGATIONS_ESCALATED,
                detail={"cause": "obligation_overdue_escalated", "escalation_event": event},
            )
            escalated.append(updated)
        return tuple(escalated)

    def expire_overdue_approval_chains(self) -> tuple[ApprovalChain, ...]:
        """Expire every overdue pending approval chain and emit an escalation witness."""
        now = self._parse_time(self._clock())
        expired: list[ApprovalChain] = []
        for chain in self._store.list_approval_chains():
            if chain.status is not ApprovalChainStatus.PENDING:
                continue
            due_at = self._parse_time(chain.due_at)
            if due_at > now:
                continue
            updated = self._replace_chain(chain, status=ApprovalChainStatus.EXPIRED)
            event = {
                "event_id": f"approval-chain-expired-{uuid4().hex[:16]}",
                "event_type": "approval_chain_expired",
                "obligation_id": "",
                "approval_chain_id": updated.chain_id,
                "command_id": updated.command_id,
                "tenant_id": updated.tenant_id,
                "owner_id": "",
                "owner_team": "",
                "escalated_at": self._clock(),
            }
            self._store.append_escalation_event(event)
            self._notifications.notify(
                tenant_id=updated.tenant_id,
                notification_type=NotificationType.APPROVAL_NEEDED,
                priority=NotificationPriority.CRITICAL,
                title="Approval chain expired",
                body=f"Approval chain {updated.chain_id} expired for command {updated.command_id}.",
                metadata=event,
            )
            self._commands.transition(
                updated.command_id,
                CommandState.DENIED,
                approval_id=updated.chain_id,
                detail={"cause": "approval_chain_expired_escalated", "escalation_event": event},
            )
            expired.append(updated)
        return tuple(expired)

    def obligations_for(self, command_id: str) -> tuple[Obligation, ...]:
        """Return obligations opened for one command."""
        return self._store.list_obligations(command_id)

    def approval_chain_for(self, command_id: str) -> ApprovalChain | None:
        """Return the approval chain opened for one command."""
        return self._store.load_approval_chain_for_command(command_id)

    def escalation_events(self) -> tuple[dict[str, Any], ...]:
        """Return auditable obligation escalation events."""
        return self._store.list_escalation_events()

    def responsibility_witness(self) -> ResponsibilityWitness:
        """Return runtime counts for unresolved organizational responsibility."""
        now = self._parse_time(self._clock())
        open_obligations = [
            obligation for obligation in self._store.list_obligations()
            if obligation.status is ObligationStatus.OPEN
        ]
        obligations = self._store.list_obligations()
        chains = self._store.list_approval_chains()
        pending_approval_chain_count = sum(
            1 for chain in chains if chain.status is ApprovalChainStatus.PENDING
        )
        overdue_approval_chain_count = sum(
            1 for chain in chains
            if chain.status is ApprovalChainStatus.PENDING
            and self._parse_time(chain.due_at) <= now
        )
        expired_approval_chain_count = sum(
            1 for chain in chains if chain.status is ApprovalChainStatus.EXPIRED
        )
        open_obligation_count = len(open_obligations)
        overdue_obligation_count = sum(
            1 for obligation in open_obligations if self._parse_time(obligation.due_at) <= now
        )
        escalated_obligation_count = sum(
            1 for obligation in obligations if obligation.status is ObligationStatus.ESCALATED
        )
        unowned_high_risk_capability_count = len(self._store.list_unowned_high_risk_capabilities())
        responsibility_debt_clear = (
            overdue_approval_chain_count == 0
            and expired_approval_chain_count == 0
            and overdue_obligation_count == 0
            and escalated_obligation_count == 0
            and unowned_high_risk_capability_count == 0
        )
        return ResponsibilityWitness(
            responsibility_debt_clear=responsibility_debt_clear,
            pending_approval_chain_count=pending_approval_chain_count,
            overdue_approval_chain_count=overdue_approval_chain_count,
            expired_approval_chain_count=expired_approval_chain_count,
            open_obligation_count=open_obligation_count,
            overdue_obligation_count=overdue_obligation_count,
            escalated_obligation_count=escalated_obligation_count,
            active_accepted_risk_count=sum(
                1 for obligation in obligations
                if obligation.obligation_type == "accepted_risk_review"
                and obligation.status in {ObligationStatus.OPEN, ObligationStatus.ESCALATED}
            ),
            active_compensation_review_count=sum(
                1 for obligation in obligations
                if obligation.obligation_type == "compensation_review"
                and obligation.status in {ObligationStatus.OPEN, ObligationStatus.ESCALATED}
            ),
            requires_review_count=sum(
                1 for obligation in obligations
                if obligation.obligation_type == "case_review"
                and obligation.status in {ObligationStatus.OPEN, ObligationStatus.ESCALATED}
            ),
            unowned_high_risk_capability_count=unowned_high_risk_capability_count,
        )

    def summary(self) -> dict[str, Any]:
        """Return mesh counters for status surfaces."""
        witness = self.responsibility_witness()
        return {
            **asdict(witness),
            "ownership_bindings": len(self._store.list_ownership()),
            "approval_policies": len(self._store.list_approval_policies()),
            "escalation_policies": len(self._store.list_escalation_policies()),
            "approval_chains": len(self._store.list_approval_chains()),
            "obligations": len(self._store.list_obligations()),
            "escalation_events": len(self._store.list_escalation_events()),
            "store": self._store.status(),
        }

    def _resolve_ownership(
        self,
        *,
        tenant_id: str,
        resource_ref: str,
        requester_id: str,
        risk_tier: str,
    ) -> TeamOwnership:
        ownership = self._store.load_ownership(tenant_id, resource_ref)
        if ownership is not None:
            return ownership
        if risk_tier == "high":
            self._store.add_unowned_high_risk_capability(resource_ref)
        if risk_tier == "high" and self._strict_high_risk_ownership:
            raise ValueError("high-risk capability requires ownership binding")
        return TeamOwnership(
            tenant_id=tenant_id,
            resource_ref=resource_ref,
            owner_team="tenant_operations",
            primary_owner_id=requester_id,
            fallback_owner_id=requester_id,
            escalation_team="tenant_operations",
        )

    def _resolve_approval_policy(
        self,
        *,
        tenant_id: str,
        capability: str,
        risk_tier: str,
        required_roles: tuple[str, ...],
    ) -> ApprovalPolicy:
        policy = self._store.load_approval_policy(tenant_id, capability, risk_tier)
        if policy is not None:
            return policy
        policy_id = f"approval-policy-{canonical_hash({
            'tenant_id': tenant_id,
            'capability': capability,
            'risk_tier': risk_tier,
            'required_roles': required_roles,
        })[:12]}"
        return ApprovalPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            capability=capability,
            risk_tier=risk_tier,
            required_roles=required_roles,
            required_approver_count=0 if risk_tier == "low" else 1,
            separation_of_duty=risk_tier == "high",
            timeout_seconds=300,
            escalation_policy_id="default",
        )

    def _create_chain(self, *, command_id: str, policy: ApprovalPolicy) -> ApprovalChain:
        due_at = self._future_iso(seconds=policy.timeout_seconds)
        chain_hash = canonical_hash({"command_id": command_id, "policy_id": policy.policy_id, "due_at": due_at})
        status = (
            ApprovalChainStatus.NOT_REQUIRED
            if policy.required_approver_count == 0
            else ApprovalChainStatus.PENDING
        )
        chain = ApprovalChain(
            chain_id=f"approval-chain-{chain_hash[:16]}",
            command_id=command_id,
            tenant_id=policy.tenant_id,
            policy_id=policy.policy_id,
            required_roles=policy.required_roles,
            required_approver_count=policy.required_approver_count,
            approvals_received=(),
            status=status,
            due_at=due_at,
        )
        self._store.save_approval_chain(chain)
        return chain

    def _open_obligation(
        self,
        *,
        command_id: str,
        tenant_id: str,
        owner: TeamOwnership,
        obligation_type: str,
        due_at: str,
        evidence_required: tuple[str, ...],
        escalation_policy_id: str,
        terminal_certificate_id: str,
    ) -> Obligation:
        obligation_hash = canonical_hash({
            "command_id": command_id,
            "obligation_type": obligation_type,
            "due_at": due_at,
            "terminal_certificate_id": terminal_certificate_id,
        })
        obligation = Obligation(
            obligation_id=f"obligation-{obligation_hash[:16]}",
            command_id=command_id,
            tenant_id=tenant_id,
            owner_id=owner.primary_owner_id,
            owner_team=owner.owner_team,
            obligation_type=obligation_type,
            due_at=due_at,
            status=ObligationStatus.OPEN,
            evidence_required=evidence_required,
            escalation_policy_id=escalation_policy_id,
            terminal_certificate_id=terminal_certificate_id,
        )
        self._store.save_obligation(obligation)
        return obligation

    def _notify_approval_needed(self, tenant_id: str, chain: ApprovalChain, ownership: TeamOwnership) -> None:
        self._notifications.notify(
            tenant_id=tenant_id,
            notification_type=NotificationType.APPROVAL_NEEDED,
            priority=NotificationPriority.HIGH,
            title="Approval required",
            body=f"Command {chain.command_id} requires authority path {chain.chain_id}.",
            metadata={
                "command_id": chain.command_id,
                "chain_id": chain.chain_id,
                "owner_team": ownership.owner_team,
                "primary_owner_id": ownership.primary_owner_id,
            },
        )

    def _transition_chain(
        self,
        command_id: str,
        chain: ApprovalChain,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        next_state = (
            CommandState.APPROVAL_CHAIN_SATISFIED
            if chain.status in {ApprovalChainStatus.SATISFIED, ApprovalChainStatus.NOT_REQUIRED}
            else CommandState.APPROVAL_CHAIN_PENDING
        )
        self._commands.transition(
            command_id,
            next_state,
            approval_id=chain.chain_id,
            detail={"cause": "approval_chain_recorded", "approval_chain": asdict(chain), **(detail or {})},
        )

    def _replace_chain(self, chain: ApprovalChain, **changes: Any) -> ApprovalChain:
        updated = ApprovalChain(
            chain_id=chain.chain_id,
            command_id=chain.command_id,
            tenant_id=chain.tenant_id,
            policy_id=chain.policy_id,
            required_roles=chain.required_roles,
            required_approver_count=chain.required_approver_count,
            approvals_received=changes.get("approvals_received", chain.approvals_received),
            status=changes.get("status", chain.status),
            due_at=chain.due_at,
        )
        self._store.save_approval_chain(updated)
        return updated

    def _replace_obligation(self, obligation: Obligation, **changes: Any) -> Obligation:
        updated = Obligation(
            obligation_id=obligation.obligation_id,
            command_id=obligation.command_id,
            tenant_id=obligation.tenant_id,
            owner_id=obligation.owner_id,
            owner_team=obligation.owner_team,
            obligation_type=obligation.obligation_type,
            due_at=obligation.due_at,
            status=changes.get("status", obligation.status),
            evidence_required=obligation.evidence_required,
            escalation_policy_id=obligation.escalation_policy_id,
            terminal_certificate_id=obligation.terminal_certificate_id,
        )
        self._store.save_obligation(updated)
        return updated

    def _escalation_policy_id_for(self, tenant_id: str, command_id: str) -> str:
        chain = self._store.load_approval_chain_for_command(command_id)
        if chain is not None:
            return self._policy_for_chain(chain).escalation_policy_id
        policies = tuple(policy for policy in self._store.list_escalation_policies() if policy.tenant_id == tenant_id)
        return policies[0].policy_id if len(policies) == 1 else "default"

    def _escalation_route(self, obligation: Obligation) -> dict[str, str]:
        policy = self._store.load_escalation_policy(obligation.tenant_id, obligation.escalation_policy_id)
        if policy is not None:
            return {
                "fallback_owner_id": policy.fallback_owner_id,
                "escalation_team": policy.escalation_team,
            }
        command = self._commands.get(obligation.command_id)
        action = self._commands.governed_action_for(obligation.command_id)
        resource_ref = action.capability if action is not None else command.intent if command is not None else ""
        ownership = (
            self._store.load_ownership(obligation.tenant_id, resource_ref)
            if resource_ref
            else None
        )
        if ownership is not None:
            return {
                "fallback_owner_id": ownership.fallback_owner_id,
                "escalation_team": ownership.escalation_team,
            }
        return {
            "fallback_owner_id": obligation.owner_id,
            "escalation_team": obligation.owner_team,
        }

    def _missing_obligation_evidence(
        self,
        obligation: Obligation,
        evidence_refs: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(
            evidence_name for evidence_name in obligation.evidence_required
            if not self._evidence_ref_satisfies(evidence_name, evidence_refs)
        )

    def _evidence_ref_satisfies(self, evidence_name: str, evidence_refs: tuple[str, ...]) -> bool:
        prefixes = (
            evidence_name,
            f"{evidence_name}:",
            f"evidence:{evidence_name}:",
        )
        return any(ref == evidence_name or ref.startswith(prefixes[1:]) for ref in evidence_refs)

    def _policy_for_chain(self, chain: ApprovalChain) -> ApprovalPolicy:
        for policy in self._store.list_approval_policies():
            if policy.policy_id == chain.policy_id:
                return policy
        return ApprovalPolicy(
            policy_id=chain.policy_id,
            tenant_id=chain.tenant_id,
            capability="",
            risk_tier="",
            required_roles=chain.required_roles,
            required_approver_count=chain.required_approver_count,
            separation_of_duty=True,
            timeout_seconds=300,
            escalation_policy_id="default",
        )

    def _future_iso(self, *, seconds: int = 0, hours: int = 0) -> str:
        return (self._parse_time(self._clock()) + timedelta(seconds=seconds, hours=hours)).isoformat()

    def _parse_time(self, value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed


def build_authority_obligation_mesh_store_from_env() -> AuthorityObligationMeshStore:
    """Create an authority-obligation mesh store using gateway persistence environment."""
    import os

    require_persistent = _truthy_env(os.environ.get("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", ""))

    backend = os.environ.get("MULLU_AUTHORITY_MESH_BACKEND", "")
    if not backend:
        backend = os.environ.get("MULLU_DB_BACKEND", "memory")
    backend = backend.strip().lower()
    if require_persistent and backend != "postgresql":
        raise AuthorityObligationMeshConfigurationError("persistent authority-obligation mesh store required")
    if backend == "postgresql":
        connection_string = os.environ.get("MULLU_AUTHORITY_MESH_DB_URL", "")
        if not connection_string:
            connection_string = os.environ.get("MULLU_DB_URL", "")
        store = PostgresAuthorityObligationMeshStore(
            connection_string or "postgresql://localhost:5432/mullu"
        )
        status = store.status()
        if require_persistent and not status.get("available"):
            close = getattr(store, "close", None)
            if callable(close):
                close()
            raise AuthorityObligationMeshConfigurationError("persistent authority-obligation mesh store unavailable")
        return store
    if backend == "memory":
        return InMemoryAuthorityObligationMeshStore()
    raise ValueError("unsupported authority-obligation mesh backend")


def _truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
