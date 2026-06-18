#!/usr/bin/env python3
"""Validate the ResearchSourceConflictMap contract.

Purpose: verify that research-source disagreements remain citation-bound,
read-only, and separated from live retrieval, source contact, answer synthesis,
memory write, publication, and terminal-closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, SearchDecision,
SearchReceipt, evidence classification, UAO, and LifeMeaningJudgment schemas.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example stores no raw source body or raw secret values.
  - Source conflicts require at least two citation refs.
  - Follow-up sensing is approval-required and cannot perform live search or
    source contact in Foundation Mode.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "research_source_conflict_map.schema.json"
DEFAULT_MAP_PATH = WORKSPACE_ROOT / "examples" / "research_source_conflict_map.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:research-source-conflict-map:1"
EXPECTED_SCHEMA_TITLE = "Research Source Conflict Map"
EXPECTED_MAP_VERSION = "research_source_conflict_map.v1"
REQUIRED_RECEIPT_REFS = {
    "research_source_conflict_map_schema": "schemas/research_source_conflict_map.schema.json",
    "search_decision_schema": "schemas/search_decision.schema.json",
    "search_receipt_schema": "schemas/search_receipt.schema.json",
    "evidence_classification_manifest_schema": "schemas/evidence_classification_manifest.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/research_source_conflict_map.schema.json",
    "examples/research_source_conflict_map.foundation.json",
    "scripts/validate_research_source_conflict_map.py",
    "tests/test_validate_research_source_conflict_map.py",
    "docs/88_research_source_conflict_map_contract.md",
    "schemas/search_decision.schema.json",
    "schemas/search_receipt.schema.json",
    "schemas/evidence_classification_manifest.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "docs/82_cross_repo_opportunity_map.md",
)
DENIED_AUTHORITY_FIELDS = (
    "external_retrieval_performed",
    "web_search_performed",
    "connector_call_performed",
    "source_contact_performed",
    "raw_source_body_stored",
    "raw_secret_value_stored",
    "answer_synthesis_allowed",
    "current_claim_allowed",
    "memory_write_performed",
    "publication_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)


class ResearchSourceConflictMapError(ValueError):
    """Raised when a ResearchSourceConflictMap artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ResearchSourceConflictMapError(f"{label} must be a JSON object")
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
            "map_id",
            "map_version",
            "research_scope",
            "source_set",
            "conflict_set",
            "follow_up_sensing",
            "authority_boundary",
            "retention_policy",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_research_source_conflict_map_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one conflict map."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("research source conflict map must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_research_scope(record.get("research_scope"), errors)
    _validate_source_set(record.get("source_set"), errors)
    _validate_conflict_set(record.get("conflict_set"), record.get("source_set"), errors)
    _validate_follow_up_sensing(record.get("follow_up_sensing"), record.get("conflict_set"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_retention_policy(record.get("retention_policy"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_research_source_conflict_map(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    map_path: Path = DEFAULT_MAP_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode map."""

    schema = _load_schema(schema_path)
    conflict_map = load_json_object(map_path, "ResearchSourceConflictMap")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_research_source_conflict_map_record(conflict_map, schema))
    return errors


def build_mutated_research_source_conflict_map(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default map."""

    conflict_map = load_json_object(DEFAULT_MAP_PATH, "ResearchSourceConflictMap")
    mutated = deepcopy(conflict_map)
    for dotted_key, value in updates.items():
        target: Any = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            if isinstance(target, list):
                target = target[int(segment)]
                continue
            next_target = target.get(segment)
            if not isinstance(next_target, (dict, list)):
                next_target = {}
                target[segment] = next_target
            target = next_target
        final_segment = segments[-1]
        if isinstance(target, list):
            target[int(final_segment)] = value
        else:
            target[final_segment] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("map_version") != EXPECTED_MAP_VERSION:
        errors.append("map_version must match research_source_conflict_map.v1")
    question_hash = _get_nested(record, "research_scope", "research_question_hash")
    _validate_digest_ref("research_scope.research_question_hash", question_hash, errors)


def _validate_research_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("research_scope must be an object")
        return
    if scope.get("source_mode") != "operator_supplied_citation_refs":
        errors.append("research_scope.source_mode must be operator_supplied_citation_refs")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("research_scope.tenant_scope must be foundation-local-only")
    expected_refs = {
        "search_decision_ref": "schemas/search_decision.schema.json",
        "search_receipt_ref": "schemas/search_receipt.schema.json",
    }
    for field_name, expected_ref in expected_refs.items():
        if scope.get(field_name) != expected_ref:
            errors.append(f"research_scope.{field_name} must be {expected_ref}")
    if not isinstance(scope.get("uao_ref"), str) or scope.get("uao_ref") == "":
        errors.append("research_scope.uao_ref must be non-empty")


def _validate_source_set(source_set: Any, errors: list[str]) -> None:
    if not isinstance(source_set, list):
        errors.append("source_set must be a list")
        return
    if len(source_set) < 2:
        errors.append("source_set must include at least two sources")
    citation_refs: set[str] = set()
    for index, source in enumerate(source_set):
        if not isinstance(source, dict):
            errors.append(f"source_set[{index}] must be an object")
            continue
        citation_ref = source.get("citation_ref")
        if isinstance(citation_ref, str):
            citation_refs.add(citation_ref)
        for field_name in ("claim_digest_ref", "source_summary_digest_ref"):
            _validate_digest_ref(f"source_set[{index}].{field_name}", source.get(field_name), errors)
        if source.get("raw_source_body") is not None:
            errors.append(f"source_set[{index}].raw_source_body must be null")
    if len(citation_refs) < 2:
        errors.append("source_set must include at least two citation refs")


def _validate_conflict_set(conflict_set: Any, source_set: Any, errors: list[str]) -> None:
    if not isinstance(conflict_set, list):
        errors.append("conflict_set must be a list")
        return
    source_citations = {
        source.get("citation_ref")
        for source in source_set
        if isinstance(source, dict) and isinstance(source.get("citation_ref"), str)
    }
    for index, conflict in enumerate(conflict_set):
        if not isinstance(conflict, dict):
            errors.append(f"conflict_set[{index}] must be an object")
            continue
        citation_refs = conflict.get("citation_refs")
        if not isinstance(citation_refs, list) or len(citation_refs) < 2:
            errors.append(f"conflict_set[{index}].citation_refs must include at least two refs")
        elif not set(citation_refs).issubset(source_citations):
            errors.append(f"conflict_set[{index}].citation_refs must be drawn from source_set")
        if conflict.get("current_claim_allowed") is not False:
            errors.append(f"conflict_set[{index}].current_claim_allowed must be false")
        if conflict.get("freshness_impact") == "none" and conflict.get("severity") == "high":
            errors.append(f"conflict_set[{index}] high severity requires freshness impact")


def _validate_follow_up_sensing(follow_up_sensing: Any, conflict_set: Any, errors: list[str]) -> None:
    if not isinstance(follow_up_sensing, list):
        errors.append("follow_up_sensing must be a list")
        return
    conflict_refs = {
        conflict.get("conflict_ref")
        for conflict in conflict_set
        if isinstance(conflict, dict) and isinstance(conflict.get("conflict_ref"), str)
    }
    for index, sensing in enumerate(follow_up_sensing):
        if not isinstance(sensing, dict):
            errors.append(f"follow_up_sensing[{index}] must be an object")
            continue
        if sensing.get("conflict_ref") not in conflict_refs:
            errors.append(f"follow_up_sensing[{index}].conflict_ref must reference conflict_set")
        if sensing.get("approval_required") is not True:
            errors.append(f"follow_up_sensing[{index}].approval_required must be true")
        if sensing.get("live_search_allowed") is not False:
            errors.append(f"follow_up_sensing[{index}].live_search_allowed must be false")
        if sensing.get("source_contact_allowed") is not False:
            errors.append(f"follow_up_sensing[{index}].source_contact_allowed must be false")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_retention_policy(retention_policy: Any, errors: list[str]) -> None:
    if not isinstance(retention_policy, dict):
        errors.append("retention_policy must be an object")
        return
    if retention_policy.get("citation_refs_retained") is not True:
        errors.append("retention_policy.citation_refs_retained must be true")
    if retention_policy.get("raw_source_bodies_retained") is not False:
        errors.append("retention_policy.raw_source_bodies_retained must be false")
    if retention_policy.get("private_payload_redacted") is not True:
        errors.append("retention_policy.private_payload_redacted must be true")
    if retention_policy.get("operator_review_required") is not True:
        errors.append("retention_policy.operator_review_required must be true")
    if not isinstance(retention_policy.get("retention_policy_ref"), str) or retention_policy.get("retention_policy_ref") == "":
        errors.append("retention_policy.retention_policy_ref must be non-empty")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    refs = record.get("receipt_refs")
    if not isinstance(summary, dict) or not isinstance(refs, dict):
        errors.append("contract_summary and receipt_refs must be typed")
        return
    expected_counts = {
        "source_count": _list_len(record.get("source_set")),
        "conflict_count": _list_len(record.get("conflict_set")),
        "follow_up_sensing_count": _list_len(record.get("follow_up_sensing")),
        "authority_denial_count": len(DENIED_AUTHORITY_FIELDS),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value:
        errors.append(f"{label} must not store raw source URL or body")


def _get_nested(record: dict[str, Any], parent_name: str, field_name: str) -> Any:
    parent = record.get(parent_name)
    return parent.get(field_name) if isinstance(parent, dict) else None


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
    """Validate ResearchSourceConflictMap artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ResearchSourceConflictMap contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_research_source_conflict_map(args.schema, args.map)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "research_source_conflict_map_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "map_path": workspace_display_path(args.map),
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
        print("[PASS] research_source_conflict_map")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
