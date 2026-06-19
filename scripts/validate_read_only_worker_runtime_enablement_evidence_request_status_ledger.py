#!/usr/bin/env python3
"""Validate read-only worker runtime enablement evidence request status ledgers.

Purpose: prove the runtime enablement evidence request status ledger is a
read-only status projection, not an evidence submission or authority grant.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime enablement operator input request emitter and status
ledger schema.
Invariants:
  - The ledger is derived from the operator input request.
  - Evidence submission, acceptance, rejection, authorization, runtime
    enablement, dispatch, worker invocation, receipt emission, receipt append,
    terminal closure, success claim, connector authority, filesystem writes,
    network access, and secret serialization remain denied.
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

from scripts.emit_read_only_worker_runtime_enablement_operator_input_request import (  # noqa: E402
    emit_runtime_enablement_operator_input_request,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "read_only_worker_runtime_enablement_evidence_request_status_ledger.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "read_only_worker_runtime_enablement_evidence_request_status_ledger.foundation.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "read_only_worker_runtime_enablement_evidence_request_status_ledger_validation.json"
)
LEDGER_ID = (
    "read-only-worker-runtime-enablement-evidence-request-status-ledger-"
    "foundation-repo-inspection-20260619"
)
BLOCKED_ACTIONS = (
    "read_only_worker_runtime_enablement",
    "read_only_worker_runtime_dispatch_admission",
    "read_only_worker_runtime_dispatch",
    "read_only_worker_invocation",
    "read_only_worker_runtime_receipt_emission",
    "read_only_worker_receipt_append",
    "read_only_worker_terminal_closure_claim",
)
FALSE_LEDGER_FIELDS = (
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
    "evidence_submitted",
    "evidence_accepted",
    "evidence_rejected",
    "authority_granted",
)
TRUE_LEDGER_FIELDS = (
    "status_ledger_issued",
    "status_ledger_is_not_evidence",
    "status_ledger_is_not_submission",
    "status_ledger_is_not_acceptance",
    "status_ledger_is_not_rejection",
    "status_ledger_is_not_authorization",
    "status_ledger_is_not_runtime_enablement",
    "status_ledger_is_not_dispatch",
    "status_ledger_is_not_worker_invocation",
    "status_ledger_is_not_receipt_emission",
    "status_ledger_is_not_receipt_append",
    "status_ledger_is_not_terminal_closure",
    "status_ledger_is_not_success_claim",
)
FALSE_RECORD_FIELDS = (
    "evidence_submitted",
    "evidence_accepted",
    "evidence_rejected",
    "authority_granted",
    "runtime_enablement_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "terminal_closure_allowed",
)
TRUE_RECORD_FIELDS = (
    "required",
    "evidence_required",
    "status_only",
    "status_is_not_evidence",
    "status_is_not_submission",
    "status_is_not_acceptance",
    "status_is_not_rejection",
    "status_is_not_authorization",
    "status_is_not_runtime_enablement",
    "status_is_not_dispatch",
    "status_is_not_worker_invocation",
    "status_is_not_receipt_emission",
    "status_is_not_receipt_append",
    "status_is_not_terminal_closure",
)


@dataclass(frozen=True, slots=True)
class RuntimeEnablementEvidenceRequestStatusLedgerValidation:
    """Validation result for one runtime enablement evidence request status ledger."""

    valid: bool
    ledger_path: str
    schema_path: str
    errors: tuple[str, ...]
    status_record_count: int
    awaiting_evidence_count: int
    submitted_evidence_count: int
    accepted_evidence_count: int
    runtime_enablement_allowed: bool
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation result."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_enablement_evidence_request_status_ledger() -> dict[str, Any]:
    """Build the expected status ledger from the runtime enablement operator request."""

    request = emit_runtime_enablement_operator_input_request()
    request_payload = request.as_dict()
    required_inputs = request_payload["required_inputs"]
    status_records = [
        _status_record(required_input)
        for required_input in required_inputs
        if isinstance(required_input, dict)
    ]
    status_record_refs = [record["status_record_id"] for record in status_records]
    return {
        "ledger_id": LEDGER_ID,
        "ledger_version": "read_only_worker_runtime_enablement_evidence_request_status_ledger.v1",
        "source_operator_input_request_ref": (
            "generated://read-only-worker-runtime-enablement-operator-input-request/default"
        ),
        "source_runtime_enablement_witness_ref": (
            "examples/read_only_worker_runtime_enablement_witness.foundation.json"
        ),
        "selected_worker_path": "read_only_repo_inspection",
        "solver_outcome": "AwaitingEvidence",
        "proof_state": "Unknown",
        "ledger_state": "request_status_only",
        **{field_name: True for field_name in TRUE_LEDGER_FIELDS},
        **{field_name: False for field_name in FALSE_LEDGER_FIELDS},
        "status_records": status_records,
        "status_record_refs": status_record_refs,
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authority_grant_refs": [],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "summary": {
            "source_required_input_count": len(required_inputs),
            "status_record_count": len(status_records),
            "awaiting_evidence_count": len(status_records),
            "submitted_evidence_count": 0,
            "accepted_evidence_count": 0,
            "rejected_evidence_count": 0,
            "authority_grant_count": 0,
            "runtime_enablement_count": 0,
            "dispatch_count": 0,
            "worker_invocation_count": 0,
            "receipt_emission_count": 0,
            "receipt_append_count": 0,
            "terminal_closure_count": 0,
            "unknown_proof_state_count": len(status_records),
            "blocked_action_count": len(BLOCKED_ACTIONS),
        },
        "validators": [
            "scripts/validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.py",
            "scripts/emit_read_only_worker_runtime_enablement_operator_input_request.py",
            "tests/test_validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.py",
        ],
        "next_action": (
            "Submit governed evidence refs separately; this ledger only reports unresolved runtime "
            "enablement evidence request status."
        ),
    }


def validate_runtime_enablement_evidence_request_status_ledger(
    *,
    ledger_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> RuntimeEnablementEvidenceRequestStatusLedgerValidation:
    """Validate one runtime enablement evidence request status ledger."""

    errors: list[str] = []
    schema = _load_schema(schema_path)
    ledger = _load_json_object(ledger_path, "runtime enablement evidence request status ledger", errors)
    expected_ledger = build_runtime_enablement_evidence_request_status_ledger()
    if ledger:
        errors.extend(_validate_schema_instance(schema, ledger))
        if ledger != expected_ledger:
            errors.append("ledger does not match generated operator input request status projection")
        _validate_semantics(ledger, errors)
    summary = expected_ledger["summary"]
    return RuntimeEnablementEvidenceRequestStatusLedgerValidation(
        valid=not errors,
        ledger_path=_path_label(ledger_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        status_record_count=int(summary["status_record_count"]),
        awaiting_evidence_count=int(summary["awaiting_evidence_count"]),
        submitted_evidence_count=int(summary["submitted_evidence_count"]),
        accepted_evidence_count=int(summary["accepted_evidence_count"]),
        runtime_enablement_allowed=False,
        next_action=str(expected_ledger["next_action"]),
    )


def write_runtime_enablement_evidence_request_status_ledger_validation(
    validation: RuntimeEnablementEvidenceRequestStatusLedgerValidation,
    output_path: Path,
) -> Path:
    """Write one status ledger validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _status_record(required_input: dict[str, Any]) -> dict[str, Any]:
    source_input_id = str(required_input["input_id"])
    return {
        "status_record_id": source_input_id.replace(
            "read-only-worker-runtime-enablement-input-",
            "read-only-worker-runtime-enablement-evidence-status-",
        ),
        "source_input_id": source_input_id,
        "input_kind": str(required_input["input_kind"]),
        "required_names": list(required_input["required_names"]),
        "status": "awaiting_evidence",
        "proof_state": "Unknown",
        **{field_name: True for field_name in TRUE_RECORD_FIELDS},
        **{field_name: False for field_name in FALSE_RECORD_FIELDS},
        "submitted_evidence_refs": [],
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "authority_grant_refs": [],
        "blocked_action_refs": list(BLOCKED_ACTIONS),
        "next_action": str(required_input["next_action"]),
    }


