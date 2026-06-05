"""Purpose: declarative monitor for protected runtime invariants.

Governance scope: detection and reporting of attempts to weaken a
protected variable. This module observes a proposed before→after change
and reports violations; it never mutates and never commits — matching
the platform's "everything proposes, only Φ_gov commits" principle and
the reflex "proposals only until a gate passes" pattern.

Today the same idea is still partly reimplemented ad hoc across the
codebase: `mcoi_runtime/app/profiles.py` now adopts this monitor for the
`effect_assurance_required` floor, while the always-forced
`PROTECTED_FORBIDDEN_CAPABILITIES` floor in
`mcoi_runtime/assistant_kernel/identity.py`, the `protected_surface`
flag in the reflex contracts, and the protected-checkpoint guards can
still migrate onto a declarative registry and structured, auditable
verdict. This module is the seam those sites *can* adopt — introduced
the same way `ReceiptStore` was (a contract + default, no forced
rewiring of existing callers).

Dependencies: contract base helpers only (pure data + stdlib).
Invariants:
  - check() is pure: no mutation of inputs, deterministic output.
  - Only registered variables are inspected; unrelated keys are ignored.
  - Outputs are frozen and JSON-serializable (ContractRecord).
  - A missing key in `after` cannot violate a rule, except IMMUTABLE,
    for which removing a previously-present protected variable IS a
    violation (silent deletion is a classic protection bypass).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from mcoi_runtime.contracts._base import ContractRecord, require_non_empty_text

_ABSENT = object()


class ProtectionRule(StrEnum):
    """How a protected variable is allowed to change."""

    MUST_REMAIN_TRUE = "must_remain_true"
    MUST_REMAIN_FALSE = "must_remain_false"
    IMMUTABLE = "immutable"
    MONOTONIC_NONDECREASING = "monotonic_nondecreasing"
    MONOTONIC_NONINCREASING = "monotonic_nonincreasing"
    FORBIDDEN_VALUES = "forbidden_values"
    ALLOWED_VALUES = "allowed_values"
    REQUIRED_SUPERSET = "required_superset"


@dataclass(frozen=True, slots=True)
class ProtectedVariable(ContractRecord):
    """One declared protection over a named variable.

    `forbidden_values` / `allowed_values` / `required_members` are only
    meaningful for their corresponding rule and are otherwise ignored.
    """

    name: str
    rule: ProtectionRule
    forbidden_values: tuple[Any, ...] = ()
    allowed_values: tuple[Any, ...] = ()
    required_members: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.rule, ProtectionRule):
            raise ValueError("rule must be a ProtectionRule")
        object.__setattr__(self, "forbidden_values", tuple(self.forbidden_values))
        object.__setattr__(self, "allowed_values", tuple(self.allowed_values))
        object.__setattr__(self, "required_members", tuple(self.required_members))
        if self.rule is ProtectionRule.ALLOWED_VALUES and not self.allowed_values:
            raise ValueError("ALLOWED_VALUES rule requires allowed_values")
        if self.rule is ProtectionRule.FORBIDDEN_VALUES and not self.forbidden_values:
            raise ValueError("FORBIDDEN_VALUES rule requires forbidden_values")
        if self.rule is ProtectionRule.REQUIRED_SUPERSET and not self.required_members:
            raise ValueError("REQUIRED_SUPERSET rule requires required_members")


@dataclass(frozen=True, slots=True)
class ProtectedVariableViolation(ContractRecord):
    """A single detected attempt to weaken a protected variable."""

    name: str
    rule: ProtectionRule
    before: str
    after: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProtectionReport(ContractRecord):
    """Result of checking a proposed change. `ok` iff no violations."""

    violations: tuple[ProtectedVariableViolation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violations", tuple(self.violations))

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def violated_names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.violations)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class ProtectedVariableMonitor:
    """Declarative registry + observe-only checker for protected vars.

    Register the invariants once, then call `check(before, after)` with
    the current and proposed state mappings (config dicts, capability
    sets, policy snapshots, ...). Returns a frozen, serializable report.
    """

    def __init__(self) -> None:
        self._vars: dict[str, ProtectedVariable] = {}

    def register(self, variable: ProtectedVariable) -> None:
        if not isinstance(variable, ProtectedVariable):
            raise ValueError("variable must be a ProtectedVariable")
        if variable.name in self._vars:
            raise ValueError(f"protected variable already registered: {variable.name}")
        self._vars[variable.name] = variable

    def register_many(self, variables: tuple[ProtectedVariable, ...]) -> None:
        for variable in variables:
            self.register(variable)

    @property
    def variables(self) -> tuple[ProtectedVariable, ...]:
        return tuple(self._vars.values())

    def check(
        self,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
    ) -> ProtectionReport:
        violations: list[ProtectedVariableViolation] = []
        for name, var in self._vars.items():
            old = before.get(name, _ABSENT)
            new = after.get(name, _ABSENT)
            reason = self._violation_reason(var, old, new)
            if reason is not None:
                violations.append(
                    ProtectedVariableViolation(
                        name=name,
                        rule=var.rule,
                        before="<absent>" if old is _ABSENT else str(old),
                        after="<absent>" if new is _ABSENT else str(new),
                        reason=reason,
                    )
                )
        return ProtectionReport(violations=tuple(violations))

    @staticmethod
    def _violation_reason(
        var: ProtectedVariable, old: Any, new: Any
    ) -> str | None:
        rule = var.rule

        if rule is ProtectionRule.IMMUTABLE:
            if old is _ABSENT:
                return None  # nothing protected yet
            if new is _ABSENT:
                return "protected variable was removed"
            if new != old:
                return "protected variable is immutable once set"
            return None

        if new is _ABSENT:
            # Not being set in the proposed state — nothing to weaken.
            return None

        if rule is ProtectionRule.MUST_REMAIN_TRUE:
            return None if new is True else "must remain True"

        if rule is ProtectionRule.MUST_REMAIN_FALSE:
            return None if new is False else "must remain False"

        if rule is ProtectionRule.MONOTONIC_NONDECREASING:
            if old is _ABSENT or not (_is_number(old) and _is_number(new)):
                return None
            return None if new >= old else "must not decrease"

        if rule is ProtectionRule.MONOTONIC_NONINCREASING:
            if old is _ABSENT or not (_is_number(old) and _is_number(new)):
                return None
            return None if new <= old else "must not increase"

        if rule is ProtectionRule.FORBIDDEN_VALUES:
            return (
                "value is forbidden"
                if new in var.forbidden_values
                else None
            )

        if rule is ProtectionRule.ALLOWED_VALUES:
            return (
                None
                if new in var.allowed_values
                else "value outside the allowed set"
            )

        if rule is ProtectionRule.REQUIRED_SUPERSET:
            try:
                members = set(new)
            except TypeError:
                return "value is not a collection; required members cannot be guaranteed"
            missing = [m for m in var.required_members if m not in members]
            return (
                f"missing required protected members: {sorted(map(str, missing))}"
                if missing
                else None
            )

        return None
