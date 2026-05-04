"""Purpose: test Reflex Engine governed self-improvement contracts and gates.
Governance scope: verifies evidence binding, diagnosis/eval generation,
    protected-surface promotion blocking, and capability maturity scoring.
Dependencies: pytest and MCOI reflex/change-assurance contract/core layers.
Invariants:
  - Reflex candidates remain proposals until sandbox and certificate gates pass.
  - Protected surfaces cannot be auto-promoted.
  - Generated evals preserve evidence references.
  - Capability closure requires proof and production evidence.
"""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.change_assurance import ChangeCertificate
from mcoi_runtime.contracts.change_assurance import ChangeRisk, EvolutionChangeType
from mcoi_runtime.contracts.reflex import (
    CapabilityMaturityScore,
    ReflexEvidenceRef,
    ReflexFailureClass,
    ReflexPromotionDisposition,
    ReflexRisk,
    ReflexSandboxResult,
    ReflexUpgradeCandidate,
    RuntimeHealthSnapshot,
)
from mcoi_runtime.core.reflex import (
    build_certification_handoff,
    build_reflex_change_command,
    build_sandbox_bundle,
    candidate_requires_human_approval,
    decide_promotion,
    detect_anomalies,
    diagnose_anomaly,
    generate_eval_cases,
    propose_upgrade,
    rank_capability_gaps,
    run_reflex_replay,
)


DT = "2026-05-04T12:00:00+00:00"


def _evidence() -> ReflexEvidenceRef:
    return ReflexEvidenceRef(kind="trace", ref_id="trace-001", evidence_hash="abc123")


def _snapshot(**metrics: object) -> RuntimeHealthSnapshot:
    return RuntimeHealthSnapshot(
        snapshot_id="snap-001",
        runtime="production",
        time_window="last_1h",
        metrics=metrics,
        evidence_refs=(_evidence(),),
        captured_at=DT,
    )


def _certificate(**overrides: object) -> ChangeCertificate:
    values = {
        "certificate_id": "cert-001",
        "change_id": "chg-001",
        "schema_checks_passed": True,
        "tests_passed": True,
        "replay_passed": True,
        "invariant_checks_passed": True,
        "migration_safe": True,
        "rollback_plan_present": True,
        "approval_id": None,
        "evidence_refs": ("change_command.json", "release_certificate.json"),
        "certified_at": DT,
    }
    values.update(overrides)
    return ChangeCertificate(**values)


def test_runtime_snapshot_contract_is_frozen_and_evidence_backed() -> None:
    snapshot = _snapshot(unverified_executions=1, avg_latency_ms=840)
    payload = snapshot.to_json_dict()

    assert snapshot.snapshot_id == "snap-001"
    assert payload["evidence_refs"][0]["ref_id"] == "trace-001"
    assert isinstance(snapshot.metrics, MappingProxyType)
    with pytest.raises(Exception):
        snapshot.metrics["extra"] = 1  # type: ignore[index]


def test_detect_anomalies_maps_metrics_to_failure_class_and_risk() -> None:
    snapshot = _snapshot(unverified_executions=2, provider_timeouts=0)
    anomalies = detect_anomalies(snapshot)

    assert len(anomalies) == 1
    assert anomalies[0].failure_class is ReflexFailureClass.PROOF_MISSING
    assert anomalies[0].risk is ReflexRisk.HIGH
    assert anomalies[0].evidence_refs[0].ref_id == "trace-001"


def test_diagnosis_and_eval_preserve_causal_evidence() -> None:
    snapshot = _snapshot(pii_leaks=1)
    anomaly = detect_anomalies(snapshot)[0]
    diagnosis = diagnose_anomaly(anomaly, snapshot)
    eval_case = generate_eval_cases(diagnosis)[0]

    assert diagnosis.failure_class is ReflexFailureClass.PII_REDACTION_FAILURE
    assert diagnosis.surface == "content_safety"
    assert eval_case.diagnosis_id == diagnosis.diagnosis_id
    assert "redaction_receipt_present" in eval_case.assertions
    assert eval_case.evidence_refs[0].ref_id == "trace-001"


