"""ServiceCatalogEngine adapters for the intent substrate.

Purpose: expose service catalog requests and tasks to intent substrate
observation and opt-in request status closure.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, PRS.
Dependencies: ServiceCatalogEngine, intent substrate closure protocols, and
service catalog contract records.
Invariants: adapter lookups are read-only; closure calls route through the
catalog status transition helper; missing requests fail closed.

Two adapters, two directions:

  ServiceCatalogStateView (observation)
    Exposes tasks/requests as queryable entities for predicate
    evaluation. Entity ID convention:
        "task:<task_id>"       -> FulfillmentTask attributes
        "request:<request_id>" -> ServiceRequest attributes
    Returned mappings are stable, JSON-serializable, and contain only
    the fields predicates are likely to reference. Missing/unknown IDs
    return None (the StateView contract for "absent").

  RequestStatusClosureAdapter (action) - OPT-IN
    Drives a request's lifecycle: FULFILLED on success, CANCELLED on
    precondition failure. intent_id == request_id.

    This does NOT replace the catalog's inline synchronous auto-fulfill
    at service_catalog.py:660 - that path still works exactly as
    before. The adapter lets a caller route a *specific* request's
    fulfillment through the substrate instead, gaining the two-
    confirmation safety guarantee at the cost of asynchronous
    fulfillment (event + confirm window + tick).

    Migration note (deliberately NOT done here): to make the catalog's
    fulfillment two-confirm-safe globally, the inline all(...) block at
    service_catalog.py:660 would declare a substrate intent rather than
    calling _update_request_status directly. That changes fulfillment
    from synchronous to asynchronous and would require updating the
    catalog's existing test suite - a behavior change left as a
    maintainer decision, surfaced in the PR rather than forced.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.service_catalog import (
    FulfillmentStatus,
    ServiceRequest,
    RequestStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.service_catalog import ServiceCatalogEngine

from ..primitives import EntityId

_TASK_PREFIX = "task:"
_REQUEST_PREFIX = "request:"

_REQUEST_TERMINAL = (
    RequestStatus.FULFILLED,
    RequestStatus.DENIED,
    RequestStatus.CANCELLED,
)


class ServiceCatalogStateView:
    """StateView backed by a ServiceCatalogEngine.

    Pass instances directly as the resolver's `state_view` argument:

        resolver = IntentResolver(
            state_view=ServiceCatalogStateView(catalog),
            closure=ObligationClosureAdapter(obligations),
            spine=spine,
        )

    Predicates then reference entities by `"task:<id>"` /
    `"request:<id>"` and the resolver translates lookups through
    this adapter into engine queries.

    For substrates that need to read state from MORE than one engine,
    chain multiple StateViews via a small dispatcher:

        def state_view(eid):
            if eid.startswith("task:") or eid.startswith("request:"):
                return catalog_view(eid)
            elif eid.startswith("obligation:"):
                return obligation_view(eid)
            ...
    """

    def __init__(self, catalog: ServiceCatalogEngine) -> None:
        self._catalog = catalog

    def __call__(self, entity_id: EntityId) -> "Mapping[str, Any] | None":
        if entity_id.startswith(_TASK_PREFIX):
            return self._task_view(entity_id[len(_TASK_PREFIX):])
        if entity_id.startswith(_REQUEST_PREFIX):
            return self._request_view(entity_id[len(_REQUEST_PREFIX):])
        return None

    def _task_view(self, task_id: str) -> "Mapping[str, Any] | None":
        try:
            task = self._catalog.get_task(task_id)
        except RuntimeCoreInvariantError:
            return None
        return {
            "task_id": task.task_id,
            "request_id": task.request_id,
            "assignee_ref": task.assignee_ref,
            "status": task.status.value,
            "is_completed": task.status == FulfillmentStatus.COMPLETED,
            "is_failed": task.status == FulfillmentStatus.FAILED,
            "is_terminal": task.status
            in (
                FulfillmentStatus.COMPLETED,
                FulfillmentStatus.FAILED,
                FulfillmentStatus.CANCELLED,
            ),
        }

    def _request_view(self, request_id: str) -> "Mapping[str, Any] | None":
        try:
            req = self._catalog.get_request(request_id)
        except RuntimeCoreInvariantError:
            return None
        return {
            "request_id": req.request_id,
            "item_id": req.item_id,
            "tenant_id": req.tenant_id,
            "requester_ref": req.requester_ref,
            "status": req.status.value,
            "priority": req.priority.value,
            "is_fulfilled": req.status == RequestStatus.FULFILLED,
            "is_denied": req.status == RequestStatus.DENIED,
            "is_cancelled": req.status == RequestStatus.CANCELLED,
            "is_terminal": req.status in _REQUEST_TERMINAL,
        }


class RequestStatusClosureAdapter:
    """IntentClosure that drives ServiceCatalogEngine request lifecycle.

    OPT-IN. Maps intent_id == request_id:

      is_open(request_id)
          -> request exists AND status not in _REQUEST_TERMINAL
      close_success(request_id, reason)
          -> _update_request_status(request_id, FULFILLED)
      close_precondition_failed(request_id, reason)
          -> _update_request_status(request_id, CANCELLED,
                                    cancelled_by="intent_substrate")

    Both transitions go through the catalog's internal
    `_update_request_status` helper - the same one the inline auto-
    fulfill at service_catalog.py:660 uses for FULFILLED. We do NOT use
    the public `cancel_request` for the failure path because it carries
    user-authorization and active-task guards that don't apply to a
    substrate-determined precondition failure (a system event, not a
    user cancellation). Going through the internal helper keeps the
    semantics consistent with the existing inline fulfillment path.

    This adapter does not modify or disable the catalog's inline auto-
    fulfill. A caller wires it explicitly to route one request's
    fulfillment through the substrate; the catalog's own logic still
    handles every request not routed this way.
    """

    def __init__(self, catalog: ServiceCatalogEngine) -> None:
        self._catalog = catalog

    def is_open(self, request_id: EntityId) -> bool:
        try:
            req = self._catalog.get_request(request_id)
        except RuntimeCoreInvariantError:
            return False
        return req.status not in _REQUEST_TERMINAL

    def close_success(self, request_id: EntityId, reason: str) -> ServiceRequest:
        return self._catalog._update_request_status(
            request_id, RequestStatus.FULFILLED
        )

    def close_precondition_failed(
        self, request_id: EntityId, reason: str
    ) -> ServiceRequest:
        return self._catalog._update_request_status(
            request_id,
            RequestStatus.CANCELLED,
            cancelled_by="intent_substrate",
        )
