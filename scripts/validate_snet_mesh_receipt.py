#!/usr/bin/env python3
"""Validate the SNet mesh receipt contract.

Purpose: verify that SNet read-only mesh receipts match the repository-local
schema and preserve non-terminal, no-authority receipt semantics.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library, scripts/validate_schemas.py, and SNet
runtime contracts.
Invariants:
  - Validation is read-only.
  - SNet mesh receipts are not terminal closure evidence.
  - Raw answers and raw metadata values remain hidden.
  - SNet receipt payloads grant no execution authority.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.snet import SNET_SEMANTICS_HASH, SNET_VERSION, SNetWHType  # noqa: E402
from mcoi_runtime.snet.engine import SNetRecursiveMesh  # noqa: E402
from mcoi_runtime.snet.read_model import SNET_OPERATOR_SURFACE, create_snet_mesh_receipt  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "snet_mesh_receipt.schema.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:snet-mesh-receipt:1"
EXPECTED_SCHEMA_TITLE = "SNet Mesh Receipt"
REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "snet_version",
    "semantics_hash",
    "mesh_digest",
    "surface",
    "symbol_count",
    "question_count",
    "answer_count",
    "metadata_count",
    "relation_count",
    "unknown_count",
    "contradiction_count",
    "max_depth",
    "promotion_threshold",
    "settlement_counts",
    "terminal_closure_required",
    "receipt_is_not_terminal_closure",
    "raw_answers_exposed",
    "raw_metadata_values_exposed",
    "execution_authority_granted",
    "connector_authority_granted",
    "route_authority_granted",
    "filesystem_authority_granted",
    "evidence_refs",
)
SETTLEMENT_COUNT_FIELDS = (
    "active",
    "expanding",
    "settled",
    "dormant",
    "contradictory",
    "unknown_heavy",
    "deprecated",
)


class SNetMeshReceiptContractError(ValueError):
    """Raised when an SNet mesh receipt contract cannot be admitted."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load a JSON object from disk."""
    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SNetMeshReceiptContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""
    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title does not identify SNet mesh receipt")
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
        for field_name in REQUIRED_RECEIPT_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required receipt field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing receipt property: {field_name}")
        errors.extend(_const_property_errors(properties, "surface", SNET_OPERATOR_SURFACE))
        errors.extend(_const_property_errors(properties, "terminal_closure_required", True))
        errors.extend(_const_property_errors(properties, "receipt_is_not_terminal_closure", True))
        errors.extend(_const_property_errors(properties, "raw_answers_exposed", False))
        errors.extend(_const_property_errors(properties, "raw_metadata_values_exposed", False))
        errors.extend(_const_property_errors(properties, "execution_authority_granted", False))
        errors.extend(_const_property_errors(properties, "connector_authority_granted", False))
        errors.extend(_const_property_errors(properties, "route_authority_granted", False))
        errors.extend(_const_property_errors(properties, "filesystem_authority_granted", False))

    settlement_counts = schema.get("properties", {}).get("settlement_counts", {})
    if not isinstance(settlement_counts, dict):
        errors.append("schema settlement_counts must be an object")
    else:
        settlement_required = tuple(settlement_counts.get("required", ()))
        if settlement_required != SETTLEMENT_COUNT_FIELDS:
            errors.append("schema settlement_counts.required must match SNet settlement states")
    return errors


