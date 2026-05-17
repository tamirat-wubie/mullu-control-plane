"""Gateway autonomous capability upgrade loop.

Purpose: diagnose capability weakness and produce governed upgrade proposals
    that must pass evals, sandbox testing, ChangeCommand, ChangeCertificate,
    canary handoff, terminal closure, and learning admission before promotion.
Governance scope: capability health, weakness diagnosis, eval generation,
    sandbox requirements, change-assurance handoff, canary gating, and
    promotion blocking.
Dependencies: dataclasses, hashlib, and JSON serialization.
Invariants:
  - Upgrade plans are proposals and never mutate the capability registry.
  - Policy, payment, audit, proof, and command-spine changes are high risk.
  - High-risk changes require authority approval and second approval for
    approval-rule mutations.
  - Production deployment requires ChangeCertificate and terminal closure.
  - Learning admission is required before successful outcomes enter planning.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Mapping


MATURITY_LEVELS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")
MATURITY_RANK = {level: index for index, level in enumerate(MATURITY_LEVELS)}
RISK_TIERS = ("low", "medium", "high", "critical")
CHANGE_CLASSES = (
    "code",
    "schema",
    "policy",
    "capability",
    "authority_rules",
    "provider_behavior",
    "deployment_profile",
    "configuration",
    "payment",
    "audit",
    "proof",
    "command_spine",
)
CRITICAL_CHANGE_CLASSES = frozenset({"policy", "payment", "audit", "proof", "command_spine", "authority_rules"})


@dataclass(frozen=True, slots=True)
class CapabilityHealthSignal:
    """Observed health signal for one capability."""

    capability_id: str
    observed_at: str
    maturity_level: str
    success_rate: float
    failure_count: int
    mean_latency_ms: int
    cost_per_success: float
    open_incidents: int
    blocker_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.capability_id, "capability_id")
        _require_text(self.observed_at, "observed_at")
        if self.maturity_level not in MATURITY_LEVELS:
            raise ValueError("maturity_level_invalid")
        if not 0 <= self.success_rate <= 1:
            raise ValueError("success_rate_between_zero_and_one")
        if self.failure_count < 0:
            raise ValueError("failure_count_non_negative")
        if self.mean_latency_ms < 0:
            raise ValueError("mean_latency_non_negative")
        if self.cost_per_success < 0:
            raise ValueError("cost_per_success_non_negative")
        if self.open_incidents < 0:
            raise ValueError("open_incidents_non_negative")
        object.__setattr__(self, "blocker_codes", _normalize_text_tuple(self.blocker_codes, "blocker_codes", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class CapabilityWeaknessDiagnosis:
    """Derived weakness for one capability health signal."""

    diagnosis_id: str
    capability_id: str
    weakness_codes: tuple[str, ...]
    severity: str
    recommended_change_classes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    diagnosis_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.diagnosis_id, "diagnosis_id")
        _require_text(self.capability_id, "capability_id")
        if self.severity not in RISK_TIERS:
            raise ValueError("diagnosis_severity_invalid")
        object.__setattr__(self, "weakness_codes", _normalize_text_tuple(self.weakness_codes, "weakness_codes"))
        object.__setattr__(self, "recommended_change_classes", _normalize_text_tuple(self.recommended_change_classes, "recommended_change_classes"))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class UpgradeEvalRequirement:
    """Eval required for an upgrade candidate."""

    eval_id: str
    eval_type: str
    fixture_ref: str
    required: bool = True

    def __post_init__(self) -> None:
        _require_text(self.eval_id, "eval_id")
        _require_text(self.eval_type, "eval_type")
        _require_text(self.fixture_ref, "fixture_ref")


@dataclass(frozen=True, slots=True)
class UpgradeCandidate:
    """Non-mutating upgrade candidate."""

    candidate_id: str
    capability_id: str
    target_maturity_level: str
    change_classes: tuple[str, ...]
    risk_tier: str
    evals: tuple[UpgradeEvalRequirement, ...]
    sandbox_tests: tuple[str, ...]
    rollback_plan_ref: str
    change_command_ref: str
    change_certificate_ref: str
    canary_handoff_ref: str
    terminal_closure_ref: str
    learning_admission_ref: str
    authority_approval_required: bool
    second_approval_required: bool
    promotion_blocked: bool
    candidate_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.capability_id, "capability_id")
        if self.target_maturity_level not in MATURITY_LEVELS:
            raise ValueError("target_maturity_level_invalid")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        object.__setattr__(self, "change_classes", _normalize_text_tuple(self.change_classes, "change_classes"))
        object.__setattr__(self, "evals", tuple(self.evals))
        object.__setattr__(self, "sandbox_tests", _normalize_text_tuple(self.sandbox_tests, "sandbox_tests"))
        for field_name in (
            "rollback_plan_ref",
            "change_command_ref",
            "change_certificate_ref",
            "canary_handoff_ref",
            "terminal_closure_ref",
            "learning_admission_ref",
        ):
            _require_text(str(getattr(self, field_name)), field_name)
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.promotion_blocked:
            raise ValueError("upgrade_candidate_promotion_must_be_blocked")
        if self.risk_tier in {"high", "critical"} and not self.authority_approval_required:
            raise ValueError("high_risk_upgrade_requires_authority_approval")


@dataclass(frozen=True, slots=True)
class CapabilityUpgradePlan:
    """Full autonomous upgrade proposal plan."""

    plan_id: str
    capability_id: str
    health_signal: CapabilityHealthSignal
    diagnosis: CapabilityWeaknessDiagnosis
    candidate: UpgradeCandidate
    required_stages: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    operator_review_required: bool
    activation_blocked: bool
    plan_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.plan_id, "plan_id")
        _require_text(self.capability_id, "capability_id")
        object.__setattr__(self, "required_stages", _normalize_text_tuple(self.required_stages, "required_stages"))
        object.__setattr__(self, "blocked_reasons", _normalize_text_tuple(self.blocked_reasons, "blocked_reasons"))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not self.operator_review_required:
            raise ValueError("operator_review_required")
        if not self.activation_blocked:
            raise ValueError("activation_must_be_blocked")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-schema compatible projection."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CapabilityImprovementPortfolio:
    """Whole-mesh set of non-mutating capability improvement proposals."""

    portfolio_id: str
    generated_at: str
    plans: tuple[CapabilityUpgradePlan, ...]
    prioritized_capability_ids: tuple[str, ...]
    systemic_weakness_codes: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    operator_review_required: bool
    activation_blocked: bool
    portfolio_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.portfolio_id, "portfolio_id")
        _require_text(self.generated_at, "generated_at")
        plans = tuple(self.plans)
        if not plans:
            raise ValueError("portfolio_plans_required")
        object.__setattr__(self, "plans", plans)
        object.__setattr__(self, "prioritized_capability_ids", _normalize_text_tuple(self.prioritized_capability_ids, "prioritized_capability_ids"))
        object.__setattr__(self, "systemic_weakness_codes", _normalize_text_tuple(self.systemic_weakness_codes, "systemic_weakness_codes", allow_empty=True))
        object.__setattr__(self, "blocked_reasons", _normalize_text_tuple(self.blocked_reasons, "blocked_reasons"))
        object.__setattr__(self, "metadata", dict(self.metadata))
        _require_unique_tuple(self.prioritized_capability_ids, "portfolio_priority")
        _require_unique_tuple(self.systemic_weakness_codes, "portfolio_systemic_weakness_codes")
        _require_unique_tuple(self.blocked_reasons, "portfolio_blocked_reasons")
        _require_unique_tuple(tuple(plan.capability_id for plan in plans), "portfolio_plan_capabilities")
        plan_capability_ids = {plan.capability_id for plan in plans}
        if set(self.prioritized_capability_ids) != plan_capability_ids:
            raise ValueError("portfolio_priority_must_cover_plans")
        if any(not plan.activation_blocked or not plan.candidate.promotion_blocked for plan in plans):
            raise ValueError("portfolio_plans_must_remain_blocked")
        if not self.operator_review_required:
            raise ValueError("portfolio_operator_review_required")
        if not self.activation_blocked:
            raise ValueError("portfolio_activation_must_be_blocked")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-schema compatible projection."""
        return _json_ready(asdict(self))


