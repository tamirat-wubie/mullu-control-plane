"""
/ucja/* — UCJA L0–L9 pipeline endpoints.

Stateless: the pipeline runs each request fresh against the request payload
the client posts. Outputs are job drafts (full or partial, depending on
which layer halted).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mcoi_runtime.ucja import (
    LayerVerdict,
    UCJAPipeline,
)

router = APIRouter(prefix="/ucja", tags=["ucja"])


class QualifyRequest(BaseModel):
    """Input to /ucja/qualify — only L0 fields are required."""

    purpose_statement: str = Field(...)
    initial_state_descriptor: dict[str, Any] = Field(default_factory=dict)
    target_state_descriptor: dict[str, Any] = Field(default_factory=dict)
    boundary_specification: dict[str, Any] = Field(default_factory=dict)


class LayerResultPayload(BaseModel):
    layer: str
    verdict: str
    reason: str = ""
    suggestion: str = ""


class JobDraftPayload(BaseModel):
    job_id: str
    qualified: bool | None
    purpose_statement: str = ""
    boundary_specification: dict[str, Any] = Field(default_factory=dict)
    authority_required: list[str] = Field(default_factory=list)
    task_descriptions: list[str] = Field(default_factory=list)
    functional_groups: list[list[str]] = Field(default_factory=list)
    flow_contracts: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    deadlines: list[dict[str, Any]] = Field(default_factory=list)
    closure_criteria: list[str] = Field(default_factory=list)
    drift_detectors: list[str] = Field(default_factory=list)
    is_complete: bool


class PipelineOutcomePayload(BaseModel):
    accepted: bool
    reclassified: bool
    rejected: bool
    terminal_verdict: str
    halted_at_layer: str | None
    reason: str
    layer_results: list[LayerResultPayload]
    draft: JobDraftPayload


class DefineJobRequest(BaseModel):
    """Input to /ucja/define-job — full payload for L0 through L9."""

    purpose_statement: str
    initial_state_descriptor: dict[str, Any] = Field(default_factory=dict)
    target_state_descriptor: dict[str, Any] = Field(default_factory=dict)
    boundary_specification: dict[str, Any] = Field(default_factory=dict)
    authority_required: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    blast_radius: str = "module"
    causation_mechanism: str = "domain_specific_action"
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    deadlines: list[dict[str, Any]] = Field(default_factory=list)
    decision_authorities: list[str] = Field(default_factory=list)


def _pipeline_outcome_to_payload(outcome) -> PipelineOutcomePayload:
    draft = outcome.draft
    return PipelineOutcomePayload(
        accepted=outcome.accepted,
        reclassified=outcome.reclassified,
        rejected=outcome.rejected,
        terminal_verdict=outcome.terminal_verdict.value,
        halted_at_layer=outcome.halted_at_layer,
        reason=outcome.reason,
        layer_results=[
            LayerResultPayload(
                layer=name,
                verdict=res.verdict.value,
                reason=res.reason,
                suggestion=res.suggestion,
            )
            for name, res in draft.layer_results
        ],
        draft=JobDraftPayload(
            job_id=str(draft.job_id),
            qualified=draft.qualified,
            purpose_statement=draft.purpose_statement,
            boundary_specification=draft.boundary_specification,
            authority_required=list(draft.authority_required),
            task_descriptions=list(draft.task_descriptions),
            functional_groups=[list(g) for g in draft.functional_groups],
            flow_contracts=list(draft.flow_contracts),
            risks=list(draft.risks),
            deadlines=list(draft.deadlines),
            closure_criteria=list(draft.closure_criteria),
            drift_detectors=list(draft.drift_detectors),
            is_complete=draft.is_complete(),
        ),
    )


@router.post("/qualify", response_model=PipelineOutcomePayload)
def qualify(req: QualifyRequest) -> PipelineOutcomePayload:
    """Run only L0 — the qualification gate.

    Use this to check whether a request describes a real causal
    transformation before committing to a full job definition.
    """
    from mcoi_runtime.ucja.layers import l0_qualification
    from mcoi_runtime.ucja.job_draft import JobDraft

    payload = req.model_dump()
    draft = JobDraft(request_payload=payload)
    new_draft, result = l0_qualification(draft)
    new_draft = new_draft.with_layer("L0_qualification", result)

    accepted = result.verdict == LayerVerdict.PASS
    return PipelineOutcomePayload(
        accepted=accepted,
        reclassified=result.verdict == LayerVerdict.RECLASSIFY,
        rejected=result.verdict == LayerVerdict.REJECT,
        terminal_verdict=result.verdict.value,
        halted_at_layer=None if accepted else "L0_qualification",
        reason=result.reason or "L0 passed",
        layer_results=[
            LayerResultPayload(
                layer="L0_qualification",
                verdict=result.verdict.value,
                reason=result.reason,
                suggestion=result.suggestion,
            )
        ],
        draft=JobDraftPayload(
            job_id=str(new_draft.job_id),
            qualified=new_draft.qualified,
            is_complete=False,
        ),
    )


@router.post("/define-job", response_model=PipelineOutcomePayload)
def define_job(req: DefineJobRequest) -> PipelineOutcomePayload:
    """Run the full UCJA pipeline (L0–L9). Halts on first non-PASS layer.

    A complete result has `accepted=true` and `draft.is_complete=true`.
    """
    pipeline = UCJAPipeline()
    outcome = pipeline.run(req.model_dump())
    return _pipeline_outcome_to_payload(outcome)
