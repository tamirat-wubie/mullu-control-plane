"""
Logistics / Supply Chain Domain Adapter.

Translates logistics actions (order fulfillment, dispatch, route
planning, carrier handoff, customs clearance, delivery, inventory
transfer, return processing, inspection, warehouse receipt) into the
universal causal framework. Distinct shape:

  - Authority chain: responsible dispatcher + sequential carrier
    chain. CUSTOMS, hazmat authority, and cold-chain monitor are
    observer-shaped requirements that do not slot into the same
    handoff hierarchy.
  - Constraints carry acceptance criteria, customs requirements (HS
    codes), hazmat compliance, chain-of-custody integrity, and
    cold-chain monitoring — each with different violation_response
    (block / escalate). Hazmat and cold-chain are first-class
    physical constraints, not just paperwork.
  - Many actions are structurally irreversible after the act-of-
    handoff or act-of-clearance occurs (shipment_dispatch,
    carrier_handoff, customs_clearance, delivery, inventory_transfer).
    Planning/processing actions remain reversible.
  - Risk flags surface hazmat without authority, missing HS codes on
    international shipments, broken chain of custody, cold-chain
    breach risk, and systemic blast radius (lane / network impact).

This adapter intentionally does NOT model carrier rate sheets, customs
duty calculation, or specific hazmat regulation lookups — it models
the governance shape, and leaves jurisdiction-specific rules (IATA,
IMDG, ADR, FMCSA, Incoterms) to the calling system.
"""
from __future__ import annotations

from dataclasses import dataclass
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


class LogisticsActionKind(Enum):
    ORDER_FULFILLMENT = "order_fulfillment"
    SHIPMENT_DISPATCH = "shipment_dispatch"
    ROUTE_ASSIGNMENT = "route_assignment"
    CARRIER_HANDOFF = "carrier_handoff"
    CUSTOMS_CLEARANCE = "customs_clearance"
    DELIVERY = "delivery"
    INVENTORY_TRANSFER = "inventory_transfer"
    RETURN_PROCESSING = "return_processing"
    INSPECTION = "inspection"
    WAREHOUSE_RECEIPT = "warehouse_receipt"


@dataclass
class LogisticsRequest:
    kind: LogisticsActionKind
    summary: str
    shipment_id: str
    responsible_dispatcher: str
    carrier_chain: tuple[str, ...] = ()  # ordered handoff sequence
    shipper: str = ""
    consignee: str = ""
    origin: str = ""  # ISO 3166-1 alpha-2 e.g. "US"
    destination: str = ""  # ISO 3166-1 alpha-2 e.g. "DE"
    modes: tuple[str, ...] = ()  # subset of {"air","sea","road","rail"}
    hazmat_class: str = ""  # "" or e.g. "Class 3 Flammable"
    temperature_controlled: bool = False
    customs_required: bool = False
    hs_codes: tuple[str, ...] = ()  # Harmonized System codes
    affected_skus: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    chain_of_custody_intact: bool = True
    is_expedited: bool = False  # time-critical / emergency
    blast_radius: str = "shipment"  # shipment | lane | network | systemic


@dataclass
class LogisticsResult:
    fulfillment_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    chain_of_custody_intact: bool
    is_expedited: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


_VALID_MODES = frozenset({"air", "sea", "road", "rail"})