class AutonomousCapabilityUpgradeLoop:
    """Diagnose capability health and emit governed upgrade proposals."""

    def propose(
        self,
        signal: CapabilityHealthSignal,
        *,
        desired_maturity_level: str = "C6",
        requested_change_classes: Iterable[str] = ("capability", "configuration"),
    ) -> CapabilityUpgradePlan:
        """Return a non-mutating upgrade plan for one capability."""
        if desired_maturity_level not in MATURITY_LEVELS:
            raise ValueError("desired_maturity_level_invalid")
        change_classes = _normalize_change_classes(tuple(requested_change_classes))
        diagnosis = _diagnose(signal, change_classes)
        target = _target_maturity(signal.maturity_level, desired_maturity_level)
        candidate = _candidate_from_diagnosis(
            diagnosis,
            target_maturity_level=target,
            change_classes=change_classes,
        )
        blocked_reasons = _blocked_reasons(candidate)
        plan = CapabilityUpgradePlan(
            plan_id=f"capability-upgrade-plan-{_hash_payload({'capability_id': signal.capability_id, 'diagnosis_id': diagnosis.diagnosis_id})[:16]}",
            capability_id=signal.capability_id,
            health_signal=signal,
            diagnosis=diagnosis,
            candidate=candidate,
            required_stages=(
                "capability_health",
                "weakness_diagnosis",
                "eval_generation",
                "upgrade_candidate",
                "sandbox_test",
                "change_command",
                "change_certificate",
                "canary",
                "terminal_closure",
                "learning_admission",
            ),
            blocked_reasons=blocked_reasons,
            operator_review_required=True,
            activation_blocked=True,
            metadata={
                "plan_is_not_execution": True,
                "autonomous_proposal_allowed": True,
                "autonomous_direct_deploy_allowed": False,
            },
        )
        return _stamp_plan(plan)

    def propose_portfolio(
        self,
        signals: Iterable[CapabilityHealthSignal],
        *,
        generated_at: str,
        desired_maturity_level: str = "C6",
        requested_change_classes: Iterable[str] = ("capability", "configuration"),
        requested_change_classes_by_capability: Mapping[str, Iterable[str]] | None = None,
        max_candidates: int | None = None,
    ) -> CapabilityImprovementPortfolio:
        """Return a ranked, activation-blocked improvement portfolio."""
        _require_text(generated_at, "generated_at")
        if max_candidates is not None and max_candidates < 1:
            raise ValueError("max_candidates_positive")
        normalized_signals = tuple(signals)
        if not normalized_signals:
            raise ValueError("portfolio_signals_required")
        capability_ids = [signal.capability_id for signal in normalized_signals]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("duplicate_capability_signal")

        class_overrides = requested_change_classes_by_capability or {}
        plans = tuple(
            self.propose(
                signal,
                desired_maturity_level=desired_maturity_level,
                requested_change_classes=tuple(class_overrides.get(signal.capability_id, requested_change_classes)),
            )
            for signal in normalized_signals
        )
        ranked_plans = tuple(sorted(plans, key=_plan_priority_key))
        if max_candidates is not None:
            ranked_plans = ranked_plans[:max_candidates]
        prioritized_capability_ids = tuple(plan.capability_id for plan in ranked_plans)
        portfolio = CapabilityImprovementPortfolio(
            portfolio_id="pending",
            generated_at=generated_at,
            plans=ranked_plans,
            prioritized_capability_ids=prioritized_capability_ids,
            systemic_weakness_codes=_systemic_weakness_codes(ranked_plans),
            blocked_reasons=_portfolio_blocked_reasons(ranked_plans),
            operator_review_required=True,
            activation_blocked=True,
            metadata={
                "portfolio_is_not_execution": True,
                "autonomous_proposal_allowed": True,
                "autonomous_direct_deploy_allowed": False,
                "direct_registry_mutation_allowed": False,
                "systemic_detection": "repeated_weakness_codes",
                "selected_candidate_count": len(ranked_plans),
                "observed_signal_count": len(normalized_signals),
                "severity_counts": _severity_counts(ranked_plans),
                "evidence_ref_count": len({ref for plan in ranked_plans for ref in plan.health_signal.evidence_refs}),
            },
        )
        return _stamp_portfolio(portfolio)


