"""Tests for RequestStatusClosureAdapter opt-in service request closure.

Purpose: verify that service catalog request status closure can be driven by
the intent substrate without changing the catalog's inline fulfillment path.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, PRS.
Dependencies: ServiceCatalogEngine, EventSpineEngine, IntentResolver, and
MutableState test support.
Invariants: missing requests fail closed, terminal requests stop evaluating,
and two-confirmation stability is required before success closure.

Two layers:
  1. Adapter unit tests - is_open / close_success / close_precondition_failed
     against a real ServiceCatalogEngine.
  2. Integration - a request with no fulfillment tasks whose FULFILLED
     transition is driven entirely by the substrate when an external world
     condition holds.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.service_catalog import (
    CatalogItemKind,
    EntitlementDisposition,
    RequestPriority,
    RequestStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.service_catalog import ServiceCatalogEngine
from mcoi_runtime.intent_substrate import (
    BackgroundTicker,
    EntityAttributeEq,
    IntentResolver,
)
from mcoi_runtime.intent_substrate.adapters.service_catalog import (
    RequestStatusClosureAdapter,
)

from .conftest import MutableState

_OWNER = "alice"
_REQUESTER = "bob"


def _catalog_with_entitled_request() -> tuple[EventSpineEngine, ServiceCatalogEngine]:
    """Return a catalog with one entitled request and no fulfillment tasks."""
    spine = EventSpineEngine()
    catalog = ServiceCatalogEngine(spine)
    catalog.register_catalog_item(
        item_id="svc-vm",
        name="VM provisioning",
        tenant_id="acme",
        kind=CatalogItemKind.INFRASTRUCTURE,
        owner_ref=_OWNER,
        approval_required=False,
    )
    catalog.submit_request(
        request_id="req-1",
        item_id="svc-vm",
        tenant_id="acme",
        requester_ref=_REQUESTER,
        priority=RequestPriority.MEDIUM,
        description="provision VM",
    )
    catalog.evaluate_entitlement(
        rule_id="ent-1",
        request_id="req-1",
        disposition=EntitlementDisposition.GRANTED,
        reason="ok",
    )
    return spine, catalog


def test_is_open_true_for_entitled_request() -> None:
    _spine, catalog = _catalog_with_entitled_request()
    adapter = RequestStatusClosureAdapter(catalog)

    assert catalog.get_request("req-1").status == RequestStatus.ENTITLED
    assert adapter.is_open("req-1") is True


def test_is_open_false_for_missing_request() -> None:
    _spine, catalog = _catalog_with_entitled_request()
    adapter = RequestStatusClosureAdapter(catalog)

    assert adapter.is_open("nonexistent") is False


def test_is_open_false_after_fulfilled() -> None:
    _spine, catalog = _catalog_with_entitled_request()
    adapter = RequestStatusClosureAdapter(catalog)

    adapter.close_success("req-1", "done")

    assert catalog.get_request("req-1").status == RequestStatus.FULFILLED
    assert adapter.is_open("req-1") is False


def test_close_success_transitions_to_fulfilled() -> None:
    _spine, catalog = _catalog_with_entitled_request()
    adapter = RequestStatusClosureAdapter(catalog)

    updated = adapter.close_success("req-1", "predicates confirmed")

    assert updated.status == RequestStatus.FULFILLED
    assert catalog.get_request("req-1").status == RequestStatus.FULFILLED


def test_close_precondition_failed_transitions_to_cancelled() -> None:
    _spine, catalog = _catalog_with_entitled_request()
    adapter = RequestStatusClosureAdapter(catalog)

    updated = adapter.close_precondition_failed("req-1", "precondition failed")

    assert updated.status == RequestStatus.CANCELLED
    assert catalog.get_request("req-1").status == RequestStatus.CANCELLED
    assert adapter.is_open("req-1") is False


def _wait_for(predicate: Callable[[], bool], *, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_substrate_drives_request_to_fulfilled_when_world_condition_holds() -> None:
    """Verify an opt-in request can be fulfilled by stable substrate evidence."""
    spine, catalog = _catalog_with_entitled_request()
    world = MutableState()

    resolver = IntentResolver(
        state_view=world,
        closure=RequestStatusClosureAdapter(catalog),
        spine=spine,
        confirm_window_s=0.1,
        debounce_window_s=0.0,
    )
    resolver.register_intent(
        "req-1",
        preconditions=(),
        success=(
            EntityAttributeEq(
                "provisioning:vm-1",
                "done",
                True,
                watches_kinds=(EventType.WORLD_STATE_CHANGED,),
            ),
        ),
    )

    with BackgroundTicker(resolver, interval_s=0.02):
        resolver.evaluate("req-1")
        assert catalog.get_request("req-1").status == RequestStatus.ENTITLED
        assert resolver.pending_count() == 0

        world.set("provisioning:vm-1", {"done": True})
        resolver.evaluate("req-1")
        assert resolver.pending_count() == 1

        assert _wait_for(
            lambda: catalog.get_request("req-1").status == RequestStatus.FULFILLED,
            timeout_s=1.5,
        ), (
            "request never fulfilled - status is "
            f"{catalog.get_request('req-1').status}"
        )


def test_substrate_cancels_request_on_precondition_failure() -> None:
    spine, catalog = _catalog_with_entitled_request()
    world = MutableState()
    world.set("provisioning:vm-1", {"authorized": False})

    resolver = IntentResolver(
        state_view=world,
        closure=RequestStatusClosureAdapter(catalog),
        spine=spine,
        confirm_window_s=0.1,
        debounce_window_s=0.0,
    )
    resolver.register_intent(
        "req-1",
        preconditions=(
            EntityAttributeEq("provisioning:vm-1", "authorized", True),
        ),
        success=(),
    )

    resolver.evaluate("req-1")

    assert catalog.get_request("req-1").status == RequestStatus.CANCELLED
    assert resolver.pending_count() == 0


def test_substrate_two_confirm_rejects_flapping_world() -> None:
    """Verify a hash change prevents premature request fulfillment."""
    spine, catalog = _catalog_with_entitled_request()
    world = MutableState()
    world.set("provisioning:vm-1", {"done": True})

    resolver = IntentResolver(
        state_view=world,
        closure=RequestStatusClosureAdapter(catalog),
        spine=spine,
        confirm_window_s=10.0,
        debounce_window_s=0.0,
    )
    resolver.register_intent(
        "req-1",
        preconditions=(),
        success=(EntityAttributeEq("provisioning:vm-1", "done", True),),
    )

    resolver.evaluate("req-1")
    assert resolver.pending_count() == 1

    world.update("provisioning:vm-1", touched="x")
    resolver.tick()

    assert catalog.get_request("req-1").status == RequestStatus.ENTITLED
    assert resolver.pending_count() == 1
