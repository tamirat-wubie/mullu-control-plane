"""
SCCCE Cognitive Cycle — 15-step constraint propagation loop.

Spec source: MUSIA v3.0 §L5 SCCCE_COGNITIVE_CYCLE.

Each iteration runs all 15 steps in order. After each iteration the tension
calculator scores the symbol field; the convergence detector decides whether
to continue, terminate, or escalate.

Each step is a pluggable callback. The default step does nothing — domain
adapters wire the steps that matter for their domain. This is the
orchestration shell, not domain logic.

Step contract: each step receives the symbol field and an opaque context
dict, and may register new constructs into the field via Φ_gov. Steps that
violate Φ_gov return False; cycle aborts on first abort.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from mcoi_runtime.cognition.convergence import (
    ConvergenceDetector,
    ConvergenceReason,
    ConvergenceState,
)
from mcoi_runtime.cognition.symbol_field import SymbolField
from mcoi_runtime.cognition.tension import TensionCalculator, TensionSnapshot


# Hard cap: bounded meta-cognition rule from MUSIA spec (depth ≤ 3 means
# meta-self-references; here we enforce iteration cap ≤ max_iterations,
# step recursion via cycle.run_nested() must respect depth ≤ 3).
META_RECURSION_DEPTH_LIMIT = 3


class CycleStep(Enum):
    CONTEXT_SENSING = 0
    GOAL_ACTIVATION = 1
    CAPABILITY_ASSESSMENT = 2
    KNOWLEDGE_RETRIEVAL = 3
    WORK_DEFINITION = 4
    JOB_BOUNDARY_SETTING = 5
    TASK_DECOMPOSITION = 6
    PROCESS_PLANNING = 7
    FLOW_ORCHESTRATION = 8
    COMMUNICATION_COORDINATION = 9
    QUALITY_MONITORING = 10
    RISK_ASSESSMENT = 11
    VALUE_EVALUATION = 12
    LEARNING_INTEGRATION = 13
    ADAPTATION_EMERGENCE = 14


# A step callback receives (field, context) and returns True on success,
# False on Φ_gov rejection. Steps mutate the field by registering constructs.
StepFn = Callable[[SymbolField, dict[str, Any]], bool]


def _noop_step(field: SymbolField, ctx: dict[str, Any]) -> bool:
    return True


@dataclass
class CycleStepRecord:
    """Per-step trace entry for one iteration."""

    iteration: int
    step: CycleStep
    succeeded: bool
    field_size_after: int


@dataclass
class CycleResult:
    """Outcome of running the cycle to completion (or termination)."""

    converged: bool
    reason: ConvergenceReason
    iterations: int
    final_tension: TensionSnapshot
    tension_history: list[TensionSnapshot] = field(default_factory=list)
    step_records: list[CycleStepRecord] = field(default_factory=list)
    aborted_at_step: Optional[CycleStep] = None
    construct_graph_summary: dict[str, int] = field(default_factory=dict)

    def to_universal_result_kwargs(self) -> dict[str, Any]:
        """Shape compatible with domain_adapters.UniversalResult."""
        return {
            "construct_graph_summary": dict(self.construct_graph_summary),
            "cognitive_cycles_run": self.iterations,
            "converged": self.converged,
            "proof_state": self._proof_state_for_reason(),
        }

    def _proof_state_for_reason(self) -> str:
        # Abort takes priority — a Φ_gov rejection is FAIL regardless of
        # whatever tension state happened to coincide with the abort.
        if self.aborted_at_step is not None:
            return "Fail"
        if self.reason == ConvergenceReason.ZERO_TENSION:
            return "Pass"
        if self.reason == ConvergenceReason.STABLE:
            return "Pass"
        if self.reason == ConvergenceReason.MAX_ITERATIONS:
            return "BudgetUnknown"
        return "Unknown"


@dataclass
class SCCCECycle:
    """The 15-step cognitive cycle. Pluggable per-step callbacks."""

    tension: TensionCalculator = field(default_factory=TensionCalculator)
    convergence: ConvergenceDetector = field(default_factory=ConvergenceDetector)

    # 15 step callbacks. Default to no-op so the cycle runs cleanly with no
    # domain adapter; production callers replace the ones that matter.
    step_context_sensing: StepFn = _noop_step
    step_goal_activation: StepFn = _noop_step
    step_capability_assessment: StepFn = _noop_step
    step_knowledge_retrieval: StepFn = _noop_step
    step_work_definition: StepFn = _noop_step
    step_job_boundary_setting: StepFn = _noop_step
    step_task_decomposition: StepFn = _noop_step
    step_process_planning: StepFn = _noop_step
    step_flow_orchestration: StepFn = _noop_step
    step_communication_coordination: StepFn = _noop_step
    step_quality_monitoring: StepFn = _noop_step
    step_risk_assessment: StepFn = _noop_step
    step_value_evaluation: StepFn = _noop_step
    step_learning_integration: StepFn = _noop_step
    step_adaptation_emergence: StepFn = _noop_step

    def _ordered_steps(self) -> list[tuple[CycleStep, StepFn]]:
        return [
            (CycleStep.CONTEXT_SENSING,         self.step_context_sensing),
            (CycleStep.GOAL_ACTIVATION,         self.step_goal_activation),
            (CycleStep.CAPABILITY_ASSESSMENT,   self.step_capability_assessment),
            (CycleStep.KNOWLEDGE_RETRIEVAL,     self.step_knowledge_retrieval),
            (CycleStep.WORK_DEFINITION,         self.step_work_definition),
            (CycleStep.JOB_BOUNDARY_SETTING,    self.step_job_boundary_setting),
            (CycleStep.TASK_DECOMPOSITION,      self.step_task_decomposition),
            (CycleStep.PROCESS_PLANNING,        self.step_process_planning),
            (CycleStep.FLOW_ORCHESTRATION,      self.step_flow_orchestration),
            (CycleStep.COMMUNICATION_COORDINATION, self.step_communication_coordination),
            (CycleStep.QUALITY_MONITORING,      self.step_quality_monitoring),
            (CycleStep.RISK_ASSESSMENT,         self.step_risk_assessment),
            (CycleStep.VALUE_EVALUATION,        self.step_value_evaluation),
            (CycleStep.LEARNING_INTEGRATION,    self.step_learning_integration),
            (CycleStep.ADAPTATION_EMERGENCE,    self.step_adaptation_emergence),
        ]

    def run(
        self,
        field: SymbolField,
        context: Optional[dict[str, Any]] = None,
    ) -> CycleResult:
        ctx = dict(context or {})
        steps = self._ordered_steps()
        history: list[TensionSnapshot] = []
        records: list[CycleStepRecord] = []
        conv_state: ConvergenceState | None = None
        aborted_step: Optional[CycleStep] = None

        # Initial tension snapshot (iteration 0 baseline)
        initial = self.tension.compute(field)
        history.append(initial)

        while True:
            # Run 15 steps in order
            iteration_index = (conv_state.iterations if conv_state else 0) + 1
            for step_id, step_fn in steps:
                ok = step_fn(field, ctx)
                records.append(
                    CycleStepRecord(
                        iteration=iteration_index,
                        step=step_id,
                        succeeded=ok,
                        field_size_after=field.size,
                    )
                )
                if not ok:
                    aborted_step = step_id
                    break

            # Tension after this iteration's 15 steps
            snap = self.tension.compute(field)
            history.append(snap)

            # Update convergence
            conv_state = self.convergence.evaluate(snap, conv_state)

            if aborted_step is not None:
                # Φ_gov rejection at a step → terminate the cycle
                break

            if conv_state.converged:
                break

        return CycleResult(
            converged=conv_state.converged if conv_state else False,
            reason=conv_state.reason if conv_state else ConvergenceReason.NOT_CONVERGED,
            iterations=conv_state.iterations if conv_state else 0,
            final_tension=history[-1],
            tension_history=history,
            step_records=records,
            aborted_at_step=aborted_step,
            construct_graph_summary=field.type_counts(),
        )