def test_upgrade_planner_blocks_protected_surfaces_from_auto_promotion() -> None:
    snapshot = _snapshot(unverified_executions=1)
    diagnosis = diagnose_anomaly(detect_anomalies(snapshot)[0], snapshot)
    eval_cases = generate_eval_cases(diagnosis)
    candidate = propose_upgrade(diagnosis, eval_cases)

    assert candidate.change_surface == "proof"
    assert candidate.risk is ReflexRisk.HIGH
    assert "effect_reconciliation" in candidate.required_replays
    assert candidate.eval_ids == (eval_cases[0].eval_id,)
    assert candidate_requires_human_approval(candidate) is True


def test_low_risk_provider_routing_candidate_can_reach_auto_canary_after_gates() -> None:
    snapshot = _snapshot(premium_model_low_risk_requests=4)
    diagnosis = diagnose_anomaly(detect_anomalies(snapshot)[0], snapshot)
    candidate = propose_upgrade(diagnosis, generate_eval_cases(diagnosis))
    sandbox_result = ReflexSandboxResult(
        candidate_id=candidate.candidate_id,
        passed=True,
        report_refs=(ReflexEvidenceRef(kind="sandbox_report", ref_id="sandbox-001"),),
    )
    decision = decide_promotion(candidate, sandbox_result, _certificate())

    assert candidate.change_surface == "provider_routing"
    assert candidate.risk is ReflexRisk.LOW
    assert decision.disposition is ReflexPromotionDisposition.AUTO_CANARY_ALLOWED
    assert decision.requires_human_approval is False
    assert decision.protected_surface is False


def test_certificate_or_sandbox_failure_rejects_candidate_before_promotion() -> None:
    snapshot = _snapshot(premium_model_low_risk_requests=4)
    diagnosis = diagnose_anomaly(detect_anomalies(snapshot)[0], snapshot)
    candidate = propose_upgrade(diagnosis, generate_eval_cases(diagnosis))
    failed_sandbox = ReflexSandboxResult(
        candidate_id=candidate.candidate_id,
        passed=False,
        failed_checks=("eval:quality_regression",),
    )
    bad_certificate = _certificate(replay_passed=False)

    sandbox_decision = decide_promotion(candidate, failed_sandbox, _certificate())
    certificate_decision = decide_promotion(
        candidate,
        ReflexSandboxResult(candidate_id=candidate.candidate_id, passed=True),
        bad_certificate,
    )

    assert sandbox_decision.disposition is ReflexPromotionDisposition.REJECTED
    assert "sandbox" in sandbox_decision.reason
    assert certificate_decision.disposition is ReflexPromotionDisposition.REJECTED
    assert "certificate" in certificate_decision.reason


def test_capability_maturity_ranking_prefers_largest_verified_gap() -> None:
    email_score = CapabilityMaturityScore(
        capability="email.send",
        correctness_score=0.78,
        safety_score=0.91,
        governance_score=0.95,
        proof_score=0.62,
        latency_score=0.83,
        cost_score=0.98,
        production_evidence_score=0.30,
        missing=("live provider receipt", "deployment witness"),
    )
    faq_score = CapabilityMaturityScore(
        capability="support.faq",
        correctness_score=0.93,
        safety_score=0.96,
        governance_score=0.97,
        proof_score=0.91,
        latency_score=0.90,
        cost_score=0.94,
        production_evidence_score=0.88,
    )
    ranked = rank_capability_gaps((faq_score, email_score))

    assert ranked[0].capability == "email.send"
    assert ranked[0].verdict == "not_production_closed"
    assert ranked[1].verdict == "production_closed"
    assert ranked[0].value_gap > ranked[1].value_gap


