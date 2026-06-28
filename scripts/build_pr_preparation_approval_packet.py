#!/usr/bin/env python3
"""Build a local PR-preparation approval packet from sandbox receipts.

Purpose: convert the Developer Workflow v1 sandbox receipt bundle into a
projection-only operator approval packet for local PR candidate preparation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: sandbox receipt bundle JSON and canonical schema validation.
Invariants:
  - The packet does not create a branch, open a PR, push, merge, deploy, or call
    connectors.
  - Approval only authorizes local PR candidate packet preparation.
  - External PR creation remains forbidden in every emitted packet.
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


DEFAULT_BUNDLE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "pr_preparation_approval_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "pr_preparation_approval_packet.generated.json"
EXPECTED_RECEIPT_IDS = (
    "sandbox_patch_receipt",
    "test_gate_receipt",
    "diff_review_receipt",
    "terminal_receipt",
)
FORBIDDEN_EFFECTS = (
    "open_external_pr",
    "push_branch",
    "merge",
    "deploy",
    "call_connector",
)


@dataclass(frozen=True, slots=True)
class PrPreparationApprovalPacketValidation:
    """Validation report for a generated PR-preparation approval packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    packet_status: str
    bundle_ready: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_pr_preparation_approval_packet(
    *,
    sandbox_receipt_bundle: Mapping[str, Any],
    bundle_path: Path,
    approval_status: str = "pending",
) -> dict[str, Any]:
    """Return a projection-only local PR-preparation approval packet."""

    normalized_approval_status = _approval_status(approval_status)
    receipts = _receipt_ids(sandbox_receipt_bundle)
    completed_count = int(sandbox_receipt_bundle.get("completed_count", 0) or 0)
    required_count = int(sandbox_receipt_bundle.get("required_count", len(EXPECTED_RECEIPT_IDS)) or 0)
    bundle_status = str(sandbox_receipt_bundle.get("bundle_status") or "unknown")
    bundle_ready = (
        bundle_status == "receipts_complete"
        and completed_count == len(EXPECTED_RECEIPT_IDS)
        and required_count == len(EXPECTED_RECEIPT_IDS)
        and tuple(receipts) == EXPECTED_RECEIPT_IDS
    )
    packet_status = _packet_status(bundle_ready=bundle_ready, approval_status=normalized_approval_status)
    next_action = _next_action(bundle_ready=bundle_ready, approval_status=normalized_approval_status)
    packet = {
        "packet_id": "pr_preparation_approval_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _text_or_default(
            sandbox_receipt_bundle.get("workflow_run_id"),
            "developer_workflow_v1_foundation_run",
        ),
        "packet_status": packet_status,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "approval_required": True,
        "approval_status": normalized_approval_status,
        "next_action": next_action,
        "bundle": {
            "bundle_id": "developer_workflow_sandbox_receipt_bundle.v1",
            "bundle_status": bundle_status,
            "ready": bundle_ready,
            "completed_count": completed_count,
            "required_count": required_count,
            "receipt_ids": list(receipts),
        },
        "decision_request": {
            "decision_id": "approve_pr_preparation",
            "prompt": "Approve preparation of a local PR candidate packet only; external PR creation remains blocked.",
            "allowed_decisions": ["approve_prepare_pr_candidate", "reject", "defer"],
            "default_decision": "defer",
        },
        "authorized_effect_after_approval": "prepare_local_pr_candidate_packet",
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
        "source_refs": {
            "bundle_path": _path_label(bundle_path),
            "bundle_schema": "schemas/developer_workflow_sandbox_receipt_bundle.schema.json",
            "bundle_validator": "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py",
            "packet_builder": "python scripts/build_pr_preparation_approval_packet.py",
        },
        "packet_hash": "",
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def validate_pr_preparation_approval_packet(
    *,
    packet: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = Path("<generated>"),
) -> PrPreparationApprovalPacketValidation:
    """Validate packet schema and hard local-only approval semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(packet)))
    _validate_packet_semantics(packet, errors)
    return PrPreparationApprovalPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=_path_label(packet_path),
        packet_status=str(packet.get("packet_status") or ""),
        bundle_ready=bool(packet.get("bundle", {}).get("ready")) if isinstance(packet.get("bundle"), Mapping) else False,
    )


def write_pr_preparation_approval_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write packet JSON deterministically."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str]) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append("external_effects_allowed_must_be_false")
    if packet.get("pr_creation_allowed") is not False:
        errors.append("pr_creation_allowed_must_be_false")
    if packet.get("execution_boundary") != "local_lab_only":
        errors.append("execution_boundary_must_be_local_lab_only")
    forbidden_effects = tuple(str(effect) for effect in packet.get("forbidden_effects", ()) if str(effect).strip())
    for expected_effect in FORBIDDEN_EFFECTS:
        if expected_effect not in forbidden_effects:
            errors.append(f"missing_forbidden_effect:{expected_effect}")
    bundle = packet.get("bundle", {})
    if not isinstance(bundle, Mapping):
        errors.append("bundle_must_be_object")
        return
    bundle_ready = bundle.get("ready") is True
    approval_status = str(packet.get("approval_status") or "")
    if approval_status == "approved" and not bundle_ready:
        errors.append("approval_requires_complete_receipts")
    if bundle_ready and approval_status == "approved" and packet.get("packet_status") != "approval_recorded":
        errors.append("approved_ready_bundle_must_record_approval")
    if bundle_ready and approval_status != "approved" and packet.get("packet_status") != "awaiting_operator_approval":
        errors.append("ready_bundle_without_approval_must_await_operator_approval")
    if not bundle_ready and packet.get("packet_status") != "awaiting_receipts":
        errors.append("incomplete_bundle_must_await_receipts")
    if tuple(bundle.get("receipt_ids", ())) != EXPECTED_RECEIPT_IDS:
        errors.append("receipt_ids_must_match_canonical_order")
    expected_hash = canonical_hash({**dict(packet), "packet_hash": ""})
    if packet.get("packet_hash") != expected_hash:
        errors.append("packet_hash_mismatch")


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _receipt_ids(bundle: Mapping[str, Any]) -> tuple[str, ...]:
    receipts = bundle.get("receipts", ())
    if not isinstance(receipts, list):
        return ()
    return tuple(
        str(receipt.get("receipt_id") or "")
        for receipt in receipts
        if isinstance(receipt, Mapping)
    )


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


def _text_or_default(value: object, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _approval_status(value: str) -> str:
    normalized = str(value or "pending").strip().lower()
    if normalized not in {"pending", "approved", "rejected", "deferred"}:
        raise ValueError("approval_status_must_be_pending_approved_rejected_or_deferred")
    return normalized


def _packet_status(*, bundle_ready: bool, approval_status: str) -> str:
    if not bundle_ready:
        return "awaiting_receipts"
    if approval_status == "approved":
        return "approval_recorded"
    return "awaiting_operator_approval"


def _next_action(*, bundle_ready: bool, approval_status: str) -> str:
    if not bundle_ready:
        return "complete sandbox patch, test, diff, and terminal receipts"
    if approval_status == "approved":
        return "prepare local PR candidate packet"
    if approval_status == "rejected":
        return "revise or stop local PR candidate preparation request"
    if approval_status == "deferred":
        return "wait for operator decision on local PR candidate preparation"
    return "approve local PR candidate packet preparation"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse PR-preparation approval packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build local PR-preparation approval packet.")
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--approval-status", default="pending", choices=("pending", "approved", "rejected", "deferred"))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the PR-preparation approval packet builder."""

    args = parse_args(argv)
    try:
        bundle_path = Path(args.bundle)
        bundle = _load_json_object(bundle_path)
        packet = build_pr_preparation_approval_packet(
            sandbox_receipt_bundle=bundle,
            bundle_path=bundle_path,
            approval_status=str(args.approval_status),
        )
        output_path = write_pr_preparation_approval_packet(packet, Path(args.output))
        validation = validate_pr_preparation_approval_packet(
            packet=packet,
            schema_path=Path(args.schema),
            packet_path=output_path,
        )
    except ValueError as exc:
        print(f"PR PREPARATION APPROVAL PACKET INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"PR PREPARATION APPROVAL PACKET INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"PR PREPARATION APPROVAL PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
