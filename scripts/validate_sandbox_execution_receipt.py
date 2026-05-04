#!/usr/bin/env python3
"""Validate governed sandbox execution receipts.

Purpose: provide a reusable receipt gate for sandboxed computer, browser,
    document, and worker execution evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.sandbox_runner receipt shape and Python standard library.
Invariants:
  - Missing, unreadable, or malformed receipts fail closed.
  - Isolation fields must prove no-network, read-only rootfs, and /workspace.
  - Passing receipts must not report forbidden effects.
  - Optional capability and workspace-mutation constraints are explicit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HEX_64 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FIELDS = (
    "receipt_id",
    "request_id",
    "tenant_id",
    "capability_id",
    "sandbox_id",
    "image",
    "command_hash",
    "docker_args_hash",
    "stdout_hash",
    "stderr_hash",
    "returncode",
    "network_disabled",
    "read_only_rootfs",
    "workspace_mount",
    "forbidden_effects_observed",
    "verification_status",
    "changed_file_count",
    "changed_file_refs",
    "evidence_refs",
)


@dataclass(frozen=True, slots=True)
class SandboxReceiptValidation:
    """Validation result for one sandbox execution receipt."""

    valid: bool
    receipt_path: str
    status: str
    receipt_id: str
    capability_id: str
    verification_status: str
    detail: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def validate_sandbox_execution_receipt(
    receipt_path: Path,
    *,
    capability_prefix: str = "",
    require_passed: bool = True,
    require_no_workspace_changes: bool = False,
) -> SandboxReceiptValidation:
    """Validate one sandbox execution receipt or evidence envelope."""
    payload, load_error = _load_payload(receipt_path)
    if load_error:
        return _invalid(receipt_path, load_error, ("sandbox_receipt_unreadable",))

    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else payload
    if not isinstance(receipt, dict):
        return _invalid(receipt_path, "receipt root must be an object", ("sandbox_receipt_unreadable",))

    errors = _receipt_errors(
        receipt,
        capability_prefix=capability_prefix,
        require_passed=require_passed,
        require_no_workspace_changes=require_no_workspace_changes,
    )
    receipt_id = str(receipt.get("receipt_id", "")).strip()
    capability_id = str(receipt.get("capability_id", "")).strip()
    verification_status = str(receipt.get("verification_status", "")).strip()
    if errors:
        return SandboxReceiptValidation(
            valid=False,
            receipt_path=str(receipt_path),
            status="failed",
            receipt_id=receipt_id,
            capability_id=capability_id,
            verification_status=verification_status,
            detail=",".join(errors),
            blockers=("sandbox_receipt_invalid",),
        )
    return SandboxReceiptValidation(
        valid=True,
        receipt_path=str(receipt_path),
        status="passed",
        receipt_id=receipt_id,
        capability_id=capability_id,
        verification_status=verification_status,
        detail="sandbox receipt verified",
        blockers=(),
    )


def _load_payload(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "sandbox receipt file not found"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "sandbox receipt unreadable"
    if not isinstance(payload, dict):
        return {}, "sandbox receipt root must be an object"
    return payload, ""


def _receipt_errors(
    receipt: dict[str, Any],
    *,
    capability_prefix: str,
    require_passed: bool,
    require_no_workspace_changes: bool,
) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in receipt:
            errors.append(f"{field_name}_missing")

    receipt_id = str(receipt.get("receipt_id", "")).strip()
    if not receipt_id.startswith("sandbox-receipt-"):
        errors.append("receipt_id_not_sandbox_receipt")
    for field_name in ("request_id", "tenant_id", "capability_id", "sandbox_id", "image"):
        if not str(receipt.get(field_name, "")).strip():
            errors.append(f"{field_name}_empty")
    for field_name in ("command_hash", "docker_args_hash", "stdout_hash", "stderr_hash"):
        if not _is_hex_64(receipt.get(field_name)):
            errors.append(f"{field_name}_not_sha256")
    if receipt.get("network_disabled") is not True:
        errors.append("network_disabled_not_true")
    if receipt.get("read_only_rootfs") is not True:
        errors.append("read_only_rootfs_not_true")
    if receipt.get("workspace_mount") != "/workspace":
        errors.append("workspace_mount_not_workspace")
    if receipt.get("forbidden_effects_observed") is not False:
        errors.append("forbidden_effects_observed_not_false")
    if require_passed and receipt.get("verification_status") != "passed":
        errors.append("verification_status_not_passed")
    returncode = receipt.get("returncode")
    if returncode is not None and (not isinstance(returncode, int) or isinstance(returncode, bool)):
        errors.append("returncode_not_int_or_null")
    if require_passed and returncode != 0:
        errors.append("returncode_not_zero")
    if capability_prefix and not str(receipt.get("capability_id", "")).startswith(capability_prefix):
        errors.append("capability_id_prefix_mismatch")

    changed_refs = receipt.get("changed_file_refs")
    changed_count = receipt.get("changed_file_count")
    if not isinstance(changed_refs, list):
        errors.append("changed_file_refs_not_list")
    if not isinstance(changed_count, int) or isinstance(changed_count, bool):
        errors.append("changed_file_count_not_int")
    elif isinstance(changed_refs, list) and changed_count != len(changed_refs):
        errors.append("changed_file_count_mismatch")
    if require_no_workspace_changes and changed_count != 0:
        errors.append("changed_file_count_not_zero")
    if require_no_workspace_changes and changed_refs not in ([], ()):
        errors.append("changed_file_refs_not_empty")
    if isinstance(changed_refs, list) and not all(
        str(ref).startswith("workspace_diff:") for ref in changed_refs
    ):
        errors.append("changed_file_refs_not_workspace_diff")

    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("evidence_refs_empty")
    elif not all(str(ref).startswith("sandbox_execution:") for ref in evidence_refs):
        errors.append("evidence_refs_not_sandbox_execution")
    return tuple(dict.fromkeys(errors))


def _is_hex_64(value: Any) -> bool:
    return isinstance(value, str) and HEX_64.match(value) is not None


def _invalid(
    path: Path,
    detail: str,
    blockers: tuple[str, ...],
) -> SandboxReceiptValidation:
    del path
    return SandboxReceiptValidation(
        valid=False,
        receipt_path="",
        status="failed",
        receipt_id="",
        capability_id="",
        verification_status="",
        detail=detail,
        blockers=blockers,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse sandbox receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate governed sandbox execution receipt.")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--capability-prefix", default="")
    parser.add_argument("--allow-non-passed", action="store_true")
    parser.add_argument("--require-no-workspace-changes", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for sandbox receipt validation."""
    args = parse_args(argv)
    result = validate_sandbox_execution_receipt(
        Path(args.receipt),
        capability_prefix=args.capability_prefix,
        require_passed=not args.allow_non_passed,
        require_no_workspace_changes=args.require_no_workspace_changes,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"sandbox receipt ok: {result.receipt_id}")
    else:
        for blocker in result.blockers:
            print(f"error: {blocker}: {result.detail}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
