"""Tests for the governed invoice/email draft-only walkthrough fixture."""

from __future__ import annotations

import copy
import json

from scripts.validate_personal_assistant_invoice_email_walkthrough import (
    DEFAULT_FIXTURE,
    validate_invoice_email_walkthrough,
)


def test_personal_assistant_invoice_email_walkthrough_fixture_is_valid() -> None:
    result = validate_invoice_email_walkthrough(DEFAULT_FIXTURE)

    assert result["valid"] is True
    assert result["error_count"] == 0
    assert result["walkthrough_id"] == "personal_assistant_invoice_email_draft_walkthrough_v1"


def test_personal_assistant_invoice_email_walkthrough_validator_rejects_effect_drift(tmp_path) -> None:  # noqa: ANN001
    payload = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    unsafe = copy.deepcopy(payload)
    unsafe["effect_boundary"]["external_send_allowed"] = True
    unsafe["draft_projection"]["provider_draft_creation_allowed"] = True
    unsafe["receipt_projection"]["actions_taken"].append("email_sent")
    path = tmp_path / "unsafe_walkthrough.json"
    path.write_text(json.dumps(unsafe), encoding="utf-8")

    result = validate_invoice_email_walkthrough(path)

    assert result["valid"] is False
    assert "effect_boundary.external_send_allowed must be false" in result["errors"]
    assert "draft_projection.provider_draft_creation_allowed must be false" in result["errors"]
    assert "receipt_projection.actions_taken must not include email_sent" in result["errors"]