def _validate_semantics(ledger: dict[str, Any], errors: list[str]) -> None:
    if ledger.get("ledger_id") != LEDGER_ID:
        errors.append("ledger_id is invalid")
    if ledger.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must be AwaitingEvidence")
    if ledger.get("proof_state") != "Unknown":
        errors.append("proof_state must be Unknown")
    if ledger.get("ledger_state") != "request_status_only":
        errors.append("ledger_state must be request_status_only")
    for field_name in TRUE_LEDGER_FIELDS:
        if ledger.get(field_name) is not True:
            errors.append(f"{field_name} must be true")
    for field_name in FALSE_LEDGER_FIELDS:
        if ledger.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    for field_name in (
        "submitted_evidence_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
        "authority_grant_refs",
    ):
        if ledger.get(field_name) != []:
            errors.append(f"{field_name} must remain empty")
    if set(_string_list(ledger.get("blocked_actions"))) != set(BLOCKED_ACTIONS):
        errors.append("blocked_actions must match runtime enablement blocked actions")

    records = ledger.get("status_records")
    if not isinstance(records, list):
        errors.append("status_records must be a list")
        return
    if len(records) != 12:
        errors.append("status_records must contain twelve records")
    if ledger.get("status_record_refs") != [
        record.get("status_record_id") for record in records if isinstance(record, dict)
    ]:
        errors.append("status_record_refs must match status record ids")
    for record in records:
        if not isinstance(record, dict):
            errors.append("status_records entries must be objects")
            continue
        _validate_record(record, errors)
    _validate_summary(ledger, errors)


