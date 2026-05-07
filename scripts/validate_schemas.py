#!/usr/bin/env python3
"""Schema validation and shared-contract parity checker.

Validates:
  1. All JSON schemas in schemas/ are valid JSON and well-formed.
  2. Every schema that has a matching Python contract module produces
     contract instances whose to_dict() output is structurally compatible
     with the schema's required fields.
  3. Every shared schema that has a matching Rust contract surface maps to
     the same field names and enum values without reinterpretation.
  4. Canonical payload fixtures match schema-backed contracts and round-trip
     exactly through the Python contract surface.
  5. In --strict mode, checks that all schema properties are present in the
     Python and Rust contract surfaces, canonical Rust structs do not carry
     extra top-level or nested fields, and canonical fixtures cover the full
     declared payload surface for every fixture-backed contract.

Usage:
  python scripts/validate_schemas.py           # basic validation
  python scripts/validate_schemas.py --strict   # strict parity check
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures"

# Map schema files to their Python contract classes
SCHEMA_CONTRACT_MAP: dict[str, tuple[str, str]] = {
    "communication_message.schema.json": (
        "mcoi_runtime.contracts.communication",
        "CommunicationMessage",
    ),
    "connector_descriptor.schema.json": (
        "mcoi_runtime.contracts.connector",
        "ConnectorDescriptor",
    ),
    "connector_result.schema.json": (
        "mcoi_runtime.contracts.connector",
        "ConnectorResult",
    ),
    "delivery_result.schema.json": (
        "mcoi_runtime.contracts.communication",
        "DeliveryResult",
    ),
    "capability_descriptor.schema.json": (
        "mcoi_runtime.contracts.capability",
        "CapabilityDescriptor",
    ),
    "execution_result.schema.json": (
        "mcoi_runtime.contracts.execution",
        "ExecutionResult",
    ),
    "model_invocation.schema.json": (
        "mcoi_runtime.contracts.model",
        "ModelInvocation",
    ),
    "model_response.schema.json": (
        "mcoi_runtime.contracts.model",
        "ModelResponse",
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
    "workflow.schema.json": (
        "mcoi_runtime.contracts.workflow",
        "WorkflowDescriptor",
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
    "workflow.schema.json": RustContractMapping(
        source=REPO_ROOT / "maf" / "rust" / "crates" / "maf-orchestration" / "src" / "lib.rs",
        struct_name="WorkflowDescriptor",
        nested_fields={
            "stages": NestedRustMapping(
                struct_name="WorkflowStage",
                enum_fields={"stage_type": "StageType"},
            ),
            "bindings": NestedRustMapping(struct_name="WorkflowBinding"),
        },
    ),
}


SharedFixtureBuilder = Callable[[dict[str, Any]], Any]


FIXTURE_SCHEMA_FILES: tuple[str, ...] = tuple(SCHEMA_CONTRACT_MAP.keys())
CANONICAL_SHARED_SCHEMA_FILES: tuple[str, ...] = tuple(RUST_SCHEMA_CONTRACT_MAP.keys())


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
        except json.JSONDecodeError:
            errors.append(f"{schema_path.name}: invalid JSON")
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


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
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


def _validate_datetime_text(value: str, path: str) -> list[str]:
    if not isinstance(value, str):
        return [f"{path}: expected string date-time"]
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return [f"{path}: invalid ISO 8601 date-time string"]
    return []


def _validate_schema_instance(
    schema: dict[str, Any],
    instance: Any,
    path: str = "$",
    root_schema: dict[str, Any] | None = None,
) -> list[str]:
    if not isinstance(schema, dict) or not schema:
        return []
    root = schema if root_schema is None else root_schema

    if "allOf" in schema:
        errors: list[str] = []
        base_schema = {
            keyword: value for keyword, value in schema.items() if keyword != "allOf"
        }
        errors.extend(_validate_schema_instance(base_schema, instance, path, root))
        for branch in schema["allOf"]:
            errors.extend(_validate_schema_instance(branch, instance, path, root))
        return errors

    if "if" in schema:
        condition_errors = _validate_schema_instance(schema["if"], instance, path, root)
        if not condition_errors and "then" in schema:
            return _validate_schema_instance(schema["then"], instance, path, root)
        if condition_errors and "else" in schema:
            return _validate_schema_instance(schema["else"], instance, path, root)
        return []

    if "anyOf" in schema:
        branch_errors = [
            _validate_schema_instance(branch, instance, path, root)
            for branch in schema["anyOf"]
        ]
        if any(not errors for errors in branch_errors):
            return []
        flattened = [error for branch in branch_errors for error in branch]
        return [f"{path}: no anyOf branch matched"] + flattened

    if "$ref" in schema:
        try:
            referenced_schema = _resolve_local_schema_ref(root, str(schema["$ref"]))
        except ValueError:
            return [f"{path}: unresolved schema ref"]
        return _validate_schema_instance(referenced_schema, instance, path, root)

    errors: list[str] = []
    if "not" in schema:
        branch_errors = _validate_schema_instance(schema["not"], instance, path, root)
        if not branch_errors:
            errors.append(f"{path}: matched forbidden schema")

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        branch_errors = []
        for item_type in schema_type:
            branch_schema = dict(schema)
            branch_schema["type"] = item_type
            branch_errors.append(_validate_schema_instance(branch_schema, instance, path, root))
        if any(not item_errors for item_errors in branch_errors):
            return []
        flattened = [error for item_errors in branch_errors for error in item_errors]
        return [f"{path}: no type branch matched {schema_type}"] + flattened

    if schema_type is None and "contains" in schema:
        errors.extend(_validate_array_contains(schema, instance, path, root))
        return errors

    if schema_type == "object" or (
        schema_type is None
        and (
            "properties" in schema
            or "required" in schema
            or "additionalProperties" in schema
        )
    ):
        if not isinstance(instance, dict):
            if schema_type == "object":
                errors.append(f"{path}: expected object")
            return errors
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = required - set(instance.keys())
        if missing:
            errors.append(f"{path}: missing required fields {sorted(missing)}")

        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors.extend(_validate_schema_instance(properties[key], value, f"{path}.{key}", root))
            elif schema_type == "object" and additional is False:
                errors.append(f"{path}: unexpected property '{key}'")
            elif schema_type == "object" and isinstance(additional, dict):
                errors.extend(_validate_schema_instance(additional, value, f"{path}.{key}", root))
        return errors

    if schema_type == "array":
        if not isinstance(instance, list):
            errors.append(f"{path}: expected array")
            return errors
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} item(s)")
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(instance) > max_items:
            errors.append(f"{path}: expected at most {max_items} item(s)")
        item_schema = schema.get("items", {})
        if isinstance(item_schema, list):
            for index, item in enumerate(instance[: len(item_schema)]):
                errors.extend(
                    _validate_schema_instance(item_schema[index], item, f"{path}[{index}]", root)
                )
        else:
            for index, item in enumerate(instance):
                errors.extend(_validate_schema_instance(item_schema, item, f"{path}[{index}]", root))
        errors.extend(_validate_array_contains(schema, instance, path, root))
        return errors

    if schema_type == "string":
        if not isinstance(instance, str):
            errors.append(f"{path}: expected string")
            return errors
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(f"{path}: expected minimum length {min_length}")
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path}: expected one of {sorted(schema['enum'])}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{path}: string does not match pattern {pattern!r}")
        if schema.get("format") == "date-time":
            errors.extend(_validate_datetime_text(instance, path))
        return errors

    if schema_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            errors.append(f"{path}: expected integer")
            return errors
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: expected integer >= {minimum}")
        maximum = schema.get("maximum")
        if maximum is not None and instance > maximum:
            errors.append(f"{path}: expected integer <= {maximum}")
        return errors

    if schema_type == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            errors.append(f"{path}: expected number")
            return errors
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: expected number >= {minimum}")
        maximum = schema.get("maximum")
        if maximum is not None and instance > maximum:
            errors.append(f"{path}: expected number <= {maximum}")
        return errors

    if schema_type == "boolean":
        if not isinstance(instance, bool):
            errors.append(f"{path}: expected boolean")
        return errors

    if schema_type == "null":
        if instance is not None:
            errors.append(f"{path}: expected null")
        return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: expected one of {sorted(schema['enum'])}")
    return errors


def _validate_array_contains(
    schema: dict[str, Any],
    instance: Any,
    path: str,
    root_schema: dict[str, Any] | None = None,
) -> list[str]:
    contains_schema = schema.get("contains")
    if contains_schema is None:
        return []
    if not isinstance(instance, list):
        return [f"{path}: expected array for contains"]
    for index, item in enumerate(instance):
        if not _validate_schema_instance(
            contains_schema,
            item,
            f"{path}[{index}]",
            root_schema or schema,
        ):
            return []
    return [f"{path}: no item matched contains schema"]


def _resolve_local_schema_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError("only local JSON Pointer refs are supported")
    current: Any = root_schema
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"missing pointer segment {part!r}")
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError("referenced value is not a schema object")
    return current


def _check_fixture_schema_coverage(schema: dict[str, Any], instance: Any, path: str = "$") -> list[str]:
    if not schema or "anyOf" in schema or "$ref" in schema:
        return []

    errors: list[str] = []
    schema_type = schema.get("type")

    if schema_type == "object" and isinstance(instance, dict):
        properties = schema.get("properties", {})
        missing = set(properties) - set(instance)
        if missing:
            errors.append(f"{path}: canonical fixture missing schema properties {sorted(missing)}")
        for key, property_schema in properties.items():
            if key in instance:
                errors.extend(_check_fixture_schema_coverage(property_schema, instance[key], f"{path}.{key}"))
        return errors

    if schema_type == "array" and isinstance(instance, list):
        item_schema = schema.get("items", {})
        for index, item in enumerate(instance):
            errors.extend(_check_fixture_schema_coverage(item_schema, item, f"{path}[{index}]"))
        return errors

    return errors


def _canonical_fixture_path(schema_file: str) -> Path:
    return FIXTURE_DIR / schema_file.replace(".schema.json", ".json")


def _load_canonical_fixtures() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    for schema_file in FIXTURE_SCHEMA_FILES:
        fixtures[schema_file] = _load_json(_canonical_fixture_path(schema_file))
    return fixtures


def _build_communication_message(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.communication import CommunicationChannel, CommunicationMessage

    return CommunicationMessage(
        message_id=payload["message_id"],
        sender_id=payload["sender_id"],
        recipient_id=payload["recipient_id"],
        channel=CommunicationChannel(payload["channel"]),
        message_type=payload["message_type"],
        payload=payload["payload"],
        correlation_id=payload["correlation_id"],
        created_at=payload["created_at"],
        metadata=payload["metadata"],
    )


def _build_delivery_result(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.communication import CommunicationChannel, DeliveryResult, DeliveryStatus

    return DeliveryResult(
        delivery_id=payload["delivery_id"],
        message_id=payload["message_id"],
        status=DeliveryStatus(payload["status"]),
        channel=CommunicationChannel(payload["channel"]),
        delivered_at=payload.get("delivered_at"),
        error_code=payload.get("error_code"),
        metadata=payload["metadata"],
    )


def _build_connector_descriptor(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.connector import ConnectorDescriptor
    from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass

    return ConnectorDescriptor(
        connector_id=payload["connector_id"],
        name=payload["name"],
        provider=payload["provider"],
        effect_class=EffectClass(payload["effect_class"]),
        trust_class=TrustClass(payload["trust_class"]),
        credential_scope_id=payload["credential_scope_id"],
        enabled=payload["enabled"],
        metadata=payload["metadata"],
    )


def _build_connector_result(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.connector import ConnectorResult, ConnectorStatus

    return ConnectorResult(
        result_id=payload["result_id"],
        connector_id=payload["connector_id"],
        status=ConnectorStatus(payload["status"]),
        response_digest=payload["response_digest"],
        started_at=payload["started_at"],
        finished_at=payload["finished_at"],
        error_code=payload["error_code"],
        metadata=payload["metadata"],
    )


def _build_capability_descriptor(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.capability import CapabilityDescriptor

    return CapabilityDescriptor(
        capability_id=payload["capability_id"],
        subject_id=payload["subject_id"],
        name=payload["name"],
        version=payload["version"],
        scope=payload["scope"],
        constraints=tuple(payload["constraints"]),
        risk_tier=payload.get("risk_tier", ""),
        declared_effects=tuple(payload.get("declared_effects", ())),
        forbidden_effects=tuple(payload.get("forbidden_effects", ())),
        evidence_required=tuple(payload.get("evidence_required", ())),
        rollback=payload.get("rollback", {}),
        graph_projection=payload.get("graph_projection", {}),
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_policy_decision(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus

    return PolicyDecision(
        decision_id=payload["decision_id"],
        subject_id=payload["subject_id"],
        goal_id=payload["goal_id"],
        status=PolicyDecisionStatus(payload["status"]),
        reasons=tuple(
            DecisionReason(
                message=reason["message"],
                code=reason.get("code"),
                details=reason.get("details"),
            )
            for reason in payload["reasons"]
        ),
        issued_at=payload["issued_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_execution_result(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult

    return ExecutionResult(
        execution_id=payload["execution_id"],
        goal_id=payload["goal_id"],
        status=ExecutionOutcome(payload["status"]),
        actual_effects=tuple(
            EffectRecord(name=effect["name"], details=effect.get("details"))
            for effect in payload["actual_effects"]
        ),
        assumed_effects=tuple(
            EffectRecord(name=effect["name"], details=effect.get("details"))
            for effect in payload["assumed_effects"]
        ),
        started_at=payload["started_at"],
        finished_at=payload["finished_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_model_invocation(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.model import ModelInvocation

    return ModelInvocation(
        invocation_id=payload["invocation_id"],
        model_id=payload["model_id"],
        prompt_hash=payload["prompt_hash"],
        invoked_at=payload["invoked_at"],
        input_tokens=payload.get("input_tokens"),
        cost_estimate=payload.get("cost_estimate"),
        metadata=payload["metadata"],
    )


def _build_model_response(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.model import ModelResponse, ModelStatus, ValidationStatus

    return ModelResponse(
        response_id=payload["response_id"],
        invocation_id=payload["invocation_id"],
        status=ModelStatus(payload["status"]),
        output_digest=payload["output_digest"],
        completed_at=payload["completed_at"],
        validation_status=ValidationStatus(payload["validation_status"]),
        output_tokens=payload.get("output_tokens"),
        actual_cost=payload.get("actual_cost"),
        metadata=payload["metadata"],
    )


def _build_workflow(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.workflow import (
        StageType,
        WorkflowBinding,
        WorkflowDescriptor,
        WorkflowStage,
    )

    return WorkflowDescriptor(
        workflow_id=payload["workflow_id"],
        name=payload["name"],
        description=payload["description"],
        stages=tuple(
            WorkflowStage(
                stage_id=stage["stage_id"],
                stage_type=StageType(stage["stage_type"]),
                skill_id=stage.get("skill_id"),
                description=stage.get("description", ""),
                predecessors=tuple(stage.get("predecessors", [])),
                timeout_seconds=stage.get("timeout_seconds"),
            )
            for stage in payload["stages"]
        ),
        bindings=tuple(
            WorkflowBinding(
                binding_id=binding["binding_id"],
                source_stage_id=binding["source_stage_id"],
                source_output_key=binding["source_output_key"],
                target_stage_id=binding["target_stage_id"],
                target_input_key=binding["target_input_key"],
            )
            for binding in payload["bindings"]
        ),
        created_at=payload["created_at"],
    )


def _build_environment_fingerprint(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.environment import (
        EnvironmentFingerprint,
        PlatformDescriptor,
        RuntimeDescriptor,
    )

    return EnvironmentFingerprint(
        fingerprint_id=payload["fingerprint_id"],
        captured_at=payload["captured_at"],
        digest=payload["digest"],
        platform=PlatformDescriptor(**payload["platform"]),
        runtime=RuntimeDescriptor(**payload["runtime"]),
        tooling=payload["tooling"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_trace_entry(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.trace import TraceEntry

    return TraceEntry(
        trace_id=payload["trace_id"],
        parent_trace_id=payload["parent_trace_id"],
        event_type=payload["event_type"],
        subject_id=payload["subject_id"],
        goal_id=payload["goal_id"],
        state_hash=payload["state_hash"],
        registry_hash=payload["registry_hash"],
        timestamp=payload["timestamp"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_replay_record(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.replay import ReplayEffect, ReplayMode, ReplayRecord

    return ReplayRecord(
        replay_id=payload["replay_id"],
        trace_id=payload["trace_id"],
        source_hash=payload["source_hash"],
        approved_effects=tuple(
            ReplayEffect(
                effect_id=effect["effect_id"],
                description=effect.get("description"),
                details=effect.get("details"),
            )
            for effect in payload["approved_effects"]
        ),
        blocked_effects=tuple(
            ReplayEffect(
                effect_id=effect["effect_id"],
                description=effect.get("description"),
                details=effect.get("details"),
            )
            for effect in payload["blocked_effects"]
        ),
        mode=ReplayMode(payload["mode"]),
        recorded_at=payload["recorded_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_verification_result(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.evidence import EvidenceRecord
    from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus

    return VerificationResult(
        verification_id=payload["verification_id"],
        execution_id=payload["execution_id"],
        status=VerificationStatus(payload["status"]),
        checks=tuple(
            VerificationCheck(
                name=check["name"],
                status=VerificationStatus(check["status"]),
                details=check.get("details"),
            )
            for check in payload["checks"]
        ),
        evidence=tuple(
            EvidenceRecord(
                description=evidence["description"],
                uri=evidence.get("uri"),
                details=evidence.get("details"),
            )
            for evidence in payload["evidence"]
        ),
        closed_at=payload["closed_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_learning_admission(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
    from mcoi_runtime.contracts.policy import DecisionReason

    return LearningAdmissionDecision(
        admission_id=payload["admission_id"],
        knowledge_id=payload["knowledge_id"],
        status=LearningAdmissionStatus(payload["status"]),
        reasons=tuple(
            DecisionReason(
                message=reason["message"],
                code=reason.get("code"),
                details=reason.get("details"),
            )
            for reason in payload["reasons"]
        ),
        issued_at=payload["issued_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


def _build_plan(payload: dict[str, Any]) -> Any:
    from mcoi_runtime.contracts.plan import Plan, PlanItem

    return Plan(
        plan_id=payload["plan_id"],
        goal_id=payload["goal_id"],
        state_hash=payload["state_hash"],
        registry_hash=payload["registry_hash"],
        items=tuple(
            PlanItem(
                item_id=item["item_id"],
                description=item["description"],
                order=item.get("order"),
                depends_on=tuple(item.get("depends_on", [])),
            )
            for item in payload["items"]
        ),
        status=payload["status"],
        objective=payload["objective"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        metadata=payload["metadata"],
        extensions=payload["extensions"],
    )


FIXTURE_BUILDERS: dict[str, SharedFixtureBuilder] = {
    "communication_message.schema.json": _build_communication_message,
    "connector_descriptor.schema.json": _build_connector_descriptor,
    "connector_result.schema.json": _build_connector_result,
    "delivery_result.schema.json": _build_delivery_result,
    "capability_descriptor.schema.json": _build_capability_descriptor,
    "environment_fingerprint.schema.json": _build_environment_fingerprint,
    "policy_decision.schema.json": _build_policy_decision,
    "execution_result.schema.json": _build_execution_result,
    "model_invocation.schema.json": _build_model_invocation,
    "model_response.schema.json": _build_model_response,
    "plan.schema.json": _build_plan,
    "trace_entry.schema.json": _build_trace_entry,
    "replay_record.schema.json": _build_replay_record,
    "verification_result.schema.json": _build_verification_result,
    "workflow.schema.json": _build_workflow,
    "learning_admission.schema.json": _build_learning_admission,
}


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
        except ValueError:
            errors.append(f"{schema_file} <-> {mapping.struct_name}: Rust struct extraction failed")
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
            except ValueError:
                errors.append(f"{schema_file} <-> {enum_name}: Rust enum extraction failed")
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
            except ValueError:
                errors.append(f"{schema_file} <-> {nested_mapping.struct_name}: Rust struct extraction failed")
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
                except ValueError:
                    errors.append(f"{schema_file} <-> {enum_name}: Rust enum extraction failed")
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


def validate_canonical_fixtures(strict: bool = False) -> list[str]:
    """Validate canonical shared-contract fixtures against their schemas."""
    errors: list[str] = []

    if not FIXTURE_DIR.exists():
        return [f"Canonical fixture directory not found: {FIXTURE_DIR}"]

    expected_files = {
        schema_file.replace(".schema.json", ".json")
        for schema_file in FIXTURE_SCHEMA_FILES
    }
    actual_files = {path.name for path in FIXTURE_DIR.glob("*.json")}

    missing_files = expected_files - actual_files
    if missing_files:
        errors.append(f"canonical fixtures missing files: {sorted(missing_files)}")

    if strict:
        extra_files = actual_files - expected_files
        if extra_files:
            errors.append(f"canonical fixtures contain unexpected files: {sorted(extra_files)}")

    for schema_file in FIXTURE_SCHEMA_FILES:
        schema = _load_schema(SCHEMA_DIR / schema_file)
        fixture_path = _canonical_fixture_path(schema_file)
        if not fixture_path.exists():
            continue
        fixture = _load_json(fixture_path)
        errors.extend(
            f"{schema_file} fixture {message}"
            for message in _validate_schema_instance(schema, fixture)
        )
        if strict:
            errors.extend(
                f"{schema_file} fixture {message}"
                for message in _check_fixture_schema_coverage(schema, fixture)
            )
        print(f"  OK  {schema_file} fixture <-> {fixture_path.name}")

    return errors


def check_python_fixture_round_trip() -> list[str]:
    """Check that canonical shared fixtures round-trip exactly through Python contracts."""
    errors: list[str] = []

    mcoi_path = REPO_ROOT / "mcoi"
    if str(mcoi_path) not in sys.path:
        sys.path.insert(0, str(mcoi_path))

    fixtures = _load_canonical_fixtures()
    for schema_file, fixture in fixtures.items():
        contract = FIXTURE_BUILDERS[schema_file](fixture)
        rendered = contract.to_json_dict()
        if rendered != fixture:
            errors.append(
                f"{schema_file}: Python contract JSON surface diverges from canonical fixture"
            )
        canonical_text = json.dumps(fixture, ensure_ascii=True, separators=(",", ":"))
        rendered_text = contract.to_json()
        if rendered_text != canonical_text:
            errors.append(
                f"{schema_file}: Python contract serialization order diverges from canonical fixture"
            )
        print(f"  OK  {schema_file} fixture <-> Python contract round-trip")

    return errors


def main() -> None:
    strict = "--strict" in sys.argv

    print("=== Schema Validation ===")
    errors = validate_json_schemas()

    print("\n=== Contract-Schema Parity ===")
    errors.extend(check_contract_parity(strict=strict))

    print("\n=== Rust Contract-Schema Parity ===")
    errors.extend(check_rust_contract_parity(strict=strict))

    print("\n=== Canonical Shared Fixtures ===")
    errors.extend(validate_canonical_fixtures(strict=strict))

    print("\n=== Python Fixture Round-Trip ===")
    errors.extend(check_python_fixture_round_trip())

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
