"""Purpose: verify read-only UniversalSymbol operator projections.
Governance scope: Foundation Mode symbol inspection for component and worker
read models.
Dependencies: jsonschema, component router, symbol operator read models, and
UniversalSymbol schema.
Invariants:
  - Projected symbols satisfy the UniversalSymbol schema.
  - Operator read models deny runtime authority.
  - Worker projection remains fixture-backed and read-only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from mcoi_runtime.app.routers.components import router
from mcoi_runtime.app.symbol_operator_read_models import (
    COMPONENT_SYMBOL_READ_MODEL_ID,
    WORKER_RECEIPT_SYMBOL_READ_MODEL_ID,
    SymbolOperatorReadModelError,
    build_component_symbol_read_model,
    build_worker_receipt_symbol_read_model,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.symbol_skill_adapter import AUTHORITY_DENIAL_FIELDS


REPO_ROOT = Path(__file__).resolve().parents[2]


def _validator() -> Draft202012Validator:
    schema = json.loads((REPO_ROOT / "schemas" / "universal_symbol.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _assert_all_authority_denied(payload: dict[str, object]) -> None:
    assert payload["read_model_is_not_execution_authority"] is True
    assert payload["symbol_projection_is_read_only"] is True
    for field_name in AUTHORITY_DENIAL_FIELDS:
        assert payload[field_name] is False
    for symbol in payload["symbols"]:
        boundary = symbol["symbol_authority_boundary"]
        assert all(value is False for value in boundary.values())


def test_component_symbol_read_model_projects_schema_valid_symbols() -> None:
    read_model = build_component_symbol_read_model(limit=3)
    symbols = read_model["symbols"]
    validator = _validator()

    for symbol in symbols:
        validator.validate(symbol)

    assert read_model["read_model_id"] == COMPONENT_SYMBOL_READ_MODEL_ID
    assert read_model["operation"] == "component_symbol_read_model"
    assert read_model["source_surface"] == "component_registry_entry"
    assert read_model["source_count"] == 10
    assert read_model["selected_count"] == 3
    assert read_model["symbol_count"] == 3
    assert read_model["source_summary"]["component_count"] == 10
    assert read_model["source_summary"]["blocked_component_count"] == 1
    assert all(symbol["symbol_identity"]["symbol_kind"] == "component" for symbol in symbols)
    assert all(symbol["symbol_governance"]["governance_mode"] == "foundation" for symbol in symbols)


def test_component_symbol_route_is_read_only() -> None:
    client = _client()

    response = client.get("/api/v1/components/symbols")
    post_response = client.post("/api/v1/components/symbols", json={"action": "mutate"})
    put_response = client.put("/api/v1/components/symbols", json={"action": "mutate"})
    delete_response = client.delete("/api/v1/components/symbols")
    payload = response.json()

    assert response.status_code == 200
    assert payload["read_model_id"] == COMPONENT_SYMBOL_READ_MODEL_ID
    assert payload["governed"] is True
    assert payload["foundation_mode"] is True
    assert payload["symbol_count"] == 10
    assert payload["runtime_dispatch_performed"] is False
    assert payload["terminal_closure_allowed"] is False
    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405


def test_worker_receipt_symbol_read_model_projects_schema_valid_symbols() -> None:
    read_model = build_worker_receipt_symbol_read_model()
    symbols = read_model["symbols"]
    validator = _validator()

    for symbol in symbols:
        validator.validate(symbol)

    assert read_model["read_model_id"] == WORKER_RECEIPT_SYMBOL_READ_MODEL_ID
    assert read_model["operation"] == "worker_receipt_symbol_read_model"
    assert read_model["source_surface"] == "worker_receipt"
    assert read_model["source_count"] == 3
    assert read_model["selected_count"] == 3
    assert read_model["symbol_count"] == 3
    assert read_model["source_summary"]["blocked_chain_count"] == 2
    assert read_model["source_summary"]["recovery_required_count"] == 1
    assert read_model["source_summary"]["terminal_closure_allowed_count"] == 0
    assert all(symbol["symbol_identity"]["symbol_kind"] == "receipt" for symbol in symbols)
    assert all(symbol["symbol_identity"]["domain"] == "worker" for symbol in symbols)


def test_symbol_operator_read_models_deny_runtime_authority() -> None:
    component_model = build_component_symbol_read_model(limit=2)
    worker_model = build_worker_receipt_symbol_read_model(limit=2)

    _assert_all_authority_denied(component_model)
    _assert_all_authority_denied(worker_model)

    assert component_model["connector_call_performed"] is False
    assert component_model["filesystem_write_performed"] is False
    assert worker_model["runtime_dispatch_performed"] is False
    assert worker_model["success_claim_allowed"] is False
    assert worker_model["raw_private_payload_stored"] is False
    assert worker_model["raw_secret_value_stored"] is False


def test_symbol_operator_read_model_rejects_invalid_limits() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="limit must be between 1 and 100"):
        build_component_symbol_read_model(limit=0)
    with pytest.raises(RuntimeCoreInvariantError, match="limit must be between 1 and 100"):
        build_worker_receipt_symbol_read_model(limit=101)
    with pytest.raises(RuntimeCoreInvariantError, match="limit must be an integer"):
        build_component_symbol_read_model(limit=True)


def test_worker_receipt_symbol_read_model_rejects_live_fixture_drift() -> None:
    with pytest.raises(SymbolOperatorReadModelError, match="source_receipt_store_live_read_performed=false"):
        build_worker_receipt_symbol_read_model(
            worker_read_model={
                "source_scope": {
                    "source_receipt_store_live_read_performed": True,
                    "fixture_projection": True,
                },
                "receipt_chains": [],
            }
        )