def translate_to_universal(req: LogisticsRequest) -> UniversalRequest:
    bad_modes = [m for m in req.modes if m not in _VALID_MODES]
    if bad_modes:
        raise ValueError(
            f"unknown transport mode(s) {bad_modes!r}; valid: "
            f"{sorted(_VALID_MODES)}"
        )
    if req.origin and len(req.origin) != 2:
        raise ValueError(
            f"origin {req.origin!r} must be ISO 3166-1 alpha-2 (2-letter) or empty"
        )
    if req.destination and len(req.destination) != 2:
        raise ValueError(
            f"destination {req.destination!r} must be ISO 3166-1 alpha-2 or empty"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "logistics_state",
        "shipment_id": req.shipment_id,
        "phase": "pre_action",
        "responsible_dispatcher": req.responsible_dispatcher,
        "shipper": req.shipper,
        "consignee": req.consignee,
        "origin": req.origin,
        "destination": req.destination,
    }
    target_state = {
        "kind": "logistics_state",
        "shipment_id": req.shipment_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "chain_of_custody_intact": req.chain_of_custody_intact,
    }
    boundary = {
        "inside_predicate": (
            f"shipment_id = {req.shipment_id} ∧ "
            f"skus ⊆ {{{', '.join(req.affected_skus)}}}"
        ),
        "interface_points": list(req.affected_skus),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "logistics_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Customs requirement — international shipments need HS codes.
    # Missing HS codes blocks; hazmat without HS codes also blocks
    # (regulators require classification).
    if req.customs_required and not req.hs_codes:
        constraints.append(
            {
                "domain": "customs",
                "restriction": "hs_codes_required_for_clearance",
                "violation_response": "block",
            }
        )

    # Hazmat compliance — escalate to hazmat authority. Each shipment
    # with hazmat class gets a single hazmat constraint (not per-SKU).
    if req.hazmat_class:
        constraints.append(
            {
                "domain": "hazmat",
                "restriction": f"hazmat_compliance:{req.hazmat_class}",
                "violation_response": "escalate",
            }
        )

    # Chain of custody — hard block when broken on hazmat or cold
    # chain (compliance- or safety-critical), warn otherwise.
    if not req.chain_of_custody_intact:
        coc_response = (
            "block"
            if (req.hazmat_class or req.temperature_controlled)
            else "warn"
        )
        constraints.append(
            {
                "domain": "chain_of_custody",
                "restriction": "custody_unbroken_through_handoff",
                "violation_response": coc_response,
            }
        )

    # Cold chain — temperature-controlled shipments require continuous
    # monitoring. This is modeled as an escalation; the observer entry
    # records the monitor's presence.
    if req.temperature_controlled:
        constraints.append(
            {
                "domain": "cold_chain",
                "restriction": "continuous_temperature_monitoring",
                "violation_response": "escalate",
            }
        )

    authority = (
        f"dispatcher:{req.responsible_dispatcher}",
    ) + tuple(f"carrier:{c}" for c in req.carrier_chain)

    observer: tuple[str, ...] = ("shipment_log",)
    if req.shipper:
        observer = observer + (f"shipper:{req.shipper}",)
    if req.consignee:
        observer = observer + (f"consignee:{req.consignee}",)
    if req.origin:
        observer = observer + (f"origin:{req.origin}",)
    if req.destination:
        observer = observer + (f"destination:{req.destination}",)
    if req.customs_required:
        observer = observer + ("customs_authority",)
    if req.hazmat_class:
        observer = observer + ("hazmat_authority",)
    if req.temperature_controlled:
        observer = observer + ("cold_chain_monitor",)
    if req.chain_of_custody_intact:
        observer = observer + ("chain_of_custody_attestation",)

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
    original_request: LogisticsRequest,
) -> LogisticsResult:
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
        [f"dispatcher: {original_request.responsible_dispatcher}"]
        + [f"carrier: {c}" for c in original_request.carrier_chain]
    )

    return LogisticsResult(
        fulfillment_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        chain_of_custody_intact=original_request.chain_of_custody_intact,
        is_expedited=original_request.is_expedited,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: LogisticsRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "logistics_action",
    }


