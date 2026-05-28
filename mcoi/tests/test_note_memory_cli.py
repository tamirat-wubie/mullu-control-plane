"""Tests for the governed note memory CLI.

Purpose: verify executable capture, retrieval, expiry, rejected-delta, and
promotion commands for the note memory mesh.
Governance scope: CLI envelopes must not bypass redaction, append-only
persistence, ProofState gates, or Phi_gov promotion receipts.
Dependencies: mcoi_runtime.core.note_memory_cli.
Invariants: accepted commands persist governed events, rejected commands return
nonzero status, and direct MemoryAnchor capture is blocked.
"""

from __future__ import annotations

import json

from mcoi_runtime.core.note_memory_cli import guarded_main


def _last_json(capsys) -> dict[str, object]:
    captured = capsys.readouterr()
    return json.loads(captured.out.strip().splitlines()[-1])


def test_cli_capture_retrieve_and_list_events_redacts_before_write(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    capture_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "WorkingNote",
            "--scope",
            "task",
            "--summary",
            "capture parser note with api_key=sk-cli-secret1234567890",
            "--source-ref",
            "test:cli-capture",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--expires-at",
            "2026-06-02T00:00:00+00:00",
            "--evidence-ref",
            "test_cli_capture",
        ]
    )
    capture_envelope = _last_json(capsys)
    retrieve_code = guarded_main(["--note-store", str(note_store), "retrieve", "parser", "--scope", "task"])
    retrieve_envelope = _last_json(capsys)
    list_code = guarded_main(["--note-store", str(note_store), "list-events"])
    list_envelope = _last_json(capsys)

    assert capture_code == 0
    assert capture_envelope["ok"] is True
    assert retrieve_code == 0
    assert retrieve_envelope["payload"]["count"] == 1
    assert "sk-cli-secret" not in json.dumps(retrieve_envelope)
    assert list_code == 0
    assert list_envelope["payload"]["count"] == 1
    assert "[REDACTED:" in list_envelope["payload"]["events"][0]["content_summary"]


def test_cli_blocks_direct_memory_anchor_and_records_rejected_delta(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    blocked_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "MemoryAnchor",
            "--scope",
            "repository",
            "--summary",
            "direct anchor bypass",
            "--source-ref",
            "test:direct-anchor",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--evidence-ref",
            "direct",
        ]
    )
    blocked_envelope = _last_json(capsys)
    rejected_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "record-rejected-delta",
            "--summary",
            "Rejected direct MemoryAnchor capture path",
            "--source-ref",
            "test:direct-anchor",
            "--evidence-ref",
            "blocked_direct_anchor",
        ]
    )
    rejected_envelope = _last_json(capsys)

    assert blocked_code == 1
    assert blocked_envelope["ok"] is False
    assert "promote_memory_anchor" in blocked_envelope["error"]
    assert rejected_code == 0
    assert rejected_envelope["status"] == "rejected_delta_recorded"
    assert rejected_envelope["payload"]["event"]["kind"] == "RejectedDelta"


def test_cli_queue_and_promote_memory_anchor_with_receipt(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"
    guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "WorkingNote",
            "--scope",
            "repository",
            "--summary",
            "note CLI promotion contract has focused tests",
            "--source-ref",
            "test:cli-promotion",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--expires-at",
            "2026-06-04T00:00:00+00:00",
            "--evidence-ref",
            "test_note_memory_cli.py::test_cli_queue_and_promote",
        ]
    )
    capture_envelope = _last_json(capsys)
    source_note_id = capture_envelope["payload"]["event"]["note_id"]
    source_event_seq = capture_envelope["payload"]["event"]["event_seq"]

    queue_code = guarded_main(["--note-store", str(note_store), "queue-promotion", source_note_id])
    queue_envelope = _last_json(capsys)
    receipt = {
        "promotion_id": queue_envelope["payload"]["promotion_id"],
        "source_note_id": source_note_id,
        "anchor_id": "anchor-cli-note-contract",
        "proof_state": "Pass",
        "evidence_refs": ["test_note_memory_cli.py::test_cli_queue_and_promote"],
        "contradiction_scan": "Pass",
        "phi_gov_status": "accepted",
        "accepted_at": "2026-05-01T00:05:00+00:00",
        "accepted_by": "test-governance",
        "lineage_event_seq": source_event_seq,
    }
    promote_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "promote",
            "--note-id",
            source_note_id,
            "--receipt",
            json.dumps(receipt),
        ]
    )
    promote_envelope = _last_json(capsys)

    assert queue_code == 0
    assert queue_envelope["status"] == "promotion_queued"
    assert promote_code == 0
    assert promote_envelope["payload"]["event"]["kind"] == "MemoryAnchor"
    assert promote_envelope["payload"]["receipt"]["phi_gov_status"] == "accepted"
    assert (note_store / "anchors" / "anchor-cli-note-contract.json").exists()


def test_cli_expire_and_rebuild_report_governed_receipts(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"
    guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "WorkingNote",
            "--scope",
            "task",
            "--summary",
            "short lived note",
            "--source-ref",
            "test:expire",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--expires-at",
            "2026-06-01T01:00:00+00:00",
            "--evidence-ref",
            "test_expire",
        ]
    )
    _last_json(capsys)

    expire_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "expire",
            "--now",
            "2026-06-02T00:00:00+00:00",
        ]
    )
    expire_envelope = _last_json(capsys)
    rebuild_code = guarded_main(["--note-store", str(note_store), "rebuild-index"])
    rebuild_envelope = _last_json(capsys)

    assert expire_code == 0
    assert expire_envelope["payload"]["report"]["expired_count"] == 1
    assert rebuild_code == 0
    assert rebuild_envelope["payload"]["report"]["valid_events"] == 2
    assert rebuild_envelope["payload"]["report"]["proof_state"] == "Pass"
