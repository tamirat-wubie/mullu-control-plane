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
                "source_ref": spec.source_ref,
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
                "receipt_refs": receipt_refs,
            }
        )
    return branch_rows


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
    ]


def _result_refs(uao_branches: list[dict[str, Any]]) -> dict[str, str]:
    return {
        f"{branch['branch_id']}_decision_ref": f"decision://{branch['orchestration_id']}"
        for branch in uao_branches
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
