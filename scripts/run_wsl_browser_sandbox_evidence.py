#!/usr/bin/env python3
"""Run browser sandbox evidence collection through WSL.

Purpose: provide a Windows-side launcher for browser sandbox evidence that
executes the governed producer and validators inside a Linux WSL lane.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: WSL, Python in WSL, Docker or Docker Desktop WSL socket fallback,
and browser sandbox evidence producer/validators.
Invariants:
  - Browser sandbox evidence is produced inside Linux, not Windows.
  - Docker Desktop WSL fallback is explicit and auditable.
  - Failed launches remain blockers and never claim browser readiness.
  - The launcher does not print secret values or raw browser artifacts.
"""

from __future__ import annotations

import argparse
import json
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
    DEFAULT_SANDBOX_IMAGE,
    DEFAULT_USER,
    NATIVE_DOCKER_CLI,
    NATIVE_DOCKER_SHIM,
    NATIVE_DOCKER_SOCKET,
    WORKSPACE_ROOT,
    build_wsl_argv,
    windows_path_to_wsl_path,
)

DEFAULT_EVIDENCE_OUTPUT = ".change_assurance/browser_sandbox_evidence.json"
DEFAULT_PROBE_WORKSPACE = ".tmp/browser_sandbox_workspace"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class WslBrowserSandboxEvidenceResult:
    """Result for one Windows-to-WSL browser sandbox evidence launch."""

    status: str
    distro: str
    user: str
    workspace_wsl_path: str
    return_code: int
    stdout_tail: str
    stderr_tail: str
    blockers: tuple[str, ...]
    evidence_output: str

    @property
    def passed(self) -> bool:
        """Return whether WSL browser sandbox evidence collection passed."""

        return self.status == "passed" and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready output."""

        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def run_wsl_browser_sandbox_evidence(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    distro: str = DEFAULT_DISTRO,
    user: str = DEFAULT_USER,
    sandbox_image: str = DEFAULT_SANDBOX_IMAGE,
    evidence_output: str = DEFAULT_EVIDENCE_OUTPUT,
    probe_workspace: str = DEFAULT_PROBE_WORKSPACE,
    build_image: bool = True,
    use_native_docker_fallback: bool = True,
    runner: CommandRunner = subprocess.run,
    timeout_seconds: int = 180,
) -> WslBrowserSandboxEvidenceResult:
    """Launch browser sandbox evidence collection inside WSL."""

    _require_non_empty_text(distro, "distro")
    if user:
        _require_non_empty_text(user, "user")
    _require_non_empty_text(sandbox_image, "sandbox_image")
    _require_non_empty_text(evidence_output, "evidence_output")
    _require_non_empty_text(probe_workspace, "probe_workspace")
    _require_positive_int(timeout_seconds, "timeout_seconds")
    workspace_wsl_path = windows_path_to_wsl_path(workspace_root)
    bash_command = build_wsl_browser_sandbox_bash_command(
        workspace_wsl_path=workspace_wsl_path,
        sandbox_image=sandbox_image,
        evidence_output=evidence_output,
        probe_workspace=probe_workspace,
        build_image=build_image,
        use_native_docker_fallback=use_native_docker_fallback,
    )
    argv = build_wsl_argv(distro=distro, user=user, bash_command=bash_command)
    try:
        completed = runner(
            argv,
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return _failed_result(
            distro=distro,
            user=user,
            workspace_wsl_path=workspace_wsl_path,
            return_code=127,
            stderr_tail="wsl executable missing",
            blockers=("wsl_cli_missing",),
            evidence_output=evidence_output,
        )
    except subprocess.TimeoutExpired as exc:
        return WslBrowserSandboxEvidenceResult(
            status="failed",
            distro=distro,
            user=user,
            workspace_wsl_path=workspace_wsl_path,
            return_code=124,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or "wsl browser sandbox evidence timed out"),
            blockers=("wsl_browser_sandbox_evidence_timeout",),
            evidence_output=evidence_output,
        )
    except OSError as exc:
        return _failed_result(
            distro=distro,
            user=user,
            workspace_wsl_path=workspace_wsl_path,
            return_code=1,
            stderr_tail=type(exc).__name__,
            blockers=("wsl_browser_sandbox_launch_error",),
            evidence_output=evidence_output,
        )

    blockers = () if completed.returncode == 0 else _blockers_for_completed(completed)
    return WslBrowserSandboxEvidenceResult(
        status="passed" if not blockers else "failed",
        distro=distro,
        user=user,
        workspace_wsl_path=workspace_wsl_path,
        return_code=completed.returncode,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
        blockers=blockers,
        evidence_output=evidence_output,
    )


def build_wsl_browser_sandbox_bash_command(
    *,
    workspace_wsl_path: str,
    sandbox_image: str,
    evidence_output: str,
    probe_workspace: str,
    build_image: bool,
    use_native_docker_fallback: bool,
) -> str:
    """Build the deterministic WSL bash command for browser evidence."""

    _require_non_empty_text(workspace_wsl_path, "workspace_wsl_path")
    _require_non_empty_text(sandbox_image, "sandbox_image")
    _require_non_empty_text(evidence_output, "evidence_output")
    _require_non_empty_text(probe_workspace, "probe_workspace")
    lines = [
        "set -euo pipefail",
        f"cd {_bash_quote(workspace_wsl_path)}",
    ]
    if use_native_docker_fallback:
        lines.extend(
            [
                f"if [ -x {_bash_quote(NATIVE_DOCKER_CLI)} ] && [ -S {_bash_quote(NATIVE_DOCKER_SOCKET)} ]; then",
                "  mkdir -p .tmp/wsl-docker-native-bin",
                "  printf '%s\\n' "
                "'#!/usr/bin/env sh' "
                f"{_bash_quote(f'export DOCKER_HOST=unix://{NATIVE_DOCKER_SOCKET}')} "
                f"{_bash_quote(f'exec {NATIVE_DOCKER_CLI} \"\\$@\"')} "
                f"> {_bash_quote(NATIVE_DOCKER_SHIM)}",
                f"  chmod +x {_bash_quote(NATIVE_DOCKER_SHIM)}",
                '  export PATH="$PWD/.tmp/wsl-docker-native-bin:$PATH"',
                "fi",
            ]
        )
    lines.extend(
        [
            "docker --version",
            "docker info --format '{{json .SecurityOptions}}'",
        ]
    )
    if build_image:
        lines.extend(
            [
                "cat > /tmp/mullu-agent-runner.Dockerfile <<'EOF'",
                "FROM python:3.13-slim",
                'RUN adduser --disabled-password --gecos "" nonroot',
                "USER nonroot",
                "EOF",
                "docker build -f /tmp/mullu-agent-runner.Dockerfile "
                f"-t {_bash_quote(sandbox_image)} /tmp",
            ]
        )
    lines.extend(
        [
            "python3 scripts/produce_browser_sandbox_evidence.py "
            f"--output {_bash_quote(evidence_output)} "
            f"--workspace-root {_bash_quote(probe_workspace)} "
            "--strict --json",
            "python3 scripts/validate_sandbox_execution_receipt.py "
            f"--receipt {_bash_quote(evidence_output)} "
            "--capability-prefix browser. --require-no-workspace-changes --json",
            "python3 scripts/validate_browser_sandbox_evidence.py "
            f"--evidence {_bash_quote(evidence_output)} --json",
        ]
    )
    return "\n".join(lines)


def _failed_result(
    *,
    distro: str,
    user: str,
    workspace_wsl_path: str,
    return_code: int,
    stderr_tail: str,
    blockers: tuple[str, ...],
    evidence_output: str,
) -> WslBrowserSandboxEvidenceResult:
    return WslBrowserSandboxEvidenceResult(
        status="failed",
        distro=distro,
        user=user,
        workspace_wsl_path=workspace_wsl_path,
        return_code=return_code,
        stdout_tail="",
        stderr_tail=stderr_tail,
        blockers=blockers,
        evidence_output=evidence_output,
    )


def _blockers_for_completed(completed: subprocess.CompletedProcess[str]) -> tuple[str, ...]:
    combined_output = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
    if "docker" in combined_output and "could not be found" in combined_output:
        return ("wsl_docker_cli_missing",)
    if "cannot connect to the docker daemon" in combined_output:
        return ("wsl_docker_daemon_unreachable",)
    if "failed to connect to the docker api" in combined_output:
        return ("wsl_docker_daemon_unreachable",)
    if "permission denied" in combined_output and "docker" in combined_output:
        return ("wsl_docker_permission_denied",)
    return ("wsl_browser_sandbox_evidence_failed",)


def _bash_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _require_non_empty_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


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

    parser = argparse.ArgumentParser(description="Run browser sandbox evidence through WSL.")
    parser.add_argument("--workspace-root", type=Path, default=WORKSPACE_ROOT)
    parser.add_argument("--distro", default=DEFAULT_DISTRO)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--sandbox-image", default=DEFAULT_SANDBOX_IMAGE)
    parser.add_argument("--evidence-output", default=DEFAULT_EVIDENCE_OUTPUT)
    parser.add_argument("--probe-workspace", default=DEFAULT_PROBE_WORKSPACE)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--no-native-docker-fallback", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    if args.print_command:
        try:
            bash_command = build_wsl_browser_sandbox_bash_command(
                workspace_wsl_path=windows_path_to_wsl_path(args.workspace_root),
                sandbox_image=str(args.sandbox_image),
                evidence_output=str(args.evidence_output),
                probe_workspace=str(args.probe_workspace),
                build_image=not bool(args.skip_build),
                use_native_docker_fallback=not bool(args.no_native_docker_fallback),
            )
        except ValueError as exc:
            payload = {
                "status": "failed",
                "blockers": ["wsl_workspace_path_invalid"],
                "detail": str(exc),
            }
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else str(exc))
            return 2
        payload = {
            "status": "planned",
            "distro": str(args.distro),
            "user": str(args.user),
            "argv": build_wsl_argv(
                distro=str(args.distro),
                user=str(args.user),
                bash_command=bash_command,
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else bash_command)
        return 0

    try:
        result = run_wsl_browser_sandbox_evidence(
            workspace_root=args.workspace_root,
            distro=str(args.distro),
            user=str(args.user),
            sandbox_image=str(args.sandbox_image),
            evidence_output=str(args.evidence_output),
            probe_workspace=str(args.probe_workspace),
            build_image=not bool(args.skip_build),
            use_native_docker_fallback=not bool(args.no_native_docker_fallback),
            timeout_seconds=int(args.timeout_seconds),
        )
    except ValueError as exc:
        result = _failed_result(
            distro=str(args.distro),
            user=str(args.user),
            workspace_wsl_path="",
            return_code=2,
            stderr_tail=str(exc),
            blockers=("wsl_browser_sandbox_invalid_input",),
            evidence_output=str(args.evidence_output),
        )

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.passed:
        print(f"WSL BROWSER SANDBOX EVIDENCE PASSED distro={result.distro}")
    else:
        print(f"WSL BROWSER SANDBOX EVIDENCE FAILED blockers={list(result.blockers)}")
        if result.stderr_tail:
            print(result.stderr_tail, file=sys.stderr)
    return 0 if result.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
