#!/usr/bin/env python3
"""Validate a governed code-change loop receipt.

Purpose: validate receipt artifacts emitted by scripts/run_governed_code_change_loop.py.
Governance scope: UAO-style refs, code-worker receipt binding, non-terminal
    closure flags, SDLC receipt blockers, and explicit solver outcome.
Dependencies: Python standard library only.
Invariants:
  - Worker receipts do not imply terminal closure.
  - Closure-ready receipts require all required SDLC receipt refs.
  - Blocked receipts must carry explicit blockers.
  - Malformed, missing, or contradictory receipts fail closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = (
    WORKSPACE_ROOT / ".change_assurance" / "governed_code_change_loop_receipt.json"
)
REQUIRED_TOP_LEVEL_FIELDS = (
    "receipt_id",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
    "status",
    "action_id",
    "uao_ref",
    "causal_decision_trace_ref",
    "lease",
    "command_result",
    "code_worker_receipt_ref",
    "required_sdlc_receipt_kinds",
    "observed_sdlc_receipt_refs",
    "missing_sdlc_receipt_kinds",
    "closure_allowed",
    "solver_outcome",
    "next_action",
    "closure_blockers",
)
REQUIRED_SDLC_RECEIPT_KINDS = (
    "implementation_receipt",
    "verification_receipt",
    "recovery_handoff",
)
VALID_SOLVER_OUTCOMES = {
    "SolvedVerified",
    "SolvedUnverified",
    "AwaitingEvidence",
    "GovernanceBlocked",
}


@dataclass(frozen=True, slots=True)
class GovernedCodeChangeLoopReceiptValidation:
    """Validation result for one governed code-change loop receipt."""

    valid: bool
    receipt_path: str
    status: str
    receipt_id: str
    action_id: str
    solver_outcome: str
    closure_allowed: bool
    detail: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""

        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def validate_governed_code_change_loop_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    *,
    require_closure_ready: bool = False,
    require_sandbox_execution: bool = False,
) -> GovernedCodeChangeLoopReceiptValidation:
    """Validate one governed code-change loop receipt file."""

    payload, load_error = _load_payload(receipt_path)
    if load_error:
        return _invalid(receipt_path, load_error, ("receipt_unreadable",))

    errors = _receipt_errors(
        payload,
        require_closure_ready=require_closure_ready,
        require_sandbox_execution=require_sandbox_execution,
    )
    receipt_id = str(payload.get("receipt_id", "")).strip()
    action_id = str(payload.get("action_id", "")).strip()
    solver_outcome = str(payload.get("solver_outcome", "")).strip()
    closure_allowed = payload.get("closure_allowed") is True
    if errors:
        return GovernedCodeChangeLoopReceiptValidation(
            valid=False,
            receipt_path=_path_label(receipt_path),
            status="failed",
            receipt_id=receipt_id,
            action_id=action_id,
            solver_outcome=solver_outcome,
            closure_allowed=closure_allowed,
            detail=",".join(errors),
            blockers=("governed_code_change_loop_receipt_invalid",),
        )
    return GovernedCodeChangeLoopReceiptValidation(
        valid=True,
        receipt_path=_path_label(receipt_path),
        status="passed",
        receipt_id=receipt_id,
        action_id=action_id,
        solver_outcome=solver_outcome,
        closure_allowed=closure_allowed,
        detail="governed code-change loop receipt verified",
        blockers=(),
    )


def _load_payload(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "receipt file not found"
    if not path.is_file():
        return {}, "receipt path is not a file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "receipt unreadable"
    if not isinstance(payload, dict):
        return {}, "receipt root must be an object"
    return payload, ""


def _receipt_errors(
    receipt: Mapping[str, Any],
    *,
    require_closure_ready: bool,
    require_sandbox_execution: bool,
) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name in REQUIRED_TOP_LEVEL_FIELDS:
        if field_name not in receipt:
            errors.append(f"{field_name}_missing")

    action_id = str(receipt.get("action_id", "")).strip()
    receipt_id = str(receipt.get("receipt_id", "")).strip()
    if not action_id:
        errors.append("action_id_empty")
    if receipt_id != f"governed-code-change-loop-receipt-{action_id}":
        errors.append("receipt_id_does_not_bind_action_id")
    if receipt.get("receipt_is_not_terminal_closure") is not True:
        errors.append("receipt_is_not_terminal_closure_not_true")
    if receipt.get("terminal_closure_required") is not True:
        errors.append("terminal_closure_required_not_true")
    if receipt.get("uao_ref") != f"uao://governed-code-change/{action_id}":
        errors.append("uao_ref_does_not_bind_action_id")
    if receipt.get("causal_decision_trace_ref") != f"trace://governed-code-change/{action_id}":
        errors.append("trace_ref_does_not_bind_action_id")

    closure_allowed = receipt.get("closure_allowed")
    if not isinstance(closure_allowed, bool):
        errors.append("closure_allowed_not_bool")
        closure_allowed = False
    expected_status = "closure_ready" if closure_allowed else "blocked"
    if receipt.get("status") != expected_status:
        errors.append("status_does_not_match_closure_allowed")

    solver_outcome = receipt.get("solver_outcome")
    if solver_outcome not in VALID_SOLVER_OUTCOMES:
        errors.append("solver_outcome_invalid")

    required_kinds = _string_list(receipt.get("required_sdlc_receipt_kinds"))
    missing_kinds = _string_list(receipt.get("missing_sdlc_receipt_kinds"))
    blockers = _string_list(receipt.get("closure_blockers"))
    for field_name in (
        "required_sdlc_receipt_kinds",
        "missing_sdlc_receipt_kinds",
        "closure_blockers",
    ):
        if not _is_string_list(receipt.get(field_name)):
            errors.append(f"{field_name}_not_string_list")
    if len(set(required_kinds)) != len(required_kinds):
        errors.append("required_sdlc_receipt_kinds_duplicate")
    if len(set(missing_kinds)) != len(missing_kinds):
        errors.append("missing_sdlc_receipt_kinds_duplicate")
    if len(set(blockers)) != len(blockers):
        errors.append("closure_blockers_duplicate")
    observed = receipt.get("observed_sdlc_receipt_refs")
    if set(REQUIRED_SDLC_RECEIPT_KINDS) - set(required_kinds):
        errors.append("required_sdlc_receipt_kinds_missing_defaults")
    if not isinstance(observed, dict):
        errors.append("observed_sdlc_receipt_refs_not_object")
        observed = {}
    if isinstance(observed, dict):
        for key, value in observed.items():
            if not isinstance(key, str) or not key.strip():
                errors.append("observed_sdlc_receipt_ref_key_empty")
            if not isinstance(value, str) or not value.startswith("receipt://"):
                errors.append("observed_sdlc_receipt_ref_not_receipt_uri")
    expected_missing = tuple(kind for kind in required_kinds if kind not in observed)
    if tuple(missing_kinds) != expected_missing:
        errors.append("missing_sdlc_receipt_kinds_do_not_match_observed")
    for kind in missing_kinds:
        if f"missing_sdlc_{kind}" not in blockers:
            errors.append(f"missing_sdlc_blocker_absent:{kind}")
    if closure_allowed and missing_kinds:
        errors.append("closure_allowed_with_missing_sdlc_receipts")
    if require_closure_ready and not closure_allowed:
        errors.append("closure_ready_required")
    if not closure_allowed and not blockers:
        errors.append("blocked_receipt_requires_closure_blockers")
    if closure_allowed and blockers:
        errors.append("closure_ready_receipt_must_not_have_blockers")
    if closure_allowed and solver_outcome != "SolvedVerified":
        errors.append("closure_ready_requires_solved_verified")

    command_result = receipt.get("command_result")
    if not isinstance(command_result, dict):
        errors.append("command_result_not_object")
    else:
        errors.extend(_command_result_errors(command_result, receipt, blockers))
        if require_sandbox_execution:
            errors.extend(_sandbox_execution_required_errors(command_result))

    lease = receipt.get("lease")
    if not isinstance(lease, dict):
        errors.append("lease_not_object")
    else:
        errors.extend(_lease_errors(lease, receipt))

    metadata = receipt.get("metadata")
    if isinstance(metadata, dict):
        if metadata.get("worker_receipt_not_terminal_closure") is not True:
            errors.append("metadata_worker_receipt_not_terminal_closure_not_true")
        if metadata.get("sdlc_receipts_required_for_terminal_closure") is not True:
            errors.append("metadata_sdlc_receipts_required_not_true")
    else:
        errors.append("metadata_not_object")
    return tuple(dict.fromkeys(errors))


def _command_result_errors(
    command_result: Mapping[str, Any],
    receipt: Mapping[str, Any],
    blockers: tuple[str, ...],
) -> list[str]:
    errors: list[str] = []
    status = command_result.get("status")
    command_receipt = command_result.get("receipt")
    if status not in {"succeeded", "failed", "blocked", "timeout"}:
        errors.append("command_result_status_invalid")
    if not isinstance(command_receipt, dict):
        errors.append("command_result_receipt_not_object")
        return errors
    code_worker_receipt_id = str(command_receipt.get("receipt_id", "")).strip()
    if not code_worker_receipt_id.startswith("code-worker-receipt-"):
        errors.append("code_worker_receipt_id_invalid")
    if receipt.get("code_worker_receipt_ref") != f"receipt://{code_worker_receipt_id}":
        errors.append("code_worker_receipt_ref_mismatch")
    if command_receipt.get("network_enabled") is not False:
        errors.append("code_worker_network_enabled_not_false")
    evidence_refs = command_receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("code_worker_evidence_refs_empty")
    elif not all(isinstance(ref, str) and ref for ref in evidence_refs):
        errors.append("code_worker_evidence_refs_invalid")
    if status != "succeeded" and f"code_worker_status_{status}" not in blockers:
        errors.append("code_worker_status_blocker_absent")
    if status == "succeeded" and any(
        blocker.startswith("code_worker_status_") for blocker in blockers
    ):
        errors.append("succeeded_code_worker_has_status_blocker")
    return errors


def _sandbox_execution_required_errors(command_result: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if command_result.get("status") != "succeeded":
        errors.append("sandbox_execution_required_status_not_succeeded")
    command_receipt = command_result.get("receipt")
    if not isinstance(command_receipt, dict):
        errors.append("sandbox_execution_required_receipt_missing")
        return errors
    sandbox_receipt_id = str(command_receipt.get("sandbox_receipt_id", "")).strip()
    if not sandbox_receipt_id.startswith("sandbox-receipt-"):
        errors.append("sandbox_execution_required_sandbox_receipt_missing")
    metadata = command_receipt.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("sandbox_execution_required_metadata_missing")
        return errors
    if metadata.get("sandbox_verification_status") != "passed":
        errors.append("sandbox_execution_required_verification_not_passed")
    if metadata.get("sandbox_network_disabled") is not True:
        errors.append("sandbox_execution_required_network_not_disabled")
    if metadata.get("sandbox_read_only_rootfs") is not True:
        errors.append("sandbox_execution_required_rootfs_not_read_only")
    evidence_refs = command_receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not any(
        isinstance(ref, str) and ref.startswith("sandbox:sandbox_execution:")
        for ref in evidence_refs
    ):
        errors.append("sandbox_execution_required_evidence_ref_missing")
    return errors


def _lease_errors(
    lease: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    metadata = lease.get("metadata")
    if lease.get("tenant_id") != receipt.get("command_result", {}).get("receipt", {}).get("tenant_id"):
        errors.append("lease_tenant_does_not_match_worker_receipt")
    if lease.get("repository") != receipt.get("command_result", {}).get("receipt", {}).get("repository"):
        errors.append("lease_repository_does_not_match_worker_receipt")
    if lease.get("commit_sha") != receipt.get("command_result", {}).get("receipt", {}).get("commit_sha"):
        errors.append("lease_commit_does_not_match_worker_receipt")
    if lease.get("network_enabled") is not False:
        errors.append("lease_network_enabled_not_false")
    if isinstance(metadata, dict):
        if metadata.get("action_id") != receipt.get("action_id"):
            errors.append("lease_metadata_action_id_mismatch")
        if metadata.get("uao_ref") != receipt.get("uao_ref"):
            errors.append("lease_metadata_uao_ref_mismatch")
        if metadata.get("receipt_is_not_terminal_closure") is not True:
            errors.append("lease_metadata_receipt_boundary_missing")
    else:
        errors.append("lease_metadata_not_object")
    return errors


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


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
) -> GovernedCodeChangeLoopReceiptValidation:
    return GovernedCodeChangeLoopReceiptValidation(
        valid=False,
        receipt_path=_path_label(path),
        status="failed",
        receipt_id="",
        action_id="",
        solver_outcome="",
        closure_allowed=False,
        detail=detail,
        blockers=blockers,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate governed code-change loop receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--require-closure-ready", action="store_true")
    parser.add_argument(
        "--require-sandbox-execution",
        action="store_true",
        help="Require successful sandbox execution evidence, not just a valid blocked receipt.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    result = validate_governed_code_change_loop_receipt(
        args.receipt,
        require_closure_ready=args.require_closure_ready,
        require_sandbox_execution=args.require_sandbox_execution,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"governed code-change loop receipt ok: {result.receipt_id}")
    else:
        for blocker in result.blockers:
            print(f"error: {blocker}: {result.detail}", file=sys.stderr)
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
