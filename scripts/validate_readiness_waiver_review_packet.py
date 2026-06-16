#!/usr/bin/env python3
"""Validate the ReadinessWaiverReviewPacket contract.

Purpose: verify that readiness-waiver handling remains a bounded review packet
instead of becoming release, deployment, runtime-promotion, or terminal-closure
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, SDLC release
and deployment schemas, temporal accepted-risk expiry receipts, UAO, and
Foundation Mode evidence.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example never grants a waiver or readiness claim.
  - Deployment authority, runtime promotion, publication, terminal closure, and
    success claims remain denied.
  - Waiver expiry, compensating controls, required evidence, and blocked
    reasons are explicit.
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
EXPECTED_PACKET_VERSION = "readiness_waiver_review_packet.v1"
EXPECTED_BLOCKED_DECISION = "WAIVER_REVIEW_BLOCKED_AWAITING_APPROVAL"
REQUIRED_EVIDENCE_REFS = (
    "evidence://readiness-waiver/operator-approval",
    "evidence://readiness-waiver/phi-gov-authorization",
    "evidence://readiness-waiver/security-review",
    "evidence://readiness-waiver/rollback-recovery",
    "evidence://readiness-waiver/expiry-receipt",
    "evidence://readiness-waiver/compensating-controls",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://operator-approval/missing",
    "blocked://phi-gov/authorization-missing",
    "blocked://accepted-risk/not-issued",
    "blocked://readiness-claim/denied",
    "blocked://deployment-authority/denied",
)
REQUIRED_RECEIPT_REFS = {
    "readiness_waiver_review_packet_schema": "schemas/readiness_waiver_review_packet.schema.json",
    "sdlc_release_candidate_schema": "schemas/sdlc_release_candidate.schema.json",
    "sdlc_deployment_candidate_schema": "schemas/sdlc_deployment_candidate.schema.json",
    "sdlc_security_review_schema": "schemas/sdlc_security_review.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "temporal_accepted_risk_expiry_receipt_schema": "schemas/temporal_accepted_risk_expiry_receipt.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/readiness_waiver_review_packet.schema.json",
    "examples/readiness_waiver_review_packet.foundation.json",
    "scripts/validate_readiness_waiver_review_packet.py",
    "tests/test_validate_readiness_waiver_review_packet.py",
    "docs/86_readiness_waiver_review_packet_contract.md",
    "schemas/sdlc_release_candidate.schema.json",
    "schemas/sdlc_deployment_candidate.schema.json",
    "schemas/sdlc_security_review.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/temporal_accepted_risk_expiry_receipt.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "docs/34_accepted_risk_closure.md",
)
DENIED_DECISION_FIELDS = (
    "waiver_granted",
    "readiness_claim_allowed",
    "deployment_authority_allowed",
    "runtime_promotion_allowed",
    "external_publication_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
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
            "packet_id",
            "packet_version",
            "waiver_scope",
            "review_chain",
            "waiver_decision",
            "compensating_controls",
            "expiry_policy",
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
    _validate_review_chain(record.get("review_chain"), errors)
    _validate_waiver_decision(record.get("waiver_decision"), errors)
    _validate_compensating_controls(record.get("compensating_controls"), errors)
    _validate_expiry_policy(record.get("generated_at"), record.get("expiry_policy"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
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
    if record.get("packet_version") != EXPECTED_PACKET_VERSION:
        errors.append("packet_version must match readiness_waiver_review_packet.v1")
    if not isinstance(record.get("source_readiness_ref"), str) or record.get("source_readiness_ref") == "":
        errors.append("source_readiness_ref must be non-empty")


def _validate_waiver_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("waiver_scope must be an object")
        return
    if scope.get("readiness_surface") not in {"release", "deployment", "runtime_promotion", "connector_promotion", "public_health"}:
        errors.append("waiver_scope.readiness_surface is invalid")
    if scope.get("risk_class") not in {"medium", "high", "critical"}:
        errors.append("waiver_scope.risk_class is invalid")
    if scope.get("uao_ref") == "":
        errors.append("waiver_scope.uao_ref must be non-empty")
    if scope.get("phi_gov_ref") is not None:
        errors.append("foundation readiness waiver packet must not include Phi_gov authorization")


def _validate_review_chain(chain: Any, errors: list[str]) -> None:
    if not isinstance(chain, dict):
        errors.append("review_chain must be an object")
        return
    for field_name in (
        "operator_review_required",
        "security_review_present",
        "rollback_recovery_ref_present",
        "life_meaning_judgment_present",
        "mfidel_atomicity_preserved",
    ):
        if chain.get(field_name) is not True:
            errors.append(f"review_chain.{field_name} must be true")
    for field_name in (
        "operator_approval_present",
        "phi_gov_authorization_present",
    ):
        if chain.get(field_name) is not False:
            errors.append(f"review_chain.{field_name} must be false in Foundation Mode")
    if chain.get("accepted_risk_ref") is not None:
        errors.append("foundation readiness waiver packet must not include an accepted risk ref")


def _validate_waiver_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("waiver_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_BLOCKED_DECISION:
        errors.append("waiver_decision.decision must be WAIVER_REVIEW_BLOCKED_AWAITING_APPROVAL")
    for field_name in DENIED_DECISION_FIELDS:
        if decision.get(field_name) is not False:
            errors.append(f"waiver_decision.{field_name} must be false")
    if decision.get("operator_approval_required") is not True:
        errors.append("waiver_decision.operator_approval_required must be true")
    _require_subset(decision, "required_evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _require_subset(decision, "blocked_reason_refs", REQUIRED_BLOCKED_REASON_REFS, errors)


def _validate_compensating_controls(controls: Any, errors: list[str]) -> None:
    if not isinstance(controls, list):
        errors.append("compensating_controls must be a list")
        return
    if not controls:
        errors.append("compensating_controls must not be empty")
        return
    control_ids: set[str] = set()
    for index, control in enumerate(controls):
        if not isinstance(control, dict):
            errors.append(f"compensating_controls[{index}] must be an object")
            continue
        control_id = control.get("control_id")
        if not isinstance(control_id, str) or control_id == "":
            errors.append(f"compensating_controls[{index}].control_id must be non-empty")
        elif control_id in control_ids:
            errors.append(f"compensating_controls[{index}].control_id must be unique")
        else:
            control_ids.add(control_id)
        if control.get("active") is not True:
            errors.append(f"compensating_controls[{index}].active must be true")
        for field_name in ("owner", "evidence_ref", "verification_ref"):
            if not isinstance(control.get(field_name), str) or control.get(field_name) == "":
                errors.append(f"compensating_controls[{index}].{field_name} must be non-empty")


def _validate_expiry_policy(generated_at: Any, expiry: Any, errors: list[str]) -> None:
    if not isinstance(expiry, dict):
        errors.append("expiry_policy must be an object")
        return
    if expiry.get("expired") is not False:
        errors.append("expiry_policy.expired must be false in Foundation example")
    if expiry.get("renewal_requires_operator_approval") is not True:
        errors.append("expiry_policy.renewal_requires_operator_approval must be true")
    if expiry.get("max_duration_days") != 14:
        errors.append("expiry_policy.max_duration_days must be 14 for the Foundation example")
    if expiry.get("expiry_receipt_ref") != REQUIRED_RECEIPT_REFS["temporal_accepted_risk_expiry_receipt_schema"]:
        errors.append("expiry_policy.expiry_receipt_ref must point to temporal accepted-risk expiry schema")
    _validate_expiry_window(generated_at, expiry.get("expires_at"), errors)


def _validate_expiry_window(generated_at: Any, expires_at: Any, errors: list[str]) -> None:
    if not isinstance(generated_at, str) or not isinstance(expires_at, str):
        errors.append("generated_at and expiry_policy.expires_at must be date-time strings")
        return
    try:
        generated = _parse_utc_datetime(generated_at)
        expires = _parse_utc_datetime(expires_at)
    except ValueError as exc:
        errors.append(f"expiry_policy date-time parse failed: {exc}")
        return
    if expires <= generated:
        errors.append("expiry_policy.expires_at must be after generated_at")
    if (expires - generated).days > 30:
        errors.append("expiry_policy.expires_at must stay within 30 days")


def _parse_utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    decision = record.get("waiver_decision")
    controls = record.get("compensating_controls")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(decision, dict) or not isinstance(controls, list) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("waiver_decision, compensating_controls, receipt_refs, and contract_summary must be typed")
        return
    expected_counts = {
        "compensating_control_count": len(controls),
        "required_evidence_ref_count": _list_len(decision.get("required_evidence_refs")),
        "blocked_reason_ref_count": _list_len(decision.get("blocked_reason_refs")),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    if summary.get("waiver_granted") is not decision.get("waiver_granted"):
        errors.append("contract_summary.waiver_granted must match waiver_decision.waiver_granted")
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
