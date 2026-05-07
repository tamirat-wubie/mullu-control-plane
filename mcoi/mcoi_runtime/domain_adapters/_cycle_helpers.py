"""
Shared SCCCE cycle wiring used by every domain adapter.

The five domain adapters (software_dev, business_process,
scientific_research, manufacturing, healthcare, education) wire the SAME
seven steps with the SAME shape — they only differ in the strings/values
that flow through. This helper lifts the wiring so adapters carry only
the per-domain values.

The shared seven steps populate a SymbolField with one State, Change,
Causation, Boundary, Pattern, Transformation, Validation, Observation,
Inference, Decision, and Execution per request. The cycle then converges
to zero tension and the adapter receives a CycleResult.

Adapters that need step variation (e.g. an adapter that wants `Inference`
to be `deductive` instead of `inductive`, or a different `Causation`
mechanism) can override individual `**Overrides` keys; defaults match
the software_dev shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from mcoi_runtime.cognition import SCCCECycle, SymbolField
from mcoi_runtime.domain_adapters._types import (
    UniversalRequest,
    UniversalResult,
)
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    Constraint,
    Decision,
    Execution,
    Inference,
    Observation,
    Pattern,
    State,
    Transformation,
    Validation,
)


@dataclass
class StepOverrides:
    """Per-domain overrides for the shared cycle wiring.

    Each field has a sensible default that matches software_dev. Adapters
    set only the fields they care to differentiate.
    """

    # Causation
    causation_mechanism: str = "domain_action"
    causation_strength: float = 0.9

    # Transformation
    transformation_energy: float = 1.0
    transformation_reversibility: str = "reversible"

    # Validation
    validation_evidence_refs: tuple[str, ...] = ("default_evidence",)
    validation_confidence: float = 0.95
    validation_decision: str = "pass"

    # Observation
    observation_sensor: str = "domain_sensor"
    observation_signal: str = "ok"
    observation_confidence: float = 0.99

    # Inference
    inference_rule: str = "domain_rule"
    inference_certainty: float = 0.9
    inference_kind: str = "deductive"

    # Decision
    decision_criteria: tuple[str, ...] = ("default_criterion",)
    decision_justification: str = "default justification"

    # Execution
    execution_plan_prefix: str = "execute domain action"
    execution_resources: tuple[str, ...] = ()


def run_default_cycle(
    universal_req: UniversalRequest,
    overrides: StepOverrides,
    *,
    summary: str = "",
    capture: list | None = None,
) -> UniversalResult:
    """Run the seven shared steps and return a UniversalResult.

    The result.job_definition_id is universal_req.request_id, matching
    the contract domain adapters expect.

    If ``capture`` is provided (v4.11.0+), the cycle's constructs are
    appended to it after the cycle runs. The list is mutated in place;
    callers that don't care leave it None and pay no cost. This is the
    audit-trail capture path used by ``/domains/<name>/process?persist_run=true``.
    """
    field_obj = SymbolField()

    def step_context_sensing(f: SymbolField, ctx: dict) -> bool:
        if "initial_state_id" not in ctx:
            initial = State(configuration=universal_req.initial_state_descriptor)
            target = State(configuration=universal_req.target_state_descriptor)
            f.register(initial)
            f.register(target)
            ctx["initial_state_id"] = initial.id
            ctx["target_state_id"] = target.id
        return True

    def step_goal_activation(f: SymbolField, ctx: dict) -> bool:
        if "boundary_id" not in ctx:
            spec = universal_req.boundary_specification
            b = Boundary(
                inside_predicate=spec["inside_predicate"],
                interface_points=tuple(spec.get("interface_points", [])),
                permeability=spec.get("permeability", "selective"),
            )
            f.register(b)
            ctx["boundary_id"] = b.id
        return True

    def step_knowledge_retrieval(f: SymbolField, ctx: dict) -> bool:
        if "constraint_ids" not in ctx:
            ids: list = []
            for c_spec in universal_req.constraint_set:
                c = Constraint(
                    domain=c_spec["domain"],
                    restriction=c_spec["restriction"],
                    violation_response=c_spec.get("violation_response", "block"),
                )
                f.register(c)
                ids.append(c.id)
            ctx["constraint_ids"] = ids
        return True

    def step_work_definition(f: SymbolField, ctx: dict) -> bool:
        if "change_id" not in ctx and "initial_state_id" in ctx:
            chg = Change(
                state_before_id=ctx["initial_state_id"],
                state_after_id=ctx["target_state_id"],
                delta_vector={"summary": summary} if summary else {"summary": "domain_action"},
            )
            f.register(chg, depends_on=(ctx["initial_state_id"], ctx["target_state_id"]))
            cause = Causation(
                cause_id=ctx["initial_state_id"],
                effect_id=chg.id,
                mechanism=overrides.causation_mechanism,
                strength=overrides.causation_strength,
            )
            f.register(cause, depends_on=(ctx["initial_state_id"], chg.id))
            ctx["change_id"] = chg.id
            ctx["causation_id"] = cause.id
        return True

    def step_task_decomposition(f: SymbolField, ctx: dict) -> bool:
        if "transformation_id" not in ctx and "change_id" in ctx:
            t = Transformation(
                initial_state_id=ctx["initial_state_id"],
                target_state_id=ctx["target_state_id"],
                change_id=ctx["change_id"],
                causation_id=ctx["causation_id"],
                boundary_id=ctx["boundary_id"],
                energy_estimate=overrides.transformation_energy,
                reversibility=overrides.transformation_reversibility,
            )
            f.register(
                t,
                depends_on=(
                    ctx["initial_state_id"],
                    ctx["target_state_id"],
                    ctx["change_id"],
                    ctx["causation_id"],
                    ctx["boundary_id"],
                ),
            )
            ctx["transformation_id"] = t.id
        return True

    def step_quality_monitoring(f: SymbolField, ctx: dict) -> bool:
        if "validation_id" not in ctx and "transformation_id" in ctx:
            p = Pattern(template_state_id=ctx["target_state_id"])
            f.register(p, depends_on=(ctx["target_state_id"],))
            ctx["pattern_id"] = p.id

            v = Validation(
                target_pattern_id=p.id,
                criteria=tuple(
                    str(c["restriction"]) for c in universal_req.constraint_set
                )
                or ("default_acceptance",),
                evidence_refs=overrides.validation_evidence_refs,
                confidence=overrides.validation_confidence,
                decision=overrides.validation_decision,
            )
            f.register(v, depends_on=(p.id,))
            ctx["validation_id"] = v.id
        return True

    def step_value_evaluation(f: SymbolField, ctx: dict) -> bool:
        if "execution_id" not in ctx and "transformation_id" in ctx:
            obs = Observation(
                sensor_identifier=overrides.observation_sensor,
                raw_signal=overrides.observation_signal,
                interpreted_state_id=ctx["target_state_id"],
                confidence=overrides.observation_confidence,
            )
            f.register(obs, depends_on=(ctx["target_state_id"],))

            inf = Inference(
                premise_ids=(ctx["initial_state_id"],),
                rule_identifier=overrides.inference_rule,
                conclusion_id=ctx["target_state_id"],
                certainty=overrides.inference_certainty,
                inference_kind=overrides.inference_kind,
            )
            f.register(inf, depends_on=(ctx["initial_state_id"], ctx["target_state_id"]))

            other_option_id = uuid4()
            dec = Decision(
                option_ids=(ctx["target_state_id"], other_option_id),
                selection_criteria=overrides.decision_criteria,
                chosen_option_id=ctx["target_state_id"],
                justification=overrides.decision_justification,
            )
            f.register(dec, depends_on=(ctx["target_state_id"],))

            exe = Execution(
                plan_description=f"{overrides.execution_plan_prefix}: {summary}".strip(": "),
                decision_id=dec.id,
                resource_allocations=overrides.execution_resources,
                completion_state="completed",
                produced_change_id=ctx["change_id"],
            )
            f.register(exe, depends_on=(dec.id, ctx["change_id"]))
            ctx["execution_id"] = exe.id
        return True

    cycle = SCCCECycle(
        step_context_sensing=step_context_sensing,
        step_goal_activation=step_goal_activation,
        step_knowledge_retrieval=step_knowledge_retrieval,
        step_work_definition=step_work_definition,
        step_task_decomposition=step_task_decomposition,
        step_quality_monitoring=step_quality_monitoring,
        step_value_evaluation=step_value_evaluation,
    )
    cycle_result = cycle.run(field_obj)

    if capture is not None:
        capture.extend(field_obj.all_constructs())

    return UniversalResult(
        job_definition_id=universal_req.request_id,
        **cycle_result.to_universal_result_kwargs(),
    )
