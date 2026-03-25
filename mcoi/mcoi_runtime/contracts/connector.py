"""Purpose: canonical connector contracts for external system integration.
Governance scope: connector descriptor and connector result typing.
Dependencies: schemas/connector_descriptor.schema.json, schemas/connector_result.schema.json,
    shared contract base helpers, shared enums.
Invariants:
  - Every connector has explicit identity, provider, effect class, and trust class.
  - Connector results carry timing, digest, and status — no silent failures.
  - Effect class and trust class reuse the canonical shared enums.
  - Connectors are explicitly enabled/disabled — never ambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)
from ._shared_enums import EffectClass, TrustClass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConnectorStatus(StrEnum):
    """Outcome status of a connector invocation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


# ---------------------------------------------------------------------------
# Connector descriptor (matches connector_descriptor.schema.json)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConnectorDescriptor(ContractRecord):
    """Describes an external connector with identity, classification, and credential scope.

    Maps 1:1 to schemas/connector_descriptor.schema.json.
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
        object.__setattr__(self, "connector_id", require_non_empty_text(self.connector_id, "connector_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "provider", require_non_empty_text(self.provider, "provider"))
        if not isinstance(self.effect_class, EffectClass):
            raise ValueError("effect_class must be an EffectClass value")
        if not isinstance(self.trust_class, TrustClass):
            raise ValueError("trust_class must be a TrustClass value")
        object.__setattr__(self, "credential_scope_id", require_non_empty_text(self.credential_scope_id, "credential_scope_id"))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Connector result (matches connector_result.schema.json)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConnectorResult(ContractRecord):
    """Outcome of invoking a connector, with timing and response digest.

    Maps 1:1 to schemas/connector_result.schema.json.
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
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "connector_id", require_non_empty_text(self.connector_id, "connector_id"))
        if not isinstance(self.status, ConnectorStatus):
            raise ValueError("status must be a ConnectorStatus value")
        object.__setattr__(self, "response_digest", require_non_empty_text(self.response_digest, "response_digest"))
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        if self.error_code is not None:
            object.__setattr__(self, "error_code", require_non_empty_text(self.error_code, "error_code"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
