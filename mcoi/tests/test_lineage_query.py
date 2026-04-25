"""Purpose: verify read-only lineage URI resolution.

Governance scope: lineage parsing, replay trace projection, unresolved-node
visibility, and bounded verification reason codes.
Dependencies: lineage_query resolver and execution replay recorder.
Invariants: resolver never mutates replay state; tenant context is retained;
missing traces are explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.core.lineage_query import parse_lineage_uri, resolve_lineage_uri
from scripts.validate_schemas import _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parents[2]


def fixed_clock() -> str:
    return "2026-04-25T12:00:00Z"


def _recorder_with_trace() -> ReplayRecorder:
    recorder = ReplayRecorder(clock=fixed_clock)
    recorder.start_trace("trace-1")
    recorder.record_frame(
        "trace-1",
        "request.accepted",
        {
            "tenant_id": "tenant-1",
            "policy_version": "policy:v1",
            "model_version": "model:v1",
            "budget_id": "budget-1",
        },
        {"proof_id": "proof:request"},
    )
    recorder.record_frame(
        "trace-1",
        "output.completed",
        {
            "tenant_id": "tenant-1",
            "policy_version": "policy:v1",
            "model_version": "model:v1",
            "budget_id": "budget-1",
        },
        {"proof_id": "proof:output"},
    )
    recorder.complete_trace("trace-1")
    return recorder


def _recorder_with_indexed_refs() -> ReplayRecorder:
    recorder = ReplayRecorder(clock=fixed_clock)
    recorder.start_trace("trace-indexed")
    recorder.record_frame(
        "trace-indexed",
        "command.accepted",
        {
            "tenant_id": "tenant-1",
            "policy_version": "policy:v1",
            "model_version": "model:v1",
            "budget_id": "budget-1",
            "command_id": "cmd-1",
        },
        {"proof_id": "proof:command"},
    )
    recorder.record_frame(
        "trace-indexed",
        "output.completed",
        {
            "tenant_id": "tenant-1",
            "policy_version": "policy:v1",
            "model_version": "model:v1",
            "budget_id": "budget-1",
        },
        {"proof_id": "proof:output", "output_id": "out-1"},
    )
    recorder.complete_trace("trace-indexed")
    return recorder


def test_parse_lineage_uri_extracts_bounded_query() -> None:
    query = parse_lineage_uri("lineage://trace/trace-1?depth=7&include=policy,tenant&verify=false")

    assert query.ref.ref_type == "trace"
    assert query.ref.ref_id == "trace-1"
    assert query.depth == 7
    assert query.include == ("policy", "tenant")
    assert query.verify is False


def test_resolve_trace_lineage_projects_replay_frames() -> None:
    recorder = _recorder_with_trace()

    document = resolve_lineage_uri(
        "lineage://trace/trace-1?depth=10",
        replay_source=recorder,
        clock=fixed_clock,
    )

    assert document["verified"] is True
    assert document["root_ref"] == {"ref_type": "trace", "ref_id": "trace-1"}
    assert len(document["nodes"]) == 2
    assert len(document["edges"]) == 1
    assert document["nodes"][0]["tenant_id"] == "tenant-1"
    assert document["nodes"][1]["parent_node_ids"] == [document["nodes"][0]["node_id"]]


def test_resolved_lineage_document_satisfies_schema() -> None:
    recorder = _recorder_with_trace()
    schema = json.loads((REPO_ROOT / "schemas" / "lineage_query.schema.json").read_text(encoding="utf-8"))

    document = resolve_lineage_uri(
        "lineage://trace/trace-1?depth=10",
        replay_source=recorder,
        clock=fixed_clock,
    )
    invalid_document = {**document, "undocumented_field": "not permitted"}

    assert _validate_schema_instance(schema, document) == []
    assert document["schema_version"] == 1
    assert document["governed"] is True
    assert document["nodes"][0]["metadata"]["sequence"] == 1
    assert any("undocumented_field" in error for error in _validate_schema_instance(schema, invalid_document))


def test_resolve_missing_trace_returns_unresolved_node() -> None:
    recorder = ReplayRecorder(clock=fixed_clock)

    document = resolve_lineage_uri(
        "lineage://trace/missing-trace",
        replay_source=recorder,
        clock=fixed_clock,
    )

    assert document["verified"] is False
    assert document["verification"]["reason_codes"] == ["trace_not_found"]
    assert len(document["nodes"]) == 1
    assert document["nodes"][0]["unresolved"] is True
    assert document["unresolved_nodes"] == ["unresolved:trace:missing-trace"]


def test_resolve_output_lineage_uses_bounded_replay_index() -> None:
    recorder = _recorder_with_indexed_refs()

    document = resolve_lineage_uri(
        "lineage://output/out-1?depth=5",
        replay_source=recorder,
        clock=fixed_clock,
    )

    assert document["verified"] is True
    assert document["root_ref"] == {"ref_type": "output", "ref_id": "out-1"}
    assert document["nodes"][0]["trace_id"] == "trace-indexed"
    assert document["nodes"][1]["metadata"]["sequence"] == 2
    assert document["unresolved_nodes"] == []


def test_resolve_command_lineage_uses_bounded_replay_index() -> None:
    recorder = _recorder_with_indexed_refs()

    document = resolve_lineage_uri(
        "lineage://command/cmd-1?depth=1",
        replay_source=recorder,
        clock=fixed_clock,
    )

    assert document["verified"] is True
    assert document["root_ref"] == {"ref_type": "command", "ref_id": "cmd-1"}
    assert document["depth"] == 1
    assert len(document["nodes"]) == 1
    assert document["nodes"][0]["trace_id"] == "trace-indexed"


def test_invalid_lineage_uri_is_rejected() -> None:
    recorder = ReplayRecorder(clock=fixed_clock)

    with pytest.raises(ValueError, match="lineage scheme"):
        resolve_lineage_uri("https://trace/trace-1", replay_source=recorder, clock=fixed_clock)


def test_lineage_uri_rejects_non_integer_depth() -> None:
    with pytest.raises(ValueError, match="depth must be an integer"):
        parse_lineage_uri("lineage://trace/trace-1?depth=deep")


def test_lineage_uri_rejects_excessive_depth() -> None:
    with pytest.raises(ValueError, match="depth must be at most 100"):
        parse_lineage_uri("lineage://trace/trace-1?depth=101")
