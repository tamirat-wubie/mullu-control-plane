"""Focused non-leak tests for transition contract validation."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.state import StateCategory
from mcoi_runtime.contracts.transition import TransitionRecord


def _record(**overrides):
    defaults = dict(
        transition_id="tr-1",
        from_state_id="from-1",
        from_category=StateCategory.RUNTIME,
        to_state_id="to-1",
        to_category=StateCategory.ENVIRONMENT,
        trace_id="trace-1",
    )
    defaults.update(overrides)
    return TransitionRecord(**defaults)


def test_from_category_error_is_bounded() -> None:
    with pytest.raises(ValueError, match="^state category must be a StateCategory value$") as exc_info:
        _record(from_category="secret-runtime")  # type: ignore[arg-type]
    message = str(exc_info.value)
    assert "from_category" not in message
    assert "secret-runtime" not in message


def test_to_category_error_is_bounded() -> None:
    with pytest.raises(ValueError, match="^state category must be a StateCategory value$") as exc_info:
        _record(to_category="secret-operator")  # type: ignore[arg-type]
    message = str(exc_info.value)
    assert "to_category" not in message
    assert "secret-operator" not in message
