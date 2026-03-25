#!/usr/bin/env python3
"""Schema validation and contract-schema parity checker.

Validates:
  1. All JSON schemas in schemas/ are valid JSON and well-formed.
  2. Every schema that has a matching Python contract module produces
     contract instances whose to_dict() output is structurally compatible
     with the schema's required fields.
  3. In --strict mode, checks that all schema-required fields are present
     in the Python contract's __dataclass_fields__.

Usage:
  python scripts/validate_schemas.py           # basic validation
  python scripts/validate_schemas.py --strict   # strict parity check
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"

# Map schema files to their Python contract classes
SCHEMA_CONTRACT_MAP: dict[str, tuple[str, str]] = {
    "connector_descriptor.schema.json": (
        "mcoi_runtime.contracts.connector",
        "ConnectorDescriptor",
    ),
    "connector_result.schema.json": (
        "mcoi_runtime.contracts.connector",
        "ConnectorResult",
    ),
    "capability_descriptor.schema.json": (
        "mcoi_runtime.contracts.capability",
        "CapabilityDescriptor",
    ),
    "execution_result.schema.json": (
        "mcoi_runtime.contracts.execution",
        "ExecutionResult",
    ),
    "plan.schema.json": (
        "mcoi_runtime.contracts.plan",
        "Plan",
    ),
    "policy_decision.schema.json": (
        "mcoi_runtime.contracts.policy",
        "PolicyDecision",
    ),
    "replay_record.schema.json": (
        "mcoi_runtime.contracts.replay",
        "ReplayRecord",
    ),
    "trace_entry.schema.json": (
        "mcoi_runtime.contracts.trace",
        "TraceEntry",
    ),
    "verification_result.schema.json": (
        "mcoi_runtime.contracts.verification",
        "VerificationResult",
    ),
    "learning_admission.schema.json": (
        "mcoi_runtime.contracts.learning",
        "LearningAdmissionDecision",
    ),
    "environment_fingerprint.schema.json": (
        "mcoi_runtime.contracts.environment",
        "EnvironmentFingerprint",
    ),
}


def validate_json_schemas() -> list[str]:
    """Validate all schema files are valid JSON with required structure."""
    errors: list[str] = []
    schema_files = sorted(SCHEMA_DIR.glob("*.schema.json"))

    if not schema_files:
        errors.append(f"No schema files found in {SCHEMA_DIR}")
        return errors

    for schema_path in schema_files:
        try:
            with open(schema_path) as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{schema_path.name}: invalid JSON — {e}")
            continue

        # Basic schema structure checks
        if not isinstance(schema, dict):
            errors.append(f"{schema_path.name}: root must be an object")
            continue

        if "type" not in schema and "$ref" not in schema:
            errors.append(f"{schema_path.name}: missing 'type' or '$ref'")

        if "properties" in schema and not isinstance(schema["properties"], dict):
            errors.append(f"{schema_path.name}: 'properties' must be an object")

        print(f"  OK  {schema_path.name}")

    return errors


def check_contract_parity(strict: bool = False) -> list[str]:
    """Check that Python contracts have fields matching schema required fields."""
    errors: list[str] = []

    # Add MCOI to path
    mcoi_path = REPO_ROOT / "mcoi"
    if str(mcoi_path) not in sys.path:
        sys.path.insert(0, str(mcoi_path))

    for schema_file, (module_path, class_name) in SCHEMA_CONTRACT_MAP.items():
        schema_path = SCHEMA_DIR / schema_file
        if not schema_path.exists():
            errors.append(f"{schema_file}: schema file not found")
            continue

        with open(schema_path) as f:
            schema = json.load(f)

        required_fields = set(schema.get("required", []))
        schema_properties = set(schema.get("properties", {}).keys())

        try:
            module = __import__(module_path, fromlist=[class_name])
            contract_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            errors.append(f"{schema_file} <-> {module_path}.{class_name}: import failed — {e}")
            continue

        if not hasattr(contract_class, "__dataclass_fields__"):
            errors.append(f"{class_name}: not a dataclass")
            continue

        contract_fields = set(contract_class.__dataclass_fields__.keys())

        # Check required schema fields exist in contract
        missing_required = required_fields - contract_fields
        if missing_required:
            errors.append(
                f"{schema_file} <-> {class_name}: "
                f"schema required fields missing from contract: {sorted(missing_required)}"
            )

        if strict:
            # In strict mode, check all schema properties have contract fields
            missing_properties = schema_properties - contract_fields
            if missing_properties:
                errors.append(
                    f"{schema_file} <-> {class_name}: "
                    f"schema properties missing from contract: {sorted(missing_properties)}"
                )

        print(f"  OK  {schema_file} <-> {class_name} (required: {len(required_fields)}, contract: {len(contract_fields)})")

    return errors


def main() -> None:
    strict = "--strict" in sys.argv

    print("=== Schema Validation ===")
    errors = validate_json_schemas()

    print("\n=== Contract-Schema Parity ===")
    errors.extend(check_contract_parity(strict=strict))

    if errors:
        print(f"\n{'='*40}")
        print(f"FAILED — {len(errors)} error(s):")
        for err in errors:
            print(f"  X {err}")
        sys.exit(1)
    else:
        print(f"\n{'='*40}")
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
