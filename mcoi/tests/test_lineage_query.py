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

from gateway.command_spine import CommandLedger, CommandState, InMemoryCommandLedgerStore
from mcoi_runtime.core.artifact_lineage_dag import ArtifactLineageDAG, hash_artifact_payload
from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.core.lineage_query import (
    LineageEdge,
    LineageNode,
    _verify_graph,
    parse_lineage_uri,
    resolve_lineage_uri,
)
from mcoi_runtime.governance.policy.versioning import (
    PolicyArtifact,
    PolicyVersionRegistry,
    VersionedPolicyRule,
)
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


def _recorder_with_policy_ref(policy_version: str) -> ReplayRecorder:
    recorder = ReplayRecorder(clock=fixed_clock)
    recorder.start_trace("trace-policy-ref")
    recorder.record_frame(
        "trace-policy-ref",
        "request.accepted",
        {
            "tenant_id": "tenant-1",
            "policy_version": policy_version,
            "model_version": "model:v1",
            "budget_id": "budget-1",
        },
        {"proof_id": "proof:request"},
    )
    recorder.complete_trace("trace-policy-ref")
    return recorder


def _policy_registry() -> PolicyVersionRegistry:
    registry = PolicyVersionRegistry()
    registry.register(
        PolicyArtifact.create(
            policy_id="tenant-governance",
            version="v1",
            rules=(
                VersionedPolicyRule(
                    rule_id="tenant-boundary",
                    description="retain tenant boundary",
                    condition="tenant_id present",
                    action="allow",
                ),
            ),
            created_at="2026-04-25T12:00:00Z",
        )
    )
    return registry


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


def _command_ledger_with_events() -> tuple[CommandLedger, str]:
    ledger = CommandLedger(clock=fixed_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-command",
        actor_id="actor-command",
        source="web",
        conversation_id="conversation-command",
        idempotency_key="idem-command",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED, risk_tier="low", budget_decision="reserved")
    ledger.transition(command.command_id, CommandState.RESPONDED, output={"output_id": "out-command"})
    return ledger, command.command_id


def _artifact_lineage() -> ArtifactLineageDAG:
    lineage = ArtifactLineageDAG(clock=fixed_clock)
    lineage.register_artifact(
        artifact_id="source-json",
        artifact_hash=hash_artifact_payload({"source": True}),
        artifact_type="json",
        tenant_id="tenant-artifact",
        produced_by_event_id="event-source",
        metadata={"policy_version": "policy:v1", "budget_ref": "budget-artifact"},
    )
    lineage.register_artifact(
        artifact_id="summary-json",
        artifact_hash=hash_artifact_payload({"summary": True}),
        artifact_type="json",
        tenant_id="tenant-artifact",
        produced_by_event_id="event-summary",
        metadata={"policy_version": "policy:v1", "budget_ref": "budget-artifact"},
    )
    lineage.add_edge(
        upstream_artifact_id="source-json",
        downstream_artifact_id="summary-json",
        reason="summarize source",
    )
    return lineage


def test_parse_lineage_uri_extracts_bounded_query() -> None:
    query = parse_lineage_uri("lineage://trace/trace-1?depth=7&include=policy,tenant&verify=false")

    assert query.ref.ref_type == "trace"
    assert query.ref.ref_id == "trace-1"
    assert query.depth == 7
    assert query.include == ("policy", "tenant")
    assert query.verify is False


def test_parse_lineage_uri_accepts_artifact_refs() -> None:
    query = parse_lineage_uri("lineage://artifact/summary-json?depth=10&include=artifact,replay")

    assert query.ref.ref_type == "artifact"
    assert query.ref.ref_id == "summary-json"
    assert query.depth == 10
    assert query.include == ("artifact", "replay")


def test_parse_lineage_uri_deduplicates_include_values() -> None:
    query = parse_lineage_uri("lineage://trace/trace-1?include=policy,tenant,policy,budget")

    assert query.include == ("policy", "tenant", "budget")
    assert query.depth == 25
    assert query.verify is True


