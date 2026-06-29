"""Purpose: causal preview and dry-run engine for proposed action consequences.
Governance scope: sandbox-only action simulation, dependency coverage,
    branch risk, rollback evidence, and false-success prevention.
Dependencies: Python standard library and runtime invariant helpers only.
Invariants:
  - Preview mutates only cloned simulated state, never the supplied real state.
  - A preview receipt never certifies real execution success.
  - Unknowns reduce confidence and can block high-impact execution advice.
  - High-impact actions require fresh state, approval evidence, and recovery evidence.
  - Verdicts are derived from explicit branches, risks, constraints, and guards.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
import json
import math
from typing import Any, Callable, Mapping

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


StateTransform = Callable[[dict[str, Any]], dict[str, Any]]
ConstraintCheck = Callable[[dict[str, Any]], bool]


class CausalPreviewError(RuntimeCoreInvariantError):
    """Raised when a preview contract violates a hard invariant."""


class PreviewVerdict(StrEnum):
    """Recommendation emitted by a dry-run receipt."""

    APPROVE = "approve"
    APPROVE_WITH_GUARDS = "approve_with_guards"
    APPROVE_ONLY_IN_SANDBOX = "approve_only_in_sandbox"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    REQUIRE_MORE_EVIDENCE = "require_more_evidence"
    MODIFY_ACTION = "modify_action"
    BLOCK = "block"
    SIMULATION_INCONCLUSIVE = "simulation_inconclusive"


class ActionClass(StrEnum):
    """Universal action class used by the preview model."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SEND = "send"
    DEPLOY = "deploy"
    MERGE = "merge"
    TRANSFER = "transfer"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"
    NOTIFY = "notify"
    SCHEDULE = "schedule"
    CANCEL = "cancel"
    MOVE = "move"
    RENAME = "rename"
    TRANSFORM = "transform"
    ESCALATE = "escalate"
    ROLLBACK = "rollback"


class SideEffectClass(StrEnum):
    """Side-effect boundary that controls preview strictness."""

    NONE = "none"
    LOCAL_ONLY = "local_only"
    INTERNAL_SYSTEM = "internal_system"
    EXTERNAL_SYSTEM = "external_system"
    FINANCIAL = "financial"
    LEGAL_PUBLIC = "legal_public"
    USER_FACING = "user_facing"
    IRREVERSIBLE = "irreversible"
    SAFETY_CRITICAL = "safety_critical"


class CompensationVerificationStatus(StrEnum):
    """Evidence level for rollback or compensation plans."""

    VERIFIED = "verified"
    PLAUSIBLE = "plausible"
    UNTESTED = "untested"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    DANGEROUS = "dangerous"


