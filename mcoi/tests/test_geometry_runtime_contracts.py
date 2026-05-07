"""Focused tests for bounded geometry runtime contract helpers."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.geometry_runtime import GeometryPoint, SpatialDecision


TS = "2025-06-01T12:00:00+00:00"


def _point(**overrides) -> GeometryPoint:
    defaults = dict(
        point_id="pt-1",
        tenant_id="t-1",
        label="P1",
        x=1.0,
        y=2.0,
        z=3.0,
        created_at=TS,
    )
    defaults.update(overrides)
    return GeometryPoint(**defaults)


def test_geometry_numeric_type_message_is_bounded() -> None:
    with pytest.raises(ValueError) as exc_info:
        _point(x=True)
    message = str(exc_info.value)
    assert message == "numeric value must be a number"
    assert "x" not in message
    assert "bool" not in message


def test_geometry_numeric_finite_message_is_bounded() -> None:
    with pytest.raises(ValueError) as exc_info:
        _point(x=float("inf"))
    message = str(exc_info.value)
    assert message == "numeric value must be finite"
    assert "x" not in message
    assert "inf" not in message


def test_geometry_boolean_message_is_bounded() -> None:
    with pytest.raises(ValueError) as exc_info:
        SpatialDecision(
            decision_id="d-1",
            tenant_id="t-1",
            constraint_ref="c-1",
            passed="yes",
            reason="blocked",
            decided_at=TS,
        )
    message = str(exc_info.value)
    assert message == "value must be a boolean flag"
    assert "passed" not in message
    assert "yes" not in message
