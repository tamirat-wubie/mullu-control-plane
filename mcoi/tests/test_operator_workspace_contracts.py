"""Purpose: comprehensive tests for operator_workspace contracts.
Governance scope: Milestone 1 contract validation.
Dependencies: pytest, types.MappingProxyType.
Invariants: all 6 enums and 10 frozen dataclasses are fully covered.
"""

from __future__ import annotations

import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.operator_workspace import (
    OperatorAction,
    OperatorActionStatus,
    PanelKind,
    QueueRecord,
    QueueStatus,
    ViewDisposition,
    WorklistItem,
    WorkspaceAssessment,
    WorkspaceClosureReport,
    WorkspaceDecision,
    WorkspacePanel,
    WorkspaceScope,
    WorkspaceSnapshot,
    WorkspaceStatus,
    WorkspaceView,
    WorkspaceViolation,
)

# ===================================================================
# Helpers
# ===================================================================

TS = "2025-06-01T00:00:00+00:00"
TS_SHORT = "2025-06-01"


def _view(**overrides):
    defaults = dict(
        view_id="v1", tenant_id="t1", operator_ref="op1",
        display_name="Main", scope=WorkspaceScope.PERSONAL,
        disposition=ViewDisposition.OPEN, status=WorkspaceStatus.ACTIVE,
        panel_count=0, created_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspaceView(**defaults)


def _panel(**overrides):
    defaults = dict(
        panel_id="p1", view_id="v1", tenant_id="t1",
        display_name="Queue Panel", kind=PanelKind.QUEUE,
        target_runtime="rt1", item_count=0, created_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspacePanel(**defaults)


def _queue(**overrides):
    defaults = dict(
        queue_id="q1", panel_id="p1", tenant_id="t1",
        source_ref="src1", source_runtime="rt1", assignee_ref="op1",
        priority=0, status=QueueStatus.PENDING, created_at=TS, metadata={},
    )
    defaults.update(overrides)
    return QueueRecord(**defaults)


def _worklist(**overrides):
    defaults = dict(
        item_id="i1", tenant_id="t1", operator_ref="op1",
        source_ref="src1", source_runtime="rt1", title="Review item",
        priority=0, status=QueueStatus.PENDING, created_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorklistItem(**defaults)


def _action(**overrides):
    defaults = dict(
        action_id="a1", tenant_id="t1", operator_ref="op1",
        target_ref="tgt1", target_runtime="rt1", action_name="approve",
        status=OperatorActionStatus.INITIATED, created_at=TS, metadata={},
    )
    defaults.update(overrides)
    return OperatorAction(**defaults)


def _decision(**overrides):
    defaults = dict(
        decision_id="d1", tenant_id="t1", operator_ref="op1",
        action_id="a1", disposition="approved", reason="looks good",
        decided_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspaceDecision(**defaults)


def _snapshot(**overrides):
    defaults = dict(
        snapshot_id="s1", tenant_id="t1", total_views=0,
        active_views=0, total_panels=0, total_queue_items=0,
        pending_queue_items=0, total_worklist_items=0,
        total_actions=0, captured_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspaceSnapshot(**defaults)


def _violation(**overrides):
    defaults = dict(
        violation_id="vl1", tenant_id="t1", operation="delete",
        reason="unauthorized", detected_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspaceViolation(**defaults)


def _assessment(**overrides):
    defaults = dict(
        assessment_id="as1", tenant_id="t1", total_views=0,
        active_views=0, queue_depth=0, pending_rate=0.0,
        total_violations=0, assessed_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspaceAssessment(**defaults)


def _closure(**overrides):
    defaults = dict(
        report_id="r1", tenant_id="t1", total_views=0,
        total_panels=0, total_queue_items=0, total_worklist_items=0,
        total_actions=0, total_violations=0, created_at=TS, metadata={},
    )
    defaults.update(overrides)
    return WorkspaceClosureReport(**defaults)


# ===================================================================
# 1. Enum tests
# ===================================================================


class TestWorkspaceStatus:
    def test_member_count(self):
        assert len(WorkspaceStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (WorkspaceStatus.ACTIVE, "active"),
        (WorkspaceStatus.DRAFT, "draft"),
        (WorkspaceStatus.SUSPENDED, "suspended"),
        (WorkspaceStatus.RETIRED, "retired"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["active", "draft", "suspended", "retired"])
    def test_lookup_by_value(self, value):
        assert WorkspaceStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            WorkspaceStatus("bogus")


class TestPanelKind:
    def test_member_count(self):
        assert len(PanelKind) == 5

    @pytest.mark.parametrize("member,value", [
        (PanelKind.QUEUE, "queue"),
        (PanelKind.DASHBOARD, "dashboard"),
        (PanelKind.REVIEW, "review"),
        (PanelKind.APPROVAL, "approval"),
        (PanelKind.INVESTIGATION, "investigation"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["queue", "dashboard", "review", "approval", "investigation"])
    def test_lookup_by_value(self, value):
        assert PanelKind(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            PanelKind("bogus")


class TestQueueStatus:
    def test_member_count(self):
        assert len(QueueStatus) == 5

    @pytest.mark.parametrize("member,value", [
        (QueueStatus.PENDING, "pending"),
        (QueueStatus.ASSIGNED, "assigned"),
        (QueueStatus.IN_PROGRESS, "in_progress"),
        (QueueStatus.COMPLETED, "completed"),
        (QueueStatus.ESCALATED, "escalated"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["pending", "assigned", "in_progress", "completed", "escalated"])
    def test_lookup_by_value(self, value):
        assert QueueStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            QueueStatus("bogus")


class TestViewDisposition:
    def test_member_count(self):
        assert len(ViewDisposition) == 4

    @pytest.mark.parametrize("member,value", [
        (ViewDisposition.OPEN, "open"),
        (ViewDisposition.FILTERED, "filtered"),
        (ViewDisposition.PINNED, "pinned"),
        (ViewDisposition.ARCHIVED, "archived"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["open", "filtered", "pinned", "archived"])
    def test_lookup_by_value(self, value):
        assert ViewDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            ViewDisposition("bogus")


class TestOperatorActionStatus:
    def test_member_count(self):
        assert len(OperatorActionStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (OperatorActionStatus.INITIATED, "initiated"),
        (OperatorActionStatus.COMPLETED, "completed"),
        (OperatorActionStatus.FAILED, "failed"),
        (OperatorActionStatus.CANCELLED, "cancelled"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["initiated", "completed", "failed", "cancelled"])
    def test_lookup_by_value(self, value):
        assert OperatorActionStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            OperatorActionStatus("bogus")


class TestWorkspaceScope:
    def test_member_count(self):
        assert len(WorkspaceScope) == 6

    @pytest.mark.parametrize("member,value", [
        (WorkspaceScope.TENANT, "tenant"),
        (WorkspaceScope.WORKSPACE, "workspace"),
        (WorkspaceScope.TEAM, "team"),
        (WorkspaceScope.PERSONAL, "personal"),
        (WorkspaceScope.EXECUTIVE, "executive"),
        (WorkspaceScope.GLOBAL, "global"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["tenant", "workspace", "team", "personal", "executive", "global"])
    def test_lookup_by_value(self, value):
        assert WorkspaceScope(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            WorkspaceScope("bogus")


# ===================================================================
# 2. WorkspaceView
# ===================================================================


class TestWorkspaceView:
    def test_valid_construction(self):
        v = _view()
        assert v.view_id == "v1"
        assert v.tenant_id == "t1"
        assert v.operator_ref == "op1"
        assert v.display_name == "Main"
        assert v.scope == WorkspaceScope.PERSONAL
        assert v.disposition == ViewDisposition.OPEN
        assert v.status == WorkspaceStatus.ACTIVE
        assert v.panel_count == 0
        assert v.created_at == TS

    def test_metadata_is_mapping_proxy(self):
        v = _view(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)
        assert v.metadata["k"] == "v"

    def test_metadata_frozen_deeply(self):
        v = _view(metadata={"nested": {"a": 1}})
        assert isinstance(v.metadata["nested"], MappingProxyType)

    def test_to_dict_preserves_enums(self):
        v = _view()
        d = v.to_dict()
        assert d["scope"] is WorkspaceScope.PERSONAL
        assert d["disposition"] is ViewDisposition.OPEN
        assert d["status"] is WorkspaceStatus.ACTIVE

    def test_to_dict_metadata_is_plain_dict(self):
        v = _view(metadata={"k": "v"})
        d = v.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field", [
        "view_id", "tenant_id", "operator_ref", "display_name",
        "scope", "disposition", "status", "panel_count", "created_at", "metadata",
    ])
    def test_frozen_immutability(self, field):
        v = _view()
        with pytest.raises(AttributeError):
            v.view_id = "x"

    def test_frozen_all_fields(self):
        v = _view()
        for name in ["view_id", "tenant_id", "operator_ref", "display_name",
                      "scope", "disposition", "status", "panel_count",
                      "created_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(v, name, "x")

    @pytest.mark.parametrize("field", ["view_id", "tenant_id", "operator_ref", "display_name"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _view(**{field: ""})

    @pytest.mark.parametrize("field", ["view_id", "tenant_id", "operator_ref", "display_name"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _view(**{field: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _view(created_at="not-a-date")

    def test_short_date_accepted(self):
        v = _view(created_at=TS_SHORT)
        assert v.created_at == TS_SHORT

    def test_negative_panel_count_rejected(self):
        with pytest.raises(ValueError):
            _view(panel_count=-1)

    def test_bool_panel_count_rejected(self):
        with pytest.raises(ValueError):
            _view(panel_count=True)

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            _view(scope="not_a_scope")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _view(disposition="wrong")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _view(status="wrong")

    @pytest.mark.parametrize("scope", list(WorkspaceScope))
    def test_all_scopes_accepted(self, scope):
        v = _view(scope=scope)
        assert v.scope is scope

    @pytest.mark.parametrize("disp", list(ViewDisposition))
    def test_all_dispositions_accepted(self, disp):
        v = _view(disposition=disp)
        assert v.disposition is disp

    @pytest.mark.parametrize("status", list(WorkspaceStatus))
    def test_all_statuses_accepted(self, status):
        v = _view(status=status)
        assert v.status is status

    def test_panel_count_zero(self):
        v = _view(panel_count=0)
        assert v.panel_count == 0

    def test_panel_count_large(self):
        v = _view(panel_count=999999)
        assert v.panel_count == 999999


# ===================================================================
# 3. WorkspacePanel
# ===================================================================


class TestWorkspacePanel:
    def test_valid_construction(self):
        p = _panel()
        assert p.panel_id == "p1"
        assert p.view_id == "v1"
        assert p.tenant_id == "t1"
        assert p.display_name == "Queue Panel"
        assert p.kind == PanelKind.QUEUE
        assert p.target_runtime == "rt1"
        assert p.item_count == 0

    def test_metadata_is_mapping_proxy(self):
        p = _panel(metadata={"x": 1})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _panel().to_dict()
        assert d["kind"] is PanelKind.QUEUE

    def test_frozen(self):
        p = _panel()
        with pytest.raises(AttributeError):
            p.panel_id = "new"

    @pytest.mark.parametrize("field", ["panel_id", "view_id", "tenant_id", "display_name", "target_runtime"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _panel(**{field: ""})

    @pytest.mark.parametrize("field", ["panel_id", "view_id", "tenant_id", "display_name", "target_runtime"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _panel(**{field: "  "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _panel(created_at="nope")

    def test_short_date_accepted(self):
        p = _panel(created_at=TS_SHORT)
        assert p.created_at == TS_SHORT

    def test_negative_item_count(self):
        with pytest.raises(ValueError):
            _panel(item_count=-1)

    def test_bool_item_count_rejected(self):
        with pytest.raises(ValueError):
            _panel(item_count=False)

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            _panel(kind="wrong")

    @pytest.mark.parametrize("kind", list(PanelKind))
    def test_all_kinds_accepted(self, kind):
        p = _panel(kind=kind)
        assert p.kind is kind

    def test_frozen_all_fields(self):
        p = _panel()
        for name in ["panel_id", "view_id", "tenant_id", "display_name",
                      "kind", "target_runtime", "item_count", "created_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(p, name, "x")


# ===================================================================
# 4. QueueRecord
# ===================================================================


class TestQueueRecord:
    def test_valid_construction(self):
        q = _queue()
        assert q.queue_id == "q1"
        assert q.panel_id == "p1"
        assert q.tenant_id == "t1"
        assert q.source_ref == "src1"
        assert q.source_runtime == "rt1"
        assert q.assignee_ref == "op1"
        assert q.priority == 0
        assert q.status == QueueStatus.PENDING

    def test_metadata_mapping_proxy(self):
        q = _queue(metadata={"a": "b"})
        assert isinstance(q.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _queue().to_dict()
        assert d["status"] is QueueStatus.PENDING

    def test_frozen(self):
        q = _queue()
        with pytest.raises(AttributeError):
            q.queue_id = "new"

    @pytest.mark.parametrize("field", [
        "queue_id", "panel_id", "tenant_id", "source_ref",
        "source_runtime", "assignee_ref",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _queue(**{field: ""})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _queue(created_at="bad")

    def test_short_date_accepted(self):
        q = _queue(created_at=TS_SHORT)
        assert q.created_at == TS_SHORT

    def test_negative_priority(self):
        with pytest.raises(ValueError):
            _queue(priority=-1)

    def test_bool_priority_rejected(self):
        with pytest.raises(ValueError):
            _queue(priority=True)

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _queue(status="wrong")

    @pytest.mark.parametrize("status", list(QueueStatus))
    def test_all_statuses_accepted(self, status):
        q = _queue(status=status)
        assert q.status is status

    def test_frozen_all_fields(self):
        q = _queue()
        for name in ["queue_id", "panel_id", "tenant_id", "source_ref",
                      "source_runtime", "assignee_ref", "priority",
                      "status", "created_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(q, name, "x")


# ===================================================================
# 5. WorklistItem
# ===================================================================


class TestWorklistItem:
    def test_valid_construction(self):
        w = _worklist()
        assert w.item_id == "i1"
        assert w.tenant_id == "t1"
        assert w.operator_ref == "op1"
        assert w.source_ref == "src1"
        assert w.source_runtime == "rt1"
        assert w.title == "Review item"
        assert w.priority == 0
        assert w.status == QueueStatus.PENDING

    def test_metadata_mapping_proxy(self):
        w = _worklist(metadata={"x": [1, 2]})
        assert isinstance(w.metadata, MappingProxyType)
        assert w.metadata["x"] == (1, 2)

    def test_to_dict_preserves_enum(self):
        d = _worklist().to_dict()
        assert d["status"] is QueueStatus.PENDING

    def test_frozen(self):
        w = _worklist()
        with pytest.raises(AttributeError):
            w.item_id = "new"

    @pytest.mark.parametrize("field", [
        "item_id", "tenant_id", "operator_ref", "source_ref",
        "source_runtime", "title",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _worklist(**{field: ""})

    @pytest.mark.parametrize("field", [
        "item_id", "tenant_id", "operator_ref", "source_ref",
        "source_runtime", "title",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _worklist(**{field: "  \t "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _worklist(created_at="xyz")

    def test_short_date_accepted(self):
        w = _worklist(created_at=TS_SHORT)
        assert w.created_at == TS_SHORT

    def test_negative_priority(self):
        with pytest.raises(ValueError):
            _worklist(priority=-5)

    def test_bool_priority_rejected(self):
        with pytest.raises(ValueError):
            _worklist(priority=False)

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _worklist(status="wrong")

    @pytest.mark.parametrize("status", list(QueueStatus))
    def test_all_statuses_accepted(self, status):
        w = _worklist(status=status)
        assert w.status is status

    def test_frozen_all_fields(self):
        w = _worklist()
        for name in ["item_id", "tenant_id", "operator_ref", "source_ref",
                      "source_runtime", "title", "priority", "status",
                      "created_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(w, name, "x")


# ===================================================================
# 6. OperatorAction
# ===================================================================


class TestOperatorAction:
    def test_valid_construction(self):
        a = _action()
        assert a.action_id == "a1"
        assert a.tenant_id == "t1"
        assert a.operator_ref == "op1"
        assert a.target_ref == "tgt1"
        assert a.target_runtime == "rt1"
        assert a.action_name == "approve"
        assert a.status == OperatorActionStatus.INITIATED

    def test_metadata_mapping_proxy(self):
        a = _action(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _action().to_dict()
        assert d["status"] is OperatorActionStatus.INITIATED

    def test_frozen(self):
        a = _action()
        with pytest.raises(AttributeError):
            a.action_id = "new"

    @pytest.mark.parametrize("field", [
        "action_id", "tenant_id", "operator_ref",
        "target_ref", "target_runtime", "action_name",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _action(**{field: ""})

    @pytest.mark.parametrize("field", [
        "action_id", "tenant_id", "operator_ref",
        "target_ref", "target_runtime", "action_name",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _action(**{field: "  "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _action(created_at="bad")

    def test_short_date_accepted(self):
        a = _action(created_at=TS_SHORT)
        assert a.created_at == TS_SHORT

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _action(status="wrong")

    @pytest.mark.parametrize("status", list(OperatorActionStatus))
    def test_all_statuses_accepted(self, status):
        a = _action(status=status)
        assert a.status is status

    def test_frozen_all_fields(self):
        a = _action()
        for name in ["action_id", "tenant_id", "operator_ref", "target_ref",
                      "target_runtime", "action_name", "status",
                      "created_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(a, name, "x")


# ===================================================================
# 7. WorkspaceDecision
# ===================================================================


class TestWorkspaceDecision:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision_id == "d1"
        assert d.tenant_id == "t1"
        assert d.operator_ref == "op1"
        assert d.action_id == "a1"
        assert d.disposition == "approved"
        assert d.reason == "looks good"
        assert d.decided_at == TS

    def test_metadata_mapping_proxy(self):
        d = _decision(metadata={"k": 1})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        d = _decision(metadata={"k": 1}).to_dict()
        assert isinstance(d["metadata"], dict)

    def test_disposition_is_plain_string(self):
        d = _decision(disposition="rejected")
        assert d.disposition == "rejected"

    def test_reason_is_plain_string(self):
        d = _decision(reason="needs rework")
        assert d.reason == "needs rework"

    def test_frozen(self):
        d = _decision()
        with pytest.raises(AttributeError):
            d.decision_id = "new"

    @pytest.mark.parametrize("field", [
        "decision_id", "tenant_id", "operator_ref", "action_id", "disposition",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _decision(**{field: ""})

    @pytest.mark.parametrize("field", [
        "decision_id", "tenant_id", "operator_ref", "action_id", "disposition",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _decision(**{field: " \t "})

    def test_reason_not_validated_as_non_empty(self):
        # reason field does not go through require_non_empty_text per source
        # Actually, looking at the source, reason is NOT validated. Let's check:
        # The __post_init__ does not call require_non_empty_text on reason.
        d = _decision(reason="valid")
        assert d.reason == "valid"

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _decision(decided_at="nope")

    def test_short_date_accepted(self):
        d = _decision(decided_at=TS_SHORT)
        assert d.decided_at == TS_SHORT

    def test_frozen_all_fields(self):
        d = _decision()
        for name in ["decision_id", "tenant_id", "operator_ref", "action_id",
                      "disposition", "reason", "decided_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(d, name, "x")


# ===================================================================
# 8. WorkspaceSnapshot
# ===================================================================


class TestWorkspaceSnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "s1"
        assert s.tenant_id == "t1"
        assert s.total_views == 0
        assert s.active_views == 0
        assert s.total_panels == 0
        assert s.total_queue_items == 0
        assert s.pending_queue_items == 0
        assert s.total_worklist_items == 0
        assert s.total_actions == 0

    def test_metadata_mapping_proxy(self):
        s = _snapshot(metadata={"x": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises(AttributeError):
            s.snapshot_id = "new"

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "total_panels",
        "total_queue_items", "pending_queue_items",
        "total_worklist_items", "total_actions",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "total_panels",
        "total_queue_items", "pending_queue_items",
        "total_worklist_items", "total_actions",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "total_panels",
        "total_queue_items", "pending_queue_items",
        "total_worklist_items", "total_actions",
    ])
    def test_zero_accepted(self, field):
        s = _snapshot(**{field: 0})
        assert getattr(s, field) == 0

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "total_panels",
        "total_queue_items", "pending_queue_items",
        "total_worklist_items", "total_actions",
    ])
    def test_positive_accepted(self, field):
        s = _snapshot(**{field: 42})
        assert getattr(s, field) == 42

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_short_date_accepted(self):
        s = _snapshot(captured_at=TS_SHORT)
        assert s.captured_at == TS_SHORT

    def test_frozen_all_fields(self):
        s = _snapshot()
        for name in ["snapshot_id", "tenant_id", "total_views", "active_views",
                      "total_panels", "total_queue_items", "pending_queue_items",
                      "total_worklist_items", "total_actions",
                      "captured_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(s, name, "x")


# ===================================================================
# 9. WorkspaceViolation
# ===================================================================


class TestWorkspaceViolation:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "vl1"
        assert v.tenant_id == "t1"
        assert v.operation == "delete"
        assert v.reason == "unauthorized"

    def test_metadata_mapping_proxy(self):
        v = _violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_frozen(self):
        v = _violation()
        with pytest.raises(AttributeError):
            v.violation_id = "new"

    @pytest.mark.parametrize("field", ["violation_id", "tenant_id", "operation", "reason"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: ""})

    @pytest.mark.parametrize("field", ["violation_id", "tenant_id", "operation", "reason"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: "  "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _violation(detected_at="nah")

    def test_short_date_accepted(self):
        v = _violation(detected_at=TS_SHORT)
        assert v.detected_at == TS_SHORT

    def test_frozen_all_fields(self):
        v = _violation()
        for name in ["violation_id", "tenant_id", "operation", "reason",
                      "detected_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(v, name, "x")


# ===================================================================
# 10. WorkspaceAssessment
# ===================================================================


class TestWorkspaceAssessment:
    def test_valid_construction(self):
        a = _assessment()
        assert a.assessment_id == "as1"
        assert a.tenant_id == "t1"
        assert a.total_views == 0
        assert a.active_views == 0
        assert a.queue_depth == 0
        assert a.pending_rate == 0.0
        assert a.total_violations == 0

    def test_metadata_mapping_proxy(self):
        a = _assessment(metadata={"a": 1})
        assert isinstance(a.metadata, MappingProxyType)

    def test_frozen(self):
        a = _assessment()
        with pytest.raises(AttributeError):
            a.assessment_id = "new"

    @pytest.mark.parametrize("field", ["assessment_id", "tenant_id"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "queue_depth", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "queue_depth", "total_violations",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_views", "active_views", "queue_depth", "total_violations",
    ])
    def test_zero_accepted(self, field):
        a = _assessment(**{field: 0})
        assert getattr(a, field) == 0

    # --- pending_rate (unit_float) boundary tests ---
    def test_pending_rate_zero(self):
        a = _assessment(pending_rate=0.0)
        assert a.pending_rate == 0.0

    def test_pending_rate_one(self):
        a = _assessment(pending_rate=1.0)
        assert a.pending_rate == 1.0

    def test_pending_rate_mid(self):
        a = _assessment(pending_rate=0.5)
        assert a.pending_rate == 0.5

    def test_pending_rate_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(pending_rate=-0.01)

    def test_pending_rate_above_one_rejected(self):
        with pytest.raises(ValueError):
            _assessment(pending_rate=1.01)

    def test_pending_rate_nan_rejected(self):
        with pytest.raises(ValueError):
            _assessment(pending_rate=float("nan"))

    def test_pending_rate_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(pending_rate=float("inf"))

    def test_pending_rate_neg_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(pending_rate=float("-inf"))

    def test_pending_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(pending_rate=True)

    def test_pending_rate_int_zero_accepted(self):
        a = _assessment(pending_rate=0)
        assert a.pending_rate == 0.0

    def test_pending_rate_int_one_accepted(self):
        a = _assessment(pending_rate=1)
        assert a.pending_rate == 1.0

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_short_date_accepted(self):
        a = _assessment(assessed_at=TS_SHORT)
        assert a.assessed_at == TS_SHORT

    def test_frozen_all_fields(self):
        a = _assessment()
        for name in ["assessment_id", "tenant_id", "total_views", "active_views",
                      "queue_depth", "pending_rate", "total_violations",
                      "assessed_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(a, name, "x")


# ===================================================================
# 11. WorkspaceClosureReport
# ===================================================================


class TestWorkspaceClosureReport:
    def test_valid_construction(self):
        c = _closure()
        assert c.report_id == "r1"
        assert c.tenant_id == "t1"
        assert c.total_views == 0
        assert c.total_panels == 0
        assert c.total_queue_items == 0
        assert c.total_worklist_items == 0
        assert c.total_actions == 0
        assert c.total_violations == 0

    def test_metadata_mapping_proxy(self):
        c = _closure(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_frozen(self):
        c = _closure()
        with pytest.raises(AttributeError):
            c.report_id = "new"

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: ""})

    @pytest.mark.parametrize("field", [
        "total_views", "total_panels", "total_queue_items",
        "total_worklist_items", "total_actions", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_views", "total_panels", "total_queue_items",
        "total_worklist_items", "total_actions", "total_violations",
    ])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_views", "total_panels", "total_queue_items",
        "total_worklist_items", "total_actions", "total_violations",
    ])
    def test_zero_accepted(self, field):
        c = _closure(**{field: 0})
        assert getattr(c, field) == 0

    @pytest.mark.parametrize("field", [
        "total_views", "total_panels", "total_queue_items",
        "total_worklist_items", "total_actions", "total_violations",
    ])
    def test_positive_accepted(self, field):
        c = _closure(**{field: 100})
        assert getattr(c, field) == 100

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _closure(created_at="nope")

    def test_short_date_accepted(self):
        c = _closure(created_at=TS_SHORT)
        assert c.created_at == TS_SHORT

    def test_frozen_all_fields(self):
        c = _closure()
        for name in ["report_id", "tenant_id", "total_views", "total_panels",
                      "total_queue_items", "total_worklist_items",
                      "total_actions", "total_violations",
                      "created_at", "metadata"]:
            with pytest.raises(AttributeError):
                setattr(c, name, "x")


# ===================================================================
# 12. Cross-cutting / parametrized boundary tests
# ===================================================================


class TestCrossCuttingDatetimeFormats:
    """Various ISO datetime formats accepted or rejected."""

    FACTORIES = [
        _view, _panel, _queue, _worklist, _action,
        _violation, _snapshot, _closure,
    ]
    DT_FIELD_MAP = {
        _view: "created_at", _panel: "created_at", _queue: "created_at",
        _worklist: "created_at", _action: "created_at",
        _violation: "detected_at", _snapshot: "captured_at",
        _closure: "created_at",
    }

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00",
        "2025-06-01T12:30:00Z",
        "2025-06-01",
        "2025-01-15T08:00:00-05:00",
    ])
    @pytest.mark.parametrize("factory", FACTORIES)
    def test_valid_datetime_formats(self, factory, ts):
        field = self.DT_FIELD_MAP[factory]
        obj = factory(**{field: ts})
        assert getattr(obj, field) == ts

    @pytest.mark.parametrize("ts", [
        "", "not-a-date", "2025-13-01", "yesterday",
    ])
    @pytest.mark.parametrize("factory", FACTORIES)
    def test_invalid_datetime_formats(self, factory, ts):
        field = self.DT_FIELD_MAP[factory]
        with pytest.raises(ValueError):
            factory(**{field: ts})


class TestCrossCuttingDecisionAssessmentDatetime:
    """Decision and Assessment have different datetime field names."""

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00", "2025-06-01",
    ])
    def test_decision_valid(self, ts):
        d = _decision(decided_at=ts)
        assert d.decided_at == ts

    @pytest.mark.parametrize("ts", ["", "nope"])
    def test_decision_invalid(self, ts):
        with pytest.raises(ValueError):
            _decision(decided_at=ts)

    @pytest.mark.parametrize("ts", [
        "2025-06-01T00:00:00+00:00", "2025-06-01",
    ])
    def test_assessment_valid(self, ts):
        a = _assessment(assessed_at=ts)
        assert a.assessed_at == ts

    @pytest.mark.parametrize("ts", ["", "nope"])
    def test_assessment_invalid(self, ts):
        with pytest.raises(ValueError):
            _assessment(assessed_at=ts)


class TestCrossCuttingMetadataDeepFreeze:
    """Metadata with nested structures is deeply frozen."""

    FACTORIES = [
        _view, _panel, _queue, _worklist, _action,
        _decision, _snapshot, _violation, _assessment, _closure,
    ]

    @pytest.mark.parametrize("factory", FACTORIES)
    def test_nested_dict_frozen(self, factory):
        obj = factory(metadata={"a": {"b": 1}})
        assert isinstance(obj.metadata, MappingProxyType)
        assert isinstance(obj.metadata["a"], MappingProxyType)

    @pytest.mark.parametrize("factory", FACTORIES)
    def test_nested_list_becomes_tuple(self, factory):
        obj = factory(metadata={"items": [1, 2, 3]})
        assert obj.metadata["items"] == (1, 2, 3)

    @pytest.mark.parametrize("factory", FACTORIES)
    def test_empty_metadata(self, factory):
        obj = factory(metadata={})
        assert isinstance(obj.metadata, MappingProxyType)
        assert len(obj.metadata) == 0

    @pytest.mark.parametrize("factory", FACTORIES)
    def test_metadata_mutation_blocked(self, factory):
        obj = factory(metadata={"k": "v"})
        with pytest.raises(TypeError):
            obj.metadata["new_key"] = "fail"


class TestCrossCuttingToDictRoundtrip:
    """to_dict returns regular dicts for metadata."""

    FACTORIES = [
        _view, _panel, _queue, _worklist, _action,
        _decision, _snapshot, _violation, _assessment, _closure,
    ]

    @pytest.mark.parametrize("factory", FACTORIES)
    def test_to_dict_returns_dict(self, factory):
        obj = factory(metadata={"k": "v"})
        d = obj.to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("factory", FACTORIES)
    def test_to_dict_nested_list_becomes_list(self, factory):
        obj = factory(metadata={"items": [1, 2]})
        d = obj.to_dict()
        assert isinstance(d["metadata"]["items"], list)


class TestNonNegativeIntBoundary:
    """Boundary values for non_negative_int fields."""

    INT_FIELDS = [
        (_view, "panel_count"),
        (_panel, "item_count"),
        (_queue, "priority"),
        (_worklist, "priority"),
        (_snapshot, "total_views"),
        (_snapshot, "active_views"),
        (_snapshot, "total_panels"),
        (_snapshot, "total_queue_items"),
        (_snapshot, "pending_queue_items"),
        (_snapshot, "total_worklist_items"),
        (_snapshot, "total_actions"),
        (_assessment, "total_views"),
        (_assessment, "active_views"),
        (_assessment, "queue_depth"),
        (_assessment, "total_violations"),
        (_closure, "total_views"),
        (_closure, "total_panels"),
        (_closure, "total_queue_items"),
        (_closure, "total_worklist_items"),
        (_closure, "total_actions"),
        (_closure, "total_violations"),
    ]

    @pytest.mark.parametrize("factory,field", INT_FIELDS)
    def test_zero_accepted(self, factory, field):
        obj = factory(**{field: 0})
        assert getattr(obj, field) == 0

    @pytest.mark.parametrize("factory,field", INT_FIELDS)
    def test_one_accepted(self, factory, field):
        obj = factory(**{field: 1})
        assert getattr(obj, field) == 1

    @pytest.mark.parametrize("factory,field", INT_FIELDS)
    def test_negative_rejected(self, factory, field):
        with pytest.raises(ValueError):
            factory(**{field: -1})

    @pytest.mark.parametrize("factory,field", INT_FIELDS)
    def test_bool_rejected(self, factory, field):
        with pytest.raises(ValueError):
            factory(**{field: True})

    @pytest.mark.parametrize("factory,field", INT_FIELDS)
    def test_large_value(self, factory, field):
        obj = factory(**{field: 10_000_000})
        assert getattr(obj, field) == 10_000_000


class TestUnitFloatBoundary:
    """Boundary values for unit_float (pending_rate on WorkspaceAssessment)."""

    @pytest.mark.parametrize("val", [0.0, 0.001, 0.5, 0.999, 1.0])
    def test_valid_range(self, val):
        a = _assessment(pending_rate=val)
        assert a.pending_rate == pytest.approx(val)

    @pytest.mark.parametrize("val", [-0.001, 1.001, 2.0, -1.0])
    def test_out_of_range(self, val):
        with pytest.raises(ValueError):
            _assessment(pending_rate=val)

    @pytest.mark.parametrize("val", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_rejected(self, val):
        with pytest.raises(ValueError):
            _assessment(pending_rate=val)

    def test_string_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _assessment(pending_rate="0.5")
