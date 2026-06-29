#!/usr/bin/env python3
"""Validate the capability proof-of-success contract registry.

Purpose: verify that loaded governed capabilities have success contracts that
    cannot claim completion beyond causal proof.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS for capability
    success claims and false-success blocking.
Dependencies: capability success contract schema, capability packs, and MCOI
    runtime contracts.
Invariants:
  - Every loaded capability receives exactly one success contract.
  - Expected and forbidden deltas preserve capability effect models.
  - Mandatory capability evidence remains mandatory proof evidence.
  - High-risk contracts require independent evidence and authority blocking.
  - Pending evidence can never be labeled as completed success.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry  # noqa: E402
from mcoi_runtime.core.capability_success_contract_registry import (  # noqa: E402
    CapabilitySuccessContractRegistry,
    validate_contract_against_entry,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "capability_success_contract_registry.schema.json"
REGISTRY_PATH = WORKSPACE_ROOT / "governance" / "capability_success_contract_registry.foundation.json"
PROHIBITED_PRIVATE_REASONING_FIELDS = {
    "chain_of_thought",
    "raw_chain_of_thought",
    "private_reasoning",
    "hidden_reasoning",
    "scratchpad",
}


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load a workspace-local JSON object."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {_relative(json_path)}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_registry_record(record: dict[str, Any]) -> list[str]:
    """Validate one capability success registry record."""

    schema = _load_schema(SCHEMA_PATH)
    errors = [f"schema: {error}" for error in _validate_schema_instance(schema, record)]
    errors.extend(_validate_no_private_reasoning_fields(record, "capability_success_registry"))
    if errors:
        return errors

    try:
        entries = _load_registry_capability_entries(record)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"capability_success_registry: {_sanitize_error(exc)}"]
    entry_by_capability = {entry.capability_id: entry for entry in entries}

    try:
        registry = CapabilitySuccessContractRegistry.from_capability_entries(
            entries,
            overrides=tuple(record.get("contract_overrides", ())),
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        return [f"capability_success_registry: {_sanitize_error(exc)}"]

    read_model = registry.read_model()
    errors.extend(_validate_coverage_policy(record, read_model, entries))
    proof_policy = record["coverage_policy"]["minimum_proof_level_by_risk"]
    for capability_id, entry in sorted(entry_by_capability.items()):
        contract = registry.get_contract(capability_id)
        errors.extend(
            f"capability_success_registry: {capability_id}: {error}"
            for error in validate_contract_against_entry(
                contract,
                entry,
                minimum_proof_by_risk=proof_policy,
            )
        )
    return errors


def validate_contract(payload_path: Path = REGISTRY_PATH) -> list[str]:
    """Validate the canonical capability success registry artifact."""

    record = load_json_object(payload_path, "capability success contract registry")
    return validate_registry_record(record)


def build_validation_report(payload_path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Build a machine-readable validation receipt."""

    try:
        record = load_json_object(payload_path, "capability success contract registry")
        errors = validate_registry_record(record)
        entry_count = len(_load_registry_capability_entries(record)) if not errors else 0
        override_count = len(record.get("contract_overrides", ())) if isinstance(record, dict) else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-capability-success-contract-registry: {_sanitize_error(exc)}"]
        entry_count = 0
        override_count = 0
    valid = not errors
    checks = (
        "capability_success_registry_schema",
        "capability_success_registry_pack_refs",
        "capability_success_registry_full_coverage",
        "capability_success_registry_effect_delta_binding",
        "capability_success_registry_mandatory_evidence_binding",
        "capability_success_registry_authority_gate",
        "capability_success_registry_false_success_block",
        "capability_success_registry_receipt_integrity",
    )
    return {
        "receipt_id": "capability_success_contract_registry_validation_receipt",
        "valid": valid,
        "status": "passed" if valid else "failed",
        "schema_path": _relative(SCHEMA_PATH),
        "payload_path": _relative(payload_path),
        "loaded_capability_count": entry_count,
        "override_contract_count": override_count,
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def _load_registry_capability_entries(record: dict[str, Any]) -> tuple[CapabilityRegistryEntry, ...]:
    entries: list[CapabilityRegistryEntry] = []
    seen_refs: set[str] = set()
    for raw_ref in record.get("loaded_capability_pack_refs", ()):
        pack_ref = str(raw_ref)
        if pack_ref in seen_refs:
            raise ValueError(f"duplicate capability pack ref: {pack_ref}")
        seen_refs.add(pack_ref)
        pack_path = _workspace_path(pack_ref)
        pack = load_json_object(pack_path, f"capability pack {pack_ref}")
        raw_capabilities = pack.get("capabilities")
        if not isinstance(raw_capabilities, list):
            raise ValueError(f"capability pack must contain capabilities array: {pack_ref}")
        for index, raw_capability in enumerate(raw_capabilities):
            if not isinstance(raw_capability, dict):
                raise ValueError(f"capability pack entry must be an object: {pack_ref} capabilities[{index}]")
            entries.append(CapabilityRegistryEntry.from_mapping(raw_capability))
    capability_ids = [entry.capability_id for entry in entries]
    duplicates = sorted({capability_id for capability_id in capability_ids if capability_ids.count(capability_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate loaded capability ids: {duplicates}")
    return tuple(entries)


def _validate_coverage_policy(
    record: dict[str, Any],
    read_model: dict[str, Any],
    entries: tuple[CapabilityRegistryEntry, ...],
) -> list[str]:
    errors: list[str] = []
    policy = record.get("coverage_policy") if isinstance(record.get("coverage_policy"), dict) else {}
    if policy.get("require_contract_for_every_loaded_capability") is True:
        if read_model["contract_count"] != len(entries):
            errors.append(
                "capability_success_registry: contract count does not match loaded capability count"
            )
        loaded_ids = {entry.capability_id for entry in entries}
        registry_ids = set(read_model["capability_ids"])
        missing = sorted(loaded_ids - registry_ids)
        extra = sorted(registry_ids - loaded_ids)
        if missing:
            errors.append(f"capability_success_registry: missing contracts for {missing}")
        if extra:
            errors.append(f"capability_success_registry: extra contracts for {extra}")
    return errors


def _validate_no_private_reasoning_fields(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PROHIBITED_PRIVATE_REASONING_FIELDS:
                errors.append(f"{path}.{key} is prohibited")
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_validate_no_private_reasoning_fields(child, f"{path}[{index}]"))
    return errors


def _workspace_path(path_ref: str) -> Path:
    if not path_ref.strip():
        raise ValueError("path ref must be non-empty")
    candidate = (WORKSPACE_ROOT / path_ref).resolve(strict=False)
    try:
        candidate.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError(f"path ref escapes workspace: {path_ref}") from exc
    return candidate


def _relative(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    for path in (SCHEMA_PATH, REGISTRY_PATH, WORKSPACE_ROOT):
        message = message.replace(str(path), _relative(path) if path != WORKSPACE_ROOT else ".")
        message = message.replace(str(path.resolve(strict=False)), _relative(path) if path != WORKSPACE_ROOT else ".")
    return message


def main(argv: list[str] | None = None) -> int:
    """Validate capability success contract registry artifacts."""

    parser = argparse.ArgumentParser(description="Validate capability proof-of-success registry.")
    parser.add_argument("--payload", type=Path, default=REGISTRY_PATH, help="registry payload to validate")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)

    payload_path = args.payload if args.payload.is_absolute() else WORKSPACE_ROOT / args.payload
    report = build_validation_report(payload_path)
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1
    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] capability-success-registry: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