def test_reflex_candidate_builds_governed_change_command_for_protected_surface() -> None:
    snapshot = _snapshot(unverified_executions=1)
    diagnosis = diagnose_anomaly(detect_anomalies(snapshot)[0], snapshot)
    candidate = propose_upgrade(diagnosis, generate_eval_cases(diagnosis))

    command = build_reflex_change_command(
        candidate,
        author_id="reflex@mullusi.com",
        branch="codex/reflex-proof-gap",
        base_commit="a" * 40,
        head_commit="b" * 40,
        created_at=DT,
    )

    assert command.change_id == f"change:{candidate.candidate_id}"
    assert command.change_type is EvolutionChangeType.POLICY
    assert command.risk is ChangeRisk.CRITICAL
    assert command.requires_approval is True
    assert command.rollback_required is True
    assert command.metadata["reflex_candidate_id"] == candidate.candidate_id
    assert "no_protected_reflex_surface_without_human_approval" in command.affected_invariants


def test_reflex_certification_handoff_is_non_mutating_and_cli_ready() -> None:
    snapshot = _snapshot(premium_model_low_risk_requests=4)
    diagnosis = diagnose_anomaly(detect_anomalies(snapshot)[0], snapshot)
    candidate = propose_upgrade(diagnosis, generate_eval_cases(diagnosis))

    handoff = build_certification_handoff(
        candidate,
        author_id="reflex@mullusi.com",
        branch="codex/reflex-routing",
        base_commit="a" * 40,
        head_commit="b" * 40,
        created_at=DT,
        base_ref="main",
        head_ref="codex/reflex-routing",
    )
    payload = handoff.to_json_dict()

    assert handoff.mutation_applied is False
    assert handoff.change_command.change_type is EvolutionChangeType.CONFIGURATION
    assert handoff.change_command.risk is ChangeRisk.LOW
    assert "--strict" in handoff.command_args
    assert "main" in handoff.command_args
    assert "codex/reflex-routing" in handoff.command_args
    assert "release_certificate.json" in handoff.required_artifacts
    assert payload["change_command"]["metadata"]["reflex_change_surface"] == "provider_routing"


def test_reflex_sandbox_bundle_runs_declared_replays_without_side_effects() -> None:
    snapshot = _snapshot(premium_model_low_risk_requests=4)
    diagnosis = diagnose_anomaly(detect_anomalies(snapshot)[0], snapshot)
    eval_cases = generate_eval_cases(diagnosis)
    candidate = propose_upgrade(diagnosis, eval_cases)

    bundle = build_sandbox_bundle(candidate, eval_cases)
    payload = bundle.to_json_dict()

    assert bundle.mutation_applied is False
    assert bundle.sandbox_result.passed is True
    assert bundle.sandbox_result.failed_checks == ()
    assert bundle.eval_ids == candidate.eval_ids
    assert {result.replay_id for result in bundle.replay_results} == set(candidate.required_replays)
    assert all(result.passed for result in bundle.replay_results)
    assert payload["sandbox_result"]["passed"] is True


def test_reflex_sandbox_bundle_fails_missing_eval_and_unknown_replay() -> None:
    candidate = ReflexUpgradeCandidate(
        candidate_id="candidate:bad",
        diagnosis_id="diagnosis:bad",
        change_surface="provider_routing",
        risk=ReflexRisk.LOW,
        description="bad sandbox candidate",
        affected_files=("mcoi/mcoi_runtime/core/provider_cost_routing.py",),
        required_replays=("unknown_replay",),
        rollback_plan_ref="rollback:provider_routing",
        eval_ids=("eval:missing",),
    )

    replay_result = run_reflex_replay(candidate, "unknown_replay")
    bundle = build_sandbox_bundle(candidate, ())

    assert replay_result.passed is False
    assert "not registered" in replay_result.detail
    assert bundle.sandbox_result.passed is False
    assert "missing_eval:eval:missing" in bundle.sandbox_result.failed_checks
    assert any(
        failed_check.startswith("replay_failed:unknown_replay")
        for failed_check in bundle.sandbox_result.failed_checks
    )

