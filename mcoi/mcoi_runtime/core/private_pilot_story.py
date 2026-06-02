"""Purpose: compose the read-only governed private pilot story.
Governance scope: OrgOS request, UAO envelope, governor chain, SDLC gate,
receipt closure, and dashboard-view cohesion.
Dependencies: workflow contracts, canonical UAO examples, governor-chain read
model, and SDLC dashboard read model.
Invariants:
  - The story grants no execution or capability authority.
  - Every handoff is explicit through workflow bindings.
  - UAO decision branches preserve trace and receipt references.
  - Validation fails closed on missing, reordered, writable, or malformed links.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping

from mcoi_runtime.contracts.workflow import (
    StageType,
    WorkflowBinding,
    WorkflowDescriptor,
    WorkflowStage,
)
from mcoi_runtime.core.governor_chain import (
    GOVERNOR_CHAIN_WORKFLOW_ID,
    build_governor_chain_read_model,
)
from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.core.sdlc_dashboard import (
    SdlcDashboardError,
    build_sdlc_dashboard_summary,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_PILOT_WORKFLOW_ID = "orgos.private_pilot.governed_story.v1"
PRIVATE_PILOT_CREATED_AT = "2026-06-01T00:00:00+00:00"
PILOT_PACKET_OUTPUT_KEY = "pilot_packet_ref"
PILOT_PACKET_INPUT_KEY = "upstream_pilot_packet_ref"
PRIVATE_PILOT_STAGE_TIMEOUT_SECONDS = 600
DEFAULT_PRIVATE_PILOT_ORG_ID = "org-private-pilot"
DEFAULT_PRIVATE_PILOT_CASE_ID = "case-private-pilot"
DEFAULT_PRIVATE_PILOT_ACTOR_ID = "operator:private-pilot"
LIVE_REHEARSAL_ACTION_SOURCE = "action://orgos-private-pilot-live-rehearsal"


class PrivatePilotStoryError(ValueError):
    """Raised when the private pilot story cannot be projected safely."""


@dataclass(frozen=True, slots=True)
class PrivatePilotStoryRequest:
    """Request identity used to bind the read-only pilot story."""

    tenant_id: str
    org_id: str = DEFAULT_PRIVATE_PILOT_ORG_ID
    case_id: str = DEFAULT_PRIVATE_PILOT_CASE_ID
    actor_id: str = DEFAULT_PRIVATE_PILOT_ACTOR_ID


@dataclass(frozen=True, slots=True)
class PrivatePilotStageSpec:
    """Canonical stage row for the private pilot story descriptor."""

    order: int
    stage_id: str
    label: str
    responsibility: str


@dataclass(frozen=True, slots=True)
class UaoBranchSpec:
    """Canonical UAO branch expected by the private pilot story."""

    branch_id: str
    label: str
    source_ref: str
    expected_decision_status: str
    expected_execution_allowed: bool
    expected_closure_state: str


CANONICAL_PRIVATE_PILOT_STAGES: tuple[PrivatePilotStageSpec, ...] = (
    PrivatePilotStageSpec(
        1,
        "orgos_request",
        "OrgOS department request",
        "observe tenant-scoped department registry and authority-map request surfaces",
    ),
    PrivatePilotStageSpec(
        2,
        "uao_envelope",
        "UAO envelope",
        "bind the request to approved, blocked, and simulated UAO decision evidence",
    ),
    PrivatePilotStageSpec(
        3,
        "governor_chain",
        "Governor chain",
        "link policy, decision, design, coding, quality, release, and runtime governors",
    ),
    PrivatePilotStageSpec(
        4,
        "sdlc_gate",
        "SDLC gate",
        "project software delivery gate continuity from change request to closure",
    ),
    PrivatePilotStageSpec(
        5,
        "receipt_closure",
        "Receipt closure",
        "collect UAO, causal trace, SDLC, and closure receipt references",
    ),
    PrivatePilotStageSpec(
        6,
        "dashboard_view",
        "Dashboard view",
        "expose stable read-only operator surfaces for private pilot review",
    ),
)

UAO_BRANCH_SPECS: tuple[UaoBranchSpec, ...] = (
    UaoBranchSpec(
        "approved",
        "approved result",
        "examples/universal_action_orchestration.allowed_status_publish.json",
        "allow",
        True,
        "closed_allowed",
    ),
    UaoBranchSpec(
        "blocked",
        "blocked result",
        "examples/universal_action_orchestration.blocked_invoice_payment.json",
        "block",
        False,
        "closed_blocked",
    ),
    UaoBranchSpec(
        "rehearsal",
        "read-only rehearsal",
        "examples/uao/simulated_low_risk_readonly.json",
        "simulate",
        False,
        "closed_simulated",
    ),
)


def build_private_pilot_descriptor(
    *,
    created_at: str = PRIVATE_PILOT_CREATED_AT,
) -> WorkflowDescriptor:
    """Build the read-only workflow descriptor for the private pilot story."""

    stages: list[WorkflowStage] = []
    bindings: list[WorkflowBinding] = []
    previous_stage: PrivatePilotStageSpec | None = None
    for pilot_stage in CANONICAL_PRIVATE_PILOT_STAGES:
        predecessors = (previous_stage.stage_id,) if previous_stage is not None else ()
        stages.append(
            WorkflowStage(
                stage_id=pilot_stage.stage_id,
                stage_type=StageType.OBSERVATION,
                skill_id=None,
                description=pilot_stage.responsibility,
                predecessors=predecessors,
                timeout_seconds=PRIVATE_PILOT_STAGE_TIMEOUT_SECONDS,
            )
        )
        if previous_stage is not None:
            bindings.append(
                WorkflowBinding(
                    binding_id=f"{previous_stage.stage_id}_to_{pilot_stage.stage_id}",
                    source_stage_id=previous_stage.stage_id,
                    source_output_key=PILOT_PACKET_OUTPUT_KEY,
                    target_stage_id=pilot_stage.stage_id,
                    target_input_key=PILOT_PACKET_INPUT_KEY,
                )
            )
        previous_stage = pilot_stage

    return WorkflowDescriptor(
        workflow_id=PRIVATE_PILOT_WORKFLOW_ID,
        name="OrgOS governed private pilot story",
        description=(
            "Read-only workflow descriptor that links an OrgOS department "
            "request through UAO proof, governor-chain review, SDLC gate "
            "evidence, receipt closure, and dashboard review."
        ),
        stages=tuple(stages),
        bindings=tuple(bindings),
        created_at=created_at,
    )


def validate_private_pilot_descriptor(
    descriptor: WorkflowDescriptor | None = None,
) -> tuple[str, ...]:
    """Return private-pilot descriptor violations; empty means valid."""

    workflow = descriptor or build_private_pilot_descriptor()
    violations: list[str] = []
    if workflow.workflow_id != PRIVATE_PILOT_WORKFLOW_ID:
        violations.append("private pilot workflow identifier changed")
    if len(workflow.stages) != len(CANONICAL_PRIVATE_PILOT_STAGES):
        violations.append("private pilot stage count changed")

    expected_stage_ids = tuple(stage.stage_id for stage in CANONICAL_PRIVATE_PILOT_STAGES)
    actual_stage_ids = tuple(stage.stage_id for stage in workflow.stages)
    if actual_stage_ids != expected_stage_ids:
        violations.append("private pilot stage order changed")

    for index, expected in enumerate(CANONICAL_PRIVATE_PILOT_STAGES):
        if index >= len(workflow.stages):
            continue
        actual = workflow.stages[index]
        expected_predecessors = (
            () if index == 0 else (CANONICAL_PRIVATE_PILOT_STAGES[index - 1].stage_id,)
        )
        if actual.stage_id != expected.stage_id:
            violations.append(f"{expected.stage_id} stage identifier changed")
        if actual.stage_type is not StageType.OBSERVATION:
            violations.append(f"{expected.stage_id} must be an observation stage")
        if actual.skill_id is not None:
            violations.append(f"{expected.stage_id} must not bind a live skill")
        if actual.predecessors != expected_predecessors:
            violations.append(f"{expected.stage_id} predecessor binding changed")
        if actual.timeout_seconds != PRIVATE_PILOT_STAGE_TIMEOUT_SECONDS:
            violations.append(f"{expected.stage_id} timeout boundary changed")

    expected_bindings = _expected_bindings()
    actual_bindings = tuple(
        (
            binding.binding_id,
            binding.source_stage_id,
            binding.source_output_key,
            binding.target_stage_id,
            binding.target_input_key,
        )
        for binding in workflow.bindings
    )
    if actual_bindings != expected_bindings:
        violations.append("private pilot handoff bindings changed")
    return tuple(violations)


def load_private_pilot_uao_records(
    branch_paths: Mapping[str, Path] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load and validate UAO branch records for the private pilot story."""

    path_overrides = dict(branch_paths or {})
    records: dict[str, dict[str, Any]] = {}
    for spec in UAO_BRANCH_SPECS:
        artifact_path = path_overrides.get(spec.branch_id, WORKSPACE_ROOT / spec.source_ref)
        if not artifact_path.exists():
            raise PrivatePilotStoryError(f"missing UAO pilot artifact for {spec.branch_id}")
        if not artifact_path.is_file():
            raise PrivatePilotStoryError(f"UAO pilot artifact is not a file for {spec.branch_id}")
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except JSONDecodeError as exc:
            raise PrivatePilotStoryError(f"invalid UAO pilot artifact JSON for {spec.branch_id}") from exc
        except OSError as exc:
            raise PrivatePilotStoryError(f"unreadable UAO pilot artifact for {spec.branch_id}") from exc
        if not isinstance(payload, dict):
            raise PrivatePilotStoryError(f"UAO pilot artifact must be an object for {spec.branch_id}")
        _validate_uao_branch_record(spec, payload)
        records[spec.branch_id] = payload
    return records


