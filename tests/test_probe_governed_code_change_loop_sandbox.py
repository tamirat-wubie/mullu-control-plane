"""Purpose: test governed code-change loop sandbox readiness probe.
Governance scope: local sandbox evidence status, host/runtime blockers,
    receipt validation boundary, and strict sandbox execution admission.
Dependencies: probe_governed_code_change_loop_sandbox and subprocess fakes.
Invariants:
  - Windows/non-Linux hosts remain explicit blockers.
  - Docker daemon failures remain explicit blockers.
  - Simulated Linux sandbox success satisfies strict evidence validation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.probe_governed_code_change_loop_sandbox import (
    probe_governed_code_change_loop_sandbox,
)


def test_probe_reports_windows_and_docker_daemon_blockers(tmp_path: Path) -> None:
    output_path = tmp_path / "probe.json"
    receipt_path = tmp_path / "receipt.json"
    workspace = tmp_path / "workspace"

    result = probe_governed_code_change_loop_sandbox(
        output_path=output_path,
        receipt_output_path=receipt_path,
        probe_workspace=workspace,
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout="Python 3.13\n",
            stderr="",
        ),
        platform_system=lambda: "Windows",
        docker_runner=_blocked_docker_runner,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert result.normal_receipt_valid is True
    assert result.strict_sandbox_valid is False
    assert result.docker_cli_status == "available"
    assert result.docker_daemon_status == "unreachable"
    assert "sandbox_runner_linux_only" in result.blockers
    assert "docker_daemon_unreachable" in result.blockers
    assert "governed_code_change_loop_strict_sandbox_invalid" in result.blockers
    assert payload["receipt_is_not_terminal_closure"] is True


def test_probe_passes_with_simulated_linux_sandbox_execution(tmp_path: Path) -> None:
    output_path = tmp_path / "probe.json"
    receipt_path = tmp_path / "receipt.json"
    workspace = tmp_path / "workspace"

    result = probe_governed_code_change_loop_sandbox(
        output_path=output_path,
        receipt_output_path=receipt_path,
        probe_workspace=workspace,
        runner=lambda argv, **kwargs: subprocess.CompletedProcess(
            argv,
            0,
            stdout="Python 3.13\n",
            stderr="",
        ),
        platform_system=lambda: "Linux",
        docker_runner=_reachable_docker_runner,
    )
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert result.blockers == ()
    assert result.normal_receipt_valid is True
    assert result.strict_sandbox_valid is True
    assert result.solver_outcome == "SolvedVerified"
    assert result.closure_allowed is True
    assert receipt_payload["command_result"]["status"] == "succeeded"
    assert receipt_payload["command_result"]["receipt"]["metadata"][
        "sandbox_verification_status"
    ] == "passed"


def _blocked_docker_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
    if argv[:2] == ["docker", "--version"]:
        return subprocess.CompletedProcess(argv, 0, stdout="Docker version test\n", stderr="")
    return subprocess.CompletedProcess(argv, 1, stdout="", stderr="daemon unavailable")


def _reachable_docker_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
    if argv[:2] == ["docker", "--version"]:
        return subprocess.CompletedProcess(argv, 0, stdout="Docker version test\n", stderr="")
    return subprocess.CompletedProcess(argv, 0, stdout='["name=rootless"]\n', stderr="")
