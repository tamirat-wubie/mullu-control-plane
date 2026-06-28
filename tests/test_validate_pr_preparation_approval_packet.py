"""Tests for PR-preparation approval packet validation.

Purpose: prove the approval packet fixture stays projection-only and cannot
grant external PR creation authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_pr_preparation_approval_packet.
Invariants: packet hash is canonical, external effects are false, and local
approval only permits local PR candidate packet preparation.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_pr_preparation_approval_packet import (
    DEFAULT_OUTPUT,
    validate_pr_preparation_approval_packet,
    write_pr_preparation_approval_packet_validation,
)


def test_pr_preparation_approval_packet_fixture_validates(tmp_path: Path) -> None:
    validation = validate_pr_preparation_approval_packet()
    output_path = tmp_path / "validation.json"

    written = write_pr_preparation_approval_packet_validation(validation, output_path)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.packet_status == "awaiting_receipts"
    assert validation.bundle_ready is False
    assert validation.errors == ()
    assert payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "pr_preparation_approval_packet_validation.json"


def test_pr_preparation_approval_packet_rejects_external_pr_creation(tmp_path: Path) -> None:
    packet = json.loads(Path("examples/pr_preparation_approval_packet.foundation.json").read_text(encoding="utf-8"))
    packet["pr_creation_allowed"] = True
    packet["external_effects_allowed"] = True
    packet["forbidden_effects"] = ["push_branch", "merge", "deploy", "call_connector"]
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_pr_preparation_approval_packet(packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.external_effects_allowed: expected const False" in serialized_errors
    assert "$.pr_creation_allowed: expected const False" in serialized_errors
    assert "missing_forbidden_effect:open_external_pr" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors
