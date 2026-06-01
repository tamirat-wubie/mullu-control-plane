#!/usr/bin/env python3
"""Run repository-local workspace governance checks.

Purpose: provide one deterministic preflight command for the control-plane
checkout without depending on the broader parent workspace script surface.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library and repository-local validation scripts.
Invariants:
  - Default checks are read-only and deterministic.
  - Every check emits an explicit command receipt.
  - Full unsharded preflights use a workspace-local lock.
  - The process returns nonzero when any required check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import TracebackType
from typing import TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_RETURN_CODE = 124
PREFLIGHT_LOCK_RETURN_CODE = 125
PREFLIGHT_LOCK_ID = "workspace_governance_preflight_lock"
DEFAULT_PREFLIGHT_LOCK_PATH = WORKSPACE_ROOT / ".tmp" / "workspace-governance-preflight.lock"


class PreflightLockError(RuntimeError):
    """Raised when a full governance preflight is already active."""


@dataclass(frozen=True, slots=True)
class CheckCommand:
    """One deterministic governance check command."""

    name: str
    args: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Observed result for one governance check command."""

    name: str
    args: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """Return whether the check completed successfully."""

        return self.return_code == 0


class PreflightLock:
    """Workspace-local exclusive lock for full preflight execution."""

    def __init__(self, lock_path: Path = DEFAULT_PREFLIGHT_LOCK_PATH) -> None:
        self.lock_path = lock_path
        self._file_descriptor: int | None = None

    def __enter__(self) -> "PreflightLock":
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_descriptor = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if not _remove_stale_preflight_lock(self.lock_path):
                raise PreflightLockError(f"workspace governance preflight is already running: {self.lock_path}") from exc
            try:
                self._file_descriptor = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as retry_exc:
                raise PreflightLockError(
                    f"workspace governance preflight is already running: {self.lock_path}"
                ) from retry_exc

        payload = {
            "lock_id": PREFLIGHT_LOCK_ID,
            "pid": os.getpid(),
            "created_at_epoch": time.time(),
        }
        os.write(self._file_descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._file_descriptor is not None:
            os.close(self._file_descriptor)
            self._file_descriptor = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def build_check_commands(python_executable: str = sys.executable) -> tuple[CheckCommand, ...]:
    """Build the fixed repository-local governance check command list."""

    return (
        CheckCommand(
            "local_assurance_plan",
            (python_executable, "scripts/refresh_local_assurance.py", "--dry-run", "--json"),
        ),
        CheckCommand("protocol_manifest", (python_executable, "scripts/validate_protocol_manifest.py")),
        CheckCommand(
            "logic_governance_application",
            (python_executable, "scripts/validate_logic_governance_application.py"),
        ),
        CheckCommand(
            "public_repository_surface",
            (python_executable, "scripts/validate_public_repository_surface.py"),
        ),
        CheckCommand("proprietary_boundary", (python_executable, "scripts/validate_proprietary_boundary.py")),
        CheckCommand("release_status", (python_executable, "scripts/validate_release_status.py")),
        CheckCommand(
            "workspace_governance_preflight_receipt_contract",
            (python_executable, "scripts/validate_workspace_governance_preflight_receipt_contract.py"),
        ),
        CheckCommand(
            "workspace_governance_preflight_receipt_example",
            (python_executable, "scripts/validate_workspace_governance_preflight_receipt.py"),
        ),
        CheckCommand(
            "universal_action_orchestration_contract",
            (python_executable, "scripts/validate_universal_action_orchestration.py"),
        ),
    )


def run_check(
    command: CheckCommand,
    workspace_root: Path = WORKSPACE_ROOT,
    timeout_seconds: float | None = None,
) -> CheckResult:
    """Run one governance check command from the workspace root."""

    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive when provided")
    try:
        completed = subprocess.run(
            command.args,
            cwd=workspace_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _normalize_timeout_output(exc.stdout)
        stderr = _normalize_timeout_output(exc.stderr)
        if stderr and not stderr.endswith("\n"):
            stderr += "\n"
        stderr += f"[TIMEOUT] {command.name} exceeded {timeout_seconds} seconds: {' '.join(command.args)}\n"
        return CheckResult(command.name, command.args, TIMEOUT_RETURN_CODE, stdout, stderr)
    return CheckResult(command.name, command.args, int(completed.returncode), completed.stdout, completed.stderr)


def run_checks(
    commands: tuple[CheckCommand, ...],
    workspace_root: Path = WORKSPACE_ROOT,
    max_workers: int = 1,
    timeout_seconds: float | None = None,
) -> tuple[CheckResult, ...]:
    """Run governance checks and preserve the declared result order."""

    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive when provided")
    if max_workers == 1:
        return tuple(run_check(command, workspace_root, timeout_seconds) for command in commands)

    results_by_index: list[CheckResult | None] = [None] * len(commands)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_index = {
            executor.submit(run_check, command, workspace_root, timeout_seconds): index
            for index, command in enumerate(commands)
        }
        for future in as_completed(future_by_index):
            results_by_index[future_by_index[future]] = future.result()
    return tuple(result for result in results_by_index if result is not None)


def select_check_commands(
    commands: tuple[CheckCommand, ...],
    selected_names: tuple[str, ...] = (),
    shard_count: int = 1,
    shard_index: int = 0,
) -> tuple[CheckCommand, ...]:
    """Select a deterministic bounded subset of governance checks."""

    if shard_count < 1:
        raise ValueError("shard-count must be at least 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard-index must be in [0, shard-count)")

    command_names = {command.name for command in commands}
    unknown_names = sorted(set(selected_names) - command_names)
    if unknown_names:
        raise ValueError(f"unknown check name: {', '.join(unknown_names)}")

    selected = (
        tuple(command for command in commands if command.name in set(selected_names))
        if selected_names
        else commands
    )
    sharded = tuple(command for index, command in enumerate(selected) if index % shard_count == shard_index)
    if not sharded:
        raise ValueError("selected check set is empty")
    return sharded


def requires_full_preflight_lock(selected_names: tuple[str, ...], shard_count: int) -> bool:
    """Return whether this run needs the workspace-level preflight lock."""

    return not selected_names and shard_count == 1


@contextmanager
def maybe_full_preflight_lock(lock_required: bool, lock_path: Path = DEFAULT_PREFLIGHT_LOCK_PATH):
    """Acquire the full-preflight lock only when a full preflight is requested."""

    if not lock_required:
        yield
        return
    with PreflightLock(lock_path):
        yield


def render_results(results: tuple[CheckResult, ...], output_stream: TextIO, error_stream: TextIO) -> None:
    """Render governance check results with command witness output."""

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        output_stream.write(f"[{status}] {result.name}: {' '.join(result.args)}\n")
        if result.stdout:
            output_stream.write(result.stdout)
            if not result.stdout.endswith("\n"):
                output_stream.write("\n")
        if result.stderr:
            error_stream.write(result.stderr)
            if not result.stderr.endswith("\n"):
                error_stream.write("\n")


def build_receipt(results: tuple[CheckResult, ...]) -> dict[str, object]:
    """Build a machine-readable governance preflight receipt."""

    checks: list[dict[str, object]] = []
    for result in results:
        payload = asdict(result)
        payload["args"] = list(result.args)
        payload["passed"] = result.passed
        checks.append(payload)
    return {
        "receipt_id": "workspace_governance_preflight_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "status": "passed" if all(result.passed for result in results) else "failed",
        "check_count": len(results),
        "checks": checks,
    }


def resolve_receipt_path(receipt_path: Path, workspace_root: Path = WORKSPACE_ROOT) -> Path:
    """Resolve a workspace-local JSON receipt path and reject path escapes."""

    if receipt_path.suffix.lower() != ".json":
        raise ValueError("receipt path must use .json suffix")
    resolved_root = workspace_root.resolve()
    resolved_path = (workspace_root / receipt_path).resolve() if not receipt_path.is_absolute() else receipt_path.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"receipt path must stay under workspace root: {receipt_path}")
    return resolved_path


def write_receipt(
    receipt: dict[str, object],
    receipt_path: Path,
    workspace_root: Path = WORKSPACE_ROOT,
) -> Path:
    """Persist one machine-readable receipt under the workspace root."""

    resolved_path = resolve_receipt_path(receipt_path, workspace_root)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def main(argv: list[str] | None = None) -> int:
    """Run the workspace governance preflight."""

    parser = argparse.ArgumentParser(description="Run repository-local workspace governance checks.")
    parser.add_argument("--check", action="append", default=[], help="run only the named check; repeatable")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable preflight receipt")
    parser.add_argument("--receipt-path", type=Path, help="write the JSON receipt to this workspace-local path")
    parser.add_argument("--max-workers", type=int, default=1, help="maximum parallel check workers")
    parser.add_argument("--per-check-timeout-seconds", type=float, help="timeout for each check")
    parser.add_argument("--shard-count", type=int, default=1, help="number of deterministic shards")
    parser.add_argument("--shard-index", type=int, default=0, help="zero-based shard index")
    args = parser.parse_args(argv)

    selected_names = tuple(str(name) for name in args.check)
    try:
        commands = select_check_commands(
            build_check_commands(),
            selected_names=selected_names,
            shard_count=int(args.shard_count),
            shard_index=int(args.shard_index),
        )
    except ValueError as exc:
        sys.stderr.write(f"[FAIL] check-selection: {exc}\nSTATUS: failed\n")
        return 1

    try:
        with maybe_full_preflight_lock(requires_full_preflight_lock(selected_names, int(args.shard_count))):
            results = run_checks(
                commands,
                WORKSPACE_ROOT,
                max_workers=int(args.max_workers),
                timeout_seconds=args.per_check_timeout_seconds,
            )
    except PreflightLockError as exc:
        sys.stderr.write(f"[FAIL] preflight-lock: {exc}\nSTATUS: failed\n")
        return PREFLIGHT_LOCK_RETURN_CODE
    except ValueError as exc:
        sys.stderr.write(f"[FAIL] check-execution: {exc}\nSTATUS: failed\n")
        return 1

    receipt = build_receipt(results)
    if args.receipt_path is not None:
        try:
            write_receipt(receipt, args.receipt_path)
        except ValueError as exc:
            sys.stderr.write(f"[FAIL] receipt-path: {exc}\nSTATUS: failed\n")
            return 1

    if args.json:
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        render_results(results, sys.stdout, sys.stderr)
        sys.stdout.write(f"STATUS: {receipt['status']}\n")
    return 0 if receipt["status"] == "passed" else 1


def _normalize_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _process_is_active(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ("tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return True
        return f'"{pid}"' in completed.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_preflight_lock_payload(lock_path: Path) -> dict[str, object] | None:
    try:
        raw_payload = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PreflightLockError(f"cannot inspect existing preflight lock {lock_path}: {exc}") from exc
    try:
        parsed_payload = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return parsed_payload if isinstance(parsed_payload, dict) else {}


def _preflight_lock_payload_is_stale(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return True
    if payload.get("lock_id") != PREFLIGHT_LOCK_ID:
        return True
    pid = payload.get("pid")
    created_at_epoch = payload.get("created_at_epoch")
    if isinstance(pid, bool) or not isinstance(pid, int):
        return True
    if isinstance(created_at_epoch, bool) or not isinstance(created_at_epoch, (int, float)):
        return True
    return not _process_is_active(pid)


def _remove_stale_preflight_lock(lock_path: Path) -> bool:
    observed_payload = _read_preflight_lock_payload(lock_path)
    if not _preflight_lock_payload_is_stale(observed_payload):
        return False
    if _read_preflight_lock_payload(lock_path) != observed_payload:
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise PreflightLockError(f"cannot remove stale preflight lock {lock_path}: {exc}") from exc
    return True


if __name__ == "__main__":
    raise SystemExit(main())
