"""Focused tests for InceptaDive external-effect boundary advisories."""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.core.inceptadive_external_effect_boundary import (
    ExternalEffectBoundaryAdvisory,
    build_external_effect_boundary_advisory,
)
from mcoi_runtime.core.inceptadive_shadow_types import ShadowContext, ShadowSeverity, ShadowStage
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _context(user_input: str, **overrides: object) -> ShadowContext:
    values = {
        "request_id": "req-external-effect-1",
        "stage": ShadowStage.PREFLIGHT,
        "user_input": user_input,
        "created_at": "2026-06-20T00:00:00+00:00",
    }
    values.update(overrides)
    return ShadowContext(**values).with_integrity()


def _set_first_jsonl_field(path, field_name: str, field_value: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    payload[field_name] = field_value
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_external_effect_boundary_requires_authority_and_evidence_without_dispatch() -> None:
    context = _context(
        "deploy it with secret-token",
        candidate_action="deploy it with secret-token",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    advisory = build_external_effect_boundary_advisory(context)
    payload = advisory.to_dict()

    assert advisory.recommended_outcome == "AwaitingEvidence"
    assert advisory.awaiting_evidence is True
    assert "deployment" in advisory.action_families
    assert advisory.missing_authority_obligations == ("deployment:governance_verdict",)
    assert advisory.missing_evidence_obligations == ("deployment:evidence_ref",)
    assert payload["execution_authority"] is False
    assert payload["connector_dispatch_authority"] is False
    assert payload["memory_write_authority"] is False
    assert payload["governance_verdict_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert "deploy it with secret-token" not in str(payload)
    assert "secret-token" not in str(payload)


def test_external_effect_boundary_closes_evidence_without_granting_authority() -> None:
    context = _context(
        "send approved receipt",
        request_id="req-external-effect-2",
        candidate_action="send approved receipt",
        explicit_target="operator-review-inbox",
        scope="support-workflow",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    advisory = build_external_effect_boundary_advisory(
        context,
        required_evidence_refs=("approval-secret-ref",),
        authority_receipt_refs=("authority-secret-ref",),
    )
    payload = advisory.to_dict()

    assert advisory.recommended_outcome == "SolvedUnverified"
    assert advisory.missing_authority_obligations == ()
    assert advisory.missing_evidence_obligations == ()
    assert advisory.required_evidence_ref_count == 1
    assert advisory.authority_receipt_count == 1
    assert advisory.external_side_effect is True
    assert payload["execution_authority"] is False
    assert "approval-secret-ref" not in str(payload)
    assert "authority-secret-ref" not in str(payload)


def test_runtime_facade_returns_external_effect_boundary_advisory() -> None:
    runtime = build_inceptadive_shadow_runtime({})
    context = _context(
        "publish public claim",
        request_id="req-external-effect-3",
        stage=ShadowStage.INTERPRETATION,
        candidate_action="publish public claim",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    advisory = runtime.external_effect_advisory(context)
    payload = advisory.to_dict()
    recent_advisories = runtime.recent_external_effect_advisories(limit=5)

    assert advisory.request_id == "req-external-effect-3"
    assert advisory.strict_preflight_required is True
    assert advisory.external_side_effect is True
    assert advisory.recommended_outcome == "AwaitingEvidence"
    assert recent_advisories == (advisory,)
    assert payload["execution_authority"] is False
    assert payload["private_memory_exposed"] is False


def test_runtime_records_jsonl_external_effect_advisory_without_raw_refs(tmp_path) -> None:
    runtime = build_inceptadive_shadow_runtime(
        {"MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path)}
    )
    context = _context(
        "send approved receipt with secret-token",
        request_id="req-external-effect-jsonl-1",
        candidate_action="send approved receipt with secret-token",
        explicit_target="operator-review-inbox",
        scope="support-workflow",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    advisory = runtime.external_effect_advisory(
        context,
        required_evidence_refs=("approval-secret-ref",),
        authority_receipt_refs=("authority-secret-ref",),
    )
    recent_advisories = runtime.recent_external_effect_advisories(limit=5)
    jsonl_text = (tmp_path / "external-effect-advisories.jsonl").read_text(encoding="utf-8")

    assert recent_advisories == (advisory,)
    assert advisory.required_evidence_ref_count == 1
    assert advisory.authority_receipt_count == 1
    assert advisory.to_dict()["raw_request_text_exposed"] is False
    assert "approval-secret-ref" not in jsonl_text
    assert "authority-secret-ref" not in jsonl_text
    assert "secret-token" not in jsonl_text


def test_jsonl_shadow_store_replays_recent_result_receipt_and_advisory_after_restart(tmp_path) -> None:
    env = {
        "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path),
        "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
    }
    runtime = build_inceptadive_shadow_runtime(env)
    context = _context(
        "deploy it with replay-secret-token",
        request_id="req-external-effect-replay-1",
        stage=ShadowStage.INTERPRETATION,
        candidate_action="deploy it with replay-secret-token",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )

    result, receipt = runtime.inspect_request(context)
    advisory = runtime.external_effect_advisory(context)
    restarted_runtime = build_inceptadive_shadow_runtime(env)
    replayed_results, replayed_receipts = restarted_runtime.recent_activity(limit=5)
    replayed_advisories = restarted_runtime.recent_external_effect_advisories(limit=5)

    assert receipt is not None
    assert tuple(item.result_id for item in replayed_results) == (result.result_id,)
    assert tuple(item.receipt_id for item in replayed_receipts) == (receipt.receipt_id,)
    assert tuple(item.advisory_id for item in replayed_advisories) == (advisory.advisory_id,)
    assert replayed_results[0].snapshot_hash == result.snapshot_hash
    assert replayed_receipts[0].snapshot_hash == receipt.snapshot_hash
    assert replayed_advisories[0].missing_authority_obligations == advisory.missing_authority_obligations
    assert "replay-secret-token" not in str(replayed_results[0].to_dict())
    assert "replay-secret-token" not in str(replayed_advisories[0].to_dict())


def test_jsonl_shadow_store_rejects_corrupt_replay_record(tmp_path) -> None:
    (tmp_path / "external-effect-advisories.jsonl").write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path)})

    assert "external-effect-advisories.jsonl" in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert "invalid JSONL record" in str(exc_info.value)


def test_jsonl_shadow_store_rejects_tampered_result_snapshot(tmp_path) -> None:
    env = {
        "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path),
        "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
    }
    runtime = build_inceptadive_shadow_runtime(env)
    context = _context(
        "deploy it with tamper-secret-token",
        request_id="req-external-effect-tamper-1",
        stage=ShadowStage.INTERPRETATION,
        candidate_action="deploy it with tamper-secret-token",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    runtime.inspect_request(context)
    result_path = tmp_path / "shadow-results.jsonl"
    payload = json.loads(result_path.read_text(encoding="utf-8").splitlines()[0])
    payload["snapshot_hash"] = "tampered"
    result_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        build_inceptadive_shadow_runtime(env)

    assert "shadow-results.jsonl" in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert "invalid JSONL record" in str(exc_info.value)
    assert "tamper-secret-token" not in str(exc_info.value)


def test_jsonl_shadow_store_rejects_tampered_result_authority_flag(tmp_path) -> None:
    env = {
        "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path),
        "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
    }
    runtime = build_inceptadive_shadow_runtime(env)
    context = _context(
        "deploy it with result-authority-secret-token",
        request_id="req-external-effect-result-authority-1",
        stage=ShadowStage.INTERPRETATION,
        candidate_action="deploy it with result-authority-secret-token",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    runtime.inspect_request(context)
    _set_first_jsonl_field(tmp_path / "shadow-results.jsonl", "execution_authority", True)

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        build_inceptadive_shadow_runtime(env)

    assert "shadow-results.jsonl" in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeCoreInvariantError)
    assert "execution_authority must be false" in str(exc_info.value.__cause__)
    assert "result-authority-secret-token" not in str(exc_info.value)


def test_jsonl_shadow_store_rejects_tampered_receipt_authority_flag(tmp_path) -> None:
    env = {
        "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path),
        "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
    }
    runtime = build_inceptadive_shadow_runtime(env)
    context = _context(
        "deploy it with receipt-authority-secret-token",
        request_id="req-external-effect-receipt-authority-1",
        stage=ShadowStage.INTERPRETATION,
        candidate_action="deploy it with receipt-authority-secret-token",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    runtime.inspect_request(context)
    _set_first_jsonl_field(tmp_path / "shadow-receipts.jsonl", "execution_authority", True)

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        build_inceptadive_shadow_runtime(env)

    assert "shadow-receipts.jsonl" in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeCoreInvariantError)
    assert "execution_authority must be false" in str(exc_info.value.__cause__)
    assert "receipt-authority-secret-token" not in str(exc_info.value)


@pytest.mark.parametrize("flag_name", ("execution_authority", "raw_request_text_exposed"))
def test_jsonl_shadow_store_rejects_tampered_advisory_authority_or_exposure_flag(
    tmp_path,
    flag_name: str,
) -> None:
    env = {"MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(tmp_path)}
    runtime = build_inceptadive_shadow_runtime(env)
    context = _context(
        "send advisory-authority-secret-token",
        request_id=f"req-external-effect-advisory-{flag_name}",
        candidate_action="send advisory-authority-secret-token",
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
    )
    runtime.external_effect_advisory(context)
    _set_first_jsonl_field(tmp_path / "external-effect-advisories.jsonl", flag_name, True)

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        build_inceptadive_shadow_runtime(env)

    assert "external-effect-advisories.jsonl" in str(exc_info.value)
    assert "line 1" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeCoreInvariantError)
    assert f"{flag_name} must be false" in str(exc_info.value.__cause__)
    assert "advisory-authority-secret-token" not in str(exc_info.value)


def test_external_effect_boundary_rejects_authority_flags() -> None:
    with pytest.raises(RuntimeCoreInvariantError):
        ExternalEffectBoundaryAdvisory(
            advisory_id="external-effect-authority-violation",
            request_id="req-external-effect-4",
            context_hash="hash",
            action_families=("deployment",),
            authority_obligations=("deployment:governance_verdict",),
            evidence_obligations=("deployment:evidence_ref",),
            missing_authority_obligations=(),
            missing_evidence_obligations=(),
            required_evidence_ref_count=1,
            authority_receipt_count=1,
            retrieval_receipt_count=0,
            external_side_effect=True,
            strict_preflight_required=True,
            recommended_outcome="SolvedUnverified",
            recommended_action="continue through governance",
            execution_authority=True,
        )
