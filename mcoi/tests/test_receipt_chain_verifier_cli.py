"""Purpose: verify the operator CLI receipt-chain verifier.
Governance scope: read-only proof verification for exported transition receipts.
Dependencies: mcoi_runtime.app.cli and proof/state-machine contracts.
Invariants: verifier recomputes receipt hashes, receipt ids, replay tokens, and
causal-parent linkage without mutating runtime state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

from mcoi_runtime.app.cli import main
from mcoi_runtime.contracts.proof import TransitionReceipt, certify_transition
from mcoi_runtime.contracts.state_machine import StateMachineSpec, TransitionRule


TIMESTAMP = "2026-04-28T00:00:00Z"


def _machine() -> StateMachineSpec:
    return StateMachineSpec(
        machine_id="receipt-chain-test",
        name="Receipt Chain Test",
        version="1.0.0",
        states=("pending", "running", "done"),
        initial_state="pending",
        terminal_states=("done",),
        transitions=(
            TransitionRule(from_state="pending", to_state="running", action="start"),
            TransitionRule(from_state="running", to_state="done", action="finish"),
        ),
    )


def _receipt_pair() -> tuple[TransitionReceipt, TransitionReceipt]:
    first = certify_transition(
        _machine(),
        entity_id="entity-1",
        from_state="pending",
        to_state="running",
        action="start",
        before_state_hash="before-1",
        after_state_hash="after-1",
        actor_id="tester",
        reason="start",
        causal_parent="genesis",
        timestamp=TIMESTAMP,
    ).receipt
    second = certify_transition(
        _machine(),
        entity_id="entity-1",
        from_state="running",
        to_state="done",
        action="finish",
        before_state_hash="after-1",
        after_state_hash="after-2",
        actor_id="tester",
        reason="finish",
        causal_parent=first.receipt_hash,
        timestamp=TIMESTAMP,
    ).receipt
    return first, second


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_verify_receipt_chain_accepts_json_receipts(tmp_path: Path, capsys) -> None:
    receipts = [asdict(receipt) for receipt in _receipt_pair()]
    input_path = _write_json(tmp_path / "receipts.json", {"receipts": receipts})

    rc = main(["verify-receipt-chain", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 0
    assert "OK  receipt chain verified - 2 receipts, chain intact" in output
    assert "FAIL" not in output


def test_verify_receipt_chain_accepts_jsonl_proof_capsules(tmp_path: Path, capsys) -> None:
    first, second = _receipt_pair()
    lines = [
        json.dumps({"receipt": asdict(first), "lineage_depth": 0}),
        json.dumps({"receipt": asdict(second), "lineage_depth": 1}),
    ]
    input_path = tmp_path / "receipts.jsonl"
    input_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rc = main(["verify-receipt-chain", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 0
    assert "2 receipts" in output
    assert "chain intact" in output


def test_verify_receipt_chain_rejects_hash_mismatch(tmp_path: Path, capsys) -> None:
    first, second = _receipt_pair()
    tampered = replace(second, receipt_hash="0" * 64)
    input_path = _write_json(tmp_path / "tampered.json", [asdict(first), asdict(tampered)])

    rc = main(["verify-receipt-chain", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 1
    assert "FAIL receipt chain verification failed" in output
    assert "receipt_index: 1" in output
    assert "field: receipt_hash" in output


def test_verify_receipt_chain_rejects_causal_parent_mismatch(tmp_path: Path, capsys) -> None:
    first, _second = _receipt_pair()
    independent = certify_transition(
        _machine(),
        entity_id="entity-1",
        from_state="running",
        to_state="done",
        action="finish",
        before_state_hash="after-1",
        after_state_hash="after-2",
        actor_id="tester",
        reason="finish",
        causal_parent="genesis",
        timestamp=TIMESTAMP,
    ).receipt
    input_path = _write_json(tmp_path / "bad-parent.json", [asdict(first), asdict(independent)])

    rc = main(["verify-receipt-chain", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 1
    assert "receipt_index: 1" in output
    assert "field: causal_parent" in output


def test_verify_receipt_chain_rejects_missing_fields(tmp_path: Path, capsys) -> None:
    input_path = _write_json(tmp_path / "missing.json", [{"receipt_id": "rcpt-only"}])

    rc = main(["verify-receipt-chain", str(input_path)])
    output = capsys.readouterr().out

    assert rc == 3
    assert "receipt[0] field" in output
    assert "must be a non-empty string" in output
