#!/usr/bin/env python3
"""Validate the SNet episode replay contract.

Purpose: verify that a bounded SNet episode can be replayed from governed
inputs and produce the expected read-only mesh receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, scripts/validate_schemas.py, SNet
runtime contracts, and scripts/validate_snet_mesh_receipt.py.
Invariants:
  - Validation is read-only.
  - Episode replay is deterministic for the same governed input.
  - Episode answer bindings are bounded to the finite SNet WH spine.
  - Episode replay grants no execution, connector, route, or filesystem authority.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
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

from mcoi_runtime.contracts.snet import (  # noqa: E402
    SNET_SEMANTICS_HASH,
    SNET_VERSION,
    SNetInquiryBudget,
    SNetOntologyStatus,
    SNetValidationState,
    SNetWHType,
    WH_TYPES,
)
from mcoi_runtime.snet.engine import SNetRecursiveMesh  # noqa: E402
from mcoi_runtime.snet.read_model import create_snet_mesh_receipt  # noqa: E402
from scripts import validate_snet_mesh_receipt as receipt_validator  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "snet_episode.schema.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:snet-episode:1"
EXPECTED_SCHEMA_TITLE = "SNet Episode"
SNET_EPISODE_SURFACE = "snet_episode_replay"
REQUIRED_EPISODE_FIELDS = (
    "episode_id",
    "snet_version",
    "semantics_hash",
    "surface",
    "replay_mode",
    "tick_scope",
    "input_digest",
    "seed_symbol",
    "budget",
    "perspective",
    "context",
    "confidence",
    "validation_state",
    "answer_bindings",
    "expected_mesh_digest",
    "expected_receipt_id",
    "expected_counts",
    "expected_receipt",
    "raw_answers_bounded",
    "raw_answers_exposed",
    "raw_metadata_values_exposed",
    "execution_authority_granted",
    "connector_authority_granted",
    "route_authority_granted",
    "filesystem_authority_granted",
    "evidence_refs",
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
WH_FIELD_NAMES = tuple(wh_type.value for wh_type in WH_TYPES)


class SNetEpisodeReplayContractError(ValueError):
    """Raised when an SNet episode replay contract cannot be admitted."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load a JSON object from disk."""
    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SNetEpisodeReplayContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""
    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title does not identify SNet episode")
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
        for field_name in REQUIRED_EPISODE_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required episode field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing episode property: {field_name}")
        errors.extend(_const_property_errors(properties, "snet_version", SNET_VERSION))
        errors.extend(_const_property_errors(properties, "semantics_hash", SNET_SEMANTICS_HASH))
        errors.extend(_const_property_errors(properties, "surface", SNET_EPISODE_SURFACE))
        errors.extend(_const_property_errors(properties, "replay_mode", "deterministic_local"))
        errors.extend(_const_property_errors(properties, "tick_scope", "root_single_tick"))
        errors.extend(_const_property_errors(properties, "raw_answers_bounded", True))
        for field_name in RAW_EXPOSURE_FIELDS + AUTHORITY_FIELDS:
            errors.extend(_const_property_errors(properties, field_name, False))

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return errors + ["schema $defs must be an object"]
    answer_bindings = defs.get("answer_bindings")
    if not isinstance(answer_bindings, dict):
        errors.append("schema must define answer_bindings")
    else:
        answer_properties = answer_bindings.get("properties")
        if not isinstance(answer_properties, dict):
            errors.append("answer_bindings.properties must be an object")
        else:
            missing_wh_fields = sorted(set(WH_FIELD_NAMES) - set(answer_properties))
            if missing_wh_fields:
                errors.append(f"answer_bindings missing WH fields: {missing_wh_fields}")
        if answer_bindings.get("additionalProperties") is not False:
            errors.append("answer_bindings must close additional properties")
        if answer_bindings.get("maxProperties") != len(WH_TYPES):
            errors.append("answer_bindings.maxProperties must match SNet WH spine length")
    return errors


