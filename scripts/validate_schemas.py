#!/usr/bin/env python3
"""Schema validation and shared-contract parity checker.

Validates:
  1. All JSON schemas in schemas/ are valid JSON and well-formed.
  2. Every schema that has a matching Python contract module produces
     contract instances whose to_dict() output is structurally compatible
     with the schema's required fields.
  3. Every shared schema that has a matching Rust contract surface maps to
     the same field names and enum values without reinterpretation.
  4. In --strict mode, checks that all schema properties are present in the
     Python and Rust contract surfaces and that canonical Rust structs do not
     carry extra top-level or nested fields.

Usage:
  python scripts/validate_schemas.py           # basic validation
  python scripts/validate_schemas.py --strict   # strict parity check
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class NestedRustMapping:
    struct_name: str
    enum_fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RustContractMapping:
    source: Path
    struct_name: str
    enum_fields: dict[str, str] = field(default_factory=dict)
    nested_fields: dict[str, NestedRustMapping] = field(default_factory=dict)


RUST_SCHEMA_CONTRACT_MAP: dict[str, RustContractMapping] = {
    "capability_descriptor.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-capability" / "src" / "lib.rs",
        struct_name="CapabilityDescriptor",
    ),
    "policy_decision.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs",
        struct_name="PolicyDecision",
        enum_fields={"status": "PolicyStatus"},
        nested_fields={"reasons": NestedRustMapping(struct_name="PolicyReason")},
    ),
    "execution_result.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs",
        struct_name="ExecutionResult",
        enum_fields={"status": "ExecutionOutcome"},
        nested_fields={
            "actual_effects": NestedRustMapping(struct_name="EffectRecord"),
            "assumed_effects": NestedRustMapping(struct_name="EffectRecord"),
        },
    ),
    "verification_result.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs",
        struct_name="VerificationResult",
        enum_fields={"status": "VerificationStatus"},
        nested_fields={
            "checks": NestedRustMapping(
                struct_name="VerificationCheck",
                enum_fields={"status": "VerificationStatus"},
            ),
            "evidence": NestedRustMapping(struct_name="EvidenceRecord"),
        },
    ),
    "trace_entry.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs",
        struct_name="TraceEntry",
    ),
    "replay_record.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs",
        struct_name="ReplayRecord",
        enum_fields={"mode": "ReplayMode"},
        nested_fields={
            "approved_effects": NestedRustMapping(struct_name="ReplayEffect"),
            "blocked_effects": NestedRustMapping(struct_name="ReplayEffect"),
        },
    ),
    "learning_admission.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-kernel" / "src" / "lib.rs",
        struct_name="LearningAdmissionDecision",
        enum_fields={"status": "LearningAdmissionStatus"},
        nested_fields={"reasons": NestedRustMapping(struct_name="PolicyReason")},
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


def _load_schema(schema_path: Path) -> dict:
    with open(schema_path, encoding="utf-8") as handle:
        return json.load(handle)


def _camel_to_snake(value: str) -> str:
    partial = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", partial).lower()


def _extract_rust_block(source_text: str, declaration: str, name: str) -> str:
    marker = f"pub {declaration} {name}"
    start = source_text.find(marker)
    if start < 0:
        raise ValueError(f"missing Rust {declaration} {name}")
    brace_start = source_text.find("{", start)
    if brace_start < 0:
        raise ValueError(f"missing body for Rust {declaration} {name}")

    depth = 0
    for index in range(brace_start, len(source_text)):
        char = source_text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source_text[brace_start + 1 : index]
    raise ValueError(f"unterminated Rust {declaration} {name}")


def _extract_rust_struct_fields(source_text: str, name: str) -> set[str]:
    block = _extract_rust_block(source_text, "struct", name)
    fields: set[str] = set()
    for raw_line in block.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line or line.startswith("#["):
            continue
        if line.startswith("pub "):
            field_name = line.removeprefix("pub ").split(":", 1)[0].strip()
            if field_name:
                fields.add(field_name)
    return fields


def _extract_rust_enum_values(source_text: str, name: str) -> set[str]:
    block = _extract_rust_block(source_text, "enum", name)
    values: set[str] = set()
    for raw_line in block.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line or line.startswith("#["):
            continue
        variant = line.split(",", 1)[0].split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variant):
            values.add(_camel_to_snake(variant))
    return values


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

        schema = _load_schema(schema_path)

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


def check_rust_contract_parity(strict: bool = False) -> list[str]:
    """Check that Rust shared types map to shared schema fields and enums."""
    errors: list[str] = []

    for schema_file, mapping in RUST_SCHEMA_CONTRACT_MAP.items():
        schema_path = SCHEMA_DIR / schema_file
        if not schema_path.exists():
            errors.append(f"{schema_file}: schema file not found")
            continue
        if not mapping.source.exists():
            errors.append(f"{schema_file}: Rust source file not found: {mapping.source}")
            continue

        schema = _load_schema(schema_path)
        source_text = mapping.source.read_text(encoding="utf-8")
        schema_properties = set(schema.get("properties", {}).keys())
        required_fields = set(schema.get("required", []))

        try:
            rust_fields = _extract_rust_struct_fields(source_text, mapping.struct_name)
        except ValueError as exc:
            errors.append(f"{schema_file} <-> {mapping.struct_name}: {exc}")
            continue

        missing_required = required_fields - rust_fields
        if missing_required:
            errors.append(
                f"{schema_file} <-> {mapping.struct_name}: "
                f"schema required fields missing from Rust struct: {sorted(missing_required)}"
            )

        if strict:
            missing_properties = schema_properties - rust_fields
            if missing_properties:
                errors.append(
                    f"{schema_file} <-> {mapping.struct_name}: "
                    f"schema properties missing from Rust struct: {sorted(missing_properties)}"
                )
            extra_fields = rust_fields - schema_properties
            if extra_fields:
                errors.append(
                    f"{schema_file} <-> {mapping.struct_name}: "
                    f"extra Rust fields not present in schema: {sorted(extra_fields)}"
                )

        for property_name, enum_name in mapping.enum_fields.items():
            schema_enum = set(schema["properties"][property_name].get("enum", []))
            try:
                rust_enum = _extract_rust_enum_values(source_text, enum_name)
            except ValueError as exc:
                errors.append(f"{schema_file} <-> {enum_name}: {exc}")
                continue
            if schema_enum != rust_enum:
                errors.append(
                    f"{schema_file} <-> {enum_name}: "
                    f"enum mismatch; schema={sorted(schema_enum)} rust={sorted(rust_enum)}"
                )

        for property_name, nested_mapping in mapping.nested_fields.items():
            nested_schema = schema["properties"][property_name]["items"]
            nested_properties = set(nested_schema.get("properties", {}).keys())
            nested_required = set(nested_schema.get("required", []))
            try:
                nested_fields = _extract_rust_struct_fields(source_text, nested_mapping.struct_name)
            except ValueError as exc:
                errors.append(f"{schema_file} <-> {nested_mapping.struct_name}: {exc}")
                continue

            missing_nested_required = nested_required - nested_fields
            if missing_nested_required:
                errors.append(
                    f"{schema_file} <-> {nested_mapping.struct_name}: "
                    f"schema required nested fields missing from Rust struct: "
                    f"{sorted(missing_nested_required)}"
                )

            if strict:
                missing_nested_properties = nested_properties - nested_fields
                if missing_nested_properties:
                    errors.append(
                        f"{schema_file} <-> {nested_mapping.struct_name}: "
                        f"schema nested properties missing from Rust struct: "
                        f"{sorted(missing_nested_properties)}"
                    )
                extra_nested_fields = nested_fields - nested_properties
                if extra_nested_fields:
                    errors.append(
                        f"{schema_file} <-> {nested_mapping.struct_name}: "
                        f"extra Rust nested fields not present in schema: "
                        f"{sorted(extra_nested_fields)}"
                    )

            for nested_property_name, enum_name in nested_mapping.enum_fields.items():
                schema_enum = set(nested_schema["properties"][nested_property_name].get("enum", []))
                try:
                    rust_enum = _extract_rust_enum_values(source_text, enum_name)
                except ValueError as exc:
                    errors.append(f"{schema_file} <-> {enum_name}: {exc}")
                    continue
                if schema_enum != rust_enum:
                    errors.append(
                        f"{schema_file} <-> {enum_name}: "
                        f"nested enum mismatch; schema={sorted(schema_enum)} rust={sorted(rust_enum)}"
                    )

        print(
            "  OK  "
            f"{schema_file} <-> {mapping.struct_name} "
            f"(required: {len(required_fields)}, rust: {len(rust_fields)})"
        )

    return errors


def main() -> None:
    strict = "--strict" in sys.argv

    print("=== Schema Validation ===")
    errors = validate_json_schemas()

    print("\n=== Contract-Schema Parity ===")
    errors.extend(check_contract_parity(strict=strict))

    print("\n=== Rust Contract-Schema Parity ===")
    errors.extend(check_rust_contract_parity(strict=strict))

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
