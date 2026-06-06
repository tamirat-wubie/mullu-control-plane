"""Tests for Universal Evidence Graph contracts.

Purpose: prove UEG runtime contracts preserve typed evidence mesh invariants.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, and PRS contract validation.
Dependencies: mcoi_runtime.contracts.universal_evidence_graph.
Invariants: graph references are explicit, evidence-backed, and deterministic.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.universal_evidence_graph import (
    UniversalEvidenceGraph,
    UniversalEvidenceGraphEdge,
    UniversalEvidenceGraphEdgeKind,
    UniversalEvidenceGraphNode,
    UniversalEvidenceGraphNodeKind,
    UniversalEvidenceQuestionAnswer,
    UniversalEvidenceQuestionKind,
)


TS = "2026-06-06T08:30:00+00:00"


def _node(**overrides: object) -> UniversalEvidenceGraphNode:
    values = {
        "node_id": "node-claim",
        "node_kind": UniversalEvidenceGraphNodeKind.CLAIM,
        "label": "Foundation Mode claim",
        "source_ref": "claim://foundation/mode",
        "evidence_refs": ("docs/FOUNDATION_MODE.md",),
        "confidence": 0.9,
        "created_at": TS,
        "metadata": {"surface": "sdlc"},
    }
    values.update(overrides)
    return UniversalEvidenceGraphNode(**values)


def _edge(**overrides: object) -> UniversalEvidenceGraphEdge:
    values = {
        "edge_id": "edge-support",
        "edge_kind": UniversalEvidenceGraphEdgeKind.SUPPORTS,
        "source_node_id": "node-receipt",
        "target_node_id": "node-claim",
        "evidence_refs": ("receipt://workspace-governance-preflight",),
        "confidence": 0.9,
        "created_at": TS,
        "metadata": {"reason": "receipt anchors claim"},
    }
    values.update(overrides)
    return UniversalEvidenceGraphEdge(**values)


def _question(**overrides: object) -> UniversalEvidenceQuestionAnswer:
    values = {
        "question_id": "question-why",
        "question_kind": UniversalEvidenceQuestionKind.WHY,
        "target_node_id": "node-claim",
        "answer_node_ids": ("node-receipt",),
        "answer_edge_ids": ("edge-support",),
        "confidence": 0.9,
        "created_at": TS,
    }
    values.update(overrides)
    return UniversalEvidenceQuestionAnswer(**values)


def _graph(**overrides: object) -> UniversalEvidenceGraph:
    values = {
        "graph_id": "ueg-foundation-thread-001",
        "version": "ueg.v1",
        "generated_at": TS,
        "nodes": (
            _node(),
            _node(
                node_id="node-receipt",
                node_kind=UniversalEvidenceGraphNodeKind.RECEIPT,
                label="Preflight receipt",
                source_ref="receipt://workspace-governance-preflight",
                evidence_refs=(".tmp/workspace-governance-preflight-receipt.json",),
                confidence=1.0,
            ),
        ),
        "edges": (_edge(),),
        "questions": (_question(),),
        "receipt_refs": ("receipt://workspace-governance-preflight",),
        "metadata": {"foundation_mode": True},
    }
    values.update(overrides)
    return UniversalEvidenceGraph(**values)


def test_universal_evidence_graph_round_trips_to_json_dict() -> None:
    graph = _graph()
    payload = graph.to_json_dict()

    assert payload["graph_id"] == "ueg-foundation-thread-001"
    assert payload["nodes"][0]["node_kind"] == "claim"
    assert payload["edges"][0]["edge_kind"] == "supports"
    assert payload["questions"][0]["question_kind"] == "why"


def test_universal_evidence_graph_rejects_dangling_edge_source() -> None:
    with pytest.raises(ValueError, match="source_node_id"):
        _graph(edges=(_edge(source_node_id="node-missing"),))


def test_universal_evidence_graph_rejects_duplicate_node_ids() -> None:
    duplicate_nodes = (
        _node(node_id="node-claim"),
        _node(node_id="node-claim", source_ref="claim://duplicate"),
    )

    with pytest.raises(ValueError, match="duplicate node_id"):
        _graph(nodes=duplicate_nodes)


def test_universal_evidence_graph_rejects_question_dangling_answer_edge() -> None:
    with pytest.raises(ValueError, match="answer_edge_ids"):
        _graph(questions=(_question(answer_edge_ids=("edge-missing",)),))


def test_universal_evidence_graph_requires_evidence_refs() -> None:
    with pytest.raises(ValueError, match="evidence_refs"):
        _node(evidence_refs=())
