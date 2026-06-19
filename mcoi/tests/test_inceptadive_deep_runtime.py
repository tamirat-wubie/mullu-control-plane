"""Focused tests for bounded InceptaDive deep runtime activation."""

from __future__ import annotations

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowMode,
    ShadowSeverity,
    ShadowStage,
    ShadowVerdict,
)


def _context(user_input: str, **overrides: object) -> ShadowContext:
    values = {
        "request_id": "req-deep-runtime-1",
        "stage": ShadowStage.INTERPRETATION,
        "user_input": user_input,
        "created_at": "2026-06-18T00:00:00+00:00",
    }
    values.update(overrides)
    return ShadowContext(**values).with_integrity()


def test_deep_engine_runs_when_gate_selects_deep_and_records_receipt() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1"})
    context = _context("deploy it", risk_level=ShadowSeverity.HIGH, external_side_effect=True)

    result, receipt = runtime.inspect_request(context)
    summary = runtime.console_summary(created_at="2026-06-18T00:01:00+00:00")

    assert result.mode == ShadowMode.DEEP
    assert result.needs_deep_pass is False
    assert result.verdict in {ShadowVerdict.BLOCK_RECOMMENDED, ShadowVerdict.REPAIR_REQUIRED, ShadowVerdict.ADVISORY}
    assert result.to_dict()["execution_authority"] is False
    assert receipt is not None
    assert receipt.receipt_id.startswith("shadow-receipt-")
    assert summary.recent_result_count == 1
    assert summary.receipt_count == 1
    assert summary.to_dict()["raw_request_text_exposed"] is False
    assert "deploy it" not in str(summary.to_dict())


def test_deep_engine_can_be_disabled_without_silent_success() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "0"})
    context = _context("deploy it", risk_level=ShadowSeverity.HIGH, external_side_effect=True)

    result, _receipt = runtime.inspect_request(context)

    assert result.mode == ShadowMode.DEEP
    assert result.verdict == ShadowVerdict.DEEP_REQUIRED
    assert result.needs_deep_pass is True
    assert result.to_dict()["execution_authority"] is False
