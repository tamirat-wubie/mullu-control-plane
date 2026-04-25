"""Tests for the pilot proof-slice witness script.

Purpose: verify deterministic pilot witness generation and file emission.
Governance scope: [OCE, CDCV, UWMA, PRS]
Dependencies: scripts.pilot_proof_slice and gateway closure path.
Invariants:
  - A witness is emitted only after terminal certification.
  - Proof flags are explicit and true for a successful slice.
  - Invalid input is rejected before gateway execution.
"""

from __future__ import annotations

import json

import pytest

from scripts.pilot_proof_slice import (
    PilotProofSliceConfig,
    main,
    run_pilot_proof_slice,
    write_witness,
)


def test_run_pilot_proof_slice_emits_terminal_witness() -> None:
    witness = run_pilot_proof_slice(PilotProofSliceConfig())

    assert witness["terminal_disposition"] == "committed"
    assert witness["success_claim_allowed"] is True
    assert witness["proof"]["terminal_certified"] is True
    assert witness["proof"]["response_evidence_closed"] is True
    assert witness["proof"]["memory_promoted"] is True
    assert witness["proof"]["learning_decided"] is True
    assert witness["proof"]["responded"] is True
    assert witness["event_count"] >= 8


def test_write_witness_persists_deterministic_json(tmp_path) -> None:
    witness = run_pilot_proof_slice(PilotProofSliceConfig(message_id="pilot-message-file"))
    output_path = tmp_path / "pilot_witness.json"

    written = write_witness(witness, output_path)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert loaded["witness_id"] == witness["witness_id"]
    assert loaded["command_id"] == witness["command_id"]
    assert loaded["terminal_certificate_id"] == witness["terminal_certificate_id"]
    assert loaded["latest_event_hash"] == witness["latest_event_hash"]


def test_cli_writes_witness_file(tmp_path, capsys) -> None:
    output_path = tmp_path / "cli_witness.json"

    exit_code = main(["--output", str(output_path), "--message-id", "pilot-message-cli"])
    captured = capsys.readouterr()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert "pilot proof slice witness written" in captured.out
    assert loaded["message_id"] == "pilot-message-cli"
    assert loaded["proof"]["responded"] is True


def test_config_rejects_empty_identity() -> None:
    with pytest.raises(ValueError, match="identity_id must be a non-empty string") as exc_info:
        PilotProofSliceConfig(identity_id="")

    assert str(exc_info.value) == "identity_id must be a non-empty string"
    assert exc_info.type is ValueError
    assert exc_info.match("identity_id")
