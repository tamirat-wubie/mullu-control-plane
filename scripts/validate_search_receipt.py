#!/usr/bin/env python3
"""Validate the SearchReceipt contract.

Purpose: verify the post-decision receipt contract for search evidence,
freshness, citations, conflicts, retrieval errors, and retrieval safety.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - SearchReceipt records evidence metadata, not retrieved content bodies.
  - Current-information claims require fresh evidence and citation refs.
  - Retrieved content remains evidence only, not instruction authority.
  - Mfidel atomicity remains preserved.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "search_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "search_receipt.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:search-receipt:1"
EXPECTED_SCHEMA_TITLE = "Search Receipt"
EXPECTED_RECEIPT_VERSION = "search_receipt.v1"
REQUIRED_EVIDENCE_REFS = (
    "schemas/search_receipt.schema.json",
    "examples/search_receipt.foundation.json",
    "scripts/validate_search_receipt.py",
    "tests/test_validate_search_receipt.py",
    "docs/78_search_receipt_contract.md",
    "docs/maps/MULLUSI_SEARCH_LAYER_MAP.md",
    "examples/sdlc/requirement_search_receipt_contract_20260614.json",
    "examples/sdlc/design_search_receipt_contract_20260614.json",
)
FALSE_GUARDS = (
    "execution_authority_granted",
    "terminal_closure",
    "raw_secret_material_included",
    "retrieved_instruction_authority_granted",
)


class SearchReceiptError(ValueError):
    """Raised when a SearchReceipt artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SearchReceiptError(f"{label} must be a JSON object")
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
            "search_decision_ref",
            "receipt_state",
            "search_state",
            "freshness_result",
            "evidence_summary",
            "evidence_items",
            "citation_refs",
            "retrieval_errors",
            "retrieval_safety_result",
            "governance_guards",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        receipt_version_schema = properties.get("receipt_version", {})
        if not isinstance(receipt_version_schema, dict) or receipt_version_schema.get("const") != EXPECTED_RECEIPT_VERSION:
            errors.append("schema property receipt_version must const search_receipt.v1")
    return errors


