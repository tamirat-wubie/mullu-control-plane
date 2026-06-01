"""Tests for the optional governed note memory FastAPI adapter.

Purpose: verify route contracts and handler envelopes without requiring
FastAPI as a core dependency.
Governance scope: HTTP-shaped adapter must preserve runtime validation,
append-only persistence, retrieval guards, rejected-delta evidence, and
promotion receipt semantics.
Dependencies: mcoi_runtime.core.note_memory_fastapi_router.
Invariants: route specs are stable, handlers remain governed, and missing
FastAPI is explicit when router creation is requested.
"""

from __future__ import annotations

from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime
from mcoi_runtime.core.note_memory_fastapi_router import (
    NoteMemoryFastAPIAdapter,
    create_note_memory_fastapi_router,
)


def _working_note(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "kind": "WorkingNote",
        "scope": "task",
        "content_summary": "http parser note",
        "source_ref": "test:http",
        "proof_state": "Pass",
        "trust_zone": "workspace",
        "expires_at": "2999-01-01T00:00:00+00:00",
        "evidence_refs": ["test_note_memory_fastapi_router"],
    }
    value.update(overrides)
    return value


def test_note_memory_fastapi_adapter_route_specs_are_stable() -> None:
    specs = NoteMemoryFastAPIAdapter.route_specs()

    assert len(specs) == 10
    assert [(spec.method, spec.path, spec.handler_name) for spec in specs] == [
        ("POST", "/api/v1/notes/events", "capture_note"),
        ("POST", "/api/v1/notes/rejected-deltas", "record_rejected_delta"),
        ("POST", "/api/v1/notes/episodes", "capture_episode_capsule"),
        ("POST", "/api/v1/notes/retrieve", "retrieve_notes"),
        ("POST", "/api/v1/notes/expire", "expire_temporary_notes"),
        ("POST", "/api/v1/notes/promotions", "queue_promotion"),
        ("POST", "/api/v1/notes/anchors", "promote_memory_anchor"),
        ("POST", "/api/v1/notes/index/rebuild", "rebuild_index"),
        ("GET", "/api/v1/notes/dashboard", "dashboard_snapshot"),
        ("GET", "/api/v1/notes/events", "list_events"),
    ]
    assert all(spec.purpose for spec in specs)


