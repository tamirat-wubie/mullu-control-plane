"""
Energy / Utilities Domain Adapter.

Translates energy operations (generation dispatch, load curtailment,
outage response, maintenance windows, interconnection requests, rate
filings, emergency demand response, meter validation, carbon
reporting, grid reconfiguration) into the universal causal framework.
Distinct shape:

  - Authority chain: control-room operator + approver chain (system
    operator + reliability coordinator). The BALANCING_AUTHORITY,
    regulators (FERC/NERC/state PUC), and reliability coordinator are
    observer-shaped requirements — bulk-power-system reliability
    governance rides as observation, not authorization.
  - Constraints carry acceptance criteria, N-1 contingency
    (deterministic reliability standard), reliability-critical bulk
    impact, and regulatory-regime requirements — each with different
    violation_response. N-1 is a hard block UNLESS declared emergency,
    where it relaxes to escalate (operator may take temporary
    risk on grid).
  - Many actions are physically irreversible once committed
    (generation_dispatch, load_curtailment, grid_reconfiguration,
    outage_response, emergency_demand_response). Planning and
    reporting actions remain reversible.
  - Risk flags surface N-1 violations, reliability-critical actions
    without RC engagement, missing regulatory regime tags, and
    interconnect-level blast radius.

This adapter intentionally does NOT model power flow, market clearing,
or specific NERC standards — it models the governance shape, and
leaves jurisdiction-specific rules (NERC TPL/EOP/CIP, FERC OATT,
state RPS) to the calling system.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from mcoi_runtime.domain_adapters._cycle_helpers import (
    StepOverrides,
    run_default_cycle,
)
from mcoi_runtime.domain_adapters.software_dev import (
    UniversalRequest,
    UniversalResult,
)


class EnergyActionKind(Enum):
    GENERATION_DISPATCH = "generation_dispatch"
    LOAD_CURTAILMENT = "load_curtailment"
    OUTAGE_RESPONSE = "outage_response"
    MAINTENANCE_WINDOW = "maintenance_window"
    INTERCONNECTION_REQUEST = "interconnection_request"
    RATE_FILING = "rate_filing"
    EMERGENCY_DEMAND_RESPONSE = "emergency_demand_response"
    METER_DATA_VALIDATION = "meter_data_validation"
    CARBON_REPORTING = "carbon_reporting"
    GRID_RECONFIGURATION = "grid_reconfiguration"


@dataclass
class EnergyRequest:
    kind: EnergyActionKind
    summary: str
    operation_id: str
    responsible_operator: str
    approver_chain: tuple[str, ...] = ()
    balancing_authority: str = ""  # e.g. "CAISO", "MISO", "PJM", "ERCOT"
    service_territory: str = ""  # utility name
    jurisdiction: str = ""  # "FERC" | "NERC" | "US-CA-PUC" | etc.
    regulatory_regime: tuple[str, ...] = ()  # e.g. ("NERC_CIP","FERC_OATT")
    affected_assets: tuple[str, ...] = ()  # generators/lines/substations
    megawatts: Decimal = Decimal("0")  # signed: + generation, - load
    acceptance_criteria: tuple[str, ...] = ()
    reliability_critical: bool = False  # affects bulk power system
    n_minus_1_compliant: bool = True  # contingency analysis pass
    is_emergency: bool = False  # declared emergency operating state
    blast_radius: str = "asset"  # asset | feeder | balancing_area | interconnect


@dataclass
class EnergyResult:
    operating_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    n_minus_1_compliant: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


_RELIABILITY_KINDS = (
    EnergyActionKind.GENERATION_DISPATCH,
    EnergyActionKind.LOAD_CURTAILMENT,
    EnergyActionKind.OUTAGE_RESPONSE,
    EnergyActionKind.GRID_RECONFIGURATION,
    EnergyActionKind.EMERGENCY_DEMAND_RESPONSE,
)


def translate_to_universal(req: EnergyRequest) -> UniversalRequest:
    if req.reliability_critical and not req.balancing_authority:
        raise ValueError(
            f"reliability-critical action {req.kind.value!r} requires "
            "a balancing_authority"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "energy_state",
        "operation_id": req.operation_id,
        "phase": "pre_action",
        "responsible_operator": req.responsible_operator,
        "balancing_authority": req.balancing_authority,
        "assets": list(req.affected_assets),
    }
    target_state = {
        "kind": "energy_state",
        "operation_id": req.operation_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "n_minus_1_compliant": req.n_minus_1_compliant,
    }
    boundary = {
        "inside_predicate": (
            f"operation_id = {req.operation_id} ∧ "
            f"assets ⊆ {{{', '.join(req.affected_assets)}}}"
        ),
        "interface_points": list(req.affected_assets),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "energy_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # N-1 contingency — NERC mandates the system survive any single
    # element loss. Hard block on reliability-critical actions when
    # not satisfied, UNLESS declared emergency where the operator
    # may take temporary risk to maintain service.
    if (
        req.reliability_critical
        and not req.n_minus_1_compliant
    ):
        n1_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "n_minus_1",
                "restriction": "single_contingency_compliant",
                "violation_response": n1_response,
            }
        )

    # Reliability-critical actions on the bulk system must engage
    # the reliability coordinator — modeled as escalation if RC
    # isn't in the approver chain (we infer presence from observer
    # entries, not authority — RC is a witness, not an authorizer).
    # The constraint here is "RC engagement"; the observer entry
    # records the actual presence.
    if req.reliability_critical and req.kind in _RELIABILITY_KINDS:
        constraints.append(
            {
                "domain": "rc_engagement",
                "restriction": "reliability_coordinator_engaged",
                "violation_response": "escalate",
            }
        )

    # Regulatory regime requirements — each regime becomes its own
    # escalation requiring regulator-shaped observation.
    for regime in req.regulatory_regime:
        constraints.append(
            {
                "domain": "regulatory",
                "restriction": f"compliance_with:{regime}",
                "violation_response": "escalate",
            }
        )

    authority = (
        f"operator:{req.responsible_operator}",
    ) + tuple(f"approver:{a}" for a in req.approver_chain)

    observer: tuple[str, ...] = ("control_room_log",)
    if req.balancing_authority:
        observer = observer + (f"balancing_authority:{req.balancing_authority}",)
    if req.service_territory:
        observer = observer + (f"territory:{req.service_territory}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    for regime in req.regulatory_regime:
        observer = observer + (f"regulator:{regime}",)
    if req.reliability_critical:
        observer = observer + ("reliability_coordinator",)

    return UniversalRequest(
        purpose_statement=purpose,
        initial_state_descriptor=initial_state,
        target_state_descriptor=target_state,
        boundary_specification=boundary,
        constraint_set=tuple(constraints),
        authority_required=authority,
        observer_required=observer,
    )


def translate_from_universal(
    universal_result: UniversalResult,
    original_request: EnergyRequest,
) -> EnergyResult:
    protocol = _protocol_from_constructs(
        universal_result.construct_graph_summary,
        original_request,
    )
    risk_flags = _risk_flags_from_result(universal_result, original_request)
    governance_status = (
        "approved"
        if universal_result.proof_state == "Pass"
        else f"blocked: {universal_result.proof_state}"
    )

    signoffs = tuple(
        [f"operator: {original_request.responsible_operator}"]
        + [f"approver: {a}" for a in original_request.approver_chain]
    )

    return EnergyResult(
        operating_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        n_minus_1_compliant=original_request.n_minus_1_compliant,
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: EnergyRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "energy_action",
    }


def run_with_ucja(
    req: EnergyRequest,
    *,
    capture: list | None = None,
) -> EnergyResult:
    from mcoi_runtime.ucja import UCJAPipeline

    payload = _request_to_ucja_payload(req)
    outcome = UCJAPipeline().run(payload)

    if not outcome.accepted:
        proof_state = "Fail" if outcome.rejected else "Unknown"
        rejected = (
            {"layer": outcome.halted_at_layer, "reason": outcome.reason},
        )
        universal_result = UniversalResult(
            job_definition_id=outcome.draft.job_id,
            construct_graph_summary={},
            cognitive_cycles_run=0,
            converged=False,
            proof_state=proof_state,
            rejected_deltas=rejected,
        )
        return translate_from_universal(universal_result, req)

    universal_req = translate_to_universal(req)
    overrides = StepOverrides(
        causation_mechanism="energy_action",
        causation_strength=0.97,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.97,
        observation_sensor="scada_telemetry",
        observation_signal="setpoint_committed",
        observation_confidence=0.99,
        inference_rule="reliability_standard",
        inference_certainty=0.95,
        inference_kind="deductive",  # standards apply mechanically
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "n_minus_1_or_emergency",
        ),
        decision_justification=(
            f"energy action {req.kind.value} for op {req.operation_id} "
            f"on {req.balancing_authority or 'unspecified BA'} "
            f"({'emergency' if req.is_emergency else 'normal'} state)"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for op {req.operation_id}",
        execution_resources=tuple(req.affected_assets),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: EnergyActionKind, summary: str) -> str:
    verb_map = {
        EnergyActionKind.GENERATION_DISPATCH:        "commit_generation_setpoint",
        EnergyActionKind.LOAD_CURTAILMENT:           "shed_load_to_balance_grid",
        EnergyActionKind.OUTAGE_RESPONSE:            "restore_service_to_loads",
        EnergyActionKind.MAINTENANCE_WINDOW:         "schedule_asset_out_of_service",
        EnergyActionKind.INTERCONNECTION_REQUEST:    "evaluate_new_resource_connection",
        EnergyActionKind.RATE_FILING:                "petition_regulator_for_tariff",
        EnergyActionKind.EMERGENCY_DEMAND_RESPONSE:  "invoke_emergency_load_relief",
        EnergyActionKind.METER_DATA_VALIDATION:      "verify_meter_data_for_settlement",
        EnergyActionKind.CARBON_REPORTING:           "report_emissions_to_registry",
        EnergyActionKind.GRID_RECONFIGURATION:       "alter_topology_for_operating_state",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "asset":           "closed",
        "feeder":          "selective",
        "balancing_area":  "selective",
        "interconnect":    "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: EnergyActionKind) -> str:
    if kind in (
        EnergyActionKind.GENERATION_DISPATCH,
        EnergyActionKind.LOAD_CURTAILMENT,
        EnergyActionKind.OUTAGE_RESPONSE,
        EnergyActionKind.GRID_RECONFIGURATION,
        EnergyActionKind.EMERGENCY_DEMAND_RESPONSE,
    ):
        return "irreversible"  # physical commit
    if kind in (
        EnergyActionKind.MAINTENANCE_WINDOW,
        EnergyActionKind.INTERCONNECTION_REQUEST,
        EnergyActionKind.RATE_FILING,
        EnergyActionKind.METER_DATA_VALIDATION,
        EnergyActionKind.CARBON_REPORTING,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: EnergyRequest) -> tuple[str, ...]:
    refs: list[str] = ["scada_log"]
    if req.reliability_critical:
        refs.append("contingency_analysis_report")
    if req.kind == EnergyActionKind.METER_DATA_VALIDATION:
        refs.append("meter_data_set")
    if req.kind == EnergyActionKind.CARBON_REPORTING:
        refs.append("emissions_inventory")
    if req.kind == EnergyActionKind.RATE_FILING:
        refs.append("cost_of_service_study")
    if req.is_emergency:
        refs.append("emergency_declaration")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: EnergyRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial grid state for op {req.operation_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply reliability standards to current operating state")
    if summary.get("decision", 0) > 0:
        steps.append("Decide on energy action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.reliability_critical:
        if req.n_minus_1_compliant:
            steps.append("Confirm N-1 contingency analysis on file")
        elif req.is_emergency:
            steps.append("Document emergency operating state and N-1 deviation")
        else:
            steps.append("Block: N-1 not satisfied and not in emergency state")
        steps.append("Coordinate with reliability coordinator")
    for a in req.approver_chain:
        steps.append(f"Approver signoff: {a}")
    if summary.get("validation", 0) > 0:
        steps.append("Validate against acceptance criteria")
    if req.kind == EnergyActionKind.GENERATION_DISPATCH:
        steps.append("Issue setpoint to generator and confirm response")
    elif req.kind == EnergyActionKind.LOAD_CURTAILMENT:
        steps.append("Notify affected customers and shed load")
    elif req.kind == EnergyActionKind.OUTAGE_RESPONSE:
        steps.append("Dispatch crews and restore service in priority order")
    elif req.kind == EnergyActionKind.GRID_RECONFIGURATION:
        steps.append("Open/close switching devices per plan")
    elif req.kind == EnergyActionKind.EMERGENCY_DEMAND_RESPONSE:
        steps.append("Invoke EDR contracts and broadcast public appeal")
    elif req.kind == EnergyActionKind.RATE_FILING:
        steps.append("Submit filing to regulatory commission")
    elif req.kind == EnergyActionKind.CARBON_REPORTING:
        steps.append("Submit emissions report to registry")
    if summary.get("execution", 0) > 0:
        steps.append("Persist event to operating log and settlement record")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: EnergyRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("reliability_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.reliability_critical and not req.n_minus_1_compliant:
        if req.is_emergency:
            flags.append(
                "n_minus_1_violation_under_emergency — operator is taking "
                "temporary risk; document factual predicate"
            )
        else:
            flags.append(
                "n_minus_1_violation_non_emergency — block until contingency "
                "analysis passes or emergency declared"
            )
    if req.is_emergency:
        flags.append(
            "emergency_operating_state — verify declaration and notify "
            "reliability coordinator"
        )
    if req.reliability_critical and req.kind in _RELIABILITY_KINDS:
        flags.append(
            f"reliability_critical_{req.kind.value} — RC engagement "
            "required"
        )
    if (
        req.kind in (
            EnergyActionKind.RATE_FILING,
            EnergyActionKind.CARBON_REPORTING,
        )
        and not req.regulatory_regime
    ):
        flags.append(
            f"{req.kind.value}_without_regulatory_regime — verify filing "
            "venue"
        )
    if req.blast_radius == "interconnect":
        flags.append(
            "interconnect_blast_radius — affects multiple balancing areas"
        )
    if req.kind in (
        EnergyActionKind.GENERATION_DISPATCH,
        EnergyActionKind.LOAD_CURTAILMENT,
        EnergyActionKind.OUTAGE_RESPONSE,
        EnergyActionKind.GRID_RECONFIGURATION,
        EnergyActionKind.EMERGENCY_DEMAND_RESPONSE,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — physical commit; confirm "
            "before execution"
        )
    return tuple(flags)
