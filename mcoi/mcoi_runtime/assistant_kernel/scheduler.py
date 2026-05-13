"""Purpose: assistant schedule request contracts.
Governance scope: recurrence identity, approval waits, idempotency keys, and
    bounded scheduling metadata.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Scheduling creates a future action record, not immediate execution.
  - Every scheduled action has a deterministic idempotency key.
  - Approval waits are represented explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


@dataclass(frozen=True, slots=True)
class AssistantScheduleRequest:
    """Request to schedule a future assistant action."""

    tenant_id: str
    owner_id: str
    capability_id: str
    run_at: str
    requested_at: str
    approval_required: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "owner_id", ensure_non_empty_text("owner_id", self.owner_id))
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        object.__setattr__(self, "run_at", ensure_non_empty_text("run_at", self.run_at))
        object.__setattr__(self, "requested_at", ensure_non_empty_text("requested_at", self.requested_at))
        if not isinstance(self.approval_required, bool):
            raise RuntimeCoreInvariantError("approval_required must be boolean")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ScheduledAssistantAction:
    """Governed future action record."""

    schedule_id: str
    tenant_id: str
    owner_id: str
    capability_id: str
    run_at: str
    idempotency_key: str
    state: str
    approval_required: bool
    metadata: dict[str, Any] = field(default_factory=dict)


def schedule_assistant_action(request: AssistantScheduleRequest) -> ScheduledAssistantAction:
    """Create a deterministic scheduled action record."""
    idempotency_key = stable_identifier(
        "assistant-idempotency",
        {
            "tenant_id": request.tenant_id,
            "owner_id": request.owner_id,
            "capability_id": request.capability_id,
            "run_at": request.run_at,
        },
    )
    return ScheduledAssistantAction(
        schedule_id=stable_identifier("assistant-schedule", {"idempotency_key": idempotency_key}),
        tenant_id=request.tenant_id,
        owner_id=request.owner_id,
        capability_id=request.capability_id,
        run_at=request.run_at,
        idempotency_key=idempotency_key,
        state="waiting_for_approval" if request.approval_required else "scheduled",
        approval_required=request.approval_required,
        metadata=dict(request.metadata),
    )