def build_private_pilot_live_rehearsal_uao_record(
    request: PrivatePilotStoryRequest,
    admission_previews: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    *,
    created_at: str = PRIVATE_PILOT_CREATED_AT,
) -> dict[str, Any]:
    """Build a UAO v1 simulation receipt from live OrgOS admission previews."""

    _validate_request(request)
    previews = _validated_live_rehearsal_previews(request, admission_previews)
    preview_ids = [preview["admission_preview_id"] for preview in previews]
    preview_decisions = [preview["decision"] for preview in previews]
    preview_step_ids = [preview["step_id"] for preview in previews]
    action_id = stable_identifier(
        "act-private-pilot-rehearsal",
        {
            "tenant_id": request.tenant_id,
            "org_id": request.org_id,
            "case_id": request.case_id,
            "actor_id": request.actor_id,
            "preview_ids": preview_ids,
            "preview_decisions": preview_decisions,
        },
    )
    trace_ref = f"trace://{stable_identifier('cdt-private-pilot-rehearsal', {'action_id': action_id})}"
    admission_receipt_ref = f"receipt://{stable_identifier('uao-admission-private-pilot-rehearsal', {'action_id': action_id})}"
    trace_receipt_ref = f"receipt://{stable_identifier('uao-trace-private-pilot-rehearsal', {'action_id': action_id})}"
    simulation_receipt_ref = f"receipt://{stable_identifier('uao-simulation-private-pilot-rehearsal', {'action_id': action_id})}"
    closure_receipt_ref = f"receipt://{stable_identifier('uao-closure-private-pilot-rehearsal', {'action_id': action_id})}"
    receipt_set_ref = f"receipt-set://{action_id}"
    simulation_ref = f"simulation://{action_id}"
    closure_ref = f"closure://{action_id}"
    capability_refs = _live_rehearsal_capability_refs(previews)
    evidence_refs = _live_rehearsal_evidence_refs(previews)
    policy_refs = _live_rehearsal_policy_refs(previews)
    temporal_refs = [f"temporal://private-pilot/{request.case_id}/rehearsal-window"]
    closure_confirmation = stable_identifier(
        "universal-action-closure-confirmation",
        {
            "closure_state": "closed_simulated",
            "reconciliation_ref": "",
            "memory_ref": "",
        },
    )
    delta_ref = stable_identifier(
        "private-pilot-rehearsal-delta",
        {
            "action_id": action_id,
            "trace_ref": trace_ref,
            "preview_ids": preview_ids,
        },
    )
    record = {
        "orchestration_id": stable_identifier(
            "private-pilot-rehearsal-uao",
            {
                "action_id": action_id,
                "trace_ref": trace_ref,
                "delta_ref": delta_ref,
            },
        ),
        "uao_schema_version": "uao.v1",
        "action_id": action_id,
        "tenant_id": request.tenant_id,
        "actor_id": request.actor_id,
        "created_at": created_at,
        "action_envelope": {
            "source": LIVE_REHEARSAL_ACTION_SOURCE,
            "actor": request.actor_id,
            "tenant": request.tenant_id,
            "intent": "private_pilot_live_rehearsal",
            "target": f"target://orgos/{request.org_id}/{request.case_id}/private-pilot",
            "risk": "low",
            "requested_at": created_at,
            "approval_ref": None,
            "evidence_refs": evidence_refs,
            "capability_refs": capability_refs,
        },
        "effect_bearing": False,
        "effect_classes": [],
        "input_refs": [
            LIVE_REHEARSAL_ACTION_SOURCE,
            *evidence_refs,
        ],
        "policy_refs": policy_refs,
        "capability_refs": capability_refs,
        "temporal_refs": temporal_refs,
        "exposure_boundary": {
            "redaction_level": "user_safe",
            "allowed_audiences": ["operator", "auditor"],
            "blocked_payload_classes": [
                "raw_private_reasoning",
                "secrets",
                "internal_provider_payloads",
                "cross_tenant_data",
            ],
        },
        "pipeline_stages": [
            _uao_stage(
                "stage_action",
                1,
                "action",
                "completed",
                [LIVE_REHEARSAL_ACTION_SOURCE],
                [f"envelope://{action_id}"],
            ),
            _uao_stage(
                "stage_evidence",
                2,
                "evidence",
                "completed",
                evidence_refs,
                [f"evidence-set://{action_id}"],
            ),
            _uao_stage(
                "stage_trace",
                3,
                "trace",
                "completed",
                [f"evidence-set://{action_id}"],
                [trace_ref],
                trace_receipt_ref,
            ),
            _uao_stage(
                "stage_admission",
                4,
                "admission",
                "simulated",
                [trace_ref],
                [f"decision://{action_id}"],
                admission_receipt_ref,
            ),
            _uao_stage(
                "stage_capability",
                5,
                "capability",
                "simulated",
                capability_refs,
                [f"capability-binding://{action_id}/simulation"],
            ),
            _uao_stage(
                "stage_execution",
                6,
                "execution",
                "simulated",
                [f"capability-binding://{action_id}/simulation"],
                [simulation_ref],
                simulation_receipt_ref,
            ),
            _uao_stage(
                "stage_receipt",
                7,
                "receipt",
                "completed",
                [simulation_ref],
                [receipt_set_ref],
                simulation_receipt_ref,
            ),
            _uao_stage(
                "stage_reconciliation",
                8,
                "reconciliation",
                "skipped",
                [receipt_set_ref],
                [],
                None,
                "simulation_only",
            ),
            _uao_stage(
                "stage_memory",
                9,
                "memory",
                "skipped",
                [f"decision://{action_id}"],
                [],
                None,
                "simulation_only",
            ),
            _uao_stage(
                "stage_closure",
                10,
                "closure",
                "completed",
                [receipt_set_ref],
                [closure_ref],
                closure_receipt_ref,
            ),
        ],
        "admission_guards": _live_rehearsal_admission_guards(
            request=request,
            previews=previews,
            capability_refs=capability_refs,
            evidence_refs=evidence_refs,
            policy_refs=policy_refs,
            temporal_refs=temporal_refs,
            admission_receipt_ref=admission_receipt_ref,
        ),
        "decision": {
            "status": "simulate",
            "reason_code": "live_orgos_rehearsal_only",
            "proof_state": "Unknown",
            "solver_outcome": "AwaitingEvidence",
            "next_action": "inspect_live_rehearsal_receipt",
            "execution_allowed": False,
        },
        "trace_ref": trace_ref,
        "causal_decision_trace_ref": trace_ref,
        "admission_receipt_ref": admission_receipt_ref,
        "execution_receipt_ref": None,
        "receipts": [
            _uao_receipt(
                admission_receipt_ref,
                "R1",
                "admission",
                "stage_admission",
                f"live OrgOS admission preview(s): {', '.join(preview_ids)}",
                False,
            ),
            _uao_receipt(
                trace_receipt_ref,
                "R1",
                "trace",
                "stage_trace",
                "live OrgOS causal preview trace linked",
                False,
            ),
            _uao_receipt(
                simulation_receipt_ref,
                "R0",
                "simulation",
                "stage_execution",
                f"read-only private pilot rehearsal for step(s): {', '.join(preview_step_ids)}",
                False,
            ),
            _uao_receipt(
                closure_receipt_ref,
                "R1",
                "closure",
                "stage_closure",
                closure_confirmation,
                False,
            ),
        ],
        "reconciliation": {
            "status": "not_required",
            "observed_outcome_ref": None,
            "required_for_closure": False,
            "mismatch_reason": None,
        },
        "memory_update": {
            "status": "not_required",
            "memory_ref": None,
            "learning_allowed": False,
        },
        "closure_state": "closed_simulated",
        "closure": {
            "status": "closed_simulated",
            "terminal": True,
            "closure_receipt_ref": closure_receipt_ref,
            "reconciliation_ref": None,
            "memory_ref": None,
            "next_action": "inspect_live_rehearsal_receipt",
        },
        "raw_reasoning_included": False,
        "lineage": {
            "delta_ref": delta_ref,
            "logged_in_lineage": True,
            "accepted_deltas": [],
            "rejected_deltas": [
                {
                    "delta_id": delta_ref,
                    "reason": "live_orgos_rehearsal_only",
                    "logged_in_lineage": True,
                }
            ],
        },
    }
    _validate_uao_branch_record(UAO_BRANCH_SPECS[2], record)
    return record


