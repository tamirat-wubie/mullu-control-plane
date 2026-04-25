"""Tests for deployment witness preflight readiness.

Purpose: verify the preflight reports DNS, GitHub input, workflow, and endpoint
readiness without mutating deployment state.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.preflight_deployment_witness.
Invariants:
  - The runtime witness secret value is never read.
  - Workflow dispatch is never executed.
  - Endpoint probes can be skipped for pre-apply readiness checks.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
        workflow_state: str = "active",
    ) -> None:
        self.gateway_url = gateway_url
        self.expected_environment = expected_environment
        self.secret_present = secret_present
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
            payload = [{"name": "MULLU_RUNTIME_WITNESS_SECRET"}] if self.secret_present else []
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
    assert len(report.steps) == 6
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
    assert len(report.steps) == 4
    assert report.steps[-1].name == "deployment witness workflow"
    assert any(step.name == "runtime witness secret" for step in report.steps)


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


def _healthy_getter(url: str) -> tuple[int, dict[str, str]]:
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
    raise AssertionError(f"unexpected url: {url}")


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
