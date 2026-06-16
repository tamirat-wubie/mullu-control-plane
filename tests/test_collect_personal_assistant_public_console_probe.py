"""Tests for personal-assistant public console probe collection.

Purpose: prove deployed console evidence can be collected without mutating
deployment state or assistant authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_public_console_probe.
Invariants:
  - SolvedVerified requires JSON, HTML, and no-effect lane closure.
  - Missing or drifted route evidence preserves AwaitingEvidence.
  - Raw response bodies are not serialized into receipts.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_public_console_probe import (  # noqa: E402
    EXPECTED_LANE_IDS,
    HTML_ROUTE,
    JSON_ROUTE,
    HttpProbeResult,
    collect_personal_assistant_public_console_probe,
    main,
)


FIXED_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _console_payload(*, mutate_effect: bool = False) -> bytes:
    lanes = []
    for lane_id in EXPECTED_LANE_IDS:
        lanes.append(
            {
                "lane_id": lane_id,
                "stage": "foundation",
                "state": "mounted",
                "receipt_required": True,
                "execution_allowed": mutate_effect,
                "live_connector_execution_allowed": False,
                "connector_mutation_allowed": False,
                "external_effect_allowed": False,
                "customer_readiness_claim_allowed": False,
                "nested_mind_live_activation_allowed": False,
            }
        )
    payload = {
        "console_id": "personal_assistant_console_foundation",
        "status": "foundation_read_only",
        "solver_outcome": "SolvedVerified",
        "governed": True,
        "lane_status": {
            "lane_count": len(EXPECTED_LANE_IDS),
            "execution_allowed": mutate_effect,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_effect_allowed": False,
            "customer_readiness_claim_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "lanes": lanes,
        },
    }
    return json.dumps(payload).encode("utf-8")


def _html_body() -> bytes:
    return (
        "<html><title>Mullu Personal Assistant Console</title>"
        "<body>Foundation Lanes foundation_read_only "
        "/api/v1/console/personal-assistant Execution Allowed False</body></html>"
    ).encode("utf-8")


def test_probe_closes_when_json_html_and_no_effect_boundary_pass() -> None:
    def http_getter(method: str, url: str) -> HttpProbeResult:
        assert method == "GET"
        if url.endswith(JSON_ROUTE):
            return HttpProbeResult(200, {"content-type": "application/json"}, _console_payload(), True, "")
        if url.endswith(HTML_ROUTE):
            return HttpProbeResult(200, {"content-type": "text/html"}, _html_body(), True, "")
        raise AssertionError(url)

    receipt = collect_personal_assistant_public_console_probe(
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    summary = receipt["summary"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["console_read_model_verified"] is True
    assert summary["html_view_verified"] is True
    assert summary["no_effect_boundary_verified"] is True
    assert summary["observed_lane_count"] == len(EXPECTED_LANE_IDS)
    assert receipt["effect_boundary"]["execution_allowed"] is False  # type: ignore[index]


def test_probe_preserves_awaiting_evidence_on_json_404() -> None:
    def http_getter(method: str, url: str) -> HttpProbeResult:
        assert method == "GET"
        if url.endswith(JSON_ROUTE):
            return HttpProbeResult(404, {"content-type": "application/json"}, b'{"detail":"missing"}', True, "http_error")
        if url.endswith(HTML_ROUTE):
            return HttpProbeResult(200, {"content-type": "text/html"}, _html_body(), True, "")
        raise AssertionError(url)

    receipt = collect_personal_assistant_public_console_probe(
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    observations = {item["route_id"]: item for item in receipt["route_observations"]}  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["probe_closed"] is False  # type: ignore[index]
    assert observations["console_json"]["passed"] is False
    assert observations["console_json"]["error"] == "unexpected_status_code"


def test_probe_blocks_effect_boundary_drift_without_serializing_raw_body() -> None:
    def http_getter(method: str, url: str) -> HttpProbeResult:
        assert method == "GET"
        if url.endswith(JSON_ROUTE):
            raw_body = _console_payload(mutate_effect=True) + b" private provider token"
            return HttpProbeResult(200, {"content-type": "application/json"}, raw_body, True, "")
        if url.endswith(HTML_ROUTE):
            return HttpProbeResult(200, {"content-type": "text/html"}, _html_body(), True, "")
        raise AssertionError(url)

    receipt = collect_personal_assistant_public_console_probe(
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    serialized = json.dumps(receipt, sort_keys=True)

    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["no_effect_boundary_verified"] is False  # type: ignore[index]
    assert receipt["effect_boundary"]["raw_response_bodies_serialized"] is False  # type: ignore[index]
    assert "private provider token" not in serialized
    assert "no_effect_boundary_mismatch" in serialized


def test_probe_cli_writes_closed_receipt(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    def http_getter(method: str, url: str) -> HttpProbeResult:
        assert method == "GET"
        if url.endswith(JSON_ROUTE):
            return HttpProbeResult(200, {"content-type": "application/json"}, _console_payload(), True, "")
        if url.endswith(HTML_ROUTE):
            return HttpProbeResult(200, {"content-type": "text/html"}, _html_body(), True, "")
        raise AssertionError(url)

    output_path = tmp_path / "personal_assistant_public_console_probe.json"
    exit_code = main(
        ["--output", str(output_path), "--json"],
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["summary"]["probe_closed"] is True
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""
