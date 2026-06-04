#!/usr/bin/env python3
"""Run a governed code-change loop request and write a receipt.

Purpose: bridge a JSON request into the lease-bound sandboxed code worker and
    emit a governed code-change loop receipt artifact.
Governance scope: UAO-style action refs, code-worker execution receipts,
    SDLC receipt closure requirements, and explicit closure blockers.
Dependencies: mcoi_runtime.core.governed_code_change_loop and sandboxed code
    worker runtime.
Invariants:
  - This script does not create terminal closure by itself.
  - Worker receipts are recorded as non-terminal execution evidence.
  - Closure remains blocked unless required SDLC receipt refs are supplied.
  - Malformed input fails closed before worker dispatch.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.core.governed_code_change_loop import (  # noqa: E402
    GovernedCodeChangeRequest,
    GovernedCodeChangeLoopResult,
    run_governed_code_change_loop,
)
from mcoi_runtime.workers.code_worker import SandboxedCodeWorker  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "governed_code_change_loop_receipt.json"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
REQUIRED_REQUEST_FIELDS = (
    "action_id",
    "tenant_id",
    "actor_id",
    "repository",
    "commit_sha",
    "command_id",
    "argv",
    "allowed_paths",
    "allowed_commands",
    "expires_at",
)


def run_from_file(
    *,
    request_path: Path,
    output_path: Path = DEFAULT_OUTPUT,
    workspace_root: Path = WORKSPACE_ROOT,
    sandbox_image: str = "mullu-agent-runner:latest",
    runner: CommandRunner = subprocess.run,
    platform_system: Callable[[], str] = platform.system,
) -> GovernedCodeChangeLoopResult:
    """Load one governed code-change request, execute it, and persist a receipt."""

    request = load_request(request_path)
    worker = SandboxedCodeWorker(
        workspace_root=str(workspace_root),
        clock=_validation_clock,
        runner=runner,
        platform_system=platform_system,
        sandbox_image=sandbox_image,
    )
    result = run_governed_code_change_loop(request, worker)
    write_receipt(result, output_path)
    return result


def load_request(request_path: Path) -> GovernedCodeChangeRequest:
    """Load and validate one governed code-change request JSON object."""

    payload = _load_json_object(request_path, "governed code-change request")
    _require_fields(payload, REQUIRED_REQUEST_FIELDS)
    return GovernedCodeChangeRequest(
        action_id=str(payload["action_id"]),
        tenant_id=str(payload["tenant_id"]),
        actor_id=str(payload["actor_id"]),
        repository=str(payload["repository"]),
        commit_sha=str(payload["commit_sha"]),
        command_id=str(payload["command_id"]),
        argv=_tuple_of_strings(payload["argv"], "argv"),
        cwd=str(payload.get("cwd", ".")),
        allowed_paths=_tuple_of_strings(payload["allowed_paths"], "allowed_paths"),
        allowed_commands=_tuple_of_string_tuples(payload["allowed_commands"], "allowed_commands"),
        expires_at=str(payload["expires_at"]),
        timeout_seconds=int(payload.get("timeout_seconds", 120)),
        memory_mb=int(payload.get("memory_mb", 1024)),
        observed_sdlc_receipt_refs=_string_mapping(
            payload.get("observed_sdlc_receipt_refs", {}),
            "observed_sdlc_receipt_refs",
        ),
        required_sdlc_receipt_kinds=_tuple_of_strings(
            payload.get(
                "required_sdlc_receipt_kinds",
                (
                    "implementation_receipt",
                    "verification_receipt",
                    "recovery_handoff",
                ),
            ),
            "required_sdlc_receipt_kinds",
        ),
        metadata=_metadata_mapping(payload.get("metadata", {})),
    )


def write_receipt(result: GovernedCodeChangeLoopResult, output_path: Path) -> Path:
    """Persist the governed code-change loop receipt."""

    resolved_output = output_path if output_path.is_absolute() else WORKSPACE_ROOT / output_path
    payload = result.to_json_dict()
    payload["receipt_id"] = f"governed-code-change-loop-receipt-{result.action_id}"
    payload["receipt_is_not_terminal_closure"] = True
    payload["terminal_closure_required"] = True
    payload["status"] = "closure_ready" if result.closure_allowed else "blocked"
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return resolved_output


def _load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _require_fields(payload: dict[str, Any], field_names: Sequence[str]) -> None:
    for field_name in field_names:
        if field_name not in payload:
            raise ValueError(f"missing required governed code-change request field: {field_name}")


def _tuple_of_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array of strings")
    result = tuple(_non_empty_string(item, f"{field_name}[{index}]") for index, item in enumerate(value))
    if not result:
        raise ValueError(f"{field_name} must contain at least one item")
    return result


def _tuple_of_string_tuples(value: Any, field_name: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array of argv arrays")
    result = tuple(
        _tuple_of_strings(item, f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )
    if not result:
        raise ValueError(f"{field_name} must contain at least one command")
    return result


def _string_mapping(value: Any, field_name: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return {
        _non_empty_string(key, f"{field_name}.key"): _non_empty_string(item, f"{field_name}[{key}]")
        for key, item in value.items()
    }


def _metadata_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("metadata must be an object")
    return dict(value)


def _non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validation_clock() -> str:
    return "2026-05-07T12:00:00+00:00"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run governed code-change loop receipt producer.")
    parser.add_argument("--request", required=True, help="Path to governed code-change request JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Receipt output path.")
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT), help="Workspace root for worker execution.")
    parser.add_argument("--sandbox-image", default="mullu-agent-runner:latest", help="Sandbox image for executed commands.")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary to stdout.")
    parser.add_argument(
        "--require-closure",
        action="store_true",
        help="Return non-zero when closure remains blocked.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    args = parse_args(argv)
    try:
        result = run_from_file(
            request_path=Path(args.request),
            output_path=Path(args.output),
            workspace_root=Path(args.workspace_root),
            sandbox_image=str(args.sandbox_image),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] governed-code-change-loop: {_sanitize_error(exc)}", file=sys.stderr)
        return 1

    summary = {
        "action_id": result.action_id,
        "closure_allowed": result.closure_allowed,
        "solver_outcome": result.solver_outcome,
        "next_action": result.next_action,
        "closure_blockers": list(result.closure_blockers),
        "code_worker_receipt_ref": result.code_worker_receipt_ref,
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif result.closure_allowed:
        print(f"[PASS] governed-code-change-loop closure_ready action_id={result.action_id}")
    else:
        print(
            "[BLOCKED] governed-code-change-loop "
            f"action_id={result.action_id} blockers={list(result.closure_blockers)}"
        )
    if args.require_closure and not result.closure_allowed:
        return 2
    return 0


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    workspace_text = str(WORKSPACE_ROOT.resolve(strict=False))
    return message.replace(workspace_text, "<workspace>")


if __name__ == "__main__":
    raise SystemExit(main())
