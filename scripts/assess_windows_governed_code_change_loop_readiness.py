#!/usr/bin/env python3
"""Assess Windows readiness for governed code-change loop sandbox evidence.

Purpose: give a Windows operator deterministic preflight evidence before
    attempting the Linux strict sandbox probe.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, Docker CLI, optional WSL CLI, and the
    WSL strict probe launcher command builder.
Invariants:
  - This assessor never claims strict sandbox readiness.
  - Local-only Windows mode never probes WSL or Docker.
  - Windows host blockers are explicit and bounded.
  - The strict evidence path remains delegated to the Linux/WSL launcher.
  - Generated commands are argv-only and shell-free at the Windows boundary.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

WORKSPACE_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT_FOR_IMPORT))

from scripts.run_wsl_governed_code_change_loop_sandbox_probe import (  # noqa: E402
    DEFAULT_DISTRO,
    DEFAULT_PROBE_OUTPUT,
    DEFAULT_PROBE_WORKSPACE,
    DEFAULT_RECEIPT_OUTPUT,
    DEFAULT_SANDBOX_IMAGE,
    DEFAULT_USER,
    WORKSPACE_ROOT,
    build_wsl_argv,
    build_wsl_probe_bash_command,
    windows_path_to_wsl_path,
)


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class CommandProbe:
    """Bounded probe result for one local prerequisite command."""

    status: str
    return_code: int | None
    stdout_tail: str
    stderr_tail: str
    blocker: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready output."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class WindowsCodeChangeLoopReadiness:
    """Windows host readiness result for strict evidence collection."""

    status: str
    solver_outcome: str
    platform_system: str
    docker_cli: CommandProbe
    docker_daemon: CommandProbe
    wsl_cli: CommandProbe
    wsl_distro: CommandProbe
    blockers: tuple[str, ...]
    strict_probe_argv: tuple[str, ...]
    next_action: str

    @property
    def ready_to_launch_strict_probe(self) -> bool:
        """Return whether local prerequisites for the WSL strict launcher pass."""

        return not self.blockers and self.status == "ready_to_collect_evidence"

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready output."""

        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["strict_probe_argv"] = list(self.strict_probe_argv)
        payload["docker_cli"] = self.docker_cli.as_dict()
        payload["docker_daemon"] = self.docker_daemon.as_dict()
        payload["wsl_cli"] = self.wsl_cli.as_dict()
        payload["wsl_distro"] = self.wsl_distro.as_dict()
        return payload


