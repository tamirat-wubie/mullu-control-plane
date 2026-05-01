"""Tests for deployment witness preflight readiness.

Purpose: verify the preflight reports DNS, GitHub input, workflow, and endpoint
readiness without mutating deployment state.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.preflight_deployment_witness.
Invariants:
  - Runtime witness and conformance secret values are never read.
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
        workflow_state: str = "active",
    ) -> None:
        self.gateway_url = gateway_url
        self.expected_environment = expected_environment
        self.secret_present = secret_present
        self.conformance_secret_present = conformance_secret_present
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
    assert len(report.steps) == 8
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
    assert len(report.steps) == 5
    assert report.steps[-1].name == "deployment witness workflow"
    assert any(step.name == "runtime witness secret" for step in report.steps)
    assert any(step.name == "runtime conformance secret" for step in report.steps)


def test_preflight_deployment_witness_accepts_mounted_runtime_secret() -> None:
    runner = FakeRunner(secret_present=False)

    report = preflight_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runtime_secret_present=True,
        conformance_secret_present=True,
        probe_endpoints=False,
        runner=runner,
        resolver=lambda host: ("203.0.113.10",),
    )

    secret_step = next(step for step in report.steps if step.name == "runtime witness secret")
    conformance_secret_step = next(step for step in report.steps if step.name == "runtime conformance secret")
    assert report.ready is True
    assert secret_step.passed is True
    assert conformance_secret_step.passed is True
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
    assert len(report.steps) == 6


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
            "authority_responsibility_debt_clear": True,
            "authority_pending_approval_chain_count": 0,
            "authority_overdue_approval_chain_count": 0,
            "authority_open_obligation_count": 0,
            "authority_overdue_obligation_count": 0,
            "authority_escalated_obligation_count": 0,
            "authority_unowned_high_risk_capability_count": 0,
            "authority_directory_sync_receipt_valid": True,
            "terminal_status": "conformant_with_gaps",
            "open_conformance_gaps": ["known_limitations_documentation_drift"],
            "evidence_refs": ["gateway_witness:test"],
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


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
