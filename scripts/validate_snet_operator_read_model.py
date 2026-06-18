#!/usr/bin/env python3
"""Validate the SNet operator read-model contract.

Purpose: verify that the bounded SNet operator projection matches its public
schema while preserving raw-data suppression and no-authority semantics.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library, scripts/validate_schemas.py, SNet
runtime contracts, and scripts/validate_snet_mesh_receipt.py.
Invariants:
  - Validation is read-only.
  - SNet operator read models expose bounded summaries only.
  - Raw answers and raw metadata values remain hidden.
  - SNet operator read models grant no execution authority.
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

from mcoi_runtime.contracts.snet import SNetWHType  # noqa: E402
from mcoi_runtime.snet.engine import SNetRecursiveMesh  # noqa: E402
from mcoi_runtime.snet.read_model import SNET_OPERATOR_SURFACE, build_snet_operator_read_model  # noqa: E402
from scripts import validate_snet_mesh_receipt as receipt_validator  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "snet_operator_read_model.schema.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:snet-operator-read-model:1"
EXPECTED_SCHEMA_TITLE = "SNet Operator Read Model"
REQUIRED_READ_MODEL_FIELDS = (
    "enabled",
    "surface",
    "raw_answers_exposed",
    "raw_metadata_values_exposed",
    "execution_authority_granted",
    "connector_authority_granted",
    "route_authority_granted",
    "filesystem_authority_granted",
    "episode_replay",
    "receipt_reconstruction",
    "audit_explanation",
    "blocked_authorities",
    "symbol_count",
    "question_count",
    "answer_count",
    "metadata_count",
    "relation_count",
    "unknown_count",
    "contradiction_count",
    "settlement_counts",
    "selected_symbols",
    "truncated_symbol_count",
    "receipt",
)
SYMBOL_SUMMARY_FIELDS = (
    "symbol_id",
    "label",
    "symbol_type",
    "sense_id",
    "ontology_status",
    "settlement_state",
    "depth",
    "parent_context",
    "metadata_count",
    "relation_count",
    "inquiry_count",
)
AUTHORITY_FIELDS = (
    "execution_authority_granted",
    "connector_authority_granted",
    "route_authority_granted",
    "filesystem_authority_granted",
)
RAW_EXPOSURE_FIELDS = ("raw_answers_exposed", "raw_metadata_values_exposed")
COUNT_FIELDS = (
    "symbol_count",
    "question_count",
    "answer_count",
    "metadata_count",
    "relation_count",
    "unknown_count",
    "contradiction_count",
)
BLOCKED_AUTHORITIES = {
    "snet_live_execution_authority",
    "snet_connector_authority",
    "snet_filesystem_authority",
    "snet_autonomous_action_routing",
    "terminal_closure_authority",
}


class SNetOperatorReadModelContractError(ValueError):
    """Raised when an SNet operator read model cannot be admitted."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load a JSON object from disk."""
    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SNetOperatorReadModelContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""
    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title does not identify SNet operator read model")
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
        for field_name in REQUIRED_READ_MODEL_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required read-model field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing read-model property: {field_name}")
        errors.extend(_const_property_errors(properties, "enabled", True))
        errors.extend(_const_property_errors(properties, "surface", SNET_OPERATOR_SURFACE))
        for field_name in RAW_EXPOSURE_FIELDS + AUTHORITY_FIELDS:
            errors.extend(_const_property_errors(properties, field_name, False))

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return errors + ["schema $defs must be an object"]
    symbol_summary = defs.get("symbol_summary")
    if not isinstance(symbol_summary, dict):
        errors.append("schema must define symbol_summary")
    else:
        if symbol_summary.get("additionalProperties") is not False:
            errors.append("symbol_summary must close additional properties")
        summary_required = tuple(symbol_summary.get("required", ()))
        if summary_required != SYMBOL_SUMMARY_FIELDS:
            errors.append("symbol_summary.required must match runtime summary fields")

    receipt_schema = defs.get("snet_mesh_receipt")
    if not isinstance(receipt_schema, dict):
        errors.append("schema must define embedded snet_mesh_receipt")
    else:
        if receipt_schema.get("additionalProperties") is not False:
            errors.append("embedded snet_mesh_receipt must close additional properties")
    return errors