def test_lineage_uri_rejects_unsupported_include_value() -> None:
    with pytest.raises(ValueError, match="unsupported lineage include value"):
        parse_lineage_uri("lineage://trace/trace-1?include=policy,secrets")


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
    assert document["document_id"].startswith("lineage-doc:")
    assert document["document_hash"].startswith("sha256:")
    assert len(document["document_hash"]) == 71
    assert document["permalink"] == "lineage://trace/trace-1"
    assert document["governed"] is True
    assert document["verification"]["checked_nodes"] == 2
    assert document["verification"]["checked_edges"] == 1
    assert document["nodes"][0]["metadata"]["sequence"] == 1
    assert any("undocumented_field" in error for error in _validate_schema_instance(schema, invalid_document))


def test_resolved_artifact_lineage_document_satisfies_schema() -> None:
    schema = json.loads((REPO_ROOT / "schemas" / "lineage_query.schema.json").read_text(encoding="utf-8"))
    document = resolve_lineage_uri(
        "lineage://artifact/summary-json?depth=10",
        replay_source=ReplayRecorder(clock=fixed_clock),
        artifact_source=_artifact_lineage(),
        clock=fixed_clock,
    )

    assert _validate_schema_instance(schema, document) == []
    assert document["verified"] is True
    assert document["root_ref"] == {"ref_type": "artifact", "ref_id": "summary-json"}
    assert document["nodes"][0]["node_id"] == "artifact:source-json"
    assert document["nodes"][1]["parent_node_ids"] == ["artifact:source-json"]
    assert document["edges"] == [
        {
            "from_node_id": "artifact:source-json",
            "to_node_id": "artifact:summary-json",
            "relation": "depends_on",
        }
    ]
    assert document["nodes"][1]["metadata"]["replay_plan_ready"] is True
    assert document["nodes"][1]["metadata"]["replay_plan_hash"]


def test_lineage_document_projects_policy_version_read_model() -> None:
    recorder = _recorder_with_trace()

    document = resolve_lineage_uri(
        "lineage://trace/trace-1?depth=10",
        replay_source=recorder,
        clock=fixed_clock,
    )
    policy_projection = document["policy_versions"][0]

    assert policy_projection["policy_version"] == "policy:v1"
    assert policy_projection["node_count"] == 2
    assert policy_projection["tenant_ids"] == ["tenant-1"]
    assert set(policy_projection["node_ids"]) == {node["node_id"] for node in document["nodes"]}
    assert policy_projection["registry_lookup_status"] == "not_requested"
    assert policy_projection["policy_id"] == ""
    assert policy_projection["registry_version"] == ""
    assert policy_projection["artifact_hash"] == ""
    assert policy_projection["rule_count"] == 0
    assert policy_projection["created_at"] == ""


def test_lineage_document_enriches_policy_version_from_registry() -> None:
    registry = _policy_registry()

    document = resolve_lineage_uri(
        "lineage://trace/trace-policy-ref?depth=10",
        replay_source=_recorder_with_policy_ref("tenant-governance@v1"),
        clock=fixed_clock,
        policy_registry=registry,
    )
    policy_projection = document["policy_versions"][0]

    assert policy_projection["policy_version"] == "tenant-governance@v1"
    assert policy_projection["registry_lookup_status"] == "matched"
    assert policy_projection["policy_id"] == "tenant-governance"
    assert policy_projection["registry_version"] == "v1"
    assert policy_projection["artifact_hash"].startswith("policy-artifact-")
    assert policy_projection["rule_count"] == 1
    assert policy_projection["created_at"] == "2026-04-25T12:00:00Z"
    assert "rules" not in policy_projection


def test_lineage_document_reports_policy_registry_lookup_boundaries() -> None:
    registry = _policy_registry()

    unparseable_document = resolve_lineage_uri(
        "lineage://trace/trace-policy-ref?depth=10",
        replay_source=_recorder_with_policy_ref("policy:v1"),
        clock=fixed_clock,
        policy_registry=registry,
    )
    missing_document = resolve_lineage_uri(
        "lineage://trace/trace-policy-ref?depth=10",
        replay_source=_recorder_with_policy_ref("tenant-governance@v2"),
        clock=fixed_clock,
        policy_registry=registry,
    )

    assert unparseable_document["policy_versions"][0]["registry_lookup_status"] == "unparseable_ref"
    assert unparseable_document["policy_versions"][0]["policy_id"] == ""
    assert unparseable_document["policy_versions"][0]["rule_count"] == 0
    assert missing_document["policy_versions"][0]["registry_lookup_status"] == "not_found"
    assert missing_document["policy_versions"][0]["policy_id"] == "tenant-governance"
    assert missing_document["policy_versions"][0]["registry_version"] == "v2"
    assert missing_document["policy_versions"][0]["artifact_hash"] == ""


