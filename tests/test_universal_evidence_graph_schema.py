"""Tests for Universal Evidence Graph schema and fixture validation.

Purpose: prove the UEG schema and shipped fixture remain aligned with validators.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, and PRS fixture validation.
Dependencies: scripts.validate_schemas and scripts.validate_artifacts.
Invariants: schema-backed fixture validation fails closed on drift.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_artifacts import validate_mcoi_runtime_fixture
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_universal_evidence_graph_fixture_matches_schema() -> None:
    schema = _load_schema(REPO_ROOT / "schemas" / "universal_evidence_graph.schema.json")
    payload = json.loads(
        (REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "universal_evidence_graph.json").read_text(
            encoding="utf-8"
        )
    )

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["graph_id"] == "ueg-foundation-thread-001"
    assert payload["questions"][0]["answer_edge_ids"] == [
        "edge-receipt-supports-claim",
        "edge-policy-governs-claim",
    ]


def test_universal_evidence_graph_mcoi_runtime_fixture_validates() -> None:
    fixture_path = (
        REPO_ROOT
        / "integration"
        / "contracts_compat"
        / "fixtures"
        / "mcoi_runtime"
        / "universal_evidence_graph.json"
    )

    errors = validate_mcoi_runtime_fixture(fixture_path)

    assert errors == []
    assert fixture_path.name == "universal_evidence_graph.json"
    assert fixture_path.exists()
