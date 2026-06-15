#!/usr/bin/env python3
"""Validate Component Harness graph artifacts.

Purpose: prove component graph examples and runtime projections are
schema-valid, deterministic, endpoint-closed, and denied execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_graph.schema.json,
examples/component_graph.foundation.json, component graph runtime, and upstream
Component Harness validators.
Invariants:
  - Every graph edge endpoint references a registered component node.
  - Dependency, request-path, bundle, and blocked-path relationships are
    explicit.
  - Graph projection cannot grant execution, mutation, connector, or terminal
    closure authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_graph import build_component_graph  # noqa: E402
from scripts.validate_component_autopsy import validate_component_autopsy  # noqa: E402
from scripts.validate_component_read_model import validate_component_read_model  # noqa: E402
from scripts.validate_component_registry import validate_component_registry  # noqa: E402
from scripts.validate_component_request_simulation import validate_component_request_simulation  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_graph.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_graph.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_graph_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentGraphValidation:
    """Schema and semantic validation report for the component graph."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    component_count: int
    edge_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_graph(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentGraphValidation:
    """Validate the component graph schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component graph schema", errors)
    example = _load_json_object(example_path, "component graph example", errors)

    registry_validation = validate_component_registry()
    if not registry_validation.ok:
        errors.extend(f"component registry validation failed: {error}" for error in registry_validation.errors)
    read_model_validation = validate_component_read_model()
    if not read_model_validation.ok:
        errors.extend(f"component read model validation failed: {error}" for error in read_model_validation.errors)
    simulation_validation = validate_component_request_simulation()
    if not simulation_validation.ok:
        errors.extend(
            f"component request simulation validation failed: {error}"
            for error in simulation_validation.errors
        )
    autopsy_validation = validate_component_autopsy()
    if not autopsy_validation.ok:
        errors.extend(f"component autopsy validation failed: {error}" for error in autopsy_validation.errors)

    runtime_graph = build_component_graph()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_graph:
            errors.append(f"{_path_label(example_path)}: example does not match runtime graph")
        _validate_graph_semantics(example, errors, _path_label(example_path))
    _validate_graph_semantics(runtime_graph, errors, "runtime component graph")

    summary = runtime_graph.get("summary", {})
    return ComponentGraphValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        component_count=int(summary.get("component_count", 0)) if isinstance(summary, dict) else 0,
        edge_count=int(summary.get("edge_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_graph_validation(
    validation: ComponentGraphValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic component graph validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_graph_semantics(graph: dict[str, Any], errors: list[str], label: str) -> None:
    if graph.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if graph.get("graph_is_not_execution_authority") is not True:
        errors.append(f"{label}: graph must not be execution authority")
    for field_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
    ):
        if graph.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    if graph.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    memberships = graph.get("bundle_memberships")
    blocked_paths = graph.get("blocked_paths")
    summary = graph.get("summary")
    if not isinstance(nodes, list) or not nodes:
        errors.append(f"{label}: nodes must be non-empty")
        return
    if not isinstance(edges, list):
        errors.append(f"{label}: edges must be a list")
        return
    if not isinstance(memberships, list):
        errors.append(f"{label}: bundle_memberships must be a list")
        return
    if not isinstance(blocked_paths, list):
        errors.append(f"{label}: blocked_paths must be a list")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    node_ids = [str(node.get("component_id")) for node in nodes if isinstance(node, dict)]
    if len(node_ids) != len(set(node_ids)):
        errors.append(f"{label}: node component_ids must be unique")
    node_set = set(node_ids)
    for edge in edges:
        if not isinstance(edge, dict):
            errors.append(f"{label}: edge entries must be objects")
            continue
        if edge.get("edge_is_not_execution_authority") is not True:
            errors.append(f"{label}: edge must not be execution authority")
        endpoints = {str(edge.get("from_component_id")), str(edge.get("to_component_id"))}
        if not endpoints.issubset(node_set):
            errors.append(f"{label}: edge {edge.get('edge_id')} references unregistered endpoint")
        if edge.get("relation") == "request_path_next" and not _string_list(edge.get("scenario_refs")):
            errors.append(f"{label}: request path edge must carry scenario refs")
    for membership in memberships:
        if not isinstance(membership, dict):
            errors.append(f"{label}: bundle membership entries must be objects")
            continue
        if membership.get("component_id") not in node_set:
            errors.append(f"{label}: bundle membership references unregistered component")
        if membership.get("membership_is_not_execution_authority") is not True:
            errors.append(f"{label}: bundle membership must not be execution authority")
    blocked_component_ids = {str(path.get("component_id")) for path in blocked_paths if isinstance(path, dict)}
    if blocked_component_ids != node_set:
        errors.append(f"{label}: blocked_paths must cover every component")
    for path in blocked_paths:
        if not isinstance(path, dict):
            errors.append(f"{label}: blocked path entries must be objects")
            continue
        if path.get("terminal_closure_blocked") is not True:
            errors.append(f"{label}: blocked path terminal_closure_blocked must be true")
    if summary.get("component_count") != len(nodes):
        errors.append(f"{label}: summary.component_count must match nodes")
    if summary.get("edge_count") != len(edges):
        errors.append(f"{label}: summary.edge_count must match edges")
    if summary.get("bundle_membership_count") != len(memberships):
        errors.append(f"{label}: summary.bundle_membership_count must match memberships")
    if "authority_denial_receipt" not in _string_list(graph.get("expected_receipts")):
        errors.append(f"{label}: expected_receipts must include authority_denial_receipt")


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
    raise ValueError("non-finite JSON constants are not permitted")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component graph validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness graph.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component graph validation."""

    args = parse_args(argv)
    validation = validate_component_graph(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_graph_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT GRAPH VALID")
    else:
        print(f"COMPONENT GRAPH INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
