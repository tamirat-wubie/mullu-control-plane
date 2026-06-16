#!/usr/bin/env python3
"""Validate the ConnectorActionPromotionGate contract.

Purpose: verify that connector action promotion remains a receipt-bound,
non-executing gate until UAO, Phi_gov, operator approval, secret access,
connector-worker execution, and rollback evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers,
ConnectorDescriptor, ConnectorResult, Universal Action Orchestration, and
Foundation Mode connector fixtures.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example never permits live connector calls.
  - Secret values and raw provider responses are never required or serialized.
  - Connector promotion cannot bypass UAO, Phi_gov, operator approval, failure
    handling, or rollback evidence.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "connector_action_promotion_gate.schema.json"
DEFAULT_GATE_PATH = WORKSPACE_ROOT / "examples" / "connector_action_promotion_gate.foundation.json"
DEFAULT_CONNECTOR_DESCRIPTOR_PATH = WORKSPACE_ROOT / "integration" / "contracts_compat" / "fixtures" / "connector_descriptor.json"
DEFAULT_CONNECTOR_RESULT_PATH = WORKSPACE_ROOT / "integration" / "contracts_compat" / "fixtures" / "connector_result.json"
DEFAULT_CONNECTOR_DESCRIPTOR_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "connector_descriptor.schema.json"
DEFAULT_CONNECTOR_RESULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "connector_result.schema.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:connector-action-promotion-gate:1"
EXPECTED_SCHEMA_TITLE = "Connector Action Promotion Gate"
EXPECTED_RECEIPT_VERSION = "connector_action_promotion_gate.v1"
EXPECTED_DESCRIPTOR_REF = "integration/contracts_compat/fixtures/connector_descriptor.json"
EXPECTED_RESULT_REF = "integration/contracts_compat/fixtures/connector_result.json"
EXPECTED_BLOCKED_DECISION = "PROMOTION_BLOCKED_AWAITING_LIVE_EVIDENCE"
REQUIRED_LIVE_EVIDENCE_REFS = (
    "evidence://connector-action/uao-admission",
    "evidence://connector-action/phi-gov-authorization",
    "evidence://connector-action/operator-approval",
    "evidence://connector-action/credential-scope-live-bound",
    "evidence://connector-action/secret-access-receipt",
    "evidence://connector-action/connector-worker-execution-receipt",
    "evidence://connector-action/rollback-recovery-receipt",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://phi-gov/authorization-missing",
    "blocked://operator-approval/missing",
    "blocked://secret-access-receipt/missing",
    "blocked://connector-worker-execution-receipt/missing",
    "blocked://rollback-recovery/missing",
)
REQUIRED_RECEIPT_REFS = {
    "connector_action_promotion_gate_schema": "schemas/connector_action_promotion_gate.schema.json",
    "connector_descriptor_schema": "schemas/connector_descriptor.schema.json",
    "connector_result_schema": "schemas/connector_result.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "connector_self_healing_receipt_schema": "schemas/connector_self_healing_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/connector_action_promotion_gate.schema.json",
    "examples/connector_action_promotion_gate.foundation.json",
    "scripts/validate_connector_action_promotion_gate.py",
    "tests/test_validate_connector_action_promotion_gate.py",
    "schemas/connector_descriptor.schema.json",
    "schemas/connector_result.schema.json",
    EXPECTED_DESCRIPTOR_REF,
    EXPECTED_RESULT_REF,
    "schemas/universal_action_orchestration.schema.json",
    "schemas/connector_self_healing_receipt.schema.json",
    "docs/10_external_integration_plane.md",
)
DENIED_DECISION_FIELDS = (
    "promotion_allowed",
    "live_connector_call_allowed",
    "external_write_allowed",
    "secret_access_allowed",
    "runtime_dispatch_allowed",
    "deployment_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
    "raw_secret_material_included",
)


class ConnectorActionPromotionGateError(ValueError):
    """Raised when a ConnectorActionPromotionGate artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConnectorActionPromotionGateError(f"{label} must be a JSON object")
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
            "source_connector_descriptor_ref",
            "source_connector_result_ref",
            "promotion_scope",
            "authority_preflight",
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


