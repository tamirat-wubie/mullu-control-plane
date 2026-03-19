"""Purpose: canonical deployment binding and conformance contracts.
Governance scope: deployment profile binding, conformance verdict, and violation typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every runtime invocation is governed by an explicit deployment profile.
  - Profile violations are typed and surfaced, never silent.
  - Conformance verdicts are deterministic for identical inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class ConformanceVerdict(StrEnum):
    CONFORMANT = "conformant"
    VIOLATION = "violation"
    PARTIAL = "partial"


class ViolationType(StrEnum):
    AUTONOMY_VIOLATION = "autonomy_violation"
    PROVIDER_NOT_ALLOWED = "provider_not_allowed"
    ROUTE_NOT_ALLOWED = "route_not_allowed"
    IMPORT_NOT_ALLOWED = "import_not_allowed"
    EXPORT_NOT_ALLOWED = "export_not_allowed"
    RETENTION_EXCEEDED = "retention_exceeded"


@dataclass(frozen=True, slots=True)
class DeploymentBinding(ContractRecord):
    """The active deployment profile bound to this runtime session."""

    profile_id: str
    autonomy_mode: str
    policy_pack_id: str | None = None
    policy_pack_version: str | None = None
    allowed_executor_routes: tuple[str, ...] = ()
    allowed_observer_routes: tuple[str, ...] = ()
    export_enabled: bool = True
    import_enabled: bool = False
    max_retention_days: int = 90
    telemetry_enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", require_non_empty_text(self.profile_id, "profile_id"))
        object.__setattr__(self, "autonomy_mode", require_non_empty_text(self.autonomy_mode, "autonomy_mode"))
        object.__setattr__(self, "allowed_executor_routes", freeze_value(list(self.allowed_executor_routes)))
        object.__setattr__(self, "allowed_observer_routes", freeze_value(list(self.allowed_observer_routes)))


@dataclass(frozen=True, slots=True)
class ConformanceViolation(ContractRecord):
    """One detected conformance violation."""

    violation_type: ViolationType
    field_name: str
    expected: str
    actual: str

    def __post_init__(self) -> None:
        if not isinstance(self.violation_type, ViolationType):
            raise ValueError("violation_type must be a ViolationType value")
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))


@dataclass(frozen=True, slots=True)
class DeploymentConformanceReport(ContractRecord):
    """Conformance assessment of a run against its deployment profile."""

    report_id: str
    profile_id: str
    verdict: ConformanceVerdict
    violations: tuple[ConformanceViolation, ...] = ()
    providers_consulted: tuple[str, ...] = ()
    providers_blocked: tuple[str, ...] = ()
    routes_blocked: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "profile_id", require_non_empty_text(self.profile_id, "profile_id"))
        if not isinstance(self.verdict, ConformanceVerdict):
            raise ValueError("verdict must be a ConformanceVerdict value")
        object.__setattr__(self, "violations", freeze_value(list(self.violations)))
        object.__setattr__(self, "providers_consulted", freeze_value(list(self.providers_consulted)))
        object.__setattr__(self, "providers_blocked", freeze_value(list(self.providers_blocked)))
        object.__setattr__(self, "routes_blocked", freeze_value(list(self.routes_blocked)))

    @property
    def is_conformant(self) -> bool:
        return self.verdict is ConformanceVerdict.CONFORMANT
