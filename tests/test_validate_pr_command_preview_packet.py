"""Tests for PR command preview packet validation.

Purpose: prove the fixture remains blocked and non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_pr_command_preview_packet.
Invariants: blocked fixture renders no external PR command text.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_pr_command_preview_packet import (
    DEFAULT_OUTPUT,
    validate_pr_command_preview_packet,
    write_pr_command_preview_packet_validation,
)


def test_pr_command_preview_packet_fixture_validates(tmp_path: Path) -> None:
    validation = validate_pr_command_preview_packet()
    written = write_pr_command_preview_packet_validation(validation, tmp_path / "validation.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.preview_status == "blocked"
    assert validation.commands_rendered is False
    assert validation.errors == ()
    assert payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "pr_command_preview_packet_validation.json"


def test_pr_command_preview_packet_rejects_executed_claim(tmp_path: Path) -> None:
    packet = json.loads(Path("examples/pr_command_preview_packet.foundation.json").read_text(encoding="utf-8"))
    packet["execution_performed"] = True
    packet["preview_only"] = False
    packet_path = tmp_path / "preview.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_pr_command_preview_packet(packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.preview_only: expected const True" in serialized_errors
    assert "$.execution_performed: expected const False" in serialized_errors
    assert "preview_only_must_be_true" in serialized_errors
    assert "execution_performed_must_be_false" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors
