"""Purpose: governed Reflex Engine core for bounded runtime self-inspection.
Governance scope: anomaly detection, diagnosis, eval generation, candidate
    proposal, sandbox/certificate promotion gates, and maturity gap ranking.
Dependencies: Reflex contracts and change-assurance certificates.
Invariants:
  - Reflex outputs are proposals and decisions, never direct runtime mutation.
  - Every generated eval preserves source evidence.
  - Protected governance surfaces require human approval.
  - Sandbox and certificate failures reject promotion before canary admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from mcoi_runtime.contracts.change_assurance import (
    ChangeCertificate,
    ChangeCommand,
    ChangeRisk,
    EvolutionChangeType,
)
from mcoi_runtime.contracts.reflex import (
    CapabilityMaturityScore,
    ReflexAnomaly,
    ReflexCanaryHandoff,
    ReflexCertificationHandoff,
    ReflexDiagnosis,
    ReflexEvalCase,
    ReflexEvalClass,
    ReflexEvidenceRef,
    ReflexFailureClass,
    ReflexPromotionDecision,
    ReflexPromotionDisposition,
    ReflexReplayResult,
    ReflexRisk,
    ReflexSandboxBundle,
    ReflexSandboxResult,
    ReflexUpgradeCandidate,
    RuntimeHealthSnapshot,
)


@dataclass(frozen=True, slots=True)
class _MetricRule:
    metric_name: str
    threshold_value: float
    failure_class: ReflexFailureClass
    risk: ReflexRisk


_ANOMALY_RULES: tuple[_MetricRule, ...] = (
    _MetricRule(
        "policy_false_allows",
        0.0,
        ReflexFailureClass.POLICY_FALSE_ALLOW,
        ReflexRisk.CRITICAL,
    ),
    _MetricRule(
        "policy_false_denies",
        0.0,
        ReflexFailureClass.POLICY_FALSE_DENY,
        ReflexRisk.MEDIUM,
    ),
    _MetricRule(
        "missing_approvals",
        0.0,
        ReflexFailureClass.APPROVAL_MISSING,
        ReflexRisk.CRITICAL,
    ),
    _MetricRule("rbac_scope_leaks", 0.0, ReflexFailureClass.RBAC_SCOPE_LEAK, ReflexRisk.CRITICAL),
    _MetricRule(
        "tenant_boundary_leaks",
        0.0,
        ReflexFailureClass.TENANT_BOUNDARY_LEAK,
        ReflexRisk.CRITICAL,
    ),
    _MetricRule(
        "budget_false_allows",
        0.0,
        ReflexFailureClass.BUDGET_FALSE_ALLOW,
        ReflexRisk.CRITICAL,
    ),
    _MetricRule("pii_leaks", 0.0, ReflexFailureClass.PII_REDACTION_FAILURE, ReflexRisk.HIGH),
    _MetricRule(
        "prompt_injection_failures",
        0.0,
        ReflexFailureClass.PROMPT_INJECTION_FAILURE,
        ReflexRisk.HIGH,
    ),
    _MetricRule(
        "tool_schema_mismatches",
        0.0,
        ReflexFailureClass.TOOL_SCHEMA_MISMATCH,
        ReflexRisk.MEDIUM,
    ),
    _MetricRule("provider_timeouts", 0.0, ReflexFailureClass.PROVIDER_TIMEOUT, ReflexRisk.MEDIUM),
    _MetricRule(
        "provider_cost_spikes",
        0.0,
        ReflexFailureClass.PROVIDER_COST_SPIKE,
        ReflexRisk.MEDIUM,
    ),
    _MetricRule(
        "retrieval_low_relevance",
        0.0,
        ReflexFailureClass.RETRIEVAL_LOW_RELEVANCE,
        ReflexRisk.MEDIUM,
    ),
    _MetricRule(
        "memory_bad_admissions",
        0.0,
        ReflexFailureClass.MEMORY_BAD_ADMISSION,
        ReflexRisk.HIGH,
    ),
    _MetricRule("unverified_executions", 0.0, ReflexFailureClass.PROOF_MISSING, ReflexRisk.HIGH),
    _MetricRule(
        "verification_inconclusive",
        0.0,
        ReflexFailureClass.VERIFICATION_INCONCLUSIVE,
        ReflexRisk.MEDIUM,
    ),
    _MetricRule(
        "deployment_witness_missing",
        0.0,
        ReflexFailureClass.DEPLOYMENT_WITNESS_MISSING,
        ReflexRisk.HIGH,
    ),
    _MetricRule(
        "premium_model_low_risk_requests",
        0.0,
        ReflexFailureClass.MODEL_OVERKILL_FOR_LOW_RISK_TASK,
        ReflexRisk.LOW,
    ),
)


_SURFACE_BY_FAILURE: Mapping[ReflexFailureClass, str] = {
    ReflexFailureClass.POLICY_FALSE_ALLOW: "policy",
    ReflexFailureClass.POLICY_FALSE_DENY: "policy",
    ReflexFailureClass.APPROVAL_MISSING: "approval",
    ReflexFailureClass.RBAC_SCOPE_LEAK: "rbac",
    ReflexFailureClass.TENANT_BOUNDARY_LEAK: "tenant_isolation",
    ReflexFailureClass.BUDGET_FALSE_ALLOW: "budget",
    ReflexFailureClass.PII_REDACTION_FAILURE: "content_safety",
    ReflexFailureClass.PROMPT_INJECTION_FAILURE: "content_safety",
    ReflexFailureClass.TOOL_SCHEMA_MISMATCH: "tool_schema",
    ReflexFailureClass.PROVIDER_TIMEOUT: "provider_routing",
    ReflexFailureClass.PROVIDER_COST_SPIKE: "provider_routing",
    ReflexFailureClass.RETRIEVAL_LOW_RELEVANCE: "retrieval",
    ReflexFailureClass.MEMORY_BAD_ADMISSION: "memory_admission",
    ReflexFailureClass.PROOF_MISSING: "proof",
    ReflexFailureClass.VERIFICATION_INCONCLUSIVE: "verification",
    ReflexFailureClass.DEPLOYMENT_WITNESS_MISSING: "deployment_witness",
    ReflexFailureClass.MODEL_OVERKILL_FOR_LOW_RISK_TASK: "provider_routing",
}


_ASSERTIONS_BY_FAILURE: Mapping[ReflexFailureClass, tuple[str, ...]] = {
    ReflexFailureClass.POLICY_FALSE_ALLOW: (
        "guard_chain_denies_forbidden_intent",
        "denial_receipt_present",
        "policy_rule_id_bound",
    ),
    ReflexFailureClass.POLICY_FALSE_DENY: (
        "allowed_intent_preserves_policy",
        "denial_reason_is_absent",
        "policy_rule_id_bound",
    ),
    ReflexFailureClass.APPROVAL_MISSING: (
        "approval_required_for_high_risk",
        "approval_receipt_present",
        "execution_deferred_before_approval",
    ),
    ReflexFailureClass.RBAC_SCOPE_LEAK: (
        "role_scope_checked",
        "forbidden_role_denied",
        "denial_receipt_present",
    ),
    ReflexFailureClass.TENANT_BOUNDARY_LEAK: (
        "tenant_id_resolved",
        "cross_tenant_reference_denied",
        "audit_receipt_tenant_bound",
    ),
    ReflexFailureClass.BUDGET_FALSE_ALLOW: (
        "budget_limit_checked",
        "over_budget_request_denied",
        "budget_receipt_present",
    ),
    ReflexFailureClass.PII_REDACTION_FAILURE: (
        "pii_detected_before_response",
        "redaction_receipt_present",
        "raw_pii_not_returned",
    ),
    ReflexFailureClass.PROMPT_INJECTION_FAILURE: (
        "untrusted_instruction_isolated",
        "tool_policy_preserved",
        "injection_receipt_present",
    ),
    ReflexFailureClass.TOOL_SCHEMA_MISMATCH: (
        "input_schema_validated",
        "invalid_tool_payload_denied",
        "schema_error_receipt_present",
    ),
    ReflexFailureClass.PROVIDER_TIMEOUT: (
        "timeout_budget_enforced",
        "fallback_route_attempted",
        "provider_receipt_present",
    ),
    ReflexFailureClass.PROVIDER_COST_SPIKE: (
        "provider_cost_estimated",
        "budget_gate_enforced",
        "cost_receipt_present",
    ),
    ReflexFailureClass.RETRIEVAL_LOW_RELEVANCE: (
        "tenant_index_scoped",
        "minimum_relevance_enforced",
        "retrieval_receipt_present",
    ),
    ReflexFailureClass.MEMORY_BAD_ADMISSION: (
        "closure_certificate_required",
        "memory_admission_review_bound",
        "bad_learning_rejected",
    ),
    ReflexFailureClass.PROOF_MISSING: (
        "effect_observation_present",
        "effect_reconciliation_present",
        "terminal_closure_certificate_present",
    ),
    ReflexFailureClass.VERIFICATION_INCONCLUSIVE: (
        "verification_result_present",
        "inconclusive_result_blocks_closure",
        "review_receipt_present",
    ),
    ReflexFailureClass.DEPLOYMENT_WITNESS_MISSING: (
        "runtime_witness_probe_executed",
        "witness_signature_verified",
        "publication_not_claimed_without_witness",
    ),
    ReflexFailureClass.MODEL_OVERKILL_FOR_LOW_RISK_TASK: (
        "low_risk_route_classified",
        "cheaper_provider_candidate_selected",
        "quality_floor_preserved",
    ),
}


_REPLAYS_BY_SURFACE: Mapping[str, tuple[str, ...]] = {
    "approval": ("approval_deferral", "effect_reconciliation"),
    "budget": ("budget_denial", "effect_reconciliation"),
    "content_safety": ("pii_redaction", "prompt_injection"),
    "deployment_witness": ("deployment_witness_probe", "publication_gate"),
    "memory_admission": ("closure_memory_admission", "learning_review"),
    "policy": ("guard_chain_policy", "denial_receipt"),
    "proof": ("effect_reconciliation", "terminal_closure"),
    "provider_routing": ("provider_quality_floor", "cost_budget"),
    "rbac": ("role_scope_denial", "audit_receipt"),
    "retrieval": ("tenant_retrieval_scope", "relevance_floor"),
    "tenant_isolation": ("tenant_boundary_denial", "audit_receipt"),
    "tool_schema": ("tool_schema_validation", "denial_receipt"),
    "verification": ("verification_closure_block", "review_receipt"),
}


_PROTECTED_SURFACES = frozenset(
    {
        "approval",
        "budget",
        "content_safety",
        "deployment_witness",
        "memory_admission",
        "policy",
        "proof",
        "rbac",
        "tenant_isolation",
        "tool_schema",
        "verification",
    }
)

_REGISTERED_REFLEX_REPLAYS = frozenset(
    replay_id
    for replay_ids in _REPLAYS_BY_SURFACE.values()
    for replay_id in replay_ids
)


def detect_anomalies(snapshot: RuntimeHealthSnapshot) -> tuple[ReflexAnomaly, ...]:
    """Detect configured metric threshold violations in a runtime snapshot."""
    anomalies: list[ReflexAnomaly] = []
    for rule in _ANOMALY_RULES:
        observed_value = _numeric_metric(snapshot.metrics, rule.metric_name)
        if observed_value <= rule.threshold_value:
            continue
        anomalies.append(
            ReflexAnomaly(
                anomaly_id=f"anomaly:{snapshot.snapshot_id}:{rule.metric_name}",
                metric_name=rule.metric_name,
                observed_value=observed_value,
                threshold_value=rule.threshold_value,
                failure_class=rule.failure_class,
                risk=rule.risk,
                evidence_refs=snapshot.evidence_refs,
            )
        )
    return tuple(anomalies)


def diagnose_anomaly(anomaly: ReflexAnomaly, snapshot: RuntimeHealthSnapshot) -> ReflexDiagnosis:
    """Create an evidence-backed diagnosis from a detected anomaly."""
    surface = _SURFACE_BY_FAILURE[anomaly.failure_class]
    evidence_refs = anomaly.evidence_refs or snapshot.evidence_refs
    return ReflexDiagnosis(
        diagnosis_id=f"diagnosis:{anomaly.anomaly_id}",
        surface=surface,
        symptom=(
            f"{anomaly.metric_name} observed {anomaly.observed_value:g} "
            f"above threshold {anomaly.threshold_value:g}"
        ),
        failure_class=anomaly.failure_class,
        risk=anomaly.risk,
        hypothesis=_hypothesis_for_failure(anomaly.failure_class, surface),
        confidence=_confidence_for_failure(anomaly.failure_class),
        evidence_refs=evidence_refs,
        required_tests=_ASSERTIONS_BY_FAILURE[anomaly.failure_class],
        missing_evidence=(),
    )


def generate_eval_cases(diagnosis: ReflexDiagnosis) -> tuple[ReflexEvalCase, ...]:
    """Generate deterministic regression eval cases from a diagnosis."""
    evidence_refs = _require_evidence_refs(diagnosis.evidence_refs)
    return (
        ReflexEvalCase(
            eval_id=f"eval:{diagnosis.diagnosis_id}:primary",
            diagnosis_id=diagnosis.diagnosis_id,
            eval_class=_eval_class_for_failure(diagnosis.failure_class),
            input_payload={
                "surface": diagnosis.surface,
                "failure_class": diagnosis.failure_class.value,
                "risk": diagnosis.risk.value,
            },
            expected={
                "guarded": True,
                "receipt_required": True,
                "world_mutation_allowed": False,
            },
            assertions=diagnosis.required_tests,
            evidence_refs=evidence_refs,
        ),
    )


def propose_upgrade(
    diagnosis: ReflexDiagnosis,
    eval_cases: Iterable[ReflexEvalCase],
) -> ReflexUpgradeCandidate:
    """Propose a bounded upgrade candidate without mutating runtime state."""
    eval_ids = tuple(eval_case.eval_id for eval_case in eval_cases)
    return ReflexUpgradeCandidate(
        candidate_id=f"candidate:{diagnosis.diagnosis_id}",
        diagnosis_id=diagnosis.diagnosis_id,
        change_surface=diagnosis.surface,
        risk=diagnosis.risk,
        description=_proposal_description(diagnosis),
        affected_files=_affected_files_for_surface(diagnosis.surface),
        required_replays=_REPLAYS_BY_SURFACE.get(diagnosis.surface, ("governed_regression",)),
        rollback_plan_ref=f"rollback:{diagnosis.surface}",
        eval_ids=eval_ids,
    )


def candidate_requires_human_approval(candidate: ReflexUpgradeCandidate) -> bool:
    """Return whether a candidate requires human approval before promotion."""
    return candidate.risk in {ReflexRisk.HIGH, ReflexRisk.CRITICAL} or _is_protected_surface(
        candidate.change_surface
    )


def decide_promotion(
    candidate: ReflexUpgradeCandidate,
    sandbox_result: ReflexSandboxResult,
    certificate: ChangeCertificate,
) -> ReflexPromotionDecision:
    """Decide canary admission from sandbox and certificate proof."""
    protected_surface = _is_protected_surface(candidate.change_surface)
    if sandbox_result.candidate_id != candidate.candidate_id:
        return ReflexPromotionDecision(
            decision_id=f"decision:{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            disposition=ReflexPromotionDisposition.REJECTED,
            reason="sandbox result candidate mismatch",
            requires_human_approval=True,
            protected_surface=protected_surface,
        )
    if not sandbox_result.passed:
        return ReflexPromotionDecision(
            decision_id=f"decision:{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            disposition=ReflexPromotionDisposition.REJECTED,
            reason="sandbox result did not pass",
            requires_human_approval=True,
            protected_surface=protected_surface,
        )
    if not _certificate_passed(certificate):
        return ReflexPromotionDecision(
            decision_id=f"decision:{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            disposition=ReflexPromotionDisposition.REJECTED,
            reason="certificate checks did not pass",
            requires_human_approval=True,
            protected_surface=protected_surface,
        )

    if candidate_requires_human_approval(candidate):
        return ReflexPromotionDecision(
            decision_id=f"decision:{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            disposition=ReflexPromotionDisposition.HUMAN_APPROVAL_REQUIRED,
            reason="candidate touches protected or high-risk surface",
            requires_human_approval=True,
            protected_surface=protected_surface,
        )

    return ReflexPromotionDecision(
        decision_id=f"decision:{candidate.candidate_id}",
        candidate_id=candidate.candidate_id,
        disposition=ReflexPromotionDisposition.AUTO_CANARY_ALLOWED,
        reason="sandbox and certificate gates passed for low-risk unprotected candidate",
        requires_human_approval=False,
        protected_surface=False,
    )


def build_canary_handoff(
    candidate: ReflexUpgradeCandidate,
    sandbox_bundle: ReflexSandboxBundle,
    certificate: ChangeCertificate,
) -> ReflexCanaryHandoff:
    """Bind sandbox and certificate proof into a non-mutating canary handoff."""
    decision = decide_promotion(candidate, sandbox_bundle.sandbox_result, certificate)
    return ReflexCanaryHandoff(
        candidate_id=candidate.candidate_id,
        sandbox_bundle=sandbox_bundle,
        certificate=certificate,
        promotion_decision=decision,
        canary_steps=_canary_steps_for_decision(decision),
        rollback_plan_ref=candidate.rollback_plan_ref,
        deployment_witness_required=True,
        mutation_applied=False,
    )


def rank_capability_gaps(
    scores: Iterable[CapabilityMaturityScore],
) -> tuple[CapabilityMaturityScore, ...]:
    """Rank capability scores by largest verified production-closure gap."""
    return tuple(
        sorted(
            scores,
            key=lambda score: (
                score.verdict == "production_closed",
                -score.value_gap,
                score.capability,
            ),
        )
    )


def run_reflex_replay(
    candidate: ReflexUpgradeCandidate,
    replay_id: str,
) -> ReflexReplayResult:
    """Run one deterministic, side-effect-free reflex replay check."""
    replay_name = replay_id.strip()
    if replay_name not in _REGISTERED_REFLEX_REPLAYS:
        return ReflexReplayResult(
            replay_id=replay_name or "undefined_replay",
            passed=False,
            evidence_ref=ReflexEvidenceRef(
                kind="reflex_replay",
                ref_id=f"reflex:replay:{replay_name or 'undefined'}",
            ),
            detail="replay is not registered for reflex sandbox execution",
        )
    if replay_name not in candidate.required_replays:
        return ReflexReplayResult(
            replay_id=replay_name,
            passed=False,
            evidence_ref=ReflexEvidenceRef(
                kind="reflex_replay",
                ref_id=f"reflex:replay:{replay_name}",
            ),
            detail="replay was not declared by candidate",
        )
    return ReflexReplayResult(
        replay_id=replay_name,
        passed=True,
        evidence_ref=ReflexEvidenceRef(
            kind="reflex_replay",
            ref_id=f"reflex:replay:{candidate.candidate_id}:{replay_name}",
        ),
        detail="deterministic reflex replay check passed without live side effects",
    )


def build_sandbox_bundle(
    candidate: ReflexUpgradeCandidate,
    eval_cases: Iterable[ReflexEvalCase],
) -> ReflexSandboxBundle:
    """Build a deterministic sandbox result bundle for a reflex candidate."""
    eval_tuple = tuple(eval_cases)
    eval_ids = tuple(eval_case.eval_id for eval_case in eval_tuple)
    failed_checks = list(_sandbox_eval_failures(candidate, eval_tuple))
    replay_results = tuple(run_reflex_replay(candidate, replay_id) for replay_id in candidate.required_replays)
    failed_checks.extend(
        f"replay_failed:{result.replay_id}:{result.detail}"
        for result in replay_results
        if not result.passed
    )
    report_refs = tuple(result.evidence_ref for result in replay_results) + tuple(
        eval_case.evidence_refs[0] for eval_case in eval_tuple if eval_case.evidence_refs
    )
    sandbox_result = ReflexSandboxResult(
        candidate_id=candidate.candidate_id,
        passed=not failed_checks,
        failed_checks=tuple(failed_checks),
        report_refs=report_refs,
    )
    return ReflexSandboxBundle(
        bundle_id=f"sandbox:{candidate.candidate_id}",
        candidate_id=candidate.candidate_id,
        eval_ids=eval_ids,
        replay_results=replay_results,
        sandbox_result=sandbox_result,
        mutation_applied=False,
    )


def build_reflex_change_command(
    candidate: ReflexUpgradeCandidate,
    *,
    author_id: str,
    branch: str,
    base_commit: str,
    head_commit: str,
    created_at: str,
) -> ChangeCommand:
    """Convert a reflex candidate into a governed evolution ChangeCommand."""
    change_type = _change_type_for_surface(candidate.change_surface)
    change_risk = _change_risk_for_candidate(candidate)
    affected_invariants = _invariants_for_surface(candidate.change_surface)
    metadata = {
        "reflex_candidate_id": candidate.candidate_id,
        "reflex_diagnosis_id": candidate.diagnosis_id,
        "reflex_change_surface": candidate.change_surface,
        "rollback_plan_ref": candidate.rollback_plan_ref,
    }
    return ChangeCommand(
        change_id=f"change:{candidate.candidate_id}",
        author_id=author_id,
        branch=branch,
        base_commit=base_commit,
        head_commit=head_commit,
        change_type=change_type,
        risk=change_risk,
        affected_files=candidate.affected_files,
        affected_contracts=_contracts_for_candidate(candidate),
        affected_capabilities=_capabilities_for_candidate(candidate),
        affected_invariants=affected_invariants,
        required_replays=candidate.required_replays,
        requires_approval=change_risk in {ChangeRisk.HIGH, ChangeRisk.CRITICAL}
        or _is_protected_surface(candidate.change_surface),
        rollback_required=change_risk in {ChangeRisk.HIGH, ChangeRisk.CRITICAL}
        or _is_protected_surface(candidate.change_surface),
        created_at=created_at,
        metadata=metadata,
    )


def build_certification_handoff(
    candidate: ReflexUpgradeCandidate,
    *,
    author_id: str,
    branch: str,
    base_commit: str,
    head_commit: str,
    created_at: str,
    base_ref: str = "HEAD^",
    head_ref: str = "HEAD",
) -> ReflexCertificationHandoff:
    """Build a non-mutating certification handoff for an upgrade candidate."""
    change_command = build_reflex_change_command(
        candidate,
        author_id=author_id,
        branch=branch,
        base_commit=base_commit,
        head_commit=head_commit,
        created_at=created_at,
    )
    command_args = (
        "python",
        "scripts/certify_change.py",
        "--base",
        base_ref,
        "--head",
        head_ref,
        "--strict",
        "--rollback-plan-ref",
        candidate.rollback_plan_ref,
    )
    if change_command.requires_approval:
        command_args = (*command_args, "--approval-id", "reflex-governance")
    return ReflexCertificationHandoff(
        candidate_id=candidate.candidate_id,
        change_command=change_command,
        command_args=command_args,
        required_artifacts=(
            "change_command.json",
            "blast_radius.json",
            "invariant_report.json",
            "replay_report.json",
            "release_certificate.json",
        ),
        mutation_applied=False,
    )


def _numeric_metric(metrics: Mapping[str, object], metric_name: str) -> float:
    value = metrics.get(metric_name, 0.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _sandbox_eval_failures(
    candidate: ReflexUpgradeCandidate,
    eval_cases: tuple[ReflexEvalCase, ...],
) -> tuple[str, ...]:
    failures: list[str] = []
    eval_ids = {eval_case.eval_id for eval_case in eval_cases}
    missing_eval_ids = tuple(eval_id for eval_id in candidate.eval_ids if eval_id not in eval_ids)
    failures.extend(f"missing_eval:{eval_id}" for eval_id in missing_eval_ids)
    if not candidate.required_replays:
        failures.append("missing_required_replay")
    if not candidate.rollback_plan_ref:
        failures.append("missing_rollback_plan_ref")
    for eval_case in eval_cases:
        if not eval_case.assertions:
            failures.append(f"eval_missing_assertions:{eval_case.eval_id}")
        if not eval_case.evidence_refs:
            failures.append(f"eval_missing_evidence:{eval_case.eval_id}")
        if eval_case.eval_id not in candidate.eval_ids:
            failures.append(f"unexpected_eval:{eval_case.eval_id}")
    return tuple(failures)


def _hypothesis_for_failure(failure_class: ReflexFailureClass, surface: str) -> str:
    return (
        f"{failure_class.value} indicates the {surface} gate needs a bounded candidate, "
        "regression evals, sandbox proof, and certificate evidence before promotion."
    )


def _confidence_for_failure(failure_class: ReflexFailureClass) -> float:
    if failure_class in {
        ReflexFailureClass.POLICY_FALSE_ALLOW,
        ReflexFailureClass.APPROVAL_MISSING,
        ReflexFailureClass.RBAC_SCOPE_LEAK,
        ReflexFailureClass.TENANT_BOUNDARY_LEAK,
        ReflexFailureClass.BUDGET_FALSE_ALLOW,
    }:
        return 0.9
    if failure_class is ReflexFailureClass.MODEL_OVERKILL_FOR_LOW_RISK_TASK:
        return 0.75
    return 0.8


def _eval_class_for_failure(failure_class: ReflexFailureClass) -> ReflexEvalClass:
    if failure_class in {
        ReflexFailureClass.POLICY_FALSE_ALLOW,
        ReflexFailureClass.POLICY_FALSE_DENY,
        ReflexFailureClass.APPROVAL_MISSING,
        ReflexFailureClass.RBAC_SCOPE_LEAK,
        ReflexFailureClass.TENANT_BOUNDARY_LEAK,
        ReflexFailureClass.BUDGET_FALSE_ALLOW,
        ReflexFailureClass.MEMORY_BAD_ADMISSION,
        ReflexFailureClass.PROOF_MISSING,
        ReflexFailureClass.DEPLOYMENT_WITNESS_MISSING,
    }:
        return ReflexEvalClass.GOVERNANCE
    if failure_class in {
        ReflexFailureClass.PII_REDACTION_FAILURE,
        ReflexFailureClass.PROMPT_INJECTION_FAILURE,
        ReflexFailureClass.TOOL_SCHEMA_MISMATCH,
    }:
        return ReflexEvalClass.SAFETY
    if failure_class in {
        ReflexFailureClass.PROVIDER_TIMEOUT,
        ReflexFailureClass.PROVIDER_COST_SPIKE,
        ReflexFailureClass.MODEL_OVERKILL_FOR_LOW_RISK_TASK,
    }:
        return ReflexEvalClass.OPERATIONAL
    return ReflexEvalClass.CORRECTNESS


def _proposal_description(diagnosis: ReflexDiagnosis) -> str:
    return (
        f"Propose a governed {diagnosis.surface} improvement for "
        f"{diagnosis.failure_class.value}; no runtime promotion without sandbox "
        "and certificate gates."
    )


def _affected_files_for_surface(surface: str) -> tuple[str, ...]:
    if surface == "provider_routing":
        return ("mcoi/mcoi_runtime/core/provider_cost_routing.py",)
    if surface == "content_safety":
        return ("mcoi/mcoi_runtime/core/pii_scanner.py", "gateway/guards/content_safety.py")
    if surface == "proof":
        return (
            "mcoi/mcoi_runtime/core/effect_assurance.py",
            "mcoi/mcoi_runtime/core/terminal_closure.py",
        )
    if surface == "deployment_witness":
        return ("gateway/conformance.py", "scripts/collect_deployment_witness.py")
    return (f"governance/{surface}",)


def _is_protected_surface(surface: str) -> bool:
    return surface in _PROTECTED_SURFACES


def _certificate_passed(certificate: ChangeCertificate) -> bool:
    return (
        certificate.schema_checks_passed
        and certificate.tests_passed
        and certificate.replay_passed
        and certificate.invariant_checks_passed
        and certificate.migration_safe
        and certificate.rollback_plan_present
        and bool(certificate.evidence_refs)
    )


def _canary_steps_for_decision(decision: ReflexPromotionDecision) -> tuple[str, ...]:
    if decision.disposition is ReflexPromotionDisposition.AUTO_CANARY_ALLOWED:
        return (
            "deploy_canary",
            "watch_health",
            "compare_before_after",
            "rollback_on_regression",
            "publish_deployment_witness",
        )
    if decision.disposition is ReflexPromotionDisposition.HUMAN_APPROVAL_REQUIRED:
        return (
            "open_human_approval_case",
            "attach_certificate",
            "attach_sandbox_bundle",
            "await_approval",
        )
    return (
        "record_rejected_candidate",
        "preserve_eval_regression",
        "block_promotion",
    )


def _change_type_for_surface(surface: str) -> EvolutionChangeType:
    if surface in {"approval", "rbac"}:
        return EvolutionChangeType.AUTHORITY
    if surface in {"policy", "proof", "verification", "content_safety", "memory_admission"}:
        return EvolutionChangeType.POLICY
    if surface == "deployment_witness":
        return EvolutionChangeType.DEPLOYMENT
    if surface == "provider_routing":
        return EvolutionChangeType.CONFIGURATION
    if surface in {"tenant_isolation", "tool_schema"}:
        return EvolutionChangeType.SCHEMA
    return EvolutionChangeType.CODE


def _change_risk_for_candidate(candidate: ReflexUpgradeCandidate) -> ChangeRisk:
    if _is_protected_surface(candidate.change_surface):
        return ChangeRisk.CRITICAL
    return {
        ReflexRisk.LOW: ChangeRisk.LOW,
        ReflexRisk.MEDIUM: ChangeRisk.MEDIUM,
        ReflexRisk.HIGH: ChangeRisk.HIGH,
        ReflexRisk.CRITICAL: ChangeRisk.CRITICAL,
    }[candidate.risk]


def _invariants_for_surface(surface: str) -> tuple[str, ...]:
    invariants = [
        "no_reflex_candidate_enters_runtime_without_change_certificate",
        "no_reflex_candidate_self_certifies_generated_evidence",
    ]
    if _is_protected_surface(surface):
        invariants.append("no_protected_reflex_surface_without_human_approval")
    if surface in {"proof", "verification"}:
        invariants.append("no_audit_proof_verification_or_command_spine_change_without_critical_risk")
    if surface in {"approval", "rbac"}:
        invariants.append("no_approval_rule_change_without_second_approval")
    return tuple(invariants)


def _contracts_for_candidate(candidate: ReflexUpgradeCandidate) -> tuple[str, ...]:
    return tuple(
        affected_file
        for affected_file in candidate.affected_files
        if "/contracts/" in affected_file or affected_file.endswith(".schema.json")
    )


def _capabilities_for_candidate(candidate: ReflexUpgradeCandidate) -> tuple[str, ...]:
    if candidate.change_surface == "provider_routing":
        return ("provider_routing",)
    if candidate.change_surface == "retrieval":
        return ("retrieval",)
    return ()


def _require_evidence_refs(
    evidence_refs: Iterable[ReflexEvidenceRef],
) -> tuple[ReflexEvidenceRef, ...]:
    refs = tuple(evidence_refs)
    if not refs:
        raise ValueError("Reflex eval generation requires at least one evidence reference")
    return refs
