#!/usr/bin/env python3
"""Build an external PR execution approval witness.

Purpose: record whether local PR-tool admission has explicit operator approval
for branch push and external pull-request creation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: PR tool admission packet and local schema validation.
Invariants:
  - External execution authority requires local PR-tool admission plus approval.
  - Pending or incomplete witnesses keep external effects disabled.
  - This witness records authority evidence only; it never pushes or opens a PR.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_ADMISSION_PACKET = REPO_ROOT / "examples" / "pr_tool_admission_packet.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "external_pr_execution_approval_witness.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "external_pr_execution_approval_witness.generated.json"
APPROVED_EFFECTS = ("push_branch", "open_external_pr")
REQUIRED_BEFORE_EXECUTION = (
    "local_pr_tool_admission",
    "operator_external_pr_approval",
    "rollback_plan",
    "diff_and_test_receipts",
    "workspace_boundary",
)
FORBIDDEN_WITHOUT_APPROVAL = (
    "push_branch",
    "open_external_pr",
    "merge",
    "deploy",
    "call_connector",
)


@dataclass(frozen=True, slots=True)
class ExternalPrExecutionApprovalWitnessValidation:
    """Validation report for an external PR execution approval witness."""

    ok: bool
    errors: tuple[str, ...]
    witness_path: str
    approval_status: str
    execution_status: str
    external_effects_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_external_pr_execution_approval_witness(
    *,
    admission_packet: Mapping[str, Any],
    admission_packet_path: Path,
    approval_status: str = "pending",
) -> dict[str, Any]:
    """Return an approval witness without executing external PR effects."""

    normalized_approval = _approval_status(approval_status)
    local_admitted = admission_packet.get("local_pr_tool_admitted") is True
    approved = normalized_approval == "approved" and local_admitted
    if not local_admitted:
        execution_status = "awaiting_local_pr_tool_admission"
    elif not approved:
        execution_status = "awaiting_operator_approval"
    else:
        execution_status = "approved_for_external_pr_execution"
    candidate = admission_packet.get("candidate", {})
    if not isinstance(candidate, Mapping):
        candidate = {}
    witness = {
        "witness_id": "external_pr_execution_approval_witness.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _text_or_default(
            admission_packet.get("workflow_run_id"),
            "developer_workflow_v1_foundation_run",
        ),
        "approval_status": normalized_approval,
        "execution_status": execution_status,
        "execution_boundary": "external_repository_pr",
        "operator_approved_external_effects": approved,
        "external_effects_allowed": approved,
        "pr_creation_allowed": approved,
        "branch_push_allowed": approved,
        "approved_external_effects": list(APPROVED_EFFECTS) if approved else [],
        "admission": {
            "admission_status": str(admission_packet.get("admission_status") or "blocked_candidate_incomplete"),
            "local_pr_tool_admitted": local_admitted,
            "admission_packet_hash": str(admission_packet.get("packet_hash") or ""),
            "candidate_title": str(candidate.get("title") or ""),
            "branch_name": str(candidate.get("branch_name") or ""),
            "local_tool_actions_allowed": [str(item) for item in admission_packet.get("local_tool_actions_allowed", ())],
        },
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "rollback": {
            "required": True,
            "branch_delete_command": "git push origin --delete <branch> after confirmed external PR rollback",
            "pr_close_command": "close external pull request through approved PR provider rollback path",
            "evidence_refs": [str(item) for item in candidate.get("rollback_evidence_refs", ())],
        },
        "forbidden_without_approval": list(FORBIDDEN_WITHOUT_APPROVAL),
        "source_refs": {
            "admission_packet_path": _path_label(admission_packet_path),
            "admission_packet_schema": "schemas/pr_tool_admission_packet.schema.json",
            "witness_builder": "python scripts/build_external_pr_execution_approval_witness.py",
        },
        "witness_hash": "",
    }
    witness["witness_hash"] = canonical_hash(witness)
    return witness


def validate_external_pr_execution_approval_witness(
    *,
    witness: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    witness_path: Path = Path("<generated>"),
) -> ExternalPrExecutionApprovalWitnessValidation:
    """Validate schema and external PR execution approval semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(witness)))
    _validate_witness_semantics(witness, errors)
    return ExternalPrExecutionApprovalWitnessValidation(
        ok=not errors,
        errors=tuple(errors),
        witness_path=_path_label(witness_path),
        approval_status=str(witness.get("approval_status") or ""),
        execution_status=str(witness.get("execution_status") or ""),
        external_effects_allowed=witness.get("external_effects_allowed") is True,
    )


