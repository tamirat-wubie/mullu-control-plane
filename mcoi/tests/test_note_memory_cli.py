"""Tests for the governed note memory CLI.

Purpose: verify executable capture, episode-capsule capture, retrieval, expiry,
rejected-delta, contradiction, and promotion commands for the note memory mesh.
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


def test_cli_capture_retrieve_dashboard_and_list_events_redacts_before_write(tmp_path, capsys) -> None:
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
    decision_capture_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "DecisionRecord",
            "--scope",
            "task",
            "--summary",
            "CLI decision cites parser retrieval receipt",
            "--source-ref",
            "test:cli-decision",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--evidence-ref",
            "test_cli_capture",
            "--retrieval-receipt-ref",
            retrieve_envelope["payload"]["receipt"]["receipt_id"],
        ]
    )
    decision_capture_envelope = _last_json(capsys)
    dashboard_code = guarded_main(["--note-store", str(note_store), "dashboard", "--limit", "5"])
    dashboard_envelope = _last_json(capsys)
    list_code = guarded_main(["--note-store", str(note_store), "list-events"])
    list_envelope = _last_json(capsys)

    assert capture_code == 0
    assert capture_envelope["ok"] is True
    assert retrieve_code == 0
    assert retrieve_envelope["payload"]["count"] == 1
    assert retrieve_envelope["payload"]["receipt"]["receipt_id"].startswith("note-retrieval-")
    assert len(retrieve_envelope["payload"]["receipt"]["snapshot_hash"]) == 64
    assert retrieve_envelope["payload"]["receipt"]["returned_count"] == 1
    assert "sk-cli-secret" not in json.dumps(retrieve_envelope)
    assert decision_capture_code == 0
    assert decision_capture_envelope["payload"]["event"]["retrieval_receipt_refs"] == [
        retrieve_envelope["payload"]["receipt"]["receipt_id"]
    ]
    assert dashboard_code == 0
    assert dashboard_envelope["status"] == "dashboard_snapshot"
    assert dashboard_envelope["payload"]["snapshot_id"].startswith("note-memory-dashboard-")
    assert len(dashboard_envelope["payload"]["snapshot_hash"]) == 64
    assert dashboard_envelope["payload"]["summary"]["event_count"] == 2
    assert dashboard_envelope["payload"]["filters"]["retrieval_receipt_ref"] == ""
    assert dashboard_envelope["payload"]["summary"]["retrieval_influence_count"] == 1
    assert dashboard_envelope["payload"]["recent_notes"][0]["note_id"] == decision_capture_envelope["payload"]["event"]["note_id"]
    assert dashboard_envelope["payload"]["recent_notes"][0]["retrieval_receipt_refs"] == [
        retrieve_envelope["payload"]["receipt"]["receipt_id"]
    ]
    assert dashboard_envelope["payload"]["retrieval_influence"][0]["citing_note_id"] == decision_capture_envelope[
        "payload"
    ]["event"]["note_id"]
    assert list_code == 0
    assert list_envelope["payload"]["count"] == 2
    assert "[REDACTED:" in list_envelope["payload"]["events"][0]["content_summary"]
    assert list_envelope["payload"]["events"][1]["retrieval_receipt_refs"] == [
        retrieve_envelope["payload"]["receipt"]["receipt_id"]
    ]

    filtered_dashboard_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "dashboard",
            "--limit",
            "5",
            "--retrieval-receipt-ref",
            retrieve_envelope["payload"]["receipt"]["receipt_id"],
        ]
    )
    filtered_dashboard_envelope = _last_json(capsys)
    assert filtered_dashboard_code == 0
    assert (
        filtered_dashboard_envelope["payload"]["filters"]["retrieval_receipt_ref"]
        == retrieve_envelope["payload"]["receipt"]["receipt_id"]
    )
    assert filtered_dashboard_envelope["payload"]["summary"]["retrieval_influence_count"] == 1
    assert filtered_dashboard_envelope["payload"]["retrieval_influence"][0]["citing_note_id"] == decision_capture_envelope[
        "payload"
    ]["event"]["note_id"]


def test_cli_dashboard_rejects_unbounded_limit(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    dashboard_code = guarded_main(["--note-store", str(note_store), "dashboard", "--limit", "101"])
    dashboard_envelope = _last_json(capsys)

    assert dashboard_code == 1
    assert dashboard_envelope["ok"] is False
    assert dashboard_envelope["status"] == "rejected"
    assert "dashboard limit" in dashboard_envelope["error"]


def test_cli_dashboard_rejects_malformed_retrieval_influence_filter(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    dashboard_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "dashboard",
            "--retrieval-receipt-ref",
            "manual-note-ref",
        ]
    )
    dashboard_envelope = _last_json(capsys)

    assert dashboard_code == 1
    assert dashboard_envelope["ok"] is False
    assert dashboard_envelope["status"] == "rejected"
    assert "retrieval_receipt_ref must reference a note retrieval receipt" in dashboard_envelope["error"]


def test_cli_rejects_malformed_retrieval_receipt_ref(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    capture_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "DecisionRecord",
            "--scope",
            "task",
            "--summary",
            "CLI decision rejects arbitrary retrieval refs",
            "--source-ref",
            "test:cli-bad-retrieval-ref",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--evidence-ref",
            "test_cli_rejects_malformed_retrieval_receipt_ref",
            "--retrieval-receipt-ref",
            "manual-note-ref",
        ]
    )
    capture_envelope = _last_json(capsys)
    list_code = guarded_main(["--note-store", str(note_store), "list-events"])
    list_envelope = _last_json(capsys)

    assert capture_code == 1
    assert capture_envelope["status"] == "rejected"
    assert "retrieval_receipt_ref must reference a note retrieval receipt" in capture_envelope["error"]
    assert list_code == 0
    assert list_envelope["payload"]["count"] == 0


def test_cli_claim_contradiction_records_decision_evidence(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    first_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "DecisionRecord",
            "--scope",
            "repository",
            "--summary",
            "note memory console disabled",
            "--source-ref",
            "test:cli-claim-prior",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--evidence-ref",
            "prior-claim",
            "--claim-key",
            "note_memory.console.state",
            "--claim-value",
            "disabled",
        ]
    )
    first_envelope = _last_json(capsys)
    second_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture",
            "--kind",
            "DecisionRecord",
            "--scope",
            "repository",
            "--summary",
            "note memory console mounted",
            "--source-ref",
            "test:cli-claim-current",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--evidence-ref",
            "current-claim",
            "--claim-key",
            "note_memory.console.state",
            "--claim-value",
            "mounted",
        ]
    )
    second_envelope = _last_json(capsys)
    list_code = guarded_main(["--note-store", str(note_store), "list-events"])
    list_envelope = _last_json(capsys)

    assert first_code == 0
    assert second_code == 0
    assert first_envelope["payload"]["event"]["claim_value"] == "disabled"
    assert second_envelope["payload"]["event"]["claim_value"] == "mounted"
    assert list_code == 0
    assert list_envelope["payload"]["count"] == 3
    contradiction = list_envelope["payload"]["events"][2]
    assert contradiction["action"] == "contradict"
    assert contradiction["claim_key"] == "note_memory.console.state"
    assert contradiction["relation_refs"] == [first_envelope["payload"]["event"]["event_id"]]


def test_cli_capture_episode_writes_structured_sidecar(tmp_path, capsys) -> None:
    note_store = tmp_path / "notes"

    capture_code = guarded_main(
        [
            "--note-store",
            str(note_store),
            "capture-episode",
            "--episode-id",
            "episode-cli-note-memory",
            "--goal",
            "Close governed note memory CLI capsule support",
            "--scope",
            "repository",
            "--proof-state",
            "Pass",
            "--trust-zone",
            "workspace",
            "--constraint",
            "Append-only event lineage remains intact",
            "--decision",
            "Expose capture-episode as a dedicated CLI command",
            "--changed-file",
            "mcoi/mcoi_runtime/core/note_memory_cli.py",
            "--verification-ref",
            "python -m pytest mcoi/tests/test_note_memory_cli.py",
            "--evidence-ref",
            "test_cli_capture_episode_writes_structured_sidecar",
        ]
    )
    capture_envelope = _last_json(capsys)

    capsule_path = note_store / "episodes" / "episode-cli-note-memory.json"
    capsule = json.loads(capsule_path.read_text(encoding="utf-8"))

    assert capture_code == 0
    assert capture_envelope["status"] == "episode_capsule_captured"
    assert capture_envelope["payload"]["event"]["kind"] == "EpisodeCapsule"
    assert capsule["episode_id"] == "episode-cli-note-memory"
    assert capsule["event_id"] == capture_envelope["payload"]["event"]["event_id"]
    assert capsule["verification_refs"] == ["python -m pytest mcoi/tests/test_note_memory_cli.py"]


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
