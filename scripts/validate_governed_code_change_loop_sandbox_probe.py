#!/usr/bin/env python3
"""Validate governed code-change loop sandbox probe evidence.

Purpose: validate readiness evidence emitted by
    scripts/probe_governed_code_change_loop_sandbox.py.
Governance scope: probe shape, blocker consistency, strict sandbox readiness,
    non-terminal receipt boundary, and host/runtime claim separation.
Dependencies: Python standard library only.
Invariants:
  - Failed probes can be valid evidence only when blockers are explicit.
  - Strict readiness requires passed probe status and no blockers.
  - Probe output paths must be repository-relative labels, not host paths.
  - Terminal closure is never implied by the probe artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROBE_PATH = (
    WORKSPACE_ROOT / ".change_assurance" / "governed_code_change_loop_sandbox_probe.json"
)
REQUIRED_FIELDS = (
    "probe_id",
    "status",
    "output_path",
    "receipt_path",
    "request_path",
    "platform_system",
    "docker_cli_status",
    "docker_daemon_status",
    "normal_receipt_valid",
    "strict_sandbox_valid",
    "solver_outcome",
    "closure_allowed",
    "blockers",
    "receipt_id",
    "code_worker_receipt_ref",
    "closure_blockers",
    "strict_validation_detail",
    "normal_validation_detail",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
)
VALID_STATUS = {"passed", "failed"}
VALID_DOCKER_CLI_STATUS = {"available", "missing", "failed"}
VALID_DOCKER_DAEMON_STATUS = {"reachable", "unreachable"}
VALID_SOLVER_OUTCOMES = {
    "SolvedVerified",
    "SolvedUnverified",
    "AwaitingEvidence",
    "GovernanceBlocked",
}


@dataclass(frozen=True, slots=True)
class GovernedCodeChangeLoopSandboxProbeValidation:
    """Validation result for one sandbox probe evidence artifact."""

    valid: bool
    probe_path: str
    status: str
    probe_id: str
    strict_sandbox_valid: bool
    detail: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready output."""

        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def validate_governed_code_change_loop_sandbox_probe(
    probe_path: Path = DEFAULT_PROBE_PATH,
    *,
    require_strict_sandbox_ready: bool = False,
) -> GovernedCodeChangeLoopSandboxProbeValidation:
    """Validate one governed code-change loop sandbox probe artifact."""

    payload, load_error = _load_payload(probe_path)
    if load_error:
        return _invalid(probe_path, load_error, ("sandbox_probe_unreadable",))
    errors = _probe_errors(
        payload,
        require_strict_sandbox_ready=require_strict_sandbox_ready,
    )
    if errors:
        return GovernedCodeChangeLoopSandboxProbeValidation(
            valid=False,
            probe_path=_path_label(probe_path),
            status="failed",
            probe_id=str(payload.get("probe_id", "")).strip(),
            strict_sandbox_valid=payload.get("strict_sandbox_valid") is True,
            detail=",".join(errors),
            blockers=("governed_code_change_loop_sandbox_probe_invalid",),
        )
    return GovernedCodeChangeLoopSandboxProbeValidation(
        valid=True,
        probe_path=_path_label(probe_path),
        status="passed",
        probe_id=str(payload["probe_id"]),
        strict_sandbox_valid=payload["strict_sandbox_valid"] is True,
        detail="governed code-change loop sandbox probe verified",
        blockers=(),
    )


