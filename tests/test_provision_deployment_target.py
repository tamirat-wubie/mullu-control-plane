"""Tests for deployment witness target provisioning.

Purpose: verify repository variable binding for gateway deployment targets.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.provision_deployment_target.
Invariants:
  - Gateway URL must be explicit and scheme-qualified.
  - Expected environment is bounded to pilot or production.
  - Repository variables are set only after validation passes.
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.provision_deployment_target import main, provision_deployment_target


class FakeRunner:
    """Deterministic gh variable set runner fixture."""

    def __init__(self) -> None:
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
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def test_provision_deployment_target_sets_repository_variables() -> None:
    runner = FakeRunner()

    target = provision_deployment_target(
        gateway_url="https://gateway.example.com/",
        expected_environment="pilot",
        runner=runner,
    )

    assert target.gateway_url == "https://gateway.example.com"
    assert target.expected_environment == "pilot"
    assert len(runner.commands) == 2
    assert runner.commands[0] == [
        "gh",
        "variable",
        "set",
        "MULLU_GATEWAY_URL",
        "--repo",
        "tamirat-wubie/mullu-control-plane",
        "--body",
        "https://gateway.example.com",
    ]
    assert runner.commands[1][-1] == "pilot"


def test_provision_deployment_target_rejects_missing_url() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="gateway URL is required"):
        provision_deployment_target(
            gateway_url="",
            expected_environment="pilot",
            runner=runner,
        )

    assert runner.commands == []


def test_provision_deployment_target_rejects_invalid_environment() -> None:
    runner = FakeRunner()

    with pytest.raises(RuntimeError, match="expected environment"):
        provision_deployment_target(
            gateway_url="https://gateway.example.com",
            expected_environment="staging",
            runner=runner,
        )

    assert runner.commands == []


def test_cli_reports_invalid_url(capsys) -> None:
    exit_code = main(["--gateway-url", "gateway.example.com"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "deployment target provisioning failed" in captured.out
    assert "must start with" in captured.out
