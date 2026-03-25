"""Purpose: operator workspace integration bridge.
Governance scope: composing operator workspace with service requests,
    case reviews, remediations, reporting, settlement, continuity,
    and executive control; memory mesh and graph attachment.
Dependencies: operator_workspace engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every workspace action emits events.
  - Workspace state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.operator_workspace import PanelKind, WorkspaceScope
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .operator_workspace import OperatorWorkspaceEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-wksint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class OperatorWorkspaceIntegration:
    """Integration bridge for operator workspace with platform layers."""

    def __init__(
        self,
        workspace_engine: OperatorWorkspaceEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(workspace_engine, OperatorWorkspaceEngine):
            raise RuntimeCoreInvariantError(
                "workspace_engine must be an OperatorWorkspaceEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._workspace = workspace_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Workspace from service requests
    # ------------------------------------------------------------------

    def workspace_from_service_requests(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Service Fulfillment Queue",
            scope=WorkspaceScope.TEAM,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Service Requests", kind=PanelKind.QUEUE,
            target_runtime="service_catalog",
        )
        _emit(self._events, "workspace_from_service_requests", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "service_requests",
        }

    # ------------------------------------------------------------------
    # Workspace from case reviews
    # ------------------------------------------------------------------

    def workspace_from_case_reviews(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Investigation Queue",
            scope=WorkspaceScope.TEAM,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Case Reviews", kind=PanelKind.INVESTIGATION,
            target_runtime="case",
        )
        _emit(self._events, "workspace_from_case_reviews", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "case_reviews",
        }

    # ------------------------------------------------------------------
    # Workspace from remediations
    # ------------------------------------------------------------------

    def workspace_from_remediations(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Remediation Queue",
            scope=WorkspaceScope.TEAM,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Remediations", kind=PanelKind.QUEUE,
            target_runtime="remediation",
        )
        _emit(self._events, "workspace_from_remediations", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "remediations",
        }

    # ------------------------------------------------------------------
    # Workspace from reporting
    # ------------------------------------------------------------------

    def workspace_from_reporting(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Reporting Dashboard",
            scope=WorkspaceScope.WORKSPACE,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Reports", kind=PanelKind.DASHBOARD,
            target_runtime="reporting",
        )
        _emit(self._events, "workspace_from_reporting", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "reporting",
        }

    # ------------------------------------------------------------------
    # Workspace from settlement
    # ------------------------------------------------------------------

    def workspace_from_settlement(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Settlement Review",
            scope=WorkspaceScope.TEAM,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Settlements", kind=PanelKind.REVIEW,
            target_runtime="settlement",
        )
        _emit(self._events, "workspace_from_settlement", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "settlement",
        }

    # ------------------------------------------------------------------
    # Workspace from continuity
    # ------------------------------------------------------------------

    def workspace_from_continuity(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Continuity Operations",
            scope=WorkspaceScope.TEAM,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Continuity Events", kind=PanelKind.QUEUE,
            target_runtime="continuity",
        )
        _emit(self._events, "workspace_from_continuity", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "continuity",
        }

    # ------------------------------------------------------------------
    # Workspace from executive control
    # ------------------------------------------------------------------

    def workspace_from_executive_control(
        self,
        view_id: str,
        panel_id: str,
        tenant_id: str,
        operator_ref: str,
    ) -> dict[str, Any]:
        view = self._workspace.register_view(
            view_id=view_id, tenant_id=tenant_id, operator_ref=operator_ref,
            display_name="Executive Control Panel",
            scope=WorkspaceScope.EXECUTIVE,
        )
        panel = self._workspace.register_panel(
            panel_id=panel_id, view_id=view_id, tenant_id=tenant_id,
            display_name="Executive Issues", kind=PanelKind.APPROVAL,
            target_runtime="executive_control",
        )
        _emit(self._events, "workspace_from_executive_control", {
            "view_id": view_id, "panel_id": panel_id,
        }, view_id)
        return {
            "view_id": view.view_id,
            "panel_id": panel.panel_id,
            "tenant_id": tenant_id,
            "operator_ref": operator_ref,
            "panel_kind": panel.kind.value,
            "target_runtime": panel.target_runtime,
            "source_type": "executive_control",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_workspace_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        snap = self._workspace.workspace_snapshot(
            snapshot_id=stable_identifier("snap-wks", {"scope": scope_ref_id, "ts": now}),
            tenant_id=scope_ref_id,
        )
        content = {
            "total_views": snap.total_views,
            "active_views": snap.active_views,
            "total_panels": snap.total_panels,
            "total_queue_items": snap.total_queue_items,
            "pending_queue_items": snap.pending_queue_items,
            "total_worklist_items": snap.total_worklist_items,
            "total_actions": snap.total_actions,
        }
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-wks", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)}),
            scope_ref_id=scope_ref_id,
            title=f"Operator workspace state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("operator_workspace", "ui", "queues"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        _emit(self._events, "attach_workspace_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return mem

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_workspace_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        snap = self._workspace.workspace_snapshot(
            snapshot_id=stable_identifier("gsnap-wks", {"scope": scope_ref_id, "ts": _now_iso()}),
            tenant_id=scope_ref_id,
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_views": snap.total_views,
            "active_views": snap.active_views,
            "total_panels": snap.total_panels,
            "total_queue_items": snap.total_queue_items,
            "pending_queue_items": snap.pending_queue_items,
            "total_worklist_items": snap.total_worklist_items,
            "total_actions": snap.total_actions,
        }
