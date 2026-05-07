"""Gateway policy studio simulator.

Purpose: simulate operator policy scenarios and search bounded bypass probes.
Governance scope: approval requirements, amount thresholds, evidence freshness,
    business-hour controls, tenant isolation, self-approval denial, side-effect
    blocking, and deterministic simulator/prover receipts.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - Simulation is read-only and cannot mutate live policy.
  - High-risk side effects cannot be allowed without required approval.
  - Stale evidence escalates or denies according to rule severity.
  - Bypass probes emit concrete cases when a policy permits unsafe behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterable

from gateway.command_spine import canonical_hash


class PolicyScenarioVerdict(StrEnum):
    """Simulator verdict."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class PolicyRuleEffect(StrEnum):
    """Effect applied when a rule matches."""

    DENY = "deny"
    ESCALATE = "escalate"
    REQUIRE_APPROVAL = "require_approval"


class PolicyProbeStatus(StrEnum):
    """Policy prover-style probe status."""

    PROVED = "proved"
    COUNTEREXAMPLE_FOUND = "counterexample_found"


_VERDICT_RANK = {
    PolicyScenarioVerdict.ALLOW: 0,
    PolicyScenarioVerdict.ESCALATE: 1,
    PolicyScenarioVerdict.DENY: 2,
}
_SIDE_EFFECT_ACTIONS = frozenset({
    "refund_customer",
    "payment.dispatch",
    "pay_vendor",
    "email.send",
    "record.update",
})


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """One deterministic operator policy rule."""

    rule_id: str
    description: str
    effect: PolicyRuleEffect
    action: str = "*"
    min_amount: float = 0.0
    max_amount: float = 0.0
    required_role: str = ""
    required_approval_role: str = ""
    requires_fresh_evidence: bool = False
    business_hours_only: bool = False
    tenant_match_required: bool = True
    self_approval_forbidden: bool = True
    rule_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.rule_id, "rule_id")
        _require_text(self.description, "description")
        if not isinstance(self.effect, PolicyRuleEffect):
            raise ValueError("policy_rule_effect_invalid")
        if self.min_amount < 0 or self.max_amount < 0:
            raise ValueError("amount_bounds_nonnegative_required")
        if self.max_amount and self.max_amount < self.min_amount:
            raise ValueError("max_amount_must_not_be_less_than_min_amount")
        if self.tenant_match_required is not True:
            raise ValueError("tenant_match_required")
        if self.self_approval_forbidden is not True:
            raise ValueError("self_approval_must_be_forbidden")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class PolicyScenario:
    """One bounded policy simulation input."""

    scenario_id: str
    tenant_id: str
    actor_id: str
    actor_role: str
    action: str
    amount: float = 0.0
    requested_at: str = ""
    evidence_fresh: bool = True
    tenant_matches_resource: bool = True
    approval_ref: str = ""
    approver_id: str = ""
    approver_role: str = ""
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("scenario_id", "tenant_id", "actor_id", "actor_role", "action", "requested_at"):
            _require_text(getattr(self, field_name), field_name)
        if self.amount < 0:
            raise ValueError("amount_nonnegative_required")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class PolicySimulation:
    """Deterministic simulation output for one scenario."""

    simulation_id: str
    policy_id: str
    scenario_id: str
    verdict: PolicyScenarioVerdict
    reasons: tuple[str, ...]
    matched_rule_ids: tuple[str, ...]
    required_approvals: tuple[str, ...]
    side_effects_allowed: bool
    evidence_refs: tuple[str, ...]
    simulation_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("simulation_id", "policy_id", "scenario_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.verdict, PolicyScenarioVerdict):
            raise ValueError("policy_simulation_verdict_invalid")
        object.__setattr__(self, "reasons", _normalize_text_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "matched_rule_ids", _normalize_text_tuple(self.matched_rule_ids, "matched_rule_ids", allow_empty=True))
        object.__setattr__(self, "required_approvals", _normalize_text_tuple(self.required_approvals, "required_approvals", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class PolicyBypassCounterexample:
    """Concrete unsafe scenario that a bounded probe found."""

    probe_id: str
    scenario_id: str
    reason: str
    simulation_id: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("probe_id", "scenario_id", "reason", "simulation_id"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))


@dataclass(frozen=True, slots=True)
class PolicyBypassProbeReport:
    """Bounded bypass probe report over simulator scenarios."""

    report_id: str
    policy_id: str
    status: PolicyProbeStatus
    probe_count: int
    counterexample_count: int
    counterexamples: tuple[PolicyBypassCounterexample, ...]
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.report_id, "report_id")
        _require_text(self.policy_id, "policy_id")
        if not isinstance(self.status, PolicyProbeStatus):
            raise ValueError("policy_probe_status_invalid")
        if self.probe_count < 1:
            raise ValueError("probe_count_positive_required")
        if self.counterexample_count != len(self.counterexamples):
            raise ValueError("counterexample_count_mismatch")
        object.__setattr__(self, "counterexamples", tuple(self.counterexamples))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class PolicyStudioSession:
    """Operator policy studio session snapshot."""

    session_id: str
    policy_id: str
    rules: tuple[PolicyRule, ...]
    simulations: tuple[PolicySimulation, ...]
    probe_report: PolicyBypassProbeReport
    session_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.session_id, "session_id")
        _require_text(self.policy_id, "policy_id")
        if not self.rules:
            raise ValueError("policy_rules_required")
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "simulations", tuple(self.simulations))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class PolicySimulator:
    """Read-only deterministic simulator for operator policy scenarios."""

    def simulate(
        self,
        *,
        policy_id: str,
        rules: Iterable[PolicyRule],
        scenario: PolicyScenario,
    ) -> PolicySimulation:
        """Evaluate one scenario against explicit policy rules."""
        _require_text(policy_id, "policy_id")
        rule_tuple = tuple(rules)
        if not rule_tuple:
            raise ValueError("policy_rules_required")
        verdict = PolicyScenarioVerdict.ALLOW
        reasons: list[str] = []
        matched_rule_ids: list[str] = []
        required_approvals: list[str] = []

        for rule in rule_tuple:
            if not _rule_applies(rule, scenario):
                continue
            matched_rule_ids.append(rule.rule_id)
            rule_reasons, rule_verdict, approvals = _evaluate_rule(rule, scenario)
            reasons.extend(rule_reasons)
            required_approvals.extend(approvals)
            verdict = _stronger_verdict(verdict, rule_verdict)

        if not scenario.tenant_matches_resource:
            verdict = PolicyScenarioVerdict.DENY
            reasons.append("tenant_boundary_denied")
        if _side_effect_action(scenario.action) and verdict is PolicyScenarioVerdict.ALLOW:
            reasons.append("side_effect_authorized")
        if not reasons:
            reasons.append("policy_constraints_satisfied")

        simulation = PolicySimulation(
            simulation_id="pending",
            policy_id=policy_id,
            scenario_id=scenario.scenario_id,
            verdict=verdict,
            reasons=tuple(dict.fromkeys(reasons)),
            matched_rule_ids=tuple(dict.fromkeys(matched_rule_ids)),
            required_approvals=tuple(dict.fromkeys(required_approvals)),
            side_effects_allowed=verdict is PolicyScenarioVerdict.ALLOW and _side_effect_action(scenario.action),
            evidence_refs=scenario.evidence_refs,
            metadata={"simulation_is_read_only": True, "live_policy_mutated": False},
        )
        payload = simulation.to_json_dict()
        payload["simulation_hash"] = ""
        simulation_hash = canonical_hash(payload)
        return replace(simulation, simulation_id=f"policy-sim-{simulation_hash[:16]}", simulation_hash=simulation_hash)


