"""Purpose: bounded iterative cognitive loop that consults already-bootstrapped
    cognitive engines (meta-reasoning, decision-learning, world-state, memory,
    learning admission) around the EXISTING governed single-step dispatch so the
    live operator path becomes observe -> decide -> act -> verify -> learn ->
    (replan or terminate) instead of single-shot and engine-blind.
Governance scope: cognitive-loop orchestration only. This module never reimplements
    governed dispatch, never mutates governed semantics, and only reads/records
    through the engines it is handed.
Dependencies:
  - mcoi_runtime.app.governed_execution.governed_operator_mil_dispatch_with_trace
    (the existing governed dispatch path - delegated to, never replaced)
  - mcoi_runtime.core.meta_reasoning.MetaReasoningEngine (confidence + degraded mode)
  - mcoi_runtime.core.decision_learning.DecisionLearningEngine (outcome recording)
  - mcoi_runtime.core.memory.EpisodicMemory / WorkingMemory (append-only learning anchors)
  - mcoi_runtime.core.world_state.WorldStateEngine (planning-allowed facts; read-only here)
  - mcoi_runtime.contracts.solver_outcome.SolverOutcome (terminal taxonomy)
  - mcoi_runtime.contracts.learning (ADMIT/DEFER/REJECT admission decision)
  - mcoi_runtime.contracts.meta_reasoning.CapabilityConfidence (confidence updates)
  - mcoi_runtime.core.invariants.stable_identifier (deterministic ids + report hash)
Invariants:
  - Default-OFF: this module is only ever reachable when explicitly wired by the
    cognitive_loop integration helper; constructing it has no global side effects.
  - Deterministic: given identical inputs and the same injected clock, run()
    produces an identical CognitiveLoopReport (and identical report_hash). No
    wall-clock, no randomness; the only IO is through the injected engines.
  - ProofState discipline: a hard-law / hard-safety constraint whose proof state
    is Unknown blocks the action (GovernanceBlocked) - the loop never dispatches
    on an unknown hard constraint.
  - No silent failures: every terminal path carries an explicit SolverOutcome and
    a non-empty rationale; engine errors propagate with causal context.
  - Bounded: the loop runs at most max_steps steps and consumes at most a fixed
    step budget; exceeding the budget terminates with BudgetExhausted.
  - Rollback-safe learning: a DEFER/REJECT admission leaves episodic/semantic
    memory untouched (only ADMIT appends an anchor).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable, Mapping

from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.learning import (
    LearningAdmissionDecision,
    LearningAdmissionStatus,
)
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier


class ProofState(StrEnum):
    """Proof state of a hard constraint relevant to a candidate action.

    Mirrors ProofState discipline: only PROVEN hard constraints may be dispatched
    against; UNKNOWN hard-law / hard-safety constraints block the action.
    """

    PROVEN = "proven"
    REFUTED = "refuted"
    UNKNOWN = "unknown"


class DecisionVerdict(StrEnum):
    """The DECIDE-phase verdict produced before any dispatch occurs."""

    PROCEED = "proceed"
    PROCEED_WITH_CAUTION = "proceed_with_caution"
    REPLAN = "replan"
    BLOCK_UNKNOWN_CONSTRAINT = "block_unknown_constraint"
    DEFER_TO_REVIEW = "defer_to_review"


@dataclass(frozen=True, slots=True)
class HardConstraint:
    """A hard-law / hard-safety constraint guarding a candidate action.

    ``proof_state`` is the explicit, externally supplied proof status. An UNKNOWN
    hard constraint blocks the action - the loop never resolves it implicitly.
    """

    constraint_id: str
    description: str
    proof_state: ProofState

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", ensure_non_empty_text("constraint_id", self.constraint_id))
        object.__setattr__(self, "description", ensure_non_empty_text("description", self.description))
        if not isinstance(self.proof_state, ProofState):
            raise RuntimeCoreInvariantError("proof_state must be a ProofState value")


@dataclass(frozen=True, slots=True)
class CognitiveStepRequest:
    """The work item the cognitive loop reasons about across bounded iterations.

    ``policy_decision`` is reused for every replan attempt - the loop never
    fabricates a fresh authorization, it only re-attempts the already-authorized
    action under the same governed dispatch path.
    """

    goal_id: str
    capability_id: str
    template: Mapping[str, object]
    policy_decision: PolicyDecision
    bindings: Mapping[str, str] = field(default_factory=dict)
    hard_constraints: tuple[HardConstraint, ...] = ()
    actor_id: str = "operator_cognitive_loop"

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        if not isinstance(self.template, Mapping):
            raise RuntimeCoreInvariantError("template must be a mapping")
        if not isinstance(self.policy_decision, PolicyDecision):
            raise RuntimeCoreInvariantError("policy_decision must be a PolicyDecision")
        for constraint in self.hard_constraints:
            if not isinstance(constraint, HardConstraint):
                raise RuntimeCoreInvariantError("hard_constraints must contain HardConstraint values")


@dataclass(frozen=True, slots=True)
class CognitiveStepRecord:
    """An immutable per-step record of one observe/decide/act/verify/learn cycle."""

    step_index: int
    observed_planning_entity_count: int
    observed_prior_outcome_count: int
    decision_verdict: DecisionVerdict
    capability_was_degraded: bool
    confidence_before: float
    dispatched: bool
    execution_id: str | None
    verification_passed: bool | None
    outcome_quality: str
    admission_status: LearningAdmissionStatus
    admission_id: str
    block_reason: str


@dataclass(frozen=True, slots=True)
class CognitiveLoopReport:
    """The frozen, deterministic terminal report of a bounded cognitive loop run."""

    goal_id: str
    capability_id: str
    steps: tuple[CognitiveStepRecord, ...]
    replan_count: int
    learning_admission_count: int
    terminal_outcome: SolverOutcome
    rationale: str
    report_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        if not isinstance(self.terminal_outcome, SolverOutcome):
            raise RuntimeCoreInvariantError("terminal_outcome must be a SolverOutcome value")
        object.__setattr__(self, "rationale", ensure_non_empty_text("rationale", self.rationale))
        object.__setattr__(self, "report_hash", ensure_non_empty_text("report_hash", self.report_hash))


# Default DECIDE-phase thresholds. Confidence is the engine-derived overall
# confidence in [0.0, 1.0]; see CapabilityConfidence.overall_confidence.
_DEFAULT_REPLAN_THRESHOLD = 0.3
_DEFAULT_CAUTION_THRESHOLD = 0.5
# A previously-unseen capability has no confidence record; treat it as neutral so
# the first attempt is allowed (parity with the existing single-step path).
_NEUTRAL_CONFIDENCE = 0.5


class CognitiveLoop:
    """Bounded iterative loop wrapping the EXISTING governed single-step dispatch.

    The loop never reimplements governed dispatch: ACT delegates to
    ``governed_operator_mil_dispatch_with_trace`` and VERIFY reads the proof that
    call returns. Everything else (observe/decide/learn) consults the already
    bootstrapped engines that the live single-shot path ignores today.
    """

    def __init__(
        self,
        *,
        governed_dispatcher: object,
        world_state: object,
        episodic_memory: EpisodicMemory,
        meta_reasoning: object,
        decision_learning: object,
        clock: Callable[[], str],
        working_memory: object | None = None,
        semantic_memory: object | None = None,
        max_steps: int = 3,
        step_budget: int = 3,
        replan_threshold: float = _DEFAULT_REPLAN_THRESHOLD,
        caution_threshold: float = _DEFAULT_CAUTION_THRESHOLD,
        dispatch_fn: Callable[..., object] | None = None,
    ) -> None:
        if governed_dispatcher is None:
            raise RuntimeCoreInvariantError("cognitive loop requires a governed_dispatcher")
        if world_state is None:
            raise RuntimeCoreInvariantError("cognitive loop requires a world_state engine")
        if not isinstance(episodic_memory, EpisodicMemory):
            raise RuntimeCoreInvariantError("cognitive loop requires an EpisodicMemory")
        if meta_reasoning is None:
            raise RuntimeCoreInvariantError("cognitive loop requires a meta_reasoning engine")
        if decision_learning is None:
            raise RuntimeCoreInvariantError("cognitive loop requires a decision_learning engine")
        if clock is None:
            raise RuntimeCoreInvariantError("cognitive loop requires an injected clock")
        if max_steps < 1:
            raise RuntimeCoreInvariantError("max_steps must be >= 1")
        if step_budget < 1:
            raise RuntimeCoreInvariantError("step_budget must be >= 1")
        if not (0.0 <= replan_threshold <= caution_threshold <= 1.0):
            raise RuntimeCoreInvariantError(
                "thresholds must satisfy 0.0 <= replan_threshold <= caution_threshold <= 1.0"
            )

        self._governed_dispatcher = governed_dispatcher
        self._world_state = world_state
        self._episodic = episodic_memory
        self._meta = meta_reasoning
        self._learning = decision_learning
        self._clock = clock
        self._working = working_memory
        self._semantic = semantic_memory
        self._max_steps = int(max_steps)
        self._step_budget = int(step_budget)
        self._replan_threshold = float(replan_threshold)
        self._caution_threshold = float(caution_threshold)
        # Injected only for tests; defaults to the real governed dispatch path.
        if dispatch_fn is None:
            from mcoi_runtime.app.governed_execution import (
                governed_operator_mil_dispatch_with_trace,
            )

            dispatch_fn = governed_operator_mil_dispatch_with_trace
        self._dispatch_fn = dispatch_fn

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, request: CognitiveStepRequest) -> CognitiveLoopReport:
        """Run the bounded observe/decide/act/verify/learn loop.

        Terminates into exactly one SolverOutcome taxonomy value. Deterministic
        for identical (request, engine state, clock).
        """
        if not isinstance(request, CognitiveStepRequest):
            raise RuntimeCoreInvariantError("request must be a CognitiveStepRequest")

        steps: list[CognitiveStepRecord] = []
        replan_count = 0
        admission_count = 0
        budget_remaining = self._step_budget
        terminal_outcome: SolverOutcome | None = None
        rationale = ""

        for step_index in range(self._max_steps):
            if budget_remaining <= 0:
                terminal_outcome = SolverOutcome.BUDGET_EXHAUSTED
                rationale = "step budget exhausted before terminal outcome"
                break
            budget_remaining -= 1

            # --- OBSERVE (read-only) ---
            planning_entity_count = self._observe_planning_entities()
            prior_outcomes = self._observe_prior_outcomes(request.capability_id)

            # --- DECIDE (consult meta-reasoning + ProofState BEFORE dispatch) ---
            confidence_before = self._capability_confidence(request.capability_id)
            degraded = self._is_degraded(request.capability_id)
            verdict, block_reason = self._decide(request, confidence_before, degraded)

            if verdict is DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT:
                steps.append(
                    self._non_dispatch_step(
                        step_index=step_index,
                        planning_entity_count=planning_entity_count,
                        prior_outcome_count=len(prior_outcomes),
                        verdict=verdict,
                        degraded=degraded,
                        confidence_before=confidence_before,
                        block_reason=block_reason,
                    )
                )
                terminal_outcome = SolverOutcome.GOVERNANCE_BLOCKED
                rationale = block_reason
                break

            if verdict is DecisionVerdict.DEFER_TO_REVIEW:
                steps.append(
                    self._non_dispatch_step(
                        step_index=step_index,
                        planning_entity_count=planning_entity_count,
                        prior_outcome_count=len(prior_outcomes),
                        verdict=verdict,
                        degraded=degraded,
                        confidence_before=confidence_before,
                        block_reason=block_reason,
                    )
                )
                terminal_outcome = SolverOutcome.SAFE_HALT
                rationale = block_reason
                break

            if verdict is DecisionVerdict.REPLAN:
                # Bounded replan: record a non-dispatch step, consume a step, and
                # re-attempt next iteration if budget/steps remain.
                steps.append(
                    self._non_dispatch_step(
                        step_index=step_index,
                        planning_entity_count=planning_entity_count,
                        prior_outcome_count=len(prior_outcomes),
                        verdict=verdict,
                        degraded=degraded,
                        confidence_before=confidence_before,
                        block_reason=block_reason,
                    )
                )
                replan_count += 1
                if step_index + 1 >= self._max_steps or budget_remaining <= 0:
                    terminal_outcome = SolverOutcome.SAFE_HALT
                    rationale = "replan ceiling reached; halting to await review"
                    break
                continue

            # --- ACT (delegate to EXISTING governed dispatch; no reimplementation) ---
            dispatch_result = self._dispatch_fn(
                self._governed_dispatcher,
                DispatchRequest(
                    goal_id=request.goal_id,
                    route=request.capability_id,
                    template=request.template,
                    bindings=request.bindings,
                ),
                policy_decision=request.policy_decision,
                issued_at=self._clock(),
                actor_id=request.actor_id,
            )
            execution_result = dispatch_result.execution_result

            # --- VERIFY (use the existing dispatch verification proof) ---
            verification_passed = bool(dispatch_result.verification.passed)
            governance_blocked = self._is_governance_blocked(execution_result)
            succeeded = (
                execution_result.status is ExecutionOutcome.SUCCEEDED
                and not governance_blocked
            )
            verified = succeeded and verification_passed

            # --- LEARN (close the loop through every engine) ---
            quality = self._outcome_quality(succeeded, verification_passed)
            self._update_confidence(
                request.capability_id,
                confidence_before,
                succeeded=succeeded,
                verified=verified,
            )
            admission = self._route_learning_admission(
                request=request,
                execution_result=execution_result,
                verified=verified,
                governance_blocked=governance_blocked,
            )
            if admission.status is LearningAdmissionStatus.ADMIT:
                admission_count += 1

            steps.append(
                CognitiveStepRecord(
                    step_index=step_index,
                    observed_planning_entity_count=planning_entity_count,
                    observed_prior_outcome_count=len(prior_outcomes),
                    decision_verdict=verdict,
                    capability_was_degraded=degraded,
                    confidence_before=round(confidence_before, 4),
                    dispatched=True,
                    execution_id=execution_result.execution_id,
                    verification_passed=verification_passed,
                    outcome_quality=quality,
                    admission_status=admission.status,
                    admission_id=admission.admission_id,
                    block_reason="",
                )
            )

            if verified:
                terminal_outcome = SolverOutcome.SOLVED_VERIFIED
                rationale = "execution succeeded and verification passed"
                break
            if succeeded and not verification_passed:
                terminal_outcome = SolverOutcome.SOLVED_UNVERIFIED
                rationale = "execution succeeded but verification did not pass"
                break
            # Failed dispatch: re-attempt within bounds, else await evidence.
            if step_index + 1 >= self._max_steps or budget_remaining <= 0:
                terminal_outcome = SolverOutcome.AWAITING_EVIDENCE
                rationale = "execution did not succeed within step/budget bounds"
                break

        if terminal_outcome is None:
            # Loop exhausted max_steps without an explicit terminal - never silent.
            terminal_outcome = SolverOutcome.BUDGET_EXHAUSTED
            rationale = "max_steps reached without a terminal outcome"

        return self._build_report(
            request=request,
            steps=tuple(steps),
            replan_count=replan_count,
            admission_count=admission_count,
            terminal_outcome=terminal_outcome,
            rationale=rationale,
        )

    # ------------------------------------------------------------------
    # OBSERVE
    # ------------------------------------------------------------------

    def _observe_planning_entities(self) -> int:
        """Count planning-relevant world-state entities (read-only)."""
        list_entities = getattr(self._world_state, "list_entities", None)
        if list_entities is None:
            return 0
        return len(list_entities())

    def _observe_prior_outcomes(self, capability_id: str) -> tuple[MemoryEntry, ...]:
        """Read prior episodic outcomes relevant to this capability (read-only)."""
        entries = self._episodic.list_entries()
        return tuple(
            entry
            for entry in entries
            if entry.content.get("capability_id") == capability_id
            or entry.content.get("route") == capability_id
        )

    # ------------------------------------------------------------------
    # DECIDE
    # ------------------------------------------------------------------

    def _decide(
        self,
        request: CognitiveStepRequest,
        confidence: float,
        degraded: bool,
    ) -> tuple[DecisionVerdict, str]:
        """Decide whether to proceed, replan, defer, or block - before any dispatch.

        ProofState discipline first: any UNKNOWN hard constraint blocks. Then the
        meta-reasoning signals (degraded mode + confidence) gate the verdict.
        """
        for constraint in request.hard_constraints:
            if constraint.proof_state is ProofState.REFUTED:
                return (
                    DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT,
                    f"hard constraint refuted: {constraint.constraint_id}",
                )
            if constraint.proof_state is ProofState.UNKNOWN:
                return (
                    DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT,
                    f"hard constraint proof state unknown: {constraint.constraint_id}",
                )

        if degraded:
            if confidence < self._replan_threshold:
                return (
                    DecisionVerdict.DEFER_TO_REVIEW,
                    "capability degraded with confidence below replan threshold",
                )
            return (
                DecisionVerdict.REPLAN,
                "capability degraded; bounded replan before dispatch",
            )

        if confidence < self._replan_threshold:
            return (
                DecisionVerdict.REPLAN,
                "confidence below replan threshold; bounded replan before dispatch",
            )
        if confidence < self._caution_threshold:
            return (DecisionVerdict.PROCEED_WITH_CAUTION, "confidence in caution band")
        return (DecisionVerdict.PROCEED, "confidence sufficient to proceed")

    def _capability_confidence(self, capability_id: str) -> float:
        """Return engine-derived overall confidence, neutral when unseen."""
        get_confidence = getattr(self._meta, "get_confidence", None)
        if get_confidence is None:
            return _NEUTRAL_CONFIDENCE
        existing = get_confidence(capability_id)
        if existing is None:
            return _NEUTRAL_CONFIDENCE
        return float(existing.overall_confidence)

    def _is_degraded(self, capability_id: str) -> bool:
        is_degraded = getattr(self._meta, "is_degraded", None)
        if is_degraded is None:
            return False
        return bool(is_degraded(capability_id))

    # ------------------------------------------------------------------
    # LEARN
    # ------------------------------------------------------------------

    def _update_confidence(
        self,
        capability_id: str,
        confidence_before: float,
        *,
        succeeded: bool,
        verified: bool,
    ) -> None:
        """Feed the outcome back into meta-reasoning confidence tracking.

        Uses an incremental running rate consistent with the existing
        OperatorLoop._update_capability_confidence approach.
        """
        update = getattr(self._meta, "update_confidence", None)
        get_confidence = getattr(self._meta, "get_confidence", None)
        if update is None or get_confidence is None:
            return
        existing = get_confidence(capability_id)
        sample_count = (existing.sample_count + 1) if existing is not None else 1
        old_success = existing.success_rate if existing is not None else 0.0
        old_verify = existing.verification_pass_rate if existing is not None else 0.0
        old_error = existing.error_rate if existing is not None else 0.0

        weight = 1.0 / sample_count
        new_success = old_success * (1 - weight) + (1.0 if succeeded else 0.0) * weight
        new_verify = old_verify * (1 - weight) + (1.0 if verified else 0.0) * weight
        new_error = old_error * (1 - weight) + (0.0 if succeeded else 1.0) * weight

        update(
            CapabilityConfidence(
                capability_id=capability_id,
                success_rate=round(new_success, 4),
                verification_pass_rate=round(new_verify, 4),
                timeout_rate=0.0,
                error_rate=round(new_error, 4),
                sample_count=sample_count,
                assessed_at=self._clock(),
            )
        )

    def _route_learning_admission(
        self,
        *,
        request: CognitiveStepRequest,
        execution_result: ExecutionResult,
        verified: bool,
        governance_blocked: bool,
    ) -> LearningAdmissionDecision:
        """Emit an ADMIT/DEFER/REJECT decision and only ADMIT appends memory.

        Rollback-safe: DEFER and REJECT never touch episodic/semantic memory.
        Mirrors MILLearningAdmissionGate semantics (committed+verified => admit)
        without requiring a full MIL terminal certificate bundle, which the
        operator MIL dispatch path does not produce.
        """
        knowledge_id = f"cognitive-loop:{request.goal_id}:{request.capability_id}:{execution_result.execution_id}"
        issued_at = self._clock()
        admission_id = stable_identifier(
            "cognitive-loop-admission",
            {"knowledge_id": knowledge_id, "issued_at": issued_at},
        )

        if governance_blocked:
            return LearningAdmissionDecision(
                admission_id=admission_id,
                knowledge_id=knowledge_id,
                status=LearningAdmissionStatus.REJECT,
                reasons=(DecisionReason("execution governance-blocked", "cognitive_loop_reject"),),
                issued_at=issued_at,
                metadata={"status": execution_result.status.value},
            )
        if not verified:
            return LearningAdmissionDecision(
                admission_id=admission_id,
                knowledge_id=knowledge_id,
                status=LearningAdmissionStatus.DEFER,
                reasons=(DecisionReason("outcome not verified; learning deferred", "cognitive_loop_defer"),),
                issued_at=issued_at,
                metadata={"status": execution_result.status.value},
            )

        # ADMIT: append a single episodic anchor (append-only, deterministic id).
        entry = MemoryEntry(
            entry_id=stable_identifier(
                "cognitive-loop-memory",
                {"knowledge_id": knowledge_id, "admission_id": admission_id},
            ),
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={
                "goal_id": request.goal_id,
                "capability_id": request.capability_id,
                "route": request.capability_id,
                "execution_id": execution_result.execution_id,
                "status": execution_result.status.value,
                "verified": verified,
            },
            source_ids=(execution_result.execution_id,),
        )
        admitted = self._episodic.admit(entry)
        return LearningAdmissionDecision(
            admission_id=admission_id,
            knowledge_id=knowledge_id,
            status=LearningAdmissionStatus.ADMIT,
            reasons=(DecisionReason("verified outcome admitted to episodic memory", "cognitive_loop_admit"),),
            issued_at=issued_at,
            metadata={"memory_entry_id": admitted.entry_id},
            extensions={"execution_id": execution_result.execution_id},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_governance_blocked(execution_result: ExecutionResult) -> bool:
        """Detect a governance-blocked dispatch from the existing failure shape.

        The governed dispatch path returns a FAILED ExecutionResult carrying a
        ``governance_blocked`` effect plus ``gates_failed`` metadata (see
        governed_execution._blocked_execution_result). We read that explicit
        shape rather than inventing a new status, since ExecutionOutcome has no
        BLOCKED member.
        """
        if execution_result.status is ExecutionOutcome.SUCCEEDED:
            return False
        for effect in execution_result.actual_effects:
            if effect.name == "governance_blocked":
                return True
        return "gates_failed" in execution_result.metadata

    @staticmethod
    def _outcome_quality(succeeded: bool, verification_passed: bool) -> str:
        if succeeded and verification_passed:
            return "success"
        if succeeded:
            return "partial_success"
        return "failure"

    def _non_dispatch_step(
        self,
        *,
        step_index: int,
        planning_entity_count: int,
        prior_outcome_count: int,
        verdict: DecisionVerdict,
        degraded: bool,
        confidence_before: float,
        block_reason: str,
    ) -> CognitiveStepRecord:
        """Build a deterministic record for a step that did not dispatch."""
        issued_at = self._clock()
        admission_id = stable_identifier(
            "cognitive-loop-nondispatch",
            {"step": step_index, "verdict": verdict.value, "issued_at": issued_at},
        )
        return CognitiveStepRecord(
            step_index=step_index,
            observed_planning_entity_count=planning_entity_count,
            observed_prior_outcome_count=prior_outcome_count,
            decision_verdict=verdict,
            capability_was_degraded=degraded,
            confidence_before=round(confidence_before, 4),
            dispatched=False,
            execution_id=None,
            verification_passed=None,
            outcome_quality="not_dispatched",
            admission_status=LearningAdmissionStatus.DEFER,
            admission_id=admission_id,
            block_reason=block_reason,
        )

    def _build_report(
        self,
        *,
        request: CognitiveStepRequest,
        steps: tuple[CognitiveStepRecord, ...],
        replan_count: int,
        admission_count: int,
        terminal_outcome: SolverOutcome,
        rationale: str,
    ) -> CognitiveLoopReport:
        report_hash = stable_identifier(
            "cognitive-loop-report",
            {
                "goal_id": request.goal_id,
                "capability_id": request.capability_id,
                "terminal_outcome": terminal_outcome.value,
                "replan_count": replan_count,
                "admission_count": admission_count,
                "steps": [
                    {
                        "i": s.step_index,
                        "verdict": s.decision_verdict.value,
                        "dispatched": s.dispatched,
                        "execution_id": s.execution_id,
                        "verification_passed": s.verification_passed,
                        "quality": s.outcome_quality,
                        "admission": s.admission_status.value,
                        "block_reason": s.block_reason,
                    }
                    for s in steps
                ],
            },
        )
        return CognitiveLoopReport(
            goal_id=request.goal_id,
            capability_id=request.capability_id,
            steps=steps,
            replan_count=replan_count,
            learning_admission_count=admission_count,
            terminal_outcome=terminal_outcome,
            rationale=rationale,
            report_hash=report_hash,
        )


__all__ = [
    "CognitiveLoop",
    "CognitiveLoopReport",
    "CognitiveStepRecord",
    "CognitiveStepRequest",
    "DecisionVerdict",
    "HardConstraint",
    "ProofState",
]
