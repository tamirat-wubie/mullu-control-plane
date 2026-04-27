"""
UCJA Layers — L0 through L9.

Each layer is a function:
    Layer(JobDraft) -> tuple[JobDraft, LayerResult]

L0 is the qualification gate. L1–L9 progressively enrich the job
definition. The pipeline runner halts on the first non-PASS result.

The default implementations are deliberately minimal: each layer fills in
the slots it owns from `request_payload` and prior-layer outputs. Domain
adapters override layers when they need richer logic — but the contract
that L0 qualifies and L9 closes is universal.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from mcoi_runtime.ucja.job_draft import JobDraft, LayerResult, LayerVerdict


Layer = Callable[[JobDraft], tuple[JobDraft, LayerResult]]


# ---- L0: Reality Qualification ----


def l0_qualification(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    """Decide whether the request describes a real causal transformation.

    Required signals in request_payload:
      - purpose_statement (non-empty)
      - initial_state_descriptor (dict)
      - target_state_descriptor (dict)
      - boundary_specification (dict with inside_predicate)

    Missing signals → REJECT with reason. Vague but recoverable signals
    (e.g. empty target_state) → RECLASSIFY with suggestion.
    """
    p = draft.request_payload
    purpose = p.get("purpose_statement", "")
    if not purpose:
        return (
            draft,
            LayerResult(
                verdict=LayerVerdict.REJECT,
                reason="L0: purpose_statement is empty; cannot qualify a request without a stated purpose",
            ),
        )

    initial = p.get("initial_state_descriptor", {})
    target = p.get("target_state_descriptor", {})
    if not initial:
        return (
            draft,
            LayerResult(
                verdict=LayerVerdict.RECLASSIFY,
                reason="L0: initial_state_descriptor is empty",
                suggestion="provide initial state observations before requalifying",
            ),
        )
    if not target:
        return (
            draft,
            LayerResult(
                verdict=LayerVerdict.RECLASSIFY,
                reason="L0: target_state_descriptor is empty",
                suggestion="define target state explicitly before requalifying",
            ),
        )

    boundary = p.get("boundary_specification", {})
    if not boundary.get("inside_predicate"):
        return (
            draft,
            LayerResult(
                verdict=LayerVerdict.REJECT,
                reason="L0: boundary_specification.inside_predicate is missing; "
                "an unbounded transformation cannot be qualified",
            ),
        )

    new_draft = replace(
        draft,
        qualified=True,
        qualification_reason="L0: purpose, states, boundary all present",
    )
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L1: Purpose & Boundary Definition ----


def l1_purpose_boundary(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    p = draft.request_payload
    new_draft = replace(
        draft,
        purpose_statement=p.get("purpose_statement", ""),
        boundary_specification=dict(p.get("boundary_specification", {})),
        authority_required=tuple(p.get("authority_required", [])),
    )
    if not new_draft.authority_required:
        return (
            new_draft,
            LayerResult(
                verdict=LayerVerdict.RECLASSIFY,
                reason="L1: no authority_required declared",
                suggestion="declare at least one authority before proceeding",
            ),
        )
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L2: Transformation Modeling ----


def l2_transformation(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    p = draft.request_payload
    initial = dict(p.get("initial_state_descriptor", {}))
    target = dict(p.get("target_state_descriptor", {}))
    mechanism = p.get("causation_mechanism", "domain_specific_action")
    new_draft = replace(
        draft,
        initial_state_descriptor=initial,
        target_state_descriptor=target,
        causation_mechanism=mechanism,
    )
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L3: Dependency & Assumption Mapping ----


def l3_dependency(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    p = draft.request_payload
    deps = tuple(p.get("dependencies", []))
    assumptions = tuple(p.get("assumptions", ()))
    if not assumptions and not deps:
        # No declared dependencies or assumptions is suspicious but not blocking
        assumptions = ("no_dependencies_declared",)
    new_draft = replace(draft, dependencies=deps, assumptions=assumptions)
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L4: Causal Task Decomposition ----


MAX_TASK_DEPTH = 5  # MUSIA spec: bounded depth for L4


def l4_decomposition(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    """Decompose the transformation into atomic tasks.

    Default rule: each acceptance criterion becomes a task; if none are
    declared, a single 'apply_transformation' task is generated.
    """
    p = draft.request_payload
    criteria = tuple(p.get("acceptance_criteria", ()))
    if criteria:
        tasks = tuple(f"satisfy:{c}" for c in criteria)
    else:
        tasks = ("apply_transformation",)
    if len(tasks) > MAX_TASK_DEPTH * 5:  # generous flat-list cap
        return (
            draft,
            LayerResult(
                verdict=LayerVerdict.RECLASSIFY,
                reason="L4_decomposition_limit_exceeded",
                suggestion="group acceptance criteria before requalifying",
            ),
        )
    new_draft = replace(draft, task_descriptions=tasks)
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L5: Functional Structuring ----


def l5_functional(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    """Group tasks into functional groups. Default: one group per task.

    Domain adapters can replace this with smarter grouping.
    """
    groups = tuple((t,) for t in draft.task_descriptions)
    new_draft = replace(draft, functional_groups=groups)
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L6: Flow Connector Contracts ----


def l6_flow_connector(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    """Sequential flow contract by default: group N feeds group N+1."""
    contracts: list[dict] = []
    for i in range(len(draft.functional_groups) - 1):
        contracts.append(
            {
                "from_group_index": i,
                "to_group_index": i + 1,
                "kind": "sequential",
                "interface_contract": "completion_of_prior",
            }
        )
    new_draft = replace(draft, flow_contracts=tuple(contracts))
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L7: Failure / Risk / Degradation ----


def l7_failure_risk(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    p = draft.request_payload
    blast_radius = p.get("blast_radius", "module")
    risks = list(p.get("risks", ()))

    if blast_radius == "system":
        risks.append("system_blast_radius — partial deployment recommended")
    elif blast_radius == "service":
        risks.append("service_blast_radius — staged rollout recommended")

    if not risks:
        risks = ["no_risks_declared"]

    thresholds: tuple[dict, ...] = (
        {"metric": "failure_rate", "threshold": 0.05, "action": "halt"},
        {"metric": "latency_p99_ms", "threshold": 5000, "action": "alert"},
    )
    new_draft = replace(
        draft,
        risks=tuple(risks),
        degradation_thresholds=thresholds,
    )
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L8: Temporal & Decision Governance ----


def l8_temporal(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    p = draft.request_payload
    deadlines = tuple(p.get("deadlines", ()))
    if not deadlines:
        deadlines = (
            {
                "scope": "job_total",
                "validity_window_seconds": 86400,  # 24h default
                "on_expiry": "re_evaluate",
            },
        )
    decision_authorities = tuple(p.get("decision_authorities", ()))
    if not decision_authorities:
        decision_authorities = draft.authority_required
    new_draft = replace(
        draft,
        deadlines=deadlines,
        decision_authorities=decision_authorities,
    )
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- L9: Closure / Validation / Drift Control ----


def l9_closure(draft: JobDraft) -> tuple[JobDraft, LayerResult]:
    """Final layer. Defines closure criteria + drift detectors."""
    p = draft.request_payload
    criteria = tuple(p.get("acceptance_criteria", ()))
    if not criteria:
        return (
            draft,
            LayerResult(
                verdict=LayerVerdict.RECLASSIFY,
                reason="L9: no acceptance_criteria — cannot define closure",
                suggestion="declare measurable acceptance criteria before requalifying",
            ),
        )

    drift_detectors = (
        "input_distribution_shift",
        "assumption_invalidation",
        "boundary_violation",
    )
    new_draft = replace(
        draft,
        closure_criteria=criteria,
        drift_detectors=drift_detectors,
    )
    return new_draft, LayerResult(verdict=LayerVerdict.PASS)


# ---- Default ordered layer list ----


DEFAULT_LAYERS: tuple[tuple[str, Layer], ...] = (
    ("L0_qualification",  l0_qualification),
    ("L1_purpose_boundary", l1_purpose_boundary),
    ("L2_transformation", l2_transformation),
    ("L3_dependency",     l3_dependency),
    ("L4_decomposition",  l4_decomposition),
    ("L5_functional",     l5_functional),
    ("L6_flow_connector", l6_flow_connector),
    ("L7_failure_risk",   l7_failure_risk),
    ("L8_temporal",       l8_temporal),
    ("L9_closure",        l9_closure),
)