def build_private_pilot_story(
    request: PrivatePilotStoryRequest,
    *,
    uao_records: Mapping[str, Mapping[str, Any]] | None = None,
    governor_chain: Mapping[str, Any] | None = None,
    sdlc_dashboard: Mapping[str, Any] | None = None,
    created_at: str = PRIVATE_PILOT_CREATED_AT,
) -> dict[str, Any]:
    """Build the read-only private pilot story read model."""

    _validate_request(request)
    workflow = build_private_pilot_descriptor(created_at=created_at)
    descriptor_violations = list(validate_private_pilot_descriptor(workflow))
    loaded_uao_records = (
        load_private_pilot_uao_records() if uao_records is None else dict(uao_records)
    )
    _validate_uao_record_set(loaded_uao_records)
    try:
        governor_read_model = (
            build_governor_chain_read_model(created_at=created_at)
            if governor_chain is None
            else dict(governor_chain)
        )
        sdlc_read_model = (
            build_sdlc_dashboard_summary()
            if sdlc_dashboard is None
            else dict(sdlc_dashboard)
        )
    except SdlcDashboardError as exc:
        raise PrivatePilotStoryError("sdlc dashboard projection unavailable") from exc

    uao_branches = _uao_branch_summaries(loaded_uao_records)
    receipt_refs = _unique_text(
        [
            *(ref for branch in uao_branches for ref in branch["receipt_refs"]),
            *_text_list(sdlc_read_model.get("receipt_refs")),
        ]
    )
    causal_trace_refs = _unique_text(
        [
            *(branch["causal_decision_trace_ref"] for branch in uao_branches),
            *_text_list(sdlc_read_model.get("causal_decision_trace_refs")),
        ]
    )
    uao_refs = _unique_text(
        [
            *(branch["orchestration_id"] for branch in uao_branches),
            *_text_list(sdlc_read_model.get("uao_refs")),
        ]
    )
    source_violations = _source_violations(governor_read_model, sdlc_read_model, uao_branches)
    violations = tuple([*descriptor_violations, *source_violations])
    stage_rows = _stage_rows(
        request=request,
        uao_branches=uao_branches,
        governor_read_model=governor_read_model,
        sdlc_read_model=sdlc_read_model,
        receipt_refs=receipt_refs,
        causal_trace_refs=causal_trace_refs,
    )
    return {
        "story_id": f"private-pilot-story:{request.tenant_id}:{request.org_id}:{request.case_id}",
        "read_model_version": "private_pilot_story.v1",
        "read_only": True,
        "governed": True,
        "valid": not violations,
        "violations": violations,
        "created_at": created_at,
        "composition_outcome": "SolvedVerified" if not violations else "GovernanceBlocked",
        "pilot_execution_outcome": "AwaitingEvidence",
        "execution_state": "read_only_rehearsal_not_executed",
        "authority_boundary": {
            "execution_authority_granted": False,
            "effect_bearing": False,
            "live_capabilities_invoked": False,
            "grants_new_capability_authority": False,
            "external_mutation_allowed": False,
        },
        "request": {
            "tenant_id": request.tenant_id,
            "org_id": request.org_id,
            "case_id": request.case_id,
            "actor_id": request.actor_id,
            "intent": "governed_private_pilot_rehearsal",
        },
        "orgos": _orgos_refs(request),
        "workflow": workflow.to_json_dict(),
        "stage_count": len(stage_rows),
        "stages": stage_rows,
        "uao_branch_count": len(uao_branches),
        "uao_branches": uao_branches,
        "result_refs": _result_refs(uao_branches),
        "governor_chain": {
            "workflow_id": GOVERNOR_CHAIN_WORKFLOW_ID,
            "valid": bool(governor_read_model.get("valid")),
            "stage_count": int(governor_read_model.get("stage_count", 0)),
            "handoff": _text(governor_read_model.get("handoff")),
            "chain": _text_list(governor_read_model.get("chain")),
            "dashboard_ref": "mcoi_runtime.core.governor_chain.build_governor_chain_read_model",
        },
        "sdlc_dashboard": {
            "dashboard_id": _text(sdlc_read_model.get("dashboard_id")),
            "read_only": bool(sdlc_read_model.get("read_only")),
            "governed": bool(sdlc_read_model.get("governed")),
            "stage_count": int(sdlc_read_model.get("stage_count", 0)),
            "blocker_count": int(sdlc_read_model.get("blocker_count", 0)),
            "receipt_count": int(sdlc_read_model.get("receipt_count", 0)),
            "closure": dict(sdlc_read_model.get("closure", {})),
            "dashboard_ref": "/software/receipts/sdlc/dashboard",
        },
        "dashboard_refs": _dashboard_refs(request),
        "receipt_count": len(receipt_refs),
        "receipt_refs": receipt_refs,
        "uao_ref_count": len(uao_refs),
        "uao_refs": uao_refs,
        "causal_decision_trace_ref_count": len(causal_trace_refs),
        "causal_decision_trace_refs": causal_trace_refs,
        "closure": {
            "status": "ready_for_private_pilot_rehearsal" if not violations else "blocked",
            "terminal": False,
            "next_action": "run tenant-bound private pilot rehearsal",
            "requires_live_execution_before_product_claim": True,
        },
    }


