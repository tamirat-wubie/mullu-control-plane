"""Tests for Symbolic Simulation Engine schema and fixture validation.

Purpose: prove the SSE schema and shipped fixture remain aligned with validators.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS fixture validation.
Dependencies: scripts.validate_schemas and scripts.validate_artifacts.
Invariants: schema-backed fixture validation fails closed on drift.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_artifacts import validate_mcoi_runtime_fixture
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_symbolic_simulation_engine_fixture_matches_schema() -> None:
    schema = _load_schema(REPO_ROOT / "schemas" / "symbolic_simulation_engine.schema.json")
    payload = json.loads(
        (REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "symbolic_simulation_engine.json").read_text(
            encoding="utf-8"
        )
    )

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["run_id"] == "sse-run-001"
    assert payload["metadata"]["sequence"] == "action_simulate_compare_decide_execute_gate"


def test_symbolic_simulation_engine_mcoi_runtime_fixture_validates() -> None:
    fixture_path = (
        REPO_ROOT
        / "integration"
        / "contracts_compat"
        / "fixtures"
        / "mcoi_runtime"
        / "symbolic_simulation_engine.json"
    )

    errors = validate_mcoi_runtime_fixture(fixture_path)

    assert errors == []
    assert fixture_path.name == "symbolic_simulation_engine.json"
    assert fixture_path.exists()
