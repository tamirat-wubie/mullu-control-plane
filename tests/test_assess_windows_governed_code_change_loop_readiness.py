"""Purpose: test Windows readiness assessment for governed code-change loop proof.
Governance scope: Windows prerequisite sensing, explicit blockers, and strict
    evidence command retention.
Dependencies: pytest, subprocess, pathlib, and Windows readiness assessor.
Invariants:
  - The assessor does not claim strict sandbox readiness.
  - Missing Docker or WSL prerequisites produce explicit blockers.
  - The generated next command routes through the WSL strict probe launcher.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PureWindowsPath

from scripts.assess_windows_governed_code_change_loop_readiness import (
    assess_windows_readiness,
    main,
)


def test_assessor_reports_ready_to_collect_when_prerequisites_pass(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        if argv[:2] == ["docker", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Docker version 29.5.2\n", stderr="")
        if argv[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(argv, 0, stdout='["name=rootless"]\n', stderr="")
        if argv[:2] == ["wsl", "--status"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Default Version: 2\n", stderr="")
        if argv[:3] == ["wsl", "-d", "Ubuntu"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Linux host\n", stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Windows",
        build_image=False,
    )

    assert result.ready_to_launch_strict_probe is True
    assert result.status == "ready_to_collect_evidence"
    assert result.solver_outcome == "AwaitingEvidence"
    assert result.blockers == ()
    assert result.docker_cli.status == "passed"
    assert result.docker_daemon.status == "passed"
    assert result.wsl_cli.status == "passed"
    assert result.wsl_distro.status == "passed"
    assert result.strict_probe_argv[:5] == ("wsl", "-d", "Ubuntu", "-u", "root")
    assert "python3 scripts/probe_governed_code_change_loop_sandbox.py" in result.strict_probe_argv[-1]


def test_assessor_reports_missing_docker_and_wsl(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        raise FileNotFoundError(argv[0])

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Windows",
    )

    assert result.ready_to_launch_strict_probe is False
    assert result.status == "blocked"
    assert result.blockers == ("windows_docker_cli_missing", "windows_wsl_cli_missing")
    assert result.docker_cli.status == "missing"
    assert result.docker_daemon.status == "missing"
    assert result.wsl_cli.status == "missing"
    assert result.wsl_distro.status == "missing"
    assert result.next_action == "resolve blockers before running the WSL strict probe"


def test_assessor_keeps_non_windows_host_as_blocked(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Linux",
    )

    assert result.status == "blocked"
    assert result.blockers == ("windows_host_required",)
    assert result.platform_system == "Linux"
    assert result.solver_outcome == "AwaitingEvidence"


def test_assessor_reports_daemon_failure_without_collapsing_cli_status(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        if argv[:2] == ["docker", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Docker version test\n", stderr="")
        if argv[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="daemon unreachable")
        if argv[:2] == ["wsl", "--status"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Default Version: 2\n", stderr="")
        if argv[:3] == ["wsl", "-d", "Ubuntu"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Linux host\n", stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Windows",
    )

    assert result.status == "blocked"
    assert result.blockers == ("windows_docker_daemon_unreachable",)
    assert result.docker_cli.status == "passed"
    assert result.docker_daemon.status == "failed"
    assert result.docker_daemon.stderr_tail == "daemon unreachable"


def test_assessor_reports_unavailable_target_wsl_distro(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        if argv[:2] == ["docker", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Docker version test\n", stderr="")
        if argv[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(argv, 0, stdout='["name=seccomp"]\n', stderr="")
        if argv[:2] == ["wsl", "--status"]:
            return subprocess.CompletedProcess(argv, 0, stdout="Default Version: 2\n", stderr="")
        if argv[:3] == ["wsl", "-d", "Ubuntu"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="distro missing")
        raise AssertionError(f"unexpected argv: {argv}")

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Windows",
    )

    assert result.status == "blocked"
    assert result.blockers == ("windows_wsl_distro_unavailable",)
    assert result.wsl_cli.status == "passed"
    assert result.wsl_distro.status == "failed"
    assert result.wsl_distro.stderr_tail == "distro missing"


def test_assessor_removes_nul_separators_from_wsl_text(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        if argv[:2] == ["wsl", "--status"]:
            return subprocess.CompletedProcess(argv, 0, stdout="D\x00e\x00f\x00a\x00u\x00l\x00t\x00\n\x00", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Windows",
    )

    assert result.status == "ready_to_collect_evidence"
    assert result.wsl_cli.stdout_tail == "Default\n"
    assert "\x00" not in result.wsl_cli.stdout_tail


def test_assessor_timeout_reports_bounded_blocker(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        if argv[:2] == ["docker", "--version"]:
            raise subprocess.TimeoutExpired(argv, timeout=1, output=b"partial", stderr=b"slow")
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    result = assess_windows_readiness(
        workspace_root=Path("ignored"),
        runner=runner,
        platform_system=lambda: "Windows",
    )

    assert result.status == "blocked"
    assert result.blockers == ("windows_docker_cli_timeout",)
    assert result.docker_cli.return_code == 124
    assert result.docker_cli.stdout_tail == "partial"
    assert result.docker_cli.stderr_tail == "slow"


def test_print_command_json_returns_plan(monkeypatch, capsys) -> None:  # noqa: ANN001
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: PureWindowsPath("C:/Users/tmrtl/repo"))

    exit_code = main(["--print-command", "--json", "--skip-build"])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert '"status": "planned"' in streams.out
    assert '"solver_outcome": "AwaitingEvidence"' in streams.out
    assert "wsl" in streams.out
    assert "python3 scripts/probe_governed_code_change_loop_sandbox.py" in streams.out
    assert "docker build -f" not in streams.out
    assert streams.err == ""
