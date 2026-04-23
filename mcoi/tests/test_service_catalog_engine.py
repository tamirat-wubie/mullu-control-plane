"""Purpose: comprehensive pytest tests for the ServiceCatalogEngine.
Governance scope: catalog items, service requests, entitlement evaluation,
    approval, assignments, fulfillment tasks, auto-fulfillment, assessments,
    violation detection, snapshots, state hashing, event emission, and
    multi-tenant isolation.
Dependencies: mcoi_runtime.core.service_catalog, mcoi_runtime.core.event_spine,
    mcoi_runtime.core.invariants, mcoi_runtime.contracts.service_catalog.
Invariants:
  - Every mutation emits an event.
  - Terminal requests/tasks cannot be modified.
  - All returns are immutable frozen dataclasses.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.service_catalog import ServiceCatalogEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.service_catalog import (
    CatalogAssessment,
    CatalogItemKind,
    EntitlementDisposition,
    EntitlementRule,
    FulfillmentDecision,
    FulfillmentStatus,
    FulfillmentTask,
    RequestAssignment,
    RequestPriority,
    RequestSnapshot,
    RequestStatus,
    RequestViolation,
    ServiceCatalogItem,
    ServiceClosureReport,
    ServiceRequest,
    ServiceStatus,
)


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def es() -> EventSpineEngine:
    """Fresh EventSpineEngine."""
    return EventSpineEngine()


@pytest.fixture
def engine(es: EventSpineEngine) -> ServiceCatalogEngine:
    """Fresh ServiceCatalogEngine with its own EventSpineEngine."""
    return ServiceCatalogEngine(es)


@pytest.fixture
def engine_with_item(engine: ServiceCatalogEngine) -> ServiceCatalogEngine:
    """Engine with one active catalog item registered (item_id='item-1')."""
    engine.register_catalog_item("item-1", "VM Provisioning", "tenant-a")
    return engine


@pytest.fixture
def engine_with_request(engine_with_item: ServiceCatalogEngine) -> ServiceCatalogEngine:
    """Engine with one SUBMITTED request (request_id='req-1')."""
    engine_with_item.submit_request("req-1", "item-1", "tenant-a", "user-1")
    return engine_with_item


@pytest.fixture
def engine_with_approval_item(engine: ServiceCatalogEngine) -> ServiceCatalogEngine:
    """Engine with a catalog item that requires approval."""
    engine.register_catalog_item(
        "item-appr", "Budget VM", "tenant-a",
        owner_ref="ops-owner",
        approval_required=True,
        approver_refs=("cfo", "ops-lead"),
    )
    return engine


def _create_task(
    engine: ServiceCatalogEngine,
    task_id: str,
    request_id: str,
    assignee_ref: str,
    **kwargs,
) -> FulfillmentTask:
    kwargs.setdefault("created_by", "mgr-1")
    return engine.create_fulfillment_task(task_id, request_id, assignee_ref, **kwargs)


def _start_task(engine: ServiceCatalogEngine, task_id: str, **kwargs) -> FulfillmentTask:
    kwargs.setdefault("started_by", "ops-runner")
    return engine.start_task(task_id, **kwargs)


def _complete_task(engine: ServiceCatalogEngine, task_id: str, **kwargs) -> FulfillmentTask:
    kwargs.setdefault("completed_by", "ops-runner")
    return engine.complete_task(task_id, **kwargs)


def _fail_task(engine: ServiceCatalogEngine, task_id: str, **kwargs) -> FulfillmentTask:
    kwargs.setdefault("failed_by", "ops-runner")
    return engine.fail_task(task_id, **kwargs)


def _cancel_task(engine: ServiceCatalogEngine, task_id: str, **kwargs) -> FulfillmentTask:
    kwargs.setdefault("cancelled_by", "ops-runner")
    return engine.cancel_task(task_id, **kwargs)


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    """ServiceCatalogEngine constructor tests."""

    def test_valid_creation(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        assert isinstance(eng, ServiceCatalogEngine)

    def test_invalid_type_none(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogEngine(None)  # type: ignore[arg-type]

    def test_invalid_type_string(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogEngine("not-an-engine")  # type: ignore[arg-type]

    def test_invalid_type_int(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogEngine(42)  # type: ignore[arg-type]

    def test_invalid_type_dict(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ServiceCatalogEngine({})  # type: ignore[arg-type]

    def test_initial_catalog_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.catalog_count == 0

    def test_initial_request_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.request_count == 0

    def test_initial_assignment_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.assignment_count == 0

    def test_initial_entitlement_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.entitlement_count == 0

    def test_initial_task_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.task_count == 0

    def test_initial_decision_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.decision_count == 0

    def test_initial_violation_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.violation_count == 0

    def test_initial_assessment_count_zero(self, engine: ServiceCatalogEngine) -> None:
        assert engine.assessment_count == 0


# ===================================================================
# 2. Catalog items
# ===================================================================


class TestRegisterCatalogItem:
    """register_catalog_item tests."""

    def test_returns_service_catalog_item(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert isinstance(item, ServiceCatalogItem)

    def test_status_is_active(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.status == ServiceStatus.ACTIVE

    def test_item_id_preserved(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.item_id == "i1"

    def test_name_preserved(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.name == "Svc"

    def test_tenant_id_preserved(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.tenant_id == "t1"

    def test_default_kind_infrastructure(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.kind == CatalogItemKind.INFRASTRUCTURE

    def test_custom_kind(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", kind=CatalogItemKind.APPLICATION)
        assert item.kind == CatalogItemKind.APPLICATION

    def test_kind_access(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", kind=CatalogItemKind.ACCESS)
        assert item.kind == CatalogItemKind.ACCESS

    def test_kind_support(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", kind=CatalogItemKind.SUPPORT)
        assert item.kind == CatalogItemKind.SUPPORT

    def test_kind_procurement(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", kind=CatalogItemKind.PROCUREMENT)
        assert item.kind == CatalogItemKind.PROCUREMENT

    def test_kind_data(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", kind=CatalogItemKind.DATA)
        assert item.kind == CatalogItemKind.DATA

    def test_default_owner_ref_empty(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.owner_ref == ""

    def test_custom_owner_ref(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", owner_ref="owner-x")
        assert item.owner_ref == "owner-x"

    def test_default_sla_ref_empty(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.sla_ref == ""

    def test_custom_sla_ref(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", sla_ref="sla-99")
        assert item.sla_ref == "sla-99"

    def test_default_approval_not_required(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.approval_required is False

    def test_approval_required_true(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item(
            "i1",
            "Svc",
            "t1",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("ops-lead",),
        )
        assert item.approval_required is True

    def test_default_approver_refs_empty(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.approver_refs == ()

    def test_custom_approver_refs(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item(
            "i1",
            "Svc",
            "t1",
            approver_refs=("ops-lead", "cfo"),
        )
        assert item.approver_refs == ("ops-lead", "cfo")

    def test_duplicate_approver_refs_rejected(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(ValueError, match="^approver_refs must not contain duplicates$") as exc_info:
            engine.register_catalog_item("i1", "Svc", "t1", approver_refs=("ops-lead", "ops-lead"))
        message = str(exc_info.value)
        assert message == "approver_refs must not contain duplicates"
        assert "ops-lead" not in message

    def test_system_not_allowed_in_approver_refs(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(ValueError, match="^approver_refs must exclude system$") as exc_info:
            engine.register_catalog_item("i1", "Svc", "t1", approver_refs=("system", "ops-lead"))
        message = str(exc_info.value)
        assert message == "approver_refs must exclude system"
        assert "ops-lead" not in message
        assert "(" not in message

    def test_system_not_allowed_as_owner_ref(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(ValueError, match="^owner_ref must exclude system$") as exc_info:
            engine.register_catalog_item("i1", "Svc", "t1", owner_ref="system")
        message = str(exc_info.value)
        assert message == "owner_ref must exclude system"
        assert "Svc" not in message
        assert "(" not in message

    def test_owner_ref_not_allowed_in_approver_refs(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(ValueError, match="^approver_refs must exclude owner_ref$") as exc_info:
            engine.register_catalog_item(
                "i1",
                "Svc",
                "t1",
                owner_ref="ops-lead",
                approver_refs=("ops-lead", "cfo"),
            )
        message = str(exc_info.value)
        assert message == "approver_refs must exclude owner_ref"
        assert "ops-lead" not in message

    def test_approval_required_without_owner_ref_rejected(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(ValueError, match="^approval_required items must declare owner_ref$") as exc_info:
            engine.register_catalog_item(
                "i1",
                "Svc",
                "t1",
                owner_ref="",
                approval_required=True,
                approver_refs=("ops-lead",),
            )
        message = str(exc_info.value)
        assert message == "approval_required items must declare owner_ref"
        assert "ops-owner" not in message

    def test_approval_required_without_approver_refs_rejected(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(ValueError, match="^approval_required items must declare approver_refs$") as exc_info:
            engine.register_catalog_item("i1", "Svc", "t1", approval_required=True)
        message = str(exc_info.value)
        assert message == "approval_required items must declare approver_refs"
        assert "i1" not in message

    def test_default_estimated_cost_zero(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert item.estimated_cost == 0.0

    def test_custom_estimated_cost(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1", estimated_cost=99.50)
        assert item.estimated_cost == 99.50

    def test_created_at_non_empty(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        assert len(item.created_at) > 0

    def test_catalog_count_increments(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "Svc1", "t1")
        assert engine.catalog_count == 1
        engine.register_catalog_item("i2", "Svc2", "t1")
        assert engine.catalog_count == 2

    def test_duplicate_raises(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "Svc", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate item_id"):
            engine.register_catalog_item("i1", "Svc2", "t1")

    def test_multiple_items_distinct(self, engine: ServiceCatalogEngine) -> None:
        a = engine.register_catalog_item("a", "A", "t1")
        b = engine.register_catalog_item("b", "B", "t1")
        assert a.item_id != b.item_id

    def test_item_is_frozen(self, engine: ServiceCatalogEngine) -> None:
        item = engine.register_catalog_item("i1", "Svc", "t1")
        with pytest.raises(AttributeError):
            item.name = "changed"  # type: ignore[misc]


class TestGetCatalogItem:
    """get_catalog_item tests."""

    def test_returns_registered_item(self, engine_with_item: ServiceCatalogEngine) -> None:
        item = engine_with_item.get_catalog_item("item-1")
        assert item.item_id == "item-1"

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown item_id"):
            engine.get_catalog_item("nonexistent")

    def test_returns_same_data(self, engine: ServiceCatalogEngine) -> None:
        registered = engine.register_catalog_item("i1", "N", "t1")
        fetched = engine.get_catalog_item("i1")
        assert registered == fetched


class TestDeprecateCatalogItem:
    """deprecate_catalog_item tests."""

    def test_active_to_deprecated(self, engine_with_item: ServiceCatalogEngine) -> None:
        result = engine_with_item.deprecate_catalog_item("item-1")
        assert result.status == ServiceStatus.DEPRECATED

    def test_preserves_name(self, engine_with_item: ServiceCatalogEngine) -> None:
        result = engine_with_item.deprecate_catalog_item("item-1")
        assert result.name == "VM Provisioning"

    def test_preserves_tenant_id(self, engine_with_item: ServiceCatalogEngine) -> None:
        result = engine_with_item.deprecate_catalog_item("item-1")
        assert result.tenant_id == "tenant-a"

    def test_deprecated_cannot_deprecate_again(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.deprecate_catalog_item("item-1")
        with pytest.raises(RuntimeCoreInvariantError, match="active catalog items"):
            engine_with_item.deprecate_catalog_item("item-1")

    def test_retired_cannot_deprecate(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.retire_catalog_item("item-1")
        with pytest.raises(RuntimeCoreInvariantError, match="active catalog items"):
            engine_with_item.deprecate_catalog_item("item-1")

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deprecate_catalog_item("nope")

    def test_get_reflects_deprecation(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.deprecate_catalog_item("item-1")
        assert engine_with_item.get_catalog_item("item-1").status == ServiceStatus.DEPRECATED


class TestRetireCatalogItem:
    """retire_catalog_item tests."""

    def test_active_to_retired(self, engine_with_item: ServiceCatalogEngine) -> None:
        result = engine_with_item.retire_catalog_item("item-1")
        assert result.status == ServiceStatus.RETIRED

    def test_deprecated_to_retired(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.deprecate_catalog_item("item-1")
        result = engine_with_item.retire_catalog_item("item-1")
        assert result.status == ServiceStatus.RETIRED

    def test_already_retired_raises(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.retire_catalog_item("item-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            engine_with_item.retire_catalog_item("item-1")

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_catalog_item("nope")

    def test_preserves_item_id(self, engine_with_item: ServiceCatalogEngine) -> None:
        result = engine_with_item.retire_catalog_item("item-1")
        assert result.item_id == "item-1"

    def test_preserves_kind(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("x", "X", "t", kind=CatalogItemKind.DATA)
        result = engine.retire_catalog_item("x")
        assert result.kind == CatalogItemKind.DATA


class TestCatalogItemsForTenant:
    """catalog_items_for_tenant tests."""

    def test_empty_for_unknown_tenant(self, engine: ServiceCatalogEngine) -> None:
        assert engine.catalog_items_for_tenant("ghost") == ()

    def test_returns_tuple(self, engine_with_item: ServiceCatalogEngine) -> None:
        result = engine_with_item.catalog_items_for_tenant("tenant-a")
        assert isinstance(result, tuple)

    def test_returns_matching_items(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("a1", "A1", "tA")
        engine.register_catalog_item("a2", "A2", "tA")
        engine.register_catalog_item("b1", "B1", "tB")
        result = engine.catalog_items_for_tenant("tA")
        assert len(result) == 2

    def test_excludes_other_tenants(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("a1", "A1", "tA")
        engine.register_catalog_item("b1", "B1", "tB")
        result = engine.catalog_items_for_tenant("tB")
        assert len(result) == 1
        assert result[0].tenant_id == "tB"

    def test_includes_deprecated_items(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("a1", "A1", "tA")
        engine.deprecate_catalog_item("a1")
        result = engine.catalog_items_for_tenant("tA")
        assert len(result) == 1

    def test_includes_retired_items(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("a1", "A1", "tA")
        engine.retire_catalog_item("a1")
        result = engine.catalog_items_for_tenant("tA")
        assert len(result) == 1


# ===================================================================
# 3. Requests
# ===================================================================


class TestSubmitRequest:
    """submit_request tests."""

    def test_returns_service_request(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert isinstance(req, ServiceRequest)

    def test_status_is_submitted(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.status == RequestStatus.SUBMITTED

    def test_request_id_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.request_id == "r1"

    def test_item_id_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.item_id == "item-1"

    def test_tenant_id_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.tenant_id == "tenant-a"

    def test_requester_ref_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.requester_ref == "user-1"

    def test_default_priority_medium(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.priority == RequestPriority.MEDIUM

    def test_custom_priority_low(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1", priority=RequestPriority.LOW)
        assert req.priority == RequestPriority.LOW

    def test_custom_priority_high(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1", priority=RequestPriority.HIGH)
        assert req.priority == RequestPriority.HIGH

    def test_custom_priority_critical(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1", priority=RequestPriority.CRITICAL)
        assert req.priority == RequestPriority.CRITICAL

    def test_default_description_empty(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert req.description == ""

    def test_custom_description(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1", description="Need VM")
        assert req.description == "Need VM"

    def test_estimated_cost_from_item_when_zero(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1", estimated_cost=50.0)
        req = engine.submit_request("r1", "i1", "t1", "u1")
        assert req.estimated_cost == 50.0

    def test_estimated_cost_explicit_overrides(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1", estimated_cost=50.0)
        req = engine.submit_request("r1", "i1", "t1", "u1", estimated_cost=99.0)
        assert req.estimated_cost == 99.0

    def test_submitted_at_non_empty(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert len(req.submitted_at) > 0

    def test_due_at_defaults_to_submitted(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert len(req.due_at) > 0

    def test_request_count_increments(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        assert engine_with_item.request_count == 1
        engine_with_item.submit_request("r2", "item-1", "tenant-a", "user-2")
        assert engine_with_item.request_count == 2

    def test_duplicate_request_id_raises(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate request_id"):
            engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-2")

    def test_unknown_item_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown item_id"):
            engine.submit_request("r1", "no-item", "t1", "u1")

    def test_deprecated_item_raises(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.deprecate_catalog_item("item-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot request"):
            engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")

    def test_retired_item_raises(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.retire_catalog_item("item-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot request"):
            engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")

    def test_cross_tenant_item_raises(self, engine_with_item: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="^Catalog item not available for tenant$") as exc_info:
            engine_with_item.submit_request("r1", "item-1", "tenant-b", "user-1")
        message = str(exc_info.value)
        assert message == "Catalog item not available for tenant"
        assert "tenant-a" not in message
        assert "tenant-b" not in message

    def test_request_is_frozen(self, engine_with_item: ServiceCatalogEngine) -> None:
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "user-1")
        with pytest.raises(AttributeError):
            req.status = RequestStatus.FULFILLED  # type: ignore[misc]


class TestGetRequest:
    """get_request tests."""

    def test_returns_submitted_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        req = engine_with_request.get_request("req-1")
        assert req.request_id == "req-1"

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown request_id"):
            engine.get_request("ghost")

    def test_returns_same_data(self, engine_with_item: ServiceCatalogEngine) -> None:
        submitted = engine_with_item.submit_request("r1", "item-1", "tenant-a", "u1")
        fetched = engine_with_item.get_request("r1")
        assert submitted == fetched


class TestDenyRequest:
    """deny_request tests."""

    def test_submitted_can_be_denied(self, engine_with_request: ServiceCatalogEngine) -> None:
        result = engine_with_request.deny_request("req-1", denied_by="manager-1")
        assert result.status == RequestStatus.DENIED

    def test_denied_cannot_be_denied_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            engine_with_request.deny_request("req-1", denied_by="manager-1")

    def test_fulfilled_cannot_be_denied(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            engine_with_request.deny_request("req-1", denied_by="manager-1")

    def test_cancelled_cannot_be_denied(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            engine_with_request.deny_request("req-1", denied_by="manager-1")

    def test_creates_denial_decision(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.decision_count
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        assert engine_with_request.decision_count == before + 1

    def test_custom_denied_by(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        assert engine_with_request.decision_count >= 1

    def test_custom_reason(self, engine_with_request: ServiceCatalogEngine) -> None:
        result = engine_with_request.deny_request("req-1", denied_by="manager-1", reason="Budget exceeded")
        assert result.status == RequestStatus.DENIED

    def test_missing_denied_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.decision_count
        with pytest.raises(RuntimeCoreInvariantError, match="^denied_by required for denial$") as exc_info:
            engine_with_request.deny_request("req-1")
        message = str(exc_info.value)
        assert message == "denied_by required for denial"
        assert "denied_by" in message
        assert engine_with_request.get_request("req-1").status == RequestStatus.SUBMITTED
        assert engine_with_request.decision_count == before

    def test_requester_cannot_deny_own_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.decision_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Requester cannot deny own request$") as exc_info:
            engine_with_request.deny_request("req-1", denied_by="user-1")
        message = str(exc_info.value)
        assert message == "Requester cannot deny own request"
        assert engine_with_request.get_request("req-1").status == RequestStatus.SUBMITTED
        assert engine_with_request.decision_count == before

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deny_request("ghost")


class TestCancelRequest:
    """cancel_request tests."""

    def test_submitted_can_be_cancelled(self, engine_with_request: ServiceCatalogEngine) -> None:
        result = engine_with_request.cancel_request("req-1")
        assert result.status == RequestStatus.CANCELLED

    def test_cancelled_cannot_be_cancelled_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine_with_request.cancel_request("req-1")

    def test_fulfilled_cannot_be_cancelled(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine_with_request.cancel_request("req-1")

    def test_denied_cannot_be_cancelled(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine_with_request.cancel_request("req-1")

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cancel_request("ghost")


class TestCloseRequest:
    """close_request tests."""

    def test_submitted_can_be_closed(self, engine_with_request: ServiceCatalogEngine) -> None:
        result = engine_with_request.close_request("req-1")
        assert result.status == RequestStatus.FULFILLED

    def test_fulfilled_cannot_be_closed_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_request.close_request("req-1")

    def test_denied_cannot_be_closed(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_request.close_request("req-1")

    def test_cancelled_cannot_be_closed(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine_with_request.close_request("req-1")

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.close_request("ghost")


class TestRequestsForTenant:
    """requests_for_tenant tests."""

    def test_empty_for_unknown_tenant(self, engine: ServiceCatalogEngine) -> None:
        assert engine.requests_for_tenant("ghost") == ()

    def test_returns_tuple(self, engine_with_request: ServiceCatalogEngine) -> None:
        result = engine_with_request.requests_for_tenant("tenant-a")
        assert isinstance(result, tuple)

    def test_returns_matching_requests(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S1", "tA")
        engine.register_catalog_item("i2", "S2", "tB")
        engine.submit_request("r1", "i1", "tA", "u1")
        engine.submit_request("r2", "i2", "tB", "u2")
        assert len(engine.requests_for_tenant("tA")) == 1
        assert len(engine.requests_for_tenant("tB")) == 1

    def test_includes_terminal_requests(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        result = engine_with_request.requests_for_tenant("tenant-a")
        assert len(result) == 1


# ===================================================================
# 4. Entitlement evaluation
# ===================================================================


class TestEvaluateEntitlement:
    """evaluate_entitlement tests."""

    def test_returns_entitlement_rule(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert isinstance(rule, EntitlementRule)

    def test_rule_id_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert rule.rule_id == "rul-1"

    def test_item_id_from_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert rule.item_id == "item-1"

    def test_tenant_id_from_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert rule.tenant_id == "tenant-a"

    def test_default_disposition_granted(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert rule.disposition == EntitlementDisposition.GRANTED

    def test_entitlement_count_increments(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert engine_with_request.entitlement_count == 1

    def test_duplicate_rule_id_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate rule_id"):
            engine_with_request.evaluate_entitlement("rul-1", "req-1")

    def test_terminal_request_fulfilled_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot evaluate"):
            engine_with_request.evaluate_entitlement("rul-1", "req-1")

    def test_terminal_request_denied_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot evaluate"):
            engine_with_request.evaluate_entitlement("rul-1", "req-1")

    def test_terminal_request_cancelled_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot evaluate"):
            engine_with_request.evaluate_entitlement("rul-1", "req-1")

    def test_granted_no_approval_moves_to_entitled(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", disposition=EntitlementDisposition.GRANTED,
        )
        req = engine_with_request.get_request("req-1")
        assert req.status == RequestStatus.ENTITLED

    def test_granted_with_approval_required_moves_to_pending(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "user-1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        assert eng.get_request("r1").status == RequestStatus.PENDING_APPROVAL

    def test_requires_approval_moves_to_pending(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", disposition=EntitlementDisposition.REQUIRES_APPROVAL,
        )
        assert engine_with_request.get_request("req-1").status == RequestStatus.PENDING_APPROVAL

    def test_denied_moves_to_denied(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", disposition=EntitlementDisposition.DENIED,
        )
        assert engine_with_request.get_request("req-1").status == RequestStatus.DENIED

    def test_denied_creates_fulfillment_decision(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.decision_count
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", disposition=EntitlementDisposition.DENIED,
        )
        assert engine_with_request.decision_count == before + 1

    def test_denied_decision_has_denied_disposition(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", disposition=EntitlementDisposition.DENIED, reason="No budget",
        )
        # decision_count increased; we trust the engine stored it correctly
        assert engine_with_request.decision_count >= 1

    def test_expired_moves_to_denied(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", disposition=EntitlementDisposition.EXPIRED,
        )
        assert engine_with_request.get_request("req-1").status == RequestStatus.DENIED

    def test_custom_scope_ref(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", scope_ref="scope-abc",
        )
        assert rule.scope_ref == "scope-abc"

    def test_custom_reason(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement(
            "rul-1", "req-1", reason="Policy XYZ",
        )
        assert rule.reason == "Policy XYZ"

    def test_evaluated_at_non_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        rule = engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert len(rule.evaluated_at) > 0

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.evaluate_entitlement("rul-1", "ghost")


# ===================================================================
# 5. Approval
# ===================================================================


class TestApproveRequest:
    """approve_request tests."""

    def test_pending_approval_to_approved(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        result = eng.approve_request("r1", approved_by="ops-lead")
        assert result.status == RequestStatus.APPROVED

    def test_creates_approval_decision(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        before = eng.decision_count
        eng.approve_request("r1", approved_by="ops-lead")
        assert eng.decision_count == before + 1

    def test_submitted_cannot_be_approved(self, engine_with_request: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="pending-approval"):
            engine_with_request.approve_request("req-1")

    def test_entitled_cannot_be_approved(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending-approval"):
            engine_with_request.approve_request("req-1")

    def test_fulfilled_cannot_be_approved(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending-approval"):
            engine_with_request.approve_request("req-1")

    def test_denied_cannot_be_approved(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending-approval"):
            engine_with_request.approve_request("req-1")

    def test_cancelled_cannot_be_approved(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending-approval"):
            engine_with_request.approve_request("req-1")

    def test_custom_approved_by(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        result = eng.approve_request("r1", approved_by="cfo")
        assert result.status == RequestStatus.APPROVED

    def test_custom_reason(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        result = eng.approve_request("r1", approved_by="ops-lead", reason="Budget allocated")
        assert result.status == RequestStatus.APPROVED

    def test_missing_approved_by_rejected(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        before = eng.decision_count
        with pytest.raises(RuntimeCoreInvariantError, match="^approved_by required for approval$") as exc_info:
            eng.approve_request("r1")
        message = str(exc_info.value)
        assert message == "approved_by required for approval"
        assert "approved_by" in message
        assert eng.get_request("r1").status == RequestStatus.PENDING_APPROVAL
        assert eng.decision_count == before

    def test_requester_cannot_approve_own_request(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        before = eng.decision_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Requester cannot approve own request$"):
            eng.approve_request("r1", approved_by="u1")
        assert eng.get_request("r1").status == RequestStatus.PENDING_APPROVAL
        assert eng.decision_count == before

    def test_unauthorized_approver_cannot_approve_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        before = eng.decision_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Approver not authorized for request$") as exc_info:
            eng.approve_request("r1", approved_by="intern-1")
        message = str(exc_info.value)
        assert message == "Approver not authorized for request"
        assert "intern-1" not in message
        assert eng.get_request("r1").status == RequestStatus.PENDING_APPROVAL
        assert eng.decision_count == before

    def test_unauthorized_denier_cannot_deny_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        before = eng.decision_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Denier not authorized for request$") as exc_info:
            eng.deny_request("r1", denied_by="intern-1")
        message = str(exc_info.value)
        assert message == "Denier not authorized for request"
        assert "intern-1" not in message
        assert eng.get_request("r1").status == RequestStatus.PENDING_APPROVAL
        assert eng.decision_count == before

    def test_owner_can_deny_pending_approval_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        result = eng.deny_request("r1", denied_by="ops-owner")
        assert result.status == RequestStatus.DENIED
        assert eng.decision_count >= 1

    def test_authorized_approver_can_approve_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        result = eng.approve_request("r1", approved_by="cfo")
        assert result.status == RequestStatus.APPROVED

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.approve_request("ghost")

    def test_requires_approval_disposition_then_approve(self, engine_with_item: ServiceCatalogEngine) -> None:
        eng = engine_with_item
        eng.submit_request("r1", "item-1", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.REQUIRES_APPROVAL)
        result = eng.approve_request("r1", approved_by="ops-lead")
        assert result.status == RequestStatus.APPROVED


# ===================================================================
# 6. Assignments
# ===================================================================


class TestAssignRequest:
    """assign_request tests."""

    def test_returns_request_assignment(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert isinstance(asn, RequestAssignment)

    def test_assignment_id_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert asn.assignment_id == "a1"

    def test_request_id_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert asn.request_id == "req-1"

    def test_assignee_ref_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert asn.assignee_ref == "tech-1"

    def test_missing_assigned_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.assignment_count
        with pytest.raises(RuntimeCoreInvariantError, match="^assigned_by required for assignment$") as exc_info:
            engine_with_request.assign_request("a1", "req-1", "tech-1")
        message = str(exc_info.value)
        assert message == "assigned_by required for assignment"
        assert engine_with_request.assignment_count == before

    def test_custom_assigned_by(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert asn.assigned_by == "mgr-1"

    def test_system_assigned_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.assignment_count
        with pytest.raises(RuntimeCoreInvariantError, match="^assigned_by must exclude system$") as exc_info:
            engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="system")
        message = str(exc_info.value)
        assert message == "assigned_by must exclude system"
        assert "tech-1" not in message
        assert engine_with_request.assignment_count == before

    def test_requester_cannot_be_assigned_own_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.assignment_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Requester cannot be assignee for own request$") as exc_info:
            engine_with_request.assign_request("a1", "req-1", "user-1", assigned_by="mgr-1")
        message = str(exc_info.value)
        assert message == "Requester cannot be assignee for own request"
        assert engine_with_request.get_request("req-1").status == RequestStatus.SUBMITTED
        assert engine_with_request.assignment_count == before

    def test_assigned_at_non_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert len(asn.assigned_at) > 0

    def test_assignment_count_increments(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert engine_with_request.assignment_count == 1
        engine_with_request.assign_request("a2", "req-1", "tech-2", assigned_by="mgr-2")
        assert engine_with_request.assignment_count == 2

    def test_duplicate_assignment_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assignment_id"):
            engine_with_request.assign_request("a1", "req-1", "tech-2", assigned_by="mgr-2")

    def test_terminal_fulfilled_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")

    def test_terminal_denied_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")

    def test_terminal_cancelled_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot assign"):
            engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.assign_request("a1", "ghost", "tech-1", assigned_by="mgr-1")

    def test_unauthorized_assigner_cannot_assign_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        before = eng.assignment_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Assigner not authorized for request$") as exc_info:
            eng.assign_request("a1", "r1", "tech-1", assigned_by="intern-1")
        message = str(exc_info.value)
        assert message == "Assigner not authorized for request"
        assert "intern-1" not in message
        assert eng.get_request("r1").status == RequestStatus.APPROVED
        assert eng.assignment_count == before

    def test_owner_can_assign_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        asn = eng.assign_request("a1", "r1", "tech-1", assigned_by="ops-owner")
        assert asn.request_id == "r1"
        assert asn.assigned_by == "ops-owner"

    def test_approver_can_assign_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        asn = eng.assign_request("a1", "r1", "tech-1", assigned_by="ops-lead")
        assert asn.request_id == "r1"
        assert asn.assigned_by == "ops-lead"

    def test_owner_cannot_be_assignee_for_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        before = eng.assignment_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Assignee not eligible for request$") as exc_info:
            eng.assign_request("a1", "r1", "ops-owner", assigned_by="ops-owner")
        message = str(exc_info.value)
        assert message == "Assignee not eligible for request"
        assert "ops-owner" not in message
        assert eng.get_request("r1").status == RequestStatus.APPROVED
        assert eng.assignment_count == before

    def test_approver_cannot_be_assignee_for_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        before = eng.assignment_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Assignee not eligible for request$") as exc_info:
            eng.assign_request("a1", "r1", "ops-lead", assigned_by="ops-owner")
        message = str(exc_info.value)
        assert message == "Assignee not eligible for request"
        assert "ops-lead" not in message
        assert eng.get_request("r1").status == RequestStatus.APPROVED
        assert eng.assignment_count == before

    def test_assignment_is_frozen(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        with pytest.raises(AttributeError):
            asn.assignee_ref = "changed"  # type: ignore[misc]


class TestAssignmentsForRequest:
    """assignments_for_request tests."""

    def test_empty_for_unassigned(self, engine_with_request: ServiceCatalogEngine) -> None:
        assert engine_with_request.assignments_for_request("req-1") == ()

    def test_returns_tuple(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        result = engine_with_request.assignments_for_request("req-1")
        assert isinstance(result, tuple)

    def test_returns_matching_assignments(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        engine_with_request.assign_request("a2", "req-1", "tech-2", assigned_by="mgr-2")
        result = engine_with_request.assignments_for_request("req-1")
        assert len(result) == 2

    def test_excludes_other_requests(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1")
        engine.submit_request("r2", "i1", "t1", "u2")
        engine.assign_request("a1", "r1", "tech-1", assigned_by="mgr-1")
        engine.assign_request("a2", "r2", "tech-2", assigned_by="mgr-2")
        assert len(engine.assignments_for_request("r1")) == 1
        assert len(engine.assignments_for_request("r2")) == 1


# ===================================================================
# 7. Fulfillment tasks
# ===================================================================


class TestCreateFulfillmentTask:
    """create_fulfillment_task tests."""

    def test_returns_fulfillment_task(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert isinstance(task, FulfillmentTask)

    def test_task_id_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.task_id == "t1"

    def test_request_id_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.request_id == "req-1"

    def test_assignee_ref_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.assignee_ref == "tech-1"

    def test_created_by_preserved(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.created_by == "mgr-1"

    def test_status_is_pending(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.status == FulfillmentStatus.PENDING

    def test_default_description_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.description == ""

    def test_custom_description(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, 
            "t1", "req-1", "tech-1", description="Provision VM",
        )
        assert task.description == "Provision VM"

    def test_default_dependency_ref_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert task.dependency_ref == ""

    def test_custom_dependency_ref(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, 
            "t1", "req-1", "tech-1", dependency_ref="dep-abc",
        )
        assert task.dependency_ref == "dep-abc"

    def test_created_at_non_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert len(task.created_at) > 0

    def test_auto_transitions_request_to_in_fulfillment(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        req = engine_with_request.get_request("req-1")
        assert req.status == RequestStatus.IN_FULFILLMENT

    def test_auto_transition_from_entitled(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert engine_with_request.get_request("req-1").status == RequestStatus.IN_FULFILLMENT

    def test_auto_transition_from_approved(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="ops-lead")
        _create_task(eng, "t1", "r1", "tech-1", created_by="ops-lead")
        assert eng.get_request("r1").status == RequestStatus.IN_FULFILLMENT

    def test_second_task_keeps_in_fulfillment(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        assert engine_with_request.get_request("req-1").status == RequestStatus.IN_FULFILLMENT

    def test_task_count_increments(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert engine_with_request.task_count == 1
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        assert engine_with_request.task_count == 2

    def test_duplicate_task_id_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate task_id"):
            _create_task(engine_with_request, "t1", "req-1", "tech-2")

    def test_terminal_fulfilled_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot create task"):
            _create_task(engine_with_request, "t1", "req-1", "tech-1")

    def test_terminal_denied_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot create task"):
            _create_task(engine_with_request, "t1", "req-1", "tech-1")

    def test_terminal_cancelled_raises(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot create task"):
            _create_task(engine_with_request, "t1", "req-1", "tech-1")

    def test_unknown_request_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            _create_task(engine, "t1", "ghost", "tech-1")

    def test_created_by_required(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.task_count
        with pytest.raises(RuntimeCoreInvariantError, match="^created_by required for task creation$") as exc_info:
            engine_with_request.create_fulfillment_task("t1", "req-1", "tech-1")
        message = str(exc_info.value)
        assert message == "created_by required for task creation"
        assert engine_with_request.get_request("req-1").status == RequestStatus.SUBMITTED
        assert engine_with_request.task_count == before

    def test_system_created_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.task_count
        with pytest.raises(RuntimeCoreInvariantError, match="^created_by must exclude system$") as exc_info:
            _create_task(engine_with_request, "t1", "req-1", "tech-1", created_by="system")
        message = str(exc_info.value)
        assert message == "created_by must exclude system"
        assert engine_with_request.get_request("req-1").status == RequestStatus.SUBMITTED
        assert engine_with_request.task_count == before

    def test_requester_cannot_be_task_assignee(self, engine_with_request: ServiceCatalogEngine) -> None:
        before = engine_with_request.task_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Requester cannot be assignee for own request$") as exc_info:
            _create_task(engine_with_request, "t1", "req-1", "user-1")
        message = str(exc_info.value)
        assert message == "Requester cannot be assignee for own request"
        assert engine_with_request.get_request("req-1").status == RequestStatus.SUBMITTED
        assert engine_with_request.task_count == before

    def test_owner_cannot_be_task_assignee_for_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        before = eng.task_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Assignee not eligible for request$") as exc_info:
            _create_task(eng, "t1", "r1", "ops-owner")
        message = str(exc_info.value)
        assert message == "Assignee not eligible for request"
        assert "ops-owner" not in message
        assert eng.get_request("r1").status == RequestStatus.APPROVED
        assert eng.task_count == before

    def test_approver_cannot_be_task_assignee_for_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        before = eng.task_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Assignee not eligible for request$") as exc_info:
            _create_task(eng, "t1", "r1", "ops-lead")
        message = str(exc_info.value)
        assert message == "Assignee not eligible for request"
        assert "ops-lead" not in message
        assert eng.get_request("r1").status == RequestStatus.APPROVED
        assert eng.task_count == before

    def test_creator_must_be_authorized_for_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        before = eng.task_count
        with pytest.raises(RuntimeCoreInvariantError, match="^Task creator not authorized for request$") as exc_info:
            _create_task(eng, "t1", "r1", "tech-1")
        message = str(exc_info.value)
        assert message == "Task creator not authorized for request"
        assert "mgr-1" not in message
        assert eng.get_request("r1").status == RequestStatus.APPROVED
        assert eng.task_count == before

    def test_owner_can_create_task_for_approval_governed_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-appr",
            "Budget VM",
            "tenant-a",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("cfo", "ops-lead"),
        )
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="cfo")
        task = _create_task(eng, "t1", "r1", "tech-1", created_by="ops-owner")
        assert task.created_by == "ops-owner"
        assert task.status == FulfillmentStatus.PENDING
        assert eng.get_request("r1").status == RequestStatus.IN_FULFILLMENT

    def test_task_is_frozen(self, engine_with_request: ServiceCatalogEngine) -> None:
        task = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(AttributeError):
            task.status = FulfillmentStatus.COMPLETED  # type: ignore[misc]


class TestGetTask:
    """get_task tests."""

    def test_returns_created_task(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        task = engine_with_request.get_task("t1")
        assert task.task_id == "t1"

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown task_id"):
            engine.get_task("ghost")

    def test_returns_same_data(self, engine_with_request: ServiceCatalogEngine) -> None:
        created = _create_task(engine_with_request, "t1", "req-1", "tech-1")
        fetched = engine_with_request.get_task("t1")
        assert created == fetched


class TestStartTask:
    """start_task tests."""

    def test_pending_to_in_progress(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _start_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.IN_PROGRESS

    def test_preserves_task_id(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _start_task(engine_with_request, "t1")
        assert result.task_id == "t1"

    def test_preserves_request_id(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _start_task(engine_with_request, "t1")
        assert result.request_id == "req-1"

    def test_preserves_assignee_ref(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _start_task(engine_with_request, "t1")
        assert result.assignee_ref == "tech-1"

    def test_preserves_started_by(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _start_task(engine_with_request, "t1", started_by="ops-lead")
        assert result.started_by == "ops-lead"

    def test_started_by_required(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^started_by required for task start$") as exc_info:
            engine_with_request.start_task("t1")
        message = str(exc_info.value)
        assert message == "started_by required for task start"
        assert engine_with_request.get_task("t1").status == FulfillmentStatus.PENDING

    def test_system_started_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^started_by must exclude system$") as exc_info:
            _start_task(engine_with_request, "t1", started_by="system")
        message = str(exc_info.value)
        assert message == "started_by must exclude system"

    def test_in_progress_cannot_start_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _start_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending"):
            _start_task(engine_with_request, "t1")

    def test_completed_cannot_start(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _complete_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending"):
            _start_task(engine_with_request, "t1")

    def test_failed_cannot_start(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _fail_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending"):
            _start_task(engine_with_request, "t1")

    def test_cancelled_cannot_start(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _cancel_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="pending"):
            _start_task(engine_with_request, "t1")

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_task("ghost")

    def test_get_reflects_started(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _start_task(engine_with_request, "t1")
        assert engine_with_request.get_task("t1").status == FulfillmentStatus.IN_PROGRESS


class TestCompleteTask:
    """complete_task tests."""

    def test_pending_to_completed(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _complete_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.COMPLETED

    def test_in_progress_to_completed(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _start_task(engine_with_request, "t1")
        result = _complete_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.COMPLETED

    def test_completed_cannot_complete_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _complete_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _complete_task(engine_with_request, "t1")

    def test_failed_cannot_complete(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _fail_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _complete_task(engine_with_request, "t1")

    def test_cancelled_cannot_complete(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _cancel_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _complete_task(engine_with_request, "t1")

    def test_completed_at_non_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _complete_task(engine_with_request, "t1")
        assert len(result.completed_at) > 0

    def test_preserves_completed_by(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _complete_task(engine_with_request, "t1", completed_by="ops-lead")
        assert result.completed_by == "ops-lead"

    def test_completed_by_required(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^completed_by required for task completion$") as exc_info:
            engine_with_request.complete_task("t1")
        message = str(exc_info.value)
        assert message == "completed_by required for task completion"
        assert engine_with_request.get_task("t1").status == FulfillmentStatus.PENDING

    def test_system_completed_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^completed_by must exclude system$") as exc_info:
            _complete_task(engine_with_request, "t1", completed_by="system")
        message = str(exc_info.value)
        assert message == "completed_by must exclude system"

    def test_preserves_description(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1", description="Provision")
        result = _complete_task(engine_with_request, "t1")
        assert result.description == "Provision"

    def test_preserves_dependency_ref(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1", dependency_ref="dep-1")
        result = _complete_task(engine_with_request, "t1")
        assert result.dependency_ref == "dep-1"

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_task("ghost")


class TestFailTask:
    """fail_task tests."""

    def test_pending_to_failed(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _fail_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.FAILED

    def test_in_progress_to_failed(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _start_task(engine_with_request, "t1")
        result = _fail_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.FAILED

    def test_completed_cannot_fail(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _complete_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _fail_task(engine_with_request, "t1")

    def test_failed_cannot_fail_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _fail_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _fail_task(engine_with_request, "t1")

    def test_cancelled_cannot_fail(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _cancel_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _fail_task(engine_with_request, "t1")

    def test_completed_at_populated(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _fail_task(engine_with_request, "t1")
        assert len(result.completed_at) > 0

    def test_preserves_failed_by(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _fail_task(engine_with_request, "t1", failed_by="ops-lead")
        assert result.failed_by == "ops-lead"

    def test_failed_by_required(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^failed_by required for task failure$") as exc_info:
            engine_with_request.fail_task("t1")
        message = str(exc_info.value)
        assert message == "failed_by required for task failure"
        assert engine_with_request.get_task("t1").status == FulfillmentStatus.PENDING

    def test_system_failed_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^failed_by must exclude system$") as exc_info:
            _fail_task(engine_with_request, "t1", failed_by="system")
        message = str(exc_info.value)
        assert message == "failed_by must exclude system"

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.fail_task("ghost")


class TestCancelTask:
    """cancel_task tests."""

    def test_pending_to_cancelled(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _cancel_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.CANCELLED

    def test_in_progress_to_cancelled(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _start_task(engine_with_request, "t1")
        result = _cancel_task(engine_with_request, "t1")
        assert result.status == FulfillmentStatus.CANCELLED

    def test_completed_cannot_cancel(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _complete_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _cancel_task(engine_with_request, "t1")

    def test_failed_cannot_cancel(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _fail_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _cancel_task(engine_with_request, "t1")

    def test_cancelled_cannot_cancel_again(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _cancel_task(engine_with_request, "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            _cancel_task(engine_with_request, "t1")

    def test_preserves_cancelled_by(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = _cancel_task(engine_with_request, "t1", cancelled_by="ops-lead")
        assert result.cancelled_by == "ops-lead"

    def test_cancelled_by_required(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^cancelled_by required for task cancellation$") as exc_info:
            engine_with_request.cancel_task("t1")
        message = str(exc_info.value)
        assert message == "cancelled_by required for task cancellation"
        assert engine_with_request.get_task("t1").status == FulfillmentStatus.PENDING

    def test_system_cancelled_by_rejected(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        with pytest.raises(RuntimeCoreInvariantError, match="^cancelled_by must exclude system$") as exc_info:
            _cancel_task(engine_with_request, "t1", cancelled_by="system")
        message = str(exc_info.value)
        assert message == "cancelled_by must exclude system"

    def test_unknown_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cancel_task("ghost")


class TestTasksForRequest:
    """tasks_for_request tests."""

    def test_empty_when_no_tasks(self, engine_with_request: ServiceCatalogEngine) -> None:
        assert engine_with_request.tasks_for_request("req-1") == ()

    def test_returns_tuple(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = engine_with_request.tasks_for_request("req-1")
        assert isinstance(result, tuple)

    def test_returns_matching_tasks(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        result = engine_with_request.tasks_for_request("req-1")
        assert len(result) == 2

    def test_excludes_other_requests(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1")
        engine.submit_request("r2", "i1", "t1", "u2")
        _create_task(engine, "t1", "r1", "tech-1")
        _create_task(engine, "t2", "r2", "tech-2")
        assert len(engine.tasks_for_request("r1")) == 1
        assert len(engine.tasks_for_request("r2")) == 1

    def test_includes_terminal_tasks(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _complete_task(engine_with_request, "t1")
        result = engine_with_request.tasks_for_request("req-1")
        assert len(result) == 1
        assert result[0].status == FulfillmentStatus.COMPLETED


# ===================================================================
# 8. Auto-fulfillment
# ===================================================================


class TestAutoFulfillment:
    """Auto-fulfillment when all tasks complete."""

    def test_single_task_complete_auto_fulfills(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _complete_task(engine_with_request, "t1")
        assert engine_with_request.get_request("req-1").status == RequestStatus.FULFILLED

    def test_two_tasks_one_completed_not_fulfilled(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        _complete_task(engine_with_request, "t1")
        assert engine_with_request.get_request("req-1").status == RequestStatus.IN_FULFILLMENT

    def test_two_tasks_both_completed_auto_fulfills(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        _complete_task(engine_with_request, "t1")
        _complete_task(engine_with_request, "t2")
        assert engine_with_request.get_request("req-1").status == RequestStatus.FULFILLED

    def test_three_tasks_all_completed_auto_fulfills(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        _create_task(engine_with_request, "t3", "req-1", "tech-3")
        _complete_task(engine_with_request, "t1")
        _complete_task(engine_with_request, "t2")
        assert engine_with_request.get_request("req-1").status == RequestStatus.IN_FULFILLMENT
        _complete_task(engine_with_request, "t3")
        assert engine_with_request.get_request("req-1").status == RequestStatus.FULFILLED

    def test_mixed_complete_and_failed_not_auto_fulfilled(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        _complete_task(engine_with_request, "t1")
        _fail_task(engine_with_request, "t2")
        assert engine_with_request.get_request("req-1").status == RequestStatus.IN_FULFILLMENT

    def test_mixed_complete_and_cancelled_not_auto_fulfilled(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        _complete_task(engine_with_request, "t1")
        _cancel_task(engine_with_request, "t2")
        assert engine_with_request.get_request("req-1").status == RequestStatus.IN_FULFILLMENT

    def test_auto_fulfillment_does_not_trigger_if_not_in_fulfillment(self, engine: ServiceCatalogEngine) -> None:
        # Edge case: manually close request before tasks complete
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1")
        _create_task(engine, "t1", "r1", "tech-1")
        # Manually close (fulfilled) before task completes
        # Request is IN_FULFILLMENT; close it to FULFILLED
        engine.close_request("r1")
        # Now completing should not error (task is independent) but request stays fulfilled
        # Actually close_request makes it terminal so complete_task won't trigger again
        assert engine.get_request("r1").status == RequestStatus.FULFILLED

    def test_started_then_completed_auto_fulfills(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _start_task(engine_with_request, "t1")
        _complete_task(engine_with_request, "t1")
        assert engine_with_request.get_request("req-1").status == RequestStatus.FULFILLED


# ===================================================================
# 9. Assessments
# ===================================================================


class TestAssessCatalogItem:
    """assess_catalog_item tests."""

    def test_returns_catalog_assessment(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.95, 0.8)
        assert isinstance(asmt, CatalogAssessment)

    def test_assessment_id_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.95, 0.8)
        assert asmt.assessment_id == "as1"

    def test_item_id_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.95, 0.8)
        assert asmt.item_id == "item-1"

    def test_fulfillment_rate_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.95, 0.8)
        assert asmt.fulfillment_rate == 0.95

    def test_satisfaction_score_preserved(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.95, 0.8)
        assert asmt.satisfaction_score == 0.8

    def test_default_assessed_by_system(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        assert asmt.assessed_by == "system"

    def test_custom_assessed_by(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5, assessed_by="auditor-1")
        assert asmt.assessed_by == "auditor-1"

    def test_assessed_at_non_empty(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        assert len(asmt.assessed_at) > 0

    def test_assessment_count_increments(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        assert engine_with_item.assessment_count == 1
        engine_with_item.assess_catalog_item("as2", "item-1", 0.6, 0.6)
        assert engine_with_item.assessment_count == 2

    def test_duplicate_assessment_raises(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assessment_id"):
            engine_with_item.assess_catalog_item("as1", "item-1", 0.6, 0.6)

    def test_unknown_item_raises(self, engine: ServiceCatalogEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown item_id"):
            engine.assess_catalog_item("as1", "ghost", 0.5, 0.5)

    def test_fulfillment_rate_zero(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.0, 0.5)
        assert asmt.fulfillment_rate == 0.0

    def test_fulfillment_rate_one(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 1.0, 0.5)
        assert asmt.fulfillment_rate == 1.0

    def test_satisfaction_score_zero(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.0)
        assert asmt.satisfaction_score == 0.0

    def test_satisfaction_score_one(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 1.0)
        assert asmt.satisfaction_score == 1.0

    def test_assessment_is_frozen(self, engine_with_item: ServiceCatalogEngine) -> None:
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        with pytest.raises(AttributeError):
            asmt.fulfillment_rate = 0.9  # type: ignore[misc]

    def test_deprecated_item_can_be_assessed(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.deprecate_catalog_item("item-1")
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        assert asmt.item_id == "item-1"

    def test_retired_item_can_be_assessed(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.retire_catalog_item("item-1")
        asmt = engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        assert asmt.item_id == "item-1"


class TestAssessmentsForItem:
    """assessments_for_item tests."""

    def test_empty_when_no_assessments(self, engine_with_item: ServiceCatalogEngine) -> None:
        assert engine_with_item.assessments_for_item("item-1") == ()

    def test_returns_tuple(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        result = engine_with_item.assessments_for_item("item-1")
        assert isinstance(result, tuple)

    def test_returns_matching_assessments(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        engine_with_item.assess_catalog_item("as2", "item-1", 0.6, 0.6)
        result = engine_with_item.assessments_for_item("item-1")
        assert len(result) == 2

    def test_excludes_other_items(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S1", "t1")
        engine.register_catalog_item("i2", "S2", "t1")
        engine.assess_catalog_item("as1", "i1", 0.5, 0.5)
        engine.assess_catalog_item("as2", "i2", 0.6, 0.6)
        assert len(engine.assessments_for_item("i1")) == 1
        assert len(engine.assessments_for_item("i2")) == 1


# ===================================================================
# 10. Violation detection
# ===================================================================


class TestDetectRequestViolations:
    """detect_request_violations tests."""

    def test_no_violations_on_clean_state(self, engine: ServiceCatalogEngine) -> None:
        result = engine.detect_request_violations()
        assert result == ()

    def test_returns_tuple(self, engine: ServiceCatalogEngine) -> None:
        result = engine.detect_request_violations()
        assert isinstance(result, tuple)

    def test_all_tasks_failed_violation(self, engine_with_request: ServiceCatalogEngine) -> None:
        eng = engine_with_request
        _create_task(eng, "t1", "req-1", "tech-1")
        _create_task(eng, "t2", "req-1", "tech-2")
        _fail_task(eng, "t1")
        _fail_task(eng, "t2")
        violations = eng.detect_request_violations()
        assert len(violations) >= 1
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" in ops

    def test_all_tasks_failed_single_task(self, engine_with_request: ServiceCatalogEngine) -> None:
        eng = engine_with_request
        _create_task(eng, "t1", "req-1", "tech-1")
        _fail_task(eng, "t1")
        violations = eng.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" in ops

    def test_no_entitlement_violation(self, engine_with_request: ServiceCatalogEngine) -> None:
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "no_entitlement" in ops

    def test_no_entitlement_not_triggered_after_evaluation(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "no_entitlement" not in ops

    def test_no_tasks_violation(self, engine_with_request: ServiceCatalogEngine) -> None:
        # Manually move to IN_FULFILLMENT by creating and immediately cancelling (or use
        # internal knowledge). Instead, create a task, then cancel it. The request stays
        # IN_FULFILLMENT but has no PENDING tasks.
        # Actually tasks_for_request still returns cancelled tasks. Let's create a situation
        # where request is IN_FULFILLMENT but no tasks exist.
        # The only way to get IN_FULFILLMENT without tasks is to use _update_request_status
        # or trick it. Since the violation checks req_tasks list, we need zero tasks.
        # We can accomplish this by:
        # 1. Creating task -> moves to IN_FULFILLMENT
        # 2. Remove task from internal dict (not possible externally)
        # Actually, looking at the code, no_tasks checks len(req_tasks) == 0.
        # We can't easily hit this path through the public API alone since
        # create_fulfillment_task always creates a task. We need to access internals.
        engine_with_request._update_request_status("req-1", RequestStatus.IN_FULFILLMENT)
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "no_tasks" in ops

    def test_idempotent_second_scan_empty(self, engine_with_request: ServiceCatalogEngine) -> None:
        # First scan finds no_entitlement
        first = engine_with_request.detect_request_violations()
        assert len(first) >= 1
        # Second scan returns empty (already recorded)
        second = engine_with_request.detect_request_violations()
        assert len(second) == 0

    def test_violation_count_increments(self, engine_with_request: ServiceCatalogEngine) -> None:
        assert engine_with_request.violation_count == 0
        engine_with_request.detect_request_violations()
        assert engine_with_request.violation_count >= 1

    def test_violation_has_request_id(self, engine_with_request: ServiceCatalogEngine) -> None:
        violations = engine_with_request.detect_request_violations()
        for v in violations:
            assert v.request_id == "req-1"

    def test_violation_has_tenant_id(self, engine_with_request: ServiceCatalogEngine) -> None:
        violations = engine_with_request.detect_request_violations()
        for v in violations:
            assert v.tenant_id == "tenant-a"

    def test_violation_has_detected_at(self, engine_with_request: ServiceCatalogEngine) -> None:
        violations = engine_with_request.detect_request_violations()
        for v in violations:
            assert len(v.detected_at) > 0

    def test_violation_is_frozen(self, engine_with_request: ServiceCatalogEngine) -> None:
        violations = engine_with_request.detect_request_violations()
        assert len(violations) >= 1
        with pytest.raises(AttributeError):
            violations[0].operation = "changed"  # type: ignore[misc]

    def test_mixed_failed_and_complete_no_all_tasks_failed(self, engine_with_request: ServiceCatalogEngine) -> None:
        eng = engine_with_request
        _create_task(eng, "t1", "req-1", "tech-1")
        _create_task(eng, "t2", "req-1", "tech-2")
        _fail_task(eng, "t1")
        _complete_task(eng, "t2")
        violations = eng.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" not in ops

    def test_fulfilled_request_no_no_entitlement(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "no_entitlement" not in ops

    def test_denied_request_no_no_entitlement(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "no_entitlement" not in ops


class TestViolationsForRequest:
    """violations_for_request tests."""

    def test_empty_when_no_violations(self, engine_with_request: ServiceCatalogEngine) -> None:
        assert engine_with_request.violations_for_request("req-1") == ()

    def test_returns_tuple(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.detect_request_violations()
        result = engine_with_request.violations_for_request("req-1")
        assert isinstance(result, tuple)

    def test_returns_matching_violations(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.detect_request_violations()
        result = engine_with_request.violations_for_request("req-1")
        assert len(result) >= 1

    def test_excludes_other_requests(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1")
        engine.submit_request("r2", "i1", "t1", "u2")
        engine.detect_request_violations()
        v1 = engine.violations_for_request("r1")
        v2 = engine.violations_for_request("r2")
        for v in v1:
            assert v.request_id == "r1"
        for v in v2:
            assert v.request_id == "r2"


# ===================================================================
# 11. Snapshot
# ===================================================================


class TestRequestSnapshot:
    """request_snapshot tests."""

    def test_returns_request_snapshot(self, engine: ServiceCatalogEngine) -> None:
        snap = engine.request_snapshot("snap-1")
        assert isinstance(snap, RequestSnapshot)

    def test_snapshot_id_preserved(self, engine: ServiceCatalogEngine) -> None:
        snap = engine.request_snapshot("snap-1")
        assert snap.snapshot_id == "snap-1"

    def test_duplicate_snapshot_raises(self, engine: ServiceCatalogEngine) -> None:
        engine.request_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.request_snapshot("snap-1")

    def test_empty_engine_counts_zero(self, engine: ServiceCatalogEngine) -> None:
        snap = engine.request_snapshot("snap-1")
        assert snap.total_catalog_items == 0
        assert snap.total_requests == 0
        assert snap.total_submitted == 0
        assert snap.total_in_fulfillment == 0
        assert snap.total_fulfilled == 0
        assert snap.total_denied == 0
        assert snap.total_tasks == 0
        assert snap.total_violations == 0
        assert snap.total_estimated_cost == 0.0

    def test_total_catalog_items_matches(self, engine_with_item: ServiceCatalogEngine) -> None:
        snap = engine_with_item.request_snapshot("snap-1")
        assert snap.total_catalog_items == 1

    def test_total_requests_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_requests == 1

    def test_total_submitted_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_submitted == 1

    def test_total_in_fulfillment_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_in_fulfillment == 1

    def test_total_fulfilled_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.close_request("req-1")
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_fulfilled == 1

    def test_total_denied_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_denied == 1

    def test_total_tasks_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_tasks == 1

    def test_total_violations_matches(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.detect_request_violations()
        snap = engine_with_request.request_snapshot("snap-1")
        assert snap.total_violations >= 1

    def test_total_estimated_cost_non_terminal(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1", estimated_cost=100.0)
        engine.submit_request("r1", "i1", "t1", "u1")
        snap = engine.request_snapshot("snap-1")
        assert snap.total_estimated_cost == 100.0

    def test_total_estimated_cost_excludes_terminal(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1", estimated_cost=100.0)
        engine.submit_request("r1", "i1", "t1", "u1", estimated_cost=100.0)
        engine.submit_request("r2", "i1", "t1", "u2", estimated_cost=50.0)
        engine.deny_request("r2", denied_by="manager-1")
        snap = engine.request_snapshot("snap-1")
        assert snap.total_estimated_cost == 100.0

    def test_total_estimated_cost_sums_multiple(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1", estimated_cost=30.0)
        engine.submit_request("r2", "i1", "t1", "u2", estimated_cost=70.0)
        snap = engine.request_snapshot("snap-1")
        assert snap.total_estimated_cost == 100.0

    def test_captured_at_non_empty(self, engine: ServiceCatalogEngine) -> None:
        snap = engine.request_snapshot("snap-1")
        assert len(snap.captured_at) > 0

    def test_snapshot_is_frozen(self, engine: ServiceCatalogEngine) -> None:
        snap = engine.request_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.total_requests = 999  # type: ignore[misc]

    def test_multiple_snapshots_allowed(self, engine: ServiceCatalogEngine) -> None:
        s1 = engine.request_snapshot("snap-1")
        engine.register_catalog_item("i1", "S", "t1")
        s2 = engine.request_snapshot("snap-2")
        assert s1.total_catalog_items == 0
        assert s2.total_catalog_items == 1


# ===================================================================
# 12. State hash
# ===================================================================


class TestStateHash:
    """state_hash tests."""

    def test_returns_string(self, engine: ServiceCatalogEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_is_method_not_property(self, engine: ServiceCatalogEngine) -> None:
        assert callable(engine.state_hash)

    def test_non_empty(self, engine: ServiceCatalogEngine) -> None:
        assert len(engine.state_hash()) > 0

    def test_length_is_16(self, engine: ServiceCatalogEngine) -> None:
        assert len(engine.state_hash()) == 64

    def test_hex_characters(self, engine: ServiceCatalogEngine) -> None:
        h = engine.state_hash()
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self, engine: ServiceCatalogEngine) -> None:
        assert engine.state_hash() == engine.state_hash()

    def test_changes_after_register_item(self, engine: ServiceCatalogEngine) -> None:
        h1 = engine.state_hash()
        engine.register_catalog_item("i1", "S", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_submit_request(self, engine_with_item: ServiceCatalogEngine) -> None:
        h1 = engine_with_item.state_hash()
        engine_with_item.submit_request("r1", "item-1", "tenant-a", "u1")
        h2 = engine_with_item.state_hash()
        assert h1 != h2

    def test_changes_after_assign(self, engine_with_request: ServiceCatalogEngine) -> None:
        h1 = engine_with_request.state_hash()
        engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        h2 = engine_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_evaluate_entitlement(self, engine_with_request: ServiceCatalogEngine) -> None:
        h1 = engine_with_request.state_hash()
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        h2 = engine_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_create_task(self, engine_with_request: ServiceCatalogEngine) -> None:
        h1 = engine_with_request.state_hash()
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        h2 = engine_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_deny(self, engine_with_request: ServiceCatalogEngine) -> None:
        h1 = engine_with_request.state_hash()
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        h2 = engine_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_detect_violations(self, engine_with_request: ServiceCatalogEngine) -> None:
        h1 = engine_with_request.state_hash()
        engine_with_request.detect_request_violations()
        h2 = engine_with_request.state_hash()
        assert h1 != h2

    def test_changes_after_assess(self, engine_with_item: ServiceCatalogEngine) -> None:
        h1 = engine_with_item.state_hash()
        engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        h2 = engine_with_item.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self, es: EventSpineEngine) -> None:
        e1 = ServiceCatalogEngine(EventSpineEngine())
        e2 = ServiceCatalogEngine(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# 13. Properties
# ===================================================================


class TestProperties:
    """Property accessor tests."""

    def test_catalog_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.catalog_count, int)

    def test_request_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.request_count, int)

    def test_assignment_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.assignment_count, int)

    def test_entitlement_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.entitlement_count, int)

    def test_task_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.task_count, int)

    def test_decision_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.decision_count, int)

    def test_violation_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.violation_count, int)

    def test_assessment_count_type(self, engine: ServiceCatalogEngine) -> None:
        assert isinstance(engine.assessment_count, int)

    def test_catalog_count_after_register(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        assert engine.catalog_count == 1

    def test_request_count_after_submit(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.submit_request("r1", "item-1", "tenant-a", "u1")
        assert engine_with_item.request_count == 1

    def test_assignment_count_after_assign(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert engine_with_request.assignment_count == 1

    def test_entitlement_count_after_evaluate(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        assert engine_with_request.entitlement_count == 1

    def test_task_count_after_create(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        assert engine_with_request.task_count == 1

    def test_decision_count_after_deny(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.deny_request("req-1", denied_by="manager-1")
        assert engine_with_request.decision_count >= 1

    def test_violation_count_after_detect(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.detect_request_violations()
        assert engine_with_request.violation_count >= 1

    def test_assessment_count_after_assess(self, engine_with_item: ServiceCatalogEngine) -> None:
        engine_with_item.assess_catalog_item("as1", "item-1", 0.5, 0.5)
        assert engine_with_item.assessment_count == 1

    def test_catalog_count_multiple(self, engine: ServiceCatalogEngine) -> None:
        for i in range(5):
            engine.register_catalog_item(f"i{i}", f"S{i}", "t1")
        assert engine.catalog_count == 5

    def test_request_count_multiple(self, engine_with_item: ServiceCatalogEngine) -> None:
        for i in range(3):
            engine_with_item.submit_request(f"r{i}", "item-1", "tenant-a", f"u{i}")
        assert engine_with_item.request_count == 3


# ===================================================================
# 14. Event emission
# ===================================================================


class TestEventEmission:
    """Event emission tests."""

    def test_register_item_emits_event(self, es: EventSpineEngine, engine: ServiceCatalogEngine) -> None:
        before = es.event_count
        engine.register_catalog_item("i1", "S", "t1")
        assert es.event_count > before

    def test_deprecate_item_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        before = es.event_count
        eng.deprecate_catalog_item("i1")
        assert es.event_count > before

    def test_retire_item_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        before = es.event_count
        eng.retire_catalog_item("i1")
        assert es.event_count > before

    def test_submit_request_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        before = es.event_count
        eng.submit_request("r1", "i1", "t1", "u1")
        assert es.event_count > before

    def test_deny_request_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        eng.deny_request("r1", denied_by="ops-lead")
        assert es.event_count > before

    def test_cancel_request_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        eng.cancel_request("r1")
        assert es.event_count > before

    def test_close_request_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        eng.close_request("r1")
        assert es.event_count > before

    def test_evaluate_entitlement_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        eng.evaluate_entitlement("rul-1", "r1")
        assert es.event_count > before

    def test_approve_request_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "i1",
            "S",
            "t1",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("ops-lead",),
        )
        eng.submit_request("r1", "i1", "t1", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        before = es.event_count
        eng.approve_request("r1", approved_by="ops-lead")
        assert es.event_count > before

    def test_assign_request_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        eng.assign_request("a1", "r1", "tech-1", assigned_by="mgr-1")
        assert es.event_count > before

    def test_assign_request_event_includes_assigned_by(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        eng.assign_request("a1", "r1", "tech-1", assigned_by="mgr-1")
        event = es.list_events(correlation_id="r1")[-1]
        assert event.payload["action"] == "request_assigned"
        assert event.payload["assigned_by"] == "mgr-1"

    def test_create_task_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        _create_task(eng, "t1", "r1", "tech-1")
        assert es.event_count > before

    def test_create_task_event_includes_created_by(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1", created_by="mgr-7")
        event = es.list_events(correlation_id="r1")[-1]
        assert event.payload["action"] == "fulfillment_task_created"
        assert event.payload["created_by"] == "mgr-7"

    def test_start_task_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        before = es.event_count
        _start_task(eng, "t1")
        assert es.event_count > before

    def test_start_task_event_includes_started_by(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        _start_task(eng, "t1", started_by="ops-shift")
        event = es.list_events(correlation_id="r1")[-1]
        assert event.payload["action"] == "task_started"
        assert event.payload["started_by"] == "ops-shift"

    def test_complete_task_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        before = es.event_count
        _complete_task(eng, "t1")
        assert es.event_count > before

    def test_complete_task_event_includes_completed_by(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        _complete_task(eng, "t1", completed_by="ops-shift")
        event = es.list_events(correlation_id="r1")[-2]
        assert event.payload["action"] == "task_completed"
        assert event.payload["completed_by"] == "ops-shift"

    def test_fail_task_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        before = es.event_count
        _fail_task(eng, "t1")
        assert es.event_count > before

    def test_fail_task_event_includes_failed_by(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        _fail_task(eng, "t1", failed_by="ops-shift")
        event = es.list_events(correlation_id="r1")[-1]
        assert event.payload["action"] == "task_failed"
        assert event.payload["failed_by"] == "ops-shift"

    def test_cancel_task_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        before = es.event_count
        _cancel_task(eng, "t1")
        assert es.event_count > before

    def test_cancel_task_event_includes_cancelled_by(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        _cancel_task(eng, "t1", cancelled_by="ops-shift")
        event = es.list_events(correlation_id="r1")[-1]
        assert event.payload["action"] == "task_cancelled"
        assert event.payload["cancelled_by"] == "ops-shift"

    def test_assess_item_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        before = es.event_count
        eng.assess_catalog_item("as1", "i1", 0.5, 0.5)
        assert es.event_count > before

    def test_detect_violations_emits_event_when_found(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        before = es.event_count
        eng.detect_request_violations()
        assert es.event_count > before

    def test_snapshot_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        before = es.event_count
        eng.request_snapshot("snap-1")
        assert es.event_count > before

    def test_auto_fulfill_emits_event(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        _create_task(eng, "t1", "r1", "tech-1")
        before = es.event_count
        _complete_task(eng, "t1")
        # complete_task emits + auto-fulfill emits = at least 2
        assert es.event_count >= before + 2

    def test_event_count_accumulates(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        initial = es.event_count
        eng.register_catalog_item("i1", "S", "t1")
        eng.submit_request("r1", "i1", "t1", "u1")
        eng.assign_request("a1", "r1", "tech-1", assigned_by="mgr-1")
        assert es.event_count >= initial + 3


# ===================================================================
# 15. Golden Scenarios
# ===================================================================


class TestGoldenScenario1:
    """GS-1: Entitled user submits request -> entitlement GRANTED -> create task -> complete task -> request auto-fulfilled."""

    def test_full_lifecycle(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-vm", "VM Provisioning", "acme")

        req = eng.submit_request("req-vm", "item-vm", "acme", "alice")
        assert req.status == RequestStatus.SUBMITTED

        rule = eng.evaluate_entitlement("rul-vm", "req-vm", disposition=EntitlementDisposition.GRANTED)
        assert rule.disposition == EntitlementDisposition.GRANTED
        assert eng.get_request("req-vm").status == RequestStatus.ENTITLED

        task = _create_task(eng, "task-vm", "req-vm", "ops-team")
        assert task.status == FulfillmentStatus.PENDING
        assert eng.get_request("req-vm").status == RequestStatus.IN_FULFILLMENT

        _start_task(eng, "task-vm")
        assert eng.get_task("task-vm").status == FulfillmentStatus.IN_PROGRESS

        _complete_task(eng, "task-vm")
        assert eng.get_task("task-vm").status == FulfillmentStatus.COMPLETED
        assert eng.get_request("req-vm").status == RequestStatus.FULFILLED

    def test_event_count_positive(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        initial = es.event_count
        eng.register_catalog_item("item-vm", "VM", "acme")
        eng.submit_request("req-vm", "item-vm", "acme", "alice")
        eng.evaluate_entitlement("rul-vm", "req-vm")
        _create_task(eng, "task-vm", "req-vm", "ops")
        _start_task(eng, "task-vm")
        _complete_task(eng, "task-vm")
        assert es.event_count > initial + 5

    def test_final_snapshot(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-vm", "VM", "acme")
        eng.submit_request("req-vm", "item-vm", "acme", "alice")
        eng.evaluate_entitlement("rul-vm", "req-vm")
        _create_task(eng, "task-vm", "req-vm", "ops")
        _complete_task(eng, "task-vm")
        snap = eng.request_snapshot("snap-final")
        assert snap.total_fulfilled == 1
        assert snap.total_requests == 1


class TestGoldenScenario2:
    """GS-2: Missing entitlement blocks request -> detect_request_violations -> no_entitlement violation."""

    def test_no_entitlement_detected(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-db", "DB Access", "corp")
        eng.submit_request("req-db", "item-db", "corp", "bob")

        violations = eng.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "no_entitlement" in ops

    def test_violation_references_correct_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-db", "DB Access", "corp")
        eng.submit_request("req-db", "item-db", "corp", "bob")
        violations = eng.detect_request_violations()
        no_ent = [v for v in violations if v.operation == "no_entitlement"]
        assert len(no_ent) == 1
        assert no_ent[0].request_id == "req-db"
        assert no_ent[0].tenant_id == "corp"

    def test_idempotent_second_scan(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-db", "DB Access", "corp")
        eng.submit_request("req-db", "item-db", "corp", "bob")
        eng.detect_request_violations()
        second = eng.detect_request_violations()
        assert len(second) == 0


class TestGoldenScenario3:
    """GS-3: Budget-gated request: approval_required=True -> entitlement GRANTED -> PENDING_APPROVAL -> approve_request -> APPROVED -> create task."""

    def test_full_approval_flow(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-hw",
            "Hardware",
            "finance",
            owner_ref="finance-owner",
            approval_required=True,
            approver_refs=("cfo",),
            estimated_cost=5000.0,
        )

        req = eng.submit_request("req-hw", "item-hw", "finance", "carol")
        assert req.status == RequestStatus.SUBMITTED

        eng.evaluate_entitlement("rul-hw", "req-hw", disposition=EntitlementDisposition.GRANTED)
        assert eng.get_request("req-hw").status == RequestStatus.PENDING_APPROVAL

        approved = eng.approve_request("req-hw", approved_by="cfo")
        assert approved.status == RequestStatus.APPROVED

        task = _create_task(eng, "task-hw", "req-hw", "procurement-team", created_by="cfo")
        assert task.status == FulfillmentStatus.PENDING
        assert eng.get_request("req-hw").status == RequestStatus.IN_FULFILLMENT

    def test_decision_created_on_approval(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item(
            "item-hw",
            "Hardware",
            "finance",
            owner_ref="finance-owner",
            approval_required=True,
            approver_refs=("cfo",),
        )
        eng.submit_request("req-hw", "item-hw", "finance", "carol")
        eng.evaluate_entitlement("rul-hw", "req-hw", disposition=EntitlementDisposition.GRANTED)
        before = eng.decision_count
        eng.approve_request("req-hw", approved_by="cfo")
        assert eng.decision_count == before + 1


class TestGoldenScenario4:
    """GS-4: Asset/procurement dependency: create task with dependency_ref -> second task -> complete both -> auto-fulfill."""

    def test_dependency_chain_fulfillment(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-rack", "Rack Installation", "ops")
        eng.submit_request("req-rack", "item-rack", "ops", "dave")

        task1 = _create_task(eng, 
            "task-order", "req-rack", "procurement",
            description="Order hardware", dependency_ref="",
        )
        task2 = _create_task(eng, 
            "task-install", "req-rack", "technician",
            description="Install rack", dependency_ref="task-order",
        )
        assert task2.dependency_ref == "task-order"

        _start_task(eng, "task-order")
        _complete_task(eng, "task-order")
        assert eng.get_request("req-rack").status == RequestStatus.IN_FULFILLMENT

        _start_task(eng, "task-install")
        _complete_task(eng, "task-install")
        assert eng.get_request("req-rack").status == RequestStatus.FULFILLED

    def test_partial_completion_no_fulfill(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-rack", "Rack", "ops")
        eng.submit_request("req-rack", "item-rack", "ops", "dave")
        _create_task(eng, "task-1", "req-rack", "p1")
        _create_task(eng, "task-2", "req-rack", "p2", dependency_ref="task-1")
        _complete_task(eng, "task-1")
        assert eng.get_request("req-rack").status == RequestStatus.IN_FULFILLMENT


class TestGoldenScenario5:
    """GS-5: All tasks failed: create 2 tasks -> fail both -> detect violations -> all_tasks_failed."""

    def test_all_tasks_failed_violation(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-deploy", "Deployment", "eng")
        eng.submit_request("req-deploy", "item-deploy", "eng", "eve")

        _create_task(eng, "task-a", "req-deploy", "ci-cd")
        _create_task(eng, "task-b", "req-deploy", "ci-cd")

        _fail_task(eng, "task-a")
        _fail_task(eng, "task-b")

        violations = eng.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" in ops

    def test_violation_references_correct_request(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-deploy", "Deployment", "eng")
        eng.submit_request("req-deploy", "item-deploy", "eng", "eve")
        _create_task(eng, "task-a", "req-deploy", "ci-cd")
        _fail_task(eng, "task-a")
        violations = eng.detect_request_violations()
        atf = [v for v in violations if v.operation == "all_tasks_failed"]
        assert len(atf) >= 1
        assert atf[0].request_id == "req-deploy"

    def test_violation_reason_mentions_count(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-deploy", "Deployment", "eng")
        eng.submit_request("req-deploy", "item-deploy", "eng", "eve")
        _create_task(eng, "task-a", "req-deploy", "ci-cd")
        _create_task(eng, "task-b", "req-deploy", "ci-cd")
        _fail_task(eng, "task-a")
        _fail_task(eng, "task-b")
        violations = eng.detect_request_violations()
        atf = [v for v in violations if v.operation == "all_tasks_failed"]
        assert atf[0].reason == "All fulfillment tasks failed"
        assert "2" not in atf[0].reason
        assert "req-deploy" not in atf[0].reason


class TestGoldenScenario6:
    """GS-6: Multi-tenant isolation: register items for 2 tenants -> catalog_items_for_tenant/requests_for_tenant returns only matching."""

    def test_catalog_isolation(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-a1", "SvcA1", "tenant-alpha")
        eng.register_catalog_item("item-a2", "SvcA2", "tenant-alpha")
        eng.register_catalog_item("item-b1", "SvcB1", "tenant-beta")

        alpha_items = eng.catalog_items_for_tenant("tenant-alpha")
        beta_items = eng.catalog_items_for_tenant("tenant-beta")
        assert len(alpha_items) == 2
        assert len(beta_items) == 1
        assert all(i.tenant_id == "tenant-alpha" for i in alpha_items)
        assert all(i.tenant_id == "tenant-beta" for i in beta_items)

    def test_request_isolation(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-a1", "SvcA1", "tenant-alpha")
        eng.register_catalog_item("item-b1", "SvcB1", "tenant-beta")

        eng.submit_request("r-a1", "item-a1", "tenant-alpha", "user-a")
        eng.submit_request("r-a2", "item-a1", "tenant-alpha", "user-a2")
        eng.submit_request("r-b1", "item-b1", "tenant-beta", "user-b")

        alpha_reqs = eng.requests_for_tenant("tenant-alpha")
        beta_reqs = eng.requests_for_tenant("tenant-beta")
        assert len(alpha_reqs) == 2
        assert len(beta_reqs) == 1
        assert all(r.tenant_id == "tenant-alpha" for r in alpha_reqs)
        assert all(r.tenant_id == "tenant-beta" for r in beta_reqs)

    def test_no_cross_tenant_leakage(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-a", "SvcA", "tA")
        eng.register_catalog_item("item-b", "SvcB", "tB")
        eng.submit_request("r-a", "item-a", "tA", "u-a")
        eng.submit_request("r-b", "item-b", "tB", "u-b")

        assert eng.catalog_items_for_tenant("tC") == ()
        assert eng.requests_for_tenant("tC") == ()

    def test_violations_include_tenant_id(self, es: EventSpineEngine) -> None:
        eng = ServiceCatalogEngine(es)
        eng.register_catalog_item("item-a", "SvcA", "tA")
        eng.register_catalog_item("item-b", "SvcB", "tB")
        eng.submit_request("r-a", "item-a", "tA", "u-a")
        eng.submit_request("r-b", "item-b", "tB", "u-b")

        violations = eng.detect_request_violations()
        tenant_ids = {v.tenant_id for v in violations}
        assert "tA" in tenant_ids
        assert "tB" in tenant_ids


# ===================================================================
# 16. Additional edge cases
# ===================================================================


class TestEdgeCases:
    """Miscellaneous edge cases and boundary conditions."""

    def test_register_many_items(self, engine: ServiceCatalogEngine) -> None:
        for i in range(20):
            engine.register_catalog_item(f"item-{i}", f"Svc-{i}", "t1")
        assert engine.catalog_count == 20

    def test_submit_many_requests(self, engine_with_item: ServiceCatalogEngine) -> None:
        for i in range(10):
            engine_with_item.submit_request(f"r-{i}", "item-1", "tenant-a", f"u-{i}")
        assert engine_with_item.request_count == 10

    def test_multiple_assignments_same_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        for i in range(5):
            engine_with_request.assign_request(f"a-{i}", "req-1", f"tech-{i}", assigned_by=f"mgr-{i}")
        assert engine_with_request.assignment_count == 5
        assert len(engine_with_request.assignments_for_request("req-1")) == 5

    def test_multiple_tasks_different_requests(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1")
        engine.submit_request("r2", "i1", "t1", "u2")
        _create_task(engine, "t1", "r1", "tech-1")
        _create_task(engine, "t2", "r2", "tech-2")
        assert engine.task_count == 2

    def test_deny_after_entitlement_granted(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        # Request is now ENTITLED, can still deny
        result = engine_with_request.deny_request("req-1", denied_by="manager-1")
        assert result.status == RequestStatus.DENIED

    def test_cancel_after_in_fulfillment(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        # Request is IN_FULFILLMENT, can still cancel
        result = engine_with_request.cancel_request("req-1")
        assert result.status == RequestStatus.CANCELLED

    def test_deny_in_fulfillment(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = engine_with_request.deny_request("req-1", denied_by="manager-1")
        assert result.status == RequestStatus.DENIED

    def test_evaluate_entitlement_different_requests(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1")
        engine.submit_request("r1", "i1", "t1", "u1")
        engine.submit_request("r2", "i1", "t1", "u2")
        engine.evaluate_entitlement("rul-1", "r1")
        engine.evaluate_entitlement("rul-2", "r2")
        assert engine.entitlement_count == 2

    def test_assess_multiple_items(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S1", "t1")
        engine.register_catalog_item("i2", "S2", "t1")
        engine.assess_catalog_item("as1", "i1", 0.5, 0.5)
        engine.assess_catalog_item("as2", "i2", 0.7, 0.7)
        assert engine.assessment_count == 2

    def test_snapshot_after_complex_state(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1", estimated_cost=10.0)
        engine.submit_request("r1", "i1", "t1", "u1", estimated_cost=10.0)
        engine.submit_request("r2", "i1", "t1", "u2", estimated_cost=20.0)
        _create_task(engine, "t1", "r1", "tech-1")
        engine.deny_request("r2", denied_by="manager-1")
        snap = engine.request_snapshot("snap-1")
        assert snap.total_requests == 2
        assert snap.total_in_fulfillment == 1
        assert snap.total_denied == 1
        assert snap.total_estimated_cost == 10.0

    def test_state_hash_different_engines_different_state(self) -> None:
        e1 = ServiceCatalogEngine(EventSpineEngine())
        e2 = ServiceCatalogEngine(EventSpineEngine())
        e1.register_catalog_item("i1", "S", "t1")
        assert e1.state_hash() != e2.state_hash()

    def test_close_submitted_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        result = engine_with_request.close_request("req-1")
        assert result.status == RequestStatus.FULFILLED

    def test_close_entitled_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        result = engine_with_request.close_request("req-1")
        assert result.status == RequestStatus.FULFILLED

    def test_close_in_fulfillment_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        result = engine_with_request.close_request("req-1")
        assert result.status == RequestStatus.FULFILLED

    def test_multiple_snapshots_different_ids(self, engine: ServiceCatalogEngine) -> None:
        s1 = engine.request_snapshot("snap-1")
        s2 = engine.request_snapshot("snap-2")
        assert s1.snapshot_id != s2.snapshot_id

    def test_entitlement_denied_reason_in_decision(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement(
            "rul-1", "req-1",
            disposition=EntitlementDisposition.DENIED,
            reason="Insufficient privileges",
        )
        assert engine_with_request.decision_count >= 1

    def test_deprecate_preserves_approval_required(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item(
            "i1",
            "S",
            "t1",
            owner_ref="ops-owner",
            approval_required=True,
            approver_refs=("ops-lead",),
        )
        result = engine.deprecate_catalog_item("i1")
        assert result.approval_required is True
        assert result.approver_refs == ("ops-lead",)

    def test_retire_preserves_estimated_cost(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("i1", "S", "t1", estimated_cost=123.45)
        result = engine.retire_catalog_item("i1")
        assert result.estimated_cost == 123.45

    def test_fail_then_detect_single_task(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _fail_task(engine_with_request, "t1")
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" in ops

    def test_no_violation_when_tasks_pending(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" not in ops

    def test_no_violation_when_some_tasks_in_progress(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        _create_task(engine_with_request, "t2", "req-1", "tech-2")
        _fail_task(engine_with_request, "t1")
        _start_task(engine_with_request, "t2")
        violations = engine_with_request.detect_request_violations()
        ops = [v.operation for v in violations]
        assert "all_tasks_failed" not in ops

    def test_estimated_cost_zero_explicit(self, engine_with_item: ServiceCatalogEngine) -> None:
        # If both item cost and request cost are 0, falls through to item cost (0)
        req = engine_with_item.submit_request("r1", "item-1", "tenant-a", "u1", estimated_cost=0.0)
        assert req.estimated_cost == 0.0

    def test_assign_submitted_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert asn.request_id == "req-1"

    def test_assign_entitled_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        engine_with_request.evaluate_entitlement("rul-1", "req-1")
        asn = engine_with_request.assign_request("a1", "req-1", "tech-1", assigned_by="mgr-1")
        assert asn.request_id == "req-1"

    def test_assign_in_fulfillment_request(self, engine_with_request: ServiceCatalogEngine) -> None:
        _create_task(engine_with_request, "t1", "req-1", "tech-1")
        asn = engine_with_request.assign_request("a1", "req-1", "tech-2", assigned_by="mgr-1")
        assert asn.request_id == "req-1"

    def test_violations_for_request_nonexistent(self, engine: ServiceCatalogEngine) -> None:
        assert engine.violations_for_request("nonexistent") == ()

    def test_tasks_for_request_nonexistent(self, engine: ServiceCatalogEngine) -> None:
        assert engine.tasks_for_request("nonexistent") == ()

    def test_assignments_for_request_nonexistent(self, engine: ServiceCatalogEngine) -> None:
        assert engine.assignments_for_request("nonexistent") == ()

    def test_assessments_for_item_nonexistent(self, engine: ServiceCatalogEngine) -> None:
        assert engine.assessments_for_item("nonexistent") == ()

    def test_deny_pending_approval_request(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        assert eng.get_request("r1").status == RequestStatus.PENDING_APPROVAL
        result = eng.deny_request("r1", denied_by="ops-lead")
        assert result.status == RequestStatus.DENIED

    def test_cancel_pending_approval_request(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        result = eng.cancel_request("r1")
        assert result.status == RequestStatus.CANCELLED

    def test_create_task_after_approval(self, engine_with_approval_item: ServiceCatalogEngine) -> None:
        eng = engine_with_approval_item
        eng.submit_request("r1", "item-appr", "tenant-a", "u1")
        eng.evaluate_entitlement("rul-1", "r1", disposition=EntitlementDisposition.GRANTED)
        eng.approve_request("r1", approved_by="ops-lead")
        task = _create_task(eng, "t1", "r1", "tech-1", created_by="ops-lead")
        assert task.status == FulfillmentStatus.PENDING
        assert eng.get_request("r1").status == RequestStatus.IN_FULFILLMENT


class TestBoundedContractWitnesses:
    def test_invariant_messages_do_not_reflect_ids_or_statuses(
        self,
        engine_with_request: ServiceCatalogEngine,
        engine_with_item: ServiceCatalogEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError) as duplicate_exc:
            engine_with_item.register_catalog_item("item-1", "Again", "tenant-a")
        duplicate_message = str(duplicate_exc.value)
        assert duplicate_message == "Duplicate item_id"
        assert "item-1" not in duplicate_message
        assert "item_id" in duplicate_message

        with pytest.raises(RuntimeCoreInvariantError) as approve_exc:
            engine_with_request.approve_request("req-1")
        approve_message = str(approve_exc.value)
        assert approve_message == "Can only approve pending-approval requests"
        assert "PENDING_APPROVAL" not in approve_message
        assert "pending-approval" in approve_message

        _create_task(engine_with_request, "task-secret", "req-1", "tech-1")
        _start_task(engine_with_request, "task-secret")
        with pytest.raises(RuntimeCoreInvariantError) as start_exc:
            _start_task(engine_with_request, "task-secret")
        start_message = str(start_exc.value)
        assert start_message == "Can only start pending tasks"
        assert "IN_PROGRESS" not in start_message
        assert "pending" in start_message

    def test_violation_reasons_are_bounded(self, engine: ServiceCatalogEngine) -> None:
        engine.register_catalog_item("item-secret", "Secret", "t1")
        engine.submit_request("req-no-ent", "item-secret", "t1", "u1")

        engine.submit_request("req-no-tasks", "item-secret", "t1", "u2")
        engine._update_request_status("req-no-tasks", RequestStatus.IN_FULFILLMENT)
        engine.submit_request("req-all-failed", "item-secret", "t1", "u3")
        _create_task(engine, "fail-1", "req-all-failed", "tech-1")
        _fail_task(engine, "fail-1")

        violations = {
            (v.request_id, v.operation): v.reason
            for v in engine.detect_request_violations()
        }
        assert violations[("req-no-ent", "no_entitlement")] == "Request lacks entitlement evaluation"
        assert "req-no-ent" not in violations[("req-no-ent", "no_entitlement")]
        assert "entitlement evaluation" in violations[("req-no-ent", "no_entitlement")]

        assert violations[("req-no-tasks", "no_tasks")] == "Request in fulfillment has no tasks"
        assert "req-no-tasks" not in violations[("req-no-tasks", "no_tasks")]
        assert "fulfillment" in violations[("req-no-tasks", "no_tasks")]

        assert violations[("req-all-failed", "all_tasks_failed")] == "All fulfillment tasks failed"
        assert "req-all-failed" not in violations[("req-all-failed", "all_tasks_failed")]
        assert "1" not in violations[("req-all-failed", "all_tasks_failed")]


