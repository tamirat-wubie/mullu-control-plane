#!/usr/bin/env python3
"""Validate read-only worker runtime enablement submitted evidence refs.

Purpose: prove submitted-for-review runtime enablement evidence refs do not
accept evidence, grant authority, enable runtime, dispatch, invoke workers,
emit receipts, append receipts, claim terminal closure, serialize secrets, or
cross connector/filesystem/network boundaries.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime enablement evidence request status ledger and submitted
evidence refs schema.
Invariants:
  - Submitted refs are record-only and review-pending.
  - Existing foundation witnesses can be submitted for review, but none satisfy
    the requested runtime enablement input name by themselves.
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

from scripts.validate_read_only_worker_runtime_enablement_evidence_request_status_ledger import (  # noqa: E402
    BLOCKED_ACTIONS,
    build_runtime_enablement_evidence_request_status_ledger,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_runtime_enablement_submitted_evidence_refs.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_runtime_enablement_submitted_evidence_refs.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "read_only_worker_runtime_enablement_submitted_evidence_refs_validation.json"
SUBMISSION_ID = "read-only-worker-runtime-enablement-submitted-evidence-refs-foundation-repo-inspection-20260619"
SOURCE_STATUS_LEDGER_REF = "examples/read_only_worker_runtime_enablement_evidence_request_status_ledger.foundation.json"
SOURCE_OPERATOR_INPUT_REQUEST_REF = "generated://read-only-worker-runtime-enablement-operator-input-request/default"
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
TRUE_TOP_LEVEL_FIELDS = (
    "evidence_submitted",
    "submitted_refs_are_not_acceptance",
    "submitted_refs_are_not_rejection",
    "submitted_refs_are_not_authorization",
    "submitted_refs_are_not_runtime_enablement",
    "submitted_refs_are_not_dispatch",
    "submitted_refs_are_not_worker_invocation",
    "submitted_refs_are_not_receipt_emission",
    "submitted_refs_are_not_receipt_append",
    "submitted_refs_are_not_terminal_closure",
    "submitted_refs_are_not_success_claim",
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
TRUE_RECORD_FIELDS = (
    "record_is_not_acceptance",
    "record_is_not_authorization",
    "record_is_not_runtime_enablement",
    "record_is_not_dispatch",
    "record_is_not_worker_invocation",
    "record_is_not_receipt_emission",
    "record_is_not_receipt_append",
    "record_is_not_terminal_closure",
)
FOUNDATION_REPO_REFS = {
    "terminal_closure_certificate": "examples/read_only_worker_terminal_closure_witness.foundation.json",
    "runtime_runner_registration": "examples/read_only_worker_runtime_runner_registration_witness.foundation.json",
    "runtime_dispatch_endpoint_registration": "examples/read_only_worker_runtime_dispatch_endpoint_registration_witness.foundation.json",
    "runtime_receipt_emitter_registration": "examples/read_only_worker_runtime_receipt_emitter_registration_witness.foundation.json",
    "runtime_receipt_store_activation": "examples/read_only_worker_runtime_receipt_store_activation_witness.foundation.json",
    "active_runtime_lease_observation": "examples/read_only_worker_active_runtime_lease_admission_witness.foundation.json",
    "uao_dispatch_authorization": "examples/read_only_worker_uao_dispatch_authorization_witness.foundation.json",
    "phi_gov_dispatch_authorization": "examples/read_only_worker_phi_gov_dispatch_authorization_witness.foundation.json",
    "runtime_dispatch_admission": "examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json",
    "runtime_disablement_rollback_plan": "examples/read_only_worker_runtime_disablement_rollback_plan.foundation.json",
    "trusted_runtime_clock": "examples/read_only_worker_trusted_runtime_clock_receipt.foundation.json",
}
MISSING_INPUT_NOTES = {
    "operator_runtime_enablement_approval": "operator runtime enablement approval ref is not present in repository-local evidence",
}


@dataclass(frozen=True, slots=True)
class RuntimeEnablementSubmittedEvidenceRefsValidation:
    """Validation result for runtime enablement submitted evidence refs."""

    valid: bool
    evidence_refs_path: str
    schema_path: str
    errors: tuple[str, ...]
    submitted_record_count: int
    records_with_repo_ref_count: int
    awaiting_operator_evidence_count: int
    submitted_evidence_ref_count: int
    accepted_evidence_count: int
    runtime_enablement_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_enablement_submitted_evidence_refs() -> dict[str, Any]:
    """Build submitted-for-review evidence refs from the status ledger projection."""

    status_ledger = build_runtime_enablement_evidence_request_status_ledger()
    status_records = status_ledger["status_records"]
    submitted_records = [_submitted_record(record) for record in status_records if isinstance(record, dict)]
    submitted_record_refs = [record["submitted_record_id"] for record in submitted_records]
    submitted_evidence_refs = [
        evidence_ref
        for record in submitted_records
        for evidence_ref in _string_list(record.get("submitted_evidence_refs"))
    ]
    records_with_repo_ref_count = sum(1 for record in submitted_records if record["submitted_evidence_refs"])
    awaiting_operator_evidence_count = sum(
        1 for record in submitted_records if record["submission_state"] == "awaiting_operator_evidence"
    )
    return {
        "submission_id": SUBMISSION_ID,
        "submission_version": "read_only_worker_runtime_enablement_submitted_evidence_refs.v1",
        "source_status_ledger_ref": SOURCE_STATUS_LEDGER_REF,
        "source_operator_input_request_ref": SOURCE_OPERATOR_INPUT_REQUEST_REF,
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "submission_state": "partial_repo_refs_submitted_for_review",
        "review_state": "not_evaluated",
        **{field_name: True for field_name in TRUE_TOP_LEVEL_FIELDS},
        **{field_name: False for field_name in FALSE_TOP_LEVEL_FIELDS},
        "submitted_records": submitted_records,
        "submitted_record_refs": submitted_record_refs,
        "submitted_evidence_refs": submitted_evidence_refs,
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authority_grant_refs": [],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "summary": {
            "source_required_input_count": len(status_records),
            "submitted_record_count": len(submitted_records),
            "records_with_repo_ref_count": records_with_repo_ref_count,
            "records_awaiting_operator_evidence_count": awaiting_operator_evidence_count,
            "submitted_evidence_ref_count": len(submitted_evidence_refs),
            "accepted_evidence_count": 0,
            "rejected_evidence_count": 0,
            "authority_grant_count": 0,
            "runtime_enablement_count": 0,
            "dispatch_count": 0,
            "worker_invocation_count": 0,
            "receipt_emission_count": 0,
            "receipt_append_count": 0,
            "terminal_closure_count": 0,
            "unknown_proof_state_count": len(submitted_records),
            "blocked_action_count": len(BLOCKED_ACTIONS),
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_enablement_submitted_evidence_refs.py",
            "scripts/validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.py",
            "tests/test_validate_read_only_worker_runtime_enablement_submitted_evidence_refs.py",
        ],
        "next_action": (
            "Review submitted repo-local evidence refs, then separately bind missing operator approval "
            "before any acceptance or runtime enablement decision."
        ),
    }


def validate_runtime_enablement_submitted_evidence_refs(
    *,
    evidence_refs_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeEnablementSubmittedEvidenceRefsValidation:
    """Validate one runtime enablement submitted evidence refs artifact."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    evidence_refs = _load_json_object(evidence_refs_path, "runtime enablement submitted evidence refs", errors)
    expected_evidence_refs = build_runtime_enablement_submitted_evidence_refs()
    if evidence_refs:
        errors.extend(_validate_schema_instance(schema, evidence_refs))
        if evidence_refs != expected_evidence_refs:
            errors.append("submitted evidence refs do not match generated status ledger projection")
        _validate_semantics(evidence_refs, errors)
    summary = expected_evidence_refs["summary"]
    return RuntimeEnablementSubmittedEvidenceRefsValidation(
        valid=not errors,
        evidence_refs_path=_path_label(evidence_refs_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        submitted_record_count=int(summary["submitted_record_count"]),
        records_with_repo_ref_count=int(summary["records_with_repo_ref_count"]),
        awaiting_operator_evidence_count=int(summary["records_awaiting_operator_evidence_count"]),
        submitted_evidence_ref_count=int(summary["submitted_evidence_ref_count"]),
        accepted_evidence_count=int(summary["accepted_evidence_count"]),
        runtime_enablement_allowed=False,
        next_action=str(expected_evidence_refs["next_action"]),
    )


def write_runtime_enablement_submitted_evidence_refs_validation(
    validation: RuntimeEnablementSubmittedEvidenceRefsValidation,
    output_path: Path,
) -> Path:
    """Write one submitted evidence refs validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def write_runtime_enablement_submitted_evidence_refs_fixture(output_path: Path) -> Path:
    """Write the generated submitted evidence refs fixture."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_runtime_enablement_submitted_evidence_refs(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _submitted_record(status_record: dict[str, Any]) -> dict[str, Any]:
    input_kind = str(status_record["input_kind"])
    evidence_ref = FOUNDATION_REPO_REFS.get(input_kind)
    required_names = list(status_record["required_names"])
    has_repo_ref = evidence_ref is not None
    review_note = (
        "Foundation witness ref submitted for review; it is not accepted evidence and does not satisfy the "
        "requested runtime enablement input name by itself."
        if has_repo_ref
        else MISSING_INPUT_NOTES.get(input_kind, "required operator evidence is not present")
    )
    return {
        "submitted_record_id": str(status_record["status_record_id"]).replace(
            "read-only-worker-runtime-enablement-evidence-status-",
            "read-only-worker-runtime-enablement-submitted-evidence-",
        ),
        "source_status_record_id": str(status_record["status_record_id"]),
        "source_input_id": str(status_record["source_input_id"]),
        "input_kind": input_kind,
        "required_names": required_names,
        "submission_state": "submitted_for_review" if has_repo_ref else "awaiting_operator_evidence",
        "review_state": "not_evaluated",
        "proof_state": "Unknown",
        "submitted_for_review": has_repo_ref,
        **{field_name: False for field_name in FALSE_RECORD_FIELDS},
        "submitted_evidence_refs": [evidence_ref] if has_repo_ref and evidence_ref else [],
        "missing_evidence_names": [] if has_repo_ref else required_names,
        "candidate_ref_kind": "foundation_witness_ref" if has_repo_ref else "missing_operator_input",
        **{field_name: True for field_name in TRUE_RECORD_FIELDS},
        "blocked_action_refs": list(BLOCKED_ACTIONS),
        "review_note": review_note,
        "next_action": str(status_record["next_action"]),
    }


def _validate_semantics(evidence_refs: dict[str, Any], errors: list[str]) -> None:
    if evidence_refs.get("submission_id") != SUBMISSION_ID:
        errors.append("submission_id is invalid")
    for field_name in TRUE_TOP_LEVEL_FIELDS:
        if evidence_refs.get(field_name) is not True:
            errors.append(f"{field_name} must be true")
    for field_name in FALSE_TOP_LEVEL_FIELDS:
        if evidence_refs.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    for field_name in ("accepted_evidence_refs", "rejected_evidence_refs", "authority_grant_refs"):
        if evidence_refs.get(field_name) != []:
            errors.append(f"{field_name} must remain empty")
    if set(_string_list(evidence_refs.get("blocked_actions"))) != set(BLOCKED_ACTIONS):
        errors.append("blocked_actions must match runtime enablement blocked actions")

    records = evidence_refs.get("submitted_records")
    if not isinstance(records, list):
        errors.append("submitted_records must be a list")
        return
    if len(records) != 12:
        errors.append("submitted_records must contain twelve records")
    if evidence_refs.get("submitted_record_refs") != [
        record.get("submitted_record_id") for record in records if isinstance(record, dict)
    ]:
        errors.append("submitted_record_refs must match submitted record ids")
    observed_evidence_refs: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            errors.append("submitted_records entries must be objects")
            continue
        _validate_record(record, errors)
        observed_evidence_refs.extend(_string_list(record.get("submitted_evidence_refs")))
    if evidence_refs.get("submitted_evidence_refs") != observed_evidence_refs:
        errors.append("submitted_evidence_refs must match record submitted evidence refs")
    for evidence_ref in observed_evidence_refs:
        if not (REPO_ROOT / evidence_ref).exists():
            errors.append(f"submitted evidence ref missing: {evidence_ref}")
    _validate_summary(evidence_refs, errors)


def _validate_record(record: dict[str, Any], errors: list[str]) -> None:
    input_kind = str(record.get("input_kind", ""))
    expected_ref = FOUNDATION_REPO_REFS.get(input_kind)
    evidence_refs = _string_list(record.get("submitted_evidence_refs"))
    missing_names = _string_list(record.get("missing_evidence_names"))
    for field_name in TRUE_RECORD_FIELDS:
        if record.get(field_name) is not True:
            errors.append(f"submitted record {field_name} must be true")
    for field_name in FALSE_RECORD_FIELDS:
        if record.get(field_name) is not False:
            errors.append(f"submitted record {field_name} must be false")
    if expected_ref:
        if record.get("submission_state") != "submitted_for_review":
            errors.append("repo-ref records must be submitted_for_review")
        if record.get("submitted_for_review") is not True:
            errors.append("repo-ref records must set submitted_for_review true")
        if evidence_refs != [expected_ref]:
            errors.append("repo-ref records must carry the expected submitted evidence ref")
        if missing_names:
            errors.append("repo-ref records must not carry missing evidence names")
    else:
        if record.get("submission_state") != "awaiting_operator_evidence":
            errors.append("missing-input records must be awaiting_operator_evidence")
        if record.get("submitted_for_review") is not False:
            errors.append("missing-input records must set submitted_for_review false")
        if evidence_refs:
            errors.append("missing-input records must not carry submitted evidence refs")
        if missing_names != _string_list(record.get("required_names")):
            errors.append("missing-input records must list required names as missing evidence")
    if set(_string_list(record.get("blocked_action_refs"))) != set(BLOCKED_ACTIONS):
        errors.append("submitted record blocked_action_refs must match blocked actions")


def _validate_summary(evidence_refs: dict[str, Any], errors: list[str]) -> None:
    records = evidence_refs.get("submitted_records")
    summary = evidence_refs.get("summary")
    if not isinstance(records, list) or not isinstance(summary, dict):
        errors.append("summary requires submitted_records list")
        return
    submitted_evidence_refs = [
        evidence_ref
        for record in records
        if isinstance(record, dict)
        for evidence_ref in _string_list(record.get("submitted_evidence_refs"))
    ]
    expected_counts = {
        "source_required_input_count": len(records),
        "submitted_record_count": len(records),
        "records_with_repo_ref_count": sum(1 for record in records if isinstance(record, dict) and _string_list(record.get("submitted_evidence_refs"))),
        "records_awaiting_operator_evidence_count": sum(1 for record in records if isinstance(record, dict) and record.get("submission_state") == "awaiting_operator_evidence"),
        "submitted_evidence_ref_count": len(submitted_evidence_refs),
        "accepted_evidence_count": 0,
        "rejected_evidence_count": 0,
        "authority_grant_count": 0,
        "runtime_enablement_count": 0,
        "dispatch_count": 0,
        "worker_invocation_count": 0,
        "receipt_emission_count": 0,
        "receipt_append_count": 0,
        "terminal_closure_count": 0,
        "unknown_proof_state_count": sum(1 for record in records if isinstance(record, dict) and record.get("proof_state") == "Unknown"),
        "blocked_action_count": len(_string_list(evidence_refs.get("blocked_actions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match submitted refs state")


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
    raise ValueError("non-finite JSON constants are not permitted")


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
    """Parse submitted evidence refs validation arguments."""

    parser = argparse.ArgumentParser(description="Validate read-only worker runtime enablement submitted evidence refs.")
    parser.add_argument("--evidence-refs", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-fixture", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for submitted evidence refs validation."""

    args = parse_args(argv)
    if args.write_fixture:
        write_runtime_enablement_submitted_evidence_refs_fixture(Path(args.evidence_refs))
    validation = validate_runtime_enablement_submitted_evidence_refs(
        evidence_refs_path=Path(args.evidence_refs),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_enablement_submitted_evidence_refs_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime enablement submitted evidence refs valid")
    else:
        print(f"runtime enablement submitted evidence refs invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
