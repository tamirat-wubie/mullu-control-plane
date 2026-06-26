"""Focused tests for InceptaDive external-effect boundary advisories."""

from __future__ import annotations

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