def build_private_pilot_operator_view(story: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact read-only operator view from a private pilot story."""

    if not isinstance(story, Mapping):
        raise PrivatePilotStoryError("private pilot operator view requires a story object")
    if story.get("read_only") is not True:
        raise PrivatePilotStoryError("private pilot operator view requires a read-only story")
    if story.get("governed") is not True:
        raise PrivatePilotStoryError("private pilot operator view requires a governed story")

    request = story.get("request")
    if not isinstance(request, Mapping):
        raise PrivatePilotStoryError("private pilot operator view requires request binding")
    tenant_id = _text(request.get("tenant_id"))
    org_id = _text(request.get("org_id"))
    case_id = _text(request.get("case_id"))
    actor_id = _text(request.get("actor_id"))
    if not tenant_id or not org_id or not case_id or not actor_id:
        raise PrivatePilotStoryError("private pilot operator view request binding is incomplete")

    authority = story.get("authority_boundary")
    if not isinstance(authority, Mapping):
        raise PrivatePilotStoryError("private pilot operator view requires authority boundary")
    uao_branches = [
        branch for branch in story.get("uao_branches", [])
        if isinstance(branch, Mapping)
    ]
    rehearsal_branch = next(
        (branch for branch in uao_branches if branch.get("branch_id") == "rehearsal"),
        None,
    )
    if rehearsal_branch is None:
        raise PrivatePilotStoryError("private pilot operator view requires rehearsal branch")

    governor_chain = story.get("governor_chain")
    governor_chain = governor_chain if isinstance(governor_chain, Mapping) else {}
    sdlc_dashboard = story.get("sdlc_dashboard")
    sdlc_dashboard = sdlc_dashboard if isinstance(sdlc_dashboard, Mapping) else {}
    closure = story.get("closure")
    closure = closure if isinstance(closure, Mapping) else {}
    orgos = story.get("orgos")
    orgos = orgos if isinstance(orgos, Mapping) else {}
    dashboard_refs = _unique_text([
        *_text_list(story.get("dashboard_refs")),
        "/software/receipts/private-pilot/operator-view",
        "/software/receipts/private-pilot/operator-view/view",
    ])

    checks = [
        _operator_check(
            "story_read_only",
            story.get("read_only") is True,
            "private_pilot_story_read_only",
            ["/software/receipts/private-pilot/story"],
        ),
        _operator_check(
            "no_execution_authority",
            authority.get("execution_authority_granted") is False,
            "execution_authority_not_granted",
            ["authority://private-pilot/no-execution"],
        ),
        _operator_check(
            "no_external_mutation",
            authority.get("external_mutation_allowed") is False,
            "external_mutation_blocked",
            ["authority://private-pilot/no-external-mutation"],
        ),
        _operator_check(
            "uao_rehearsal_simulated",
            rehearsal_branch.get("decision_status") == "simulate"
            and rehearsal_branch.get("execution_allowed") is False,
            "uao_rehearsal_is_simulation_only",
            [_text(rehearsal_branch.get("closure_receipt_ref"))],
        ),
        _operator_check(
            "governor_chain_valid",
            governor_chain.get("valid") is True,
            "governor_chain_read_model_valid",
            [GOVERNOR_CHAIN_WORKFLOW_ID],
        ),
        _operator_check(
            "sdlc_dashboard_read_only",
            sdlc_dashboard.get("read_only") is True
            and sdlc_dashboard.get("governed") is True,
            "sdlc_dashboard_governed_read_only",
            [_text(sdlc_dashboard.get("dashboard_ref"))],
        ),
        _operator_check(
            "receipt_refs_bound",
            int(story.get("receipt_count", 0)) > 0,
            "receipt_refs_present",
            _text_list(story.get("receipt_refs"))[:3],
        ),
    ]
    operator_ready = all(check["passed"] for check in checks)
    receipt_refs = _text_list(story.get("receipt_refs"))
    uao_refs = _text_list(story.get("uao_refs"))
    causal_trace_refs = _text_list(story.get("causal_decision_trace_refs"))
    timeline = [
        _operator_timeline_item(
            1,
            "request",
            "OrgOS request",
            "tenant_bound",
            "request_scope_bound",
            [
                _text(orgos.get("department_registry_ref")),
                _text(orgos.get("authority_map_ref")),
                _text(orgos.get("case_proof_timeline_ref")),
            ],
        ),
        _operator_timeline_item(
            2,
            "uao_rehearsal",
            "UAO rehearsal",
            _text(rehearsal_branch.get("decision_status")),
            _text(rehearsal_branch.get("solver_outcome")),
            [
                _text(rehearsal_branch.get("source_ref")),
                _text(rehearsal_branch.get("causal_decision_trace_ref")),
                _text(rehearsal_branch.get("closure_receipt_ref")),
            ],
            receipt_refs=_text_list(rehearsal_branch.get("receipt_refs")),
            execution_allowed=bool(rehearsal_branch.get("execution_allowed")),
        ),
        _operator_timeline_item(
            3,
            "governor_chain",
            "Governor chain",
            "valid" if governor_chain.get("valid") is True else "blocked",
            _text(governor_chain.get("handoff")),
            [
                GOVERNOR_CHAIN_WORKFLOW_ID,
                _text(governor_chain.get("dashboard_ref")),
            ],
            stage_count=int(governor_chain.get("stage_count", 0)),
        ),
        _operator_timeline_item(
            4,
            "sdlc_evidence",
            "SDLC evidence",
            "ready" if int(sdlc_dashboard.get("blocker_count", 0)) == 0 else "blocked",
            _text(sdlc_dashboard.get("dashboard_id")),
            [
                _text(sdlc_dashboard.get("dashboard_ref")),
                _text(sdlc_dashboard.get("closure", {}).get("closure_receipt_ref"))
                if isinstance(sdlc_dashboard.get("closure"), Mapping)
                else "",
            ],
            stage_count=int(sdlc_dashboard.get("stage_count", 0)),
            receipt_refs=_text_list(sdlc_dashboard.get("closure", {}).get("receipt_refs"))
            if isinstance(sdlc_dashboard.get("closure"), Mapping)
            else [],
        ),
        _operator_timeline_item(
            5,
            "receipt_closure",
            "Receipt closure",
            _text(closure.get("status")),
            _text(closure.get("next_action")),
            receipt_refs,
            receipt_refs=receipt_refs,
        ),
    ]
    return {
        "operator_view_id": f"private-pilot-operator-view:{tenant_id}:{org_id}:{case_id}",
        "read_model_version": "private_pilot_operator_view.v1",
        "read_only": True,
        "governed": True,
        "story_id": _text(story.get("story_id")),
        "story_ref": "/software/receipts/private-pilot/story",
        "html_view_ref": "/software/receipts/private-pilot/operator-view/view",
        "request": {
            "tenant_id": tenant_id,
            "org_id": org_id,
            "case_id": case_id,
            "actor_id": actor_id,
            "intent": _text(request.get("intent")),
        },
        "summary": {
            "composition_outcome": _text(story.get("composition_outcome")),
            "pilot_execution_outcome": _text(story.get("pilot_execution_outcome")),
            "execution_state": _text(story.get("execution_state")),
            "operator_outcome": "SolvedVerified" if operator_ready else "GovernanceBlocked",
            "operator_ready": operator_ready,
            "next_action": _text(closure.get("next_action")),
        },
        "authority_boundary": {
            "execution_authority_granted": authority.get("execution_authority_granted") is True,
            "dispatch_authority_granted": authority.get("dispatch_authority_granted") is True,
            "external_mutation_allowed": authority.get("external_mutation_allowed") is True,
            "live_capabilities_invoked": authority.get("live_capabilities_invoked") is True,
        },
        "operator_check_count": len(checks),
        "operator_checks": checks,
        "timeline_count": len(timeline),
        "timeline": timeline,
        "receipt_panel": {
            "receipt_count": len(receipt_refs),
            "receipts": _operator_ref_panel(receipt_refs, limit=16),
            "uao_count": len(uao_refs),
            "uao_refs": _operator_ref_panel(uao_refs, limit=12),
            "causal_trace_count": len(causal_trace_refs),
            "causal_trace_refs": _operator_ref_panel(causal_trace_refs, limit=12),
        },
        "dashboard_refs": dashboard_refs,
    }


def _validate_request(request: PrivatePilotStoryRequest) -> None:
    for field_name, value in (
        ("tenant_id", request.tenant_id),
        ("org_id", request.org_id),
        ("case_id", request.case_id),
        ("actor_id", request.actor_id),
    ):
        if not _text(value):
            raise PrivatePilotStoryError(f"private pilot request field is empty: {field_name}")


def _validate_uao_record_set(records: Mapping[str, Mapping[str, Any]]) -> None:
    for spec in UAO_BRANCH_SPECS:
        record = records.get(spec.branch_id)
        if not isinstance(record, Mapping):
            raise PrivatePilotStoryError(f"missing UAO branch record for {spec.branch_id}")
        _validate_uao_branch_record(spec, record)


def _validate_uao_branch_record(spec: UaoBranchSpec, record: Mapping[str, Any]) -> None:
    required_fields = (
        "orchestration_id",
        "tenant_id",
        "actor_id",
        "decision",
        "trace_ref",
        "causal_decision_trace_ref",
        "admission_receipt_ref",
        "receipts",
        "closure_state",
        "closure",
        "raw_reasoning_included",
    )
    missing = [field_name for field_name in required_fields if field_name not in record]
    if missing:
        raise PrivatePilotStoryError(
            f"UAO branch {spec.branch_id} missing field(s): {', '.join(missing)}"
        )
    decision = record.get("decision")
    if not isinstance(decision, Mapping):
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} decision must be an object")
    if decision.get("status") != spec.expected_decision_status:
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} decision status changed")
    if decision.get("execution_allowed") is not spec.expected_execution_allowed:
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} execution boundary changed")
    if record.get("closure_state") != spec.expected_closure_state:
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} closure state changed")
    if record.get("raw_reasoning_included") is not False:
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} exposes raw reasoning")
    closure = record.get("closure")
    if not isinstance(closure, Mapping):
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} closure must be an object")
    for field_name in ("closure_receipt_ref", "reconciliation_ref", "memory_ref"):
        if field_name not in closure:
            raise PrivatePilotStoryError(
                f"UAO branch {spec.branch_id} closure missing {field_name}"
            )
    if not isinstance(record.get("receipts"), list) or not record["receipts"]:
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} requires receipt records")
    if not _text(record.get("trace_ref")):
        raise PrivatePilotStoryError(f"UAO branch {spec.branch_id} trace ref is empty")
    if not _text(record.get("causal_decision_trace_ref")):
        raise PrivatePilotStoryError(
            f"UAO branch {spec.branch_id} causal decision trace ref is empty"
        )
    if spec.branch_id == "rehearsal" and record.get("effect_bearing") is not False:
        raise PrivatePilotStoryError("UAO rehearsal branch must remain non-effect-bearing")


def _uao_branch_summaries(records: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    branch_rows: list[dict[str, Any]] = []
    for spec in UAO_BRANCH_SPECS:
        record = records[spec.branch_id]
        decision = record["decision"]
        receipt_refs = _unique_text(
            receipt.get("receipt_id")
            for receipt in record["receipts"]
            if isinstance(receipt, Mapping)
        )
        branch_rows.append(
            {
                "branch_id": spec.branch_id,
                "label": spec.label,
                "source_ref": _branch_source_ref(spec, record),
                "orchestration_id": _text(record.get("orchestration_id")),
                "tenant_id": _text(record.get("tenant_id")),
                "actor_id": _text(record.get("actor_id")),
                "decision_status": _text(decision.get("status")),
                "proof_state": _text(decision.get("proof_state")),
                "solver_outcome": _text(decision.get("solver_outcome")),
                "execution_allowed": bool(decision.get("execution_allowed")),
                "trace_ref": _text(record.get("trace_ref")),
                "causal_decision_trace_ref": _text(record.get("causal_decision_trace_ref")),
                "admission_receipt_ref": _text(record.get("admission_receipt_ref")),
                "closure_state": _text(record.get("closure_state")),
                "closure_receipt_ref": _closure_receipt_ref(record),
                "reconciliation_ref": _closure_reconciliation_ref(record),
                "memory_ref": _closure_memory_ref(record),
                "receipt_refs": receipt_refs,
            }
        )
    return branch_rows


def _validated_live_rehearsal_previews(
    request: PrivatePilotStoryRequest,
    admission_previews: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(admission_previews, (str, bytes)) or not isinstance(admission_previews, (tuple, list)):
        raise PrivatePilotStoryError("private pilot live rehearsal previews must be an array")
    if not admission_previews:
        raise PrivatePilotStoryError("private pilot live rehearsal requires at least one preview")
    previews: list[Mapping[str, Any]] = []
    for index, preview in enumerate(admission_previews):
        if not isinstance(preview, Mapping):
            raise PrivatePilotStoryError(f"private pilot live rehearsal preview {index} must be an object")
        for field_name in (
            "admission_preview_id",
            "case_id",
            "step_id",
            "read_only",
            "governed",
            "decision",
            "reason_code",
            "execution_authority_granted",
            "dispatch_authority_granted",
            "gate_preview",
            "handoff",
            "causal_decision_trace",
        ):
            if field_name not in preview:
                raise PrivatePilotStoryError(
                    f"private pilot live rehearsal preview missing field: {field_name}"
                )
        if preview["case_id"] != request.case_id:
            raise PrivatePilotStoryError("private pilot live rehearsal case binding changed")
        if preview["read_only"] is not True or preview["governed"] is not True:
            raise PrivatePilotStoryError("private pilot live rehearsal preview must be governed read-only")
        if preview["execution_authority_granted"] is not False:
            raise PrivatePilotStoryError("private pilot live rehearsal must not grant execution authority")
        if preview["dispatch_authority_granted"] is not False:
            raise PrivatePilotStoryError("private pilot live rehearsal must not grant dispatch authority")
        causal_trace = preview.get("causal_decision_trace")
        if not isinstance(causal_trace, Mapping):
            raise PrivatePilotStoryError("private pilot live rehearsal causal trace missing")
        tenant_id = _text(causal_trace.get("tenant"))
        if tenant_id and tenant_id != request.tenant_id:
            raise PrivatePilotStoryError("private pilot live rehearsal tenant binding changed")
        if causal_trace.get("decision") != preview["decision"]:
            raise PrivatePilotStoryError("private pilot live rehearsal decision trace mismatch")
        previews.append(preview)
    return previews


def _live_rehearsal_capability_refs(previews: list[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    for preview in previews:
        handoff = preview.get("handoff")
        if isinstance(handoff, Mapping):
            capability_id = _text(handoff.get("capability_id"))
            if capability_id:
                refs.append(f"capability://orgos/{capability_id}")
    return _unique_text(refs or ["capability://orgos/private-pilot/read-only-rehearsal"])


def _live_rehearsal_evidence_refs(previews: list[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    for preview in previews:
        preview_id = _text(preview.get("admission_preview_id"))
        if preview_id:
            refs.append(f"evidence://orgos/admission-preview/{preview_id}")
        gate_preview = preview.get("gate_preview")
        if isinstance(gate_preview, Mapping):
            preview_ref = _text(gate_preview.get("preview_id"))
            if preview_ref:
                refs.append(f"evidence://orgos/gate-preview/{preview_ref}")
            refs.extend(_text_list(gate_preview.get("evidence_refs")))
        handoff = preview.get("handoff")
        if isinstance(handoff, Mapping):
            refs.extend(_text_list(handoff.get("evidence_refs")))
    return _unique_text(refs or ["evidence://orgos/private-pilot/rehearsal"])


def _live_rehearsal_policy_refs(previews: list[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = ["policy://orgos/private-pilot/read-only-rehearsal"]
    for preview in previews:
        handoff = preview.get("handoff")
        if isinstance(handoff, Mapping):
            step_id = _text(handoff.get("step_id"))
            if step_id:
                refs.append(f"policy://orgos/plan-step/{step_id}/handoff")
    return _unique_text(refs)


def _live_rehearsal_admission_guards(
    *,
    request: PrivatePilotStoryRequest,
    previews: list[Mapping[str, Any]],
    capability_refs: list[str],
    evidence_refs: list[str],
    policy_refs: list[str],
    temporal_refs: list[str],
    admission_receipt_ref: str,
) -> list[dict[str, Any]]:
    preview_guard_values = [
        _text(
            preview.get("causal_decision_trace", {})
            .get("guard_verdicts", {})
            .get("evidence_sufficient")
        )
        for preview in previews
        if isinstance(preview.get("causal_decision_trace"), Mapping)
        and isinstance(preview["causal_decision_trace"].get("guard_verdicts"), Mapping)
    ]
    evidence_passed = all(value == "Pass" for value in preview_guard_values) and bool(preview_guard_values)
    capability_passed = all(
        _text(
            preview.get("causal_decision_trace", {})
            .get("guard_verdicts", {})
            .get("capability_certified")
        )
        in {"", "Pass", "not_required_for_read_only_preview"}
        for preview in previews
        if isinstance(preview.get("causal_decision_trace"), Mapping)
        and isinstance(preview["causal_decision_trace"].get("guard_verdicts"), Mapping)
    )
    return [
        _uao_guard("identity_valid", "passed", "Pass", "actor_identity_bound", [f"actor://{request.actor_id}"]),
        _uao_guard("tenant_valid", "passed", "Pass", "tenant_scope_resolved", [f"tenant://{request.tenant_id}"]),
        _uao_guard("authority_valid", "passed", "Pass", "orgos_preview_authority_checked", capability_refs),
        _uao_guard("policy_allows", "simulated", "Unknown", "preview_only_no_execution", policy_refs),
        _uao_guard("risk_acceptable", "passed", "Pass", "read_only_rehearsal_low_risk", policy_refs),
        _uao_guard("budget_available", "passed", "Pass", "read_only_rehearsal_budget_available", [f"budget://{request.tenant_id}/private-pilot"]),
        _uao_guard(
            "evidence_sufficient",
            "passed" if evidence_passed else "simulated",
            "Pass" if evidence_passed else "Unknown",
            "orgos_preview_evidence_checked" if evidence_passed else "orgos_preview_evidence_not_terminal",
            evidence_refs,
        ),
        _uao_guard("temporal_window_valid", "passed", "Pass", "rehearsal_window_open", temporal_refs),
        _uao_guard(
            "capability_certified",
            "passed" if capability_passed else "simulated",
            "Pass" if capability_passed else "Unknown",
            "orgos_capability_preview_checked" if capability_passed else "orgos_capability_preview_not_terminal",
            capability_refs,
        ),
        _uao_guard("recovery_available", "passed", "Pass", "read_only_no_rollback_needed", ["recovery://orgos/private-pilot/read-only-no-op"]),
        _uao_guard("receipt_emittable", "passed", "Pass", "live_rehearsal_receipt_emitted", [admission_receipt_ref]),
    ]


def _uao_stage(
    stage_id: str,
    stage_order: int,
    stage_kind: str,
    status: str,
    input_refs: list[str],
    output_refs: list[str],
    receipt_ref: str | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_order": stage_order,
        "stage_kind": stage_kind,
        "status": status,
        "input_refs": input_refs,
        "output_refs": output_refs,
        "receipt_ref": receipt_ref,
        "failure_reason": failure_reason,
    }


def _uao_guard(
    guard: str,
    verdict: str,
    proof_state: str,
    reason_code: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "guard": guard,
        "verdict": verdict,
        "proof_state": proof_state,
        "reason_code": reason_code,
        "evidence_refs": _unique_text(evidence_refs),
    }


def _uao_receipt(
    receipt_id: str,
    tier: str,
    kind: str,
    stage_id: str,
    confirms: str,
    external_state_confirmed: bool,
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "tier": tier,
        "kind": kind,
        "stage_id": stage_id,
        "confirms": confirms,
        "external_state_confirmed": external_state_confirmed,
    }


def _branch_source_ref(spec: UaoBranchSpec, record: Mapping[str, Any]) -> str:
    envelope = record.get("action_envelope")
    if isinstance(envelope, Mapping):
        action_source = _text(envelope.get("source"))
        if action_source == LIVE_REHEARSAL_ACTION_SOURCE:
            return action_source
    return spec.source_ref


def _stage_rows(
    *,
    request: PrivatePilotStoryRequest,
    uao_branches: list[dict[str, Any]],
    governor_read_model: Mapping[str, Any],
    sdlc_read_model: Mapping[str, Any],
    receipt_refs: list[str],
    causal_trace_refs: list[str],
) -> list[dict[str, Any]]:
    orgos = _orgos_refs(request)
    stage_sources: dict[str, list[str]] = {
        "orgos_request": [
            orgos["department_registry_ref"],
            orgos["authority_map_ref"],
        ],
        "uao_envelope": [branch["source_ref"] for branch in uao_branches],
        "governor_chain": [GOVERNOR_CHAIN_WORKFLOW_ID],
        "sdlc_gate": [_text(sdlc_read_model.get("dashboard_id"))],
        "receipt_closure": receipt_refs,
        "dashboard_view": _dashboard_refs(request),
    }
    stage_results: dict[str, str] = {
        "orgos_request": "tenant_scoped_read_model_refs_bound",
        "uao_envelope": "approved_blocked_and_rehearsal_branches_bound",
        "governor_chain": "valid" if governor_read_model.get("valid") is True else "blocked",
        "sdlc_gate": "ready" if sdlc_read_model.get("read_only") is True else "blocked",
        "receipt_closure": "receipt_refs_bound",
        "dashboard_view": "dashboard_refs_bound",
    }
    rows: list[dict[str, Any]] = []
    for spec in CANONICAL_PRIVATE_PILOT_STAGES:
        rows.append(
            {
                "order": spec.order,
                "stage_id": spec.stage_id,
                "stage_type": StageType.OBSERVATION.value,
                "label": spec.label,
                "responsibility": spec.responsibility,
                "input_key": "" if spec.order == 1 else PILOT_PACKET_INPUT_KEY,
                "output_key": PILOT_PACKET_OUTPUT_KEY,
                "source_refs": stage_sources[spec.stage_id],
                "result": stage_results[spec.stage_id],
                "causal_trace_ref_count": len(causal_trace_refs)
                if spec.stage_id == "receipt_closure"
                else 0,
            }
        )
    return rows


def _orgos_refs(request: PrivatePilotStoryRequest) -> dict[str, str]:
    org_base = f"/api/v1/orgs/{request.org_id}"
    case_base = f"/api/v1/cases/{request.case_id}"
    return {
        "org_id": request.org_id,
        "case_id": request.case_id,
        "department_registry_ref": f"{org_base}/department-registry",
        "department_registry_view_ref": f"{org_base}/department-registry/view",
        "authority_map_ref": f"{org_base}/authority-map",
        "authority_map_view_ref": f"{org_base}/authority-map/view",
        "case_portfolio_ref": f"{org_base}/case-portfolio",
        "case_portfolio_view_ref": f"{org_base}/case-portfolio/view",
        "case_proof_timeline_ref": f"{case_base}/proof-timeline",
    }


def _dashboard_refs(request: PrivatePilotStoryRequest) -> list[str]:
    orgos = _orgos_refs(request)
    return [
        orgos["department_registry_view_ref"],
        orgos["authority_map_view_ref"],
        orgos["case_portfolio_view_ref"],
        "/software/receipts/sdlc/dashboard",
        "/software/receipts/private-pilot/story",
        "/software/receipts/private-pilot/operator-view",
        "/software/receipts/private-pilot/operator-view/view",
    ]


def _result_refs(uao_branches: list[dict[str, Any]]) -> dict[str, str]:
    return {
        f"{branch['branch_id']}_decision_ref": f"decision://{branch['orchestration_id']}"
        for branch in uao_branches
    }


def _operator_check(
    check_id: str,
    passed: bool,
    reason_code: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "proof_state": "Pass" if passed else f"Fail({reason_code})",
        "reason_code": reason_code,
        "evidence_refs": _unique_text(evidence_refs),
    }


def _operator_timeline_item(
    order: int,
    step_id: str,
    label: str,
    status: str,
    outcome: str,
    source_refs: list[str],
    *,
    receipt_refs: list[str] | None = None,
    execution_allowed: bool = False,
    stage_count: int = 0,
) -> dict[str, Any]:
    receipts = _unique_text(receipt_refs or [])
    return {
        "order": order,
        "step_id": step_id,
        "label": label,
        "status": status,
        "outcome": outcome,
        "execution_allowed": execution_allowed,
        "stage_count": stage_count,
        "source_refs": _operator_ref_panel(source_refs, limit=6),
        "receipt_refs": _operator_ref_panel(receipts, limit=6),
    }


def _operator_ref_panel(values: list[str], *, limit: int) -> dict[str, Any]:
    refs = _unique_text(values)
    return {
        "ref_count": len(refs),
        "refs": refs[:limit],
        "truncated": len(refs) > limit,
    }


def _source_violations(
    governor_read_model: Mapping[str, Any],
    sdlc_read_model: Mapping[str, Any],
    uao_branches: list[dict[str, Any]],
) -> tuple[str, ...]:
    violations: list[str] = []
    if governor_read_model.get("valid") is not True:
        violations.append("governor chain read model is invalid")
    if governor_read_model.get("read_only") is not True:
        violations.append("governor chain must remain read-only")
    if sdlc_read_model.get("read_only") is not True:
        violations.append("SDLC dashboard must remain read-only")
    if sdlc_read_model.get("governed") is not True:
        violations.append("SDLC dashboard must remain governed")
    expected_decisions = {
        "approved": ("allow", True),
        "blocked": ("block", False),
        "rehearsal": ("simulate", False),
    }
    for branch in uao_branches:
        expected = expected_decisions.get(branch["branch_id"])
        if expected is None:
            violations.append(f"unexpected UAO branch: {branch['branch_id']}")
            continue
        if (branch["decision_status"], branch["execution_allowed"]) != expected:
            violations.append(f"UAO branch result changed: {branch['branch_id']}")
        if not branch["receipt_refs"]:
            violations.append(f"UAO branch has no receipts: {branch['branch_id']}")
    return tuple(violations)


def _expected_bindings() -> tuple[tuple[str, str, str, str, str], ...]:
    expected: list[tuple[str, str, str, str, str]] = []
    for previous_stage, next_stage in zip(
        CANONICAL_PRIVATE_PILOT_STAGES,
        CANONICAL_PRIVATE_PILOT_STAGES[1:],
    ):
        expected.append(
            (
                f"{previous_stage.stage_id}_to_{next_stage.stage_id}",
                previous_stage.stage_id,
                PILOT_PACKET_OUTPUT_KEY,
                next_stage.stage_id,
                PILOT_PACKET_INPUT_KEY,
            )
        )
    return tuple(expected)


def _closure_receipt_ref(record: Mapping[str, Any]) -> str:
    closure = record.get("closure")
    if not isinstance(closure, Mapping):
        return ""
    return _text(closure.get("closure_receipt_ref"))


def _closure_reconciliation_ref(record: Mapping[str, Any]) -> str:
    closure = record.get("closure")
    if not isinstance(closure, Mapping):
        return ""
    return _text(closure.get("reconciliation_ref"))


def _closure_memory_ref(record: Mapping[str, Any]) -> str:
    closure = record.get("closure")
    if not isinstance(closure, Mapping):
        return ""
    return _text(closure.get("memory_ref"))


def _unique_text(values: Any) -> list[str]:
    observed: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in observed:
            continue
        observed.add(text)
        result.append(text)
    return result


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]
