"""Integration test — substrate observing real ServiceCatalogEngine state.

Demonstrates the substrate's first real consumer: a service catalog
request transitioning through its own internal lifecycle (task
creation -> task completion -> auto-fulfillment) is OBSERVED by an
intent_substrate intent, which then drives a separate obligation to
COMPLETED with two-confirmation safety.

This is not a replacement for the catalog's inline auto-fulfill at
service_catalog.py:660 — it's the layer ABOVE: catalog runs as
before, but higher-level intents can react safely to catalog state
transitions.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.obligation import ObligationState
from mcoi_runtime.contracts.service_catalog import (
    CatalogItemKind,
    EntitlementDisposition,
    RequestPriority,
    RequestStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.service_catalog import ServiceCatalogEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    IntentResolver,
    ObligationClosureAdapter,
    declare_intent,
)
from mcoi_runtime.intent_substrate.adapters.service_catalog import (
    ServiceCatalogStateView,
)

from .conftest import make_deadline, make_owner


# Identities. Constraints in service_catalog enforce:
#   requester_ref != assignee_ref
#   approver/assigner authorization (relaxed when approval_required=False)
_OWNER = "alice"
_REQUESTER = "bob"
_ASSIGNEE = "carol"


def _build_catalog_through_in_fulfillment():
    """Spin up a catalog and drive a request all the way to having a
    PENDING task (request status = IN_FULFILLMENT). Returns the spine,
    catalog, and request.
    """
    spine = EventSpineEngine()
    catalog = ServiceCatalogEngine(spine)

    catalog.register_catalog_item(
        item_id="svc-vm-prov",
        name="VM provisioning",
        tenant_id="acme",
        kind=CatalogItemKind.INFRASTRUCTURE,
        owner_ref=_OWNER,
        approval_required=False,
    )
    request = catalog.submit_request(
        request_id="req-001",
        item_id="svc-vm-prov",
        tenant_id="acme",
        requester_ref=_REQUESTER,
        priority=RequestPriority.MEDIUM,
        description="provision VM",
    )
    catalog.evaluate_entitlement(
        rule_id="ent-1", request_id="req-001",
        disposition=EntitlementDisposition.GRANTED, reason="ok",
    )
    catalog.assign_request(
        assignment_id="asgn-1", request_id="req-001",
        assignee_ref=_ASSIGNEE, assigned_by=_OWNER,
    )
    catalog.create_fulfillment_task(
        task_id="task-1", request_id="req-001",
        assignee_ref=_ASSIGNEE, created_by=_OWNER,
        description="provision",
    )
    return spine, catalog, request


# ---- StateView lookups ----


def test_state_view_returns_task_attributes():
    _spine, catalog, _req = _build_catalog_through_in_fulfillment()
    view = ServiceCatalogStateView(catalog)
    state = view("task:task-1")
    assert state is not None
    assert state["task_id"] == "task-1"
    assert state["status"] == "pending"
    assert state["is_completed"] is False
    assert state["is_terminal"] is False


def test_state_view_returns_request_attributes():
    _spine, catalog, _req = _build_catalog_through_in_fulfillment()
    view = ServiceCatalogStateView(catalog)
    state = view("request:req-001")
    assert state is not None
    assert state["request_id"] == "req-001"
    assert state["is_fulfilled"] is False
    # After task creation the request auto-transitions to IN_FULFILLMENT.
    assert state["status"] == "in_fulfillment"


def test_state_view_returns_none_for_missing_task():
    _spine, catalog, _req = _build_catalog_through_in_fulfillment()
    view = ServiceCatalogStateView(catalog)
    assert view("task:nonexistent") is None


def test_state_view_returns_none_for_missing_request():
    _spine, catalog, _req = _build_catalog_through_in_fulfillment()
    view = ServiceCatalogStateView(catalog)
    assert view("request:nonexistent") is None


def test_state_view_returns_none_for_unknown_prefix():
    _spine, catalog, _req = _build_catalog_through_in_fulfillment()
    view = ServiceCatalogStateView(catalog)
    assert view("widget:foo") is None


def test_state_view_reflects_task_completion_after_mutation():
    _spine, catalog, _req = _build_catalog_through_in_fulfillment()
    catalog.start_task("task-1", started_by=_ASSIGNEE)
    catalog.complete_task("task-1", completed_by=_ASSIGNEE)

    view = ServiceCatalogStateView(catalog)
    state = view("task:task-1")
    assert state["is_completed"] is True
    assert state["status"] == "completed"


# ---- End-to-end: substrate observing catalog drives obligation closure ----


def _wait_for(predicate, *, timeout_s=2.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_request_fulfillment_drives_obligation_completion():
    """The substrate observes catalog tasks completing, sees the
    request reach FULFILLED via the catalog's own auto-fulfill, and
    drives a separate obligation to COMPLETED with two-confirm safety.

    This is the textbook 'react to a real engine's state' pattern.
    """
    spine, catalog, _req = _build_catalog_through_in_fulfillment()

    obligations = ObligationRuntimeEngine()
    resolver = IntentResolver(
        state_view=ServiceCatalogStateView(catalog),
        closure=ObligationClosureAdapter(obligations),
        spine=spine,
        confirm_window_s=0.1,
        debounce_window_s=0.0,
    )

    # Declare an obligation that should close when req-001 reaches
    # FULFILLED. The catalog emits CUSTOM events on every mutation, so
    # predicates watching CUSTOM get re-evaluated whenever the catalog
    # state changes — fine for correctness, modestly inefficient.
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner("ops"), deadline=make_deadline(),
        description="close when req-001 fulfills",
        correlation_id="req-001-followup",
        success=(
            EntityAttributeEq(
                "request:req-001", "is_fulfilled", True,
                watches_kinds=(EventType.CUSTOM,),
            ),
        ),
    )

    seen_event_ids: set[str] = set()

    def drain():
        # Drain newly-emitted spine events into the resolver. Real
        # production would route this via a registered subscription;
        # here we explicitly poll to keep the test direct.
        for ev in spine.list_events():
            if ev.event_id in seen_event_ids:
                continue
            seen_event_ids.add(ev.event_id)
            resolver.on_event(ev)

    drain()  # consume the events from setup

    with BackgroundTicker(resolver, interval_s=0.02):
        catalog.start_task("task-1", started_by=_ASSIGNEE)
        drain()
        # Sanity: request not yet fulfilled (task is just started).
        assert catalog.get_request("req-001").status != RequestStatus.FULFILLED
        assert (
            obligations.get_obligation(obl.obligation_id).state
            == ObligationState.PENDING
        )

        catalog.complete_task("task-1", completed_by=_ASSIGNEE)
        drain()

        # Catalog auto-fulfilled the request (only one task, now COMPLETED).
        assert catalog.get_request("req-001").status == RequestStatus.FULFILLED

        assert _wait_for(
            lambda: obligations.get_obligation(obl.obligation_id).state
            == ObligationState.COMPLETED,
            timeout_s=1.5,
        ), (
            f"obligation never completed — state is "
            f"{obligations.get_obligation(obl.obligation_id).state}"
        )