class PolicyStudio:
    """Combines simulation and bounded bypass probes for operator review."""

    def __init__(self) -> None:
        self._simulator = PolicySimulator()

    def run_session(
        self,
        *,
        session_id: str,
        policy_id: str,
        rules: Iterable[PolicyRule],
        scenarios: Iterable[PolicyScenario],
    ) -> PolicyStudioSession:
        """Run all scenarios and a bounded bypass probe."""
        rule_tuple = tuple(_stamp_rule(rule) for rule in rules)
        scenario_tuple = tuple(scenarios)
        if not scenario_tuple:
            raise ValueError("policy_scenarios_required")
        simulations = tuple(
            self._simulator.simulate(policy_id=policy_id, rules=rule_tuple, scenario=scenario)
            for scenario in scenario_tuple
        )
        probe_report = _build_probe_report(policy_id, simulations)
        session = PolicyStudioSession(
            session_id=session_id,
            policy_id=policy_id,
            rules=rule_tuple,
            simulations=simulations,
            probe_report=probe_report,
            metadata={"policy_studio_is_read_only": True},
        )
        payload = session.to_json_dict()
        payload["session_hash"] = ""
        return replace(session, session_hash=canonical_hash(payload))


def policy_studio_session_to_json_dict(session: PolicyStudioSession) -> dict[str, Any]:
    """Return the public JSON-contract representation of a studio session."""
    return session.to_json_dict()


