"""Tests for deployment witness preflight readiness.

Purpose: verify the preflight reports DNS, GitHub input, workflow, and endpoint
readiness without mutating deployment state.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.preflight_deployment_witness.
Invariants:
  - Runtime witness, conformance, and deployment witness secret values are
    never read.
  - Workflow dispatch is never executed.
  - Endpoint probes can be skipped for pre-apply readiness checks.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.preflight_deployment_witness import (
    main,
    preflight_deployment_witness,
    write_preflight_report,
)


class FakeRunner:
    """Deterministic GitHub CLI runner fixture."""

    def __init__(
        self,
        *,
        gateway_url: str = "https://gateway.mullusi.com",
        expected_environment: str = "pilot",
        secret_present: bool = True,
        conformance_secret_present: bool = True,
        deployment_witness_secret_present: bool = True,
        workflow_state: str = "active",
    ) -> None:
        self.gateway_url = gateway_url
        self.expected_environment = expected_environment
        self.secret_present = secret_present
        self.conformance_secret_present = conformance_secret_present
        self.deployment_witness_secret_present = deployment_witness_secret_present
        self.workflow_state = workflow_state
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        assert check is True
        assert capture_output is True
        assert text is True

        if command[:3] == ["gh", "variable", "list"]:
            return _completed(
                command,
                [
                    {"name": "MULLU_GATEWAY_URL", "value": self.gateway_url},
                    {
                        "name": "MULLU_EXPECTED_RUNTIME_ENV",
                        "value": self.expected_environment,
                    },
                ],
            )
        if command[:3] == ["gh", "secret", "list"]:
            payload = []
            if self.secret_present:
                payload.append({"name": "MULLU_RUNTIME_WITNESS_SECRET"})
            if self.conformance_secret_present:
                payload.append({"name": "MULLU_RUNTIME_CONFORMANCE_SECRET"})
            if self.deployment_witness_secret_present:
                payload.append({"name": "MULLU_DEPLOYMENT_WITNESS_SECRET"})
            return _completed(command, payload)
        if command[:3] == ["gh", "workflow", "list"]:
            return _completed(
                command,
                [
                    {
                        "name": "Deployment Witness Collection",
                        "path": ".github/workflows/deployment-witness.yml",
                        "state": self.workflow_state,
                    }
                ],
            )
        raise AssertionError(f"unexpected command: {command}")


def test_preflight_deployment_witness_reports_ready(tmp_path: Path) -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_healthy_getter,
    )
    output_path = write_preflight_report(report, tmp_path / "preflight.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert report.ready is True
    assert report.gateway_url == "https://gateway.mullusi.com"
    assert len(report.steps) == 9
    assert all(step.passed for step in report.steps)
    assert payload["ready"] is True
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_preflight_deployment_witness_reports_mismatched_variables() -> None:
    runner = FakeRunner(gateway_url="https://old.mullusi.com")

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_healthy_getter,
    )

    variable_step = next(step for step in report.steps if step.name == "repository variables")
    assert report.ready is False
    assert variable_step.passed is False
    assert "MULLU_GATEWAY_URL" in variable_step.detail


def test_preflight_deployment_witness_can_skip_endpoint_probes() -> None:
    runner = FakeRunner(secret_present=False)

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=lambda url: pytest.fail(f"unexpected endpoint probe: {url}"),
    )

    assert report.ready is False
    assert len(report.steps) == 6
    assert report.steps[-1].name == "deployment witness workflow"
    assert any(step.name == "runtime witness secret" for step in report.steps)
    assert any(step.name == "runtime conformance secret" for step in report.steps)
    assert any(step.name == "deployment witness secret" for step in report.steps)


def test_preflight_deployment_witness_accepts_mounted_runtime_secret() -> None:
    runner = FakeRunner(secret_present=False)

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runtime_secret_present=True,
        conformance_secret_present=True,
        deployment_witness_secret_present=True,
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
    )

    secret_step = next(step for step in report.steps if step.name == "runtime witness secret")
    conformance_secret_step = next(step for step in report.steps if step.name == "runtime conformance secret")
    deployment_secret_step = next(step for step in report.steps if step.name == "deployment witness secret")
    assert report.ready is True
    assert secret_step.passed is True
    assert conformance_secret_step.passed is True
    assert deployment_secret_step.passed is True
    assert secret_step.detail == "present:mounted-environment"
    assert not any(command[:3] == ["gh", "secret", "list"] for command in runner.commands)


def test_preflight_deployment_witness_accepts_valid_mcp_manifest() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        mcp_capability_manifest_path=str(Path("examples") / "mcp_capability_manifest.json"),
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
    )

    manifest_step = next(step for step in report.steps if step.name == "mcp capability manifest")
    assert report.ready is True
    assert manifest_step.passed is True
    assert "valid=True" in manifest_step.detail
    assert "capabilities=1" in manifest_step.detail
    assert "approval_policies=1" in manifest_step.detail
    assert len(report.steps) == 7


def test_preflight_deployment_witness_rejects_invalid_mcp_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "invalid_mcp_manifest.json"
    manifest_path.write_text(json.dumps({"tools": []}), encoding="utf-8")
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        mcp_capability_manifest_path=str(manifest_path),
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
    )

    manifest_step = next(step for step in report.steps if step.name == "mcp capability manifest")
    assert report.ready is False
    assert manifest_step.passed is False
    assert "valid=False" in manifest_step.detail
    assert "MCP manifest requires at least one tool" in manifest_step.detail
    assert manifest_step.detail.endswith("]")


def test_preflight_deployment_witness_reports_missing_conformance_secret() -> None:
    runner = FakeRunner(conformance_secret_present=False)

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
    )

    secret_step = next(step for step in report.steps if step.name == "runtime conformance secret")
    assert report.ready is False
    assert secret_step.passed is False
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET" in secret_step.detail


def test_preflight_deployment_witness_reports_missing_deployment_witness_secret() -> None:
    runner = FakeRunner(deployment_witness_secret_present=False)

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
    )

    secret_step = next(step for step in report.steps if step.name == "deployment witness secret")
    assert report.ready is False
    assert secret_step.passed is False
    assert "MULLU_DEPLOYMENT_WITNESS_SECRET" in secret_step.detail


def test_preflight_deployment_witness_rejects_expired_conformance_certificate() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_expired_conformance_getter,
    )
    conformance_step = next(step for step in report.steps if step.name == "runtime conformance endpoint")

    assert report.ready is False
    assert conformance_step.passed is False
    assert "fresh=False" in conformance_step.detail


def test_preflight_deployment_witness_rejects_responsibility_debt() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_responsibility_debt_getter,
    )
    conformance_step = next(step for step in report.steps if step.name == "runtime conformance endpoint")

    assert report.ready is False
    assert conformance_step.passed is False
    assert "responsibility_debt_clear=False" in conformance_step.detail


def test_preflight_deployment_witness_rejects_runtime_witness_responsibility_debt() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_runtime_witness_responsibility_debt_getter,
    )
    witness_step = next(step for step in report.steps if step.name == "gateway runtime witness endpoint")

    assert report.ready is False
    assert witness_step.passed is False
    assert "responsibility_debt_clear=False" in witness_step.detail


def test_preflight_deployment_witness_rejects_invalid_runtime_mcp_manifest() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_invalid_mcp_manifest_conformance_getter,
    )
    conformance_step = next(step for step in report.steps if step.name == "runtime conformance endpoint")

    assert report.ready is False
    assert conformance_step.passed is False
    assert "mcp_manifest_configured=True" in conformance_step.detail
    assert "mcp_manifest_valid=False" in conformance_step.detail


def test_preflight_deployment_witness_rejects_missing_plan_bundle_witness() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_missing_plan_bundle_conformance_getter,
    )
    conformance_step = next(step for step in report.steps if step.name == "runtime conformance endpoint")

    assert report.ready is False
    assert conformance_step.passed is False
    assert "plan_bundle_passed=False" in conformance_step.detail


def test_preflight_deployment_witness_dns_failure_detail_is_bounded() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: (_ for _ in ()).throw(OSError("dns-secret-token")),
    )
    dns_step = next(step for step in report.steps if step.name == "dns resolution")
    serialized_report = json.dumps(report.to_json_dict(), sort_keys=True)

    assert report.ready is False
    assert dns_step.passed is False
    assert dns_step.detail == "failed:resolution_error"
    assert "dns-secret-token" not in serialized_report


def test_preflight_deployment_witness_endpoint_details_omit_raw_evidence_values() -> None:
    runner = FakeRunner()

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
        json_getter=_private_evidence_getter,
    )
    serialized_report = json.dumps(report.to_json_dict(), sort_keys=True)

    assert report.ready is True
    assert "health-secret" not in serialized_report
    assert "runtime-secret-value" not in serialized_report
    assert "private-conformance-evidence" not in serialized_report
    assert "private-check-detail" not in serialized_report


def test_preflight_deployment_witness_command_failure_is_bounded() -> None:
    def failing_runner(command: list[str], *, check: bool, capture_output: bool, text: bool):
        raise subprocess.CalledProcessError(
            returncode=7,
            cmd=command,
            output="stdout-secret-token",
            stderr="stderr-secret-token",
        )

    with pytest.raises(RuntimeError) as exc_info:
        preflight_deployment_witness(
            gateway_host="gateway.mullusi.com",
            expected_environment="pilot",
            runner=failing_runner,
            resolver=lambda host: ("203.0.113.10",),
        )

    message = str(exc_info.value)
    assert message == "command failed: gh variable list: exit_code=7"
    assert "stdout-secret-token" not in message
    assert "stderr-secret-token" not in message


def test_preflight_deployment_witness_rejects_invalid_host() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="must not include URL scheme"):
        preflight_deployment_witness(
            gateway_host="https://gateway.mullusi.com",
            expected_environment="pilot",
            runner=runner,
        )

    assert runner.commands == []


def test_cli_writes_report_and_returns_not_ready(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "scripts.preflight_deployment_witness.subprocess.run",
        FakeRunner(workflow_state="disabled_manually"),
    )
    monkeypatch.setattr(
        "scripts.preflight_deployment_witness._resolve_host",
        lambda host: ("203.0.113.10",),
    )
    monkeypatch.setattr(
        "scripts.preflight_deployment_witness._get_json",
        _healthy_getter,
    )

    exit_code = main(
        [
            "--gateway-host",
            "gateway.mullusi.com",
            "--output",
            str(tmp_path / "preflight.json"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "ready: false" in captured.out
    assert "disabled_manually" in captured.out
    assert (tmp_path / "preflight.json").exists()


def _healthy_getter(url: str) -> tuple[int, dict[str, Any]]:
    if url.endswith("/health"):
        return 200, {"status": "healthy"}
    if url.endswith("/gateway/witness"):
        return 200, {
            "witness_id": "runtime-witness-1",
            "environment": "pilot",
            "runtime_status": "healthy",
            "gateway_status": "healthy",
            "latest_command_event_hash": "abc123",
            "latest_terminal_certificate_id": "terminal-1",
            "responsibility_debt_clear": True,
            "signed_at": "2026-04-25T00:00:00Z",
            "signature_key_id": "runtime",
            "signature": "hmac-sha256:placeholder",
        }
    if url.endswith("/runtime/conformance"):
        return 200, {
            "certificate_id": "conf-0123456789abcdef",
            "environment": "pilot",
            "issued_at": "2026-04-25T00:00:00+00:00",
            "expires_at": "2099-04-25T00:30:00+00:00",
            "gateway_witness_valid": True,
            "runtime_witness_valid": True,
            "latest_anchor_valid": True,
            "command_closure_canary_passed": True,
            "capability_admission_canary_passed": True,
            "dangerous_capability_isolation_canary_passed": True,
            "streaming_budget_canary_passed": True,
            "lineage_query_canary_passed": True,
            "authority_obligation_canary_passed": True,
            "authority_responsibility_debt_clear": True,
            "authority_pending_approval_chain_count": 0,
            "authority_overdue_approval_chain_count": 0,
            "authority_open_obligation_count": 0,
            "authority_overdue_obligation_count": 0,
            "authority_escalated_obligation_count": 0,
            "authority_unowned_high_risk_capability_count": 0,
            "authority_directory_sync_receipt_valid": True,
            "mcp_capability_manifest_configured": False,
            "mcp_capability_manifest_valid": True,
            "mcp_capability_manifest_capability_count": 0,
            "capability_plan_bundle_canary_passed": True,
            "capability_plan_bundle_count": 0,
            "capsule_registry_certified": True,
            "physical_worker_canary_passed": True,
            "physical_worker_canary_id": "physical-worker-canary-test",
            "physical_worker_canary_artifact_hash": "sha256:" + "a" * 64,
            "physical_worker_canary_evidence_count": 1,
            "proof_coverage_matrix_current": True,
            "proof_coverage_declared_routes_classified": True,
            "proof_coverage_declared_route_count": 301,
            "proof_coverage_unclassified_route_count": 0,
            "known_limitations_aligned": False,
            "security_model_aligned": False,
            "terminal_status": "conformant_with_gaps",
            "open_conformance_gaps": ["known_limitations_documentation_drift"],
            "evidence_refs": ["gateway_witness:test"],
            "checks": [
                {
                    "check_id": "gateway_witness_valid",
                    "passed": True,
                    "evidence_ref": "gateway_witness:test",
                    "detail": "verified",
                }
            ],
            "signature_key_id": "runtime-conformance-test",
            "signature": "hmac-sha256:placeholder",
        }
    raise AssertionError(f"unexpected url: {url}")


def _expired_conformance_getter(url: str) -> tuple[int, dict[str, Any]]:
    status, payload = _healthy_getter(url)
    if url.endswith("/runtime/conformance"):
        return status, {**payload, "expires_at": "2026-04-25T00:30:00+00:00"}
    return status, payload


def _responsibility_debt_getter(url: str) -> tuple[int, dict[str, Any]]:
    status, payload = _healthy_getter(url)
    if url.endswith("/runtime/conformance"):
        return status, {**payload, "authority_responsibility_debt_clear": False}
    return status, payload


def _runtime_witness_responsibility_debt_getter(url: str) -> tuple[int, dict[str, Any]]:
    status, payload = _healthy_getter(url)
    if url.endswith("/gateway/witness"):
        return status, {**payload, "responsibility_debt_clear": False}
    return status, payload


def _invalid_mcp_manifest_conformance_getter(url: str) -> tuple[int, dict[str, Any]]:
    status, payload = _healthy_getter(url)
    if url.endswith("/runtime/conformance"):
        return status, {
            **payload,
            "mcp_capability_manifest_configured": True,
            "mcp_capability_manifest_valid": False,
            "mcp_capability_manifest_capability_count": 1,
        }
    return status, payload


def _missing_plan_bundle_conformance_getter(url: str) -> tuple[int, dict[str, Any]]:
    status, payload = _healthy_getter(url)
    if url.endswith("/runtime/conformance"):
        return status, {**payload, "capability_plan_bundle_canary_passed": False}
    return status, payload


def _private_evidence_getter(url: str) -> tuple[int, dict[str, Any]]:
    status, payload = _healthy_getter(url)
    if url.endswith("/health"):
        return status, {**payload, "internal_secret": "health-secret"}
    if url.endswith("/gateway/witness"):
        return status, {
            **payload,
            "signature": "hmac-sha256:runtime-secret-value",
            "internal_evidence_ref": "proof://private-runtime-evidence",
        }
    if url.endswith("/runtime/conformance"):
        return status, {
            **payload,
            "evidence_refs": ["proof://private-conformance-evidence"],
            "checks": [
                {
                    "check_id": "private_check",
                    "passed": True,
                    "evidence_ref": "proof://private-check-evidence",
                    "detail": "private-check-detail",
                }
            ],
        }
    raise AssertionError(f"unexpected url: {url}")


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