def _load_payload(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "probe file not found"
    if not path.is_file():
        return {}, "probe path is not a file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "probe unreadable"
    if not isinstance(payload, dict):
        return {}, "probe root must be an object"
    return payload, ""


def _probe_errors(
    probe: Mapping[str, Any],
    *,
    require_strict_sandbox_ready: bool,
) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in probe:
            errors.append(f"{field_name}_missing")

    probe_id = str(probe.get("probe_id", "")).strip()
    receipt_id = str(probe.get("receipt_id", "")).strip()
    status = probe.get("status")
    blockers = _string_list(probe.get("blockers"))
    closure_blockers = _string_list(probe.get("closure_blockers"))
    platform_system = str(probe.get("platform_system", "")).strip()
    docker_cli_status = probe.get("docker_cli_status")
    docker_daemon_status = probe.get("docker_daemon_status")
    solver_outcome = probe.get("solver_outcome")

    if not probe_id.startswith("governed-code-change-loop-sandbox-probe-"):
        errors.append("probe_id_invalid")
    if not receipt_id.startswith("governed-code-change-loop-receipt-"):
        errors.append("receipt_id_invalid")
    code_worker_receipt_ref = probe.get("code_worker_receipt_ref")
    if not isinstance(code_worker_receipt_ref, str) or not code_worker_receipt_ref.startswith(
        "receipt://code-worker-receipt-"
    ):
        errors.append("code_worker_receipt_ref_invalid")
    if status not in VALID_STATUS:
        errors.append("status_invalid")
    if not _is_string_list(probe.get("blockers")):
        errors.append("blockers_not_string_list")
    if not _is_string_list(probe.get("closure_blockers")):
        errors.append("closure_blockers_not_string_list")
    if len(set(blockers)) != len(blockers):
        errors.append("blockers_duplicate")
    if len(set(closure_blockers)) != len(closure_blockers):
        errors.append("closure_blockers_duplicate")
    if status == "passed" and blockers:
        errors.append("passed_probe_has_blockers")
    if status == "failed" and not blockers:
        errors.append("failed_probe_requires_blockers")
    if docker_cli_status not in VALID_DOCKER_CLI_STATUS:
        errors.append("docker_cli_status_invalid")
    if docker_daemon_status not in VALID_DOCKER_DAEMON_STATUS:
        errors.append("docker_daemon_status_invalid")
    if solver_outcome not in VALID_SOLVER_OUTCOMES:
        errors.append("solver_outcome_invalid")

    if probe.get("receipt_is_not_terminal_closure") is not True:
        errors.append("receipt_is_not_terminal_closure_not_true")
    if probe.get("terminal_closure_required") is not True:
        errors.append("terminal_closure_required_not_true")
    for field_name in ("normal_receipt_valid", "strict_sandbox_valid", "closure_allowed"):
        if not isinstance(probe.get(field_name), bool):
            errors.append(f"{field_name}_not_bool")
    for field_name in ("output_path", "receipt_path", "request_path"):
        value = probe.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field_name}_empty")
        elif _looks_like_host_path(value):
            errors.append(f"{field_name}_must_be_repository_relative")

    if probe.get("normal_receipt_valid") is not True:
        errors.append("normal_receipt_validation_not_passed")
    if probe.get("strict_sandbox_valid") is True and status != "passed":
        errors.append("strict_sandbox_valid_with_failed_status")
    if probe.get("strict_sandbox_valid") is False and status == "passed":
        errors.append("passed_status_without_strict_sandbox_validation")
    if platform_system.lower() != "linux" and "sandbox_runner_linux_only" not in blockers:
        errors.append("non_linux_probe_missing_linux_only_blocker")
    if docker_cli_status != "available" and f"docker_cli_{docker_cli_status}" not in blockers:
        errors.append("docker_cli_blocker_missing")
    if docker_daemon_status != "reachable" and f"docker_daemon_{docker_daemon_status}" not in blockers:
        errors.append("docker_daemon_blocker_missing")
    if solver_outcome != "SolvedVerified" and f"solver_outcome_{solver_outcome}" not in blockers:
        errors.append("solver_outcome_blocker_missing")
    if probe.get("closure_allowed") is False and not closure_blockers:
        errors.append("blocked_closure_requires_closure_blockers")
    if probe.get("closure_allowed") is True and closure_blockers:
        errors.append("closure_allowed_with_closure_blockers")

    if require_strict_sandbox_ready:
        errors.extend(_strict_readiness_errors(probe, blockers))
    return tuple(dict.fromkeys(errors))


def _strict_readiness_errors(probe: Mapping[str, Any], blockers: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    if probe.get("status") != "passed":
        errors.append("strict_sandbox_ready_requires_passed_status")
    if blockers:
        errors.append("strict_sandbox_ready_requires_no_blockers")
    if str(probe.get("platform_system", "")).lower() != "linux":
        errors.append("strict_sandbox_ready_requires_linux")
    if probe.get("docker_cli_status") != "available":
        errors.append("strict_sandbox_ready_requires_docker_cli")
    if probe.get("docker_daemon_status") != "reachable":
        errors.append("strict_sandbox_ready_requires_docker_daemon")
    if probe.get("normal_receipt_valid") is not True:
        errors.append("strict_sandbox_ready_requires_normal_receipt_valid")
    if probe.get("strict_sandbox_valid") is not True:
        errors.append("strict_sandbox_ready_requires_strict_sandbox_valid")
    if probe.get("solver_outcome") != "SolvedVerified":
        errors.append("strict_sandbox_ready_requires_solved_verified")
    if probe.get("closure_allowed") is not True:
        errors.append("strict_sandbox_ready_requires_closure_allowed")
    return errors


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _looks_like_host_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized.startswith("/") or (
        len(normalized) >= 3
        and normalized[1] == ":"
        and normalized[2] == "/"
        and normalized[0].isalpha()
    )


def _path_label(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _invalid(
    path: Path,
    detail: str,
    blockers: tuple[str, ...],
) -> GovernedCodeChangeLoopSandboxProbeValidation:
    return GovernedCodeChangeLoopSandboxProbeValidation(
        valid=False,
        probe_path=_path_label(path),
        status="failed",
        probe_id="",
        strict_sandbox_valid=False,
        detail=detail,
        blockers=blockers,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Validate governed code-change loop sandbox probe evidence."
    )
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE_PATH)
    parser.add_argument("--require-strict-sandbox-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    result = validate_governed_code_change_loop_sandbox_probe(
        args.probe,
        require_strict_sandbox_ready=args.require_strict_sandbox_ready,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"governed code-change loop sandbox probe ok: {result.probe_id}")
    else:
        for blocker in result.blockers:
            print(f"error: {blocker}: {result.detail}", file=sys.stderr)
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