def assess_windows_readiness(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    distro: str = DEFAULT_DISTRO,
    user: str = DEFAULT_USER,
    sandbox_image: str = DEFAULT_SANDBOX_IMAGE,
    probe_output: str = DEFAULT_PROBE_OUTPUT,
    receipt_output: str = DEFAULT_RECEIPT_OUTPUT,
    probe_workspace: str = DEFAULT_PROBE_WORKSPACE,
    build_image: bool = True,
    use_native_docker_fallback: bool = True,
    with_preflight: bool = False,
    local_only: bool = False,
    runner: CommandRunner = subprocess.run,
    platform_system: Callable[[], str] | None = None,
    timeout_seconds: int = 20,
) -> WindowsCodeChangeLoopReadiness:
    """Assess Windows host prerequisites without running strict evidence."""

    _require_positive_int(timeout_seconds, "timeout_seconds")
    platform_probe = platform_system or platform.system
    observed_platform = platform_probe()
    blockers: list[str] = []
    if observed_platform.lower() != "windows":
        blockers.append("windows_host_required")

    if local_only:
        skipped_probe = CommandProbe(
            status="skipped",
            return_code=None,
            stdout_tail="",
            stderr_tail="local-only mode does not probe strict sandbox prerequisites",
            blocker=None,
        )
        status = "local_only_ready" if not blockers else "blocked"
        next_action = (
            "run local governance preflight; strict Linux sandbox evidence remains AwaitingEvidence"
            if not blockers
            else "run local-only mode from a Windows host"
        )
        return WindowsCodeChangeLoopReadiness(
            status=status,
            solver_outcome="AwaitingEvidence",
            platform_system=observed_platform,
            docker_cli=skipped_probe,
            docker_daemon=skipped_probe,
            wsl_cli=skipped_probe,
            wsl_distro=skipped_probe,
            blockers=tuple(blockers),
            strict_probe_argv=(),
            next_action=next_action,
        )

    docker_cli = _probe_command(
        ("docker", "--version"),
        missing_blocker="windows_docker_cli_missing",
        failed_blocker="windows_docker_cli_failed",
        timeout_blocker="windows_docker_cli_timeout",
        runner=runner,
        timeout_seconds=timeout_seconds,
    )
    docker_daemon = _probe_command(
        ("docker", "info", "--format", "{{json .SecurityOptions}}"),
        missing_blocker="windows_docker_cli_missing",
        failed_blocker="windows_docker_daemon_unreachable",
        timeout_blocker="windows_docker_daemon_timeout",
        runner=runner,
        timeout_seconds=timeout_seconds,
    )
    wsl_cli = _probe_command(
        ("wsl", "--status"),
        missing_blocker="windows_wsl_cli_missing",
        failed_blocker="windows_wsl_status_failed",
        timeout_blocker="windows_wsl_status_timeout",
        runner=runner,
        timeout_seconds=timeout_seconds,
    )
    wsl_distro = _probe_command(
        ("wsl", "-d", distro, "--", "uname", "-a"),
        missing_blocker="windows_wsl_cli_missing",
        failed_blocker="windows_wsl_distro_unavailable",
        timeout_blocker="windows_wsl_distro_timeout",
        runner=runner,
        timeout_seconds=timeout_seconds,
    )
    for probe in (docker_cli, docker_daemon, wsl_cli, wsl_distro):
        if probe.blocker and probe.blocker not in blockers:
            blockers.append(probe.blocker)

    strict_probe_argv = _strict_probe_argv(
        workspace_root=workspace_root,
        distro=distro,
        user=user,
        sandbox_image=sandbox_image,
        probe_output=probe_output,
        receipt_output=receipt_output,
        probe_workspace=probe_workspace,
        build_image=build_image,
        use_native_docker_fallback=use_native_docker_fallback,
        with_preflight=with_preflight,
    )
    status = "ready_to_collect_evidence" if not blockers else "blocked"
    next_action = (
        "run strict_probe_argv to collect Linux sandbox evidence"
        if not blockers
        else "resolve blockers before running the WSL strict probe"
    )
    return WindowsCodeChangeLoopReadiness(
        status=status,
        solver_outcome="AwaitingEvidence",
        platform_system=observed_platform,
        docker_cli=docker_cli,
        docker_daemon=docker_daemon,
        wsl_cli=wsl_cli,
        wsl_distro=wsl_distro,
        blockers=tuple(blockers),
        strict_probe_argv=tuple(strict_probe_argv),
        next_action=next_action,
    )


