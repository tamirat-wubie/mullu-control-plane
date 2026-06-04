#!/usr/bin/env python3
"""Run the governed code-change loop strict sandbox probe through WSL.

Purpose: provide a repeatable Windows-side launcher for collecting strict
    Linux sandbox evidence without requiring a separate Linux workstation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: WSL, Ubuntu by default, Python in WSL, Docker Desktop WSL socket
    fallback, governed code-change loop probe and validators.
Invariants:
  - Strict sandbox execution is still collected inside Linux.
  - Docker Desktop WSL bind-mount translation remains delegated to the sandbox runner.
  - Launcher failures are explicit blockers, never silent readiness claims.
  - Probe receipts remain non-terminal closure evidence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DISTRO = "Ubuntu"
DEFAULT_USER = "root"
DEFAULT_SANDBOX_IMAGE = "mullu-agent-runner:latest"
DEFAULT_PROBE_OUTPUT = ".change_assurance/governed_code_change_loop_sandbox_probe.json"
DEFAULT_RECEIPT_OUTPUT = ".change_assurance/governed_code_change_loop_probe_receipt.json"
DEFAULT_PROBE_WORKSPACE = ".tmp/governed-code-change-loop-probe-workspace"
NATIVE_DOCKER_CLI = "/mnt/wsl/docker-desktop/cli-tools/usr/bin/docker"
NATIVE_DOCKER_SOCKET = "/mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock"
NATIVE_DOCKER_SHIM = ".tmp/wsl-docker-native-bin/docker"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class WslStrictProbeLaunchResult:
    """Result for a Windows-to-WSL strict sandbox probe launch."""

    status: str
    distro: str
    user: str
    workspace_wsl_path: str
    return_code: int
    stdout_tail: str
    stderr_tail: str
    blockers: tuple[str, ...]
    probe_output: str
    receipt_output: str

    @property
    def passed(self) -> bool:
        """Return whether the WSL launcher completed strict evidence collection."""

        return self.status == "passed" and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready output."""

        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def run_wsl_strict_probe(
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
    runner: CommandRunner = subprocess.run,
    timeout_seconds: int = 180,
) -> WslStrictProbeLaunchResult:
    """Launch strict sandbox evidence collection inside WSL."""

    _require_non_empty_text(distro, "distro")
    if user:
        _require_non_empty_text(user, "user")
    _require_non_empty_text(sandbox_image, "sandbox_image")
    _require_positive_int(timeout_seconds, "timeout_seconds")
    workspace_wsl_path = windows_path_to_wsl_path(workspace_root)
    bash_command = build_wsl_probe_bash_command(
        workspace_wsl_path=workspace_wsl_path,
        sandbox_image=sandbox_image,
        probe_output=probe_output,
        receipt_output=receipt_output,
        probe_workspace=probe_workspace,
        build_image=build_image,
        use_native_docker_fallback=use_native_docker_fallback,
        with_preflight=with_preflight,
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
        return WslStrictProbeLaunchResult(
            status="failed",
            distro=distro,
            user=user,
            workspace_wsl_path=workspace_wsl_path,
            return_code=127,
            stdout_tail="",
            stderr_tail="wsl executable missing",
            blockers=("wsl_cli_missing",),
            probe_output=probe_output,
            receipt_output=receipt_output,
        )
    except subprocess.TimeoutExpired as exc:
        return WslStrictProbeLaunchResult(
            status="failed",
            distro=distro,
            user=user,
            workspace_wsl_path=workspace_wsl_path,
            return_code=124,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or "wsl strict probe timed out"),
            blockers=("wsl_strict_probe_timeout",),
            probe_output=probe_output,
            receipt_output=receipt_output,
        )
    except OSError as exc:
        return WslStrictProbeLaunchResult(
            status="failed",
            distro=distro,
            user=user,
            workspace_wsl_path=workspace_wsl_path,
            return_code=1,
            stdout_tail="",
            stderr_tail=type(exc).__name__,
            blockers=("wsl_launch_error",),
            probe_output=probe_output,
            receipt_output=receipt_output,
        )

    blockers = () if completed.returncode == 0 else ("wsl_strict_probe_command_failed",)
    return WslStrictProbeLaunchResult(
        status="passed" if not blockers else "failed",
        distro=distro,
        user=user,
        workspace_wsl_path=workspace_wsl_path,
        return_code=completed.returncode,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
        blockers=blockers,
        probe_output=probe_output,
        receipt_output=receipt_output,
    )


def build_wsl_argv(*, distro: str, user: str, bash_command: str) -> list[str]:
    """Build the argv used to launch bash inside the target WSL distro."""

    _require_non_empty_text(distro, "distro")
    _require_non_empty_text(bash_command, "bash_command")
    argv = ["wsl", "-d", distro]
    if user:
        _require_non_empty_text(user, "user")
        argv.extend(["-u", user])
    argv.extend(["--", "bash", "-lc", bash_command])
    return argv