class ConstraintCheckStatus(StrEnum):
    """Result of one branch-level invariant check."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class TruthLevel(StrEnum):
    """Truth level of a preview receipt."""

    INTENDED_ACTION = "intended_action"
    SIMULATED_CONSEQUENCE = "simulated_consequence"
    EXECUTED_CONSEQUENCE = "executed_consequence"
    VERIFIED_REAL_OUTCOME = "verified_real_outcome"


_HIGH_IMPACT_SIDE_EFFECTS = frozenset(
    {
        SideEffectClass.EXTERNAL_SYSTEM,
        SideEffectClass.FINANCIAL,
        SideEffectClass.LEGAL_PUBLIC,
        SideEffectClass.USER_FACING,
        SideEffectClass.IRREVERSIBLE,
        SideEffectClass.SAFETY_CRITICAL,
    }
)

_MUTATING_SIDE_EFFECTS = frozenset(
    {
        SideEffectClass.LOCAL_ONLY,
        SideEffectClass.INTERNAL_SYSTEM,
        SideEffectClass.EXTERNAL_SYSTEM,
        SideEffectClass.FINANCIAL,
        SideEffectClass.LEGAL_PUBLIC,
        SideEffectClass.USER_FACING,
        SideEffectClass.IRREVERSIBLE,
        SideEffectClass.SAFETY_CRITICAL,
    }
)

_DEFAULT_BRANCH_IDS = (
    "expected",
    "best_case",
    "known_failure",
    "partial_failure",
    "adversarial",
    "rollback",
    "unknown_dependency",
    "stale_state",
)


@dataclass(frozen=True, slots=True)
class SymbolicPreviewState:
    """Immutable source state for one preview episode."""

    identity: Mapping[str, Any]
    constraints: Mapping[str, Any]
    mutable_state: Mapping[str, Any]
    exposure: Mapping[str, Any]
    history: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("identity", "constraints", "mutable_state", "exposure"):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise CausalPreviewError(f"{field_name} must be a mapping")
        if isinstance(self.history, (str, bytes)) or not isinstance(self.history, tuple):
            object.__setattr__(self, "history", tuple(self.history))


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Frozen state evidence used as the simulation starting point."""

    snapshot_id: str
    state_hash: str
    captured_at: str
    freshness_score: float
    completeness_score: float
    source_confidence: float
    state: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("snapshot_id", "state_hash", "captured_at"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        for field_name in (
            "freshness_score",
            "completeness_score",
            "source_confidence",
        ):
            object.__setattr__(
                self,
                field_name,
                _unit_float(getattr(self, field_name), field_name),
            )
        if not isinstance(self.state, Mapping):
            raise CausalPreviewError("state must be a mapping")


@dataclass(frozen=True, slots=True)
class CausalPreviewAction:
    """Action proposal admitted into sandbox-only consequence preview."""

    action_id: str
    action_class: ActionClass
    actor_id: str
    target_ref: str
    goal: str
    side_effect_class: SideEffectClass = SideEffectClass.NONE
    parameters: Mapping[str, Any] = field(default_factory=dict)
    known_dependencies: tuple[str, ...] = ()
    suspected_dependencies: tuple[str, ...] = ()
    approval_refs: tuple[str, ...] = ()
    rollback_evidence_refs: tuple[str, ...] = ()
    compensation_evidence_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    required_branch_ids: tuple[str, ...] = _DEFAULT_BRANCH_IDS

    def __post_init__(self) -> None:
        for field_name in ("action_id", "actor_id", "target_ref", "goal"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "action_class", ActionClass(self.action_class))
        object.__setattr__(
            self,
            "side_effect_class",
            SideEffectClass(self.side_effect_class),
        )
        if not isinstance(self.parameters, Mapping):
            raise CausalPreviewError("parameters must be a mapping")
        for field_name in (
            "known_dependencies",
            "suspected_dependencies",
            "approval_refs",
            "rollback_evidence_refs",
            "compensation_evidence_refs",
            "assumptions",
            "required_branch_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _text_tuple(getattr(self, field_name), field_name, allow_empty=True),
            )

    @property
    def high_impact(self) -> bool:
        """Return whether the action crosses a strict side-effect boundary."""

        return self.side_effect_class in _HIGH_IMPACT_SIDE_EFFECTS

    @property
    def mutating(self) -> bool:
        """Return whether execution would alter state outside a pure read."""

        return self.side_effect_class in _MUTATING_SIDE_EFFECTS


@dataclass(frozen=True, slots=True)
class CausalNode:
    """Node in the dry-run causal graph."""

    node_id: str
    node_type: str
    description: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        for field_name in ("node_id", "node_type", "description"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "confidence", _unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class CausalEdge:
    """Directed relationship in the dry-run causal graph."""

    source: str
    target: str
    relation: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        for field_name in ("source", "target", "relation"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "confidence", _unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class CausalGraph:
    """Preview graph binding action, target, dependencies, risks, and evidence."""

    nodes: tuple[CausalNode, ...]
    edges: tuple[CausalEdge, ...]

    @property
    def graph_hash(self) -> str:
        """Return a deterministic graph identifier."""

        return stable_identifier(
            "causal-preview-graph",
            {
                "nodes": tuple(
                    {
                        "node_id": node.node_id,
                        "node_type": node.node_type,
                        "description": node.description,
                        "confidence": node.confidence,
                    }
                    for node in self.nodes
                ),
                "edges": tuple(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "confidence": edge.confidence,
                    }
                    for edge in self.edges
                ),
            },
        )


@dataclass(slots=True)
class CausalBranch:
    """One possible future branch simulated by the preview engine."""

    branch_id: str
    name: str
    likelihood: float
    simulated_changes: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    constraint_checks: list["ConstraintCheckResult"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ConstraintCheckResult:
    """One invariant check observed within a branch."""

    check_id: str
    branch_id: str
    status: ConstraintCheckStatus
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("check_id", "branch_id", "reason"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "status",
            ConstraintCheckStatus(self.status),
        )


@dataclass(frozen=True, slots=True)
class RiskScore:
    """Multidimensional preview risk score."""

    risk_type: str
    severity: float
    likelihood: float
    exposure: float
    irreversibility: float
    uncertainty: float
    cascade_potential: float
    mitigation_strength: float
    description: str

    def __post_init__(self) -> None:
        for field_name in ("risk_type", "description"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        for field_name in (
            "severity",
            "likelihood",
            "exposure",
            "irreversibility",
            "uncertainty",
            "cascade_potential",
            "mitigation_strength",
        ):
            object.__setattr__(
                self,
                field_name,
                _unit_float(getattr(self, field_name), field_name),
            )

    def total(self) -> float:
        """Compute bounded risk using mitigation as the denominator."""

        denominator = max(self.mitigation_strength, 0.1)
        return min(
            1.0,
            (
                self.severity
                * self.likelihood
                * self.exposure
                * self.irreversibility
                * self.uncertainty
                * self.cascade_potential
            )
            / denominator,
        )


@dataclass(frozen=True, slots=True)
class CompensationPlan:
    """Rollback or forward-repair plan projected by the preview."""

    plan_id: str
    name: str
    steps: tuple[str, ...]
    verification_status: CompensationVerificationStatus
    evidence_refs: tuple[str, ...]
    limitations: tuple[str, ...]
    recovery_confidence: float

    def __post_init__(self) -> None:
        for field_name in ("plan_id", "name"):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "steps", _text_tuple(self.steps, "steps"))
        object.__setattr__(
            self,
            "verification_status",
            CompensationVerificationStatus(self.verification_status),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True),
        )
        object.__setattr__(
            self,
            "limitations",
            _text_tuple(self.limitations, "limitations", allow_empty=True),
        )
        object.__setattr__(
            self,
            "recovery_confidence",
            _unit_float(self.recovery_confidence, "recovery_confidence"),
        )


@dataclass(frozen=True, slots=True)
class CausalPreviewReceipt:
    """Auditable result of one causal preview run."""

    receipt_id: str
    engine_version: str
    action_id: str
    truth_level: TruthLevel
    state_snapshot_hash: str
    snapshot_freshness: float
    simulation_boundary: str
    permissions_checked: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    causal_graph_hash: str
    causal_graph_summary: Mapping[str, Any]
    branch_summary: tuple[Mapping[str, Any], ...]
    predicted_direct_effects: tuple[str, ...]
    predicted_indirect_effects: tuple[str, ...]
    predicted_delayed_effects: tuple[str, ...]
    constraint_checks: tuple[ConstraintCheckResult, ...]
    violations: tuple[str, ...]
    risks: tuple[RiskScore, ...]
    compensation_plans: tuple[CompensationPlan, ...]
    branch_coverage_score: float
    confidence_score: float
    verdict: PreviewVerdict
    required_guards: tuple[str, ...]
    post_execution_verification_plan: tuple[str, ...]
    limitations: tuple[str, ...]
    success_certified: bool = False
    state_hash_after_preview: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "engine_version",
            "action_id",
            "state_snapshot_hash",
            "simulation_boundary",
            "causal_graph_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, getattr(self, field_name)),
            )
        object.__setattr__(self, "truth_level", TruthLevel(self.truth_level))
        object.__setattr__(self, "verdict", PreviewVerdict(self.verdict))
        object.__setattr__(
            self,
            "snapshot_freshness",
            _unit_float(self.snapshot_freshness, "snapshot_freshness"),
        )
        object.__setattr__(
            self,
            "branch_coverage_score",
            _unit_float(self.branch_coverage_score, "branch_coverage_score"),
        )
        object.__setattr__(
            self,
            "confidence_score",
            _unit_float(self.confidence_score, "confidence_score"),
        )
        if self.success_certified is not False:
            raise CausalPreviewError("preview receipt cannot certify real success")


class UniversalCausalPreviewDryRunEngine:
    """Preview proposed actions without granting execution authority."""

    ENGINE_VERSION = "causal-preview.v1"

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        constraint_checks: Mapping[str, ConstraintCheck] | None = None,
    ) -> None:
        self._clock = clock
        self._constraint_checks = dict(constraint_checks or {})

    def run(
        self,
        *,
        real_state: SymbolicPreviewState,
        action: CausalPreviewAction,
        snapshot: StateSnapshot | None = None,
        effect_model: StateTransform | None = None,
    ) -> CausalPreviewReceipt:
        """Simulate a proposed action and return an evidence-bounded receipt."""

        admission_violations = self._admit(action)
        source_snapshot = snapshot or self._snapshot(real_state)
        if admission_violations:
            return self._receipt(
                action=action,
                snapshot=source_snapshot,
                graph=CausalGraph(nodes=(), edges=()),
                branches=(),
                risks=(),
                compensations=(),
                unknowns=tuple(admission_violations),
                assumptions=action.assumptions,
                required_guards=("Clarify or bound the proposed action.",),
                verdict=PreviewVerdict.BLOCK,
                limitations=("No simulation was trusted because admission failed.",),
                real_state=real_state,
            )

        if action.high_impact and source_snapshot.freshness_score < 0.95:
            return self._receipt(
                action=action,
                snapshot=source_snapshot,
                graph=self._build_causal_graph(action, ()),
                branches=(),
                risks=(
                    RiskScore(
                        risk_type="stale_state",
                        severity=0.8,
                        likelihood=0.7,
                        exposure=_exposure_for(action),
                        irreversibility=_irreversibility_for(action),
                        uncertainty=0.9,
                        cascade_potential=0.7,
                        mitigation_strength=0.3,
                        description="Snapshot is too stale for high-impact preview.",
                    ),
                ),
                compensations=(),
                unknowns=("State snapshot is not fresh enough for high-impact action.",),
                assumptions=action.assumptions,
                required_guards=("Refresh state snapshot before execution.",),
                verdict=PreviewVerdict.REQUIRE_MORE_EVIDENCE,
                limitations=("Receipt is not valid for guarded execution.",),
                real_state=real_state,
            )

        simulation_state = self._clone_for_simulation(source_snapshot)
        dependencies, dependency_unknowns = self._discover_dependencies(action)
        graph = self._build_causal_graph(action, dependencies)
        assumptions = self._assumptions(action)
        branches = self._generate_branches(action, dependency_unknowns)

        for branch in branches:
            branch_state = deepcopy(simulation_state)
            self._simulate_branch(
                branch_state=branch_state,
                action=action,
                branch=branch,
                effect_model=effect_model,
            )
            self._check_constraints(
                branch_state=branch_state,
                action=action,
                branch=branch,
            )

        unknowns = _unique_texts(
            (*dependency_unknowns, *self._collect_branch_unknowns(branches))
        )
        compensations = self._build_compensations(action)
        risks = self._score_risks(
            action=action,
            snapshot=source_snapshot,
            branches=branches,
            compensations=compensations,
            unknowns=unknowns,
        )
        required_guards = self._select_guards(
            action=action,
            risks=risks,
            compensations=compensations,
            unknowns=unknowns,
        )
        confidence = self._compute_confidence(
            snapshot=source_snapshot,
            branches=branches,
            compensations=compensations,
            unknowns=unknowns,
        )
        verdict = self._select_verdict(
            action=action,
            branches=branches,
            risks=risks,
            compensations=compensations,
            unknowns=unknowns,
            confidence=confidence,
        )

        return self._receipt(
            action=action,
            snapshot=source_snapshot,
            graph=graph,
            branches=branches,
            risks=risks,
            compensations=compensations,
            unknowns=unknowns,
            assumptions=assumptions,
            required_guards=required_guards,
            verdict=verdict,
            limitations=(
                "Dry-run estimates possible outcomes but does not prove real execution success.",
                "Receipt becomes invalid if target state changes before execution.",
            ),
            real_state=real_state,
        )

    def _admit(self, action: CausalPreviewAction) -> tuple[str, ...]:
        violations: list[str] = []
        for forbidden_flag in (
            "execute_now",
            "send_now",
            "charge_now",
            "deploy_now",
            "delete_now",
            "publish_now",
        ):
            if action.parameters.get(forbidden_flag) is True:
                violations.append(f"Dry-run cannot honor {forbidden_flag}.")
        if action.high_impact and not action.approval_refs:
            violations.append("High-impact action lacks approval evidence.")
        return tuple(violations)

    def _snapshot(self, state: SymbolicPreviewState) -> StateSnapshot:
        raw_state = {
            "identity": deepcopy(dict(state.identity)),
            "constraints": deepcopy(dict(state.constraints)),
            "mutable_state": deepcopy(dict(state.mutable_state)),
            "exposure": deepcopy(dict(state.exposure)),
            "history": deepcopy(tuple(dict(item) for item in state.history)),
        }
        state_hash = _state_hash(raw_state)
        return StateSnapshot(
            snapshot_id=stable_identifier("causal-preview-snapshot", {"state": raw_state}),
            state_hash=state_hash,
            captured_at=self._clock(),
            freshness_score=1.0,
            completeness_score=1.0,
            source_confidence=1.0,
            state=raw_state,
        )

    def _clone_for_simulation(self, snapshot: StateSnapshot) -> dict[str, Any]:
        return {
            "identity": deepcopy(dict(snapshot.state.get("identity", {}))),
            "constraints": deepcopy(dict(snapshot.state.get("constraints", {}))),
            "mutable_state": deepcopy(dict(snapshot.state.get("mutable_state", {}))),
            "exposure": deepcopy(dict(snapshot.state.get("exposure", {}))),
            "history": deepcopy(tuple(snapshot.state.get("history", ()))),
            "simulation_only": True,
        }

    def _discover_dependencies(
        self,
        action: CausalPreviewAction,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        dependencies = _unique_texts(
            (f"target:{action.target_ref}", f"actor:{action.actor_id}", *action.known_dependencies)
        )
        unknowns: list[str] = []
        if action.suspected_dependencies:
            dependencies = _unique_texts((*dependencies, *action.suspected_dependencies))
            unknowns.append("Suspected dependency coverage is not verified.")
        if action.high_impact and not action.known_dependencies:
            unknowns.append("High-impact action has no known dependency evidence.")
        if action.side_effect_class in {
            SideEffectClass.EXTERNAL_SYSTEM,
            SideEffectClass.FINANCIAL,
            SideEffectClass.USER_FACING,
            SideEffectClass.LEGAL_PUBLIC,
        } and not action.parameters.get("external_confirmation_ref"):
            unknowns.append("External system behavior lacks confirmation evidence.")
        return dependencies, tuple(unknowns)

    def _build_causal_graph(
        self,
        action: CausalPreviewAction,
        dependencies: tuple[str, ...],
    ) -> CausalGraph:
        nodes = [
            CausalNode(
                node_id=f"action:{action.action_id}",
                node_type="action",
                description="action proposed for target",
            ),
            CausalNode(
                node_id=f"target:{action.target_ref}",
                node_type="target",
                description=action.target_ref,
            ),
            CausalNode(
                node_id=f"constraint:{action.side_effect_class.value}",
                node_type="constraint",
                description="side effect class constraint",
            ),
        ]
        edges = [
            CausalEdge(
                source=f"action:{action.action_id}",
                target=f"target:{action.target_ref}",
                relation="modifies" if action.mutating else "observes",
            ),
            CausalEdge(
                source=f"constraint:{action.side_effect_class.value}",
                target=f"action:{action.action_id}",
                relation="bounds",
            ),
        ]
        for dependency in dependencies:
            nodes.append(
                CausalNode(
                    node_id=f"dependency:{dependency}",
                    node_type="dependency",
                    description=dependency,
                    confidence=0.8,
                )
            )
            edges.append(
                CausalEdge(
                    source=f"action:{action.action_id}",
                    target=f"dependency:{dependency}",
                    relation="depends_on",
                    confidence=0.8,
                )
            )
        if action.rollback_evidence_refs or action.compensation_evidence_refs:
            nodes.append(
                CausalNode(
                    node_id=f"compensation:{action.action_id}",
                    node_type="compensation",
                    description="recovery evidence available",
                    confidence=0.9,
                )
            )
            edges.append(
                CausalEdge(
                    source=f"compensation:{action.action_id}",
                    target=f"action:{action.action_id}",
                    relation="mitigates",
                    confidence=0.9,
                )
            )
        return CausalGraph(nodes=tuple(nodes), edges=tuple(edges))

    def _assumptions(self, action: CausalPreviewAction) -> tuple[str, ...]:
        return _unique_texts(
            (
                "Snapshot accurately represents the target state at capture time.",
                "Preview cannot certify real execution success.",
                "No real-world mutation occurs during dry-run.",
                f"Action goal is interpreted as: {action.goal}",
                *action.assumptions,
            )
        )

    def _generate_branches(
        self,
        action: CausalPreviewAction,
        dependency_unknowns: tuple[str, ...],
    ) -> tuple[CausalBranch, ...]:
        branch_specs = {
            "expected": ("Expected outcome", 0.45),
            "best_case": ("Best-case outcome", 0.1),
            "known_failure": ("Known failure", 0.12),
            "partial_failure": ("Partial failure", 0.11),
            "adversarial": ("Adversarial branch", 0.08),
            "rollback": ("Rollback branch", 0.07),
            "unknown_dependency": ("Unknown dependency branch", 0.05),
            "stale_state": ("Stale state branch", 0.02),
        }
        branches: list[CausalBranch] = []
        for branch_id in _DEFAULT_BRANCH_IDS:
            name, likelihood = branch_specs[branch_id]
            branch = CausalBranch(
                branch_id=branch_id,
                name=name,
                likelihood=likelihood,
            )
            if branch_id == "unknown_dependency" and dependency_unknowns:
                branch.unknowns.extend(dependency_unknowns)
            branches.append(branch)
        return tuple(branches)

    def _simulate_branch(
        self,
        *,
        branch_state: dict[str, Any],
        action: CausalPreviewAction,
        branch: CausalBranch,
        effect_model: StateTransform | None,
    ) -> None:
        branch.simulated_changes.append(
            f"Simulated {action.action_class.value} on {action.target_ref}."
        )
        if effect_model is not None and branch.branch_id in {"expected", "best_case"}:
            modeled_state = effect_model(deepcopy(branch_state))
            if not isinstance(modeled_state, dict):
                branch.violations.append("Effect model did not return a state mapping.")
            else:
                branch_state.update(modeled_state)
                branch.simulated_changes.append("Applied provided effect model to cloned state.")
        if action.mutating:
            branch.simulated_changes.append("Direct simulated mutation stays inside sandbox.")
        if branch.branch_id == "known_failure":
            branch.simulated_changes.append("Modeled direct failure before goal completion.")
        if branch.branch_id == "partial_failure":
            branch.simulated_changes.append("Modeled incomplete downstream propagation.")
        if branch.branch_id == "adversarial":
            branch.simulated_changes.append("Modeled misuse, dependency drift, or permission mismatch.")
        if branch.branch_id == "rollback":
            branch.simulated_changes.append("Modeled recovery path availability.")
            if action.mutating and not (
                action.rollback_evidence_refs or action.compensation_evidence_refs
            ):
                branch.unknowns.append("Rollback or compensation evidence is missing.")

    def _check_constraints(
        self,
        *,
        branch_state: dict[str, Any],
        action: CausalPreviewAction,
        branch: CausalBranch,
    ) -> None:
        branch.constraint_checks.append(
            ConstraintCheckResult(
                check_id=f"{branch.branch_id}:no_real_mutation",
                branch_id=branch.branch_id,
                status=ConstraintCheckStatus.PASS
                if branch_state.get("simulation_only") is True
                else ConstraintCheckStatus.FAIL,
                reason="Simulation state is isolated from real state.",
            )
        )
        if action.high_impact and not action.approval_refs:
            branch.violations.append("High-impact action lacks approval evidence.")
            branch.constraint_checks.append(
                ConstraintCheckResult(
                    check_id=f"{branch.branch_id}:approval_evidence",
                    branch_id=branch.branch_id,
                    status=ConstraintCheckStatus.FAIL,
                    reason="Approval evidence is required for high-impact action.",
                )
            )
        else:
            branch.constraint_checks.append(
                ConstraintCheckResult(
                    check_id=f"{branch.branch_id}:approval_evidence",
                    branch_id=branch.branch_id,
                    status=ConstraintCheckStatus.PASS,
                    reason="Approval boundary is satisfied or not required.",
                )
            )
        for check_id, check in sorted(self._constraint_checks.items()):
            try:
                passed = check(deepcopy(branch_state))
            except Exception as exc:
                branch.constraint_checks.append(
                    ConstraintCheckResult(
                        check_id=f"{branch.branch_id}:{check_id}",
                        branch_id=branch.branch_id,
                        status=ConstraintCheckStatus.UNKNOWN,
                        reason="Constraint check raised an exception.",
                    )
                )
                branch.unknowns.append(f"Constraint check {check_id} could not be proven.")
                continue
            status = ConstraintCheckStatus.PASS if passed else ConstraintCheckStatus.FAIL
            branch.constraint_checks.append(
                ConstraintCheckResult(
                    check_id=f"{branch.branch_id}:{check_id}",
                    branch_id=branch.branch_id,
                    status=status,
                    reason="Constraint passed." if passed else "Constraint failed.",
                )
            )
            if not passed:
                branch.violations.append(f"Constraint check {check_id} failed.")

    def _build_compensations(
        self,
        action: CausalPreviewAction,
    ) -> tuple[CompensationPlan, ...]:
        if not action.mutating:
            return ()
        evidence_refs = _unique_texts(
            (*action.rollback_evidence_refs, *action.compensation_evidence_refs)
        )
        if action.rollback_evidence_refs:
            status = CompensationVerificationStatus.VERIFIED
            recovery_confidence = 0.9
        elif action.compensation_evidence_refs:
            status = CompensationVerificationStatus.PLAUSIBLE
            recovery_confidence = 0.7
        elif action.side_effect_class is SideEffectClass.IRREVERSIBLE:
            status = CompensationVerificationStatus.UNAVAILABLE
            recovery_confidence = 0.1
        else:
            status = CompensationVerificationStatus.UNTESTED
            recovery_confidence = 0.35
        return (
            CompensationPlan(
                plan_id=stable_identifier(
                    "causal-preview-compensation",
                    {
                        "action_id": action.action_id,
                        "status": status.value,
                        "evidence_refs": evidence_refs,
                    },
                ),
                name="rollback_or_forward_repair",
                steps=(
                    "Stop further execution.",
                    "Restore previous known-good state where evidence permits.",
                    "Verify target state after compensation.",
                    "Emit recovery receipt.",
                    "Escalate unresolved effects.",
                ),
                verification_status=status,
                evidence_refs=evidence_refs,
                limitations=(
                    "May not repair effects outside controlled boundary.",
                    "May not reverse irreversible external side effects.",
                ),
                recovery_confidence=recovery_confidence,
            ),
        )

    def _score_risks(
        self,
        *,
        action: CausalPreviewAction,
        snapshot: StateSnapshot,
        branches: tuple[CausalBranch, ...],
        compensations: tuple[CompensationPlan, ...],
        unknowns: tuple[str, ...],
    ) -> tuple[RiskScore, ...]:
        risks: list[RiskScore] = []
        mitigation_strength = _mitigation_strength(compensations)
        for branch in branches:
            if branch.branch_id == "expected" and not branch.violations and not branch.unknowns:
                continue
            if not action.mutating and not branch.violations and not branch.unknowns:
                continue
            risks.append(
                RiskScore(
                    risk_type=branch.branch_id,
                    severity=0.9 if branch.violations else 0.5,
                    likelihood=branch.likelihood,
                    exposure=_exposure_for(action),
                    irreversibility=_irreversibility_for(action),
                    uncertainty=0.85 if branch.unknowns else 0.4,
                    cascade_potential=0.75 if action.high_impact else 0.35,
                    mitigation_strength=mitigation_strength,
                    description="risk from simulated branch",
                )
            )
        if snapshot.completeness_score < 0.9 or snapshot.source_confidence < 0.9:
            risks.append(
                RiskScore(
                    risk_type="weak_snapshot_evidence",
                    severity=0.6,
                    likelihood=0.6,
                    exposure=_exposure_for(action),
                    irreversibility=_irreversibility_for(action),
                    uncertainty=0.8,
                    cascade_potential=0.6,
                    mitigation_strength=mitigation_strength,
                    description="Snapshot completeness or source confidence is weak.",
                )
            )
        if unknowns:
            risks.append(
                RiskScore(
                    risk_type="unresolved_unknowns",
                    severity=0.5,
                    likelihood=0.8,
                    exposure=_exposure_for(action),
                    irreversibility=_irreversibility_for(action),
                    uncertainty=0.9,
                    cascade_potential=0.65,
                    mitigation_strength=mitigation_strength,
                    description="Unresolved unknowns remain after branch simulation.",
                )
            )
        return tuple(risks)

    def _select_guards(
        self,
        *,
        action: CausalPreviewAction,
        risks: tuple[RiskScore, ...],
        compensations: tuple[CompensationPlan, ...],
        unknowns: tuple[str, ...],
    ) -> tuple[str, ...]:
        guards: list[str] = ["Require post-execution verification if action executes."]
        if unknowns:
            guards.append("Resolve preview unknowns before execution.")
        if risks:
            guards.append("Keep monitoring active until delayed effects settle.")
        if compensations:
            guards.append("Keep compensation path available during execution.")
        if action.high_impact:
            guards.append("Use staged rollout or reduced blast radius.")
        if action.parameters.get("sandbox_only") is True:
            guards.append("Keep execution inside sandbox boundary.")
        return _unique_texts(guards)

    def _compute_confidence(
        self,
        *,
        snapshot: StateSnapshot,
        branches: tuple[CausalBranch, ...],
        compensations: tuple[CompensationPlan, ...],
        unknowns: tuple[str, ...],
    ) -> float:
        branch_confidence = self._branch_coverage(branches, None)
        unknown_confidence = 1.0 - min(0.65, 0.12 * len(unknowns))
        recovery_confidence = 1.0
        if compensations:
            recovery_confidence = min(plan.recovery_confidence for plan in compensations)
        return max(
            0.0,
            min(
                snapshot.freshness_score,
                snapshot.completeness_score,
                snapshot.source_confidence,
                branch_confidence,
                unknown_confidence,
                recovery_confidence,
            ),
        )

    def _select_verdict(
        self,
        *,
        action: CausalPreviewAction,
        branches: tuple[CausalBranch, ...],
        risks: tuple[RiskScore, ...],
        compensations: tuple[CompensationPlan, ...],
        unknowns: tuple[str, ...],
        confidence: float,
    ) -> PreviewVerdict:
        if any(branch.violations for branch in branches):
            return PreviewVerdict.BLOCK
        if action.parameters.get("sandbox_only") is True:
            return PreviewVerdict.APPROVE_ONLY_IN_SANDBOX
        if self._branch_coverage(branches, action.required_branch_ids) < 0.8:
            return PreviewVerdict.SIMULATION_INCONCLUSIVE
        if confidence < 0.35:
            return PreviewVerdict.SIMULATION_INCONCLUSIVE
        if action.high_impact and unknowns:
            return PreviewVerdict.REQUIRE_MORE_EVIDENCE
        if action.side_effect_class is SideEffectClass.IRREVERSIBLE and not compensations:
            return PreviewVerdict.REQUIRE_HUMAN_REVIEW
        if any(
            plan.verification_status
            in {
                CompensationVerificationStatus.UNAVAILABLE,
                CompensationVerificationStatus.DANGEROUS,
            }
            for plan in compensations
        ):
            return PreviewVerdict.REQUIRE_HUMAN_REVIEW
        if any(risk.total() > 0.7 for risk in risks):
            return PreviewVerdict.REQUIRE_HUMAN_REVIEW
        if risks or compensations:
            return PreviewVerdict.APPROVE_WITH_GUARDS
        return PreviewVerdict.APPROVE

    def _receipt(
        self,
        *,
        action: CausalPreviewAction,
        snapshot: StateSnapshot,
        graph: CausalGraph,
        branches: tuple[CausalBranch, ...],
        risks: tuple[RiskScore, ...],
        compensations: tuple[CompensationPlan, ...],
        unknowns: tuple[str, ...],
        assumptions: tuple[str, ...],
        required_guards: tuple[str, ...],
        verdict: PreviewVerdict,
        limitations: tuple[str, ...],
        real_state: SymbolicPreviewState,
    ) -> CausalPreviewReceipt:
        direct, indirect, delayed = _predicted_effects(branches)
        constraint_checks = tuple(
            check for branch in branches for check in branch.constraint_checks
        )
        violations = _unique_texts(
            violation for branch in branches for violation in branch.violations
        )
        branch_coverage = self._branch_coverage(branches, action.required_branch_ids)
        confidence = self._confidence_for_receipt(
            snapshot=snapshot,
            branches=branches,
            compensations=compensations,
            unknowns=unknowns,
        )
        if verdict in {
            PreviewVerdict.BLOCK,
            PreviewVerdict.REQUIRE_MORE_EVIDENCE,
            PreviewVerdict.SIMULATION_INCONCLUSIVE,
        }:
            confidence = min(confidence, 0.35 if verdict is not PreviewVerdict.BLOCK else 0.2)
        receipt_id = stable_identifier(
            "causal-preview-receipt",
            {
                "action_id": action.action_id,
                "snapshot": snapshot.state_hash,
                "verdict": verdict.value,
                "branches": tuple(branch.branch_id for branch in branches),
            },
        )
        return CausalPreviewReceipt(
            receipt_id=receipt_id,
            engine_version=self.ENGINE_VERSION,
            action_id=action.action_id,
            truth_level=TruthLevel.SIMULATED_CONSEQUENCE,
            state_snapshot_hash=snapshot.state_hash,
            snapshot_freshness=snapshot.freshness_score,
            simulation_boundary="sandbox_readonly_preview",
            permissions_checked=(f"actor:{action.actor_id}", f"target:{action.target_ref}"),
            assumptions=_unique_texts(assumptions),
            unknowns=_unique_texts(unknowns),
            causal_graph_hash=graph.graph_hash if graph.nodes else "causal-preview-graph-empty",
            causal_graph_summary={
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "node_types": sorted({node.node_type for node in graph.nodes}),
            },
            branch_summary=tuple(_branch_summary(branch) for branch in branches),
            predicted_direct_effects=direct,
            predicted_indirect_effects=indirect,
            predicted_delayed_effects=delayed,
            constraint_checks=constraint_checks,
            violations=violations,
            risks=risks,
            compensation_plans=compensations,
            branch_coverage_score=branch_coverage,
            confidence_score=confidence,
            verdict=verdict,
            required_guards=_unique_texts(required_guards),
            post_execution_verification_plan=_verification_plan(action),
            limitations=_unique_texts(limitations),
            success_certified=False,
            state_hash_after_preview=_state_hash(
                {
                    "identity": dict(real_state.identity),
                    "constraints": dict(real_state.constraints),
                    "mutable_state": dict(real_state.mutable_state),
                    "exposure": dict(real_state.exposure),
                    "history": tuple(dict(item) for item in real_state.history),
                }
            ),
        )

    def _confidence_for_receipt(
        self,
        *,
        snapshot: StateSnapshot,
        branches: tuple[CausalBranch, ...],
        compensations: tuple[CompensationPlan, ...],
        unknowns: tuple[str, ...],
    ) -> float:
        if not branches:
            return min(snapshot.freshness_score, snapshot.completeness_score, snapshot.source_confidence)
        return self._compute_confidence(
            snapshot=snapshot,
            branches=branches,
            compensations=compensations,
            unknowns=unknowns,
        )

    def _branch_coverage(
        self,
        branches: tuple[CausalBranch, ...],
        required_branch_ids: tuple[str, ...] | None,
    ) -> float:
        required = required_branch_ids or _DEFAULT_BRANCH_IDS
        if not required:
            return 1.0
        present = {branch.branch_id for branch in branches}
        return len([branch_id for branch_id in required if branch_id in present]) / len(required)

    def _collect_branch_unknowns(self, branches: tuple[CausalBranch, ...]) -> tuple[str, ...]:
        return _unique_texts(unknown for branch in branches for unknown in branch.unknowns)


def _branch_summary(branch: CausalBranch) -> Mapping[str, Any]:
    return {
        "branch_id": branch.branch_id,
        "name": branch.name,
        "likelihood": branch.likelihood,
        "simulated_change_count": len(branch.simulated_changes),
        "violation_count": len(branch.violations),
        "unknown_count": len(branch.unknowns),
    }


def _predicted_effects(
    branches: tuple[CausalBranch, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    direct: list[str] = []
    indirect: list[str] = []
    delayed: list[str] = []
    for branch in branches:
        for change in branch.simulated_changes:
            if "Direct" in change or "Simulated" in change:
                direct.append(change)
            elif "downstream" in change or "dependency" in change:
                indirect.append(change)
            else:
                delayed.append(change)
    return _unique_texts(direct), _unique_texts(indirect), _unique_texts(delayed)


def _verification_plan(action: CausalPreviewAction) -> tuple[str, ...]:
    plan = [
        "Verify target state after execution.",
        "Compare actual outcome against preview predictions.",
        "Check delayed side effects.",
        "Emit post-execution verification receipt before success claim.",
    ]
    if action.mutating:
        plan.append("Verify rollback or compensation readiness before execution.")
    return tuple(plan)


def _exposure_for(action: CausalPreviewAction) -> float:
    exposure = {
        SideEffectClass.NONE: 0.1,
        SideEffectClass.LOCAL_ONLY: 0.2,
        SideEffectClass.INTERNAL_SYSTEM: 0.35,
        SideEffectClass.EXTERNAL_SYSTEM: 0.75,
        SideEffectClass.FINANCIAL: 0.9,
        SideEffectClass.LEGAL_PUBLIC: 0.9,
        SideEffectClass.USER_FACING: 0.8,
        SideEffectClass.IRREVERSIBLE: 0.85,
        SideEffectClass.SAFETY_CRITICAL: 1.0,
    }
    return exposure[action.side_effect_class]


def _irreversibility_for(action: CausalPreviewAction) -> float:
    irreversibility = {
        SideEffectClass.NONE: 0.1,
        SideEffectClass.LOCAL_ONLY: 0.25,
        SideEffectClass.INTERNAL_SYSTEM: 0.35,
        SideEffectClass.EXTERNAL_SYSTEM: 0.55,
        SideEffectClass.FINANCIAL: 0.8,
        SideEffectClass.LEGAL_PUBLIC: 0.85,
        SideEffectClass.USER_FACING: 0.65,
        SideEffectClass.IRREVERSIBLE: 1.0,
        SideEffectClass.SAFETY_CRITICAL: 0.95,
    }
    return irreversibility[action.side_effect_class]


def _mitigation_strength(compensations: tuple[CompensationPlan, ...]) -> float:
    if not compensations:
        return 0.2
    return max(0.1, min(plan.recovery_confidence for plan in compensations))


def _state_hash(state: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise CausalPreviewError("state must be deterministic JSON") from exc
    return stable_identifier("state", {"encoded": encoded})


def _unit_float(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CausalPreviewError(f"{field_name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise CausalPreviewError(f"{field_name} must be finite")
    if result < 0.0 or result > 1.0:
        raise CausalPreviewError(f"{field_name} must be between 0.0 and 1.0")
    return result


def _text_tuple(
    values: Any,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise CausalPreviewError(f"{field_name} must be an array")
    result = tuple(ensure_non_empty_text(field_name, item) for item in values)
    if not result and not allow_empty:
        raise CausalPreviewError(f"{field_name} must contain at least one item")
    return result


def _unique_texts(values: Any) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text and text not in result:
                result.append(text)
    return tuple(result)
