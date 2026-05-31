"""Focused tests for app-level InceptaDive Shadow posture facade."""

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
        "request_id": "req-shadow-facade-1",
        "stage": ShadowStage.INTERPRETATION,
        "user_input": user_input,
        "created_at": "2026-05-31T00:00:00+00:00",
    }
    values.update(overrides)
    return ShadowContext(**values).with_integrity()


def test_runtime_health_posture_exposes_redacted_ready_state() -> None:
    runtime = build_inceptadive_shadow_runtime({})

    posture = runtime.health_posture(created_at="2026-05-31T00:00:00+00:00")
    payload = posture.to_dict()

    assert posture.status == "ready"
    assert payload["enabled"] is True
    assert payload["receipts_enabled"] is True
    assert payload["deep_engine_available"] is False
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False


def test_runtime_health_posture_reflects_disabled_and_dependency_flags() -> None:
    runtime = build_inceptadive_shadow_runtime(
        {
            "MULLU_INCEPTADIVE_SHADOW_ENABLED": "0",
            "MULLU_INCEPTADIVE_SHADOW_RECEIPTS_ENABLED": "0",
            "MULLU_INCEPTADIVE_SHADOW_DEPENDENCY_AVAILABLE": "0",
            "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
        }
    )

    posture = runtime.health_posture(created_at="2026-05-31T00:00:00+00:00")

    assert posture.status == "disabled"
    assert posture.enabled is False
    assert posture.receipts_enabled is False
    assert posture.dependency_available is False
    assert posture.deep_engine_available is True
    assert posture.to_dict()["execution_authority"] is False


def test_runtime_console_summary_counts_recent_results_without_raw_text() -> None:
    runtime = build_inceptadive_shadow_runtime({})
    light_context = _context("continue the project")
    preflight_context = _context(
        "delete production logs",
        request_id="req-shadow-facade-2",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="delete production logs",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    light_result, light_receipt = runtime.inspect_request(light_context)
    preflight_result, preflight_receipt = runtime.preflight_action(preflight_context)
    receipts = tuple(receipt for receipt in (light_receipt, preflight_receipt) if receipt is not None)

    summary = runtime.console_summary(
        results=(light_result, preflight_result),
        receipts=receipts,
        created_at="2026-05-31T00:00:00+00:00",
    )
    payload = summary.to_dict()

    assert summary.recent_result_count == 2
    assert summary.receipt_count == 2
    assert "light:1" in summary.mode_counts
    assert "strict_preflight:1" in summary.mode_counts
    assert summary.repair_required_count >= 1
    assert summary.block_recommended_count == 1
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert "continue the project" not in str(payload)
    assert "delete production logs" not in str(payload)


def test_runtime_disabled_inspection_still_has_non_executing_posture() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_ENABLED": "0"})
    context = _context("deploy it")

    result, receipt = runtime.inspect_request(context)
    summary = runtime.console_summary(
        results=(result,),
        receipts=tuple(receipt for receipt in (receipt,) if receipt is not None),
        created_at="2026-05-31T00:00:00+00:00",
    )

    assert result.mode == ShadowMode.OFF
    assert result.verdict == ShadowVerdict.CLEAR
    assert summary.enabled is False
    assert summary.recent_result_count == 1
    assert summary.to_dict()["execution_authority"] is False
