"""Phase 195D — Adapter & Connector Governance.

Purpose: Ensures no external side effect occurs without governed execution authority.
Governance scope: all effectful adapters and connectors.
Dependencies: execution_authority.
Invariants: fail-closed on missing authority, all effects audited.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

@dataclass(frozen=True, slots=True)
class AdapterAuthority:
    """Proof that an adapter call was authorized through governed execution."""
    authority_id: str
    actor_id: str
    adapter_type: str
    operation: str
    issued_at: str

class AdapterAuthorityError(Exception):
    """Raised when an adapter is called without valid authority."""
    pass

@dataclass
class AdapterAuditEntry:
    adapter_type: str
    operation: str
    authorized: bool
    actor_id: str
    timestamp: str

class AdapterGovernanceGuard:
    """Guards all effectful adapter calls. Tracks authorized vs unauthorized attempts."""

    def __init__(self):
        self._audit: list[AdapterAuditEntry] = []
        self._blocked: int = 0

    def authorize(self, adapter_type: str, operation: str, actor_id: str) -> AdapterAuthority:
        now = datetime.now(timezone.utc).isoformat()
        self._audit.append(AdapterAuditEntry(adapter_type, operation, True, actor_id, now))
        return AdapterAuthority(
            authority_id=f"auth-{len(self._audit)}",
            actor_id=actor_id,
            adapter_type=adapter_type,
            operation=operation,
            issued_at=now,
        )

    def deny(self, adapter_type: str, operation: str, reason: str = "no_authority") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._audit.append(AdapterAuditEntry(adapter_type, operation, False, "unknown", now))
        self._blocked += 1

    def require_authority(self, authority: AdapterAuthority | None, adapter_type: str, operation: str) -> None:
        if authority is None:
            self.deny(adapter_type, operation)
            raise AdapterAuthorityError(f"No authority for {adapter_type}.{operation}")
        if authority.adapter_type != adapter_type:
            self.deny(adapter_type, operation, "type_mismatch")
            raise AdapterAuthorityError(f"Authority type mismatch: {authority.adapter_type} != {adapter_type}")

    @property
    def total_calls(self) -> int:
        return len(self._audit)

    @property
    def authorized_calls(self) -> int:
        return sum(1 for a in self._audit if a.authorized)

    @property
    def blocked_calls(self) -> int:
        return self._blocked

    def governance_ratio(self) -> float:
        return self.authorized_calls / self.total_calls if self.total_calls else 1.0

    def audit_report(self) -> dict[str, Any]:
        return {
            "total": self.total_calls,
            "authorized": self.authorized_calls,
            "blocked": self.blocked_calls,
            "ratio": round(self.governance_ratio(), 3),
            "adapters_used": list(set(a.adapter_type for a in self._audit)),
        }

# Registry of all effectful adapters that require governance
EFFECTFUL_ADAPTERS = frozenset({
    "shell_executor",
    "http_connector",
    "smtp_communication",
    "browser_adapter",
    "stub_model",
    "filesystem_observer",
    "process_observer",
    "external_connector",
})

def is_effectful(adapter_type: str) -> bool:
    return adapter_type in EFFECTFUL_ADAPTERS
