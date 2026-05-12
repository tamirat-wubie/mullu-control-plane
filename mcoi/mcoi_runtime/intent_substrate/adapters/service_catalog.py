"""ServiceCatalogStateView — adapter that exposes ServiceCatalogEngine
tasks and requests as queryable entities for predicate evaluation.

Entity ID convention:
    "task:<task_id>"      -> FulfillmentTask attributes
    "request:<request_id>" -> ServiceRequest attributes

Returned attribute mappings are stable, JSON-serializable, and
contain only the fields predicates are likely to reference. Missing
or unknown IDs return None (the StateView contract for "absent").

Why this and not RequestStatusClosureAdapter (yet):
    The catalog already has inline auto-fulfill logic at
    service_catalog.py:660 that calls _update_request_status to
    FULFILLED when all tasks complete. Adding a substrate-driven
    closure would race with that. Replacing the inline logic is a
    separate decision worth its own PR — this adapter focuses on the
    safer step: letting substrate intents *observe* catalog state to
    drive other lifecycle (e.g., close an obligation when a request
    fulfills).

If you later want substrate-driven request closure, the adapter
would be ~30 LOC: implement IntentClosure where is_open checks
request.status not in _REQUEST_TERMINAL, close_success calls
catalog._update_request_status(id, RequestStatus.FULFILLED), and
close_precondition_failed calls catalog.cancel_request.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.service_catalog import (
    FulfillmentStatus,
    RequestStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.service_catalog import ServiceCatalogEngine

from ..primitives import EntityId

_TASK_PREFIX = "task:"
_REQUEST_PREFIX = "request:"


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
            "is_terminal": req.status
            in (
                RequestStatus.FULFILLED,
                RequestStatus.DENIED,
                RequestStatus.CANCELLED,
            ),
        }
