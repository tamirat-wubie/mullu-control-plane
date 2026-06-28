"""Tests for local PR candidate packet validation.

Purpose: prove the fixture remains local-only and hash checked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_local_pr_candidate_packet.
Invariants: PR creation, branch push, and external effects stay blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_local_pr_candidate_packet import (
    DEFAULT_OUTPUT,
    validate_local_pr_candidate_packet,
    write_local_pr_candidate_packet_validation,
)


def test_local_pr_candidate_packet_fixture_validates(tmp_path: Path) -> None:
    validation = validate_local_pr_candidate_packet()
    written = write_local_pr_candidate_packet_validation(validation, tmp_path / "validation.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.candidate_status == "awaiting_receipts"
    assert validation.candidate_ready is False
    assert validation.errors == ()
    assert payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "local_pr_candidate_packet_validation.json"


def test_local_pr_candidate_packet_rejects_external_overclaim(tmp_path: Path) -> None:
    packet = json.loads(Path("examples/local_pr_candidate_packet.foundation.json").read_text(encoding="utf-8"))
    packet["external_effects_allowed"] = True
    packet["pr_creation_allowed"] = True
    packet["branch_push_allowed"] = True
    packet["forbidden_effects"] = ["merge", "deploy", "call_connector"]
    packet_path = tmp_path / "candidate.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_local_pr_candidate_packet(packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.external_effects_allowed: expected const False" in serialized_errors
    assert "$.pr_creation_allowed: expected const False" in serialized_errors
    assert "$.branch_push_allowed: expected const False" in serialized_errors
    assert "missing_forbidden_effect:open_external_pr" in serialized_errors
    assert "packet_hash_mismatch" in serialized_errors
