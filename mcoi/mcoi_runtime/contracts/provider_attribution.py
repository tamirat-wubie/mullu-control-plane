"""Purpose: canonical provider attribution contracts for per-operation plane identity.
Governance scope: provider identity attribution records only.
Dependencies: provider contracts and shared contract validation helpers.
Invariants:
  - Attribution never fabricates a provider outside the provider registry.
  - Each record binds one operation, one provider class, one provider id, one source reference, and one evidence id.
  - Attribution source is explicit so selection, routing, and fallback paths remain distinguishable.
  - Datetime fields are valid ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.contracts.provider import ProviderClass

from ._base import ContractRecord, require_datetime_text, require_non_empty_text


class ProviderAttributionSource(StrEnum):
    """Declared source of a provider attribution decision."""

    HEALTHY_PLANE_RESOLUTION = "healthy_plane_resolution"
    ROUTING_DECISION = "routing_decision"
    EXECUTION_RECEIPT = "execution_receipt"


@dataclass(frozen=True, slots=True)
class ProviderAttribution(ContractRecord):
    """Immutable provider identity attribution for one runtime operation."""

    attribution_id: str
    operation_id: str
    request_id: str
    provider_id: str
    provider_class: ProviderClass
    source: ProviderAttributionSource
    source_ref_id: str
    evidence_id: str
    attributed_at: str
    execution_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "attribution_id",
            "operation_id",
            "request_id",
            "provider_id",
            "source_ref_id",
            "evidence_id",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.execution_id is not None:
            object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.provider_class, ProviderClass):
            raise ValueError("provider_class must be a ProviderClass value")
        if not isinstance(self.source, ProviderAttributionSource):
            raise ValueError("source must be a ProviderAttributionSource value")
        object.__setattr__(self, "attributed_at", require_datetime_text(self.attributed_at, "attributed_at"))
