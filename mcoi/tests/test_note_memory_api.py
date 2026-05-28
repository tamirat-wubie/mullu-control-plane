"""Tests for the governed note memory runtime API.

Purpose: verify JSON-compatible note memory request envelopes for local service
and HTTP adapter boundaries.
Governance scope: runtime envelopes must preserve append-only persistence,
redaction, retrieval guards, rejected-delta evidence, expiry, and Phi_gov
promotion receipt checks.
Dependencies: mcoi_runtime.core.note_memory_api.
Invariants: accepted requests persist governed events, invalid requests fail
closed, and retrieval does not mutate lineage.
"""

from __future__ import annotations

from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime


def _working_note(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "kind": "WorkingNote",
        "scope": "task",
        "content_summary": "runtime parser note with api_key=sk-runtime-secret123456",
        "source_ref": "test:runtime",
        "proof_state": "Pass",
        "trust_zone": "workspace",
        "expires_at": "2026-06-02T00:00:00+00:00",
        "evidence_refs": ["test_note_memory_api"],
    }
    value.update(overrides)
    return value


def test_runtime_capture_retrieve_and_list_events_preserve_governed_envelopes(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    captured = runtime.capture_note(_working_note()).to_dict()
    retrieved = runtime.retrieve_notes({"query": "parser", "scope": "task"}).to_dict()
    listed = runtime.list_events().to_dict()

    assert captured["governed"] is True
    assert captured["ok"] is True
    assert captured["status"] == "captured"
    assert "sk-runtime-secret" not in captured["payload"]["event"]["content_summary"]
    assert retrieved["payload"]["count"] == 1
    assert listed["payload"]["count"] == 1
    assert listed["payload"]["events"][0]["note_id"] == captured["payload"]["event"]["note_id"]


def test_runtime_rejects_invalid_capture_without_persisting(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.capture_note(_working_note(kind="MemoryAnchor")).to_dict()
    listed = runtime.list_events().to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "promote_memory_anchor" in rejected["error"]
    assert listed["payload"]["count"] == 0


def test_runtime_rejected_delta_expiry_and_rebuild_emit_receipts(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    runtime.capture_note(_working_note(expires_at="2026-06-01T00:00:00+00:00"))

    rejected_delta = runtime.record_rejected_delta(
        {
            "summary": "Rejected unsafe note promotion",
            "source_ref": "test:rejected",
            "evidence_refs": ["blocked"],
        }
    ).to_dict()
    expired = runtime.expire_temporary_notes({"now": "2026-06-02T00:00:00+00:00"}).to_dict()
    rebuilt = runtime.rebuild_index().to_dict()

    assert rejected_delta["ok"] is True
    assert rejected_delta["payload"]["event"]["kind"] == "RejectedDelta"
    assert expired["payload"]["report"]["expired_count"] == 1
    assert rebuilt["payload"]["report"]["proof_state"] == "Pass"
    assert rebuilt["payload"]["report"]["valid_events"] == 3


def test_runtime_queue_and_promote_memory_anchor_with_receipt(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    captured = runtime.capture_note(_working_note(scope="repository")).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    source_event_seq = captured["payload"]["event"]["event_seq"]

    queued = runtime.queue_promotion({"note_id": source_note_id}).to_dict()
    promoted = runtime.promote_memory_anchor(
        {
            "note_id": source_note_id,
            "receipt": {
                "promotion_id": queued["payload"]["promotion_id"],
                "source_note_id": source_note_id,
                "anchor_id": "anchor-runtime-note-contract",
                "proof_state": "Pass",
                "evidence_refs": ["test_note_memory_api"],
                "contradiction_scan": "Pass",
                "phi_gov_status": "accepted",
                "accepted_at": "2026-05-27T00:05:00+00:00",
                "accepted_by": "test-governance",
                "lineage_event_seq": source_event_seq,
            },
        }
    ).to_dict()

    assert queued["status"] == "promotion_queued"
    assert promoted["ok"] is True
    assert promoted["payload"]["event"]["kind"] == "MemoryAnchor"
    assert (tmp_path / "notes" / "anchors" / "anchor-runtime-note-contract.json").exists()
