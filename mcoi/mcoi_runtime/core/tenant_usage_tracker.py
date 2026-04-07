"""Tenant Usage Tracker — Per-tenant metrics for billing and insights.

Purpose: Tracks LLM usage, gateway messages, skill executions, and costs
    per tenant for billing, capacity planning, and usage dashboards.
Governance scope: metric aggregation only.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Metrics are tenant-scoped (no cross-tenant leakage).
  - Bounded: per-tenant counters, not per-request storage.
  - Thread-safe — concurrent metric updates are safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class TenantUsage:
    """Aggregated usage metrics for a single tenant."""

    tenant_id: str
    llm_calls: int = 0
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    llm_cost: float = 0.0
    gateway_messages: int = 0
    gateway_errors: int = 0
    skill_executions: int = 0
    skill_errors: int = 0
    sessions_created: int = 0
    approvals_denied: int = 0
    rate_limit_denials: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "llm_calls": self.llm_calls,
            "llm_tokens": self.llm_tokens_input + self.llm_tokens_output,
            "llm_cost": round(self.llm_cost, 4),
            "gateway_messages": self.gateway_messages,
            "gateway_errors": self.gateway_errors,
            "skill_executions": self.skill_executions,
            "sessions_created": self.sessions_created,
        }


class TenantUsageTracker:
    """Per-tenant usage tracking."""

    MAX_TENANTS = 50_000

    def __init__(self) -> None:
        self._usage: dict[str, TenantUsage] = {}
        self._lock = threading.Lock()

    def _get(self, tenant_id: str) -> TenantUsage:
        if tenant_id not in self._usage:
            if len(self._usage) >= self.MAX_TENANTS:
                lowest = min(self._usage, key=lambda t: self._usage[t].llm_calls + self._usage[t].gateway_messages)
                del self._usage[lowest]
            self._usage[tenant_id] = TenantUsage(tenant_id=tenant_id)
        return self._usage[tenant_id]

    def record_llm(self, tenant_id: str, *, tokens_in: int = 0, tokens_out: int = 0, cost: float = 0.0) -> None:
        with self._lock:
            u = self._get(tenant_id)
            u.llm_calls += 1
            u.llm_tokens_input += tokens_in
            u.llm_tokens_output += tokens_out
            u.llm_cost += cost

    def record_message(self, tenant_id: str, *, error: bool = False) -> None:
        with self._lock:
            u = self._get(tenant_id)
            u.gateway_messages += 1
            if error:
                u.gateway_errors += 1

    def record_skill(self, tenant_id: str, *, success: bool = True) -> None:
        with self._lock:
            u = self._get(tenant_id)
            u.skill_executions += 1
            if not success:
                u.skill_errors += 1

    def record_session(self, tenant_id: str) -> None:
        with self._lock:
            self._get(tenant_id).sessions_created += 1

    def record_rate_denial(self, tenant_id: str) -> None:
        with self._lock:
            self._get(tenant_id).rate_limit_denials += 1

    def get(self, tenant_id: str) -> TenantUsage | None:
        with self._lock:
            return self._usage.get(tenant_id)

    def top_by_cost(self, limit: int = 10) -> list[TenantUsage]:
        with self._lock:
            return sorted(self._usage.values(), key=lambda u: -u.llm_cost)[:limit]

    def top_by_volume(self, limit: int = 10) -> list[TenantUsage]:
        with self._lock:
            return sorted(self._usage.values(), key=lambda u: -(u.llm_calls + u.gateway_messages))[:limit]

    def with_errors(self) -> list[TenantUsage]:
        with self._lock:
            return [u for u in self._usage.values() if u.gateway_errors > 0 or u.skill_errors > 0]

    def reset(self, tenant_id: str) -> bool:
        with self._lock:
            if tenant_id in self._usage:
                self._usage[tenant_id] = TenantUsage(tenant_id=tenant_id)
                return True
            return False

    @property
    def tenant_count(self) -> int:
        return len(self._usage)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tenants": len(self._usage),
                "total_cost": round(sum(u.llm_cost for u in self._usage.values()), 4),
                "total_calls": sum(u.llm_calls for u in self._usage.values()),
                "total_messages": sum(u.gateway_messages for u in self._usage.values()),
            }
