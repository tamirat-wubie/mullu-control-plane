#!/usr/bin/env python3
"""Build a local PR candidate packet from PR-preparation approval.

Purpose: create a projection-only packet that describes a local PR candidate
without opening an external pull request, pushing a branch, merging, deploying,
or calling connectors.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: PR-preparation approval packet and local schema validation.
Invariants:
  - Candidate readiness requires approved local PR preparation and complete
    sandbox receipts.
  - Generated packets keep external effects, PR creation, and branch push false.
  - Rollback evidence is preserved from receipt refs when available.
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


DEFAULT_APPROVAL_PACKET = REPO_ROOT / "examples" / "pr_preparation_approval_packet.foundation.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "local_pr_candidate_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "local_pr_candidate_packet.generated.json"
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
class LocalPrCandidatePacketValidation:
    """Validation report for a local PR candidate packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    candidate_status: str
    candidate_ready: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_local_pr_candidate_packet(
    *,
    approval_packet: Mapping[str, Any],
    approval_packet_path: Path,
    title: str,
    branch_name: str,
    summary: str,
) -> dict[str, Any]:
    """Return a local PR candidate packet without external PR authority."""

    bundle = approval_packet.get("bundle", {})
    if not isinstance(bundle, Mapping):
        bundle = {}
    approval_status = str(approval_packet.get("approval_status") or "pending")
    bundle_ready = bundle.get("ready") is True
    candidate_ready = approval_status == "approved" and bundle_ready
    if not bundle_ready:
        candidate_status = "awaiting_receipts"
    elif approval_status != "approved":
        candidate_status = "awaiting_operator_approval"
    else:
        candidate_status = "ready_for_pr_tool"
    packet = {
        "packet_id": "local_pr_candidate_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": _text_or_default(approval_packet.get("workflow_run_id"), "developer_workflow_v1_foundation_run"),
        "candidate_status": candidate_status,
        "candidate_ready": candidate_ready,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "pr_creation_allowed": False,
        "branch_push_allowed": False,
        "title": _required_text(title, "title"),
        "branch_name": _required_text(branch_name, "branch_name"),
        "summary": _required_text(summary, "summary"),
        "approval": {
            "approval_status": approval_status,
            "approval_required": approval_packet.get("approval_required") is True,
            "authorized_effect": str(approval_packet.get("authorized_effect_after_approval") or ""),
        },
        "bundle": {
            "ready": bundle_ready,
            "completed_count": int(bundle.get("completed_count", 0) or 0),
            "required_count": int(bundle.get("required_count", 0) or 0),
            "receipt_ids": [str(item) for item in bundle.get("receipt_ids", ())],
        },
        "diff_refs": ["sandbox_patch_receipt", "diff_review_receipt"] if bundle_ready else [],
        "test_refs": ["test_gate_receipt"] if bundle_ready else [],
        "rollback": {
            "required": True,
            "command": "use sandbox receipt rollback_command before discarding candidate",
            "evidence_refs": ["sandbox_patch_receipt"] if bundle_ready else [],
        },
        "forbidden_effects": list(FORBIDDEN_EFFECTS),
        "source_refs": {
            "approval_packet_path": _path_label(approval_packet_path),
            "approval_packet_schema": "schemas/pr_preparation_approval_packet.schema.json",
            "candidate_builder": "python scripts/build_local_pr_candidate_packet.py",
        },
        "packet_hash": "",
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def validate_local_pr_candidate_packet(
    *,
    packet: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = Path("<generated>"),
) -> LocalPrCandidatePacketValidation:
    """Validate schema and local-only candidate semantics."""

    errors: list[str] = []
    schema = _load_json_object(schema_path)
    errors.extend(str(error) for error in _validate_schema_instance(schema, dict(packet)))
    _validate_packet_semantics(packet, errors)
    return LocalPrCandidatePacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=_path_label(packet_path),
        candidate_status=str(packet.get("candidate_status") or ""),
        candidate_ready=packet.get("candidate_ready") is True,
    )


def write_local_pr_candidate_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic local PR candidate packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str]) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append("external_effects_allowed_must_be_false")
    if packet.get("pr_creation_allowed") is not False:
        errors.append("pr_creation_allowed_must_be_false")
    if packet.get("branch_push_allowed") is not False:
        errors.append("branch_push_allowed_must_be_false")
    for expected_effect in FORBIDDEN_EFFECTS:
        effects = tuple(str(effect) for effect in packet.get("forbidden_effects", ()) if str(effect).strip())
        if expected_effect not in effects:
            errors.append(f"missing_forbidden_effect:{expected_effect}")
    approval = packet.get("approval", {})
    bundle = packet.get("bundle", {})
    if not isinstance(approval, Mapping) or not isinstance(bundle, Mapping):
        errors.append("approval_and_bundle_must_be_objects")
        return
    should_be_ready = approval.get("approval_status") == "approved" and bundle.get("ready") is True
    if packet.get("candidate_ready") is not should_be_ready:
        errors.append("candidate_ready_mismatch")
    if should_be_ready and packet.get("candidate_status") != "ready_for_pr_tool":
        errors.append("approved_complete_candidate_must_be_ready_for_pr_tool")
    if tuple(bundle.get("receipt_ids", ())) != EXPECTED_RECEIPT_IDS:
        errors.append("receipt_ids_must_match_canonical_order")
    if packet.get("packet_hash") != canonical_hash({**dict(packet), "packet_hash": ""}):
        errors.append("packet_hash_mismatch")


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


def _text_or_default(value: object, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _required_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name}_required")
    return normalized


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse local PR candidate packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build local PR candidate packet.")
    parser.add_argument("--approval-packet", default=str(DEFAULT_APPROVAL_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--title", default="Prepare governed local Developer Workflow candidate")
    parser.add_argument("--branch-name", default="codex/developer-workflow-local-candidate")
    parser.add_argument("--summary", default="Local PR candidate packet prepared from Developer Workflow receipts.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for local PR candidate packet building."""

    args = parse_args(argv)
    try:
        approval_packet_path = Path(args.approval_packet)
        approval_packet = _load_json_object(approval_packet_path)
        packet = build_local_pr_candidate_packet(
            approval_packet=approval_packet,
            approval_packet_path=approval_packet_path,
            title=str(args.title),
            branch_name=str(args.branch_name),
            summary=str(args.summary),
        )
        output_path = write_local_pr_candidate_packet(packet, Path(args.output))
        validation = validate_local_pr_candidate_packet(
            packet=packet,
            schema_path=Path(args.schema),
            packet_path=output_path,
        )
    except ValueError as exc:
        print(f"LOCAL PR CANDIDATE PACKET INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"LOCAL PR CANDIDATE PACKET INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"LOCAL PR CANDIDATE PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
