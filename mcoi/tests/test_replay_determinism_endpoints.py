"""Purpose: verify replay determinism HTTP endpoint.

Governance scope: operator-facing deterministic replay report generation over
completed replay traces.
Dependencies: FastAPI test client, replay recorder, replay determinism router.
Invariants: reports are governed; missing traces fail closed; unknown
operations are explicit mismatches, not silent success.
"""

from __future__ import annotations

import os

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture()
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_ENABLED"] = "true"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.routers.deps import deps
    from mcoi_runtime.app.server import app

    trace_id = "replay-http-trace"
    if deps.replay_recorder.get_trace(trace_id) is None:
        deps.replay_recorder.start_trace(trace_id)
        deps.replay_recorder.record_frame(trace_id, "add", {"a": 2, "b": 3}, {"result": 5})
        deps.replay_recorder.record_frame(trace_id, "echo", {"value": "ok"}, {"value": "ok"})
        deps.replay_recorder.complete_trace(trace_id)
    return TestClient(app)


def test_replay_determinism_endpoint_returns_match_report(client) -> None:
    response = client.post(
        "/api/v1/replay/replay-http-trace/determinism",
        json={
            "replay_id": "replay-http-fixed",
            "operations": {
                "add": {"kind": "add_numbers"},
                "echo": {"kind": "echo_field", "field": "value"},
            },
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["governed"] is True
    assert data["report"]["deterministic"] is True
    assert data["report"]["matched_frames"] == 2
    assert data["report"]["report_hash"].startswith("replay-report-")


def test_replay_determinism_endpoint_reports_unknown_operation(client) -> None:
    response = client.post(
        "/api/v1/replay/replay-http-trace/determinism",
        json={"operations": {"add": {"kind": "add_numbers"}}},
    )
    report = response.json()["report"]

    assert response.status_code == 200
    assert report["deterministic"] is False
    assert report["reason_codes"] == ["unknown_operation"]
    assert report["frame_checks"][1]["operation"] == "echo"


def test_replay_determinism_endpoint_missing_trace_fails_closed(client) -> None:
    response = client.post(
        "/api/v1/replay/missing-trace/determinism",
        json={"operations": {}},
    )
    detail = response.json()["detail"]

    assert response.status_code == 404
    assert detail["error_code"] == "replay_trace_not_found"
    assert detail["governed"] is True
