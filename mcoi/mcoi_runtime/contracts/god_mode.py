"""Purpose: god-mode capability contracts.

Governance scope: typed contracts for privileged ("god mode") capabilities that
bypass one or more standard governance controls. Every god capability ships
DORMANT and is invocable only after an explicit two-stage user agreement:

  1. Registration agreement — promotes a dormant capability to ARMED.
  2. Activation agreement — issues a single short-lived invocation ticket.

Dependencies: shared contract base helpers.

Invariants:
  - God capabilities are inert until a registration agreement is recorded.
  - Each invocation requires a fresh, unexpired, unconsumed ticket.
  - Tickets are single-use unless explicitly session-scoped.
  - Justifications are mandatory and bounded in length.
  - Withdrawals and revocations are first-class and irreversible-as-events.
  - Receipts capture pre/post hashes and the full agreement chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_positive_int,
)


# ---------------------------------------------------------------------------
# Bounded text helpers (god-mode-local — keep validation messages stable
# without depending on the global field-label allowlist)
# ---------------------------------------------------------------------------


_MIN_JUSTIFICATION_CHARS = 50
_MAX_JUSTIFICATION_CHARS = 2000
_MAX_TICKET_TTL_SECONDS = 3600
_MIN_TICKET_TTL_SECONDS = 5


def _require_justification(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = value.strip()
    if len(text) < _MIN_JUSTIFICATION_CHARS:
        raise ValueError(
            f"{field_name} must be at least {_MIN_JUSTIFICATION_CHARS} chars"
        )
    if len(text) > _MAX_JUSTIFICATION_CHARS:
        raise ValueError(
            f"{field_name} must not exceed {_MAX_JUSTIFICATION_CHARS} chars"
        )
    return text


def _require_ttl_seconds(value: int, field_name: str) -> int:
    require_positive_int(value, field_name)
    if value < _MIN_TICKET_TTL_SECONDS:
        raise ValueError(
            f"{field_name} must be >= {_MIN_TICKET_TTL_SECONDS} seconds"
        )
    if value > _MAX_TICKET_TTL_SECONDS:
        raise ValueError(
            f"{field_name} must not exceed {_MAX_TICKET_TTL_SECONDS} seconds"
        )
    return value


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GodCapabilityState(StrEnum):
    """Lifecycle of a god capability in the registry."""

    DORMANT = "dormant"              # registered but no agreement → not invocable
    PENDING_DUAL = "pending_dual"    # 1 of 2 agreements recorded for a dual-control cap
    ARMED = "armed"                  # registration agreement(s) recorded → invocable via ticket
    SUSPENDED = "suspended"          # operator-paused; tickets refused
    WITHDRAWN = "withdrawn"          # registration revoked; back to dormant-class


class GodCapabilityBlastRadius(StrEnum):
    """Severity tiering for god capabilities."""

    LOCAL = "local"              # affects a single record / single tenant scope
    TENANT = "tenant"            # affects an entire tenant
    PLATFORM = "platform"        # affects multi-tenant platform state
    CATASTROPHIC = "catastrophic"  # irreversible / cross-system blast


class GodTicketState(StrEnum):
    """Lifecycle of an issued invocation ticket."""

    ISSUED = "issued"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class GodAgreementKind(StrEnum):
    """Two layers of consent in the god-mode flow."""

    REGISTRATION = "registration"  # agree to make capability invocable at all
    ACTIVATION = "activation"      # agree to issue one ticket


class GodReceiptOutcome(StrEnum):
    """Outcome captured on a consumption receipt."""

    SUCCESS = "success"
    FAILURE = "failure"
    ABORTED = "aborted"


# ---------------------------------------------------------------------------
# Capability descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GodCapability(ContractRecord):
    """Static descriptor for a privileged capability.

    A capability is a *proposal* — it does nothing until promoted to ARMED via
    a `RegistrationAgreement`. Capabilities are registered at module import
    time by the subsystem that owns the underlying privileged operation.
    """

    module: str
    name: str
    description: str
    blast_radius: GodCapabilityBlastRadius
    bypasses: tuple[str, ...]
    default_ttl_seconds: int = 60
    requires_session: bool = False
    min_justification_chars: int = _MIN_JUSTIFICATION_CHARS
    one_shot: bool = True
    requires_dual_control: bool = False
    dual_control_min_actors: int = 2

    def __post_init__(self) -> None:
        object.__setattr__(self, "module", require_non_empty_text(self.module, "module"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(
            self,
            "description",
            require_non_empty_text(self.description, "description"),
        )
        if not isinstance(self.blast_radius, GodCapabilityBlastRadius):
            raise ValueError("blast_radius must be a GodCapabilityBlastRadius value")
        bypasses = freeze_value(list(self.bypasses))
        if not isinstance(bypasses, tuple) or not bypasses:
            raise ValueError("bypasses must contain at least one bypass label")
        for item in bypasses:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("bypasses entries must be non-empty strings")
        object.__setattr__(self, "bypasses", bypasses)
        _require_ttl_seconds(self.default_ttl_seconds, "default_ttl_seconds")
        if self.min_justification_chars < _MIN_JUSTIFICATION_CHARS:
            raise ValueError(
                f"min_justification_chars must be >= {_MIN_JUSTIFICATION_CHARS}"
            )
        if self.min_justification_chars > _MAX_JUSTIFICATION_CHARS:
            raise ValueError(
                f"min_justification_chars must be <= {_MAX_JUSTIFICATION_CHARS}"
            )
        if not isinstance(self.requires_session, bool):
            raise ValueError("requires_session must be a bool")
        if not isinstance(self.one_shot, bool):
            raise ValueError("one_shot must be a bool")
        if not isinstance(self.requires_dual_control, bool):
            raise ValueError("requires_dual_control must be a bool")
        if not isinstance(self.dual_control_min_actors, int) or isinstance(
            self.dual_control_min_actors, bool
        ):
            raise ValueError("dual_control_min_actors must be an int")
        if self.dual_control_min_actors < 2:
            raise ValueError("dual_control_min_actors must be >= 2")
        if self.dual_control_min_actors > 5:
            raise ValueError("dual_control_min_actors must be <= 5")

    @property
    def key(self) -> tuple[str, str]:
        return (self.module, self.name)

    @property
    def fqn(self) -> str:
        return f"{self.module}.{self.name}"


# ---------------------------------------------------------------------------
# Agreement records (consent ledger)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegistrationAgreement(ContractRecord):
    """Operator consent that promotes a DORMANT capability to ARMED."""

    agreement_id: str
    capability_module: str
    capability_name: str
    actor_id: str
    justification: str
    recorded_at: str
    withdrawn_at: str = ""
    withdrawn_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agreement_id",
            require_non_empty_text(self.agreement_id, "agreement_id"),
        )
        object.__setattr__(
            self,
            "capability_module",
            require_non_empty_text(self.capability_module, "capability_module"),
        )
        object.__setattr__(
            self,
            "capability_name",
            require_non_empty_text(self.capability_name, "capability_name"),
        )
        object.__setattr__(
            self, "actor_id", require_non_empty_text(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "justification", _require_justification(self.justification, "justification")
        )
        object.__setattr__(
            self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at")
        )
        if self.withdrawn_at:
            object.__setattr__(
                self,
                "withdrawn_at",
                require_datetime_text(self.withdrawn_at, "withdrawn_at"),
            )
            if not self.withdrawn_reason.strip():
                raise ValueError("withdrawn_reason required when withdrawn_at is set")

    @property
    def is_active(self) -> bool:
        return not self.withdrawn_at


@dataclass(frozen=True, slots=True)
class ActivationAgreement(ContractRecord):
    """Per-invocation consent that becomes a single-use `GodModeTicket`."""

    agreement_id: str
    capability_module: str
    capability_name: str
    actor_id: str
    justification: str
    target: tuple[tuple[str, str], ...]
    requested_ttl_seconds: int
    recorded_at: str
    tenant_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agreement_id",
            require_non_empty_text(self.agreement_id, "agreement_id"),
        )
        object.__setattr__(
            self,
            "capability_module",
            require_non_empty_text(self.capability_module, "capability_module"),
        )
        object.__setattr__(
            self,
            "capability_name",
            require_non_empty_text(self.capability_name, "capability_name"),
        )
        object.__setattr__(
            self, "actor_id", require_non_empty_text(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "justification", _require_justification(self.justification, "justification")
        )
        target = freeze_value(list(self.target))
        if not isinstance(target, tuple):
            raise ValueError("target must be tuple-castable")
        for entry in target:
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or not isinstance(entry[0], str)
                or not isinstance(entry[1], str)
            ):
                raise ValueError("target entries must be (str, str) pairs")
        object.__setattr__(self, "target", target)
        _require_ttl_seconds(self.requested_ttl_seconds, "requested_ttl_seconds")
        object.__setattr__(
            self, "recorded_at", require_datetime_text(self.recorded_at, "recorded_at")
        )
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a string")


# ---------------------------------------------------------------------------
# Ticket + consumption receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GodModeTicket(ContractRecord):
    """Single-use invocation grant derived from an `ActivationAgreement`."""

    ticket_id: str
    agreement_id: str
    capability_module: str
    capability_name: str
    actor_id: str
    issued_at: str
    expires_at: str
    state: GodTicketState
    tenant_id: str = ""
    consumed_at: str = ""
    revoked_at: str = ""
    revoked_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "ticket_id", require_non_empty_text(self.ticket_id, "ticket_id")
        )
        object.__setattr__(
            self,
            "agreement_id",
            require_non_empty_text(self.agreement_id, "agreement_id"),
        )
        object.__setattr__(
            self,
            "capability_module",
            require_non_empty_text(self.capability_module, "capability_module"),
        )
        object.__setattr__(
            self,
            "capability_name",
            require_non_empty_text(self.capability_name, "capability_name"),
        )
        object.__setattr__(
            self, "actor_id", require_non_empty_text(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "issued_at", require_datetime_text(self.issued_at, "issued_at")
        )
        object.__setattr__(
            self, "expires_at", require_datetime_text(self.expires_at, "expires_at")
        )
        if not isinstance(self.state, GodTicketState):
            raise ValueError("state must be a GodTicketState value")
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a string")
        if self.consumed_at:
            object.__setattr__(
                self,
                "consumed_at",
                require_datetime_text(self.consumed_at, "consumed_at"),
            )
        if self.revoked_at:
            object.__setattr__(
                self,
                "revoked_at",
                require_datetime_text(self.revoked_at, "revoked_at"),
            )
            if not self.revoked_reason.strip():
                raise ValueError("revoked_reason required when revoked_at is set")


@dataclass(frozen=True, slots=True)
class GodModeReceipt(ContractRecord):
    """Audit receipt produced when a god ticket is consumed."""

    receipt_id: str
    ticket_id: str
    agreement_id: str
    capability_module: str
    capability_name: str
    actor_id: str
    outcome: GodReceiptOutcome
    consumed_at: str
    pre_state_hash: str
    post_state_hash: str
    tenant_id: str = ""
    detail: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    failure_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "receipt_id", require_non_empty_text(self.receipt_id, "receipt_id")
        )
        object.__setattr__(
            self, "ticket_id", require_non_empty_text(self.ticket_id, "ticket_id")
        )
        object.__setattr__(
            self,
            "agreement_id",
            require_non_empty_text(self.agreement_id, "agreement_id"),
        )
        object.__setattr__(
            self,
            "capability_module",
            require_non_empty_text(self.capability_module, "capability_module"),
        )
        object.__setattr__(
            self,
            "capability_name",
            require_non_empty_text(self.capability_name, "capability_name"),
        )
        object.__setattr__(
            self, "actor_id", require_non_empty_text(self.actor_id, "actor_id")
        )
        if not isinstance(self.outcome, GodReceiptOutcome):
            raise ValueError("outcome must be a GodReceiptOutcome value")
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a string")
        object.__setattr__(
            self,
            "consumed_at",
            require_datetime_text(self.consumed_at, "consumed_at"),
        )
        object.__setattr__(
            self,
            "pre_state_hash",
            require_non_empty_text(self.pre_state_hash, "pre_state_hash"),
        )
        object.__setattr__(
            self,
            "post_state_hash",
            require_non_empty_text(self.post_state_hash, "post_state_hash"),
        )
        detail = freeze_value(list(self.detail))
        if not isinstance(detail, tuple):
            raise ValueError("detail must be tuple-castable")
        for entry in detail:
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or not isinstance(entry[0], str)
                or not isinstance(entry[1], str)
            ):
                raise ValueError("detail entries must be (str, str) pairs")
        object.__setattr__(self, "detail", detail)
        if self.outcome != GodReceiptOutcome.SUCCESS and not self.failure_reason.strip():
            raise ValueError("failure_reason is required for non-success outcomes")


__all__ = [
    "GodCapabilityState",
    "GodCapabilityBlastRadius",
    "GodTicketState",
    "GodAgreementKind",
    "GodReceiptOutcome",
    "GodCapability",
    "RegistrationAgreement",
    "ActivationAgreement",
    "GodModeTicket",
    "GodModeReceipt",
]
