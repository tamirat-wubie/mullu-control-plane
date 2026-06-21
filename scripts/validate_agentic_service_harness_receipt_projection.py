#!/usr/bin/env python3
"""Validate Agentic Service Harness Receipt projection contract.

Purpose: prove the harness can project existing receipt references by AgentRun
id without admitting receipt-store append, inline receipt bodies, mutation
routes, connector calls, branch writes, pull-request creation, or terminal
closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_receipt_projection.schema.json,
examples/agentic_service_harness_receipt_projection.foundation.json,
scripts.validate_agentic_service_harness_evidence_bundle_projection, and
scripts.validate_schemas.
Invariants:
  - Source EvidenceBundle projection validates first.
  - Every projected receipt ref exists in the source EvidenceBundle projection.
  - Receipt bodies are never inlined; refs remain reference-only.
  - Append, mutation, external effects, secrets, and terminal closure fail closed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_evidence_bundle_projection import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_EVIDENCE_BUNDLE_EXAMPLES,
    validate_agentic_service_harness_evidence_bundle_projection,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_receipt_projection.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_receipt_projection.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_receipt_projection_validation.json"
EXPECTED_REPORT_ID = "agentic_service_harness_receipt_projection"
EXPECTED_SOURCE_EVIDENCE_BUNDLE_REF = "examples/agentic_service_harness_evidence_bundle_projection.foundation.json"
EXPECTED_FOUNDATION_PHASE = "foundation_receipt_projection_by_agent_run"
EXPECTED_PROJECTION_ID = "receipt-projection-foundation"
EXPECTED_RECEIPT_REFS = {
    "receipt_projection_schema": "schemas/agentic_service_harness_receipt_projection.schema.json",
    "receipt_projection_fixture": "examples/agentic_service_harness_receipt_projection.foundation.json",
    "evidence_bundle_projection_schema": "schemas/agentic_service_harness_evidence_bundle_projection.schema.json",
    "evidence_bundle_projection_fixture": EXPECTED_SOURCE_EVIDENCE_BUNDLE_REF,
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = frozenset(
    {
        "receipt_query_route_admitted",
        "receipt_store_append_enabled",
        "inline_receipt_body_allowed",
        "mutation_endpoints_admitted",
        "adapter_execution_enabled",
        "connector_call_enabled",
        "branch_write_enabled",
        "pull_request_creation_enabled",
        "secret_values_serialized",
        "receipt_query_route_enabled",
        "inline_receipt_body_enabled",
        "runtime_state_write_enabled",
        "mutation_endpoint_enabled",
        "append_enabled",
        "runtime_collection_enabled",
        "terminal_closure",
    }
)
REQUIRED_TRUE_FLAGS = frozenset(
    {
        "read_only",
        "contract_only",
        "source_binding_required",
        "redaction_policy_required",
        "required_for_closure",
        "report_is_not_terminal_closure",
        "terminal_closure_required",
    }
)
ALLOWED_SECRET_KEYS = {"secret_values_serialized"}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ReceiptProjectionValidation:
    """Schema and semantic validation report for Receipt projection."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    projection_count: int
    run_count: int
    evidence_bundle_source_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_receipt_projection(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_evidence_bundle_path: Path = DEFAULT_EVIDENCE_BUNDLE_EXAMPLES[0],
) -> ReceiptProjectionValidation:
    """Validate Receipt projection examples against schema and invariants."""
    errors: list[str] = []
    evidence_validation = validate_agentic_service_harness_evidence_bundle_projection()
    if not evidence_validation.ok:
        errors.extend(f"source EvidenceBundle projection invalid: {error}" for error in evidence_validation.errors)

    schema = _load_json_object(schema_path, "Receipt projection schema", errors)
    source_projection = _load_json_object(source_evidence_bundle_path, "source EvidenceBundle projection", errors)
    source_bundles = _source_bundles_by_run_id(source_projection)

    examples: list[dict[str, Any]] = []
    projection_count = 0
    observed_run_ids: set[str] = set()
    for example_path in example_paths:
        example = _load_json_object(example_path, f"Receipt projection example {_path_label(example_path)}", errors)
        if not example:
            continue
        examples.append(example)
        projections = _objects(example.get("receipt_projections"))
        projection_count += len(projections)
        observed_run_ids.update(str(item.get("run_id")) for item in projections if isinstance(item.get("run_id"), str))
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_projection_semantics(example, source_bundles, errors, _path_label(example_path))

    return ReceiptProjectionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        projection_count=projection_count,
        run_count=len(observed_run_ids),
        evidence_bundle_source_ok=evidence_validation.ok,
    )


