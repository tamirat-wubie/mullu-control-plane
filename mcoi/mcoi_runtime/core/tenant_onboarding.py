"""Tenant Onboarding — Automated tenant setup workflow.

Purpose: Orchestrates the steps required to onboard a new tenant:
    create budget, assign rate limit plan, register identity,
    configure gateway channel mapping, and activate tenant gating.
Governance scope: tenant lifecycle management.
Dependencies: none (pure orchestration).
Invariants:
  - Onboarding is atomic in intent (all-or-nothing validation).
  - Each step is tracked and auditable.
  - Failed onboarding produces a clear error report.
  - Thread-safe — concurrent onboardings are safe.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class OnboardingStep:
    """A single step in the onboarding process."""

    name: str
    status: str  # "pending", "completed", "failed", "skipped"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class OnboardingResult:
    """Result of a tenant onboarding."""

    tenant_id: str
    success: bool
    steps: tuple[OnboardingStep, ...]
    completed_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "success": self.success,
            "steps": [
                {"name": s.name, "status": s.status, "detail": s.detail}
                for s in self.steps
            ],
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class OnboardingRequest:
    """Request to onboard a new tenant."""

    tenant_id: str
    tenant_name: str
    plan: str = "free"  # free, pro, enterprise
    admin_identity_id: str = ""
    admin_email: str = ""
    channels: tuple[str, ...] = ()  # Channels to configure
    metadata: dict[str, Any] = field(default_factory=dict)


class TenantOnboarding:
    """Automated tenant onboarding workflow.

    Usage:
        onboarding = TenantOnboarding(clock=lambda: "2026-04-07T12:00:00Z")

        # Register step handlers
        onboarding.register_step("create_budget", budget_handler)
        onboarding.register_step("assign_plan", plan_handler)
        onboarding.register_step("register_identity", identity_handler)

        # Run onboarding
        result = onboarding.onboard(OnboardingRequest(
            tenant_id="t1", tenant_name="Acme Corp",
            plan="pro", admin_identity_id="admin@acme.com",
        ))
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._step_handlers: list[tuple[str, Callable[[OnboardingRequest], str]]] = []
        self._lock = threading.Lock()
        self._onboarded: dict[str, OnboardingResult] = {}
        self._total_onboarded = 0
        self._total_failed = 0

    def register_step(
        self,
        name: str,
        handler: Callable[[OnboardingRequest], str],
    ) -> None:
        """Register an onboarding step handler.

        Handler receives OnboardingRequest and returns a detail string.
        Raise an exception to indicate failure.
        Steps execute in registration order.
        """
        self._step_handlers.append((name, handler))

    def onboard(self, request: OnboardingRequest) -> OnboardingResult:
        """Execute the full onboarding workflow."""
        # Check if already onboarded
        with self._lock:
            if request.tenant_id in self._onboarded:
                existing = self._onboarded[request.tenant_id]
                if existing.success:
                    return OnboardingResult(
                        tenant_id=request.tenant_id,
                        success=False,
                        steps=(),
                        error="tenant already onboarded",
                    )

        steps: list[OnboardingStep] = []
        failed = False
        error_msg = ""

        for name, handler in self._step_handlers:
            if failed:
                steps.append(OnboardingStep(name=name, status="skipped", detail="previous step failed"))
                continue

            try:
                detail = handler(request)
                steps.append(OnboardingStep(name=name, status="completed", detail=detail))
            except Exception as exc:
                exc_type = type(exc).__name__
                steps.append(OnboardingStep(name=name, status="failed", detail="step execution error"))
                failed = True
                error_msg = "step '{}' failed ({})".format(name, exc_type)

        success = not failed
        result = OnboardingResult(
            tenant_id=request.tenant_id,
            success=success,
            steps=tuple(steps),
            completed_at=self._clock(),
            error=error_msg,
        )

        with self._lock:
            self._onboarded[request.tenant_id] = result
            if success:
                self._total_onboarded += 1
            else:
                self._total_failed += 1

        return result

    def get_result(self, tenant_id: str) -> OnboardingResult | None:
        with self._lock:
            return self._onboarded.get(tenant_id)

    def is_onboarded(self, tenant_id: str) -> bool:
        with self._lock:
            result = self._onboarded.get(tenant_id)
            return result is not None and result.success

    @property
    def step_count(self) -> int:
        return len(self._step_handlers)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "registered_steps": len(self._step_handlers),
                "total_onboarded": self._total_onboarded,
                "total_failed": self._total_failed,
                "tenants_tracked": len(self._onboarded),
            }
