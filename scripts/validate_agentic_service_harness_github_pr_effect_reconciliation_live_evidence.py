#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR effect reconciliation live evidence.

Purpose: prove read-only GitHub PR effect reconciliation evidence is collected,
bounded, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_effect_reconciliation_live_evidence.schema.json,
examples/agentic_service_harness_github_pr_effect_reconciliation_live_evidence.foundation.json,
scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract, and scripts.validate_schemas.
Invariants:
  - The live evidence binds to the effect reconciliation evidence contract.
  - Branch, pull request, check, merge, and branch-deletion observations are reconciled.
  - The witness grants no repository mutation, secret, destructive, or terminal closure authority.
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

from scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_CONTRACT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_CONTRACT_SCHEMA,
    validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_effect_reconciliation_live_evidence.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_pr_effect_reconciliation_live_evidence.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_effect_reconciliation_live_evidence_validation.json"
)
EXPECTED_SOURCE_CONTRACT_REF = (
    "examples/agentic_service_harness_github_pr_effect_reconciliation_evidence_contract.foundation.json"
)
EXPECTED_BINDING_ID = "agentic_service_harness_github_pr_effect_reconciliation_live_evidence"
EXPECTED_EVIDENCE_REF = "evidence://effect-reconciliation-before-terminal-closure"
EXPECTED_RECEIPT_REFS = {
    "github_pr_effect_reconciliation_live_evidence_schema": (
        "schemas/agentic_service_harness_github_pr_effect_reconciliation_live_evidence.schema.json"
    ),
    "github_pr_effect_reconciliation_evidence_contract_schema": (
        "schemas/agentic_service_harness_github_pr_effect_reconciliation_evidence_contract.schema.json"
    ),
    "github_pr_effect_reconciliation_witness_schema": (
        "schemas/agentic_service_harness_github_pr_effect_reconciliation_witness.schema.json"
    ),
    "github_pr_terminal_closure_certificate_witness_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_witness.schema.json"
    ),
}
REQUIRED_FALSE_FLAGS = (
    "authority_granted",
    "terminal_closure",
    "is_draft",
    "head_branch_exists_after_merge",
    "terminal_closure_authorized",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "ready_for_review_enabled",
    "pull_request_merge_enabled",
    "repository_write_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "receipt_store_append_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "repository_written_by_witness",
    "connector_called_by_witness",
    "mutation_route_admitted_by_witness",
    "receipt_store_appended_by_witness",
    "secret_values_serialized_by_witness",
)
REQUIRED_TRUE_FLAGS = (
    "effect_reconciliation_collected",
    "read_only",
    "all_required_checks_green",
    "branch_state_reconciled",
    "pull_request_state_reconciled",
    "check_state_reconciled",
    "merge_state_reconciled",
    "branch_deletion_state_reconciled",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "secret_values_serialized_by_witness",
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
class GitHubPrEffectReconciliationLiveEvidenceValidation:
    """Schema and semantic validation report for live effect reconciliation evidence."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_evidence_contract_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_effect_reconciliation_live_evidence(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_contract_schema_path: Path = DEFAULT_SOURCE_CONTRACT_SCHEMA,
    source_contract_example_paths: Sequence[Path] = DEFAULT_SOURCE_CONTRACT_EXAMPLES,
) -> GitHubPrEffectReconciliationLiveEvidenceValidation:
    """Validate GitHub PR effect reconciliation live evidence examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR effect reconciliation live evidence schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_effect_reconciliation_evidence_contract(
        schema_path=source_contract_schema_path,
        example_paths=source_contract_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source PR effect reconciliation evidence contract: {error}" for error in source_validation.errors)
    source_contract = _load_json_object(
        source_contract_example_paths[0],
        "GitHub PR effect reconciliation evidence contract source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(example_path, f"GitHub PR effect reconciliation live evidence {_path_label(example_path)}", errors)
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_live_evidence_semantics(example, source_contract, errors, _path_label(example_path))
    return GitHubPrEffectReconciliationLiveEvidenceValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_evidence_contract_ref=EXPECTED_SOURCE_CONTRACT_REF,
    )


def write_github_pr_effect_reconciliation_live_evidence_validation(
    validation: GitHubPrEffectReconciliationLiveEvidenceValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic live evidence validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_live_evidence_semantics(
    payload: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("binding_id",), EXPECTED_BINDING_ID, errors, label)
    _require_equal(payload, ("source_evidence_contract_ref",), EXPECTED_SOURCE_CONTRACT_REF, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(payload, ("witness_kind",), "effect_reconciliation_live_evidence", errors, label)
    _require_equal(payload, ("evidence_ref",), EXPECTED_EVIDENCE_REF, errors, label)
    _require_equal(payload, ("observed_pull_request", "state"), "MERGED", errors, label)
    _require_equal(payload, ("observed_pull_request", "observation_source"), "gh_pr_view_and_ls_remote_read_only", errors, label)
    _require_equal(payload, ("observed_checks", "observation_source"), "gh_pr_checks_read_only", errors, label)
    _require_equal(payload, ("observed_checks", "bucket"), "pass", errors, label)
    _require_equal(payload, ("observed_checks", "failed_count"), 0, errors, label)
    _require_equal(payload, ("observed_checks", "pending_count"), 0, errors, label)
    _require_equal(payload, ("effect_boundary", "network_policy"), "read_only_github_metadata", errors, label)
    if source_contract:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_contract, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("evidence_ref",),
            _get_nested(source_contract, ("requested_evidence_ref",)),
            errors,
            label,
        )
    for key, expected_value in EXPECTED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        dotted_path = ".".join(path)
        if path[-1] in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if path[-1] in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if path[-1] not in ALLOWED_SECRET_KEYS and _contains_secret_token(path[-1]):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


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


def _require_equal(payload: Mapping[str, Any], path: tuple[str, ...], expected: object, errors: list[str], label: str) -> None:
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
    return any(token in key.lower() for token in FORBIDDEN_SECRET_KEY_TOKENS)


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_mutated_live_evidence(**updates: Any) -> dict[str, Any]:
    """Build a deep-copied example with double-underscore path overrides."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--source-contract-schema", type=Path, default=DEFAULT_SOURCE_CONTRACT_SCHEMA)
    parser.add_argument("--source-contract-example", type=Path, action="append", dest="source_contract_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_effect_reconciliation_live_evidence(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_contract_schema_path=args.source_contract_schema,
        source_contract_example_paths=(
            tuple(args.source_contract_examples) if args.source_contract_examples else DEFAULT_SOURCE_CONTRACT_EXAMPLES
        ),
    )
    write_github_pr_effect_reconciliation_live_evidence_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR EFFECT RECONCILIATION LIVE EVIDENCE VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