def _probe_command(
    argv: tuple[str, ...],
    *,
    missing_blocker: str,
    failed_blocker: str,
    timeout_blocker: str,
    runner: CommandRunner,
    timeout_seconds: int,
) -> CommandProbe:
    try:
        completed = runner(
            list(argv),
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return CommandProbe(
            status="missing",
            return_code=127,
            stdout_tail="",
            stderr_tail=f"{argv[0]} executable missing",
            blocker=missing_blocker,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandProbe(
            status="timeout",
            return_code=124,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or f"{argv[0]} command timed out"),
            blocker=timeout_blocker,
        )
    except OSError as exc:
        return CommandProbe(
            status="failed",
            return_code=1,
            stdout_tail="",
            stderr_tail=type(exc).__name__,
            blocker=failed_blocker,
        )

    return CommandProbe(
        status="passed" if completed.returncode == 0 else "failed",
        return_code=completed.returncode,
        stdout_tail=_tail(completed.stdout or ""),
        stderr_tail=_tail(completed.stderr or ""),
        blocker=None if completed.returncode == 0 else failed_blocker,
    )


def _strict_probe_argv(
    *,
    workspace_root: Path,
    distro: str,
    user: str,
    sandbox_image: str,
    probe_output: str,
    receipt_output: str,
    probe_workspace: str,
    build_image: bool,
    use_native_docker_fallback: bool,
    with_preflight: bool,
) -> list[str]:
    bash_command = build_wsl_probe_bash_command(
        workspace_wsl_path=windows_path_to_wsl_path(workspace_root),
        sandbox_image=sandbox_image,
        probe_output=probe_output,
        receipt_output=receipt_output,
        probe_workspace=probe_workspace,
        build_image=build_image,
        use_native_docker_fallback=use_native_docker_fallback,
        with_preflight=with_preflight,
    )
    return build_wsl_argv(distro=distro, user=user, bash_command=bash_command)


def _require_positive_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _tail(value: object, *, max_chars: int = 4000) -> str:
    text = _ensure_text(value)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _ensure_text(value: object) -> str:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").replace("\x00", "")
    return str(value)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Assess Windows readiness for governed code-change loop strict evidence."
    )
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--distro", default=DEFAULT_DISTRO)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--sandbox-image", default=DEFAULT_SANDBOX_IMAGE)
    parser.add_argument("--probe-output", default=DEFAULT_PROBE_OUTPUT)
    parser.add_argument("--receipt-output", default=DEFAULT_RECEIPT_OUTPUT)
    parser.add_argument("--probe-workspace", default=DEFAULT_PROBE_WORKSPACE)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--no-native-docker-fallback", action="store_true")
    parser.add_argument("--with-preflight", action="store_true")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Skip WSL/Docker strict sandbox probes and emit a Windows-local validation posture.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    if args.print_command:
        if args.local_only:
            payload = {
                "status": "local_only_ready",
                "solver_outcome": "AwaitingEvidence",
                "strict_probe_argv": [],
                "blockers": [],
                "next_action": "run local governance preflight; strict Linux sandbox evidence remains AwaitingEvidence",
            }
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["next_action"])
            return 0
        try:
            strict_probe_argv = _strict_probe_argv(
                workspace_root=args.workspace_root,
                distro=str(args.distro),
                user=str(args.user),
                sandbox_image=str(args.sandbox_image),
                probe_output=str(args.probe_output),
                receipt_output=str(args.receipt_output),
                probe_workspace=str(args.probe_workspace),
                build_image=not bool(args.skip_build),
                use_native_docker_fallback=not bool(args.no_native_docker_fallback),
                with_preflight=bool(args.with_preflight),
            )
        except ValueError as exc:
            payload = {
                "status": "blocked",
                "solver_outcome": "AwaitingEvidence",
                "blockers": ["windows_readiness_assessor_invalid_input"],
                "detail": str(exc),
            }
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(exc))
            return 2
        payload = {
            "status": "planned",
            "solver_outcome": "AwaitingEvidence",
            "strict_probe_argv": list(strict_probe_argv),
            "blockers": [],
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else " ".join(strict_probe_argv))
        return 0

    try:
        result = assess_windows_readiness(
            workspace_root=args.workspace_root,
            distro=str(args.distro),
            user=str(args.user),
            sandbox_image=str(args.sandbox_image),
            probe_output=str(args.probe_output),
            receipt_output=str(args.receipt_output),
            probe_workspace=str(args.probe_workspace),
            build_image=not bool(args.skip_build),
            use_native_docker_fallback=not bool(args.no_native_docker_fallback),
            with_preflight=bool(args.with_preflight),
            local_only=bool(args.local_only),
            timeout_seconds=int(args.timeout_seconds),
        )
    except ValueError as exc:
        payload = {
            "status": "blocked",
            "solver_outcome": "AwaitingEvidence",
            "blockers": ["windows_readiness_assessor_invalid_input"],
            "detail": str(exc),
        }
        if args.json or args.print_command:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"WINDOWS READINESS ASSESSOR BLOCKED: {payload['blockers']}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.ready_to_launch_strict_probe:
        print("WINDOWS GOVERNED CODE-CHANGE LOOP READINESS: ready_to_collect_evidence")
    else:
        print(f"WINDOWS GOVERNED CODE-CHANGE LOOP READINESS BLOCKED blockers={list(result.blockers)}")
    return 0 if result.ready_to_launch_strict_probe or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
