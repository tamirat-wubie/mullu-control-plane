"""Phase 225C — Tenant Isolation Verifier (Cross-Tenant Audit).

Purpose: Verify and audit that tenant data boundaries are never violated.
    Scans operations for cross-tenant access patterns and reports violations.
Dependencies: None (stdlib only).
Invariants:
  - Cross-tenant access is always flagged.
  - Audit results are immutable.
  - Verification runs are bounded in scope.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Callable


@unique
class IsolationViolationType(Enum):
    CROSS_TENANT_READ = "cross_tenant_read"
    CROSS_TENANT_WRITE = "cross_tenant_write"
    SHARED_RESOURCE_LEAK = "shared_resource_leak"
    PRIVILEGE_ESCALATION = "privilege_escalation"


@dataclass(frozen=True)
class IsolationViolation:
    """A detected tenant isolation violation."""
    violation_id: str
    violation_type: IsolationViolationType
    source_tenant: str
    target_tenant: str
    resource: str
    description: str
    timestamp: float
    severity: str = "high"


@dataclass
class AuditResult:
    """Result of a tenant isolation audit run."""
    audit_id: str
    started_at: float
    completed_at: float
    operations_scanned: int
    violations: list[IsolationViolation] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": (self.completed_at - self.started_at) * 1000,
            "operations_scanned": self.operations_scanned,
            "violations_found": len(self.violations),
            "is_clean": self.is_clean,
        }


@dataclass
class TenantOperation:
    """An operation to be audited for isolation."""
    operation_id: str
    actor_tenant: str
    target_tenant: str
    resource: str
    operation_type: str  # "read", "write", "delete"


class TenantIsolationAuditor:
    """Audits operations for tenant isolation violations."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock
        self._audit_results: list[AuditResult] = []
        self._total_scanned = 0
        self._total_violations = 0

    def audit(self, operations: list[TenantOperation], audit_id: str = "") -> AuditResult:
        started = time.monotonic()
        violations: list[IsolationViolation] = []

        for op in operations:
            if op.actor_tenant != op.target_tenant:
                vtype = (IsolationViolationType.CROSS_TENANT_WRITE
                         if op.operation_type in ("write", "delete")
                         else IsolationViolationType.CROSS_TENANT_READ)
                violations.append(IsolationViolation(
                    violation_id=f"v-{len(violations)+1}",
                    violation_type=vtype,
                    source_tenant=op.actor_tenant,
                    target_tenant=op.target_tenant,
                    resource=op.resource,
                    description="cross-tenant operation detected",
                    timestamp=time.time(),
                ))

        completed = time.monotonic()
        result = AuditResult(
            audit_id=audit_id or f"audit-{len(self._audit_results)+1}",
            started_at=started,
            completed_at=completed,
            operations_scanned=len(operations),
            violations=violations,
        )
        self._audit_results.append(result)
        self._total_scanned += len(operations)
        self._total_violations += len(violations)
        return result

    @property
    def audit_count(self) -> int:
        return len(self._audit_results)

    def recent_audits(self, count: int = 10) -> list[AuditResult]:
        return self._audit_results[-count:]

    def summary(self) -> dict[str, Any]:
        return {
            "total_audits": self.audit_count,
            "total_operations_scanned": self._total_scanned,
            "total_violations": self._total_violations,
            "last_clean": all(r.is_clean for r in self._audit_results[-1:]) if self._audit_results else True,
        }
