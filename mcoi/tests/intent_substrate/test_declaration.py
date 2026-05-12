"""Tests for declare_intent — obligation creation + resolver registration."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.obligation import (
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.intent_substrate import (
    EntityAttributeEq,
    IntentResolver,
    ObligationClosureAdapter,
    declare_intent,
)

from .conftest import MutableState, make_deadline, make_owner


def _build():
    state = MutableState()
    obligations = ObligationRuntimeEngine()
    spine = EventSpineEngine()
    resolver = IntentResolver(
        state_view=state,
        closure=ObligationClosureAdapter(obligations),
        spine=spine,
    )
    return state, obligations, spine, resolver


def test_creates_obligation_in_pending_state():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="ship vendor", correlation_id="corr-1",
        success=(EntityAttributeEq("vendor", "shipped", True),),
    )
    fetched = obligations.get_obligation(obl.obligation_id)
    assert fetched.state == ObligationState.PENDING
    assert fetched.description == "ship vendor"


def test_marks_obligation_with_substrate_metadata():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        preconditions=(EntityAttributeEq("a", "x", 1),),
        success=(EntityAttributeEq("b", "y", 2),),
    )
    assert obl.metadata.get("intent_substrate") == "true"
    assert obl.metadata.get("predicate_count") == "2"


def test_extra_metadata_merged():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        success=(EntityAttributeEq("e", "x", 1),),
        extra_metadata={"tenant_id": "acme", "domain": "vendor"},
    )
    assert obl.metadata["tenant_id"] == "acme"
    assert obl.metadata["domain"] == "vendor"


def test_extra_metadata_cannot_override_substrate_keys():
    _state, obligations, _spine, resolver = _build()
    with pytest.raises(ValueError, match="reserved intent_substrate keys"):
        declare_intent(
            resolver=resolver, obligation_engine=obligations,
            owner=make_owner(), deadline=make_deadline(),
            description="d", correlation_id="c",
            success=(EntityAttributeEq("e", "x", 1),),
            extra_metadata={"intent_substrate": "false"},
        )


def test_registers_intent_with_resolver():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        success=(EntityAttributeEq("e", "x", 1),),
    )
    assert resolver.is_registered(obl.obligation_id)


def test_default_trigger_is_custom():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        success=(),
    )
    assert obl.trigger == ObligationTrigger.CUSTOM


def test_custom_trigger_passed_through():
    _state, obligations, _spine, resolver = _build()
    obl = declare_intent(
        resolver=resolver, obligation_engine=obligations,
        owner=make_owner(), deadline=make_deadline(),
        description="d", correlation_id="c",
        success=(),
        trigger=ObligationTrigger.APPROVAL_REQUEST,
        trigger_ref_id="req-001",
    )
    assert obl.trigger == ObligationTrigger.APPROVAL_REQUEST
    assert obl.trigger_ref_id == "req-001"
