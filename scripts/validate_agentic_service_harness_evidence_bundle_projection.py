#!/usr/bin/env python3
"""Validate Agentic Service Harness EvidenceBundle projection contract.

Purpose: prove the harness EvidenceBundle read model groups command logs, test
logs, diff refs, policy refs, receipt refs, and source read-model refs by
AgentRun id without admitting log ingestion, receipt append, adapter execution,
connector calls, branch writes, pull-request creation, secret serialization,
mutation routes, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_evidence_bundle_projection.schema.json,
examples/agentic_service_harness_evidence_bundle_projection.foundation.json,
scripts.validate_agentic_service_harness_read_models,
scripts.validate_agentic_service_harness_adapter_registry_contract, and
scripts.validate_schemas.
Invariants:
  - Source read models and adapter registry validate first.
  - Every bundle is indexed by a source AgentRun id.
  - Evidence categories are reference-only, redacted, non-empty, and source-bound.
  - Log ingestion, receipt append, runtime collection, external effects, secrets,
    mutation routes, and terminal closure fail closed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_adapter_registry_contract import (  # noqa: E402
    validate_agentic_service_harness_adapter_registry_contract,
)
from scripts.validate_agentic_service_harness_read_models import (  # noqa: E402
    validate_agentic_service_harness_read_models,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_evidence_bundle_projection.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_evidence_bundle_projection.foundation.json",
)
DEFAULT_SOURCE_READ_MODELS = REPO_ROOT / "examples" / "agentic_service_harness_read_models.foundation.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_evidence_bundle_projection_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_evidence_bundle_projection"
EXPECTED_SOURCE_READ_MODELS_REF = "examples/agentic_service_harness_read_models.foundation.json"
EXPECTED_SOURCE_ADAPTER_REGISTRY_REF = (
    "examples/agentic_service_harness_adapter_registry_contract.foundation.json"
)
EXPECTED_FOUNDATION_PHASE = "foundation_evidence_bundle_projection_by_agent_run"
EXPECTED_PROJECTION_ID = "evidence-bundle-projection-foundation"
EXPECTED_CATEGORY_IDS = frozenset(
    {
        "command_logs",
        "test_logs",
        "diff_refs",
        "policy_refs",
        "receipt_refs",
        "source_read_models",
    }
)
EXPECTED_RECEIPT_REFS = {
    "evidence_bundle_projection_schema": (
        "schemas/agentic_service_harness_evidence_bundle_projection.schema.json"
    ),
    "evidence_bundle_projection_fixture": (
        "examples/agentic_service_harness_evidence_bundle_projection.foundation.json"
    ),
    "read_models_schema": "schemas/agentic_service_harness_read_models.schema.json",
    "read_models_fixture": "examples/agentic_service_harness_read_models.foundation.json",
    "adapter_registry_contract_schema": (
        "schemas/agentic_service_harness_adapter_registry_contract.schema.json"
    ),
    "adapter_registry_contract_fixture": (
        "examples/agentic_service_harness_adapter_registry_contract.foundation.json"
    ),
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = frozenset(
    {
        "query_route_admitted",
        "mutation_endpoints_admitted",
        "log_ingestion_enabled",
        "receipt_store_append_enabled",
        "adapter_execution_enabled",
        "connector_call_enabled",
        "branch_write_enabled",
        "pull_request_creation_enabled",
        "secret_values_serialized",
        "inline_diff_allowed",
        "query_route_enabled",
        "mutation_endpoint_enabled",
        "runtime_state_write_enabled",
        "deployment_enabled",
        "dns_mutation_enabled",
        "secret_mutation_enabled",
        "destructive_operation_enabled",
        "terminal_closure",
        "contains_secret_values",
        "inline_log_allowed",
        "append_enabled",
        "runtime_collection_enabled",
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
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "secret_values_serialized",
    "contains_secret_values",
}
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
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class EvidenceBundleProjectionValidation:
    """Schema and semantic validation report for EvidenceBundle projection."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    bundle_count: int
    run_count: int
    read_models_source_ok: bool
    adapter_registry_source_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_evidence_bundle_projection(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_read_models_path: Path = DEFAULT_SOURCE_READ_MODELS,
) -> EvidenceBundleProjectionValidation:
    """Validate EvidenceBundle projection examples against schema and invariants."""
    errors: list[str] = []
    read_models_validation = validate_agentic_service_harness_read_models()
    adapter_registry_validation = validate_agentic_service_harness_adapter_registry_contract()
    if not read_models_validation.ok:
        errors.extend(
            f"source read models invalid: {error}"
            for error in read_models_validation.errors
        )
    if not adapter_registry_validation.ok:
        errors.extend(
            f"source adapter registry invalid: {error}"
            for error in adapter_registry_validation.errors
        )

    schema = _load_json_object(schema_path, "EvidenceBundle projection schema", errors)
    source_read_models = _load_json_object(
        source_read_models_path,
        "source read models fixture",
        errors,
    )
    source_runs = _source_runs_by_id(source_read_models)
    source_receipts = _source_receipts_by_run_id(source_read_models)

    examples: list[dict[str, Any]] = []
    observed_run_ids: set[str] = set()
    bundle_count = 0
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"EvidenceBundle projection example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        bundles = _objects(example.get("bundles"))
        bundle_count += len(bundles)
        observed_run_ids.update(
            str(bundle.get("run_id"))
            for bundle in bundles
            if isinstance(bundle.get("run_id"), str)
        )
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_projection_semantics(
            example,
            source_runs,
            source_receipts,
            errors,
            _path_label(example_path),
        )

    return EvidenceBundleProjectionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        bundle_count=bundle_count,
        run_count=len(observed_run_ids),
        read_models_source_ok=read_models_validation.ok,
        adapter_registry_source_ok=adapter_registry_validation.ok,
    )