def validate_episode(episode: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one SNet episode."""
    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, episode)
    missing_fields = [field_name for field_name in REQUIRED_EPISODE_FIELDS if field_name not in episode]
    for field_name in missing_fields:
        errors.append(f"episode missing field: {field_name}")
    extra_fields = sorted(set(episode) - set(REQUIRED_EPISODE_FIELDS))
    for field_name in extra_fields:
        errors.append(f"episode has unexpected field: {field_name}")
    if missing_fields:
        return errors

    if episode["snet_version"] != SNET_VERSION:
        errors.append("snet_version must match runtime SNet version")
    if episode["semantics_hash"] != SNET_SEMANTICS_HASH:
        errors.append("semantics_hash must match runtime SNet semantics")
    if not _is_episode_id(episode["episode_id"]):
        errors.append("episode_id must match snet-episode-[0-9a-f]{16}")
    if episode["surface"] != SNET_EPISODE_SURFACE:
        errors.append("surface must be snet_episode_replay")
    if episode["replay_mode"] != "deterministic_local":
        errors.append("replay_mode must be deterministic_local")
    if episode["tick_scope"] != "root_single_tick":
        errors.append("tick_scope must be root_single_tick")
    if episode["raw_answers_bounded"] is not True:
        errors.append("raw_answers_bounded must be true")
    for field_name in RAW_EXPOSURE_FIELDS:
        if episode[field_name] is not False:
            errors.append(f"{field_name} must be false")
    for field_name in AUTHORITY_FIELDS:
        if episode[field_name] is not False:
            errors.append(f"{field_name} must be false")
    for raw_key in ("raw_answer", "raw_answers", "raw_metadata_values", "metadata_values"):
        if raw_key in episode:
            errors.append(f"episode exposes raw field: {raw_key}")

    input_payload = _input_payload_from_episode(episode)
    try:
        expected_input_digest = _sha256_json(input_payload)
    except (TypeError, ValueError) as exc:
        errors.append(f"replay input digest failed: {exc}")
        return errors
    if episode["input_digest"] != expected_input_digest:
        errors.append("input_digest must match replay input payload")
    expected_episode_id = _episode_id_from_input_digest(expected_input_digest)
    if episode["episode_id"] != expected_episode_id:
        errors.append("episode_id must derive from input_digest")

    try:
        replay_receipt = replay_episode(episode)
    except (AttributeError, KeyError, ValueError, TypeError) as exc:
        errors.append(f"replay failed: {exc}")
        return errors

    replay_receipt_json = replay_receipt.to_json_dict()
    expected_receipt = episode["expected_receipt"]
    if isinstance(expected_receipt, dict):
        errors.extend(f"expected_receipt: {error}" for error in receipt_validator.validate_receipt(expected_receipt))
    else:
        errors.append("expected_receipt must be a JSON object")
    errors.extend(f"replay_receipt: {error}" for error in receipt_validator.validate_receipt(replay_receipt_json))
    if episode["expected_mesh_digest"] != replay_receipt.mesh_digest:
        errors.append("expected_mesh_digest must match replay mesh_digest")
    if episode["expected_receipt_id"] != replay_receipt.receipt_id:
        errors.append("expected_receipt_id must match replay receipt_id")
    if expected_receipt != replay_receipt_json:
        errors.append("expected_receipt must match replay receipt")
    expected_counts = episode.get("expected_counts")
    if isinstance(expected_counts, dict):
        for field_name in COUNT_FIELDS:
            if expected_counts.get(field_name) != replay_receipt_json[field_name]:
                errors.append(f"expected_counts.{field_name} must match replay receipt")
    return errors


def replay_episode(episode: dict[str, Any]):
    """Replay one governed SNet episode and return the resulting mesh receipt."""
    budget_payload = episode["budget"]
    budget = SNetInquiryBudget(
        max_depth=budget_payload["max_depth"],
        max_questions_per_symbol=budget_payload["max_questions_per_symbol"],
        promotion_threshold=budget_payload["promotion_threshold"],
        unknown_gravity_threshold=budget_payload["unknown_gravity_threshold"],
    )
    seed_payload = episode["seed_symbol"]
    ontology_status = SNetOntologyStatus(seed_payload["ontology_status"])
    mesh = SNetRecursiveMesh(budget=budget)
    seed = mesh.add_symbol(
        seed_payload["label"],
        symbol_type=seed_payload["symbol_type"],
        sense_id=seed_payload["sense_id"],
        definition=seed_payload["definition"],
        ontology_status=ontology_status,
    )
    answer_map = {
        SNetWHType(field_name): answer
        for field_name, answer in episode["answer_bindings"].items()
    }
    validation_state = SNetValidationState(episode["validation_state"])
    mesh.run_tick_with_answers(
        seed.symbol_id,
        answer_map,
        perspective=episode["perspective"],
        context=episode["context"],
        confidence=episode["confidence"],
        validation_state=validation_state,
    )
    return create_snet_mesh_receipt(mesh)


def build_sample_episode() -> dict[str, Any]:
    """Build a deterministic SNet episode fixture without external effects."""
    base_episode: dict[str, Any] = {
        "snet_version": SNET_VERSION,
        "semantics_hash": SNET_SEMANTICS_HASH,
        "surface": SNET_EPISODE_SURFACE,
        "replay_mode": "deterministic_local",
        "tick_scope": "root_single_tick",
        "seed_symbol": {
            "label": "Seed",
            "symbol_type": "physical_biological_object",
            "sense_id": "",
            "definition": "",
            "ontology_status": "unknown_status",
        },
        "budget": {
            "max_depth": 3,
            "max_questions_per_symbol": len(WH_TYPES),
            "promotion_threshold": 0.65,
            "unknown_gravity_threshold": 3,
        },
        "perspective": "general",
        "context": "general",
        "confidence": 0.75,
        "validation_state": "supported",
        "answer_bindings": {
            "depends_on": "Water",
            "depends_on_me": "Future plant",
        },
        "raw_answers_bounded": True,
        "raw_answers_exposed": False,
        "raw_metadata_values_exposed": False,
        "execution_authority_granted": False,
        "connector_authority_granted": False,
        "route_authority_granted": False,
        "filesystem_authority_granted": False,
        "evidence_refs": (
            "snet:episode:seed-dependency",
            "snet:episode:root-single-tick",
        ),
    }
    input_digest = _sha256_json(_input_payload_from_episode(base_episode))
    episode = {
        "episode_id": _episode_id_from_input_digest(input_digest),
        "input_digest": input_digest,
        **base_episode,
    }
    replay_receipt = replay_episode(episode).to_json_dict()
    episode["expected_mesh_digest"] = replay_receipt["mesh_digest"]
    episode["expected_receipt_id"] = replay_receipt["receipt_id"]
    episode["expected_counts"] = {
        field_name: replay_receipt[field_name]
        for field_name in COUNT_FIELDS
    }
    episode["expected_receipt"] = replay_receipt
    return json.loads(json.dumps(episode, sort_keys=True))


def validate_contract(schema_path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    """Validate schema artifact and generated SNet episode replay behavior."""
    schema = _load_schema(schema_path)
    errors = validate_schema_artifact(schema)
    sample_episode = build_sample_episode()
    errors.extend(f"sample episode: {error}" for error in validate_episode(sample_episode, schema))

    answer_drift_episode = deepcopy(sample_episode)
    answer_drift_episode["answer_bindings"]["depends_on"] = "Sunlight"
    if not validate_episode(answer_drift_episode, schema):
        errors.append("answer drift mutation must be rejected")

    raw_field_episode = deepcopy(sample_episode)
    raw_field_episode["raw_answers"] = ["Water"]
    if not validate_episode(raw_field_episode, schema):
        errors.append("raw answer field mutation must be rejected")

    for field_name in AUTHORITY_FIELDS:
        authority_episode = deepcopy(sample_episode)
        authority_episode[field_name] = True
        if not validate_episode(authority_episode, schema):
            errors.append(f"{field_name} mutation must be rejected")
    return errors


def _input_payload_from_episode(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "snet_version": episode["snet_version"],
        "semantics_hash": episode["semantics_hash"],
        "surface": episode["surface"],
        "replay_mode": episode["replay_mode"],
        "tick_scope": episode["tick_scope"],
        "seed_symbol": episode["seed_symbol"],
        "budget": episode["budget"],
        "perspective": episode["perspective"],
        "context": episode["context"],
        "confidence": episode["confidence"],
        "validation_state": episode["validation_state"],
        "answer_bindings": episode["answer_bindings"],
    }


def _sha256_json(payload: dict[str, Any]) -> str:
    encoded_payload = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"sha256:{sha256(encoded_payload.encode('utf-8')).hexdigest()}"


def _episode_id_from_input_digest(input_digest: str) -> str:
    return f"snet-episode-{sha256(input_digest.encode('utf-8')).hexdigest()[:16]}"


def _const_property_errors(properties: dict[str, Any], field_name: str, expected_value: Any) -> list[str]:
    field_schema = properties.get(field_name)
    if not isinstance(field_schema, dict):
        return [f"schema {field_name} property must be an object"]
    if field_schema.get("const") != expected_value:
        return [f"schema {field_name} const must be {expected_value!r}"]
    return []


def _is_episode_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    prefix = "snet-episode-"
    suffix = value[len(prefix) :]
    return value.startswith(prefix) and len(suffix) == 16 and all(char in "0123456789abcdef" for char in suffix)


def main(argv: list[str] | None = None) -> int:
    """Validate the SNet episode replay contract and optional saved episode."""
    parser = argparse.ArgumentParser(description="Validate SNet episode replay contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--episode", type=Path)
    parser.add_argument("--emit-sample", action="store_true")
    args = parser.parse_args(argv)

    try:
        schema = _load_schema(args.schema)
        if args.emit_sample:
            sys.stdout.write(json.dumps(build_sample_episode(), indent=2, sort_keys=True))
            sys.stdout.write("\n")
            return 0
        errors = validate_contract(args.schema)
        if args.episode is not None:
            episode = load_json_object(args.episode, "SNet episode")
            errors.extend(f"saved episode: {error}" for error in validate_episode(episode, schema))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-contract: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] snet-episode-replay: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] snet_episode_schema\n")
    sys.stdout.write("[PASS] snet_episode_sample_replay\n")
    sys.stdout.write("[PASS] snet_episode_drift_rejection\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
