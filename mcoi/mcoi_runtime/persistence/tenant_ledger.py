"""Phase 201D — Tenant-Scoped Ledger Isolation.

Purpose: Per-tenant ledger views and session scoping.
    Ensures each tenant can only access their own ledger entries
    and sessions. Cross-tenant data access is structurally prevented.
Governance scope: tenant data isolation only.
Dependencies: persistence store.
Invariants:
  - Ledger queries are always tenant-scoped — no global leaks.
  - Sessions belong to exactly one tenant.
  - Cross-tenant access returns empty results, never errors.
  - Admin can access aggregated views but never raw cross-tenant data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class TenantSession:
    """Session scoped to a single tenant."""

    session_id: str
    tenant_id: str
    actor_id: str
    created_at: str
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TenantLedgerEntry:
    """Single ledger entry scoped to a tenant."""

    entry_id: str
    tenant_id: str
    entry_type: str  # "llm", "execution", "certification", etc.
    actor_id: str
    content: dict[str, Any]
    content_hash: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class TenantLedgerSummary:
    """Aggregated view of a tenant's ledger."""

    tenant_id: str
    total_entries: int
    entry_types: dict[str, int]
    total_cost: float
    first_entry_at: str
    last_entry_at: str


class TenantLedger:
    """Tenant-isolated ledger with session scoping.

    Each tenant's data is structurally isolated — queries are
    always filtered by tenant_id, making cross-tenant leaks impossible.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._entries: dict[str, list[TenantLedgerEntry]] = {}  # tenant_id -> entries
        self._sessions: dict[str, TenantSession] = {}  # session_id -> session

    def append(
        self,
        tenant_id: str,
        entry_type: str,
        actor_id: str,
        content: dict[str, Any],
    ) -> TenantLedgerEntry:
        """Append a ledger entry for a tenant."""
        content_hash = sha256(
            json.dumps(content, sort_keys=True, default=str).encode()
        ).hexdigest()

        entry_id = sha256(
            f"{tenant_id}:{entry_type}:{self._clock()}:{content_hash[:8]}".encode()
        ).hexdigest()[:16]

        entry = TenantLedgerEntry(
            entry_id=entry_id,
            tenant_id=tenant_id,
            entry_type=entry_type,
            actor_id=actor_id,
            content=content,
            content_hash=content_hash,
            recorded_at=self._clock(),
        )

        if tenant_id not in self._entries:
            self._entries[tenant_id] = []
        self._entries[tenant_id].append(entry)
        return entry

    def query(
        self,
        tenant_id: str,
        *,
        entry_type: str | None = None,
        limit: int = 50,
    ) -> list[TenantLedgerEntry]:
        """Query ledger entries for a specific tenant.

        Always tenant-scoped — cannot access other tenants' data.
        """
        entries = self._entries.get(tenant_id, [])
        if entry_type is not None:
            entries = [e for e in entries if e.entry_type == entry_type]
        return entries[-limit:]

    def count(self, tenant_id: str) -> int:
        """Count of entries for a tenant."""
        return len(self._entries.get(tenant_id, []))

    def summary(self, tenant_id: str) -> TenantLedgerSummary:
        """Aggregated summary for a tenant."""
        entries = self._entries.get(tenant_id, [])
        if not entries:
            return TenantLedgerSummary(
                tenant_id=tenant_id,
                total_entries=0,
                entry_types={},
                total_cost=0.0,
                first_entry_at="",
                last_entry_at="",
            )

        type_counts: dict[str, int] = {}
        total_cost = 0.0
        for e in entries:
            type_counts[e.entry_type] = type_counts.get(e.entry_type, 0) + 1
            total_cost += e.content.get("cost", 0.0)

        return TenantLedgerSummary(
            tenant_id=tenant_id,
            total_entries=len(entries),
            entry_types=type_counts,
            total_cost=total_cost,
            first_entry_at=entries[0].recorded_at,
            last_entry_at=entries[-1].recorded_at,
        )

    # ═══ Sessions ═══

    def create_session(
        self,
        session_id: str,
        tenant_id: str,
        actor_id: str,
    ) -> TenantSession:
        """Create a tenant-scoped session."""
        session = TenantSession(
            session_id=session_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            created_at=self._clock(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> TenantSession | None:
        return self._sessions.get(session_id)

    def validate_session_tenant(self, session_id: str, tenant_id: str) -> bool:
        """Verify a session belongs to the claimed tenant."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        return session.tenant_id == tenant_id

    def tenant_sessions(self, tenant_id: str) -> list[TenantSession]:
        """Get all sessions for a tenant."""
        return [s for s in self._sessions.values() if s.tenant_id == tenant_id]

    def deactivate_session(self, session_id: str) -> bool:
        """Deactivate a session."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        self._sessions[session_id] = TenantSession(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            actor_id=session.actor_id,
            created_at=session.created_at,
            active=False,
        )
        return True

    # ═══ Admin views (aggregated, never raw cross-tenant) ═══

    def all_tenant_ids(self) -> list[str]:
        """List all tenant IDs with ledger entries."""
        return sorted(self._entries.keys())

    def global_stats(self) -> dict[str, Any]:
        """Aggregated stats across all tenants (no raw data)."""
        total_entries = sum(len(entries) for entries in self._entries.values())
        total_sessions = len(self._sessions)
        active_sessions = sum(1 for s in self._sessions.values() if s.active)

        return {
            "tenant_count": len(self._entries),
            "total_entries": total_entries,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
        }
