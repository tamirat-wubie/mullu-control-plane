"""Purpose: public API integration bridge.
Governance scope: composing public API with service requests, case reviews,
    reporting submissions, customer accounts, marketplace listings, and
    orchestration plans; memory mesh and graph attachment.
Dependencies: public_api engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every API surface action emits events.
  - API state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.public_api import EndpointKind, ApiVisibility
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .public_api import PublicApiEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-apiint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PublicApiIntegration:
    """Integration bridge for public API with platform layers."""

    def __init__(
        self,
        api_engine: PublicApiEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(api_engine, PublicApiEngine):
            raise RuntimeCoreInvariantError("api_engine must be a PublicApiEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._api = api_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Endpoint for service request
    # ------------------------------------------------------------------

    def endpoint_for_service_request(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str = "/api/v1/service-requests",
    ) -> dict[str, Any]:
        ep = self._api.register_endpoint(
            endpoint_id=endpoint_id, tenant_id=tenant_id, path=path,
            kind=EndpointKind.WRITE, visibility=ApiVisibility.PUBLIC,
            target_runtime="service_catalog", target_action="submit",
        )
        _emit(self._events, "endpoint_for_service_request", {
            "endpoint_id": endpoint_id, "path": path,
        }, endpoint_id)
        return {
            "endpoint_id": ep.endpoint_id,
            "tenant_id": ep.tenant_id,
            "path": ep.path,
            "kind": ep.kind.value,
            "visibility": ep.visibility.value,
            "target_runtime": ep.target_runtime,
            "target_action": ep.target_action,
            "source_type": "service_request",
        }

    # ------------------------------------------------------------------
    # Endpoint for case review
    # ------------------------------------------------------------------

    def endpoint_for_case_review(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str = "/api/v1/case-reviews",
    ) -> dict[str, Any]:
        ep = self._api.register_endpoint(
            endpoint_id=endpoint_id, tenant_id=tenant_id, path=path,
            kind=EndpointKind.WRITE, visibility=ApiVisibility.INTERNAL,
            target_runtime="case", target_action="review",
        )
        _emit(self._events, "endpoint_for_case_review", {
            "endpoint_id": endpoint_id, "path": path,
        }, endpoint_id)
        return {
            "endpoint_id": ep.endpoint_id,
            "tenant_id": ep.tenant_id,
            "path": ep.path,
            "kind": ep.kind.value,
            "visibility": ep.visibility.value,
            "target_runtime": ep.target_runtime,
            "target_action": ep.target_action,
            "source_type": "case_review",
        }

    # ------------------------------------------------------------------
    # Endpoint for reporting submission
    # ------------------------------------------------------------------

    def endpoint_for_reporting_submission(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str = "/api/v1/reports",
    ) -> dict[str, Any]:
        ep = self._api.register_endpoint(
            endpoint_id=endpoint_id, tenant_id=tenant_id, path=path,
            kind=EndpointKind.MUTATION, visibility=ApiVisibility.PARTNER,
            target_runtime="reporting", target_action="submit",
        )
        _emit(self._events, "endpoint_for_reporting_submission", {
            "endpoint_id": endpoint_id, "path": path,
        }, endpoint_id)
        return {
            "endpoint_id": ep.endpoint_id,
            "tenant_id": ep.tenant_id,
            "path": ep.path,
            "kind": ep.kind.value,
            "visibility": ep.visibility.value,
            "target_runtime": ep.target_runtime,
            "target_action": ep.target_action,
            "source_type": "reporting_submission",
        }

    # ------------------------------------------------------------------
    # Endpoint for customer account
    # ------------------------------------------------------------------

    def endpoint_for_customer_account(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str = "/api/v1/customers",
    ) -> dict[str, Any]:
        ep = self._api.register_endpoint(
            endpoint_id=endpoint_id, tenant_id=tenant_id, path=path,
            kind=EndpointKind.QUERY, visibility=ApiVisibility.PUBLIC,
            target_runtime="customer", target_action="query",
        )
        _emit(self._events, "endpoint_for_customer_account", {
            "endpoint_id": endpoint_id, "path": path,
        }, endpoint_id)
        return {
            "endpoint_id": ep.endpoint_id,
            "tenant_id": ep.tenant_id,
            "path": ep.path,
            "kind": ep.kind.value,
            "visibility": ep.visibility.value,
            "target_runtime": ep.target_runtime,
            "target_action": ep.target_action,
            "source_type": "customer_account",
        }

    # ------------------------------------------------------------------
    # Endpoint for marketplace listing
    # ------------------------------------------------------------------

    def endpoint_for_marketplace_listing(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str = "/api/v1/marketplace",
    ) -> dict[str, Any]:
        ep = self._api.register_endpoint(
            endpoint_id=endpoint_id, tenant_id=tenant_id, path=path,
            kind=EndpointKind.READ, visibility=ApiVisibility.PUBLIC,
            target_runtime="marketplace", target_action="list",
        )
        _emit(self._events, "endpoint_for_marketplace_listing", {
            "endpoint_id": endpoint_id, "path": path,
        }, endpoint_id)
        return {
            "endpoint_id": ep.endpoint_id,
            "tenant_id": ep.tenant_id,
            "path": ep.path,
            "kind": ep.kind.value,
            "visibility": ep.visibility.value,
            "target_runtime": ep.target_runtime,
            "target_action": ep.target_action,
            "source_type": "marketplace_listing",
        }

    # ------------------------------------------------------------------
    # Endpoint for orchestration plan
    # ------------------------------------------------------------------

    def endpoint_for_orchestration_plan(
        self,
        endpoint_id: str,
        tenant_id: str,
        path: str = "/api/v1/orchestrations",
    ) -> dict[str, Any]:
        ep = self._api.register_endpoint(
            endpoint_id=endpoint_id, tenant_id=tenant_id, path=path,
            kind=EndpointKind.WRITE, visibility=ApiVisibility.ADMIN,
            target_runtime="meta_orchestration", target_action="execute",
        )
        _emit(self._events, "endpoint_for_orchestration_plan", {
            "endpoint_id": endpoint_id, "path": path,
        }, endpoint_id)
        return {
            "endpoint_id": ep.endpoint_id,
            "tenant_id": ep.tenant_id,
            "path": ep.path,
            "kind": ep.kind.value,
            "visibility": ep.visibility.value,
            "target_runtime": ep.target_runtime,
            "target_action": ep.target_action,
            "source_type": "orchestration_plan",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_api_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        snap = self._api.api_snapshot(
            snapshot_id=stable_identifier("snap-api", {"scope": scope_ref_id, "ts": now}),
            tenant_id=scope_ref_id,
        )
        content = {
            "total_endpoints": snap.total_endpoints,
            "active_endpoints": snap.active_endpoints,
            "total_requests": snap.total_requests,
            "accepted_requests": snap.accepted_requests,
            "rejected_requests": snap.rejected_requests,
            "rate_limited_requests": snap.rate_limited_requests,
            "deduplicated_requests": snap.deduplicated_requests,
        }
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-api", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)}),
            scope_ref_id=scope_ref_id,
            title="Public API state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("public_api", "product_surface", "endpoints"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        _emit(self._events, "attach_api_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return mem

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_api_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        snap = self._api.api_snapshot(
            snapshot_id=stable_identifier("gsnap-api", {"scope": scope_ref_id, "ts": _now_iso()}),
            tenant_id=scope_ref_id,
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_endpoints": snap.total_endpoints,
            "active_endpoints": snap.active_endpoints,
            "total_requests": snap.total_requests,
            "accepted_requests": snap.accepted_requests,
            "rejected_requests": snap.rejected_requests,
            "rate_limited_requests": snap.rate_limited_requests,
            "deduplicated_requests": snap.deduplicated_requests,
        }
