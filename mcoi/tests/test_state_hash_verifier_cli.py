"""Purpose: verify the operator CLI state-hash verifier.
Governance scope: read-only proof verification for transition state hashes.
Dependencies: mcoi_runtime.app.cli, mcoi_runtime.core.proof_bridge.
Invariants: verifier recomputes canonical v1 hashes, rejects mismatches, and
fails closed for malformed verifier inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.cli import main
from mcoi_runtime.core.proof_bridge import state_hash


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_verify_state_hash_accepts_single_hash_record(tmp_path: Path, capsys) -> None:
    record = {
        "state": "evaluating",
        "entity_id": "request:tenant-alpha:/v1/govern",
        "timestamp": "2026-04-28T00:00:00Z",
        "state_hash": state_hash("evaluating", "request:tenant-alpha:/v1/govern", "2026-04-28T00:00:00Z"),
    }
    input_path = _write_json(tmp_path / "state_hash.json", record)

    rc = main(["verify-state-hash", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 0
    assert "OK  state hash verified" in output
    assert "FAIL" not in output


def test_verify_state_hash_accepts_transition_receipt(tmp_path: Path, capsys) -> None:
    entity_id = "request:tenant-alpha:/v1/govern"
    issued_at = "2026-04-28T00:00:00Z"
    receipt = {
        "receipt_id": "rcpt-test",
        "entity_id": entity_id,
        "from_state": "evaluating",
        "to_state": "allowed",
        "before_state_hash": state_hash("evaluating", entity_id, issued_at),
        "after_state_hash": state_hash("allowed", entity_id, issued_at),
        "issued_at": issued_at,
    }
    input_path = _write_json(tmp_path / "receipt.json", {"receipt": receipt})

    rc = main(["verify-state-hash", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 0
    assert "before_state_hash and after_state_hash match" in output
    assert "FAIL" not in output


def test_verify_state_hash_rejects_mismatch(tmp_path: Path, capsys) -> None:
    record = {
        "state": "evaluating",
        "entity_id": "request:tenant-alpha:/v1/govern",
        "timestamp": "2026-04-28T00:00:00Z",
        "state_hash": "0" * 64,
    }
    input_path = _write_json(tmp_path / "bad_state_hash.json", record)

    rc = main(["verify-state-hash", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 1
    assert "FAIL state hash verification failed" in output
    assert "field: state_hash" in output


def test_verify_state_hash_rejects_missing_fields(tmp_path: Path, capsys) -> None:
    input_path = _write_json(tmp_path / "missing_state_hash.json", {"state": "evaluating"})

    rc = main(["verify-state-hash", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 3
    assert "must be a non-empty string" in output
    assert "entity_id" in output
