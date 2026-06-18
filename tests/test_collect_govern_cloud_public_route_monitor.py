"""Tests for the Govern Cloud public route monitor collector.

Purpose: verify non-mutating public route monitoring receipts.
Governance scope: Govern Cloud public read-route publication and rollback
  boundary.
Dependencies: mocked HTTP probes, schema validator, collector script.
Invariants:
  - Raw response bodies are not serialized into monitor receipts.
  - The monitor passes only when read routes pass and evaluate remains blocked.
  - Missing or widened public route evidence remains AwaitingEvidence.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_govern_cloud_public_route_monitor import (  # noqa: E402
    HttpProbeResult,
    collect_govern_cloud_public_route_monitor,
    main,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA = _ROOT / "schemas" / "govern_cloud_public_route_monitor_receipt.schema.json"
OBSERVED_AT = datetime(2026, 6, 12, 18, 0, 0, tzinfo=UTC)


def _result(status_code: int, payload: dict[str, object]) -> HttpProbeResult:
    return HttpProbeResult(
        status_code=status_code,
        headers={"content-type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
        reached_endpoint=True,
        error="",
    )


def _getter(method: str, url: str) -> HttpProbeResult:
    if method == "GET" and url.endswith("/v1/health"):
        return _result(200, {"status": "ok", "service": "mullusi-govern-cloud-staging"})
    if method == "GET" and url.endswith("/v1/version"):
        return _result(200, {"api": "2026.05.v1", "evaluator": "govern-evaluator.v1"})
    if method == "POST" and url.endswith("/v1/govern/evaluate"):
        return _result(404, {"detail": "Not Found"})
    raise AssertionError(f"unexpected request: {method} {url}")


def test_monitor_receipt_passes_for_expected_public_routes_and_blocked_evaluate() -> None:
    receipt = collect_govern_cloud_public_route_monitor(http_getter=_getter, now_utc=OBSERVED_AT)

    assert receipt["solver_outcome"] == "SolvedVerified"
    assert receipt["proof_state"] == "Pass"
    assert receipt["summary"]["passed_route_count"] == 3
    assert receipt["summary"]["public_read_routes_verified"] is True
    assert receipt["summary"]["blocked_route_guard_verified"] is True
    assert receipt["raw_secret_values_included"] is False
    assert [item["method"] for item in receipt["route_observations"]] == ["GET", "GET", "POST"]
    assert all(item["error"] == "" for item in receipt["route_observations"])
    assert _validate_schema_instance(_load_schema(SCHEMA), receipt) == []


def test_monitor_receipt_fails_when_evaluate_route_becomes_public() -> None:
    def widened_getter(method: str, url: str) -> HttpProbeResult:
        if method == "POST" and url.endswith("/v1/govern/evaluate"):
            return _result(200, {"status": "ok"})
        return _getter(method, url)

    receipt = collect_govern_cloud_public_route_monitor(http_getter=widened_getter, now_utc=OBSERVED_AT)
    evaluate = [item for item in receipt["route_observations"] if item["route_id"] == "blocked_evaluate"][0]

    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["proof_state"] == "Fail"
    assert receipt["summary"]["failed_route_count"] == 1
    assert receipt["remediation"]["decision"] == "rollback_public_proxy"
    assert evaluate["observed_status_code"] == 200
    assert evaluate["method"] == "POST"
    assert evaluate["passed"] is False
    assert evaluate["error"] == "unexpected_status_code"


def test_monitor_receipt_fails_when_health_contract_drifts() -> None:
    def degraded_getter(method: str, url: str) -> HttpProbeResult:
        if method == "GET" and url.endswith("/v1/health"):
            return _result(200, {"status": "degraded", "service": "mullusi-govern-cloud-staging"})
        return _getter(method, url)

    receipt = collect_govern_cloud_public_route_monitor(http_getter=degraded_getter, now_utc=OBSERVED_AT)
    health = [item for item in receipt["route_observations"] if item["route_id"] == "health"][0]

    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["public_read_routes_verified"] is False
    assert receipt["summary"]["blocked_route_guard_verified"] is True
    assert health["observed_status_code"] == 200
    assert health["observed_json_fields"]["status"] == "degraded"
    assert health["error"] == "unexpected_response_contract"


def test_monitor_cli_writes_receipt_without_raw_body(tmp_path: Path) -> None:
    output_path = tmp_path / "receipt.json"
    exit_code = main(
        ["--output", str(output_path)],
        http_getter=_getter,
        now_utc=OBSERVED_AT,
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))
    serialized = json.dumps(written)

    assert exit_code == 0
    assert written["summary"]["monitor_closed"] is True
    assert output_path.exists()
    assert "response_digest" in serialized
    assert '{"status": "ok"' not in serialized
    assert "raw_secret_values_included" in serialized
