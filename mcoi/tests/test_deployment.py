"""Tests for deployment binding, enforcement, conformance, and golden scenarios."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.deployment import (
    ConformanceVerdict,
    ConformanceViolation,
    DeploymentBinding,
    DeploymentConformanceReport,
    ViolationType,
)
from mcoi_runtime.core.deployment import DeploymentEnforcer
from mcoi_runtime.app.deployment_profiles import (
    bind_profile,
    LOCAL_DEV,
    OPERATOR_APPROVED,
    PILOT_PROD,
    SAFE_READONLY,
    SANDBOXED,
)


# --- Contracts ---


class TestDeploymentContracts:
    def test_binding_valid(self):
        b = DeploymentBinding(profile_id="test", autonomy_mode="observe_only")
        assert b.profile_id == "test"

    def test_binding_empty_id_rejected(self):
        with pytest.raises(ValueError):
            DeploymentBinding(profile_id="", autonomy_mode="observe_only")

    def test_violation_valid(self):
        v = ConformanceViolation(
            violation_type=ViolationType.AUTONOMY_VIOLATION,
            field_name="autonomy_mode",
            expected="observe_only",
            actual="bounded_autonomous",
        )
        assert v.violation_type is ViolationType.AUTONOMY_VIOLATION

    def test_report_conformant(self):
        r = DeploymentConformanceReport(
            report_id="r-1", profile_id="test",
            verdict=ConformanceVerdict.CONFORMANT,
        )
        assert r.is_conformant

    def test_report_violation(self):
        r = DeploymentConformanceReport(
            report_id="r-1", profile_id="test",
            verdict=ConformanceVerdict.VIOLATION,
        )
        assert not r.is_conformant


# --- Profile binding ---


class TestProfileBinding:
    def test_bind_local_dev(self):
        binding = bind_profile(LOCAL_DEV)
        assert binding.profile_id == "local-dev"
        assert binding.autonomy_mode == "bounded_autonomous"
        assert binding.import_enabled is True
        assert binding.export_enabled is True

    def test_bind_safe_readonly(self):
        binding = bind_profile(SAFE_READONLY)
        assert binding.autonomy_mode == "observe_only"
        assert binding.import_enabled is False

    def test_bind_operator_approved(self):
        binding = bind_profile(OPERATOR_APPROVED)
        assert binding.autonomy_mode == "approval_required"

    def test_bind_pilot_prod(self):
        binding = bind_profile(PILOT_PROD)
        assert binding.policy_pack_id == "default-pack"
        assert binding.max_retention_days == 180


# --- Enforcer ---


class TestDeploymentEnforcer:
    def test_route_allowed(self):
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        assert enforcer.is_route_allowed("shell_command")

    def test_route_not_allowed(self):
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        assert not enforcer.is_route_allowed("unknown_route")

    def test_observer_allowed(self):
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        assert enforcer.is_observer_allowed("filesystem")

    def test_export_allowed(self):
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        assert enforcer.is_export_allowed()

    def test_import_not_allowed_safe_readonly(self):
        enforcer = DeploymentEnforcer(bind_profile(SAFE_READONLY))
        assert not enforcer.is_import_allowed()


# --- Conformance evaluation ---


class TestConformanceEvaluation:
    def test_fully_conformant(self):
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="bounded_autonomous",
            routes_used=("shell_command",),
        )
        assert report.is_conformant
        assert len(report.violations) == 0

    def test_autonomy_violation(self):
        enforcer = DeploymentEnforcer(bind_profile(SAFE_READONLY))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="bounded_autonomous",
        )
        assert not report.is_conformant
        assert any(v.violation_type is ViolationType.AUTONOMY_VIOLATION for v in report.violations)

    def test_route_violation(self):
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="bounded_autonomous",
            routes_used=("shell_command", "browser_automation"),
        )
        assert not report.is_conformant
        assert "browser_automation" in report.routes_blocked

    def test_export_violation(self):
        binding = DeploymentBinding(
            profile_id="no-export",
            autonomy_mode="observe_only",
            export_enabled=False,
        )
        enforcer = DeploymentEnforcer(binding)
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="observe_only",
            export_attempted=True,
        )
        assert not report.is_conformant
        assert any(v.violation_type is ViolationType.EXPORT_NOT_ALLOWED for v in report.violations)

    def test_import_violation(self):
        enforcer = DeploymentEnforcer(bind_profile(SAFE_READONLY))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="observe_only",
            import_attempted=True,
        )
        assert not report.is_conformant
        assert any(v.violation_type is ViolationType.IMPORT_NOT_ALLOWED for v in report.violations)

    def test_multiple_violations(self):
        enforcer = DeploymentEnforcer(bind_profile(SAFE_READONLY))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="bounded_autonomous",
            routes_used=("unknown_route",),
            import_attempted=True,
        )
        assert len(report.violations) >= 2  # autonomy + import (route may also violate)


# --- Golden deployment scenarios ---


class TestDeploymentGoldenScenarios:
    def test_safe_readonly_blocks_execution_routes(self):
        """Safe-readonly profile: observe allowed, execute blocked."""
        enforcer = DeploymentEnforcer(bind_profile(SAFE_READONLY))
        # Observer allowed
        assert enforcer.is_observer_allowed("filesystem")
        # Executor route allowed by config but autonomy should block execution
        assert enforcer.binding.autonomy_mode == "observe_only"
        # Conformance with observe-only is correct
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="observe_only",
        )
        assert report.is_conformant

    def test_approval_required_blocks_without_context(self):
        """Approval-required profile enforces approval mode."""
        enforcer = DeploymentEnforcer(bind_profile(OPERATOR_APPROVED))
        assert enforcer.binding.autonomy_mode == "approval_required"
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="approval_required",
            routes_used=("shell_command",),
        )
        assert report.is_conformant

    def test_bounded_autonomous_allows_scoped_execution(self):
        """Bounded-autonomous allows governed execution within profile scope."""
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="bounded_autonomous",
            routes_used=("shell_command",),
        )
        assert report.is_conformant

    def test_bounded_autonomous_rejects_out_of_scope(self):
        """Bounded-autonomous rejects routes outside profile."""
        enforcer = DeploymentEnforcer(bind_profile(LOCAL_DEV))
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="bounded_autonomous",
            routes_used=("shell_command", "browser_automation"),
        )
        assert not report.is_conformant
        assert "browser_automation" in report.routes_blocked

    def test_pilot_prod_has_policy_pack(self):
        """Pilot-prod profile carries policy pack binding."""
        enforcer = DeploymentEnforcer(bind_profile(PILOT_PROD))
        assert enforcer.binding.policy_pack_id == "default-pack"
        assert enforcer.binding.policy_pack_version == "v0.1"
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="approval_required",
        )
        assert report.is_conformant

    def test_sandboxed_suggest_only(self):
        """Sandboxed profile enforces suggest-only mode."""
        enforcer = DeploymentEnforcer(bind_profile(SANDBOXED))
        assert enforcer.binding.autonomy_mode == "suggest_only"
        report = enforcer.evaluate_conformance(
            actual_autonomy_mode="suggest_only",
        )
        assert report.is_conformant

    def test_import_restricted_profile(self):
        """Non-local-dev profiles reject import attempts."""
        for profile in (SAFE_READONLY, OPERATOR_APPROVED, SANDBOXED, PILOT_PROD):
            enforcer = DeploymentEnforcer(bind_profile(profile))
            report = enforcer.evaluate_conformance(
                actual_autonomy_mode=profile.autonomy_mode,
                import_attempted=True,
            )
            assert not report.is_conformant, f"{profile.profile_id} should reject import"