def _diagnose(
    signal: CapabilityHealthSignal,
    change_classes: tuple[str, ...],
) -> CapabilityWeaknessDiagnosis:
    weakness_codes = list(signal.blocker_codes)
    if MATURITY_RANK[signal.maturity_level] < MATURITY_RANK["C4"]:
        weakness_codes.append("maturity_below_live_read")
    if signal.success_rate < 0.98:
        weakness_codes.append("success_rate_below_threshold")
    if signal.failure_count > 0:
        weakness_codes.append("failures_observed")
    if signal.mean_latency_ms > 5000:
        weakness_codes.append("latency_above_threshold")
    if signal.cost_per_success > 1.0:
        weakness_codes.append("cost_above_threshold")
    if signal.open_incidents > 0:
        weakness_codes.append("open_incidents_present")
    if not weakness_codes:
        weakness_codes.append("preventive_upgrade_review")
    severity = _severity(signal, change_classes, tuple(weakness_codes))
    diagnosis = CapabilityWeaknessDiagnosis(
        diagnosis_id="pending",
        capability_id=signal.capability_id,
        weakness_codes=tuple(dict.fromkeys(weakness_codes)),
        severity=severity,
        recommended_change_classes=change_classes,
        evidence_refs=signal.evidence_refs,
        metadata={
            "observed_maturity_level": signal.maturity_level,
            "health_observed_at": signal.observed_at,
        },
    )
    return _stamp_diagnosis(diagnosis)


