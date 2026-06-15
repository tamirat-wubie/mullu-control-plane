"""Tests for Component Harness graph validation.

Purpose: prove component graph examples, runtime projections, and validation
guardrails remain read-only, endpoint-closed, and evidence-bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_graph and component graph runtime.
Invariants: graph edges only reference registered components and never grant
execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_graph import build_component_graph
from scripts.validate_component_graph import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_graph,
    write_component_graph_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_graph.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_graph_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_graph()
    output_path = tmp_path / "component-graph-validation.json"

    written_path = write_component_graph_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.component_count == 10
    assert validation.edge_count == 19
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_graph_validation.json"


def test_component_graph_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_graph()
    edge_ids = {edge["edge_id"] for edge in example["edges"]}

    assert example == projection
    assert example["graph_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert example["summary"]["cycle_count"] == 0
    assert "edge.governance_core.request_path_next.nested_mind_bridge" in edge_ids
    assert "edge.personal_assistant.depends_on.gmail_account_binding_gate" in edge_ids


def test_component_graph_rejects_unregistered_edge_and_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["can_execute"] = True
    payload["edges"][0]["to_component_id"] = "missing_component"

    validation = validate_component_graph(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "can_execute" in serialized_errors
    assert "unregistered endpoint" in serialized_errors
    assert "example does not match runtime graph" in serialized_errors


def test_component_graph_covers_every_component_with_blocked_path() -> None:
    graph = build_component_graph()
    node_ids = {node["component_id"] for node in graph["nodes"]}
    blocked_path_ids = {path["component_id"] for path in graph["blocked_paths"]}

    assert blocked_path_ids == node_ids
    assert graph["summary"]["component_count"] == len(node_ids)
    assert all(path["terminal_closure_blocked"] is True for path in graph["blocked_paths"])
