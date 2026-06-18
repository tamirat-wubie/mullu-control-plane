"""Tests for personal-assistant public console probe receipt validation.

Purpose: prove public console witness receipts are schema-backed and fail
closed on boundary drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: collector and validator scripts for public console probes.
Invariants:
  - Closed receipts require route and no-effect evidence.
  - Open receipts remain valid unless closed evidence is required.
  - Secret-shaped serialized values are rejected.
"""

from __future__ import annotations

import copy
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
)
from scripts.validate_personal_assistant_public_console_probe_receipt import (  # noqa: E402
    validate_personal_assistant_public_console_probe_receipt,
    write_personal_assistant_public_console_probe_validation_report,
)


FIXED_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _console_payload() -> bytes:
    lanes = [
        {
            "lane_id": lane_id,
            "stage": "foundation",
            "state": "mounted",
            "receipt_required": True,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_effect_allowed": False,
            "customer_readiness_claim_allowed": False,
            "nested_mind_live_activation_allowed": False,
        }
        for lane_id in EXPECTED_LANE_IDS
    ]
    return json.dumps(
        {
            "console_id": "personal_assistant_console_foundation",
            "status": "foundation_read_only",
            "solver_outcome": "SolvedVerified",
            "governed": True,
            "lane_status": {
                "lane_count": len(EXPECTED_LANE_IDS),
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "connector_mutation_allowed": False,
                "external_effect_allowed": False,
                "customer_readiness_claim_allowed": False,
                "nested_mind_live_activation_allowed": False,
                "lanes": lanes,
            },
        }
    ).encode("utf-8")


def _html_body() -> bytes:
    return (
        "<html><title>Mullu Personal Assistant Console</title>"
        "<body>Foundation Lanes foundation_read_only "
        "/api/v1/console/personal-assistant Execution Allowed False</body></html>"
    ).encode("utf-8")


def _closed_receipt() -> dict[str, object]:
    def http_getter(method: str, url: str) -> HttpProbeResult:
        assert method == "GET"
        if url.endswith(JSON_ROUTE):
            return HttpProbeResult(200, {"content-type": "application/json"}, _console_payload(), True, "")
        if url.endswith(HTML_ROUTE):
            return HttpProbeResult(200, {"content-type": "text/html"}, _html_body(), True, "")
        raise AssertionError(url)

    return collect_personal_assistant_public_console_probe(http_getter=http_getter, now_utc=FIXED_NOW)


def _write_receipt(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "personal_assistant_public_console_probe.json"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return receipt_path


def test_validation_accepts_schema_valid_closed_probe(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())

    validation = validate_personal_assistant_public_console_probe_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is True
    assert validation.solver_outcome == "SolvedVerified"
    assert validation.probe_closed is True
    assert validation.observed_lane_count == len(EXPECTED_LANE_IDS)
    assert all(step.passed for step in validation.steps)


def test_validation_accepts_open_probe_without_require_closed(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["proof_state"] = "Fail"
    receipt["solver_outcome"] = "AwaitingEvidence"
    receipt["summary"]["probe_closed"] = False  # type: ignore[index]
    receipt["summary"]["html_view_verified"] = False  # type: ignore[index]
    receipt["route_observations"][1]["passed"] = False  # type: ignore[index]
    receipt["route_observations"][1]["error"] = "unexpected_response_contract"  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_public_console_probe_receipt(receipt_path=receipt_path)

    assert validation.valid is True
    assert validation.solver_outcome == "AwaitingEvidence"
    assert validation.probe_closed is False
    assert validation.observed_lane_count == len(EXPECTED_LANE_IDS)


def test_validation_require_closed_blocks_open_probe(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["proof_state"] = "Fail"
    receipt["solver_outcome"] = "AwaitingEvidence"
    receipt["summary"]["probe_closed"] = False  # type: ignore[index]
    receipt["summary"]["console_read_model_verified"] = False  # type: ignore[index]
    receipt["route_observations"][0]["passed"] = False  # type: ignore[index]
    receipt["route_observations"][0]["error"] = "unexpected_status_code"  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_public_console_probe_receipt(
        receipt_path=receipt_path,
        require_closed=True,
    )

    assert validation.valid is False
    assert validation.probe_closed is False
    assert any(step.name == "require closed" and step.passed is False for step in validation.steps)


def test_validation_rejects_secret_shaped_serialized_values(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    receipt["route_observations"][0]["observed_public_fields"]["status"] = "Bearer token"  # type: ignore[index]
    receipt_path = _write_receipt(tmp_path, receipt)

    validation = validate_personal_assistant_public_console_probe_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any(step.name == "secret boundary" and step.passed is False for step in validation.steps)
    assert validation.receipt_id.startswith("personal-assistant-public-console-probe-")


def test_validation_report_writer_outputs_bounded_summary(tmp_path: Path) -> None:
    receipt_path = _write_receipt(tmp_path, _closed_receipt())
    validation_path = tmp_path / "validation.json"
    validation = validate_personal_assistant_public_console_probe_receipt(receipt_path=receipt_path)

    write_personal_assistant_public_console_probe_validation_report(validation, validation_path)
    report = json.loads(validation_path.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["solver_outcome"] == "SolvedVerified"
    assert report["observed_lane_count"] == len(EXPECTED_LANE_IDS)
    assert report["receipt_path"] == "provided_receipt"
    assert len(report["steps"]) >= 6
