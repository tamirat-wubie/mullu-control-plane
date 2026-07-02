"""Tests for the WSL browser sandbox evidence launcher.

Purpose: prove Windows-to-WSL browser sandbox evidence collection preserves the
strict receipt validators and fails closed on launcher errors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.run_wsl_browser_sandbox_evidence.
Invariants:
  - Evidence production runs inside WSL/Linux.
  - The launcher keeps sandbox receipt and browser evidence validators.
  - Launch failures become explicit blockers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PureWindowsPath

from scripts.run_wsl_browser_sandbox_evidence import (
    build_wsl_browser_sandbox_bash_command,
    main,
    run_wsl_browser_sandbox_evidence,
)
from scripts.run_wsl_governed_code_change_loop_sandbox_probe import (
    NATIVE_DOCKER_CLI,
    NATIVE_DOCKER_SOCKET,
)


def test_build_wsl_browser_sandbox_bash_command_keeps_validators() -> None:
    command = build_wsl_browser_sandbox_bash_command(
        workspace_wsl_path="/mnt/c/Users/tmrtl/repo with space",
        sandbox_image="mullu-agent-runner:latest",
        evidence_output=".change_assurance/browser_sandbox_evidence.json",
        probe_workspace=".tmp/browser_sandbox_workspace",
        build_image=True,
        use_native_docker_fallback=True,
    )

    assert "cd '/mnt/c/Users/tmrtl/repo with space'" in command
    assert NATIVE_DOCKER_CLI in command
    assert NATIVE_DOCKER_SOCKET in command
    assert "docker info --format '{{json .SecurityOptions}}'" in command
    assert "docker build -f /tmp/mullu-agent-runner.Dockerfile" in command
    assert "python3 scripts/produce_browser_sandbox_evidence.py" in command
    assert "--workspace-root '.tmp/browser_sandbox_workspace'" in command
    assert "python3 scripts/validate_sandbox_execution_receipt.py" in command
    assert "--capability-prefix browser. --require-no-workspace-changes --json" in command
    assert "python3 scripts/validate_browser_sandbox_evidence.py" in command


def test_build_wsl_browser_sandbox_bash_command_quotes_single_quote_path() -> None:
    command = build_wsl_browser_sandbox_bash_command(
        workspace_wsl_path="/mnt/c/Users/tmrtl/repo's path",
        sandbox_image="mullu-agent-runner:latest",
        evidence_output=".change_assurance/browser_sandbox_evidence.json",
        probe_workspace=".tmp/browser_sandbox_workspace",
        build_image=False,
        use_native_docker_fallback=False,
    )

    assert "cd '/mnt/c/Users/tmrtl/repo'\"'\"'s path'" in command
    assert "python3 scripts/produce_browser_sandbox_evidence.py" in command
    assert "docker build -f" not in command


def test_run_wsl_browser_sandbox_evidence_reports_pass(monkeypatch) -> None:  # noqa: ANN001
    observed: dict[str, object] = {}
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout='{"valid":true}\n', stderr="")

    result = run_wsl_browser_sandbox_evidence(
        workspace_root=Path("ignored"),
        runner=runner,
        timeout_seconds=30,
        build_image=False,
    )

    assert result.passed is True
    assert result.blockers == ()
    assert result.return_code == 0
    assert result.workspace_wsl_path == "/mnt/c/Users/tmrtl/repo"
    assert result.stdout_tail == '{"valid":true}\n'
    assert observed["argv"][:5] == ["wsl", "-d", "Ubuntu", "-u", "root"]
    assert "produce_browser_sandbox_evidence.py" in observed["argv"][-1]
    assert "docker build -f" not in observed["argv"][-1]


def test_run_wsl_browser_sandbox_evidence_reports_missing_wsl(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise FileNotFoundError("wsl")

    result = run_wsl_browser_sandbox_evidence(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.status == "failed"
    assert result.return_code == 127
    assert result.blockers == ("wsl_cli_missing",)
    assert result.stderr_tail == "wsl executable missing"


def test_run_wsl_browser_sandbox_evidence_reports_nonzero_exit(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(argv, 9, stdout="", stderr="daemon unavailable")

    result = run_wsl_browser_sandbox_evidence(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.status == "failed"
    assert result.return_code == 9
    assert result.blockers == ("wsl_browser_sandbox_evidence_failed",)
    assert result.stderr_tail == "daemon unavailable"


def test_run_wsl_browser_sandbox_evidence_classifies_missing_docker(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout="The command 'docker' could not be found in this WSL 2 distro.",
            stderr="",
        )

    result = run_wsl_browser_sandbox_evidence(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.status == "failed"
    assert result.return_code == 1
    assert result.blockers == ("wsl_docker_cli_missing",)
    assert "docker" in result.stdout_tail


def test_run_wsl_browser_sandbox_evidence_timeout_decodes_bytes(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise subprocess.TimeoutExpired(argv, timeout=1, output=b"partial output", stderr=b"timed out")

    result = run_wsl_browser_sandbox_evidence(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.return_code == 124
    assert result.stdout_tail == "partial output"
    assert result.stderr_tail == "timed out"
    assert result.blockers == ("wsl_browser_sandbox_evidence_timeout",)


def test_print_command_json_reports_plan_without_launch(monkeypatch, capsys) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    exit_code = main(["--print-command", "--json", "--skip-build"])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "planned"' in streams.out
    assert "wsl" in streams.out
    assert "python3 scripts/produce_browser_sandbox_evidence.py" in streams.out
    assert "docker build -f" not in streams.out
    assert streams.err == ""