def validate_receipt_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one SearchReceipt payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("search receipt must be a JSON object")
        return errors

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match search_receipt.v1")
    _validate_counts(record, errors)
    _validate_blocked_or_failed_state(record, errors)
    _validate_budget_result(record, errors)
    _validate_current_claim_authority(record, errors)
    _validate_evidence_items(record.get("evidence_items"), record.get("citation_refs"), errors)
    _validate_retrieval_safety(record.get("retrieval_safety_result"), errors)
    _validate_governance_guards(record.get("governance_guards"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_receipt(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "SearchReceipt")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_receipt_record(receipt, schema))
    return errors


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default receipt for tests."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "SearchReceipt")
    mutated = deepcopy(receipt)
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


def _validate_counts(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("evidence_summary")
    if not isinstance(summary, dict):
        errors.append("evidence_summary must be an object")
        return
    counted_fields = {
        "evidence_count": record.get("evidence_items"),
        "citation_count": record.get("citation_refs"),
        "conflict_count": record.get("conflict_refs"),
        "stale_source_count": record.get("stale_source_refs"),
        "retrieval_error_count": record.get("retrieval_errors"),
    }
    for summary_field, collection in counted_fields.items():
        if isinstance(collection, list) and summary.get(summary_field) != len(collection):
            errors.append(f"evidence_summary.{summary_field} must match {summary_field.removesuffix('_count')} list length")
    if summary.get("content_body_included") is not False:
        errors.append("retrieved content body must not be included")


def _validate_blocked_or_failed_state(record: dict[str, Any], errors: list[str]) -> None:
    receipt_state = record.get("receipt_state")
    retrieval_errors = record.get("retrieval_errors")
    evidence_summary = record.get("evidence_summary")
    if receipt_state in {"RETRIEVAL_BLOCKED", "RETRIEVAL_FAILED"}:
        if not isinstance(retrieval_errors, list) or not retrieval_errors:
            errors.append("blocked or failed retrieval must include retrieval_errors")
        if isinstance(evidence_summary, dict) and evidence_summary.get("evidence_count") != 0:
            errors.append("blocked or failed retrieval cannot claim evidence_count")
    if receipt_state == "EVIDENCE_AVAILABLE":
        if isinstance(evidence_summary, dict) and evidence_summary.get("evidence_count", 0) < 1:
            errors.append("EVIDENCE_AVAILABLE requires at least one evidence item")
        if not record.get("citation_refs"):
            errors.append("EVIDENCE_AVAILABLE requires citation_refs")


def _validate_budget_result(record: dict[str, Any], errors: list[str]) -> None:
    budget = record.get("budget_result")
    if not isinstance(budget, dict):
        errors.append("budget_result must be an object")
        return
    if budget.get("budget_decision_ref") != record.get("search_decision_ref"):
        errors.append("budget_result.budget_decision_ref must match search_decision_ref")
    evidence_refs = budget.get("budget_evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        errors.append("budget_result.budget_evidence_refs must be a non-empty list")
    elif budget.get("budget_decision_ref") not in evidence_refs:
        errors.append("budget_result.budget_evidence_refs must include budget_decision_ref")

    state = budget.get("state")
    proof_state = budget.get("proof_state")
    decision_state = budget.get("decision_budget_state")
    binding_state = budget.get("budget_binding_state")
    if binding_state == "bound_to_search_decision":
        if decision_state != "allowed" or state != "within_budget" or proof_state != "Pass":
            errors.append("bound search budget requires allowed decision, within_budget state, and Pass proof")
    elif binding_state == "not_applicable":
        if decision_state != "not_required" or state != "not_applicable" or proof_state != "Pass":
            errors.append("not_applicable search budget requires not_required decision and Pass proof")
    elif binding_state == "blocked_by_budget":
        if decision_state != "blocked" or state != "blocked_by_budget" or proof_state != "Fail":
            errors.append("blocked_by_budget requires blocked decision, blocked_by_budget state, and Fail proof")
    elif binding_state == "budget_unknown_blocked":
        if decision_state != "unknown" or proof_state != "BudgetUnknown":
            errors.append("budget_unknown_blocked requires unknown decision and BudgetUnknown proof")

    estimated_cost = budget.get("decision_estimated_cost_units")
    budget_limit = budget.get("decision_budget_limit_units")
    remaining = budget.get("decision_budget_remaining_units")
    if state == "within_budget" and (estimated_cost is None or budget_limit is None):
        errors.append("within_budget requires decision estimated cost and budget limit units")
    if isinstance(estimated_cost, (int, float)) and not isinstance(estimated_cost, bool):
        if isinstance(budget_limit, (int, float)) and not isinstance(budget_limit, bool) and budget_limit > 0:
            expected_remaining = max(float(budget_limit) - float(estimated_cost), 0.0)
            if remaining != expected_remaining:
                errors.append("budget_result.decision_budget_remaining_units must match decision budget headroom")


def _validate_current_claim_authority(record: dict[str, Any], errors: list[str]) -> None:
    freshness = record.get("freshness_result")
    guards = record.get("governance_guards")
    if not isinstance(freshness, dict):
        errors.append("freshness_result must be an object")
        return
    current_claim_allowed = freshness.get("current_info_claim_allowed")
    proof_state = freshness.get("proof_state")
    freshness_status = freshness.get("freshness_status")
    if current_claim_allowed is True and (proof_state != "Pass" or freshness_status != "fresh"):
        errors.append("current_info_claim_allowed requires fresh Pass evidence")
    if isinstance(guards, dict) and guards.get("answer_claim_authority_granted") is True:
        if current_claim_allowed is not True:
            errors.append("answer claim authority requires current_info_claim_allowed true")
        if not record.get("citation_refs"):
            errors.append("answer claim authority requires citation_refs")


def _validate_evidence_items(evidence_items: Any, citation_refs: Any, errors: list[str]) -> None:
    if not isinstance(evidence_items, list):
        errors.append("evidence_items must be a list")
        return
    if not isinstance(citation_refs, list):
        errors.append("citation_refs must be a list")
        return
    citation_ref_set = set(citation_refs)
    for index, evidence_item in enumerate(evidence_items):
        if not isinstance(evidence_item, dict):
            errors.append(f"evidence_items[{index}] must be an object")
            continue
        if evidence_item.get("content_body") is not None:
            errors.append(f"evidence_items[{index}].content_body must be null")
        citation_ref = evidence_item.get("citation_ref")
        if citation_ref not in citation_ref_set:
            errors.append(f"evidence_items[{index}].citation_ref must be listed in citation_refs")


def _validate_retrieval_safety(retrieval_safety: Any, errors: list[str]) -> None:
    if not isinstance(retrieval_safety, dict):
        errors.append("retrieval_safety_result must be an object")
        return
    if retrieval_safety.get("retrieved_content_authority") != "evidence_only":
        errors.append("retrieved content authority must remain evidence_only")
    for field_name in (
        "prompt_injection_guard_applied",
        "private_source_scope_verified",
    ):
        if retrieval_safety.get(field_name) is not True:
            errors.append(f"retrieval_safety_result.{field_name} must be true")
    for field_name in (
        "source_instruction_authority_granted",
        "tool_instruction_from_source_allowed",
        "policy_instruction_from_source_allowed",
    ):
        if retrieval_safety.get(field_name) is not False:
            errors.append(f"retrieval_safety_result.{field_name} must be false")


def _validate_governance_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("governance_guards must be an object")
        return
    for guard_name in FALSE_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"governance_guards.{guard_name} must be false")
    if guards.get("mfidel_atomicity_preserved") is not True:
        errors.append("governance_guards.mfidel_atomicity_preserved must be true")
    if guards.get("connector_authority_granted") is True and not guards.get("answer_claim_authority_granted") in {True, False}:
        errors.append("connector_authority_granted must be explicit")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate SearchReceipt artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate SearchReceipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_receipt(args.schema, args.receipt)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "search_receipt_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
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
        print("[PASS] search_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