def write_external_pr_execution_approval_witness(witness: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic external PR execution approval witness."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(witness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_witness_semantics(witness: Mapping[str, Any], errors: list[str]) -> None:
    admission = witness.get("admission", {})
    if not isinstance(admission, Mapping):
        errors.append("admission_must_be_object")
        return
    local_admitted = admission.get("local_pr_tool_admitted") is True
    approved = witness.get("approval_status") == "approved" and local_admitted
    expected_status = (
        "approved_for_external_pr_execution"
        if approved
        else "awaiting_operator_approval"
        if local_admitted
        else "awaiting_local_pr_tool_admission"
    )
    if witness.get("execution_status") != expected_status:
        errors.append(f"execution_status_must_be:{expected_status}")
    for field_name in (
        "operator_approved_external_effects",
        "external_effects_allowed",
        "pr_creation_allowed",
        "branch_push_allowed",
    ):
        if witness.get(field_name) is not approved:
            errors.append(f"{field_name}_mismatch")
    expected_effects = tuple(APPROVED_EFFECTS) if approved else ()
    if tuple(witness.get("approved_external_effects", ())) != expected_effects:
        errors.append("approved_external_effects_mismatch")
    required = tuple(str(item) for item in witness.get("required_before_execution", ()) if str(item).strip())
    if required != REQUIRED_BEFORE_EXECUTION:
        errors.append("required_before_execution_must_match_canonical_order")
    forbidden = tuple(str(item) for item in witness.get("forbidden_without_approval", ()) if str(item).strip())
    for expected_effect in FORBIDDEN_WITHOUT_APPROVAL:
        if expected_effect not in forbidden:
            errors.append(f"missing_forbidden_without_approval:{expected_effect}")
    if witness.get("witness_hash") != canonical_hash({**dict(witness), "witness_hash": ""}):
        errors.append("witness_hash_mismatch")


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _approval_status(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in {"pending", "approved", "rejected", "deferred"}:
        raise ValueError("approval_status_must_be_pending_approved_rejected_or_deferred")
    return normalized


def _text_or_default(value: object, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse external PR execution approval witness builder arguments."""

    parser = argparse.ArgumentParser(description="Build external PR execution approval witness.")
    parser.add_argument("--admission-packet", default=str(DEFAULT_ADMISSION_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--approval-status", default="pending", choices=("pending", "approved", "rejected", "deferred"))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for external PR execution approval witness building."""

    args = parse_args(argv)
    try:
        admission_packet_path = Path(args.admission_packet)
        admission_packet = _load_json_object(admission_packet_path)
        witness = build_external_pr_execution_approval_witness(
            admission_packet=admission_packet,
            admission_packet_path=admission_packet_path,
            approval_status=str(args.approval_status),
        )
        output_path = write_external_pr_execution_approval_witness(witness, Path(args.output))
        validation = validate_external_pr_execution_approval_witness(
            witness=witness,
            schema_path=Path(args.schema),
            witness_path=output_path,
        )
    except ValueError as exc:
        print(f"EXTERNAL PR EXECUTION APPROVAL WITNESS INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"EXTERNAL PR EXECUTION APPROVAL WITNESS INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(witness, indent=2, sort_keys=True))
    else:
        print(f"EXTERNAL PR EXECUTION APPROVAL WITNESS BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