def validate_connector_action_promotion_gate_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    connector_descriptor: dict[str, Any] | None = None,
    connector_result: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one connector action promotion gate."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("connector action promotion gate must be a JSON object")
        return errors

    descriptor = connector_descriptor or load_json_object(DEFAULT_CONNECTOR_DESCRIPTOR_PATH, "ConnectorDescriptor")
    result = connector_result or load_json_object(DEFAULT_CONNECTOR_RESULT_PATH, "ConnectorResult")
    errors.extend(
        f"connector_descriptor: {error}"
        for error in _validate_schema_instance(_load_schema(DEFAULT_CONNECTOR_DESCRIPTOR_SCHEMA_PATH), descriptor)
    )
    errors.extend(
        f"connector_result: {error}"
        for error in _validate_schema_instance(_load_schema(DEFAULT_CONNECTOR_RESULT_SCHEMA_PATH), result)
    )

    _validate_top_level(record, errors)
    _validate_promotion_scope(record.get("promotion_scope"), descriptor, result, errors)
    _validate_authority_preflight(record.get("authority_preflight"), errors)
    _validate_gate_decision(record.get("gate_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_connector_action_promotion_gate(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    gate_path: Path = DEFAULT_GATE_PATH,
    connector_descriptor_path: Path = DEFAULT_CONNECTOR_DESCRIPTOR_PATH,
    connector_result_path: Path = DEFAULT_CONNECTOR_RESULT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode gate."""

    schema = _load_schema(schema_path)
    gate = load_json_object(gate_path, "ConnectorActionPromotionGate")
    descriptor = load_json_object(connector_descriptor_path, "ConnectorDescriptor")
    result = load_json_object(connector_result_path, "ConnectorResult")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_connector_action_promotion_gate_record(gate, schema, descriptor, result))
    return errors


def build_mutated_connector_action_promotion_gate(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default promotion gate."""

    gate = load_json_object(DEFAULT_GATE_PATH, "ConnectorActionPromotionGate")
    mutated = deepcopy(gate)
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
        errors.append("receipt_version must match connector_action_promotion_gate.v1")
    if record.get("source_connector_descriptor_ref") != EXPECTED_DESCRIPTOR_REF:
        errors.append("source_connector_descriptor_ref must point to the connector descriptor compatibility fixture")
    if record.get("source_connector_result_ref") != EXPECTED_RESULT_REF:
        errors.append("source_connector_result_ref must point to the connector result compatibility fixture")


def _validate_promotion_scope(
    scope: Any,
    descriptor: dict[str, Any],
    result: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(scope, dict):
        errors.append("promotion_scope must be an object")
        return
    if scope.get("connector_id") != descriptor.get("connector_id"):
        errors.append("promotion_scope.connector_id must match connector descriptor connector_id")
    if result.get("connector_id") != descriptor.get("connector_id"):
        errors.append("connector result connector_id must match connector descriptor connector_id")
    if scope.get("requested_effect_class") != descriptor.get("effect_class"):
        errors.append("promotion_scope.requested_effect_class must match connector descriptor effect_class")
    if scope.get("trust_class") != descriptor.get("trust_class"):
        errors.append("promotion_scope.trust_class must match connector descriptor trust_class")
    if scope.get("credential_scope_id") != descriptor.get("credential_scope_id"):
        errors.append("promotion_scope.credential_scope_id must match connector descriptor credential_scope_id")
    if descriptor.get("enabled") is not True:
        errors.append("connector descriptor must be enabled before promotion can be classified")
    if scope.get("uao_ref") == "":
        errors.append("promotion_scope.uao_ref must be non-empty")
    if scope.get("phi_gov_ref") is not None:
        errors.append("foundation connector promotion gate must not include Phi_gov authorization")


def _validate_authority_preflight(preflight: Any, errors: list[str]) -> None:
    if not isinstance(preflight, dict):
        errors.append("authority_preflight must be an object")
        return
    for field_name in (
        "connector_descriptor_bound",
        "connector_result_bound",
        "credential_scope_bound",
        "uao_ref_present",
        "life_meaning_judgment_present",
        "mfidel_atomicity_preserved",
    ):
        if preflight.get(field_name) is not True:
            errors.append(f"authority_preflight.{field_name} must be true")
    for field_name in (
        "phi_gov_authorization_present",
        "operator_approval_present",
        "rollback_recovery_ref_present",
        "secret_access_receipt_present",
        "connector_worker_execution_receipt_present",
    ):
        if preflight.get(field_name) is not False:
            errors.append(f"authority_preflight.{field_name} must be false in Foundation Mode")


def _validate_gate_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("gate_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_BLOCKED_DECISION:
        errors.append("gate_decision.decision must be PROMOTION_BLOCKED_AWAITING_LIVE_EVIDENCE")
    for field_name in DENIED_DECISION_FIELDS:
        if decision.get(field_name) is not False:
            errors.append(f"gate_decision.{field_name} must be false")
    if decision.get("operator_approval_required") is not True:
        errors.append("gate_decision.operator_approval_required must be true")
    _require_subset(decision, "required_live_evidence_refs", REQUIRED_LIVE_EVIDENCE_REFS, errors)
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
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(decision, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("gate_decision, receipt_refs, and contract_summary must be objects")
        return
    expected_counts = {
        "required_live_evidence_ref_count": _list_len(decision.get("required_live_evidence_refs")),
        "blocked_reason_ref_count": _list_len(decision.get("blocked_reason_refs")),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    if summary.get("promotion_allowed") is not decision.get("promotion_allowed"):
        errors.append("contract_summary.promotion_allowed must match gate_decision.promotion_allowed")
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
    """Validate ConnectorActionPromotionGate artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ConnectorActionPromotionGate contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE_PATH)
    parser.add_argument("--connector-descriptor", type=Path, default=DEFAULT_CONNECTOR_DESCRIPTOR_PATH)
    parser.add_argument("--connector-result", type=Path, default=DEFAULT_CONNECTOR_RESULT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_connector_action_promotion_gate(
        args.schema,
        args.gate,
        args.connector_descriptor,
        args.connector_result,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "connector_action_promotion_gate_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "gate_path": workspace_display_path(args.gate),
                    "connector_descriptor_path": workspace_display_path(args.connector_descriptor),
                    "connector_result_path": workspace_display_path(args.connector_result),
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
        print("[PASS] connector_action_promotion_gate")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
