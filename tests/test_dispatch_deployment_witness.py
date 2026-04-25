"""Tests for guarded deployment witness workflow dispatch.

Purpose: verify the operator shortcut gates workflow dispatch on declared
runtime inputs and downloads the workflow artifact after completion.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.dispatch_deployment_witness.
Invariants:
  - Missing runtime witness secret prevents workflow dispatch.
  - Missing or inactive workflow prevents workflow dispatch.
  - Successful dispatch returns the completed run and artifact directory.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.dispatch_deployment_witness import dispatch_deployment_witness, main


class FakeRunner:
    """Deterministic gh command runner fixture."""

    def __init__(
        self,
        *,
        secret_present: bool = True,
        workflow_state: str = "active",
        run_conclusion: str = "success",
        variables: dict[str, str] | None = None,
    ) -> None:
        self.secret_present = secret_present
        self.workflow_state = workflow_state
        self.run_conclusion = run_conclusion
        self.variables = variables or {}
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
            payload = [
                {"name": name, "value": value}
                for name, value in sorted(self.variables.items())
            ]
            return _completed(command, payload)
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
        if command[:3] == ["gh", "workflow", "run"]:
            return _completed(command, "")
        if command[:3] == ["gh", "run", "list"]:
            return _completed(
                command,
                [
                    {
                        "databaseId": 1234,
                        "createdAt": "2099-01-01T00:00:00Z",
                        "status": "completed",
                    }
                ],
            )
        if command[:3] == ["gh", "run", "watch"]:
            return _completed(command, "")
        if command[:3] == ["gh", "run", "view"]:
            return _completed(
                command,
                {
                    "databaseId": 1234,
                    "status": "completed",
                    "conclusion": self.run_conclusion,
                    "url": "https://github.com/run/1234",
                },
            )
        if command[:3] == ["gh", "run", "download"]:
            return _completed(command, "")
        raise AssertionError(f"unexpected command: {command}")


def test_dispatch_deployment_witness_runs_workflow_and_downloads_artifact(tmp_path: Path) -> None:
    runner = FakeRunner()

    result = dispatch_deployment_witness(
        gateway_url="https://gateway.example.com/",
        expected_environment="pilot",
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
    )

    assert result.run_id == 1234
    assert result.conclusion == "success"
    assert result.artifact_dir == tmp_path / "artifact"
    assert any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)
    assert any(command[:3] == ["gh", "run", "download"] for command in runner.commands)


def test_dispatch_deployment_witness_uses_repository_variables(tmp_path: Path) -> None:
    runner = FakeRunner(
        variables={
            "MULLU_GATEWAY_URL": "https://gateway.example.com/",
            "MULLU_EXPECTED_RUNTIME_ENV": "production",
        }
    )

    result = dispatch_deployment_witness(
        gateway_url="",
        expected_environment="",
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
    )

    workflow_run_command = next(
        command for command in runner.commands if command[:3] == ["gh", "workflow", "run"]
    )
    assert result.conclusion == "success"
    assert "gateway_url=https://gateway.example.com" in workflow_run_command
    assert "expected_environment=production" in workflow_run_command


def test_dispatch_deployment_witness_fails_before_dispatch_without_secret(tmp_path: Path) -> None:
    runner = FakeRunner(secret_present=False)

    with pytest.raises(RuntimeError, match="missing repository secret"):
        dispatch_deployment_witness(
            gateway_url="https://gateway.example.com",
            expected_environment="pilot",
            download_dir=tmp_path / "artifact",
            runner=runner,
        )

    assert runner.commands[0][:3] == ["gh", "secret", "list"]
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)
    assert not (tmp_path / "artifact").exists()


def test_dispatch_deployment_witness_fails_before_dispatch_when_workflow_inactive(tmp_path: Path) -> None:
    runner = FakeRunner(workflow_state="disabled_manually")

    with pytest.raises(RuntimeError, match="not active"):
        dispatch_deployment_witness(
            gateway_url="https://gateway.example.com",
            expected_environment="production",
            download_dir=tmp_path / "artifact",
            runner=runner,
        )

    assert len(runner.commands) == 2
    assert runner.commands[1][:3] == ["gh", "workflow", "list"]
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_cli_reports_missing_gateway_url(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "scripts.dispatch_deployment_witness.subprocess.run",
        FakeRunner(),
    )

    exit_code = main(["--gateway-url", ""])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "deployment witness dispatch failed" in captured.out
    assert "gateway URL is required" in captured.out


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
