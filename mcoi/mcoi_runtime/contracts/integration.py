"""Purpose: canonical connector descriptor and result contracts for the external integration plane.
Governance scope: integration plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Every connector carries explicit effect/trust classification.
  - Every invocation produces a typed result.
  - Credentials MUST NOT be used outside declared scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class EffectClass(StrEnum):
    """What kind of side effects a connector may produce."""

    INTERNAL_PURE = "internal_pure"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    HUMAN_MEDIATED = "human_mediated"
    PRIVILEGED = "privileged"


class TrustClass(StrEnum):
    """How much the platform trusts the connector's source."""

    TRUSTED_INTERNAL = "trusted_internal"
    BOUNDED_EXTERNAL = "bounded_external"
    UNTRUSTED_EXTERNAL = "untrusted_external"


class ConnectorStatus(StrEnum):
    """Outcome of a connector invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class ConnectorDescriptor(ContractRecord):
    """Describes a registered external system connector.

    Maps to schemas/connector_descriptor.schema.json.
    """

    connector_id: str
    name: str
    provider: str
    effect_class: EffectClass
    trust_class: TrustClass
    credential_scope_id: str
    enabled: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("connector_id", "name", "provider", "credential_scope_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.effect_class, EffectClass):
            raise ValueError("effect_class must be an EffectClass value")
        if not isinstance(self.trust_class, TrustClass):
            raise ValueError("trust_class must be a TrustClass value")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ConnectorResult(ContractRecord):
    """Result of a connector invocation.

    Maps to schemas/connector_result.schema.json.
    """

    result_id: str
    connector_id: str
    status: ConnectorStatus
    response_digest: str
    started_at: str
    finished_at: str
    error_code: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("result_id", "connector_id", "response_digest"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, ConnectorStatus):
            raise ValueError("status must be a ConnectorStatus value")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        if self.error_code is not None:
            object.__setattr__(self, "error_code", require_non_empty_text(self.error_code, "error_code"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
