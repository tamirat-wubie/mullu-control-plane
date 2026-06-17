#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub repository task service contract.

Purpose: prove the first GitHub repository task service and Codex-style
adapter descriptors remain read-only and contract-only before any UI, mutation
endpoint, live adapter execution, branch write, pull-request creation, secret
serialization, deployment, DNS, destructive operation, or terminal closure is
admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_repo_task_service.schema.json,
examples/agentic_service_harness_github_repo_task_service.foundation.json,
and scripts.validate_schemas.
Invariants:
  - Repository metadata probing is described as contract-only evidence.
  - Adapter descriptors deny execution and repository effects.
  - Secret-like keys, credential-like values, mutation routes, and terminal
    closure claims fail closed.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_github_repo_task_service.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_repo_task_service.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_repo_task_service_validation.json"
)
REQUIRED_ADAPTER_KINDS = ("github_repo_task", "codex_style_coding")
REQUIRED_FALSE_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "secret_values_serialized",
    "live_probe_executed",
    "writes_repository",
    "creates_branch",
    "opens_pull_request",
    "mutation_route",
    "route_admitted",
    "executes_adapter",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "approval_required_for_effects",
    "requires_workspace_sandbox",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
FORBIDDEN_ACTION_CLASSES = ("write_to_branch", "open_pr", "blocked_high_risk")
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "secret_values_serialized",
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
class GitHubRepoTaskServiceValidation:
    """Schema and semantic validation report for GitHub repo task service."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    required_adapter_kind_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_repo_task_service(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> GitHubRepoTaskServiceValidation:
    """Validate GitHub repo task service examples against schema and invariants."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub repo task service schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub repo task service example {_path_label(example_path)}",
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
        _validate_service_semantics(example, errors, _path_label(example_path))
    return GitHubRepoTaskServiceValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        required_adapter_kind_count=len(REQUIRED_ADAPTER_KINDS),
    )


def write_github_repo_task_service_validation(
    validation: GitHubRepoTaskServiceValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic GitHub repo task service validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_service_semantics(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _validate_scope_refs(example, errors, label)
    _validate_adapter_descriptors(example, errors, label)
    _validate_task_service(example, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_scope_refs(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = example.get("scope")
    probe = example.get("repository_metadata_probe")
    if not isinstance(scope, Mapping):
        errors.append(f"{label}: scope must be an object")
        return
    if not isinstance(probe, Mapping):
        errors.append(f"{label}: repository_metadata_probe must be an object")
        return
    if scope.get("repository_connection_id") != probe.get("repository_connection_id"):
        errors.append(f"{label}: repository connection refs must match")
    if scope.get("repository_slug") != probe.get("repository_slug"):
        errors.append(f"{label}: repository slug refs must match")
    if probe.get("provider") != "github":
        errors.append(f"{label}: repository metadata provider must be github")
    metadata_fields = probe.get("metadata_fields")
    if not isinstance(metadata_fields, list) or len(metadata_fields) < 4:
        errors.append(f"{label}: metadata_fields must contain repository metadata surface")
    source_refs = probe.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        errors.append(f"{label}: repository metadata source_refs must not be empty")


def _validate_adapter_descriptors(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    descriptors = example.get("adapter_descriptors")
    if not isinstance(descriptors, list):
        errors.append(f"{label}: adapter_descriptors must be a list")
        return
    observed_kinds = [str(item.get("adapter_kind")) for item in _objects(descriptors)]
    missing = sorted(set(REQUIRED_ADAPTER_KINDS) - set(observed_kinds))
    extra = sorted(set(observed_kinds) - set(REQUIRED_ADAPTER_KINDS))
    if missing:
        errors.append(f"{label}: adapter descriptors missing {missing}")
    if extra:
        errors.append(f"{label}: adapter descriptors unknown {extra}")
    if len(observed_kinds) != len(set(observed_kinds)):
        errors.append(f"{label}: adapter descriptors must not duplicate adapter_kind")
    for descriptor in _objects(descriptors):
        descriptor_label = f"{label}: adapter {descriptor.get('adapter_id')}"
        if descriptor.get("status") != "contract_only":
            errors.append(f"{descriptor_label} status must be contract_only")
        required_evidence_refs = descriptor.get("required_evidence_refs")
        if not isinstance(required_evidence_refs, list) or not required_evidence_refs:
            errors.append(f"{descriptor_label} required_evidence_refs must not be empty")
        if descriptor.get("adapter_kind") == "github_repo_task":
            allowed_modes = set(str(mode) for mode in descriptor.get("allowed_modes", ()))
            if allowed_modes != {"read_only"}:
                errors.append(f"{descriptor_label} allowed_modes must be read_only only")


def _validate_task_service(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    service = example.get("task_service")
    if not isinstance(service, Mapping):
        errors.append(f"{label}: task_service must be an object")
        return
    allowed = set(str(item) for item in service.get("allowed_action_classes", ()))
    forbidden = set(str(item) for item in service.get("forbidden_action_classes", ()))
    if allowed != {"read_only"}:
        errors.append(f"{label}: task_service allowed_action_classes must be read_only only")
    missing_forbidden = sorted(set(FORBIDDEN_ACTION_CLASSES) - forbidden)
    if missing_forbidden:
        errors.append(f"{label}: task_service forbidden_action_classes missing {missing_forbidden}")
    required_evidence_refs = service.get("required_evidence_refs")
    if not isinstance(required_evidence_refs, list) or not required_evidence_refs:
        errors.append(f"{label}: task_service required_evidence_refs must not be empty")


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


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
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
            yield from _walk_json(item, f"{path}[{index}]")


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
    """Parse GitHub repo task service validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the read-only harness GitHub repository task service contract."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for GitHub repo task service validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_github_repo_task_service(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_github_repo_task_service_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB REPO TASK SERVICE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS GITHUB REPO TASK SERVICE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
