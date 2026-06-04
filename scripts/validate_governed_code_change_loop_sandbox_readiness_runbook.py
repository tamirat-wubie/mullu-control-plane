#!/usr/bin/env python3
"""Validate governed code-change loop sandbox readiness runbook.

Purpose: keep the Linux strict-readiness handoff aligned with the executable
    probe and validator contracts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and docs/GOVERNED_CODE_CHANGE_LOOP_SANDBOX_READINESS.md.
Invariants:
  - The runbook preserves the Linux-only sandbox execution boundary.
  - Strict probe evidence and strict validation commands remain visible.
  - Blocked evidence is not confused with terminal closure.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNBOOK_PATH = WORKSPACE_ROOT / "docs" / "GOVERNED_CODE_CHANGE_LOOP_SANDBOX_READINESS.md"
DEFAULT_RUNNER_DOCKERFILE_PATH = WORKSPACE_ROOT / "docker" / "governed-code-change-loop-runner.Dockerfile"
DEFAULT_WSL_LAUNCHER_PATH = WORKSPACE_ROOT / "scripts" / "run_wsl_governed_code_change_loop_sandbox_probe.py"
REQUIRED_FRAGMENTS = (
    "sandbox execution remains Linux-only",
    "Linux execution lane",
    "WSL2 Ubuntu",
    "python scripts/run_wsl_governed_code_change_loop_sandbox_probe.py --distro Ubuntu --user root --strict --json",
    "python scripts/run_wsl_governed_code_change_loop_sandbox_probe.py --print-command --json",
    "--with-preflight",
    "Docker Desktop WSL integration",
    "Docker Desktop's native WSL CLI and socket",
    "docker/governed-code-change-loop-runner.Dockerfile",
    "docker build -f docker/governed-code-change-loop-runner.Dockerfile -t mullu-agent-runner:latest docker",
    "daemon-visible `/mnt/host/c/...`",
    "Ubuntu-readable `/mnt/c/...`",
    "wsl -d Ubuntu -u root",
    "wsl -d Ubuntu -- bash -lc",
    "AwaitingEvidence",
    "GovernanceBlocked",
    "SolvedVerified",
    "python scripts/probe_governed_code_change_loop_sandbox.py",
    "--strict --json",
    "python scripts/validate_governed_code_change_loop_sandbox_probe.py",
    "--require-strict-sandbox-ready --json",
    "python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json",
    "python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt.json",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
    "wsl_cli_missing",
    "wsl_workspace_path_invalid",
    "wsl_strict_probe_timeout",
    "wsl_strict_probe_command_failed",
    "sandbox_runner_linux_only",
    "docker_cli_missing",
    "docker_daemon_unreachable",
    "governed_code_change_loop_strict_sandbox_invalid",
    "code_worker_sandbox_runner_linux_only",
    "sandbox_verification_not_passed",
)
REQUIRED_DOCKERFILE_FRAGMENTS = (
    "FROM python:3.12-slim",
    "useradd -m nonroot",
    "USER nonroot",
    "WORKDIR /workspace",
)
REQUIRED_WSL_LAUNCHER_FRAGMENTS = (
    "Purpose: provide a repeatable Windows-side launcher",
    "build_wsl_probe_bash_command",
    "windows_path_to_wsl_path",
    "--print-command",
    '"status": "planned"',
    "NATIVE_DOCKER_SOCKET",
    "python3 scripts/probe_governed_code_change_loop_sandbox.py",
    "--require-strict-sandbox-ready --json",
    "--require-sandbox-execution --json",
    "wsl_cli_missing",
    "wsl_strict_probe_command_failed",
)


@dataclass(frozen=True, slots=True)
class RunbookValidation:
    """Validation result for the governed code-change loop sandbox runbook."""

    valid: bool
    runbook_path: str
    missing_fragments: tuple[str, ...]
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""

        payload = asdict(self)
        payload["missing_fragments"] = list(self.missing_fragments)
        return payload


def validate_runbook(runbook_path: Path = DEFAULT_RUNBOOK_PATH) -> RunbookValidation:
    """Validate the sandbox readiness runbook text contract."""

    if not runbook_path.exists():
        return RunbookValidation(
            valid=False,
            runbook_path=_path_label(runbook_path),
            missing_fragments=(),
            detail="runbook file not found",
        )
    if not runbook_path.is_file():
        return RunbookValidation(
            valid=False,
            runbook_path=_path_label(runbook_path),
            missing_fragments=(),
            detail="runbook path is not a file",
        )
    try:
        text = runbook_path.read_text(encoding="utf-8")
    except OSError as exc:
        return RunbookValidation(
            valid=False,
            runbook_path=_path_label(runbook_path),
            missing_fragments=(),
            detail=f"runbook unreadable:{type(exc).__name__}",
        )

    missing = tuple(fragment for fragment in REQUIRED_FRAGMENTS if fragment not in text)
    dockerfile_missing = _missing_file_fragments(
        DEFAULT_RUNNER_DOCKERFILE_PATH,
        REQUIRED_DOCKERFILE_FRAGMENTS,
    )
    launcher_missing = _missing_file_fragments(
        DEFAULT_WSL_LAUNCHER_PATH,
        REQUIRED_WSL_LAUNCHER_FRAGMENTS,
    )
    missing = (*missing, *dockerfile_missing, *launcher_missing)
    if missing:
        return RunbookValidation(
            valid=False,
            runbook_path=_path_label(runbook_path),
            missing_fragments=missing,
            detail="runbook missing required strict-readiness fragments",
        )
    return RunbookValidation(
        valid=True,
        runbook_path=_path_label(runbook_path),
        missing_fragments=(),
        detail="governed code-change loop sandbox readiness runbook verified",
    )


def _missing_file_fragments(file_path: Path, fragments: tuple[str, ...]) -> tuple[str, ...]:
    if not file_path.exists() or not file_path.is_file():
        return (_path_label(file_path),)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return (_path_label(file_path),)
    return tuple(fragment for fragment in fragments if fragment not in text)


def _path_label(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Validate governed code-change loop sandbox readiness runbook."
    )
    parser.add_argument("--runbook", type=Path, default=DEFAULT_RUNBOOK_PATH)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    result = validate_runbook(args.runbook)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"governed code-change loop sandbox readiness runbook ok: {result.runbook_path}")
    else:
        print(f"error: {result.detail}: {list(result.missing_fragments)}", file=sys.stderr)
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