def write_receipt_projection_validation(validation: ReceiptProjectionValidation, output_path: Path) -> Path:
    """Write one deterministic Receipt projection validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_mutated_projection(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default Receipt projection example", [])
    mutated = deepcopy(payload)
    for dotted_key, value in updates.items():
        cursor: dict[str, Any] = mutated
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            next_value = cursor.setdefault(part, {})
            if not isinstance(next_value, dict):
                raise ValueError(f"cannot descend into non-object field: {dotted_key}")
            cursor = next_value
        cursor[parts[-1]] = value
    return mutated


def _validate_projection_semantics(
    example: Mapping[str, Any],
    source_bundles: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    _check_value(example, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(example, ("source_evidence_bundle_projection_ref",), EXPECTED_SOURCE_EVIDENCE_BUNDLE_REF, errors, label)
    _validate_scope(example, source_bundles, errors, label)
    _validate_index(example, errors, label)
    _validate_receipt_projections(example, source_bundles, errors, label)
    _validate_receipt_refs(example, errors, label)
    _validate_validators(example, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_scope(
    example: Mapping[str, Any],
    source_bundles: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping_at(example, ("scope",))
    if scope.get("foundation_phase") != EXPECTED_FOUNDATION_PHASE:
        errors.append(f"{label}: scope.foundation_phase must be {EXPECTED_FOUNDATION_PHASE}")
    if scope.get("projection_id") != EXPECTED_PROJECTION_ID:
        errors.append(f"{label}: scope.projection_id must be {EXPECTED_PROJECTION_ID}")
    if source_bundles:
        project_ids = {str(bundle.get("project_id")) for bundle in source_bundles.values() if bundle.get("project_id")}
        if project_ids and scope.get("project_id") not in project_ids:
            errors.append(f"{label}: scope.project_id must match source projection project_id")


def _validate_index(example: Mapping[str, Any], errors: list[str], label: str) -> None:
    index = _mapping_at(example, ("projection_index",))
    projections = _objects(example.get("receipt_projections"))
    run_ids = {str(item.get("run_id")) for item in projections if item.get("run_id")}
    if index.get("index_key") != "run_id":
        errors.append(f"{label}: projection_index.index_key must be run_id")
    if index.get("lookup_mode") != "read_only_receipt_ref_projection":
        errors.append(f"{label}: projection_index.lookup_mode must be read_only_receipt_ref_projection")
    if index.get("projection_count") != len(projections):
        errors.append(f"{label}: projection_index.projection_count must equal receipt_projections length")
    if index.get("run_count") != len(run_ids):
        errors.append(f"{label}: projection_index.run_count must equal unique run id count")


def _validate_receipt_projections(
    example: Mapping[str, Any],
    source_bundles: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    projections = _objects(example.get("receipt_projections"))
    if not projections:
        errors.append(f"{label}: receipt_projections must not be empty")
        return
    for projection in projections:
        run_id = str(projection.get("run_id", ""))
        source_bundle = source_bundles.get(run_id)
        if source_bundle is None:
            errors.append(f"{label}: projection {run_id} does not match a source EvidenceBundle run")
            continue
        expected_id = f"receipt-projection-{run_id}"
        if projection.get("projection_id") != expected_id:
            errors.append(f"{label}: projection {run_id} projection_id must be {expected_id}")
        if projection.get("source_evidence_bundle_id") != source_bundle.get("source_evidence_bundle_id"):
            errors.append(f"{label}: projection {run_id} source_evidence_bundle_id must match source bundle")
        if projection.get("source_bundle_ref") != source_bundle.get("run_lookup_ref"):
            errors.append(f"{label}: projection {run_id} source_bundle_ref must match source run_lookup_ref")
        receipt_refs = projection.get("receipt_refs")
        if not isinstance(receipt_refs, list) or not receipt_refs:
            errors.append(f"{label}: projection {run_id} receipt_refs must not be empty")
            continue
        source_receipts = set(str(ref) for ref in _mapping_at(source_bundle, ("categories",)).get("receipt_refs", ()))
        missing = sorted(set(str(ref) for ref in receipt_refs) - source_receipts)
        if missing:
            errors.append(f"{label}: projection {run_id} receipt_refs not present in source bundle: {missing}")
        if projection.get("receipt_count") != len(receipt_refs):
            errors.append(f"{label}: projection {run_id} receipt_count must equal receipt_refs length")
        if projection.get("redaction_policy") != "reference_only_no_inline_body":
            errors.append(f"{label}: projection {run_id} redaction_policy must be reference_only_no_inline_body")
        policy_refs = projection.get("policy_refs")
        if not isinstance(policy_refs, list) or "gate://harness/no-receipt-store-append" not in policy_refs:
            errors.append(f"{label}: projection {run_id} policy_refs must include no-receipt-store-append")
        if not isinstance(policy_refs, list) or "gate://harness/terminal-closure-denied" not in policy_refs:
            errors.append(f"{label}: projection {run_id} policy_refs must include terminal-closure-denied")


def _validate_receipt_refs(example: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping_at(example, ("receipt_refs",))
    for key, expected in EXPECTED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected:
            errors.append(f"{label}: receipt_refs.{key} must be {expected}")


def _validate_validators(example: Mapping[str, Any], errors: list[str], label: str) -> None:
    commands = {str(item.get("command")) for item in _objects(example.get("validators"))}
    expected_command = "python scripts/validate_agentic_service_harness_receipt_projection.py --strict"
    if expected_command not in commands:
        errors.append(f"{label}: validators must include {expected_command}")


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if key_lower in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {path} must be false")
        if key_lower in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {path} must be true")


def _validate_secret_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS) and key_lower not in ALLOWED_SECRET_KEYS:
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _source_bundles_by_run_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    project_id = _mapping_at(payload, ("scope",)).get("project_id")
    bundles: dict[str, Mapping[str, Any]] = {}
    for bundle in _objects(payload.get("bundles")):
        run_id = bundle.get("run_id")
        if isinstance(run_id, str):
            enriched = dict(bundle)
            enriched["project_id"] = project_id
            bundles[run_id] = enriched
    return bundles


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def _mapping_at(payload: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any]:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, (list, tuple)):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _check_value(payload: Mapping[str, Any], path: tuple[str, ...], expected: Any, errors: list[str], label: str) -> None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            errors.append(f"{label}: {'.'.join(path)} is required")
            return
        current = current[key]
    if current != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            child_path = f"{path}[{index}]"
            yield child_path, str(index), item
            yield from _walk_json(item, child_path)


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield path, payload


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Receipt projection validation arguments."""
    parser = argparse.ArgumentParser(description="Validate the harness Receipt projection contract.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--source-evidence-bundle", default=str(DEFAULT_EVIDENCE_BUNDLE_EXAMPLES[0]))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Receipt projection validation."""
    args = parse_args(argv)
    example_paths = tuple(Path(example) for example in args.example) if args.example else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_receipt_projection(
        schema_path=Path(args.schema),
        example_paths=example_paths,
        source_evidence_bundle_path=Path(args.source_evidence_bundle),
    )
    write_receipt_projection_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS RECEIPT PROJECTION VALID")
    else:
        print(f"AGENTIC SERVICE HARNESS RECEIPT PROJECTION INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
