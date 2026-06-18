"""Tests for personal-assistant console read-model validation.

Purpose: prove the console contract is schema-backed, fail-closed, and unable
to serialize execution authority, readiness overclaims, raw payloads, or secret
values.
Governance scope: console read-model schema, no-effect assurance, private
payload redaction, and Foundation Mode readiness boundaries.
Dependencies: scripts.validate_personal_assistant_console_read_model.
Invariants:
  - Console validation covers the example fixture and runtime projection.
  - Execution, live connector, send, memory write, and Nested Mind authority
    remain false.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_console_read_model import (
    DEFAULT_READ_MODEL,
    validate_personal_assistant_console_read_model,
)


def test_personal_assistant_console_read_model_fixture_validates() -> None:
    result = validate_personal_assistant_console_read_model()

    assert result.valid is True
    assert result.read_model_path == "examples/personal_assistant_console_read_model.json"
    assert result.runtime_validated is True
    assert result.assurance_outcome == "SolvedVerified"
    assert result.errors == ()


def test_personal_assistant_console_fixture_binds_rehearsal_receipt_viewer() -> None:
    payload = _load_fixture()
    viewer_binding = payload["receipts"]["viewer_binding"]
    receipt_item = payload["receipts"]["items"][0]
    lane_status = payload["lane_status"]

    assert payload["sections"]["receipts"]["item_count"] == 1
    assert payload["receipts"]["receipt_count"] == 1
    assert viewer_binding["read_only_worker_rehearsal_bound"] is True
    assert viewer_binding["runtime_dispatch_allowed"] is False
    assert viewer_binding["terminal_closure_allowed"] is False
    assert receipt_item["receipt_kind"] == "read_only_worker_rehearsal_receipt"
    assert receipt_item["source_receipt_ref"] == "examples/read_only_worker_rehearsal_receipt.foundation.json"
    assert receipt_item["dispatch_admitted"] is False
    assert receipt_item["success_claim_allowed"] is False
    assert receipt_item["output_digest"].startswith("sha256:")
    assert "read-only-worker-rehearsal-receipt-foundation-repo-inspection-20260614" in payload["receipt_refs"]
    assert payload["sections"]["lane_status"]["item_count"] == lane_status["lane_count"]
    assert lane_status["lane_count"] == 12
    assert lane_status["runtime_preview_lane_count"] == 7
    assert lane_status["read_model_lane_count"] == 2
    assert lane_status["projection_only_lane_count"] == 3
    assert lane_status["execution_allowed"] is False
    assert lane_status["live_connector_execution_allowed"] is False
    assert lane_status["customer_readiness_claim_allowed"] is False
    assert lane_status["lanes"][5]["lane_id"] == "draft_projection"
    assert lane_status["lanes"][5]["route_refs"] == [
        "/api/v1/personal-assistant/drafts",
        "/api/v1/personal-assistant/drafts/email/preview",
        "/api/v1/personal-assistant/drafts/calendar/preview",
        "/api/v1/personal-assistant/drafts/task/preview",
    ]
    assert lane_status["lanes"][-1]["lane_id"] == "operator_console"
    assert lane_status["lanes"][-1]["route_refs"] == [
        "/api/v1/console/personal-assistant",
        "/api/v1/console/personal-assistant/view",
        "/api/v1/console/personal-assistant/readiness",
    ]
    assert lane_status["lanes"][6]["lane_id"] == "teamops_shared_inbox"
    assert (
        "/api/v1/personal-assistant/teamops/gmail/live-probe/readiness"
        in lane_status["lanes"][6]["route_refs"]
    )


def test_personal_assistant_console_validator_rejects_execution_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["execution_allowed"] = True
    payload["approval_queue"]["external_send_allowed"] = True
    payload["approval_queue"]["metadata"]["approval_decision_executes_action"] = True
    candidate = tmp_path / "unsafe_console.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_console_read_model(read_model_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "effect_boundary.execution_allowed must be false" in result.errors
    assert "approval_queue.external_send_allowed must be false" in result.errors
    assert "approval_queue.metadata.approval_decision_executes_action must be false" in result.errors
    assert result.runtime_validated is False


def test_personal_assistant_console_validator_rejects_receipt_viewer_authority_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["receipts"]["viewer_binding"]["runtime_dispatch_allowed"] = True
    payload["receipts"]["viewer_binding"]["projected_receipt_ids"] = ["forged-receipt"]
    payload["receipts"]["items"][0]["terminal_closure_allowed"] = True
    payload["receipts"]["items"][0]["source_receipt_ref"] = "examples/forged.json"
    candidate = tmp_path / "unsafe_receipt_viewer_console.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_console_read_model(read_model_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "receipts.viewer_binding.runtime_dispatch_allowed must be false" in result.errors
    assert "receipts.viewer_binding.projected_receipt_ids must match receipt item ids" in result.errors
    assert "receipts.items[0].terminal_closure_allowed must be false" in result.errors
    assert "receipts.items[0].source_receipt_ref must be examples/read_only_worker_rehearsal_receipt.foundation.json" in result.errors


def test_personal_assistant_console_validator_rejects_memory_and_readiness_overclaim(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["memory"]["live_memory_write_allowed"] = True
    payload["memory"]["metadata"]["nested_mind_live_activation_allowed"] = True
    payload["assurance"]["ready_for_customer_readiness_claim"] = True
    candidate = tmp_path / "unsafe_memory_console.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_console_read_model(read_model_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "memory.live_memory_write_allowed must be false" in result.errors
    assert "memory.metadata.nested_mind_live_activation_allowed must be false" in result.errors
    assert "assurance.ready_for_customer_readiness_claim must be false" in result.errors
    assert result.assurance_outcome == "SolvedVerified"


def test_personal_assistant_console_validator_rejects_lane_authority_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["lane_status"]["execution_allowed"] = True
    payload["lane_status"]["lanes"][0]["live_connector_execution_allowed"] = True
    payload["lane_status"]["lanes"][0]["schema_refs"] = []
    payload["lane_status"]["lanes"][6]["route_refs"] = []
    payload["sections"]["lane_status"]["item_count"] = 1
    candidate = tmp_path / "unsafe_lane_console.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_console_read_model(read_model_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "lane_status.execution_allowed must be false" in result.errors
    assert "lane_status.lanes[0].live_connector_execution_allowed must be false" in result.errors
    assert "lane_status.lanes[0].schema_refs must be a non-empty list" in result.errors
    assert "lane_status.lanes[6].route_refs must be non-empty for runtime preview lanes" in result.errors
    assert "sections.lane_status.item_count must match lane count" in result.errors


def test_personal_assistant_console_validator_rejects_raw_payload_and_secret(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["chat"]["recent_requests"] = [
        {
            "request_id": "pa_request_console_raw_001",
            "raw_connector_payload": "private transcript",
            "summary": "rotate Bearer secret-worker-token",
        }
    ]
    candidate = tmp_path / "raw_console.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_personal_assistant_console_read_model(read_model_path=candidate, validate_runtime=False)

    assert result.valid is False
    assert "$.chat.recent_requests[0].raw_connector_payload: raw private or secret field is forbidden" in result.errors
    assert "$.chat.recent_requests[0].summary: secret-like value must not be serialized" in result.errors
    assert result.runtime_validated is False


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_READ_MODEL.read_text(encoding="utf-8")))
