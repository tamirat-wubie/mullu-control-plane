from __future__ import annotations

from scripts.validate_governed_work_assistant_operator_dashboard import validate_dashboard_projection


def test_governed_work_assistant_operator_dashboard_fixture_validates() -> None:
    result = validate_dashboard_projection()
    assert result.valid, result.errors
    assert result.errors == ()


def test_governed_work_assistant_operator_dashboard_is_no_effect() -> None:
    result = validate_dashboard_projection()
    assert result.valid, result.errors
