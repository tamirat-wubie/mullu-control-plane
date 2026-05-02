"""Operator capability console tests.

Purpose: verify the browser-facing operator capability surface is read-only,
bounded, and backed by governed capability records.
Governance scope: operator web UI projection only.
Dependencies: gateway server and capability fabric defaults.
Invariants:
  - Operator capability views expose governed records, not raw fabric internals.
  - JSON and HTML surfaces are guarded by the authority operator boundary.
  - Filtering and pagination are deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_fabric import build_default_capability_admission_gate  # noqa: E402
from gateway.operator_capability_console import build_operator_capability_read_model  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402


class StubPlatform:
    """Minimal platform fixture for gateway app construction."""

    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {
            "response": "ok",
            "tenant_id": tenant_id,
            "identity_id": identity_id,
        }


def _clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def test_operator_capability_read_model_projects_governed_records_only() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    read_model = build_operator_capability_read_model(
        capability_admission_gate=gate,
        domain="voice",
        risk_level="medium",
        audit_limit=2,
    )

    assert read_model["enabled"] is True
    assert read_model["capability_surface"] == "governed_capability_records"
    assert read_model["raw_tool_surface_exposed"] is False
    assert read_model["domain_filter"] == "voice"
    assert read_model["risk_level_filter"] == "medium"
    assert read_model["capability_count"] == 6
    assert read_model["domain_counts"] == {"voice": 6}
    assert read_model["sandbox_required_count"] == 6
    assert read_model["admission_audit_page"]["limit"] == 2
    assert all("extensions" not in item for item in read_model["capabilities"])
    assert all("input_schema_ref" not in item for item in read_model["capabilities"])


def test_operator_capability_endpoint_reports_default_fabric() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/capabilities/read-model?domain=browser&audit_limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["domain_filter"] == "browser"
    assert payload["capability_count"] >= 1
    assert payload["raw_tool_surface_exposed"] is False
    assert payload["admission_audit_page"]["limit"] == 1
    assert all(item["domain"] == "browser" for item in payload["capabilities"])


def test_operator_capability_html_console_is_read_only() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    client = TestClient(app)

    response = client.get("/operator/capabilities?domain=voice")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Mullu Operator Capabilities" in response.text
    assert "Governed Capability Records" in response.text
    assert "voice.intent_confirm" in response.text
    assert "Raw tools exposed: false" in response.text
