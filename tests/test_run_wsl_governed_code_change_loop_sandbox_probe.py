"""Purpose: test WSL launcher for strict governed code-change loop sandbox proof.
Governance scope: Windows-to-Linux proof collection, command construction,
    failure blockers, and strict receipt validation command retention.
Dependencies: pytest, pathlib, subprocess, and WSL launcher helpers.
Invariants:
  - The launcher runs the probe inside WSL, not on Windows directly.
  - Docker Desktop native WSL fallback remains explicit and auditable.
  - WSL launch failures produce blockers instead of readiness claims.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PureWindowsPath

from scripts.run_wsl_governed_code_change_loop_sandbox_probe import (
    NATIVE_DOCKER_CLI,
    NATIVE_DOCKER_SOCKET,
    build_wsl_argv,
    build_wsl_probe_bash_command,
    main,
    run_wsl_strict_probe,
    windows_path_to_wsl_path,
)


def test_windows_path_to_wsl_path_translates_drive_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    wsl_path = windows_path_to_wsl_path(Path("ignored"))

    assert wsl_path == "/mnt/c/Users/tmrtl/repo"
    assert wsl_path.startswith("/mnt/c/")
    assert "\\" not in wsl_path


def test_build_wsl_probe_bash_command_keeps_strict_validators() -> None:
    command = build_wsl_probe_bash_command(
        workspace_wsl_path="/mnt/c/Users/tmrtl/repo with space",
        sandbox_image="mullu-agent-runner:latest",
        probe_output=".change_assurance/probe.json",
        receipt_output=".change_assurance/receipt.json",
        probe_workspace=".tmp/probe-workspace",
        build_image=True,
        use_native_docker_fallback=True,
        with_preflight=True,
    )

    assert "cd '/mnt/c/Users/tmrtl/repo with space'" in command
    assert NATIVE_DOCKER_CLI in command
    assert NATIVE_DOCKER_SOCKET in command
    assert f'exec {NATIVE_DOCKER_CLI} "\\$@"' in command
    assert "docker build -f docker/governed-code-change-loop-runner.Dockerfile" in command
    assert "python3 scripts/probe_governed_code_change_loop_sandbox.py" in command
    assert "--strict --json" in command
    assert "--require-strict-sandbox-ready --json" in command
    assert "--require-sandbox-execution --json" in command
    assert "scripts/run_workspace_governance_checks.py --json" in command


def test_build_wsl_probe_bash_command_quotes_single_quote_path() -> None:
    command = build_wsl_probe_bash_command(
        workspace_wsl_path="/mnt/c/Users/tmrtl/repo's path",
        sandbox_image="mullu-agent-runner:latest",
        probe_output=".change_assurance/probe.json",
        receipt_output=".change_assurance/receipt.json",
        probe_workspace=".tmp/probe-workspace",
        build_image=False,
        use_native_docker_fallback=False,
        with_preflight=False,
    )

    assert "cd '/mnt/c/Users/tmrtl/repo'\"'\"'s path'" in command
    assert "python3 scripts/probe_governed_code_change_loop_sandbox.py" in command
    assert "docker build -f" not in command


def test_build_wsl_argv_uses_distro_user_and_bash() -> None:
    argv = build_wsl_argv(distro="Ubuntu", user="root", bash_command="echo ok")

    assert argv[:5] == ["wsl", "-d", "Ubuntu", "-u", "root"]
    assert argv[5:] == ["--", "bash", "-lc", "echo ok"]
    assert "powershell" not in argv


def test_run_wsl_strict_probe_reports_pass(monkeypatch) -> None:  # noqa: ANN001
    observed: dict[str, object] = {}
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout='{"status":"passed"}\n', stderr="")

    result = run_wsl_strict_probe(
        workspace_root=Path("ignored"),
        runner=runner,
        timeout_seconds=30,
        build_image=False,
    )

    assert result.passed is True
    assert result.blockers == ()
    assert result.return_code == 0
    assert result.workspace_wsl_path == "/mnt/c/Users/tmrtl/repo"
    assert result.stdout_tail == '{"status":"passed"}\n'
    assert observed["argv"][:5] == ["wsl", "-d", "Ubuntu", "-u", "root"]
    assert "docker build -f" not in observed["argv"][-1]


def test_run_wsl_strict_probe_reports_missing_wsl(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise FileNotFoundError("wsl")

    result = run_wsl_strict_probe(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.status == "failed"
    assert result.return_code == 127
    assert result.blockers == ("wsl_cli_missing",)
    assert result.stderr_tail == "wsl executable missing"


def test_run_wsl_strict_probe_reports_nonzero_exit(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        return subprocess.CompletedProcess(argv, 9, stdout="", stderr="daemon unavailable")

    result = run_wsl_strict_probe(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.status == "failed"
    assert result.return_code == 9
    assert result.blockers == ("wsl_strict_probe_command_failed",)
    assert result.stderr_tail == "daemon unavailable"


def test_run_wsl_strict_probe_timeout_decodes_bytes(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise subprocess.TimeoutExpired(argv, timeout=1, output=b"partial output", stderr=b"timed out")

    result = run_wsl_strict_probe(workspace_root=Path("ignored"), runner=runner)

    assert result.passed is False
    assert result.return_code == 124
    assert result.stdout_tail == "partial output"
    assert result.stderr_tail == "timed out"
    assert result.blockers == ("wsl_strict_probe_timeout",)


def test_run_wsl_strict_probe_rejects_invalid_timeout(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    try:
        run_wsl_strict_probe(workspace_root=Path("ignored"), timeout_seconds=0)
    except ValueError as exc:
        assert "timeout_seconds must be a positive integer" in str(exc)
    else:  # pragma: no cover - explicit fail path for contract clarity
        raise AssertionError("run_wsl_strict_probe accepted a zero timeout")


def test_print_command_json_reports_plan_without_launch(monkeypatch, capsys) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    exit_code = main(["--print-command", "--json", "--skip-build"])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "planned"' in streams.out
    assert "wsl" in streams.out
    assert "python3 scripts/probe_governed_code_change_loop_sandbox.py" in streams.out
    assert "docker build -f" not in streams.out
    assert streams.err == ""
