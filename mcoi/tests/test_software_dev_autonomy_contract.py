"""F6 — software_dev autonomy contract tests.

Verifies that SoftwareRequest carries the autonomy-loop contract (mode,
quality gates, command policy spec, sandbox profile, evidence requirements,
self-debug budget, rollback flag), that defaults are sane, that new work
kinds round-trip through translate_to_universal, and that the spec converts
into a runtime CommandPolicy without dropping callers' explicit narrowings.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.adapters.code_adapter import CommandPolicy
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareCommandPolicySpec,
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
    SoftwareWorkMode,
    _request_to_ucja_payload,
    materialize_runtime_command_policy,
    translate_to_universal,
)


def _minimal_request(**overrides) -> SoftwareRequest:
    base = dict(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="x",
        repository="r",
    )
    base.update(overrides)
    return SoftwareRequest(**base)


class TestSoftwareRequestDefaults:
    def test_default_mode_is_patch_test_review(self):
        req = _minimal_request()
        assert req.mode is SoftwareWorkMode.PATCH_TEST_REVIEW

    def test_default_quality_gates_include_unit_tests_and_lint(self):
        req = _minimal_request()
        assert SoftwareQualityGate.UNIT_TESTS in req.quality_gates
        assert SoftwareQualityGate.LINT in req.quality_gates

    def test_default_self_debug_budget_is_three(self):
        req = _minimal_request()
        assert req.max_self_debug_iterations == 3

    def test_default_rollback_required_is_true(self):
        req = _minimal_request()
        assert req.rollback_required is True

    def test_default_command_policy_is_strict_spec(self):
        req = _minimal_request()
        spec = req.command_policy
        assert spec.network_allowed is False
        assert spec.sandbox_profile == "none"

    def test_default_sandbox_profile_is_none(self):
        req = _minimal_request()
        assert req.sandbox_profile == "none"

    def test_default_evidence_includes_workspace_patch_test_review(self):
        req = _minimal_request()
        for required in (
            "workspace_snapshot",
            "patch_result",
            "test_result",
            "review_record",
        ):
            assert required in req.evidence_required


class TestNewWorkKinds:
    @pytest.mark.parametrize(
        "kind,expected_verb",
        [
            (SoftwareWorkKind.TEST_GENERATION, "increase_test_coverage"),
            (SoftwareWorkKind.SECURITY_FIX, "remediate_security_finding"),
            (SoftwareWorkKind.DOCS, "update_documentation"),
            (SoftwareWorkKind.MIGRATION, "evolve_data_or_schema_state"),
            (SoftwareWorkKind.DEPENDENCY_UPDATE, "advance_dependency_versions"),
            (SoftwareWorkKind.ROLLBACK, "revert_to_prior_known_good_state"),
        ],
    )
    def test_new_kinds_translate_to_universal(self, kind, expected_verb):
        req = _minimal_request(kind=kind)
        universal = translate_to_universal(req)
        assert universal.purpose_statement.startswith(expected_verb)


class TestUCJAPayload:
    def test_payload_carries_mode_and_gates(self):
        req = _minimal_request(
            mode=SoftwareWorkMode.PATCH_AND_TEST,
            quality_gates=(SoftwareQualityGate.BUILD, SoftwareQualityGate.SECURITY_SCAN),
        )
        payload = _request_to_ucja_payload(req)
        assert payload["mode"] == "patch_and_test"
        assert payload["quality_gates"] == ["build", "security_scan"]

    def test_payload_carries_command_policy_spec(self):
        req = _minimal_request(
            command_policy=SoftwareCommandPolicySpec(
                allowed_executables=("python", "pytest"),
                denied_git_subcommands=("push",),
                max_timeout_seconds=120,
                network_allowed=False,
                sandbox_profile="docker_network_none",
            ),
        )
        payload = _request_to_ucja_payload(req)
        cp = payload["command_policy"]
        assert cp["allowed_executables"] == ["python", "pytest"]
        assert cp["denied_git_subcommands"] == ["push"]
        assert cp["max_timeout_seconds"] == 120
        assert cp["network_allowed"] is False
        assert cp["sandbox_profile"] == "docker_network_none"

    def test_payload_carries_evidence_and_rollback(self):
        req = _minimal_request(
            rollback_required=False,
            evidence_required=("snapshot_only",),
        )
        payload = _request_to_ucja_payload(req)
        assert payload["rollback_required"] is False
        assert payload["evidence_required"] == ["snapshot_only"]


class TestRuntimePolicyMaterialization:
    def test_empty_spec_inherits_adapter_defaults(self):
        spec = SoftwareCommandPolicySpec()
        policy = materialize_runtime_command_policy(spec)
        defaults = CommandPolicy()
        assert policy.allowed_executables == defaults.allowed_executables
        assert policy.denied_executables == defaults.denied_executables
        assert policy.denied_git_subcommands == defaults.denied_git_subcommands

    def test_explicit_allowlist_overrides_defaults(self):
        spec = SoftwareCommandPolicySpec(
            allowed_executables=("python", "pytest"),
        )
        policy = materialize_runtime_command_policy(spec)
        assert policy.allowed_executables == ("python", "pytest")

    def test_explicit_denylist_overrides_defaults(self):
        spec = SoftwareCommandPolicySpec(
            denied_executables=("rm",),
        )
        policy = materialize_runtime_command_policy(spec)
        assert "rm" in policy.denied_executables

    def test_timeout_and_output_caps_propagate(self):
        spec = SoftwareCommandPolicySpec(
            max_timeout_seconds=30,
            max_output_bytes=2048,
        )
        policy = materialize_runtime_command_policy(spec)
        assert policy.max_timeout_seconds == 30
        assert policy.max_output_bytes == 2048