def _severity(
    signal: CapabilityHealthSignal,
    change_classes: tuple[str, ...],
    weakness_codes: tuple[str, ...],
) -> str:
    if set(change_classes).intersection(CRITICAL_CHANGE_CLASSES):
        return "critical"
    if signal.open_incidents > 0 or signal.success_rate < 0.9:
        return "high"
    if signal.failure_count > 0 or len(weakness_codes) >= 3:
        return "medium"
    return "low"


def _candidate_from_diagnosis(
    diagnosis: CapabilityWeaknessDiagnosis,
    *,
    target_maturity_level: str,
    change_classes: tuple[str, ...],
) -> UpgradeCandidate:
    candidate_seed = {
        "capability_id": diagnosis.capability_id,
        "diagnosis_hash": diagnosis.diagnosis_hash,
        "target_maturity_level": target_maturity_level,
        "change_classes": change_classes,
    }
    seed_hash = _hash_payload(candidate_seed)[:16]
    high_risk = diagnosis.severity in {"high", "critical"}
    second_approval = bool({"policy", "authority_rules"}.intersection(change_classes))
    candidate = UpgradeCandidate(
        candidate_id=f"capability-upgrade-candidate-{seed_hash}",
        capability_id=diagnosis.capability_id,
        target_maturity_level=target_maturity_level,
        change_classes=change_classes,
        risk_tier=diagnosis.severity,
        evals=_evals_for(diagnosis, change_classes),
        sandbox_tests=(
            f"sandbox:{diagnosis.capability_id}:baseline-replay",
            f"sandbox:{diagnosis.capability_id}:provider-failure",
            f"sandbox:{diagnosis.capability_id}:rollback-path",
        ),
        rollback_plan_ref=f"rollback:{diagnosis.capability_id}:{seed_hash}",
        change_command_ref=f"change-command:{diagnosis.capability_id}:{seed_hash}",
        change_certificate_ref=f"change-certificate:{diagnosis.capability_id}:{seed_hash}",
        canary_handoff_ref=f"canary-handoff:{diagnosis.capability_id}:{seed_hash}",
        terminal_closure_ref=f"terminal-closure:{diagnosis.capability_id}:{seed_hash}",
        learning_admission_ref=f"learning-admission:{diagnosis.capability_id}:{seed_hash}",
        authority_approval_required=high_risk,
        second_approval_required=second_approval,
        promotion_blocked=True,
        metadata={
            "diagnosis_id": diagnosis.diagnosis_id,
            "change_command_required": True,
            "change_certificate_required": True,
            "canary_required": True,
            "terminal_closure_required": True,
            "learning_admission_required": True,
        },
    )
    return _stamp_candidate(candidate)


def _evals_for(
    diagnosis: CapabilityWeaknessDiagnosis,
    change_classes: tuple[str, ...],
) -> tuple[UpgradeEvalRequirement, ...]:
    eval_types = {
        "regression",
        "replay_determinism",
        "tenant_boundary",
        "no_secret_leak",
        "provider_failure",
    }
    if diagnosis.severity in {"medium", "high", "critical"}:
        eval_types.update({"prompt_injection", "approval_required"})
    if set(change_classes).intersection({"payment", "budget", "provider_behavior"}):
        eval_types.add("budget_exhaustion")
    if set(change_classes).intersection({"policy", "authority_rules"}):
        eval_types.update({"policy_bypass", "second_approval"})
    if set(change_classes).intersection({"audit", "proof", "command_spine"}):
        eval_types.update({"audit_integrity", "proof_integrity", "terminal_closure"})
    return tuple(
        UpgradeEvalRequirement(
            eval_id=f"upgrade-eval-{_safe_id(eval_type)}",
            eval_type=eval_type,
            fixture_ref=f"fixtures/{diagnosis.capability_id}/upgrade/{eval_type}.json",
        )
        for eval_type in sorted(eval_types)
    )