def test_lineage_document_hash_is_deterministic() -> None:
    recorder = _recorder_with_trace()

    first_document = resolve_lineage_uri(
        "lineage://trace/trace-1?depth=10",
        replay_source=recorder,
        clock=fixed_clock,
    )
    second_document = resolve_lineage_uri(
        "lineage://trace/trace-1?depth=10",
        replay_source=recorder,
        clock=fixed_clock,
    )

    assert first_document["document_id"] == second_document["document_id"]
    assert first_document["document_hash"] == second_document["document_hash"]
    assert first_document["document_hash"].startswith("sha256:")


def test_lineage_graph_verification_detects_edge_mismatches() -> None:
    parent = LineageNode(
        node_id="node-parent",
        node_type="request.accepted",
        parent_node_ids=(),
        trace_id="trace-graph",
        policy_version="policy:v1",
        model_version="model:v1",
        tenant_id="tenant-1",
        budget_ref="budget-1",
        proof_id="proof:parent",
        state_hash="hash-parent",
        timestamp=fixed_clock(),
    )
    child = LineageNode(
        node_id="node-child",
        node_type="output.completed",
        parent_node_ids=("node-parent",),
        trace_id="trace-graph",
        policy_version="policy:v1",
        model_version="model:v1",
        tenant_id="tenant-1",
        budget_ref="budget-1",
        proof_id="proof:child",
        state_hash="hash-child",
        timestamp=fixed_clock(),
    )
    dangling_edge = LineageEdge(from_node_id="missing-node", to_node_id="node-child", relation="caused")

    reason_codes = _verify_graph((parent, child), (dangling_edge,))

    assert "edge_endpoint_missing" in reason_codes
    assert "parent_edge_mismatch" in reason_codes
    assert "tenant_context_missing" not in reason_codes


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


def test_resolve_artifact_without_source_returns_unresolved_node() -> None:
    document = resolve_lineage_uri(
        "lineage://artifact/summary-json",
        replay_source=ReplayRecorder(clock=fixed_clock),
        clock=fixed_clock,
    )

    assert document["verified"] is False
    assert document["verification"]["reason_codes"] == ["artifact_source_not_configured"]
    assert document["nodes"][0]["metadata"]["reason"] == "artifact_source_not_configured"
    assert document["unresolved_nodes"] == ["unresolved:artifact:summary-json"]


def test_resolve_missing_artifact_returns_unresolved_node() -> None:
    document = resolve_lineage_uri(
        "lineage://artifact/missing-artifact",
        replay_source=ReplayRecorder(clock=fixed_clock),
        artifact_source=_artifact_lineage(),
        clock=fixed_clock,
    )

    assert document["verified"] is False
    assert document["verification"]["reason_codes"] == ["artifact_not_found"]
    assert document["nodes"][0]["metadata"]["reason"] == "artifact_not_found"
    assert document["unresolved_nodes"] == ["unresolved:artifact:missing-artifact"]


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


def test_resolve_command_lineage_prefers_command_source_when_available() -> None:
    replay_recorder = ReplayRecorder(clock=fixed_clock)
    command_ledger, command_id = _command_ledger_with_events()

    document = resolve_lineage_uri(
        f"lineage://command/{command_id}?depth=3",
        replay_source=replay_recorder,
        command_source=command_ledger,
        clock=fixed_clock,
    )

    assert document["verified"] is True
    assert document["nodes"][0]["node_id"] == f"command:{command_id}"
    assert document["nodes"][0]["tenant_id"] == "tenant-command"
    assert document["nodes"][1]["node_type"] == "command.received"
    assert document["nodes"][2]["budget_ref"] == "reserved"
    assert len(document["edges"]) == 2


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
