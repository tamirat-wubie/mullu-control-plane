#!/usr/bin/env python3
"""Validate observed branch workspace creation receipt.

Purpose: prove a bounded branch workspace create effect is observed and
reconciled before filesystem writes or adapter execution can be considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_observed_branch_workspace_creation_receipt.schema.json,
examples/agentic_service_harness_observed_branch_workspace_creation_receipt.foundation.json,
scripts.validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding,
and scripts.validate_schemas.
Invariants:
  - Source workspace creation authority binding passes first.
  - Expected and observed workspace create effects match.
  - Downstream effects remain denied until separate evidence is admitted.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_AUTHORITY_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_AUTHORITY_SCHEMA,
    validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_observed_branch_workspace_creation_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_observed_branch_workspace_creation_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_observed_branch_workspace_creation_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_observed_branch_workspace_creation_receipt"
EXPECTED_SOURCE_AUTHORITY_REF = (
    "examples/agentic_service_harness_approved_branch_workspace_creation_authority_binding.foundation.json"
)
EXPECTED_EFFECT = "create_one_confined_branch_workspace_without_file_writes"
EXPECTED_WORKSPACE_ID = "workspace.harness-observe-branch-workspace-creation-20260626"
EXPECTED_BRANCH_NAME = "codex/harness-observe-branch-workspace-creation-20260626"
REQUIRED_RECONCILIATION_REFS = (
    "evidence://workspace-path-confined",
    "evidence://branch-workspace-create-observed",
    "evidence://authority-single-use-consumed",
)
REQUIRED_NEXT_REFS = (
    "evidence://filesystem-write-rollback-plan",
    "evidence://non-empty-diff-admission-preflight",
    "evidence://secret-redaction-policy",
    "approval://adapter-execution/operator-decision",
    "evidence://receipt-store-write-path",
    "evidence://cleanup-receipt-after-workspace-use",
)
REQUIRED_RECEIPT_REFS = {
    "observed_workspace_receipt_schema": (
        "schemas/agentic_service_harness_observed_branch_workspace_creation_receipt.schema.json"
    ),
    "authority_binding_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_authority_binding.schema.json"
    ),
    "authority_binding_fixture": EXPECTED_SOURCE_AUTHORITY_REF,
}
REQUIRED_TRUE_FLAGS = (
    "report_is_not_terminal_closure",
    "forbidden_effects_checked",
    "workspace_created",
    "workspace_path_confined",
    "authority_single_use_consumed",
    "post_create_observation_recorded",
    "cleanup_receipt_required_before_close",
    "required_for_closure",
)
REQUIRED_FALSE_FLAGS = (
    "terminal_closure",
    "filesystem_written",
    "branch_pushed",
    "pull_request_opened",
    "adapter_executed",
    "connector_called",
    "receipt_store_appended",
    "mutation_route_admitted",
    "secret_values_serialized",
    "destructive_operation_executed",
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
class ObservedBranchWorkspaceCreationReceiptValidation:
    """Validation report for observed branch workspace creation receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_authority_binding_ref: str
    source_authority_binding_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_observed_branch_workspace_creation_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_authority_schema_path: Path = DEFAULT_SOURCE_AUTHORITY_SCHEMA,
    source_authority_example_paths: Sequence[Path] = DEFAULT_SOURCE_AUTHORITY_EXAMPLES,
) -> ObservedBranchWorkspaceCreationReceiptValidation:
    """Validate observed branch workspace creation receipt examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "observed branch workspace creation receipt schema", errors)
    source_validation = validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding(
        schema_path=source_authority_schema_path,
        example_paths=source_authority_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source workspace authority binding: {error}" for error in source_validation.errors)
    source_authority = _load_json_object(
        source_authority_example_paths[0],
        "workspace authority binding source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"observed branch workspace creation receipt {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_observed_workspace_semantics(
            example,
            source_authority,
            errors,
            _path_label(example_path),
        )

    return ObservedBranchWorkspaceCreationReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_authority_binding_ref=EXPECTED_SOURCE_AUTHORITY_REF,
        source_authority_binding_ok=source_validation.ok,
    )


def write_observed_branch_workspace_creation_receipt_validation(
    validation: ObservedBranchWorkspaceCreationReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic observed workspace creation validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_observed_workspace_semantics(
    payload: Mapping[str, Any],
    source_authority: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _require_equal(payload, ("source_authority_binding_ref",), EXPECTED_SOURCE_AUTHORITY_REF, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(payload, ("observation_status",), "workspace_create_observed", errors, label)
    _require_equal(payload, ("effect_reconciliation", "expected_effect"), EXPECTED_EFFECT, errors, label)
    _require_equal(payload, ("effect_reconciliation", "observed_effect"), EXPECTED_EFFECT, errors, label)
    _require_equal(payload, ("effect_reconciliation", "reconciliation_status"), "MATCH", errors, label)
    _require_equal(payload, ("observed_workspace", "workspace_id"), EXPECTED_WORKSPACE_ID, errors, label)
    _require_equal(payload, ("observed_workspace", "branch_name"), EXPECTED_BRANCH_NAME, errors, label)
    if source_authority:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_authority, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_authority, ("scope", "repository_connection_id")),
            errors,
            label,
        )
    _require_refs(
        _get_nested(payload, ("effect_reconciliation", "evidence_refs")),
        REQUIRED_RECONCILIATION_REFS,
        f"{label}: effect_reconciliation.evidence_refs",
        errors,
    )
    all_next_refs: list[str] = []
    next_evidence = _get_nested(payload, ("required_next_evidence",))
    if isinstance(next_evidence, Mapping):
        for refs in next_evidence.values():
            if isinstance(refs, list):
                all_next_refs.extend(str(ref) for ref in refs)
    _require_refs(all_next_refs, REQUIRED_NEXT_REFS, f"{label}: required_next_evidence", errors)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
    else:
        for phrase in (
            "filesystem write admission",
            "cleanup obligation",
            "adapter execution",
            "receipt append",
            "terminal closure",
        ):
            if phrase not in next_action:
                errors.append(f"{label}: next_action must mention {phrase}")
    _validate_flags_and_forbidden_surfaces(payload, errors, label)


def _validate_flags_and_forbidden_surfaces(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        dotted_path = ".".join(path)
        key = path[-1]
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if key not in ALLOWED_SECRET_KEYS and _contains_secret_token(key):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


def _require_refs(
    observed: object,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_refs = {str(item) for item in observed}
    for required_ref in required:
        if required_ref not in observed_refs:
            errors.append(f"{label} missing required ref {required_ref}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} missing: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _require_equal(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: object,
    errors: list[str],
    label: str,
) -> None:
    observed = _get_nested(payload, path)
    if observed != expected:
        errors.append(f"{label}: {'.'.join(path)} expected {expected!r}, observed {observed!r}")


def _get_nested(payload: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _walk_leaves(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        leaves: list[tuple[tuple[str, ...], Any]] = []
        for key, child in value.items():
            leaves.extend(_walk_leaves(child, (*path, str(key))))
        return leaves
    if isinstance(value, list):
        leaves = []
        for index, child in enumerate(value):
            leaves.extend(_walk_leaves(child, (*path, str(index))))
        return leaves
    return [(path, value)]


def _contains_secret_token(key: str) -> bool:
    lowered_key = key.lower()
    return any(token in lowered_key for token in FORBIDDEN_SECRET_KEY_TOKENS)


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_mutated_observed_workspace_receipt(**updates: Any) -> dict[str, Any]:
    """Build a deep-copied fixture with double-underscore path overrides."""

    payload = json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8"))
    mutated = deepcopy(payload)
    for key, value in updates.items():
        parts = key.split("__")
        current: Any = mutated
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = value
    return mutated


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse observed branch workspace creation validation arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--source-authority-schema", type=Path, default=DEFAULT_SOURCE_AUTHORITY_SCHEMA)
    parser.add_argument("--source-authority-example", type=Path, action="append", dest="source_authority_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run observed branch workspace creation receipt validation."""

    args = parse_args(argv)
    validation = validate_agentic_service_harness_observed_branch_workspace_creation_receipt(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_authority_schema_path=args.source_authority_schema,
        source_authority_example_paths=(
            tuple(args.source_authority_examples)
            if args.source_authority_examples
            else DEFAULT_SOURCE_AUTHORITY_EXAMPLES
        ),
    )
    write_observed_branch_workspace_creation_receipt_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS OBSERVED BRANCH WORKSPACE CREATION RECEIPT VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
