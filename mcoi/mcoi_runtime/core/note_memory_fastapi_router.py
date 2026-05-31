"""Optional FastAPI router adapter for governed note memory operations.

Purpose: expose note memory capture, episode capsule, retrieval, expiry,
rejected-delta, promotion, dashboard snapshot, rebuild, and event-listing
handlers for host FastAPI applications without making FastAPI a core runtime
dependency.
Governance scope: HTTP adapter boundary only; NoteMemoryRuntime owns request
validation, append-only persistence, guard checks, and rejection envelopes.
Dependencies: note memory runtime API, dataclasses, and optional FastAPI at
router creation.
Invariants: importing this module does not require FastAPI, route handlers do
not bypass runtime envelopes, and missing FastAPI is reported explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime


@dataclass(frozen=True)
class NoteMemoryRouteSpec:
    """Documented HTTP route contract for a governed note memory adapter."""

    method: str
    path: str
    handler_name: str
    purpose: str


class NoteMemoryFastAPIAdapter:
    """Framework-adjacent handler object for governed note memory endpoints."""

    def __init__(self, runtime: NoteMemoryRuntime) -> None:
        self.runtime = runtime

    def capture_note(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /events."""

        return self.runtime.capture_note(request_body).to_dict()

    def record_rejected_delta(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /rejected-deltas."""

        return self.runtime.record_rejected_delta(request_body).to_dict()

    def capture_episode_capsule(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /episodes."""

        return self.runtime.capture_episode_capsule(request_body).to_dict()

    def retrieve_notes(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /retrieve."""

        return self.runtime.retrieve_notes(request_body).to_dict()

    def expire_temporary_notes(self, request_body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Handle POST /expire."""

        return self.runtime.expire_temporary_notes(request_body).to_dict()

    def queue_promotion(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /promotions."""

        return self.runtime.queue_promotion(request_body).to_dict()

    def promote_memory_anchor(self, request_body: Mapping[str, Any]) -> dict[str, Any]:
        """Handle POST /anchors."""

        return self.runtime.promote_memory_anchor(request_body).to_dict()

    def rebuild_index(self) -> dict[str, Any]:
        """Handle POST /index/rebuild."""

        return self.runtime.rebuild_index().to_dict()

    def dashboard_snapshot(self, request_body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Handle GET /dashboard."""

        return self.runtime.dashboard_snapshot(request_body).to_dict()

    def list_events(self) -> dict[str, Any]:
        """Handle GET /events."""

        return self.runtime.list_events().to_dict()

    @staticmethod
    def route_specs(prefix: str = "/api/v1/notes") -> tuple[NoteMemoryRouteSpec, ...]:
        """Return the stable HTTP route contracts."""

        normalized = prefix.rstrip("/")
        return (
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/events",
                handler_name="capture_note",
                purpose="capture one governed note memory event",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/rejected-deltas",
                handler_name="record_rejected_delta",
                purpose="record durable negative evidence for a blocked delta",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/episodes",
                handler_name="capture_episode_capsule",
                purpose="capture one structured post-episode capsule",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/retrieve",
                handler_name="retrieve_notes",
                purpose="retrieve guard-approved notes without mutating lineage",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/expire",
                handler_name="expire_temporary_notes",
                purpose="expire temporary notes past their TTL",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/promotions",
                handler_name="queue_promotion",
                purpose="queue a note for Phi_gov promotion review",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/anchors",
                handler_name="promote_memory_anchor",
                purpose="promote a validated note into a MemoryAnchor",
            ),
            NoteMemoryRouteSpec(
                method="POST",
                path=f"{normalized}/index/rebuild",
                handler_name="rebuild_index",
                purpose="validate note event logs and projection fitness",
            ),
            NoteMemoryRouteSpec(
                method="GET",
                path=f"{normalized}/dashboard",
                handler_name="dashboard_snapshot",
                purpose="return a read-only operator dashboard snapshot",
            ),
            NoteMemoryRouteSpec(
                method="GET",
                path=f"{normalized}/events",
                handler_name="list_events",
                purpose="list persisted note memory events",
            ),
        )


def create_note_memory_fastapi_router(runtime: NoteMemoryRuntime, prefix: str = "/api/v1/notes"):
    """Create a FastAPI APIRouter for governed note memory endpoints.

    FastAPI is imported only here so the core note memory runtime remains
    usable in lightweight worker, CLI, and test contexts.
    """

    try:
        from fastapi import APIRouter, Body
    except ImportError as exc:
        raise RuntimeError("FastAPI is required to create the note memory router") from exc

    adapter = NoteMemoryFastAPIAdapter(runtime)
    router = APIRouter(prefix=prefix.rstrip("/"), tags=["governed-note-memory"])

    @router.post("/events")
    def capture_note(request_body: dict[str, Any] = Body(...)):
        return adapter.capture_note(request_body)

    @router.post("/rejected-deltas")
    def record_rejected_delta(request_body: dict[str, Any] = Body(...)):
        return adapter.record_rejected_delta(request_body)

    @router.post("/episodes")
    def capture_episode_capsule(request_body: dict[str, Any] = Body(...)):
        return adapter.capture_episode_capsule(request_body)

    @router.post("/retrieve")
    def retrieve_notes(request_body: dict[str, Any] = Body(...)):
        return adapter.retrieve_notes(request_body)

    @router.post("/expire")
    def expire_temporary_notes(request_body: dict[str, Any] = Body({})):
        return adapter.expire_temporary_notes(request_body)

    @router.post("/promotions")
    def queue_promotion(request_body: dict[str, Any] = Body(...)):
        return adapter.queue_promotion(request_body)

    @router.post("/anchors")
    def promote_memory_anchor(request_body: dict[str, Any] = Body(...)):
        return adapter.promote_memory_anchor(request_body)

    @router.post("/index/rebuild")
    def rebuild_index():
        return adapter.rebuild_index()

    @router.get("/dashboard")
    def dashboard_snapshot(
        limit: int = 25,
        now: str | None = None,
        retrieval_receipt_ref: str | None = None,
    ):
        request_body: dict[str, Any] = {"limit": limit}
        if now:
            request_body["now"] = now
        if retrieval_receipt_ref:
            request_body["retrieval_receipt_ref"] = retrieval_receipt_ref
        return adapter.dashboard_snapshot(request_body)

    @router.get("/events")
    def list_events():
        return adapter.list_events()

    return router
