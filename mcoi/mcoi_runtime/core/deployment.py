"""Purpose: deployment binding and conformance evaluation.
Governance scope: deployment profile enforcement and conformance checking only.
Dependencies: deployment contracts, deployment profiles, invariant helpers.
Invariants:
  - Profile binding is explicit and immutable for the session.
  - Route and provider checks are deterministic.
  - Conformance is evaluated against the bound profile, not guessed.
"""

from __future__ import annotations

from mcoi_runtime.contracts.deployment import (
    ConformanceVerdict,
    ConformanceViolation,
    DeploymentBinding,
    DeploymentConformanceReport,
    ViolationType,
)
from .invariants import ensure_non_empty_text, stable_identifier


class DeploymentEnforcer:
    """Enforces deployment profile constraints and evaluates conformance."""

    def __init__(self, binding: DeploymentBinding) -> None:
        if not isinstance(binding, DeploymentBinding):
            raise ValueError("binding must be a DeploymentBinding instance")
        self._binding = binding

    @property
    def binding(self) -> DeploymentBinding:
        return self._binding

    def is_route_allowed(self, route: str) -> bool:
        """Check if an executor route is permitted by the deployment profile."""
        return route in self._binding.allowed_executor_routes

    def is_observer_allowed(self, observer_route: str) -> bool:
        """Check if an observer route is permitted."""
        return observer_route in self._binding.allowed_observer_routes

    def is_export_allowed(self) -> bool:
        return self._binding.export_enabled

    def is_import_allowed(self) -> bool:
        return self._binding.import_enabled

    def evaluate_conformance(
        self,
        *,
        actual_autonomy_mode: str,
        routes_used: tuple[str, ...] = (),
        providers_used: tuple[str, ...] = (),
        export_attempted: bool = False,
        import_attempted: bool = False,
    ) -> DeploymentConformanceReport:
        """Evaluate whether a run conformed to the deployment profile."""
        violations: list[ConformanceViolation] = []
        routes_blocked: list[str] = []
        providers_blocked: list[str] = []

        # Autonomy mode check
        if actual_autonomy_mode != self._binding.autonomy_mode:
            violations.append(ConformanceViolation(
                violation_type=ViolationType.AUTONOMY_VIOLATION,
                field_name="autonomy_mode",
                expected=self._binding.autonomy_mode,
                actual=actual_autonomy_mode,
            ))

        # Route checks
        for route in routes_used:
            if not self.is_route_allowed(route):
                violations.append(ConformanceViolation(
                    violation_type=ViolationType.ROUTE_NOT_ALLOWED,
                    field_name="executor_route",
                    expected=f"one of {list(self._binding.allowed_executor_routes)}",
                    actual=route,
                ))
                routes_blocked.append(route)

        # Export/import checks
        if export_attempted and not self._binding.export_enabled:
            violations.append(ConformanceViolation(
                violation_type=ViolationType.EXPORT_NOT_ALLOWED,
                field_name="export_enabled",
                expected="false",
                actual="export_attempted",
            ))

        if import_attempted and not self._binding.import_enabled:
            violations.append(ConformanceViolation(
                violation_type=ViolationType.IMPORT_NOT_ALLOWED,
                field_name="import_enabled",
                expected="false",
                actual="import_attempted",
            ))

        # Determine verdict
        if not violations:
            verdict = ConformanceVerdict.CONFORMANT
        else:
            verdict = ConformanceVerdict.VIOLATION

        report_id = stable_identifier("conformance", {
            "profile_id": self._binding.profile_id,
            "violation_count": len(violations),
        })

        return DeploymentConformanceReport(
            report_id=report_id,
            profile_id=self._binding.profile_id,
            verdict=verdict,
            violations=tuple(violations),
            providers_consulted=tuple(providers_used),
            providers_blocked=tuple(providers_blocked),
            routes_blocked=tuple(routes_blocked),
        )
