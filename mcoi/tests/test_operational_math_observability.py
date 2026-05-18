"""Tests for operational mathematics receipt observability projections."""

from __future__ import annotations

import pytest

from mcoi_runtime.app.operational_math_observability import (
    OPERATIONAL_MATH_OBSERVABILITY_SOURCE,
    register_operational_math_observability,
    summarize_operational_math_receipt,
)


class FakeObservability:
    def __init__(self) -> None:
        self.sources: dict[str, object] = {}

    def register_source(self, name, source) -> None:
        self.sources[name] = source


def _receipt(**overrides: object) -> dict[str, object]:
    receipt: dict[str, object] = {
        "receipt_id": "operational_math_loop_receipt:result-1",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "target_id": "mullu-core-math",
        "event_count": 11,
        "iteration_count": 10,
        "applied_principle_ids": ["F1", "F2", "F3"],
        "unresolved_principle_ids": [],
        "result": {},
    }
    receipt.update(overrides)
    return receipt


def test_summary_marks_saturated_receipt_as_closed() -> None:
    summary = summarize_operational_math_receipt(_receipt())

    assert summary["source"] == OPERATIONAL_MATH_OBSERVABILITY_SOURCE
    assert summary["governed"] is True
    assert summary["target_id"] == "mullu-core-math"
    assert summary["status"] == "passed"
    assert summary["solver_outcome"] == "SolvedVerified"
    assert summary["iteration_count"] == 10
    assert summary["event_count"] == 11
    assert summary["applied_principle_count"] == 3
    assert summary["unresolved_principle_count"] == 0
    assert summary["requires_operator_review"] is False
    assert summary["review_signals"] == []


def test_summary_marks_incomplete_receipt_for_review() -> None:
    summary = summarize_operational_math_receipt(
        _receipt(
            status="failed",
            solver_outcome="AwaitingEvidence",
            iteration_count=2,
            event_count=3,
            applied_principle_ids=["F1", "F2"],
            unresolved_principle_ids=["F3", "F5"],
        )
    )

    assert summary["requires_operator_review"] is True
    assert summary["unresolved_principle_count"] == 2
    assert summary["unresolved_principle_ids"] == ["F3", "F5"]
    assert "operational_math_status_not_passed" in summary["review_signals"]
    assert "operational_math_unresolved_principles" in summary["review_signals"]
    assert "operational_math_solver_not_verified" in summary["review_signals"]


def test_registers_operational_math_observability_source() -> None:
    observability = FakeObservability()

    register_operational_math_observability(
        observability=observability,
        receipt_provider=lambda: _receipt(),
    )
    source = observability.sources[OPERATIONAL_MATH_OBSERVABILITY_SOURCE]
    summary = source()

    assert summary["source"] == OPERATIONAL_MATH_OBSERVABILITY_SOURCE
    assert summary["status"] == "passed"
    assert summary["requires_operator_review"] is False
    assert summary["governed"] is True


def test_observability_registration_rejects_invalid_surfaces() -> None:
    with pytest.raises(TypeError):
        register_operational_math_observability(
            observability=object(),
            receipt_provider=lambda: _receipt(),
        )

    with pytest.raises(TypeError):
        register_operational_math_observability(
            observability=FakeObservability(),
            receipt_provider=object(),  # type: ignore[arg-type]
        )


def test_summary_rejects_invalid_count_fields() -> None:
    with pytest.raises(ValueError):
        summarize_operational_math_receipt(_receipt(event_count=-1))

    with pytest.raises(TypeError):
        summarize_operational_math_receipt(object())  # type: ignore[arg-type]
