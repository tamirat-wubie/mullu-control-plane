"""Purpose: canonical deployment binding and conformance contracts.
Governance scope: deployment profile binding, conformance verdict, and violation typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every runtime invocation is governed by an explicit deployment profile.
  - Profile violations are typed and surfaced, never silent.
  - Conformance verdicts are deterministic for identical inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar, cast

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_negative_int


ContractT = TypeVar("ContractT")


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _freeze_text_array(values: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must contain only non-empty strings")
        normalized.append(value)
    return cast(tuple[str, ...], freeze_value(normalized))


def _freeze_contract_array(
    values: Any,
    field_name: str,
    record_type: type[ContractT],
    record_type_name: str,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[ContractT] = []
    for value in values:
        if not isinstance(value, record_type):
            raise ValueError(f"{field_name} must contain only {record_type_name} instances")
        normalized.append(value)
    return cast(tuple[ContractT, ...], freeze_value(normalized))


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
        if self.policy_pack_id is not None:
            object.__setattr__(
                self,
                "policy_pack_id",
                require_non_empty_text(self.policy_pack_id, "policy_pack_id"),
            )
        if self.policy_pack_version is not None:
            object.__setattr__(
                self,
                "policy_pack_version",
                require_non_empty_text(self.policy_pack_version, "policy_pack_version"),
            )
        object.__setattr__(
            self,
            "allowed_executor_routes",
            _freeze_text_array(self.allowed_executor_routes, "allowed_executor_routes"),
        )
        object.__setattr__(
            self,
            "allowed_observer_routes",
            _freeze_text_array(self.allowed_observer_routes, "allowed_observer_routes"),
        )
        object.__setattr__(self, "export_enabled", _require_bool(self.export_enabled, "export_enabled"))
        object.__setattr__(self, "import_enabled", _require_bool(self.import_enabled, "import_enabled"))
        object.__setattr__(
            self,
            "max_retention_days",
            require_non_negative_int(self.max_retention_days, "max_retention_days"),
        )
        object.__setattr__(
            self,
            "telemetry_enabled",
            _require_bool(self.telemetry_enabled, "telemetry_enabled"),
        )


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
        object.__setattr__(self, "expected", require_non_empty_text(self.expected, "expected"))
        object.__setattr__(self, "actual", require_non_empty_text(self.actual, "actual"))


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
        object.__setattr__(
            self,
            "violations",
            _freeze_contract_array(
                self.violations,
                "violations",
                ConformanceViolation,
                "ConformanceViolation",
            ),
        )
        object.__setattr__(
            self,
            "providers_consulted",
            _freeze_text_array(self.providers_consulted, "providers_consulted"),
        )
        object.__setattr__(
            self,
            "providers_blocked",
            _freeze_text_array(self.providers_blocked, "providers_blocked"),
        )
        object.__setattr__(
            self,
            "routes_blocked",
            _freeze_text_array(self.routes_blocked, "routes_blocked"),
        )

    @property
    def is_conformant(self) -> bool:
        return self.verdict is ConformanceVerdict.CONFORMANT
