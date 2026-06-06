"""Tests for Universal State Engine schema and fixture validation.

Purpose: prove the USE schema and shipped fixture remain aligned with validators.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS fixture validation.
Dependencies: scripts.validate_schemas and scripts.validate_artifacts.
Invariants: schema-backed fixture validation fails closed on state contract drift.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_artifacts import validate_mcoi_runtime_fixture
from scripts.validate_schemas import _load_schema, _validate_schema_instance


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_universal_state_engine_fixture_matches_schema() -> None:
    schema = _load_schema(REPO_ROOT / "schemas" / "universal_state_engine.schema.json")
    payload = json.loads(
        (REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "universal_state_engine.json").read_text(
            encoding="utf-8"
        )
    )

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["engine_id"] == "use-foundation-thread-001"
    assert payload["state_machines"][0]["terminal_states"] == ["closed", "rolled_back"]
    assert payload["transitions"][0]["guard_ids"] == ["guard://workflow-close-receipt"]


def test_universal_state_engine_mcoi_runtime_fixture_validates() -> None:
    fixture_path = (
        REPO_ROOT
        / "integration"
        / "contracts_compat"
        / "fixtures"
        / "mcoi_runtime"
        / "universal_state_engine.json"
    )

    errors = validate_mcoi_runtime_fixture(fixture_path)

    assert errors == []
    assert fixture_path.name == "universal_state_engine.json"
    assert fixture_path.exists()