def validate_read_model(read_model: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one SNet operator read model."""
    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, read_model)
    if not isinstance(read_model, dict):
        errors.append("read model must be a JSON object")
        return errors
    missing_fields = [field_name for field_name in REQUIRED_READ_MODEL_FIELDS if field_name not in read_model]
    for field_name in missing_fields:
        errors.append(f"read model missing field: {field_name}")
    extra_fields = sorted(set(read_model) - set(REQUIRED_READ_MODEL_FIELDS))
    for field_name in extra_fields:
        errors.append(f"read model has unexpected field: {field_name}")
    if missing_fields:
        return errors

    if read_model["enabled"] is not True:
        errors.append("enabled must be true")
    if read_model["surface"] != SNET_OPERATOR_SURFACE:
        errors.append("surface is not the read-only SNet operator surface")
    for field_name in RAW_EXPOSURE_FIELDS:
        if read_model[field_name] is not False:
            errors.append(f"{field_name} must be false")
    for field_name in AUTHORITY_FIELDS:
        if read_model[field_name] is not False:
            errors.append(f"{field_name} must be false")

    receipt = read_model.get("receipt")
    if isinstance(receipt, dict):
        errors.extend(f"receipt: {error}" for error in receipt_validator.validate_receipt(receipt))
        for field_name in COUNT_FIELDS:
            if read_model[field_name] != receipt.get(field_name):
                errors.append(f"{field_name} must match receipt")
        if read_model["settlement_counts"] != receipt.get("settlement_counts"):
            errors.append("settlement_counts must match receipt")
        errors.extend(_validate_replay_audit_sections(read_model, receipt))

    selected_symbols = read_model.get("selected_symbols")
    if isinstance(selected_symbols, list):
        symbol_count = read_model["symbol_count"]
        truncated_symbol_count = read_model["truncated_symbol_count"]
        if type(symbol_count) is int and type(truncated_symbol_count) is int:
            if len(selected_symbols) + truncated_symbol_count != symbol_count:
                errors.append("selected symbol count plus truncated_symbol_count must match symbol_count")
        else:
            errors.append("selected symbol count plus truncated_symbol_count must match symbol_count")
        for index, symbol in enumerate(selected_symbols):
            if not isinstance(symbol, dict):
                errors.append(f"selected_symbols[{index}] must be an object")
                continue
            for raw_key in ("answers", "raw_answers", "metadata_values", "raw_metadata_values"):
                if raw_key in symbol:
                    errors.append(f"selected_symbols[{index}] exposes raw field: {raw_key}")
            for field_name in SYMBOL_SUMMARY_FIELDS:
                if field_name not in symbol:
                    errors.append(f"selected_symbols[{index}] missing field: {field_name}")
    for raw_key in ("answers", "raw_answers", "metadata_values", "raw_metadata_values"):
        if raw_key in read_model:
            errors.append(f"read model exposes raw field: {raw_key}")
    return errors


def _validate_replay_audit_sections(read_model: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    episode_replay = read_model.get("episode_replay")
    receipt_reconstruction = read_model.get("receipt_reconstruction")
    audit_explanation = read_model.get("audit_explanation")
    blocked_authorities = read_model.get("blocked_authorities")
    if not isinstance(episode_replay, dict):
        errors.append("episode_replay must be an object")
    else:
        for field_name in (
            "live_execution_authority_granted",
            "connector_authority_granted",
            "filesystem_authority_granted",
            "autonomous_action_routing_granted",
        ):
            if episode_replay.get(field_name) is not False:
                errors.append(f"episode_replay.{field_name} must be false")
        if episode_replay.get("expected_receipt_id") != receipt.get("receipt_id"):
            errors.append("episode_replay.expected_receipt_id must match receipt")
        if episode_replay.get("expected_mesh_digest") != receipt.get("mesh_digest"):
            errors.append("episode_replay.expected_mesh_digest must match receipt")
    if not isinstance(receipt_reconstruction, dict):
        errors.append("receipt_reconstruction must be an object")
    else:
        if receipt_reconstruction.get("receipt_id") != receipt.get("receipt_id"):
            errors.append("receipt_reconstruction.receipt_id must match receipt")
        if receipt_reconstruction.get("mesh_digest") != receipt.get("mesh_digest"):
            errors.append("receipt_reconstruction.mesh_digest must match receipt")
        for field_name in ("raw_answers_required", "raw_metadata_required", "terminal_closure_granted"):
            if receipt_reconstruction.get(field_name) is not False:
                errors.append(f"receipt_reconstruction.{field_name} must be false")
    if not isinstance(audit_explanation, dict):
        errors.append("audit_explanation must be an object")
    else:
        if audit_explanation.get("receipt_id") != receipt.get("receipt_id"):
            errors.append("audit_explanation.receipt_id must match receipt")
        for field_name in (
            "live_execution_authority_denied",
            "connector_authority_denied",
            "filesystem_authority_denied",
            "autonomous_action_routing_denied",
            "terminal_closure_denied",
        ):
            if audit_explanation.get(field_name) is not True:
                errors.append(f"audit_explanation.{field_name} must be true")
    if not isinstance(blocked_authorities, list):
        errors.append("blocked_authorities must be a list")
    elif set(blocked_authorities) != BLOCKED_AUTHORITIES:
        errors.append("blocked_authorities must match SNet audit-only authority denials")
    return errors


def build_sample_read_model(max_symbol_count: int = 2) -> dict[str, Any]:
    """Build a deterministic SNet operator read model without external effects."""
    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(
        seed.symbol_id,
        {
            SNetWHType.DEPENDS_ON: "Water",
            SNetWHType.DEPENDS_ON_ME: "Future plant",
        },
    )
    return build_snet_operator_read_model(mesh, max_symbol_count=max_symbol_count)


def validate_contract(schema_path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    """Validate schema artifact and generated SNet operator read-model behavior."""
    schema = _load_schema(schema_path)
    errors = validate_schema_artifact(schema)
    sample_read_model = build_sample_read_model()
    errors.extend(f"sample read model: {error}" for error in validate_read_model(sample_read_model, schema))

    raw_read_model = deepcopy(sample_read_model)
    raw_read_model["raw_answers_exposed"] = True
    if not validate_read_model(raw_read_model, schema):
        errors.append("raw-answer exposure mutation must be rejected")

    raw_field_read_model = deepcopy(sample_read_model)
    raw_field_read_model["answers"] = ["Water"]
    if not validate_read_model(raw_field_read_model, schema):
        errors.append("raw answer field mutation must be rejected")

    for field_name in AUTHORITY_FIELDS:
        authority_read_model = deepcopy(sample_read_model)
        authority_read_model[field_name] = True
        if not validate_read_model(authority_read_model, schema):
            errors.append(f"{field_name} mutation must be rejected")
    return errors


def _const_property_errors(properties: dict[str, Any], field_name: str, expected_value: Any) -> list[str]:
    field_schema = properties.get(field_name)
    if not isinstance(field_schema, dict):
        return [f"schema {field_name} property must be an object"]
    if field_schema.get("const") != expected_value:
        return [f"schema {field_name} const must be {expected_value!r}"]
    return []


def main(argv: list[str] | None = None) -> int:
    """Validate the SNet operator read-model contract and optional saved model."""
    parser = argparse.ArgumentParser(description="Validate SNet operator read-model contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--read-model", type=Path)
    args = parser.parse_args(argv)

    try:
        schema = _load_schema(args.schema)
        errors = validate_contract(args.schema)
        if args.read_model is not None:
            read_model = load_json_object(args.read_model, "SNet operator read model")
            errors.extend(f"saved read model: {error}" for error in validate_read_model(read_model, schema))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-contract: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] snet-operator-read-model: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] snet_operator_read_model_schema\n")
    sys.stdout.write("[PASS] snet_operator_read_model_sample\n")
    sys.stdout.write("[PASS] snet_operator_read_model_no_authority_boundary\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
