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

    captured = runtime.capture_note(
        _working_note(claim_key="runtime.parser.state", claim_value="ready")
    ).to_dict()
    retrieved = runtime.retrieve_notes({"query": "parser", "scope": "task"}).to_dict()
    decision = runtime.capture_note(
        _working_note(
            kind="DecisionRecord",
            content_summary="runtime decision cites the parser retrieval receipt",
            source_ref="test:runtime-decision",
            expires_at=None,
            retrieval_receipt_refs=[retrieved["payload"]["receipt"]["receipt_id"]],
        )
    ).to_dict()
    listed = runtime.list_events().to_dict()
    snapshot = runtime.dashboard_snapshot({"limit": 5, "now": "2026-05-28T00:00:00+00:00"}).to_dict()
    filtered_snapshot = runtime.dashboard_snapshot(
        {
            "limit": 5,
            "retrieval_receipt_ref": retrieved["payload"]["receipt"]["receipt_id"],
        }
    ).to_dict()
    citing_note_snapshot = runtime.dashboard_snapshot(
        {
            "limit": 5,
            "retrieval_citing_note_ref": decision["payload"]["event"]["note_id"],
        }
    ).to_dict()

    assert captured["governed"] is True
    assert captured["ok"] is True
    assert captured["status"] == "captured"
    assert "sk-runtime-secret" not in captured["payload"]["event"]["content_summary"]
    assert retrieved["payload"]["count"] == 1
    assert retrieved["payload"]["receipt"]["receipt_id"].startswith("note-retrieval-")
    assert len(retrieved["payload"]["receipt"]["snapshot_hash"]) == 64
    assert retrieved["payload"]["receipt"]["query_terms"] == ["parser"]
    assert retrieved["payload"]["receipt"]["returned_count"] == 1
    assert retrieved["payload"]["receipt"]["returned_note_ids"] == [captured["payload"]["event"]["note_id"]]
    assert decision["payload"]["event"]["retrieval_receipt_refs"] == [retrieved["payload"]["receipt"]["receipt_id"]]
    assert listed["payload"]["count"] == 2
    assert listed["payload"]["events"][0]["note_id"] == captured["payload"]["event"]["note_id"]
    assert listed["payload"]["events"][0]["claim_key"] == "runtime.parser.state"
    assert listed["payload"]["events"][0]["claim_value"] == "ready"
    assert listed["payload"]["events"][1]["note_id"] == decision["payload"]["event"]["note_id"]
    assert listed["payload"]["events"][1]["retrieval_receipt_refs"] == [retrieved["payload"]["receipt"]["receipt_id"]]
    assert snapshot["payload"]["summary"]["retrieval_influence_count"] == 1
    assert snapshot["payload"]["summary"]["retrieval_influence_total_count"] == 1
    assert snapshot["payload"]["summary"]["retrieval_receipt_count"] == 1
    assert snapshot["payload"]["summary"]["retrieval_receipt_total_count"] == 1
    assert snapshot["payload"]["retrieval_influence"][0]["receipt_id"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert snapshot["payload"]["retrieval_receipts"][0]["receipt_id"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert snapshot["payload"]["retrieval_influence"][0]["citing_note_id"] == decision["payload"]["event"]["note_id"]
    assert filtered_snapshot["payload"]["filters"]["retrieval_receipt_ref"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert filtered_snapshot["payload"]["summary"]["retrieval_influence_count"] == 1
    assert filtered_snapshot["payload"]["summary"]["retrieval_influence_total_count"] == 1
    assert filtered_snapshot["payload"]["summary"]["retrieval_receipt_count"] == 1
    assert filtered_snapshot["payload"]["summary"]["retrieval_receipt_total_count"] == 1
    assert filtered_snapshot["payload"]["retrieval_influence"][0]["citing_note_id"] == decision["payload"]["event"]["note_id"]
    assert citing_note_snapshot["payload"]["filters"]["retrieval_citing_note_ref"] == decision["payload"]["event"]["note_id"]
    assert citing_note_snapshot["payload"]["summary"]["retrieval_influence_count"] == 1
    assert citing_note_snapshot["payload"]["summary"]["retrieval_influence_total_count"] == 1
    assert citing_note_snapshot["payload"]["retrieval_influence"][0]["receipt_id"] == retrieved["payload"]["receipt"]["receipt_id"]


def test_runtime_rejects_invalid_capture_without_persisting(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.capture_note(_working_note(kind="MemoryAnchor")).to_dict()
    listed = runtime.list_events().to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "promote_memory_anchor" in rejected["error"]
    assert listed["payload"]["count"] == 0


def test_runtime_rejects_malformed_retrieval_receipt_refs(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.capture_note(
        _working_note(
            kind="DecisionRecord",
            content_summary="runtime decision must reject arbitrary retrieval refs",
            source_ref="test:runtime-bad-retrieval-ref",
            expires_at=None,
            retrieval_receipt_refs=["manual-note-ref"],
        )
    ).to_dict()
    listed = runtime.list_events().to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "retrieval_receipt_ref must reference a note retrieval receipt" in rejected["error"]
    assert listed["payload"]["count"] == 0


def test_runtime_rejects_malformed_retrieval_influence_filter(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.dashboard_snapshot({"retrieval_receipt_ref": "manual-note-ref"}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "retrieval_receipt_ref must reference a note retrieval receipt" in rejected["error"]


def test_runtime_rejects_malformed_retrieval_citing_note_filter(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.dashboard_snapshot({"retrieval_citing_note_ref": "../bad-note"}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "retrieval_citing_note_ref must be a bounded symbolic identifier" in rejected["error"]


def test_runtime_rejects_string_dashboard_limit(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.dashboard_snapshot({"limit": "5"}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "limit must be an integer" in rejected["error"]


def test_runtime_rejects_boolean_dashboard_limit(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.dashboard_snapshot({"limit": True}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "limit must be an integer" in rejected["error"]


def test_runtime_rejects_non_text_dashboard_now(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.dashboard_snapshot({"now": 12345}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "now must be a string" in rejected["error"]


def test_runtime_rejects_non_text_retrieval_citing_note_filter(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.dashboard_snapshot({"retrieval_citing_note_ref": 7}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "retrieval_citing_note_ref must be a string" in rejected["error"]


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


def test_runtime_rejects_non_text_expiry_now(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    rejected = runtime.expire_temporary_notes({"now": 12345}).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "now must be a string" in rejected["error"]


def test_runtime_dashboard_snapshot_reports_operator_memory_state(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    captured = runtime.capture_note(_working_note(content_summary="dashboard parser note")).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    runtime.record_rejected_delta(
        {
            "summary": "Rejected unsafe note promotion",
            "source_ref": "test:dashboard-rejected",
            "evidence_refs": ["blocked"],
        }
    )
    runtime.queue_promotion({"note_id": source_note_id})

    snapshot = runtime.dashboard_snapshot({"limit": 5, "now": "2026-05-28T00:00:00+00:00"}).to_dict()
    repeated_snapshot = runtime.dashboard_snapshot({"limit": 5, "now": "2026-05-28T00:00:00+00:00"}).to_dict()

    assert snapshot["governed"] is True
    assert snapshot["ok"] is True
    assert snapshot["status"] == "dashboard_snapshot"
    assert snapshot["payload"]["assessed_at"] == "2026-05-28T00:00:00+00:00"
    assert snapshot["payload"]["snapshot_id"].startswith("note-memory-dashboard-")
    assert len(snapshot["payload"]["snapshot_hash"]) == 64
    assert repeated_snapshot["payload"]["snapshot_id"] == snapshot["payload"]["snapshot_id"]
    assert repeated_snapshot["payload"]["snapshot_hash"] == snapshot["payload"]["snapshot_hash"]
    assert snapshot["payload"]["summary"]["event_count"] == 2
    assert snapshot["payload"]["summary"]["active_note_count"] == 1
    assert snapshot["payload"]["summary"]["episode_capsule_count"] == 0
    assert snapshot["payload"]["summary"]["rejected_delta_count"] == 1
    assert snapshot["payload"]["summary"]["pending_promotion_count"] == 1
    assert snapshot["payload"]["summary"]["retrieval_influence_count"] == 0
    assert snapshot["payload"]["summary"]["retrieval_influence_total_count"] == 0
    assert snapshot["payload"]["summary"]["retrieval_receipt_count"] == 0
    assert snapshot["payload"]["summary"]["retrieval_receipt_total_count"] == 0
    assert snapshot["payload"]["summary"]["index_proof_state"] == "Pass"
    assert snapshot["payload"]["recent_notes"][0]["kind"] == "WorkingNote"
    assert snapshot["payload"]["rejected_deltas"][0]["kind"] == "RejectedDelta"
    assert snapshot["payload"]["pending_promotions"][0]["source_note_id"] == source_note_id


def test_runtime_dashboard_snapshot_rejects_invalid_limits(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    snapshot = runtime.dashboard_snapshot({"limit": 0}).to_dict()

    assert snapshot["governed"] is True
    assert snapshot["ok"] is False
    assert snapshot["status"] == "rejected"
    assert "dashboard limit" in snapshot["error"]


def test_runtime_dashboard_snapshot_rejects_corrupt_promotion_queue(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    captured = runtime.capture_note(_working_note(content_summary="dashboard parser note")).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    runtime.queue_promotion({"note_id": source_note_id})
    promotion_path = tmp_path / "notes" / "promotions" / "pending.jsonl"
    promotion_path.write_text('{"promotion_id": ""}\n', encoding="utf-8")

    snapshot = runtime.dashboard_snapshot({"limit": 5}).to_dict()

    assert snapshot["governed"] is True
    assert snapshot["ok"] is False
    assert snapshot["status"] == "rejected"
    assert "promotion queue entry missing promotion_id" in snapshot["error"]


def test_runtime_episode_capsule_and_claim_contradiction_envelopes(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    prior = runtime.capture_note(
        _working_note(
            kind="DecisionRecord",
            expires_at=None,
            content_summary="runtime claim says note memory is disabled",
            claim_key="runtime.note-memory.state",
            claim_value="disabled",
        )
    ).to_dict()
    current = runtime.capture_note(
        _working_note(
            kind="DecisionRecord",
            expires_at=None,
            content_summary="runtime claim says note memory is mounted",
            claim_key="runtime.note-memory.state",
            claim_value="mounted",
        )
    ).to_dict()
    episode = runtime.capture_episode_capsule(
        {
            "episode_id": "episode-runtime-note-memory",
            "goal": "Wire note-memory episode capsules",
            "scope": "repository",
            "proof_state": "Pass",
            "trust_zone": "workspace",
            "constraints": ["append-only note lineage"],
            "decisions": ["use explicit claim metadata for contradiction detection"],
            "changed_files": ["mcoi/mcoi_runtime/core/note_memory_mesh.py"],
            "verification_refs": ["python -m pytest mcoi/tests/test_note_memory_api.py"],
            "open_risks": [],
            "evidence_refs": ["test_runtime_episode_capsule_and_claim_contradiction_envelopes"],
            "relation_refs": [current["payload"]["event"]["event_id"]],
        }
    ).to_dict()
    snapshot = runtime.dashboard_snapshot({"limit": 10}).to_dict()

    assert prior["ok"] is True
    assert current["ok"] is True
    assert episode["status"] == "episode_capsule_captured"
    assert episode["payload"]["event"]["kind"] == "EpisodeCapsule"
    assert snapshot["payload"]["summary"]["event_count"] == 4
    assert snapshot["payload"]["summary"]["contradiction_count"] == 1
    assert snapshot["payload"]["summary"]["episode_capsule_count"] == 1
    assert snapshot["payload"]["episode_capsules"][0]["note_id"] == "episode-runtime-note-memory"


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


def test_runtime_rejects_string_promotion_lineage_event_seq(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    captured = runtime.capture_note(_working_note(scope="repository")).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    queued = runtime.queue_promotion({"note_id": source_note_id}).to_dict()

    rejected = runtime.promote_memory_anchor(
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
                "lineage_event_seq": "1",
            },
        }
    ).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "lineage_event_seq must be an integer" in rejected["error"]


def test_runtime_rejects_boolean_promotion_lineage_event_seq(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    captured = runtime.capture_note(_working_note(scope="repository")).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    queued = runtime.queue_promotion({"note_id": source_note_id}).to_dict()

    rejected = runtime.promote_memory_anchor(
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
                "lineage_event_seq": True,
            },
        }
    ).to_dict()

    assert rejected["governed"] is True
    assert rejected["ok"] is False
    assert rejected["status"] == "rejected"
    assert "lineage_event_seq must be an integer" in rejected["error"]
