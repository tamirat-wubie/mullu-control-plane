"""Rate Limit Quotas — Per-tenant configurable rate limits.

Purpose: Allows different tenants to have different rate limits based
    on their plan tier (free, pro, enterprise).  Overrides the default
    rate limit config per tenant and per endpoint.
Governance scope: quota configuration only.
Dependencies: RateLimitConfig from rate_limiter.py.
Invariants:
  - Default quota applies when no tenant-specific override exists.
  - Tenant overrides are applied atomically.
  - Plan tiers map to predefined quota sets.
  - Thread-safe — concurrent quota reads + writes are safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.governance.guards.rate_limit import RateLimitConfig


@dataclass(frozen=True, slots=True)
class QuotaPlan:
    """A named quota plan with rate limit configs."""

    name: str
    description: str = ""
    default_config: RateLimitConfig = field(default_factory=RateLimitConfig)
    identity_config: RateLimitConfig | None = None
    endpoint_overrides: dict[str, RateLimitConfig] = field(default_factory=dict)
    max_sessions: int = 100
    max_llm_calls_per_day: int = 0  # 0 = unlimited


# Predefined plans
FREE_PLAN = QuotaPlan(
    name="free",
    description="Free tier — limited usage",
    default_config=RateLimitConfig(max_tokens=10, refill_rate=0.5, burst_limit=5),
    identity_config=RateLimitConfig(max_tokens=5, refill_rate=0.2, burst_limit=3),
    max_sessions=10,
    max_llm_calls_per_day=50,
)

PRO_PLAN = QuotaPlan(
    name="pro",
    description="Pro tier — standard usage",
    default_config=RateLimitConfig(max_tokens=60, refill_rate=2.0, burst_limit=10),
    identity_config=RateLimitConfig(max_tokens=20, refill_rate=1.0, burst_limit=5),
    max_sessions=100,
    max_llm_calls_per_day=1000,
)

ENTERPRISE_PLAN = QuotaPlan(
    name="enterprise",
    description="Enterprise tier — high-throughput",
    default_config=RateLimitConfig(max_tokens=500, refill_rate=20.0, burst_limit=50),
    identity_config=RateLimitConfig(max_tokens=100, refill_rate=5.0, burst_limit=20),
    max_sessions=1000,
    max_llm_calls_per_day=0,  # Unlimited
)

PREDEFINED_PLANS = {
    "free": FREE_PLAN,
    "pro": PRO_PLAN,
    "enterprise": ENTERPRISE_PLAN,
}


class QuotaManager:
    """Manages per-tenant rate limit quotas.

    Usage:
        qm = QuotaManager()
        qm.assign_plan("tenant-1", "pro")
        qm.assign_plan("tenant-2", "enterprise")

        # Get effective config for a tenant
        config = qm.get_config("tenant-1")  # Returns PRO_PLAN config
        config = qm.get_config("unknown-tenant")  # Returns default (free)

        # Custom override
        qm.set_custom("tenant-3", RateLimitConfig(max_tokens=200, refill_rate=10.0))
    """

    def __init__(self, *, default_plan: str = "free") -> None:
        self._default_plan = PREDEFINED_PLANS.get(default_plan, FREE_PLAN)
        self._tenant_plans: dict[str, str] = {}  # tenant_id → plan name
        self._custom_configs: dict[str, RateLimitConfig] = {}  # tenant_id → custom config
        self._custom_identity_configs: dict[str, RateLimitConfig] = {}
        self._lock = threading.Lock()

    def assign_plan(self, tenant_id: str, plan_name: str) -> bool:
        """Assign a predefined plan to a tenant."""
        if plan_name not in PREDEFINED_PLANS:
            return False
        with self._lock:
            self._tenant_plans[tenant_id] = plan_name
            # Remove custom overrides when plan is assigned
            self._custom_configs.pop(tenant_id, None)
            self._custom_identity_configs.pop(tenant_id, None)
            return True

    def set_custom(
        self,
        tenant_id: str,
        config: RateLimitConfig,
        *,
        identity_config: RateLimitConfig | None = None,
    ) -> None:
        """Set a custom rate limit config for a tenant (overrides plan)."""
        with self._lock:
            self._custom_configs[tenant_id] = config
            if identity_config is not None:
                self._custom_identity_configs[tenant_id] = identity_config

    def get_plan(self, tenant_id: str) -> QuotaPlan:
        """Get the effective plan for a tenant."""
        with self._lock:
            plan_name = self._tenant_plans.get(tenant_id)
        if plan_name:
            return PREDEFINED_PLANS.get(plan_name, self._default_plan)
        return self._default_plan

    def get_config(self, tenant_id: str) -> RateLimitConfig:
        """Get the effective rate limit config for a tenant."""
        with self._lock:
            custom = self._custom_configs.get(tenant_id)
            if custom is not None:
                return custom
            plan_name = self._tenant_plans.get(tenant_id)
        plan = PREDEFINED_PLANS.get(plan_name, self._default_plan) if plan_name else self._default_plan
        return plan.default_config

    def get_identity_config(self, tenant_id: str) -> RateLimitConfig | None:
        """Get per-identity rate limit config for a tenant."""
        with self._lock:
            custom = self._custom_identity_configs.get(tenant_id)
            if custom is not None:
                return custom
            plan_name = self._tenant_plans.get(tenant_id)
        plan = PREDEFINED_PLANS.get(plan_name, self._default_plan) if plan_name else self._default_plan
        return plan.identity_config

    def list_tenants(self) -> dict[str, str]:
        """List tenant → plan assignments."""
        with self._lock:
            return dict(self._tenant_plans)

    def remove_tenant(self, tenant_id: str) -> bool:
        with self._lock:
            removed = tenant_id in self._tenant_plans or tenant_id in self._custom_configs
            self._tenant_plans.pop(tenant_id, None)
            self._custom_configs.pop(tenant_id, None)
            self._custom_identity_configs.pop(tenant_id, None)
            return removed

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "default_plan": self._default_plan.name,
                "tenant_plans": len(self._tenant_plans),
                "custom_overrides": len(self._custom_configs),
                "available_plans": list(PREDEFINED_PLANS.keys()),
            }