def test_note_memory_fastapi_adapter_handlers_preserve_runtime_envelopes(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    adapter = NoteMemoryFastAPIAdapter(runtime)

    captured = adapter.capture_note(_working_note())
    retrieved = adapter.retrieve_notes({"query": "parser", "scope": "task"})
    decision = adapter.capture_note(
        _working_note(
            kind="DecisionRecord",
            content_summary="adapter decision cites parser retrieval receipt",
            source_ref="test:adapter-decision",
            expires_at=None,
            retrieval_receipt_refs=[retrieved["payload"]["receipt"]["receipt_id"]],
        )
    )
    listed = adapter.list_events()
    dashboard = adapter.dashboard_snapshot({"limit": 5, "now": "2026-05-28T00:00:00+00:00"})
    filtered_dashboard = adapter.dashboard_snapshot(
        {
            "limit": 5,
            "retrieval_receipt_ref": retrieved["payload"]["receipt"]["receipt_id"],
        }
    )
    citing_note_dashboard = adapter.dashboard_snapshot(
        {
            "limit": 5,
            "retrieval_citing_note_ref": decision["payload"]["event"]["note_id"],
        }
    )

    assert captured["governed"] is True
    assert captured["ok"] is True
    assert retrieved["payload"]["count"] == 1
    assert retrieved["payload"]["receipt"]["receipt_id"].startswith("note-retrieval-")
    assert len(retrieved["payload"]["receipt"]["snapshot_hash"]) == 64
    assert decision["payload"]["event"]["retrieval_receipt_refs"] == [retrieved["payload"]["receipt"]["receipt_id"]]
    assert listed["payload"]["count"] == 2
    assert listed["payload"]["events"][0]["note_id"] == captured["payload"]["event"]["note_id"]
    assert listed["payload"]["events"][1]["note_id"] == decision["payload"]["event"]["note_id"]
    assert dashboard["payload"]["summary"]["retrieval_influence_count"] == 1
    assert dashboard["payload"]["summary"]["retrieval_influence_total_count"] == 1
    assert dashboard["payload"]["summary"]["retrieval_receipt_count"] == 1
    assert dashboard["payload"]["summary"]["retrieval_receipt_total_count"] == 1
    assert dashboard["payload"]["retrieval_influence"][0]["citing_note_id"] == decision["payload"]["event"]["note_id"]
    assert dashboard["payload"]["retrieval_receipts"][0]["receipt_id"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert filtered_dashboard["payload"]["filters"]["retrieval_receipt_ref"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert filtered_dashboard["payload"]["summary"]["retrieval_influence_count"] == 1
    assert filtered_dashboard["payload"]["summary"]["retrieval_influence_total_count"] == 1
    assert filtered_dashboard["payload"]["summary"]["retrieval_receipt_count"] == 1
    assert filtered_dashboard["payload"]["summary"]["retrieval_receipt_total_count"] == 1
    assert filtered_dashboard["payload"]["retrieval_influence"][0]["citing_note_id"] == decision["payload"]["event"]["note_id"]
    assert citing_note_dashboard["payload"]["filters"]["retrieval_citing_note_ref"] == decision["payload"]["event"]["note_id"]
    assert citing_note_dashboard["payload"]["summary"]["retrieval_influence_count"] == 1
    assert citing_note_dashboard["payload"]["retrieval_influence"][0]["receipt_id"] == retrieved["payload"]["receipt"]["receipt_id"]


def test_note_memory_fastapi_adapter_dashboard_snapshot_is_read_only(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    adapter = NoteMemoryFastAPIAdapter(runtime)
    captured = adapter.capture_note(_working_note(content_summary="dashboard parser note"))

    dashboard = adapter.dashboard_snapshot({"limit": 5})
    listed = adapter.list_events()

    assert dashboard["governed"] is True
    assert dashboard["status"] == "dashboard_snapshot"
    assert dashboard["payload"]["snapshot_id"].startswith("note-memory-dashboard-")
    assert len(dashboard["payload"]["snapshot_hash"]) == 64
    assert dashboard["payload"]["summary"]["event_count"] == 1
    assert dashboard["payload"]["recent_notes"][0]["note_id"] == captured["payload"]["event"]["note_id"]
    assert listed["payload"]["count"] == 1


def test_created_note_memory_fastapi_router_exposes_dashboard_route(tmp_path) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    captured = runtime.capture_note(_working_note(content_summary="router dashboard note")).to_dict()
    retrieved = runtime.retrieve_notes({"query": "router", "scope": "task"}).to_dict()
    decision = runtime.capture_note(
        _working_note(
            kind="DecisionRecord",
            content_summary="router decision cites dashboard retrieval receipt",
            source_ref="test:router-dashboard-decision",
            expires_at=None,
            retrieval_receipt_refs=[retrieved["payload"]["receipt"]["receipt_id"]],
        )
    ).to_dict()
    app = FastAPI()
    app.include_router(create_note_memory_fastapi_router(runtime))
    client = TestClient(app)

    dashboard = client.get(
        f"/api/v1/notes/dashboard?limit=5&retrieval_receipt_ref={retrieved['payload']['receipt']['receipt_id']}"
        f"&retrieval_citing_note_ref={decision['payload']['event']['note_id']}"
    )
    events = client.get("/api/v1/notes/events")

    assert dashboard.status_code == 200
    assert dashboard.json()["status"] == "dashboard_snapshot"
    assert dashboard.json()["payload"]["snapshot_id"].startswith("note-memory-dashboard-")
    assert len(dashboard.json()["payload"]["snapshot_hash"]) == 64
    assert dashboard.json()["payload"]["summary"]["event_count"] == 2
    assert dashboard.json()["payload"]["filters"]["retrieval_receipt_ref"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert dashboard.json()["payload"]["filters"]["retrieval_citing_note_ref"] == decision["payload"]["event"]["note_id"]
    assert dashboard.json()["payload"]["summary"]["retrieval_influence_count"] == 1
    assert dashboard.json()["payload"]["summary"]["retrieval_influence_total_count"] == 1
    assert dashboard.json()["payload"]["summary"]["retrieval_receipt_count"] == 1
    assert dashboard.json()["payload"]["summary"]["retrieval_receipt_total_count"] == 1
    assert dashboard.json()["payload"]["retrieval_influence"][0]["citing_note_id"] == decision["payload"]["event"]["note_id"]
    assert dashboard.json()["payload"]["recent_notes"][0]["note_id"] == decision["payload"]["event"]["note_id"]
    assert dashboard.json()["payload"]["recent_notes"][1]["note_id"] == captured["payload"]["event"]["note_id"]
    assert events.json()["payload"]["count"] == 2


def test_note_memory_fastapi_adapter_captures_episode_capsule(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    adapter = NoteMemoryFastAPIAdapter(runtime)

    envelope = adapter.capture_episode_capsule(
        {
            "episode_id": "episode-http-note-memory",
            "goal": "Expose episode capsule route",
            "scope": "repository",
            "proof_state": "Pass",
            "trust_zone": "workspace",
            "decisions": ["keep episode capture behind runtime envelopes"],
            "verification_refs": ["python -m pytest mcoi/tests/test_note_memory_fastapi_router.py"],
            "evidence_refs": ["test_note_memory_fastapi_adapter_captures_episode_capsule"],
        }
    )

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "episode_capsule_captured"
    assert envelope["payload"]["event"]["kind"] == "EpisodeCapsule"
    assert (tmp_path / "notes" / "episodes" / "episode-http-note-memory.json").exists()


def test_note_memory_fastapi_adapter_rejections_do_not_persist(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    adapter = NoteMemoryFastAPIAdapter(runtime)

    envelope = adapter.capture_note(_working_note(kind="MemoryAnchor"))

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "promote_memory_anchor" in envelope["error"]
    assert adapter.list_events()["payload"]["count"] == 0


def test_note_memory_fastapi_adapter_promotes_with_receipt(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")
    adapter = NoteMemoryFastAPIAdapter(runtime)
    captured = adapter.capture_note(_working_note(scope="repository"))
    source_note_id = captured["payload"]["event"]["note_id"]
    source_event_seq = captured["payload"]["event"]["event_seq"]

    queued = adapter.queue_promotion({"note_id": source_note_id})
    promoted = adapter.promote_memory_anchor(
        {
            "note_id": source_note_id,
            "receipt": {
                "promotion_id": queued["payload"]["promotion_id"],
                "source_note_id": source_note_id,
                "anchor_id": "anchor-http-note-contract",
                "proof_state": "Pass",
                "evidence_refs": ["test_note_memory_fastapi_router"],
                "contradiction_scan": "Pass",
                "phi_gov_status": "accepted",
                "accepted_at": "2026-05-27T00:05:00+00:00",
                "accepted_by": "test-governance",
                "lineage_event_seq": source_event_seq,
            },
        }
    )

    assert queued["status"] == "promotion_queued"
    assert promoted["payload"]["event"]["kind"] == "MemoryAnchor"
    assert (tmp_path / "notes" / "anchors" / "anchor-http-note-contract.json").exists()


def test_create_note_memory_fastapi_router_reports_missing_dependency(tmp_path) -> None:
    runtime = NoteMemoryRuntime.from_path(tmp_path / "notes")

    try:
        router = create_note_memory_fastapi_router(runtime)
    except RuntimeError as exc:
        assert "FastAPI is required" in str(exc)
    else:
        assert router is not None
