"""Tests for predicate kinds — affinity, missing fields, three concrete kinds."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.intent_substrate import (
    EntityAttributeEq,
    EntityAttributeThreshold,
    EntityExists,
)


def test_attr_eq_true_when_value_matches():
    p = EntityAttributeEq("vendor-001", "approved", True)
    assert p.evaluate({"approved": True}) is True


def test_attr_eq_false_when_value_differs():
    p = EntityAttributeEq("vendor-001", "approved", True)
    assert p.evaluate({"approved": False}) is False


def test_attr_eq_missing_state_is_false():
    p = EntityAttributeEq("vendor-001", "approved", True)
    assert p.evaluate(None) is False


def test_attr_eq_missing_attribute_is_false():
    p = EntityAttributeEq("vendor-001", "approved", True)
    assert p.evaluate({"other": True}) is False


def test_threshold_each_op():
    s = {"queue_depth": 10}
    assert EntityAttributeThreshold("e", "queue_depth", ">=", 10).evaluate(s) is True
    assert EntityAttributeThreshold("e", "queue_depth", ">", 10).evaluate(s) is False
    assert EntityAttributeThreshold("e", "queue_depth", "<", 11).evaluate(s) is True
    assert EntityAttributeThreshold("e", "queue_depth", "<=", 10).evaluate(s) is True
    assert EntityAttributeThreshold("e", "queue_depth", "==", 10).evaluate(s) is True
    assert EntityAttributeThreshold("e", "queue_depth", "!=", 9).evaluate(s) is True


def test_threshold_invalid_op_rejected_at_construction():
    with pytest.raises(ValueError, match="op must be"):
        EntityAttributeThreshold("e", "x", "≥", 10)


def test_threshold_non_numeric_returns_false():
    p = EntityAttributeThreshold("e", "label", ">", 1)
    assert p.evaluate({"label": "hi"}) is False


def test_threshold_missing_state_or_attr_returns_false():
    p = EntityAttributeThreshold("e", "x", ">", 0)
    assert p.evaluate(None) is False
    assert p.evaluate({}) is False


def test_exists_true_for_present_entity():
    p = EntityExists("vendor-001")
    assert p.evaluate({"any": "attrs"}) is True


def test_exists_false_for_missing_entity():
    p = EntityExists("vendor-001")
    assert p.evaluate(None) is False


def test_watches_default():
    assert EntityAttributeEq("e", "x", 1).watches() == {EventType.WORLD_STATE_CHANGED}
    assert EntityAttributeThreshold("e", "x", ">", 0).watches() == {
        EventType.WORLD_STATE_CHANGED
    }
    assert EntityExists("e").watches() == {EventType.WORLD_STATE_CHANGED}


def test_watches_custom():
    p = EntityAttributeEq(
        "e", "approved", True,
        watches_kinds=(EventType.APPROVAL_DECIDED, EventType.APPROVAL_REQUESTED),
    )
    assert p.watches() == {EventType.APPROVAL_DECIDED, EventType.APPROVAL_REQUESTED}
