"""Purpose: canonical secret lifecycle contracts for the MCOI runtime.
Governance scope: secret sourcing, scoping, masking, and persistence protection.
Dependencies: shared contract base helpers.
Invariants:
  - Secret values MUST NOT appear in repr, str, logs, or serialized artifacts.
  - Every secret is bound to a credential scope and optional provider.
  - MaskedValue.reveal() is the only sanctioned access path for the actual value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ._base import ContractRecord, require_datetime_text, require_non_empty_text


class SecretSource(StrEnum):
    """Origin of a secret value."""

    ENVIRONMENT = "environment"
    FILE = "file"
    VAULT = "vault"
    OPERATOR_INPUT = "operator_input"


class SecretStatus(StrEnum):
    """Lifecycle state of a secret."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ROTATION_PENDING = "rotation_pending"


@dataclass(frozen=True, slots=True)
class SecretDescriptor(ContractRecord):
    """Metadata envelope for a registered secret — never carries the value itself.

    Maps a secret_id to its source, scope, provider binding, timestamps, and
    current lifecycle status.
    """

    secret_id: str
    source: SecretSource
    scope_id: str
    created_at: str
    status: SecretStatus = SecretStatus.ACTIVE
    provider_id: str | None = None
    expires_at: str | None = None

    def __post_init__(self) -> None:
        for name in ("secret_id", "scope_id"):
            object.__setattr__(self, name, require_non_empty_text(getattr(self, name), name))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if not isinstance(self.source, SecretSource):
            raise ValueError("source must be a SecretSource value")
        if not isinstance(self.status, SecretStatus):
            raise ValueError("status must be a SecretStatus value")
        if self.provider_id is not None:
            object.__setattr__(
                self, "provider_id", require_non_empty_text(self.provider_id, "provider_id")
            )
        if self.expires_at is not None:
            object.__setattr__(
                self, "expires_at", require_datetime_text(self.expires_at, "expires_at")
            )


@dataclass(frozen=True, slots=True)
class SecretReference(ContractRecord):
    """A safe handle that identifies a secret without carrying its value.

    This is the only secret-related type that may appear in persisted
    artifacts or cross-boundary messages.
    """

    secret_id: str
    scope_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "secret_id", require_non_empty_text(self.secret_id, "secret_id"))
        object.__setattr__(self, "scope_id", require_non_empty_text(self.scope_id, "scope_id"))


_MASKED_DISPLAY = "***MASKED***"


class MaskedValue:
    """A value wrapper that prevents accidental exposure of secret material.

    __repr__ and __str__ always return the masked placeholder.  The actual
    value is accessible only through the explicit reveal() method.

    This class is intentionally *not* a frozen dataclass so that __repr__
    and __str__ can be safely overridden without dataclass machinery
    regenerating them.  The internal value is stored in a name-mangled
    attribute to discourage casual access.
    """

    __slots__ = ("__value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("MaskedValue requires a str value")
        object.__setattr__(self, "_MaskedValue__value", value)

    # -- safe display --------------------------------------------------

    def __repr__(self) -> str:
        return _MASKED_DISPLAY

    def __str__(self) -> str:
        return _MASKED_DISPLAY

    def __format__(self, format_spec: str) -> str:
        return _MASKED_DISPLAY

    # -- immutability --------------------------------------------------

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("MaskedValue is immutable")

    def __delattr__(self, _name: str) -> None:
        raise AttributeError("MaskedValue is immutable")

    # -- sanctioned access ---------------------------------------------

    def reveal(self) -> str:
        """Return the actual secret value.  This is the only sanctioned path."""
        return self.__value  # type: ignore[attr-defined]

    # -- equality (by revealed value) ----------------------------------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MaskedValue):
            return self.reveal() == other.reveal()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.reveal())


@dataclass(frozen=True, slots=True)
class SecretPolicy(ContractRecord):
    """Governance policy applied to secrets within a scope.

    Defaults enforce the strictest posture: never persist, never log,
    always mask in error output.
    """

    policy_id: str
    never_persist: bool = True
    never_log: bool = True
    mask_in_errors: bool = True
    rotation_warning_days: int = 30

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        if not isinstance(self.never_persist, bool):
            raise ValueError("never_persist must be a boolean")
        if not isinstance(self.never_log, bool):
            raise ValueError("never_log must be a boolean")
        if not isinstance(self.mask_in_errors, bool):
            raise ValueError("mask_in_errors must be a boolean")
        if not isinstance(self.rotation_warning_days, int) or self.rotation_warning_days < 0:
            raise ValueError("rotation_warning_days must be a non-negative integer")