def run_with_ucja(
    req: LogisticsRequest,
    *,
    capture: list | None = None,
) -> LogisticsResult:
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
        causation_mechanism="logistics_action",
        causation_strength=0.95,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.96,
        observation_sensor="shipment_telemetry",
        observation_signal="in_motion" if req.kind in (
            LogisticsActionKind.SHIPMENT_DISPATCH,
            LogisticsActionKind.CARRIER_HANDOFF,
        ) else "stationary",
        observation_confidence=0.98,
        inference_rule="incoterms_or_carrier_contract",
        inference_certainty=0.92,
        inference_kind="deductive",  # contract terms apply mechanically
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "chain_of_custody_intact",
        ),
        decision_justification=(
            f"logistics action {req.kind.value} for shipment {req.shipment_id} "
            f"{req.origin}→{req.destination}".strip().rstrip("→")
        ),
        execution_plan_prefix=f"execute {req.kind.value} for shipment {req.shipment_id}",
        execution_resources=tuple(req.affected_skus),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: LogisticsActionKind, summary: str) -> str:
    verb_map = {
        LogisticsActionKind.ORDER_FULFILLMENT:  "assemble_order_for_dispatch",
        LogisticsActionKind.SHIPMENT_DISPATCH:  "release_shipment_into_transit",
        LogisticsActionKind.ROUTE_ASSIGNMENT:   "select_transit_path",
        LogisticsActionKind.CARRIER_HANDOFF:    "transfer_custody_between_carriers",
        LogisticsActionKind.CUSTOMS_CLEARANCE:  "obtain_border_release",
        LogisticsActionKind.DELIVERY:           "transfer_custody_to_consignee",
        LogisticsActionKind.INVENTORY_TRANSFER: "move_stock_between_locations",
        LogisticsActionKind.RETURN_PROCESSING:  "reverse_logistics_intake",
        LogisticsActionKind.INSPECTION:         "verify_shipment_integrity",
        LogisticsActionKind.WAREHOUSE_RECEIPT:  "accept_inbound_into_warehouse",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "shipment": "closed",
        "lane":     "selective",
        "network":  "selective",
        "systemic": "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: LogisticsActionKind) -> str:
    if kind in (
        LogisticsActionKind.SHIPMENT_DISPATCH,
        LogisticsActionKind.CARRIER_HANDOFF,
        LogisticsActionKind.CUSTOMS_CLEARANCE,
        LogisticsActionKind.DELIVERY,
        LogisticsActionKind.INVENTORY_TRANSFER,
    ):
        return "irreversible"
    if kind in (
        LogisticsActionKind.ORDER_FULFILLMENT,
        LogisticsActionKind.ROUTE_ASSIGNMENT,
        LogisticsActionKind.RETURN_PROCESSING,
        LogisticsActionKind.INSPECTION,
        LogisticsActionKind.WAREHOUSE_RECEIPT,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: LogisticsRequest) -> tuple[str, ...]:
    refs: list[str] = ["shipment_record"]
    if req.customs_required:
        refs.append("customs_declaration")
    if req.hazmat_class:
        refs.append("hazmat_dangerous_goods_declaration")
    if req.temperature_controlled:
        refs.append("temperature_log")
    if req.chain_of_custody_intact:
        refs.append("custody_signatures")
    if req.kind == LogisticsActionKind.DELIVERY:
        refs.append("proof_of_delivery")
    if req.kind == LogisticsActionKind.INSPECTION:
        refs.append("inspection_report")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: LogisticsRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial state for shipment {req.shipment_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply Incoterms / carrier contract to handoff")
    if summary.get("decision", 0) > 0:
        steps.append("Decide whether to proceed with the logistics action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.customs_required:
        if req.hs_codes:
            steps.append(
                f"File customs declaration with HS codes "
                f"({', '.join(req.hs_codes)})"
            )
        else:
            steps.append("Block: customs required but HS codes missing")
    if req.hazmat_class:
        steps.append(
            f"Hazmat clearance: {req.hazmat_class} — file dangerous-goods "
            "declaration"
        )
    if req.temperature_controlled:
        steps.append("Verify cold-chain monitor readings continuous")
    if not req.chain_of_custody_intact:
        steps.append(
            "Investigate chain-of-custody break before proceeding"
        )
    for c in req.carrier_chain:
        steps.append(f"Carrier handoff signoff: {c}")
    if summary.get("validation", 0) > 0:
        steps.append("Validate against acceptance criteria")
    if req.kind == LogisticsActionKind.SHIPMENT_DISPATCH:
        steps.append("Release shipment to first-mile carrier")
    elif req.kind == LogisticsActionKind.CUSTOMS_CLEARANCE:
        steps.append("Obtain release entry and update tracking")
    elif req.kind == LogisticsActionKind.DELIVERY:
        steps.append("Capture proof-of-delivery signature")
    elif req.kind == LogisticsActionKind.RETURN_PROCESSING:
        steps.append("Issue RMA and route to returns warehouse")
    elif req.kind == LogisticsActionKind.WAREHOUSE_RECEIPT:
        steps.append("Reconcile inbound against PO and update WMS")
    if summary.get("execution", 0) > 0:
        steps.append("Persist event to immutable shipment ledger")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: LogisticsRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("logistics_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.customs_required and not req.hs_codes:
        flags.append(
            "customs_required_without_hs_codes — block until classification "
            "filed"
        )
    if req.hazmat_class:
        flags.append(
            f"hazmat_present ({req.hazmat_class}) — verify carrier "
            "certification and labeling"
        )
    if req.temperature_controlled and not req.chain_of_custody_intact:
        flags.append(
            "cold_chain_with_broken_custody — quality may be compromised"
        )
    if not req.chain_of_custody_intact:
        flags.append(
            "chain_of_custody_broken — investigate before further handoff"
        )
    if req.is_expedited:
        flags.append(
            "expedited_mode — verify time-critical justification and "
            "carrier availability"
        )
    if (
        req.kind == LogisticsActionKind.SHIPMENT_DISPATCH
        and not req.carrier_chain
    ):
        flags.append(
            "shipment_dispatch_without_carrier_chain — verify carrier "
            "selection"
        )
    if req.blast_radius == "systemic":
        flags.append(
            "systemic_blast_radius — affects lane / network capacity"
        )
    if req.kind in (
        LogisticsActionKind.SHIPMENT_DISPATCH,
        LogisticsActionKind.CARRIER_HANDOFF,
        LogisticsActionKind.CUSTOMS_CLEARANCE,
        LogisticsActionKind.DELIVERY,
        LogisticsActionKind.INVENTORY_TRANSFER,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before execution"
        )
    if (
        req.origin
        and req.destination
        and req.origin != req.destination
        and not req.customs_required
    ):
        flags.append(
            f"international_shipment_{req.origin}_to_{req.destination}_without_"
            "customs_required — verify customs scope"
        )
    return tuple(flags)