def write_evidence_bundle_projection_validation(
    validation: EvidenceBundleProjectionValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic EvidenceBundle projection validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_projection_semantics(
    example: Mapping[str, Any],
    source_runs: Mapping[str, Mapping[str, Any]],
    source_receipts: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    _check_value(example, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(
        example,
        ("source_read_models_ref",),
        EXPECTED_SOURCE_READ_MODELS_REF,
        errors,
        label,
    )
    _check_value(
        example,
        ("source_adapter_registry_ref",),
        EXPECTED_SOURCE_ADAPTER_REGISTRY_REF,
        errors,
        label,
    )
    _validate_scope(example, source_runs, errors, label)
    _validate_projection_index(example, errors, label)
    _validate_bundles(example, source_runs, source_receipts, errors, label)
    _validate_receipt_refs(example, errors, label)
    _validate_validators(example, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_scope(
    example: Mapping[str, Any],
    source_runs: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping_at(example, ("scope",))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("foundation_phase") != EXPECTED_FOUNDATION_PHASE:
        errors.append(f"{label}: scope.foundation_phase must be {EXPECTED_FOUNDATION_PHASE}")
    if scope.get("projection_id") != EXPECTED_PROJECTION_ID:
        errors.append(f"{label}: scope.projection_id must be {EXPECTED_PROJECTION_ID}")
    if source_runs:
        project_ids = {str(run.get("project_id")) for run in source_runs.values()}
        if scope.get("project_id") not in project_ids:
            errors.append(f"{label}: scope.project_id must match a source run project_id")


def _validate_projection_index(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    index = _mapping_at(example, ("projection_index",))
    bundles = _objects(example.get("bundles"))
    run_ids = {str(bundle.get("run_id")) for bundle in bundles if bundle.get("run_id")}
    if not index:
        errors.append(f"{label}: projection_index must be an object")
        return
    if index.get("index_key") != "run_id":
        errors.append(f"{label}: projection_index.index_key must be run_id")
    if index.get("lookup_mode") != "read_only_reference_projection":
        errors.append(f"{label}: projection_index.lookup_mode must be read_only_reference_projection")
    if index.get("bundle_count") != len(bundles):
        errors.append(f"{label}: projection_index.bundle_count must equal bundles length")
    if index.get("run_count") != len(run_ids):
        errors.append(f"{label}: projection_index.run_count must equal unique run id count")
    category_ids = set(str(item) for item in index.get("required_category_ids", ()))
    if category_ids != EXPECTED_CATEGORY_IDS:
        errors.append(f"{label}: projection_index.required_category_ids must equal {sorted(EXPECTED_CATEGORY_IDS)}")


def _validate_bundles(
    example: Mapping[str, Any],
    source_runs: Mapping[str, Mapping[str, Any]],
    source_receipts: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    bundles = _objects(example.get("bundles"))
    if not bundles:
        errors.append(f"{label}: bundles must not be empty")
        return
    for bundle in bundles:
        run_id = str(bundle.get("run_id", ""))
        source_run = source_runs.get(run_id)
        source_receipt = source_receipts.get(run_id)
        if source_run is None:
            errors.append(f"{label}: bundle {run_id} does not match a source AgentRun")
            continue
        expected_bundle_id = f"bundle-{run_id}"
        expected_lookup_ref = f"agent-run://{run_id}/evidence-bundle"
        if bundle.get("bundle_id") != expected_bundle_id:
            errors.append(f"{label}: bundle {run_id} bundle_id must be {expected_bundle_id}")
        if bundle.get("run_lookup_ref") != expected_lookup_ref:
            errors.append(f"{label}: bundle {run_id} run_lookup_ref must be {expected_lookup_ref}")
        if bundle.get("source_evidence_bundle_id") != source_run.get("evidence_bundle_id"):
            errors.append(f"{label}: bundle {run_id} source_evidence_bundle_id must match source run")
        if bundle.get("redaction_policy") != "hash_or_reference_only":
            errors.append(f"{label}: bundle {run_id} redaction_policy must be hash_or_reference_only")
        categories = _mapping_at(bundle, ("categories",))
        if not categories:
            errors.append(f"{label}: bundle {run_id} categories must be an object")
            continue
        _validate_category_names(categories, errors, label, run_id)
        if source_receipt:
            _require_category_refs(
                categories,
                "command_logs",
                source_receipt.get("commands_run_refs"),
                errors,
                label,
                run_id,
            )
            _require_category_refs(
                categories,
                "test_logs",
                source_receipt.get("tests_run_refs"),
                errors,
                label,
                run_id,
            )
            _require_category_refs(
                categories,
                "diff_refs",
                _mapping_at(source_receipt, ("files_changed",)).get("diff_refs"),
                errors,
                label,
                run_id,
            )
            _require_category_refs(
                categories,
                "receipt_refs",
                source_run.get("transition_receipt_refs"),
                errors,
                label,
                run_id,
            )
            _require_category_refs(
                categories,
                "source_read_models",
                (
                    EXPECTED_SOURCE_READ_MODELS_REF,
                    str(source_run.get("read_only_query_ref")),
                    *tuple(str(ref) for ref in source_receipt.get("evidence_refs", ())),
                ),
                errors,
                label,
                run_id,
            )
        policy_refs = categories.get("policy_refs")
        if not isinstance(policy_refs, list) or "policy://harness/allowed-read-only" not in policy_refs:
            errors.append(f"{label}: bundle {run_id} policy_refs must include allowed-read-only policy")
        if not isinstance(policy_refs, list) or "gate://harness/terminal-closure-denied" not in policy_refs:
            errors.append(f"{label}: bundle {run_id} policy_refs must include terminal-closure denial")


def _validate_category_names(
    categories: Mapping[str, Any],
    errors: list[str],
    label: str,
    run_id: str,
) -> None:
    observed = set(categories)
    if observed != EXPECTED_CATEGORY_IDS:
        errors.append(f"{label}: bundle {run_id} categories must equal {sorted(EXPECTED_CATEGORY_IDS)}")
    for category_id in EXPECTED_CATEGORY_IDS:
        refs = categories.get(category_id)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}: bundle {run_id} category {category_id} must not be empty")


def _require_category_refs(
    categories: Mapping[str, Any],
    category_id: str,
    expected_refs: Any,
    errors: list[str],
    label: str,
    run_id: str,
) -> None:
    observed_refs = set(str(ref) for ref in categories.get(category_id, ()) if isinstance(ref, str))
    required_refs = set(str(ref) for ref in _iter_refs(expected_refs))
    missing_refs = sorted(required_refs - observed_refs)
    if missing_refs:
        errors.append(f"{label}: bundle {run_id} category {category_id} missing {missing_refs}")


def _validate_receipt_refs(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    receipt_refs = _mapping_at(example, ("receipt_refs",))
    if not receipt_refs:
        errors.append(f"{label}: receipt_refs must be an object")
        return
    for key, expected in EXPECTED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected:
            errors.append(f"{label}: receipt_refs.{key} must be {expected}")


def _validate_validators(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    validators = example.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append(f"{label}: validators must not be empty")
        return
    commands = {str(item.get("command")) for item in _objects(validators)}
    expected_command = (
        "python scripts/validate_agentic_service_harness_evidence_bundle_projection.py --strict"
    )
    if expected_command not in commands:
        errors.append(f"{label}: validators must include {expected_command}")


def _validate_boolean_flags(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if key_lower in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {path} must be false")
        if key_lower in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {path} must be true")


def _validate_secret_surface(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_strings(payload):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _source_runs_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(run["run_id"]): run
        for run in _objects(payload.get("runs"))
        if isinstance(run.get("run_id"), str)
    }


def _source_receipts_by_run_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(receipt["run_id"]): receipt
        for receipt in _objects(payload.get("receipts"))
        if isinstance(receipt.get("run_id"), str)
    }


def _iter_refs(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_refs(nested)
    elif isinstance(value, Iterable):
        for item in value:
            yield from _iter_refs(item)


def _check_value(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: Any,
    errors: list[str],
    label: str,
) -> None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            errors.append(f"{label}: {'.'.join(path)} is required")
            return
        current = current[key]
    if current != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


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


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse EvidenceBundle projection validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the harness EvidenceBundle projection contract."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--source-read-models", default=str(DEFAULT_SOURCE_READ_MODELS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for EvidenceBundle projection validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_evidence_bundle_projection(
        schema_path=Path(args.schema),
        example_paths=example_paths,
        source_read_models_path=Path(args.source_read_models),
    )
    write_evidence_bundle_projection_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS EVIDENCE BUNDLE PROJECTION VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS EVIDENCE BUNDLE PROJECTION INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
