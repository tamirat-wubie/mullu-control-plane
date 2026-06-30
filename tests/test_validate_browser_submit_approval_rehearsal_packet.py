"""Purpose: verify browser.submit approval rehearsal validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_browser_submit_approval_rehearsal_packet.
Invariants:
  - Browser submit rehearsal remains no-effect.
  - Raw browser target, form, session, and secret values are rejected.
  - Ready rehearsal requires approved decision carry-forward and digest refs.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import validate_browser_submit_approval_rehearsal_packet as validator


def _foundation_packet() -> dict[str, object]:
    return json.loads(validator.DEFAULT_PACKET.read_text(encoding="utf-8"))


def test_browser_submit_approval_rehearsal_packet_passes() -> None:
    validation = validator.validate_browser_submit_approval_rehearsal_packet(require_ready=True)
    packet = _foundation_packet()

    assert validation.valid is True
    assert validation.ready is True
    assert validation.errors == ()
    assert packet["capability_id"] == "browser.submit"
    assert packet["workflow_id"] == "browser.submit.with_approval"
    assert packet["form_submit_performed"] is False
    assert packet["external_write_performed"] is False
    assert packet["requires_separate_submit_execution_receipt"] is True


def test_browser_submit_approval_rehearsal_rejects_effect_drift() -> None:
    packet = _foundation_packet()
    for field_name in validator.FALSE_EFFECT_FIELDS:
        packet[field_name] = True

    errors: list[str] = []
    validator._validate_semantics(packet, errors)

    assert any("form_submit_performed must be false" in error for error in errors)
    assert any("navigation_performed must be false" in error for error in errors)
    assert any("external_write_performed must be false" in error for error in errors)
    assert any("raw_form_payload_serialized must be false" in error for error in errors)
    assert any("secret_value_serialized must be false" in error for error in errors)


def test_browser_submit_approval_rehearsal_rejects_raw_fields() -> None:
    packet = _foundation_packet()
    packet.update(
        {
            "url": "https://private.example.invalid/form",
            "selector": "#private-form",
            "raw_form_payload": {"secret": "not-public"},
            "field_value": "secret-value",
            "cookie": "session=private",
        }
    )

    errors: list[str] = []
    validator._validate_semantics(packet, errors)

    assert any("packet must not serialize raw field: url" in error for error in errors)
    assert any("packet must not serialize raw field: selector" in error for error in errors)
    assert any("packet must not serialize raw field: raw_form_payload" in error for error in errors)
    assert any("packet must not serialize raw field: field_value" in error for error in errors)
    assert any("packet must not serialize raw field: cookie" in error for error in errors)


def test_browser_submit_approval_rehearsal_rejects_bad_hash_and_refs() -> None:
    packet = _foundation_packet()
    packet["source_url_hash"] = "https://private.example.invalid/form"
    packet["target_selector_hash"] = "not-a-hash"
    packet["form_payload_hash"] = ""
    packet["source_browser_observation_ref"] = "examples/other.json"
    packet["evidence_refs"] = ["rehearsal://browser-submit/approval-rehearsal/20260630-001"]

    errors: list[str] = []
    validator._validate_semantics(packet, errors)

    assert any("source_url_hash must be sha256 hex" in error for error in errors)
    assert any("target_selector_hash must be sha256 hex" in error for error in errors)
    assert any("form_payload_hash must be sha256 hex" in error for error in errors)
    assert any("source_browser_observation_ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_browser_submit_approval_rehearsal_rejects_unready_status_drift() -> None:
    packet = _foundation_packet()
    packet["approval_decision_ready"] = False
    packet["decision"] = "pending"
    packet["browser_submit_ready"] = False
    packet["blocked_until"] = ["approval_decision_ready"]

    errors: list[str] = []
    validator._validate_semantics(packet, errors)

    assert any("passed packet requires ready approval decision evidence" in error for error in errors)
    assert any("passed packet requires approved decision" in error for error in errors)
    assert any("passed packet requires browser_submit_ready=true" in error for error in errors)
    assert any("passed packet must not carry blockers" in error for error in errors)


def test_browser_submit_approval_rehearsal_cli_json(capsys) -> None:
    exit_code = validator.main(["--require-ready", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["ready"] is True
    assert payload["packet_path"] == "examples/browser_submit_approval_rehearsal_packet.foundation.json"
    assert payload["schema_path"] == "schemas/browser_submit_approval_rehearsal_packet.schema.json"
    assert payload["errors"] == []


def test_browser_submit_approval_rehearsal_blocked_packet_shape() -> None:
    packet = deepcopy(_foundation_packet())
    packet["status"] = "blocked"
    packet["solver_outcome"] = "AwaitingEvidence"
    packet["proof_state"] = "Unknown"
    packet["approval_decision_ready"] = False
    packet["approval_decision_valid"] = False
    packet["decision"] = "pending"
    packet["browser_submit_ready"] = False
    packet["browser_submit_authorized_by_decision"] = False
    packet["blocked_until"] = ["approval_decision_ready"]

    errors: list[str] = []
    validator._validate_semantics(packet, errors)

    assert errors == []
    assert validator._packet_ready(packet) is False


def test_browser_submit_approval_rehearsal_schema_rejects_extra_property(tmp_path: Path) -> None:
    packet = _foundation_packet()
    packet["raw_url"] = "https://private.example.invalid/form"
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validator.validate_browser_submit_approval_rehearsal_packet(packet_path=packet_path)

    assert validation.valid is False
    assert any("additionalProperties" in error or "raw field: raw_url" in error for error in validation.errors)
