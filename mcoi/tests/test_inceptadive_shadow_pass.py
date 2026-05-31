"""Focused coverage for the InceptaDive Shadow Pass foundation."""

from __future__ import annotations

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.core.inceptadive_shadow_gate import decide_shadow_mode
from mcoi_runtime.core.inceptadive_shadow_light import run_light_shadow_pass
from mcoi_runtime.core.inceptadive_shadow_preflight import run_strict_preflight
from mcoi_runtime.core.inceptadive_shadow_posture import (
    build_shadow_console_summary,
    build_shadow_health_posture,
)
from mcoi_runtime.core.inceptadive_shadow_receipt import create_shadow_receipt
from mcoi_runtime.core.inceptadive_shadow_scoring import (
    ShadowSuppressionVector,
    safe_memory_denominator,
    score_shadow_finding,
)
from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowInterrogationConfig,
    ShadowFindingKind,
    ShadowMode,
    ShadowSeverity,
    ShadowStage,
    ShadowVerdict,
)


def _context(user_input: str, **overrides: object) -> ShadowContext:
    values = {
        "request_id": "req-shadow-1",
        "stage": ShadowStage.INTERPRETATION,
        "user_input": user_input,
        "created_at": "2026-05-31T00:00:00+00:00",
    }
    values.update(overrides)
    return ShadowContext(**values).with_integrity()


def test_gate_routes_deploy_it_to_deep_shadow() -> None:
    context = _context("deploy it")

    decision = decide_shadow_mode(context)

    assert decision.mode == ShadowMode.DEEP
    assert "ambiguous_reference_without_target" in decision.triggers
    assert any(trigger.startswith("deep_action:deploy") for trigger in decision.triggers)
    assert decision.strict_fail_closed is False


def test_gate_routes_delete_to_strict_preflight() -> None:
    context = _context("delete old logs", stage=ShadowStage.PREFLIGHT)

    decision = decide_shadow_mode(context)

    assert decision.mode == ShadowMode.STRICT_PREFLIGHT
    assert decision.strict_fail_closed is True
    assert any(trigger.startswith("strict_action:delete") for trigger in decision.triggers)


def test_light_pass_clear_for_safe_summary_request() -> None:
    context = _context("summarize this attached note", explicit_target="attached note")

    result = run_light_shadow_pass(context)

    assert result.verdict == ShadowVerdict.CLEAR
    assert result.mode == ShadowMode.LIGHT
    assert result.findings[0].kind == ShadowFindingKind.SAFE_CLEAR
    assert result.to_dict()["execution_authority"] is False


def test_light_pass_requests_repair_for_continue_without_scope() -> None:
    context = _context("continue the project")

    result = run_light_shadow_pass(context)

    assert result.verdict == ShadowVerdict.REPAIR_REQUIRED
    assert result.needs_repair is True
    assert any(finding.kind == ShadowFindingKind.MISSING_SCOPE for finding in result.findings)


def test_strict_preflight_blocks_deploy_without_target_or_evidence() -> None:
    context = _context(
        "deploy production dashboard",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="deploy production dashboard",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    result = run_strict_preflight(context)

    assert result.verdict == ShadowVerdict.BLOCK_RECOMMENDED
    assert result.block_recommended is True
    assert any(finding.kind == ShadowFindingKind.MISSING_TARGET for finding in result.findings)
    assert any(finding.kind == ShadowFindingKind.MISSING_EVIDENCE for finding in result.findings)
    assert result.to_dict()["execution_authority"] is False


def test_shadow_receipt_is_deterministic_and_non_executing() -> None:
    context = _context("summarize release notes", explicit_target="release notes")
    result = run_light_shadow_pass(context)

    receipt_a = create_shadow_receipt(context, result)
    receipt_b = create_shadow_receipt(context, result)

    assert receipt_a.receipt_id == receipt_b.receipt_id
    assert receipt_a.snapshot_hash == receipt_b.snapshot_hash
    assert receipt_a.finding_ids == tuple(finding.finding_id for finding in result.findings)
    assert receipt_a.to_dict()["execution_authority"] is False


def test_scoring_uses_mesh_denominator_guard_and_suppression() -> None:
    context = _context("delete production logs", stage=ShadowStage.PREFLIGHT)
    result = run_strict_preflight(context)
    unsafe = next(finding for finding in result.findings if finding.kind == ShadowFindingKind.UNSAFE_ACTION)

    score = score_shadow_finding(
        unsafe,
        ShadowSuppressionVector(execution_risk=1.0, privacy_or_safety_risk=0.8),
    )

    assert safe_memory_denominator(3, 3) == 1
    assert safe_memory_denominator(2, 5) == 1
    assert score.priority >= 0.75
    assert score.recommended_severity == ShadowSeverity.CRITICAL


def test_integration_disabled_returns_off_result() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_ENABLED": "0"})
    context = _context("deploy it")

    result, receipt = runtime.inspect_request(context)

    assert result.mode == ShadowMode.OFF
    assert result.verdict == ShadowVerdict.CLEAR
    assert receipt is not None
    assert receipt.mode == ShadowMode.OFF


def test_shadow_health_posture_is_integrity_bound_and_redacted() -> None:
    config = ShadowInterrogationConfig(enabled=True, strict_preflight_enabled=True)

    posture = build_shadow_health_posture(
        config,
        receipts_enabled=True,
        dependency_available=True,
        deep_engine_available=False,
        created_at="2026-05-31T01:00:00+00:00",
    )

    assert posture.status == "ready"
    assert posture.snapshot_hash == posture.expected_snapshot_hash()
    assert posture.to_dict()["execution_authority"] is False
    assert posture.to_dict()["raw_request_text_exposed"] is False


def test_shadow_console_summary_counts_redacted_recent_activity() -> None:
    context = _context(
        "delete production logs",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="delete production logs",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    result = run_strict_preflight(context)
    receipt = create_shadow_receipt(context, result)

    summary = build_shadow_console_summary(
        ShadowInterrogationConfig(enabled=True),
        results=(result,),
        receipts=(receipt,),
        created_at="2026-05-31T01:00:00+00:00",
    )

    assert summary.recent_result_count == 1
    assert summary.receipt_count == 1
    assert summary.block_recommended_count == 1
    assert summary.last_result_snapshot_hash == result.snapshot_hash
    assert summary.to_dict()["private_memory_exposed"] is False
