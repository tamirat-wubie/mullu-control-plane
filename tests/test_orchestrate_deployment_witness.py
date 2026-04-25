"""Tests for governed deployment witness orchestration.

Purpose: verify the operator shortcut composes ingress rendering, repository
variable provisioning, and optional workflow dispatch.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.orchestrate_deployment_witness.
Invariants:
  - Invalid gateway hosts fail before GitHub variables are written.
  - Repository variables use the URL derived from the validated host.
  - Dispatch is opt-in and preserves the existing guarded workflow contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.orchestrate_deployment_witness import (
    main,
    orchestrate_deployment_witness,
)


class FakeRunner:
    """Deterministic kubectl and GitHub CLI runner fixture."""

    def __init__(self, *, run_conclusion: str = "success") -> None:
        self.run_conclusion = run_conclusion
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

        if command[:3] == ["kubectl", "apply", "-f"]:
            return _completed(command, "")
        if command[:3] == ["gh", "variable", "set"]:
            return _completed(command, "")
        if command[:3] == ["gh", "secret", "list"]:
            return _completed(command, [{"name": "MULLU_RUNTIME_WITNESS_SECRET"}])
        if command[:3] == ["gh", "workflow", "list"]:
            return _completed(
                command,
                [
                    {
                        "name": "Deployment Witness Collection",
                        "path": ".github/workflows/deployment-witness.yml",
                        "state": "active",
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
                        "databaseId": 5678,
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
                    "databaseId": 5678,
                    "status": "completed",
                    "conclusion": self.run_conclusion,
                    "url": "https://github.com/run/5678",
                },
            )
        if command[:3] == ["gh", "run", "download"]:
            return _completed(command, "")
        raise AssertionError(f"unexpected command: {command}")


def test_orchestrate_deployment_witness_renders_and_provisions(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        expected_environment="pilot",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        runner=runner,
    )

    variable_commands = [
        command for command in runner.commands if command[:3] == ["gh", "variable", "set"]
    ]
    assert orchestration.ingress.host == "gateway.mullusi.com"
    assert orchestration.ingress.applied is False
    assert orchestration.target.gateway_url == "https://gateway.mullusi.com"
    assert orchestration.target.expected_environment == "pilot"
    assert orchestration.dispatch is None
    assert len(variable_commands) == 2
    assert not any(command[:3] == ["kubectl", "apply", "-f"] for command in runner.commands)
    assert not any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)


def test_orchestrate_deployment_witness_can_apply_and_dispatch(tmp_path: Path) -> None:
    runner = FakeRunner()

    orchestration = orchestrate_deployment_witness(
        gateway_host="gateway.mullusi.com",
        gateway_url="https://gateway.mullusi.com/",
        expected_environment="production",
        rendered_ingress_output=tmp_path / "ingress.yaml",
        apply_ingress=True,
        dispatch=True,
        download_dir=tmp_path / "artifact",
        poll_seconds=1,
        runner=runner,
    )

    assert orchestration.ingress.applied is True
    assert orchestration.target.gateway_url == "https://gateway.mullusi.com"
    assert orchestration.target.expected_environment == "production"
    assert orchestration.dispatch is not None
    assert orchestration.dispatch.run_id == 5678
    assert orchestration.dispatch.conclusion == "success"
    assert any(command[:3] == ["kubectl", "apply", "-f"] for command in runner.commands)
    assert any(command[:3] == ["gh", "workflow", "run"] for command in runner.commands)
    assert any(command[:3] == ["gh", "run", "download"] for command in runner.commands)


def test_orchestrate_deployment_witness_rejects_host_before_provision(tmp_path: Path) -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="must not include URL scheme"):
        orchestrate_deployment_witness(
            gateway_host="https://gateway.mullusi.com",
            expected_environment="pilot",
            rendered_ingress_output=tmp_path / "ingress.yaml",
            runner=runner,
        )

    assert runner.commands == []


def test_cli_reports_invalid_host(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "scripts.orchestrate_deployment_witness.subprocess.run",
        FakeRunner(),
    )

    exit_code = main(
        [
            "--gateway-host",
            "https://gateway.mullusi.com",
            "--rendered-ingress-output",
            str(tmp_path / "ingress.yaml"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "deployment witness orchestration failed" in captured.out
    assert "must not include URL scheme" in captured.out


def _completed(command: list[str], payload: object) -> subprocess.CompletedProcess[str]:
    stdout = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
