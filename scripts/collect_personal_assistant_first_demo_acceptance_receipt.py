#!/usr/bin/env python3
"""Collect a fixture-backed acceptance receipt for the first usable demo console.

Purpose: prove the Personal Assistant first demo is visible in both the JSON
console route and the HTML console view while all effect boundaries stay false.
Governance scope: local TestClient route projection only; no live connector,
provider draft creation, email send, invoice payment, memory write, deployment
mutation, or customer-readiness claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi.testclient import TestClient

from gateway.server import create_gateway_app

_GENERATED_AT = "2026-06-22T00:00:00Z"
_REQUIRED_FALSE_EFFECT_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_send_allowed",
    "money_movement_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
)
_REQUIRED_FALSE_WALKTHROUGH_FIELDS = (
    "execution_allowed",
    "external_send_allowed",
    "provider_draft_creation_allowed",
    "invoice_payment_allowed",
    "money_movement_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
)
_REQUIRED_ACTIONS_NOT_TAKEN = (
    "email_not_sent",
    "provider_draft_not_created",
    "connector_state_not_mutated",
    "invoice_not_paid",
    "memory_not_written",
    "deployment_not_mutated",
    "customer_readiness_not_claimed",
)
_REQUIRED_HTML_MARKERS = (
    "Invoice Email Draft Walkthrough",
    "personal_assistant_invoice_email_draft_walkthrough_v1",
    "Draft Status",
    "draft_preview_only",
    "Approval Required Before Send",
    "Provider Draft Creation Allowed",
    "Invoice Payment Allowed",
    "Customer Readiness Claim Allowed",
)


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):  # noqa: ANN001
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):  # noqa: ANN001
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def collect_first_demo_acceptance_receipt(*, generated_at: str = _GENERATED_AT) -> dict[str, Any]:
    """Return a deterministic acceptance receipt for the first demo console."""

    client = TestClient(create_gateway_app(platform=StubPlatform()), raise_server_exceptions=False)
    json_response = client.get("/api/v1/console/personal-assistant")
    html_response = client.get("/api/v1/console/personal-assistant/view")
    json_post_response = client.post("/api/v1/console/personal-assistant", json={})
    html_post_response = client.post("/api/v1/console/personal-assistant/view", json={})

    json_status = json_response.status_code
    html_status = html_response.status_code
    json_post_status = json_post_response.status_code
    html_post_status = html_post_response.status_code
    payload = json_response.json() if json_status == 200 else {}
    html = html_response.text if html_status == 200 else ""

    first_demo = _mapping(payload.get("first_usable_demo"))
    walkthrough = _mapping(first_demo.get("invoice_email_walkthrough"))
    effect_boundary = _mapping(first_demo.get("effect_boundary"))
    walkthrough_effect = _mapping(walkthrough.get("effect_summary"))
    walkthrough_claims = _mapping(walkthrough.get("claim_summary"))
    actions_not_taken = tuple(str(item) for item in walkthrough.get("actions_not_taken", ()) if isinstance(item, str))

    missing_false_effects = [field for field in _REQUIRED_FALSE_EFFECT_FIELDS if effect_boundary.get(field) is not False]
    missing_false_walkthrough = [
        field for field in _REQUIRED_FALSE_WALKTHROUGH_FIELDS if walkthrough_effect.get(field) is not False
    ]
    missing_actions_not_taken = sorted(set(_REQUIRED_ACTIONS_NOT_TAKEN) - set(actions_not_taken))
    missing_html_markers = [marker for marker in _REQUIRED_HTML_MARKERS if marker not in html]
    secret_or_private_leak_detected = any(
        marker in json.dumps(payload, sort_keys=True) or marker in html
        for marker in (
            "secret-worker-token",
            "raw_private_connector_payload",
            "provider_access_token",
            "mailbox_body",
        )
    )

    checks = {
        "json_route_status_ok": json_status == 200,
        "html_route_status_ok": html_status == 200,
        "json_route_read_only": json_post_status == 405,
        "html_route_read_only": html_post_status == 405,
        "first_demo_visible": first_demo.get("read_model_id") == "first_usable_demo_operator_read_model_v1",
        "invoice_walkthrough_visible": walkthrough.get("walkthrough_id")
        == "personal_assistant_invoice_email_draft_walkthrough_v1",
        "html_panel_visible": not missing_html_markers,
        "first_demo_effects_false": not missing_false_effects,
        "invoice_walkthrough_effects_false": not missing_false_walkthrough,
        "approval_required_before_send": walkthrough.get("approval_required_before_send") is True,
        "approval_is_not_execution": walkthrough.get("approval_is_execution") is False,
        "draft_preview_not_send_authority": walkthrough_claims.get("draft_preview_is_send_authority") is False,
        "actions_not_taken_recorded": not missing_actions_not_taken,
        "secret_or_private_leak_absent": not secret_or_private_leak_detected,
        "customer_readiness_claim_absent": walkthrough_effect.get("customer_readiness_claim_allowed") is False,
    }
    status = "passed" if all(checks.values()) else "failed"
    return {
        "receipt_id": "personal_assistant_first_demo_acceptance_receipt_v1",
        "receipt_kind": "first_demo_acceptance_receipt",
        "generated_at": generated_at,
        "status": status,
        "governed": True,
        "fixture_backed": True,
        "read_only": True,
        "route_refs": [
            "/api/v1/console/personal-assistant",
            "/api/v1/console/personal-assistant/view",
        ],
        "source_refs": [
            "examples/first_usable_demo_packet.json",
            "examples/personal_assistant_invoice_email_walkthrough.json",
            "mcoi/mcoi_runtime/personal_assistant/console_first_demo.py",
            "mcoi/mcoi_runtime/personal_assistant/console_first_demo_html.py",
        ],
        "checks": checks,
        "observed": {
            "json_status": json_status,
            "html_status": html_status,
            "json_post_status": json_post_status,
            "html_post_status": html_post_status,
            "first_demo_read_model_id": str(first_demo.get("read_model_id", "")),
            "invoice_walkthrough_id": str(walkthrough.get("walkthrough_id", "")),
            "html_panel_title": "Invoice Email Draft Walkthrough" if "Invoice Email Draft Walkthrough" in html else "",
            "html_error_excerpt": html[:240] if html_status != 200 else "",
            "actions_not_taken": sorted(actions_not_taken),
        },
        "missing": {
            "false_first_demo_effect_fields": missing_false_effects,
            "false_invoice_walkthrough_effect_fields": missing_false_walkthrough,
            "actions_not_taken": missing_actions_not_taken,
            "html_markers": missing_html_markers,
        },
        "effect_boundary": {
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "provider_draft_creation_allowed": False,
            "invoice_payment_allowed": False,
            "money_movement_allowed": False,
            "memory_write_allowed": False,
            "deployment_mutation_allowed": False,
            "customer_readiness_claim_allowed": False,
        },
        "actions_not_taken": list(_REQUIRED_ACTIONS_NOT_TAKEN),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print the receipt as JSON.")
    args = parser.parse_args()

    receipt = collect_first_demo_acceptance_receipt()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json or not args.output:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "passed" else 1


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
