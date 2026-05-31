"""Focused tests for InceptaDive Shadow Pass posture summaries."""

from __future__ import annotations

from mcoi_runtime.core.inceptadive_shadow_light import run_light_shadow_pass
from mcoi_runtime.core.inceptadive_shadow_posture import (
    build_shadow_console_summary,
    build_shadow_health_posture,
)
from mcoi_runtime.core.inceptadive_shadow_preflight import run_strict_preflight
from mcoi_runtime.core.inceptadive_shadow_receipt import create_shadow_receipt
from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowInterrogationConfig,
    ShadowMode,
    ShadowSeverity,
    ShadowStage,
    ShadowVerdict,
)


def _context(user_input: str, **overrides: object) -> ShadowContext:
    values = {
        "request_id": "req-shadow-posture-1",
        "stage": ShadowStage.INTERPRETATION,
        "user_input": user_input,
        "created_at": "2026-05-31T00:00:00+00:00",
    }
    values.update(overrides)
    return ShadowContext(**values).with_integrity()


def test_health_posture_ready_when_enabled_and_dependency_available() -> None:
    config = ShadowInterrogationConfig(
        enabled=True,
        light_always_on=True,
        deep_enabled=True,
        strict_preflight_enabled=True,
        max_findings=12,
        max_depth=3,
    )

    posture = build_shadow_health_posture(
        config,
        receipts_enabled=True,
        dependency_available=True,
        deep_engine_available=False,
        created_at="2026-05-31T00:00:00+00:00",
    )

    payload = posture.to_dict()
    assert posture.status == "ready"
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert posture.snapshot_hash == posture.expected_snapshot_hash()


def test_health_posture_degraded_when_dependency_unavailable() -> None:
    config = ShadowInterrogationConfig(enabled=True)

    posture = build_shadow_health_posture(
        config,
        receipts_enabled=True,
        dependency_available=False,
        created_at="2026-05-31T00:00:00+00:00",
    )

    assert posture.status == "degraded"
    assert posture.strict_fail_closed_ready is False


def test_console_summary_counts_shadow_results_without_raw_text() -> None:
    config = ShadowInterrogationConfig(enabled=True)
    light_context = _context("continue the project")
    preflight_context = _context(
        "delete production logs",
        request_id="req-shadow-posture-2",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="delete production logs",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    light_result = run_light_shadow_pass(light_context)
    preflight_result = run_strict_preflight(preflight_context)
    receipts = (
        create_shadow_receipt(light_context, light_result),
        create_shadow_receipt(preflight_context, preflight_result),
    )

    summary = build_shadow_console_summary(
        config,
        results=(light_result, preflight_result),
        receipts=receipts,
        created_at="2026-05-31T00:00:00+00:00",
    )

    payload = summary.to_dict()
    assert summary.recent_result_count == 2
    assert summary.receipt_count == 2
    assert "light:1" in summary.mode_counts
    assert "strict_preflight:1" in summary.mode_counts
    assert "repair_required:1" in summary.verdict_counts
    assert "block_recommended:1" in summary.verdict_counts
    assert summary.repair_required_count == 2
    assert summary.block_recommended_count == 1
    assert summary.fracture_delta_count >= 2
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert "continue the project" not in str(payload)
    assert "delete production logs" not in str(payload)


def test_console_summary_is_deterministic_for_same_inputs() -> None:
    config = ShadowInterrogationConfig(enabled=True)
    context = _context("summarize release notes", explicit_target="release notes")
    result = run_light_shadow_pass(context)
    receipt = create_shadow_receipt(context, result)

    summary_a = build_shadow_console_summary(
        config,
        results=(result,),
        receipts=(receipt,),
        created_at="2026-05-31T00:00:00+00:00",
    )
    summary_b = build_shadow_console_summary(
        config,
        results=(result,),
        receipts=(receipt,),
        created_at="2026-05-31T00:00:00+00:00",
    )

    assert summary_a.summary_id == summary_b.summary_id
    assert summary_a.snapshot_hash == summary_b.snapshot_hash
    assert summary_a.last_result_snapshot_hash == result.snapshot_hash
    assert summary_a.enabled is True
    assert summary_a.to_dict()["execution_authority"] is False


def test_disabled_health_and_console_remain_read_only() -> None:
    config = ShadowInterrogationConfig(enabled=False)

    posture = build_shadow_health_posture(
        config,
        receipts_enabled=False,
        created_at="2026-05-31T00:00:00+00:00",
    )
    summary = build_shadow_console_summary(
        config,
        created_at="2026-05-31T00:00:00+00:00",
    )

    assert posture.status == "disabled"
    assert posture.to_dict()["execution_authority"] is False
    assert summary.enabled is False
    assert summary.recent_result_count == 0
    assert summary.to_dict()["execution_authority"] is False
    assert ShadowMode.OFF.value == "off"
    assert ShadowVerdict.CLEAR.value == "clear"