def _target_maturity(current: str, desired: str) -> str:
    if MATURITY_RANK[desired] <= MATURITY_RANK[current]:
        next_rank = min(MATURITY_RANK[current] + 1, MATURITY_RANK["C7"])
        return MATURITY_LEVELS[next_rank]
    return desired


def _blocked_reasons(candidate: UpgradeCandidate) -> tuple[str, ...]:
    reasons = [
        "change_command_not_certified",
        "change_certificate_not_issued",
        "sandbox_tests_not_passed",
        "canary_not_completed",
        "terminal_closure_missing",
        "learning_admission_missing",
    ]
    if candidate.authority_approval_required:
        reasons.append("authority_approval_required")
    if candidate.second_approval_required:
        reasons.append("second_approval_required")
    return tuple(reasons)


def _plan_priority_key(plan: CapabilityUpgradePlan) -> tuple[object, ...]:
    signal = plan.health_signal
    maturity_gap = MATURITY_RANK[plan.candidate.target_maturity_level] - MATURITY_RANK[signal.maturity_level]
    latency_overage = max(0, signal.mean_latency_ms - 5000)
    cost_overage = max(0.0, signal.cost_per_success - 1.0)
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return (
        severity_rank[plan.diagnosis.severity],
        -signal.open_incidents,
        -signal.failure_count,
        -maturity_gap,
        signal.success_rate,
        -latency_overage,
        -cost_overage,
        plan.capability_id,
    )


def _systemic_weakness_codes(plans: tuple[CapabilityUpgradePlan, ...]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for plan in plans:
        for weakness_code in plan.diagnosis.weakness_codes:
            counts[weakness_code] = counts.get(weakness_code, 0) + 1
    return tuple(
        weakness_code
        for weakness_code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count > 1
    )


def _portfolio_blocked_reasons(plans: tuple[CapabilityUpgradePlan, ...]) -> tuple[str, ...]:
    return _ordered_unique(
        (
            "portfolio_activation_blocked",
            "portfolio_operator_review_required",
            *(reason for plan in plans for reason in plan.blocked_reasons),
        )
    )


def _severity_counts(plans: tuple[CapabilityUpgradePlan, ...]) -> dict[str, int]:
    counts = {tier: 0 for tier in RISK_TIERS}
    for plan in plans:
        counts[plan.diagnosis.severity] += 1
    return counts


def _normalize_change_classes(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = _normalize_text_tuple(values, "change_classes")
    for value in normalized:
        if value not in CHANGE_CLASSES:
            raise ValueError("change_class_invalid")
    return tuple(dict.fromkeys(normalized))


def _stamp_diagnosis(diagnosis: CapabilityWeaknessDiagnosis) -> CapabilityWeaknessDiagnosis:
    payload = asdict(replace(diagnosis, diagnosis_id="pending", diagnosis_hash=""))
    diagnosis_hash = _hash_payload(payload)
    return replace(diagnosis, diagnosis_id=f"capability-diagnosis-{diagnosis_hash[:16]}", diagnosis_hash=diagnosis_hash)


def _stamp_candidate(candidate: UpgradeCandidate) -> UpgradeCandidate:
    payload = asdict(replace(candidate, candidate_hash=""))
    return replace(candidate, candidate_hash=_hash_payload(payload))


def _stamp_plan(plan: CapabilityUpgradePlan) -> CapabilityUpgradePlan:
    payload = asdict(replace(plan, plan_hash=""))
    return replace(plan, plan_hash=_hash_payload(payload))


def _stamp_portfolio(portfolio: CapabilityImprovementPortfolio) -> CapabilityImprovementPortfolio:
    payload = asdict(replace(portfolio, portfolio_id="pending", portfolio_hash=""))
    portfolio_hash = _hash_payload(payload)
    return replace(
        portfolio,
        portfolio_id=f"capability-improvement-portfolio-{portfolio_hash[:16]}",
        portfolio_hash=portfolio_hash,
    )


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_required")
    return value.strip()


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple | list):
        raise ValueError(f"{field_name}_must_be_array")
    normalized = tuple(str(value).strip() for value in values)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name}_required")
    if any(not value for value in normalized):
        raise ValueError(f"{field_name}_item_required")
    return normalized


def _require_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name}_must_be_unique")


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-").lower()


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value
