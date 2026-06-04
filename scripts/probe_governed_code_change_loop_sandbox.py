#!/usr/bin/env python3
"""Probe governed code-change loop sandbox execution readiness.

Purpose: produce machine-readable evidence for whether the local workstation
    can satisfy strict governed code-change loop sandbox execution.
Governance scope: code-worker lease dispatch, receipt validation, sandbox
    execution claim separation, and explicit host/runtime blockers.
Dependencies: scripts.run_governed_code_change_loop, receipt validator, Python
    subprocess, platform, pathlib, and json.
Invariants:
  - Probe receipts are non-terminal closure evidence.
  - Strict sandbox execution is separate from valid blocked evidence.
  - Host paths are not serialized except repository-relative output labels.
  - Docker/runtime failures become explicit blockers.
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


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from scripts import run_governed_code_change_loop  # noqa: E402
from scripts.validate_governed_code_change_loop_receipt import (  # noqa: E402
    validate_governed_code_change_loop_receipt,
)


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "governed_code_change_loop_sandbox_probe.json"
DEFAULT_RECEIPT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "governed_code_change_loop_probe_receipt.json"
DEFAULT_PROBE_WORKSPACE = WORKSPACE_ROOT / ".tmp" / "governed-code-change-loop-probe-workspace"
DEFAULT_ACTION_ID = "governed-code-change-loop-sandbox-probe"
DEFAULT_COMMAND_ID = "cmd-governed-code-change-loop-sandbox-probe"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class GovernedCodeChangeLoopSandboxProbeResult:
    """Result for one governed code-change loop sandbox readiness probe."""

    probe_id: str
    status: str
    output_path: str
    receipt_path: str
    platform_system: str
    docker_cli_status: str
    docker_daemon_status: str
    normal_receipt_valid: bool
    strict_sandbox_valid: bool
    solver_outcome: str
    closure_allowed: bool
    blockers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether this host satisfied strict sandbox execution evidence."""

        return self.status == "passed" and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready output."""

        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def probe_governed_code_change_loop_sandbox(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    receipt_output_path: Path = DEFAULT_RECEIPT_OUTPUT,
    probe_workspace: Path = DEFAULT_PROBE_WORKSPACE,
    action_id: str = DEFAULT_ACTION_ID,
    command_id: str = DEFAULT_COMMAND_ID,
    sandbox_image: str = "mullu-agent-runner:latest",
    runner: CommandRunner = subprocess.run,
    platform_system: Callable[[], str] = platform.system,
    docker_runner: CommandRunner = subprocess.run,
) -> GovernedCodeChangeLoopSandboxProbeResult:
    """Run one governed code-change loop probe and persist readiness evidence."""

    probe_workspace.mkdir(parents=True, exist_ok=True)
    request_path = output_path.with_suffix(".request.json")
    _write_probe_request(request_path, action_id=action_id, command_id=command_id)
    docker_cli_status = _docker_cli_status(docker_runner)
    docker_daemon_status = _docker_daemon_status(docker_runner)
    result = run_governed_code_change_loop.run_from_file(
        request_path=request_path,
        output_path=receipt_output_path,
        workspace_root=probe_workspace,
        sandbox_image=sandbox_image,
        runner=runner,
        platform_system=platform_system,
    )
    normal_validation = validate_governed_code_change_loop_receipt(receipt_output_path)
    strict_validation = validate_governed_code_change_loop_receipt(
        receipt_output_path,
        require_sandbox_execution=True,
    )
    blockers = _blockers_for(
        platform_system_value=platform_system(),
        docker_cli_status=docker_cli_status,
        docker_daemon_status=docker_daemon_status,
        normal_receipt_valid=normal_validation.valid,
        strict_sandbox_valid=strict_validation.valid,
        solver_outcome=result.solver_outcome,
        command_status=result.command_result.status.value,
        command_stderr=result.command_result.stderr,
        strict_detail=strict_validation.detail,
    )
    status = "passed" if not blockers else "failed"
    probe_result = GovernedCodeChangeLoopSandboxProbeResult(
        probe_id=f"governed-code-change-loop-sandbox-probe-{action_id}",
        status=status,
        output_path=_path_label(output_path),
        receipt_path=_path_label(receipt_output_path),
        platform_system=platform_system(),
        docker_cli_status=docker_cli_status,
        docker_daemon_status=docker_daemon_status,
        normal_receipt_valid=normal_validation.valid,
        strict_sandbox_valid=strict_validation.valid,
        solver_outcome=result.solver_outcome,
        closure_allowed=result.closure_allowed,
        blockers=blockers,
    )
    _write_json(
        output_path,
        {
            **probe_result.as_dict(),
            "receipt_id": f"governed-code-change-loop-receipt-{action_id}",
            "code_worker_receipt_ref": result.code_worker_receipt_ref,
            "closure_blockers": list(result.closure_blockers),
            "strict_validation_detail": strict_validation.detail,
            "normal_validation_detail": normal_validation.detail,
            "request_path": _path_label(request_path),
            "receipt_is_not_terminal_closure": True,
            "terminal_closure_required": True,
        },
    )
    return probe_result


def _write_probe_request(path: Path, *, action_id: str, command_id: str) -> Path:
    payload = {
        "action_id": action_id,
        "tenant_id": "tenant-local-probe",
        "actor_id": "local-operator",
        "repository": "local-worktree",
        "commit_sha": "local-worktree",
        "command_id": command_id,
        "argv": ["python", "--version"],
        "cwd": ".",
        "allowed_paths": ["."],
        "allowed_commands": [["python", "--version"]],
        "expires_at": "2026-06-30T00:00:00+00:00",
        "observed_sdlc_receipt_refs": {
            "implementation_receipt": "receipt://local/probe-implementation",
            "verification_receipt": "receipt://local/probe-verification",
            "recovery_handoff": "receipt://local/probe-recovery-handoff",
        },
        "metadata": {
            "purpose": "governed code-change loop sandbox readiness probe",
        },
    }
    return _write_json(path, payload)


def _docker_cli_status(docker_runner: CommandRunner) -> str:
    completed = _run_docker_probe(docker_runner, ("docker", "--version"))
    if completed.returncode == 0:
        return "available"
    if completed.returncode == 127:
        return "missing"
    return "failed"


def _docker_daemon_status(docker_runner: CommandRunner) -> str:
    completed = _run_docker_probe(
        docker_runner,
        ("docker", "info", "--format", "{{json .SecurityOptions}}"),
    )
    if completed.returncode == 0:
        return "reachable"
    return "unreachable"


def _run_docker_probe(
    docker_runner: CommandRunner,
    argv: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    try:
        return docker_runner(
            list(argv),
            capture_output=True,
            check=False,
            shell=False,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(list(argv), 127, stdout="", stderr="docker executable missing")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            list(argv),
            1,
            stdout="",
            stderr=type(exc).__name__,
        )


def _blockers_for(
    *,
    platform_system_value: str,
    docker_cli_status: str,
    docker_daemon_status: str,
    normal_receipt_valid: bool,
    strict_sandbox_valid: bool,
    solver_outcome: str,
    command_status: str,
    command_stderr: str,
    strict_detail: str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if platform_system_value.lower() != "linux":
        blockers.append("sandbox_runner_linux_only")
    if docker_cli_status != "available":
        blockers.append(f"docker_cli_{docker_cli_status}")
    if docker_daemon_status != "reachable":
        blockers.append(f"docker_daemon_{docker_daemon_status}")
    if not normal_receipt_valid:
        blockers.append("governed_code_change_loop_receipt_invalid")
    if not strict_sandbox_valid:
        blockers.append("governed_code_change_loop_strict_sandbox_invalid")
    if solver_outcome != "SolvedVerified":
        blockers.append(f"solver_outcome_{solver_outcome}")
    if command_status != "succeeded":
        blockers.append(f"code_worker_status_{command_status}")
    if command_stderr == "sandbox runner is linux-only":
        blockers.append("code_worker_sandbox_runner_linux_only")
    if "sandbox_execution_required_verification_not_passed" in strict_detail:
        blockers.append("sandbox_verification_not_passed")
    return tuple(dict.fromkeys(blockers))


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return resolved_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Probe governed code-change loop sandbox execution readiness."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--receipt-output", default=str(DEFAULT_RECEIPT_OUTPUT))
    parser.add_argument("--probe-workspace", default=str(DEFAULT_PROBE_WORKSPACE))
    parser.add_argument("--action-id", default=DEFAULT_ACTION_ID)
    parser.add_argument("--command-id", default=DEFAULT_COMMAND_ID)
    parser.add_argument("--sandbox-image", default="mullu-agent-runner:latest")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sandbox readiness probe."""

    args = parse_args(argv)
    result = probe_governed_code_change_loop_sandbox(
        output_path=Path(args.output),
        receipt_output_path=Path(args.receipt_output),
        probe_workspace=Path(args.probe_workspace),
        action_id=str(args.action_id),
        command_id=str(args.command_id),
        sandbox_image=str(args.sandbox_image),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.passed:
        print(f"GOVERNED CODE-CHANGE LOOP SANDBOX PROBE PASSED probe_id={result.probe_id}")
    else:
        print(
            "GOVERNED CODE-CHANGE LOOP SANDBOX PROBE FAILED "
            f"blockers={list(result.blockers)}"
        )
    return 0 if result.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