def validate_receipt(receipt: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one SNet mesh receipt."""
    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, receipt)
    if not isinstance(receipt, dict):
        errors.append("receipt must be a JSON object")
        return errors
    missing_fields = [field_name for field_name in REQUIRED_RECEIPT_FIELDS if field_name not in receipt]
    for field_name in missing_fields:
        errors.append(f"receipt missing field: {field_name}")
    extra_fields = sorted(set(receipt) - set(REQUIRED_RECEIPT_FIELDS))
    for field_name in extra_fields:
        errors.append(f"receipt has unexpected field: {field_name}")
    if missing_fields:
        return errors

    if receipt["snet_version"] != SNET_VERSION:
        errors.append("receipt snet_version does not match runtime SNet version")
    if receipt["semantics_hash"] != SNET_SEMANTICS_HASH:
        errors.append("receipt semantics_hash does not match runtime SNet semantics")
    if not _is_receipt_id(receipt["receipt_id"]):
        errors.append("receipt_id must match snet-mesh-[0-9a-f]{16}")
    if not _is_sha256_digest(receipt["mesh_digest"]):
        errors.append("mesh_digest must be a sha256 digest")
    if receipt["surface"] != SNET_OPERATOR_SURFACE:
        errors.append("receipt surface is not the read-only SNet operator surface")
    if receipt["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    if receipt["receipt_is_not_terminal_closure"] is not True:
        errors.append("receipt_is_not_terminal_closure must be true")
    if receipt["raw_answers_exposed"] is not False:
        errors.append("raw_answers_exposed must be false")
    if receipt["raw_metadata_values_exposed"] is not False:
        errors.append("raw_metadata_values_exposed must be false")
    if receipt["execution_authority_granted"] is not False:
        errors.append("execution_authority_granted must be false")
    if receipt["connector_authority_granted"] is not False:
        errors.append("connector_authority_granted must be false")
    if receipt["route_authority_granted"] is not False:
        errors.append("route_authority_granted must be false")
    if receipt["filesystem_authority_granted"] is not False:
        errors.append("filesystem_authority_granted must be false")

    settlement_counts = receipt.get("settlement_counts")
    if isinstance(settlement_counts, dict):
        settlement_total = sum(value for value in settlement_counts.values() if isinstance(value, int))
        if settlement_total != receipt["symbol_count"]:
            errors.append("settlement_counts total must match symbol_count")
    if isinstance(receipt.get("evidence_refs"), list):
        evidence_refs = receipt["evidence_refs"]
        required_prefixes = (
            "snet:mesh_digest:",
            "snet:symbols:",
            "snet:questions:",
            "snet:metadata:",
            "snet:relations:",
            "snet:unknowns:",
            "snet:contradictions:",
        )
        for prefix in required_prefixes:
            if not any(isinstance(ref, str) and ref.startswith(prefix) for ref in evidence_refs):
                errors.append(f"receipt missing evidence ref prefix: {prefix}")
    return errors


def build_sample_receipt() -> dict[str, Any]:
    """Build a deterministic SNet mesh receipt without external effects."""
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(
        seed.symbol_id,
        {
            SNetWHType.DEPENDS_ON: "Water",
            SNetWHType.DEPENDS_ON_ME: "Future plant",
        },
    )
    return create_snet_mesh_receipt(mesh).to_json_dict()


def validate_contract(schema_path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    """Validate schema artifact and generated SNet receipt behavior."""
    schema = _load_schema(schema_path)
    errors = validate_schema_artifact(schema)
    sample_receipt = build_sample_receipt()
    errors.extend(f"sample receipt: {error}" for error in validate_receipt(sample_receipt, schema))

    rejected_receipt = deepcopy(sample_receipt)
    rejected_receipt["raw_answers_exposed"] = True
    if not validate_receipt(rejected_receipt, schema):
        errors.append("raw-answer exposure mutation must be rejected")

    authority_receipt = deepcopy(sample_receipt)
    authority_receipt["execution_authority_granted"] = True
    if not validate_receipt(authority_receipt, schema):
        errors.append("execution-authority mutation must be rejected")
    for field_name in (
        "connector_authority_granted",
        "route_authority_granted",
        "filesystem_authority_granted",
    ):
        mutated_receipt = deepcopy(sample_receipt)
        mutated_receipt[field_name] = True
        if not validate_receipt(mutated_receipt, schema):
            errors.append(f"{field_name} mutation must be rejected")
    return errors


def _const_property_errors(properties: dict[str, Any], field_name: str, expected_value: Any) -> list[str]:
    field_schema = properties.get(field_name)
    if not isinstance(field_schema, dict):
        return [f"schema {field_name} property must be an object"]
    if field_schema.get("const") != expected_value:
        return [f"schema {field_name} const must be {expected_value!r}"]
    return []


def _is_receipt_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    prefix = "snet-mesh-"
    suffix = value[len(prefix) :]
    return value.startswith(prefix) and len(suffix) == 16 and all(char in "0123456789abcdef" for char in suffix)


def _is_sha256_digest(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    prefix = "sha256:"
    suffix = value[len(prefix) :]
    return value.startswith(prefix) and len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix)


def main(argv: list[str] | None = None) -> int:
    """Validate the SNet mesh receipt contract and optional saved receipt."""
    parser = argparse.ArgumentParser(description="Validate SNet mesh receipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)

    try:
        schema = _load_schema(args.schema)
        errors = validate_contract(args.schema)
        if args.receipt is not None:
            receipt = load_json_object(args.receipt, "SNet mesh receipt")
            errors.extend(f"saved receipt: {error}" for error in validate_receipt(receipt, schema))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-contract: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] snet-mesh-receipt: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] snet_mesh_receipt_schema\n")
    sys.stdout.write("[PASS] snet_mesh_receipt_sample\n")
    sys.stdout.write("[PASS] snet_mesh_receipt_no_authority_boundary\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