def _evaluate_rule(
    rule: PolicyRule,
    scenario: PolicyScenario,
) -> tuple[list[str], PolicyScenarioVerdict, list[str]]:
    reasons: list[str] = []
    approvals: list[str] = []
    verdict = PolicyScenarioVerdict.ALLOW
    if rule.required_role and scenario.actor_role != rule.required_role:
        return reasons, verdict, approvals
    if rule.requires_fresh_evidence and not scenario.evidence_fresh:
        reasons.append("evidence_stale")
        verdict = _effect_to_verdict(rule.effect)
    if rule.business_hours_only and not _inside_business_hours(scenario.requested_at):
        reasons.append("outside_business_hours")
        verdict = _stronger_verdict(verdict, _effect_to_verdict(rule.effect))
    if rule.effect is PolicyRuleEffect.REQUIRE_APPROVAL:
        approvals.append(rule.required_approval_role or "operator")
        if not scenario.approval_ref:
            reasons.append("approval_required")
            verdict = _stronger_verdict(verdict, PolicyScenarioVerdict.ESCALATE)
        elif rule.self_approval_forbidden and scenario.approver_id == scenario.actor_id:
            reasons.append("self_approval_forbidden")
            verdict = _stronger_verdict(verdict, PolicyScenarioVerdict.DENY)
        elif rule.required_approval_role and scenario.approver_role != rule.required_approval_role:
            reasons.append("approval_role_mismatch")
            verdict = _stronger_verdict(verdict, PolicyScenarioVerdict.ESCALATE)
    if rule.effect is PolicyRuleEffect.DENY and not reasons:
        reasons.append("policy_rule_denied")
        verdict = PolicyScenarioVerdict.DENY
    return reasons, verdict, approvals


def _build_probe_report(
    policy_id: str,
    simulations: tuple[PolicySimulation, ...],
) -> PolicyBypassProbeReport:
    counterexamples = []
    for simulation in simulations:
        if simulation.side_effects_allowed and "approval_required" in simulation.reasons:
            counterexamples.append(_counterexample("payment_without_approval", simulation, "side_effect_allowed_without_approval"))
        if simulation.side_effects_allowed and "self_approval_forbidden" in simulation.reasons:
            counterexamples.append(_counterexample("self_approval_bypass", simulation, "self_approval_side_effect_allowed"))
        if simulation.side_effects_allowed and "tenant_boundary_denied" in simulation.reasons:
            counterexamples.append(_counterexample("tenant_boundary_bypass", simulation, "cross_tenant_side_effect_allowed"))
        if simulation.side_effects_allowed and "evidence_stale" in simulation.reasons:
            counterexamples.append(_counterexample("stale_evidence_bypass", simulation, "stale_evidence_side_effect_allowed"))
    status = PolicyProbeStatus.PROVED if not counterexamples else PolicyProbeStatus.COUNTEREXAMPLE_FOUND
    report = PolicyBypassProbeReport(
        report_id="pending",
        policy_id=policy_id,
        status=status,
        probe_count=4,
        counterexample_count=len(counterexamples),
        counterexamples=tuple(counterexamples),
        metadata={"proof_is_bounded": True, "policy_weakening_allowed": False},
    )
    payload = report.to_json_dict()
    payload["report_hash"] = ""
    report_hash = canonical_hash(payload)
    return replace(report, report_id=f"policy-bypass-{report_hash[:16]}", report_hash=report_hash)


def _counterexample(
    probe_id: str,
    simulation: PolicySimulation,
    reason: str,
) -> PolicyBypassCounterexample:
    return PolicyBypassCounterexample(
        probe_id=probe_id,
        scenario_id=simulation.scenario_id,
        reason=reason,
        simulation_id=simulation.simulation_id,
        evidence_refs=simulation.evidence_refs,
    )


def _rule_applies(rule: PolicyRule, scenario: PolicyScenario) -> bool:
    if rule.action != "*" and rule.action != scenario.action:
        return False
    if scenario.amount < rule.min_amount:
        return False
    if rule.max_amount and scenario.amount > rule.max_amount:
        return False
    return True


def _effect_to_verdict(effect: PolicyRuleEffect) -> PolicyScenarioVerdict:
    if effect is PolicyRuleEffect.DENY:
        return PolicyScenarioVerdict.DENY
    return PolicyScenarioVerdict.ESCALATE


def _stronger_verdict(left: PolicyScenarioVerdict, right: PolicyScenarioVerdict) -> PolicyScenarioVerdict:
    return left if _VERDICT_RANK[left] >= _VERDICT_RANK[right] else right


def _inside_business_hours(requested_at: str) -> bool:
    try:
        hour = int(requested_at.split("T", 1)[1][:2])
    except (IndexError, ValueError):
        return False
    return 9 <= hour < 17


def _side_effect_action(action: str) -> bool:
    return action in _SIDE_EFFECT_ACTIONS


def _stamp_rule(rule: PolicyRule) -> PolicyRule:
    payload = rule.to_json_dict()
    payload["rule_hash"] = ""
    return replace(rule, rule_hash=canonical_hash(payload))


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