def build_wsl_probe_bash_command(
    *,
    workspace_wsl_path: str,
    sandbox_image: str,
    probe_output: str,
    receipt_output: str,
    probe_workspace: str,
    build_image: bool,
    use_native_docker_fallback: bool,
    with_preflight: bool,
) -> str:
    """Build the deterministic WSL bash command for strict evidence collection."""

    _require_non_empty_text(workspace_wsl_path, "workspace_wsl_path")
    _require_non_empty_text(sandbox_image, "sandbox_image")
    _require_non_empty_text(probe_output, "probe_output")
    _require_non_empty_text(receipt_output, "receipt_output")
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
                # Keep the dollar escaped in the WSL bash payload. Without
                # this, the Windows-to-WSL command boundary can expand "$@"
                # while generating the shim and leave a broken `docker ""`.
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
        lines.append(
            "docker build -f docker/governed-code-change-loop-runner.Dockerfile "
            f"-t {_bash_quote(sandbox_image)} docker"
        )
    lines.extend(
        [
            "python3 scripts/probe_governed_code_change_loop_sandbox.py "
            f"--output {_bash_quote(probe_output)} "
            f"--receipt-output {_bash_quote(receipt_output)} "
            f"--probe-workspace {_bash_quote(probe_workspace)} "
            f"--sandbox-image {_bash_quote(sandbox_image)} "
            "--strict --json",
            "python3 scripts/validate_governed_code_change_loop_sandbox_probe.py "
            f"--probe {_bash_quote(probe_output)} "
            "--require-strict-sandbox-ready --json",
            "python3 scripts/validate_governed_code_change_loop_receipt.py "
            f"--receipt {_bash_quote(receipt_output)} "
            "--require-sandbox-execution --json",
        ]
    )
    if with_preflight:
        lines.extend(
            [
                "python3 scripts/run_workspace_governance_checks.py "
                "--json --receipt-path .tmp/workspace-governance-preflight-receipt.json",
                "python3 scripts/validate_workspace_governance_preflight_receipt.py "
                "--receipt .tmp/workspace-governance-preflight-receipt.json",
            ]
        )
    return "\n".join(lines)


def windows_path_to_wsl_path(path: Path) -> str:
    """Translate a Windows absolute path to the WSL `/mnt/<drive>` form."""

    path_text = str(path.resolve(strict=False))
    if path_text.startswith("/"):
        return path_text
    if len(path_text) >= 3 and path_text[1:3] == ":\\":
        drive = path_text[0].lower()
        remainder = path_text[3:].replace("\\", "/")
        return f"/mnt/{drive}/{remainder}"
    raise ValueError(f"cannot translate path to WSL form: {path_text}")


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


def _tail(value: str, *, max_chars: int = 4000) -> str:
    text = _ensure_text(value)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _ensure_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run governed code-change loop strict sandbox evidence through WSL."
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
            bash_command = build_wsl_probe_bash_command(
                workspace_wsl_path=windows_path_to_wsl_path(args.workspace_root),
                sandbox_image=str(args.sandbox_image),
                probe_output=str(args.probe_output),
                receipt_output=str(args.receipt_output),
                probe_workspace=str(args.probe_workspace),
                build_image=not bool(args.skip_build),
                use_native_docker_fallback=not bool(args.no_native_docker_fallback),
                with_preflight=bool(args.with_preflight),
            )
        except ValueError as exc:
            if args.json:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "blockers": ["wsl_workspace_path_invalid"],
                            "detail": str(exc),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(str(exc), file=sys.stderr)
            return 2
        if args.json:
            print(
                json.dumps(
                    {
                        "status": "planned",
                        "distro": str(args.distro),
                        "user": str(args.user),
                        "argv": build_wsl_argv(
                            distro=str(args.distro),
                            user=str(args.user),
                            bash_command=bash_command,
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(bash_command)
        return 0

    try:
        result = run_wsl_strict_probe(
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
            timeout_seconds=int(args.timeout_seconds),
        )
    except ValueError as exc:
        result = WslStrictProbeLaunchResult(
            status="failed",
            distro=str(args.distro),
            user=str(args.user),
            workspace_wsl_path="",
            return_code=2,
            stdout_tail="",
            stderr_tail=str(exc),
            blockers=("wsl_workspace_path_invalid",),
            probe_output=str(args.probe_output),
            receipt_output=str(args.receipt_output),
        )

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.passed:
        print(f"WSL STRICT GOVERNED CODE-CHANGE LOOP PROBE PASSED distro={result.distro}")
    else:
        print(f"WSL STRICT GOVERNED CODE-CHANGE LOOP PROBE FAILED blockers={list(result.blockers)}")
        if result.stderr_tail:
            print(result.stderr_tail, file=sys.stderr)
    return 0 if result.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
