"""Spatial map schema contract tests.

Purpose: bind the gateway spatial governance read model to a public JSON schema.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/spatial_map.schema.json, spatial_governance, and FastAPI.
Invariants:
  - Spatial map wire shape is explicit and schema-validated.
  - Unknown top-level fields fail closed.
  - Judgment statuses remain bounded to allowed, blocked, or unknown.
"""

from __future__ import annotations

import os
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.validate_schemas import _load_schema, _validate_schema_instance

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    FASTAPI_AVAILABLE = False


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "spatial_map.schema.json"


@pytest.fixture
def schema() -> dict[str, object]:
    return _load_schema(SCHEMA_PATH)


@pytest.fixture
def client() -> TestClient:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_spatial_map_builder_matches_public_schema(schema: dict[str, object]) -> None:
    from mcoi_runtime.core.spatial_governance import build_gateway_spatial_map

    spatial_map = _json_safe(build_gateway_spatial_map({"database": False, "dns": False}).to_dict())

    errors = _validate_schema_instance(schema, spatial_map)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:spatial-map:1"
    assert spatial_map["frame"].startswith("gateway_architecture_space")


def test_spatial_map_endpoint_payload_matches_public_schema(
    client: TestClient,
    schema: dict[str, object],
) -> None:
    response = client.get("/api/v1/spatial-map")
    payload = response.json()

    errors = _validate_schema_instance(schema, payload["spatial_map"])

    assert response.status_code == 200
    assert payload["governed"] is True
    assert errors == []


def test_spatial_map_schema_rejects_unknown_top_level_field(schema: dict[str, object]) -> None:
    from mcoi_runtime.core.spatial_governance import build_gateway_spatial_map

    spatial_map = _json_safe(build_gateway_spatial_map({}).to_dict())
    malformed_map = deepcopy(spatial_map)
    malformed_map["silent_boundary"] = "unwitnessed"

    errors = _validate_schema_instance(schema, malformed_map)

    assert len(errors) == 1
    assert "$" in errors[0]
    assert "unexpected property 'silent_boundary'" in errors[0]


def test_spatial_map_schema_rejects_unbounded_judgment_status(schema: dict[str, object]) -> None:
    from mcoi_runtime.core.spatial_governance import build_gateway_spatial_map

    spatial_map = _json_safe(build_gateway_spatial_map({}).to_dict())
    malformed_map = deepcopy(spatial_map)
    malformed_map["judgments"][0]["status"] = "maybe"

    errors = _validate_schema_instance(schema, malformed_map)

    assert len(errors) == 1
    assert "$.judgments[0].status" in errors[0]
    assert "expected one of" in errors[0]


def _json_safe(payload: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(payload))
