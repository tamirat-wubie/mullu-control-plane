#!/usr/bin/env python3
"""Validate read-only worker runtime enablement review packets.

Purpose: review submitted-for-review runtime enablement evidence refs without
accepting evidence, granting authority, enabling runtime dispatch, invoking
workers, emitting receipts, appending receipts, or claiming terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime enablement submitted evidence refs and review packet
schema.
Invariants:
  - The review packet is derived from submitted evidence refs.
  - Review is not evidence acceptance or authority.
  - Repo-local witness refs do not satisfy runtime enablement input names.
  - Missing operator/runtime inputs remain explicit.
  - Mfidel atomicity is preserved.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_submitted_evidence_refs import (  # noqa: E402
    build_runtime_enablement_submitted_evidence_refs,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_enablement_review_packet.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_enablement_review_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_enablement_review_packet_validation.json"
REVIEW_PACKET_ID = "read-only-worker-runtime-enablement-review-packet-foundation-repo-inspection-20260619"
SOURCE_SUBMITTED_REFS_REF = "examples/read_only_worker_runtime_enablement_submitted_evidence_refs.foundation.json"
FALSE_TOP_LEVEL_FIELDS = (
    "evidence_accepted",
    "evidence_rejected",
    "authority_granted",
    "runtime_enablement_allowed",
    "runtime_enablement_executed",
    "runtime_dispatch_admitted",
    "runtime_dispatch_performed",
    "worker_invocation_performed",
    "runtime_receipt_emitted",
    "receipt_append_performed",
    "terminal_closure_performed",
    "success_claim_allowed",
    "secret_values_serialized",
    "connector_authority_allowed",
    "filesystem_write_allowed",
    "external_network_allowed",
)
TRUE_BOUNDARY_FIELDS = (
    "review_packet_is_not_acceptance",
    "review_packet_is_not_authorization",
    "review_packet_is_not_runtime_enablement",
    "review_packet_is_not_dispatch",
    "review_packet_is_not_worker_invocation",
    "review_packet_is_not_receipt_emission",
    "review_packet_is_not_receipt_append",
    "review_packet_is_not_terminal_closure",
    "review_packet_is_not_success_claim",
)
FALSE_RECORD_FIELDS = (
    "accepted",
    "rejected",
    "authority_granted",
    "runtime_enablement_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "terminal_closure_allowed",
    "candidate_ref_satisfies_required_name",
)


@dataclass(frozen=True, slots=True)
class RuntimeEnablementReviewPacketValidation:
    """Validation result for one runtime enablement review packet."""

    valid: bool
    review_packet_path: str
    schema_path: str
    errors: tuple[str, ...]
    review_record_count: int
    reviewed_repo_ref_count: int
    missing_input_count: int
    accepted_evidence_count: int
    runtime_enablement_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_enablement_review_packet() -> dict[str, Any]:
    """Build a review packet from submitted runtime enablement evidence refs."""

    submitted_refs = build_runtime_enablement_submitted_evidence_refs()
    submitted_records = submitted_refs["submitted_records"]
    review_records = [_review_record(record) for record in submitted_records if isinstance(record, dict)]
    reviewed_repo_ref_count = sum(1 for record in review_records if record["review_state"] == "reviewed_not_accepted")
    missing_input_count = sum(1 for record in review_records if record["review_state"] == "blocked_missing_external_evidence")
    return {
        "review_packet_id": REVIEW_PACKET_ID,
        "review_packet_version": "read_only_worker_runtime_enablement_review_packet.v1",
        "source_submitted_evidence_refs_ref": SOURCE_SUBMITTED_REFS_REF,
        "source_submission_id": submitted_refs["submission_id"],
        "source_status_ledger_ref": submitted_refs["source_status_ledger_ref"],
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "review_packet_state": "reviewed_with_missing_inputs",
        "review_state": "reviewed_not_accepted",
        **{field_name: True for field_name in TRUE_BOUNDARY_FIELDS},
        **{field_name: False for field_name in FALSE_TOP_LEVEL_FIELDS},
        "review_records": review_records,
        "review_record_refs": [record["review_record_id"] for record in review_records],
        "reviewed_evidence_refs": [
            ref
            for record in review_records
            for ref in _string_list(record.get("reviewed_evidence_refs"))
        ],
        "missing_evidence_names": [
            name
            for record in review_records
            for name in _string_list(record.get("missing_evidence_names"))
        ],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authority_grant_refs": [],
        "blocked_actions": list(submitted_refs["blocked_actions"]),
        "summary": {
            "source_submitted_record_count": len(submitted_records),
            "review_record_count": len(review_records),
            "reviewed_repo_ref_count": reviewed_repo_ref_count,
            "missing_input_count": missing_input_count,
            "accepted_evidence_count": 0,
            "rejected_evidence_count": 0,
            "authority_grant_count": 0,
            "runtime_enablement_count": 0,
            "dispatch_count": 0,
            "worker_invocation_count": 0,
            "receipt_emission_count": 0,
            "receipt_append_count": 0,
            "terminal_closure_count": 0,
            "blocked_action_count": len(submitted_refs["blocked_actions"]),
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_enablement_review_packet.py",
            "scripts/validate_read_only_worker_runtime_enablement_submitted_evidence_refs.py",
            "tests/test_validate_read_only_worker_runtime_enablement_review_packet.py",
        ],
        "next_action": (
            "Bind operator approval, runtime disablement rollback plan, and trusted runtime clock evidence "
            "before any evidence acceptance or runtime enablement decision."
        ),
    }


def validate_runtime_enablement_review_packet(
    *,
    review_packet_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeEnablementReviewPacketValidation:
    """Validate one runtime enablement review packet."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    review_packet = _load_json_object(review_packet_path, "runtime enablement review packet", errors)
    expected_review_packet = build_runtime_enablement_review_packet()
    if review_packet:
        errors.extend(_validate_schema_instance(schema, review_packet))
        if review_packet != expected_review_packet:
            errors.append("runtime enablement review packet does not match generated submitted-ref review")
        _validate_semantics(review_packet, errors)
    summary = expected_review_packet["summary"]
    return RuntimeEnablementReviewPacketValidation(
        valid=not errors,
        review_packet_path=_path_label(review_packet_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        review_record_count=int(summary["review_record_count"]),
        reviewed_repo_ref_count=int(summary["reviewed_repo_ref_count"]),
        missing_input_count=int(summary["missing_input_count"]),
        accepted_evidence_count=int(summary["accepted_evidence_count"]),
        runtime_enablement_allowed=False,
        next_action=str(expected_review_packet["next_action"]),
    )


def write_runtime_enablement_review_packet_validation(
    validation: RuntimeEnablementReviewPacketValidation,
    output_path: Path,
) -> Path:
    """Write one review packet validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_enablement_review_packet_fixture(output_path: Path) -> Path:
    """Write the generated review packet fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_runtime_enablement_review_packet(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _review_record(submitted_record: dict[str, Any]) -> dict[str, Any]:
    submitted_refs = _string_list(submitted_record.get("submitted_evidence_refs"))
    has_submitted_ref = bool(submitted_refs)
    return {
        "review_record_id": str(submitted_record["submitted_record_id"]).replace(
            "read-only-worker-runtime-enablement-submitted-evidence-",
            "read-only-worker-runtime-enablement-review-",
        ),
        "source_submitted_record_id": str(submitted_record["submitted_record_id"]),
        "source_status_record_id": str(submitted_record["source_status_record_id"]),
        "source_input_id": str(submitted_record["source_input_id"]),
        "input_kind": str(submitted_record["input_kind"]),
        "required_names": list(submitted_record["required_names"]),
        "review_state": "reviewed_not_accepted" if has_submitted_ref else "blocked_missing_external_evidence",
        "proof_state": "Unknown",
        "reviewed": has_submitted_ref,
        "reviewed_evidence_refs": submitted_refs,
        "missing_evidence_names": [] if has_submitted_ref else list(submitted_record["missing_evidence_names"]),
        "accepted": False,
        "rejected": False,
        "authority_granted": False,
        "runtime_enablement_allowed": False,
        "runtime_dispatch_allowed": False,
        "worker_invocation_allowed": False,
        "runtime_receipt_emission_allowed": False,
        "receipt_append_allowed": False,
        "terminal_closure_allowed": False,
        "candidate_ref_satisfies_required_name": False,
        "record_is_not_acceptance": True,
        "record_is_not_authorization": True,
        "record_is_not_runtime_enablement": True,
        "record_is_not_dispatch": True,
        "record_is_not_worker_invocation": True,
        "record_is_not_receipt_emission": True,
        "record_is_not_receipt_append": True,
        "record_is_not_terminal_closure": True,
        "review_note": (
            "Repo-local witness ref reviewed but not accepted; it does not satisfy the required runtime input."
            if has_submitted_ref
            else "Required operator/runtime evidence remains missing and blocks acceptance."
        ),
        "next_action": str(submitted_record["next_action"]),
    }


def _validate_semantics(review_packet: dict[str, Any], errors: list[str]) -> None:
    if review_packet.get("review_packet_id") != REVIEW_PACKET_ID:
        errors.append("review_packet_id is invalid")
    if review_packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must be AwaitingEvidence")
    if review_packet.get("proof_state") != "Unknown":
        errors.append("proof_state must be Unknown")
    if review_packet.get("review_packet_state") != "reviewed_with_missing_inputs":
        errors.append("review_packet_state must be reviewed_with_missing_inputs")
    for field_name in TRUE_BOUNDARY_FIELDS:
        if review_packet.get(field_name) is not True:
            errors.append(f"{field_name} must be true")
    for field_name in FALSE_TOP_LEVEL_FIELDS:
        if review_packet.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    for field_name in ("accepted_evidence_refs", "rejected_evidence_refs", "authority_grant_refs"):
        if review_packet.get(field_name) != []:
            errors.append(f"{field_name} must remain empty")
    records = review_packet.get("review_records")
    if not isinstance(records, list):
        errors.append("review_records must be a list")
        return
    if len(records) != 12:
        errors.append("review_records must contain twelve records")
    for record in records:
        if isinstance(record, dict):
            _validate_record(record, errors)
        else:
            errors.append("review_records entries must be objects")
    if review_packet.get("review_record_refs") != [record.get("review_record_id") for record in records if isinstance(record, dict)]:
        errors.append("review_record_refs must match review record ids")
    _validate_summary(review_packet, records, errors)


def _validate_record(record: dict[str, Any], errors: list[str]) -> None:
    reviewed_refs = _string_list(record.get("reviewed_evidence_refs"))
    missing_names = _string_list(record.get("missing_evidence_names"))
    if reviewed_refs:
        if record.get("review_state") != "reviewed_not_accepted":
            errors.append("records with reviewed refs must be reviewed_not_accepted")
        if record.get("reviewed") is not True:
            errors.append("records with reviewed refs must set reviewed true")
        if missing_names:
            errors.append("records with reviewed refs must not carry missing evidence names")
    else:
        if record.get("review_state") != "blocked_missing_external_evidence":
            errors.append("records without reviewed refs must be blocked_missing_external_evidence")
        if record.get("reviewed") is not False:
            errors.append("records without reviewed refs must set reviewed false")
        if not missing_names:
            errors.append("records without reviewed refs must preserve missing evidence names")
    for field_name in FALSE_RECORD_FIELDS:
        if record.get(field_name) is not False:
            errors.append(f"review record {field_name} must be false")
    for field_name in (
        "record_is_not_acceptance",
        "record_is_not_authorization",
        "record_is_not_runtime_enablement",
        "record_is_not_dispatch",
        "record_is_not_worker_invocation",
        "record_is_not_receipt_emission",
        "record_is_not_receipt_append",
        "record_is_not_terminal_closure",
    ):
        if record.get(field_name) is not True:
            errors.append(f"review record {field_name} must be true")


def _validate_summary(review_packet: dict[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = review_packet.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        return
    object_records = [record for record in records if isinstance(record, dict)]
    expected_counts = {
        "source_submitted_record_count": len(object_records),
        "review_record_count": len(object_records),
        "reviewed_repo_ref_count": sum(1 for record in object_records if record.get("review_state") == "reviewed_not_accepted"),
        "missing_input_count": sum(1 for record in object_records if record.get("review_state") == "blocked_missing_external_evidence"),
        "accepted_evidence_count": sum(1 for record in object_records if record.get("accepted") is True),
        "rejected_evidence_count": sum(1 for record in object_records if record.get("rejected") is True),
        "authority_grant_count": sum(1 for record in object_records if record.get("authority_granted") is True),
        "runtime_enablement_count": sum(1 for record in object_records if record.get("runtime_enablement_allowed") is True),
        "dispatch_count": sum(1 for record in object_records if record.get("runtime_dispatch_allowed") is True),
        "worker_invocation_count": sum(1 for record in object_records if record.get("worker_invocation_allowed") is True),
        "receipt_emission_count": sum(1 for record in object_records if record.get("runtime_receipt_emission_allowed") is True),
        "receipt_append_count": sum(1 for record in object_records if record.get("receipt_append_allowed") is True),
        "terminal_closure_count": sum(1 for record in object_records if record.get("terminal_closure_allowed") is True),
        "blocked_action_count": len(_string_list(review_packet.get("blocked_actions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match review packet state")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate read-only worker runtime enablement review packet.")
    parser.add_argument("--review-packet", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-fixture", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write_fixture:
        write_runtime_enablement_review_packet_fixture(Path(args.review_packet))
    validation = validate_runtime_enablement_review_packet(
        review_packet_path=Path(args.review_packet),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_enablement_review_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime enablement review packet valid")
    else:
        print(f"runtime enablement review packet invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