def _validate_record(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("status") != "awaiting_evidence":
        errors.append("status record status must be awaiting_evidence")
    if record.get("proof_state") != "Unknown":
        errors.append("status record proof_state must be Unknown")
    for field_name in TRUE_RECORD_FIELDS:
        if record.get(field_name) is not True:
            errors.append(f"status record {field_name} must be true")
    for field_name in FALSE_RECORD_FIELDS:
        if record.get(field_name) is not False:
            errors.append(f"status record {field_name} must be false")
    for field_name in (
        "submitted_evidence_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
        "authority_grant_refs",
    ):
        if record.get(field_name) != []:
            errors.append(f"status record {field_name} must remain empty")
    if set(_string_list(record.get("blocked_action_refs"))) != set(BLOCKED_ACTIONS):
        errors.append("status record blocked_action_refs must match blocked actions")


def _validate_summary(ledger: dict[str, Any], errors: list[str]) -> None:
    records = ledger.get("status_records")
    summary = ledger.get("summary")
    if not isinstance(records, list) or not isinstance(summary, dict):
        errors.append("summary requires status_records list")
        return
    expected_counts = {
        "source_required_input_count": len(records),
        "status_record_count": len(records),
        "awaiting_evidence_count": sum(1 for record in records if record.get("status") == "awaiting_evidence"),
        "submitted_evidence_count": sum(1 for record in records if record.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for record in records if record.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for record in records if record.get("evidence_rejected") is True),
        "authority_grant_count": sum(1 for record in records if record.get("authority_granted") is True),
        "runtime_enablement_count": sum(1 for record in records if record.get("runtime_enablement_allowed") is True),
        "dispatch_count": sum(1 for record in records if record.get("runtime_dispatch_allowed") is True),
        "worker_invocation_count": sum(1 for record in records if record.get("worker_invocation_allowed") is True),
        "receipt_emission_count": sum(1 for record in records if record.get("runtime_receipt_emission_allowed") is True),
        "receipt_append_count": sum(1 for record in records if record.get("receipt_append_allowed") is True),
        "terminal_closure_count": sum(1 for record in records if record.get("terminal_closure_allowed") is True),
        "unknown_proof_state_count": sum(1 for record in records if record.get("proof_state") == "Unknown"),
        "blocked_action_count": len(_string_list(ledger.get("blocked_actions"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match ledger state")


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
    """Parse status ledger validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate read-only worker runtime enablement evidence request status ledger."
    )
    parser.add_argument("--ledger", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for status ledger validation."""

    args = parse_args(argv)
    validation = validate_runtime_enablement_evidence_request_status_ledger(
        ledger_path=Path(args.ledger),
        schema_path=Path(args.schema),
    )
    if args.write:
        write_runtime_enablement_evidence_request_status_ledger_validation(
            validation,
            Path(args.output),
        )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime enablement evidence request status ledger valid")
    else:
        print(f"runtime enablement evidence request status ledger invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
