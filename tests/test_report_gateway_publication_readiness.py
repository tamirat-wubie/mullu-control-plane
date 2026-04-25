"""Tests for gateway publication readiness reporting.

Purpose: verify the publication readiness shortcut derives inputs and reports
GitHub/DNS gates without mutating remote state or reading secret values.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.report_gateway_publication_readiness.
Invariants:
  - Secret checks use repository secret names only.
  - Workflow dispatch is never requested by the reporter.
  - The emitted next command is built from validated publication inputs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.report_gateway_publication_readiness import (
    main,
    report_gateway_publication_readiness,
    write_gateway_publication_readiness,
)


class FakeRunner:
    """Deterministic gh metadata runner fixture."""

    def __init__(
        self,
        *,
        gateway_url: str = "https://gateway.mullusi.com",
        expected_environment: str = "pilot",
        runtime_secret_present: bool = True,
        kubeconfig_secret_present: bool = True,
        workflow_state: str = "active",
    ) -> None:
        self.gateway_url = gateway_url
        self.expected_environment = expected_environment
        self.runtime_secret_present = runtime_secret_present
        self.kubeconfig_secret_present = kubeconfig_secret_present
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
            if self.runtime_secret_present:
                payload.append({"name": "MULLU_RUNTIME_WITNESS_SECRET"})
            if self.kubeconfig_secret_present:
                payload.append({"name": "MULLU_KUBECONFIG_B64"})
            return _completed(command, payload)
        if command[:3] == ["gh", "workflow", "list"]:
            return _completed(
                command,
                [
                    {
                        "name": "Gateway Publication Orchestration",
                        "path": ".github/workflows/gateway-publication.yml",
                        "state": self.workflow_state,
                    }
                ],
            )
        raise AssertionError(f"unexpected command: {command}")


def test_report_derives_host_from_repository_variables_and_writes_command(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()

    report = report_gateway_publication_readiness(
        expected_environment="",
        dispatch_witness=True,
        runner=runner,
        resolver=_resolve_ok,
    )
    output_path = write_gateway_publication_readiness(
        report,
        tmp_path / "gateway_publication_readiness.json",
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert report.ready is True
    assert report.gateway_host == "gateway.mullusi.com"
    assert report.gateway_host_source == "repository-variable"
    assert report.expected_environment == "pilot"
    assert "--gateway-host gateway.mullusi.com" in report.next_command
    assert "--dispatch-witness" in report.next_command
    assert payload["ready"] is True
    assert payload["steps"][0]["name"] == "repository variables"
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_report_requires_kubeconfig_secret_only_when_applying_ingress() -> None:
    runner = FakeRunner(kubeconfig_secret_present=False)

    report = report_gateway_publication_readiness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        apply_ingress=True,
        runner=runner,
        resolver=_resolve_ok,
    )
    kubeconfig_step = _step(report, "kubeconfig secret")

    assert report.ready is False
    assert kubeconfig_step.passed is False
    assert kubeconfig_step.detail == "missing=MULLU_KUBECONFIG_B64"
    assert "--apply-ingress" in report.next_command
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_report_skips_kubeconfig_secret_when_not_applying_ingress() -> None:
    runner = FakeRunner(kubeconfig_secret_present=False)

    report = report_gateway_publication_readiness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=_resolve_ok,
    )
    kubeconfig_step = _step(report, "kubeconfig secret")

    assert report.ready is True
    assert kubeconfig_step.passed is True
    assert kubeconfig_step.detail == "not-required"
    assert "--apply-ingress" not in report.next_command
    assert runner.commands[0][:3] == ["gh", "secret", "list"]


def test_report_rejects_invalid_explicit_host_before_gh_commands() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="must not include URL scheme"):
        report_gateway_publication_readiness(
            gateway_host="https://gateway.mullusi.com",
            expected_environment="pilot",
            runner=runner,
            resolver=_resolve_ok,
        )

    assert runner.commands == []
    assert runner.runtime_secret_present is True
    assert runner.workflow_state == "active"


def test_report_marks_inactive_workflow_not_ready() -> None:
    runner = FakeRunner(workflow_state="disabled_manually")

    report = report_gateway_publication_readiness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        runner=runner,
        resolver=_resolve_ok,
    )
    workflow_step = _step(report, "gateway publication workflow")

    assert report.ready is False
    assert workflow_step.passed is False
    assert workflow_step.detail == "state=disabled_manually"
    assert _step(report, "runtime witness secret").passed is True
    assert _step(report, "dns resolution").passed is True


def test_report_marks_dns_failure_not_ready() -> None:
    runner = FakeRunner()

    report = report_gateway_publication_readiness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        dispatch_witness=True,
        runner=runner,
        resolver=_resolve_failure,
    )
    dns_step = _step(report, "dns resolution")

    assert report.ready is False
    assert dns_step.passed is False
    assert dns_step.detail == "failed:dns unavailable"
    assert "--dispatch-witness" in report.next_command
    assert _step(report, "gateway publication workflow").passed is True


def test_cli_writes_report_and_returns_nonzero_when_gate_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "readiness.json"
    fake_runner = FakeRunner(runtime_secret_present=False)
    monkeypatch.setattr(
        "scripts.report_gateway_publication_readiness.subprocess.run",
        fake_runner,
    )
    monkeypatch.setattr(
        "scripts.report_gateway_publication_readiness._resolve_host",
        _resolve_ok,
    )

    exit_code = main(
        [
            "--gateway-host",
            "gateway.mullusi.com",
            "--expected-environment",
            "pilot",
            "--output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert output_path.exists()
    assert payload["ready"] is False
    assert "ready: false" in captured.out
    assert "missing=MULLU_RUNTIME_WITNESS_SECRET" in captured.out
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in fake_runner.commands)


def _resolve_ok(host: str) -> tuple[str, ...]:
    assert host == "gateway.mullusi.com"
    return ("203.0.113.10",)


def _resolve_failure(host: str) -> tuple[str, ...]:
    assert host == "gateway.mullusi.com"
    raise OSError("dns unavailable")


def _step(report, name: str):
    return next(step for step in report.steps if step.name == name)


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
