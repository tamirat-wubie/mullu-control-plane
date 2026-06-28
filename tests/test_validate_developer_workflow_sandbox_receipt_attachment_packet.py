"""Tests for Developer Workflow sandbox receipt attachment packet validation.

Purpose: prove the attachment packet fails closed on action, status, and
evidence-source drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_developer_workflow_sandbox_receipt_attachment_packet.
Invariants:
  - No external effects.
  - Canonical receipt order.
  - Attachment state follows the sandbox receipt bundle.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_developer_workflow_sandbox_receipt_attachment_packet import (
    DEFAULT_OUTPUT,
    validate_developer_workflow_sandbox_receipt_attachment_packet,
    write_developer_workflow_sandbox_receipt_attachment_packet_validation,
)


ROOT = Path(__file__).resolve().parents[1]


def _default_packet() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_sandbox_receipt_attachment_packet.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    packet_path = tmp_path / "attachment-packet.json"
    packet_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


def test_attachment_packet_fixture_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_developer_workflow_sandbox_receipt_attachment_packet()
    output_path = tmp_path / "attachment-packet-validation.json"

    written_path = write_developer_workflow_sandbox_receipt_attachment_packet_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_status == "awaiting_attachments"
    assert validation.completed_count == 0
    assert validation.required_count == 4
    assert validation.next_attachment == "sandbox_patch_receipt"
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "developer_workflow_sandbox_receipt_attachment_packet_validation.json"


def test_attachment_packet_rejects_external_effect_overclaim(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["external_effects_allowed"] = True
    packet["execution_boundary"] = "production"

    validation = validate_developer_workflow_sandbox_receipt_attachment_packet(packet_path=_write_payload(tmp_path, packet))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effects_allowed must remain false" in serialized_errors
    assert "execution_boundary must be local_lab_only" in serialized_errors


def test_attachment_packet_rejects_action_and_order_drift(tmp_path: Path) -> None:
    packet = _default_packet()
    attachments = packet["attachments"]
    assert isinstance(attachments, list)
    attachments.reverse()
    attachments[0]["action"] = "skip evidence attachment"  # type: ignore[index]

    validation = validate_developer_workflow_sandbox_receipt_attachment_packet(packet_path=_write_payload(tmp_path, packet))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "attachments must list canonical receipt ids in order" in serialized_errors
    assert "action must match sandbox-to-PR packet" in serialized_errors


def test_attachment_packet_rejects_bundle_status_overclaim(tmp_path: Path) -> None:
    packet = _default_packet()
    first = packet["attachments"][0]  # type: ignore[index]
    first["status"] = "attached"  # type: ignore[index]
    packet["completed_count"] = 1

    validation = validate_developer_workflow_sandbox_receipt_attachment_packet(packet_path=_write_payload(tmp_path, packet))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "status must derive from sandbox bundle" in serialized_errors
