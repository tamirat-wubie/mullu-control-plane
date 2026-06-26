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


def test_runtime_receipt_redacts_raw_retrieval_refs_before_persistence(tmp_path) -> None:
    raw_retrieval_ref = "retrieval-secret-token-001"
    store_path = tmp_path / "shadow-store"
    runtime = build_inceptadive_shadow_runtime(
        {
            "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
            "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(store_path),
        }
    )
    context = _context(
        "deploy it with receipt",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
        retrieval_receipt_ids=(raw_retrieval_ref,),
    )

    _result, receipt = runtime.inspect_request(context)

    assert receipt is not None
    assert receipt.retrieval_receipt_ids[0].startswith("shadow_retrieval_receipt_")
    assert raw_retrieval_ref not in str(receipt.to_dict())
    assert receipt.to_dict()["retrieval_receipt_ids"] == list(receipt.retrieval_receipt_ids)
    persisted_receipts = (store_path / "shadow-receipts.jsonl").read_text(encoding="utf-8")
    assert raw_retrieval_ref not in persisted_receipts
    assert "shadow_retrieval_receipt_" in persisted_receipts
    assert receipt.to_dict()["execution_authority"] is False


def test_runtime_preflight_redacts_raw_required_evidence_refs_before_persistence(tmp_path) -> None:
    raw_evidence_ref = "approval-secret-evidence-001"
    store_path = tmp_path / "shadow-store"
    runtime = build_inceptadive_shadow_runtime(
        {
            "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
            "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(store_path),
        }
    )
    context = _context(
        "send approved receipt",
        request_id="req-deep-runtime-evidence-redaction-1",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="send approved receipt",
        explicit_target="operator-review-inbox",
        scope="support-workflow",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    result, receipt = runtime.preflight_action(context, required_evidence_refs=(raw_evidence_ref,))

    payload = result.to_dict()
    evidence_finding = next(
        finding
        for finding in result.findings
        if finding.summary == "preflight received explicit evidence references"
    )
    assert evidence_finding.evidence_refs[0].startswith("shadow_required_evidence_")
    assert raw_evidence_ref not in str(payload)
    persisted_finding = next(
        finding
        for finding in payload["findings"]
        if finding["finding_id"] == evidence_finding.finding_id
    )
    assert persisted_finding["evidence_refs"] == list(evidence_finding.evidence_refs)
    persisted_results = (store_path / "shadow-results.jsonl").read_text(encoding="utf-8")
    assert raw_evidence_ref not in persisted_results
    assert "shadow_required_evidence_" in persisted_results
    assert receipt is not None
    assert receipt.to_dict()["execution_authority"] is False


def test_deep_engine_can_be_disabled_without_silent_success() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "0"})
    context = _context("deploy it", risk_level=ShadowSeverity.HIGH, external_side_effect=True)

    result, _receipt = runtime.inspect_request(context)

    assert result.mode == ShadowMode.DEEP
    assert result.verdict == ShadowVerdict.DEEP_REQUIRED
    assert result.needs_deep_pass is True
    assert result.to_dict()["execution_authority"] is False


def test_external_effect_preflight_gets_bounded_deep_advisory_when_enabled() -> None:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1"})
    context = _context(
        "send approved receipt",
        request_id="req-deep-runtime-preflight-1",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="send approved receipt",
        explicit_target="operator-review-inbox",
        scope="support-workflow",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    result, receipt = runtime.preflight_action(context, required_evidence_refs=("approval-receipt-1",))
    payload = result.to_dict()
    summaries = tuple(finding.summary for finding in result.findings)

    assert result.mode == ShadowMode.STRICT_PREFLIGHT
    assert result.needs_deep_pass is False
    assert result.verdict in {ShadowVerdict.ADVISORY, ShadowVerdict.REPAIR_REQUIRED, ShadowVerdict.BLOCK_RECOMMENDED}
    assert any(summary == "deep interrogation found possible external side effect" for summary in summaries)
    assert any(summary == "preflight received explicit evidence references" for summary in summaries)
    assert payload["execution_authority"] is False
    assert "send approved receipt" not in str(payload)
    assert receipt is not None
    assert receipt.mode == ShadowMode.STRICT_PREFLIGHT
    assert receipt.to_dict()["execution_authority"] is False


def test_external_effect_preflight_keeps_default_disabled_deep_posture() -> None:
    runtime = build_inceptadive_shadow_runtime({})
    context = _context(
        "send approved receipt",
        request_id="req-deep-runtime-preflight-2",
        stage=ShadowStage.PREFLIGHT,
        candidate_action="send approved receipt",
        explicit_target="operator-review-inbox",
        scope="support-workflow",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    result, receipt = runtime.preflight_action(context, required_evidence_refs=("approval-receipt-1",))
    summaries = tuple(finding.summary for finding in result.findings)

    assert result.mode == ShadowMode.STRICT_PREFLIGHT
    assert result.needs_deep_pass is False
    assert not any(summary.startswith("deep interrogation found") for summary in summaries)
    assert any(summary == "preflight received explicit evidence references" for summary in summaries)
    assert result.to_dict()["execution_authority"] is False
    assert receipt is not None
    assert receipt.mode == ShadowMode.STRICT_PREFLIGHT
