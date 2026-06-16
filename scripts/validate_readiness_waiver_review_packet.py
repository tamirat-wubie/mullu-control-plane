#!/usr/bin/env python3
"""Validate the ReadinessWaiverReviewPacket contract.

Purpose: verify that readiness waiver review remains an expiry-bound,
approval-bound, non-executing packet until Phi_gov, operator approval,
accepted-risk expiry, compensating controls, rollback, and incident evidence
exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, SDLC release
and deployment schemas, temporal accepted-risk expiry receipts, UAO, and
Foundation Mode readiness documents.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example never grants a waiver or deployment authority.
  - Waiver expiry, compensating controls, blocked reasons, and receipt refs
    remain explicit.
  - Secret values and runtime/deployment effects are never required or emitted.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "readiness_waiver_review_packet.schema.json"
DEFAULT_PACKET_PATH = WORKSPACE_ROOT / "examples" / "readiness_waiver_review_packet.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:readiness-waiver-review-packet:1"
EXPECTED_SCHEMA_TITLE = "Readiness Waiver Review Packet"
EXPECTED_RECEIPT_VERSION = "readiness_waiver_review_packet.v1"
EXPECTED_SOURCE_READINESS_REF = "docs/CURRENT_READINESS_SNAPSHOT.md"
EXPECTED_BLOCKED_DECISION = "WAIVER_BLOCKED_AWAITING_APPROVAL"
REQUIRED_EVIDENCE_REFS = (
    "evidence://readiness-waiver/phi-gov-authorization",
    "evidence://readiness-waiver/operator-approval",
    "evidence://readiness-waiver/accepted-risk-expiry",
    "evidence://readiness-waiver/compensating-controls",
    "evidence://readiness-waiver/rollback-recovery",
    "evidence://readiness-waiver/incident-handoff",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://readiness-waiver/phi-gov-authorization-missing",
    "blocked://readiness-waiver/operator-approval-missing",
    "blocked://readiness-waiver/accepted-risk-expiry-missing",
    "blocked://readiness-waiver/rollback-recovery-missing",
    "blocked://readiness-waiver/incident-handoff-missing",
)
REQUIRED_RECEIPT_REFS = {
    "readiness_waiver_review_packet_schema": "schemas/readiness_waiver_review_packet.schema.json",
    "sdlc_release_candidate_schema": "schemas/sdlc_release_candidate.schema.json",
    "sdlc_deployment_candidate_schema": "schemas/sdlc_deployment_candidate.schema.json",
    "temporal_accepted_risk_expiry_receipt_schema": "schemas/temporal_accepted_risk_expiry_receipt.schema.json",
    "sdlc_security_review_schema": "schemas/sdlc_security_review.schema.json",
    "sdlc_recovery_handoff_receipt_schema": "schemas/sdlc_recovery_handoff_receipt.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_PACKET_EVIDENCE_REFS = (
    "schemas/readiness_waiver_review_packet.schema.json",
    "examples/readiness_waiver_review_packet.foundation.json",
    "scripts/validate_readiness_waiver_review_packet.py",
    "tests/test_validate_readiness_waiver_review_packet.py",
    "docs/86_readiness_waiver_review_packet_contract.md",
    "docs/CURRENT_READINESS_SNAPSHOT.md",
    "docs/FOUNDATION_MODE.md",
    "docs/82_cross_repo_opportunity_map.md",
    "schemas/temporal_accepted_risk_expiry_receipt.schema.json",
)
DENIED_DECISION_FIELDS = (
    "waiver_granted",
    "deployment_mutation_allowed",
    "production_promotion_allowed",
    "terminal_closure_allowed",
    "readiness_success_claim_allowed",
    "external_exposure_allowed",
    "raw_secret_material_included",
)


class ReadinessWaiverReviewPacketError(ValueError):
    """Raised when a ReadinessWaiverReviewPacket artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadinessWaiverReviewPacketError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "receipt_id",
            "receipt_version",
            "source_readiness_ref",
            "waiver_scope",
            "review_controls",
            "gate_decision",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_readiness_waiver_review_packet_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one readiness waiver packet."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("readiness waiver review packet must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_waiver_scope(record.get("waiver_scope"), errors)
    _validate_review_controls(record, errors)
    _validate_gate_decision(record.get("gate_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_PACKET_EVIDENCE_REFS, errors)
    return errors


def validate_readiness_waiver_review_packet(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode packet."""

    schema = _load_schema(schema_path)
    packet = load_json_object(packet_path, "ReadinessWaiverReviewPacket")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_readiness_waiver_review_packet_record(packet, schema))
    return errors


def build_mutated_readiness_waiver_review_packet(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default waiver packet."""

    packet = load_json_object(DEFAULT_PACKET_PATH, "ReadinessWaiverReviewPacket")
    mutated = deepcopy(packet)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match readiness_waiver_review_packet.v1")
    if record.get("source_readiness_ref") != EXPECTED_SOURCE_READINESS_REF:
        errors.append("source_readiness_ref must point to docs/CURRENT_READINESS_SNAPSHOT.md")


def _validate_waiver_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("waiver_scope must be an object")
        return
    if scope.get("target_environment") != "foundation_local":
        errors.append("waiver_scope.target_environment must remain foundation_local")
    if scope.get("requested_disposition") != "review_only":
        errors.append("waiver_scope.requested_disposition must remain review_only")
    if scope.get("risk_class") not in {"medium", "high", "critical"}:
        errors.append("waiver_scope.risk_class must remain medium or higher")
    if scope.get("phi_gov_ref") is not None:
        errors.append("Foundation readiness waiver review must not include Phi_gov authorization")
    checks = scope.get("violated_readiness_checks")
    if not isinstance(checks, list) or "readiness://deployment/publication" not in checks:
        errors.append("waiver_scope.violated_readiness_checks must include deployment publication readiness")


def _validate_review_controls(record: dict[str, Any], errors: list[str]) -> None:
    controls = record.get("review_controls")
    if not isinstance(controls, dict):
        errors.append("review_controls must be an object")
        return
    if controls.get("operator_approval_present") is not False:
        errors.append("review_controls.operator_approval_present must be false in Foundation Mode")
    approval_refs = controls.get("approval_refs")
    if approval_refs != []:
        errors.append("review_controls.approval_refs must be empty until operator approval exists")
    if controls.get("approval_quorum_required") != 1:
        errors.append("review_controls.approval_quorum_required must be 1")
    if controls.get("expiry_required") is not True:
        errors.append("review_controls.expiry_required must be true")
    if controls.get("accepted_risk_ref_present") is not False:
        errors.append("review_controls.accepted_risk_ref_present must be false in Foundation Mode")
    if controls.get("rollback_recovery_ref_present") is not False:
        errors.append("review_controls.rollback_recovery_ref_present must be false in Foundation Mode")
    if controls.get("incident_handoff_ref_present") is not False:
        errors.append("review_controls.incident_handoff_ref_present must be false in Foundation Mode")
    if controls.get("mfidel_atomicity_preserved") is not True:
        errors.append("review_controls.mfidel_atomicity_preserved must be true")
    compensating_controls = controls.get("compensating_controls")
    if not isinstance(compensating_controls, list) or len(compensating_controls) < 2:
        errors.append("review_controls.compensating_controls must include at least two controls")
    _validate_expiry(record.get("generated_at"), controls.get("expiry_at"), errors)


def _validate_expiry(generated_at: Any, expiry_at: Any, errors: list[str]) -> None:
    if not isinstance(generated_at, str) or not isinstance(expiry_at, str):
        errors.append("generated_at and review_controls.expiry_at must be date-time strings")
        return
    try:
        generated_dt = _parse_datetime(generated_at)
        expiry_dt = _parse_datetime(expiry_at)
    except ValueError as exc:
        errors.append(f"readiness waiver date-time parse failed: {exc}")
        return
    if expiry_dt <= generated_dt:
        errors.append("review_controls.expiry_at must be later than generated_at")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_gate_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("gate_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_BLOCKED_DECISION:
        errors.append("gate_decision.decision must be WAIVER_BLOCKED_AWAITING_APPROVAL")
    for field_name in DENIED_DECISION_FIELDS:
        if decision.get(field_name) is not False:
            errors.append(f"gate_decision.{field_name} must be false")
    if decision.get("operator_approval_required") is not True:
        errors.append("gate_decision.operator_approval_required must be true")
    if decision.get("expiry_required") is not True:
        errors.append("gate_decision.expiry_required must be true")
    _require_subset(decision, "required_evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _require_subset(decision, "blocked_reason_refs", REQUIRED_BLOCKED_REASON_REFS, errors)


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    decision = record.get("gate_decision")
    controls = record.get("review_controls")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(decision, dict) or not isinstance(controls, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("gate_decision, review_controls, receipt_refs, and contract_summary must be objects")
        return
    expected_counts = {
        "required_evidence_ref_count": _list_len(decision.get("required_evidence_refs")),
        "blocked_reason_ref_count": _list_len(decision.get("blocked_reason_refs")),
        "approval_ref_count": _list_len(controls.get("approval_refs")),
        "compensating_control_count": _list_len(controls.get("compensating_controls")),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    if summary.get("waiver_granted") is not decision.get("waiver_granted"):
        errors.append("contract_summary.waiver_granted must match gate_decision.waiver_granted")
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate ReadinessWaiverReviewPacket artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ReadinessWaiverReviewPacket contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_readiness_waiver_review_packet(args.schema, args.packet)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "readiness_waiver_review_packet_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "packet_path": workspace_display_path(args.packet),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] readiness_waiver_review_packet")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
