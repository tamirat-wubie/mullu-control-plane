"""
Finance Domain Adapter.

Translates financial actions (transactions, trades, reconciliation,
KYC/AML, audit review, regulatory disclosure) into the universal causal
framework. Distinct shape:

  - Authority chain: responsible officer + maker/checker approver chain;
    REGULATOR is a separate authority-shaped requirement that does not
    slot into the same approval hierarchy.
  - Constraints carry acceptance criteria, dual-control requirements,
    AML/sanctions flags, and high-value thresholds — each with different
    violation_response (block / escalate / warn).
  - Many actions are structurally irreversible after settlement
    (wire_transfer, trade settlement, ledger adjustment, regulatory
    disclosure once filed). RECONCILIATION and CREDIT_DECISION are the
    primary reversible actions.
  - Risk flags surface AML/sanctions hits, missing dual control,
    high-value thresholds, jurisdictional regime conflicts, and
    cross-book blast radius.

This adapter intentionally does NOT model account-level ledger math or
codify specific regulatory thresholds — it models the governance shape,
and leaves domain-specific rules (FINCEN limits, OFAC lists, SOX
controls) to the calling system. The acceptance_criteria list is where
domain-specific financial rules are encoded.
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


class FinancialActionKind(Enum):
    TRANSACTION = "transaction"
    WIRE_TRANSFER = "wire_transfer"
    TRADE = "trade"
    SETTLEMENT = "settlement"
    RECONCILIATION = "reconciliation"
    LEDGER_ADJUSTMENT = "ledger_adjustment"
    KYC_AML_CHECK = "kyc_aml_check"
    CREDIT_DECISION = "credit_decision"
    AUDIT_REVIEW = "audit_review"
    DISCLOSURE = "disclosure"


@dataclass
class FinancialRequest:
    kind: FinancialActionKind
    summary: str
    transaction_id: str
    responsible_officer: str
    approver_chain: tuple[str, ...] = ()
    counterparty: str = ""
    amount: Decimal = Decimal("0")
    currency: str = ""  # ISO 4217 e.g. "USD", "EUR", "" if N/A
    jurisdiction: str = ""  # e.g. "US", "EU", "UK"
    regulatory_regime: tuple[str, ...] = ()  # e.g. ("SOX","BASEL_III","MIFID_II")
    affected_accounts: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    aml_flags: tuple[str, ...] = ()  # known AML/sanctions hits
    requires_dual_control: bool = False
    dual_control_satisfied: bool = False
    is_high_value: bool = False  # above reporting threshold
    blast_radius: str = "transaction"  # transaction | account | book | systemic


@dataclass
class FinancialResult:
    settlement_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    dual_control_satisfied: bool
    is_high_value: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: FinancialRequest) -> UniversalRequest:
    if req.currency and len(req.currency) != 3:
        raise ValueError(
            f"currency {req.currency!r} must be ISO 4217 (3-letter) or empty"
        )
    if req.amount < 0:
        raise ValueError(f"amount {req.amount!r} must be non-negative")

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "financial_state",
        "transaction_id": req.transaction_id,
        "phase": "pre_action",
        "responsible_officer": req.responsible_officer,
        "accounts": list(req.affected_accounts),
        "counterparty": req.counterparty,
    }
    target_state = {
        "kind": "financial_state",
        "transaction_id": req.transaction_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "dual_control_satisfied": req.dual_control_satisfied,
    }
    boundary = {
        "inside_predicate": (
            f"transaction_id = {req.transaction_id} ∧ "
            f"accounts ⊆ {{{', '.join(req.affected_accounts)}}}"
        ),
        "interface_points": list(req.affected_accounts),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "financial_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Dual-control constraint.
    # If required but not satisfied → block (cannot post a four-eyes
    # transaction with one set of eyes). If required and satisfied,
    # no constraint is added (the observer records it instead).
    if req.requires_dual_control and not req.dual_control_satisfied:
        constraints.append(
            {
                "domain": "dual_control",
                "restriction": "maker_checker_signoff_required",
                "violation_response": "block",
            }
        )

    # AML/sanctions flags — each flag becomes an escalation. These
    # don't auto-block (compliance officer adjudicates), but they
    # must be cleared before settlement.
    for flag in req.aml_flags:
        constraints.append(
            {
                "domain": "aml_sanctions",
                "restriction": f"clear_flag:{flag}",
                "violation_response": "escalate",
            }
        )

    # High-value threshold for transfers/trades — escalates to
    # senior approver, doesn't block.
    if req.is_high_value and req.kind in (
        FinancialActionKind.WIRE_TRANSFER,
        FinancialActionKind.TRADE,
        FinancialActionKind.TRANSACTION,
    ):
        constraints.append(
            {
                "domain": "threshold",
                "restriction": "high_value_requires_senior_approval",
                "violation_response": "escalate",
            }
        )

    # Authority: responsible officer + approver chain. Regulators are
    # recorded separately as observer requirements.
    authority = (
        f"officer:{req.responsible_officer}",
    ) + tuple(f"approver:{a}" for a in req.approver_chain)

    observer: tuple[str, ...] = ("transaction_journal_audit",)
    for regime in req.regulatory_regime:
        observer = observer + (f"regulator:{regime}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    if req.requires_dual_control and req.dual_control_satisfied:
        observer = observer + ("maker_checker_attestation",)

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
    original_request: FinancialRequest,
) -> FinancialResult:
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
        [f"officer: {original_request.responsible_officer}"]
        + [f"approver: {a}" for a in original_request.approver_chain]
    )

    return FinancialResult(
        settlement_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        dual_control_satisfied=original_request.dual_control_satisfied,
        is_high_value=original_request.is_high_value,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: FinancialRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "financial_action",
    }


def run_with_ucja(
    req: FinancialRequest,
    *,
    capture: list | None = None,
) -> FinancialResult:
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
        causation_mechanism="financial_action",
        causation_strength=0.95,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.97,
        observation_sensor="ledger_observation",
        observation_signal="posted",
        observation_confidence=0.99,
        inference_rule="accounting_rule",
        inference_certainty=0.95,
        inference_kind="deductive",  # accounting follows formal rules
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "dual_control_or_not_required",
        ),
        decision_justification=(
            f"financial action {req.kind.value} for {req.transaction_id} "
            f"{'with maker-checker signoff' if req.dual_control_satisfied else 'under single-officer authority'}"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for transaction {req.transaction_id}",
        execution_resources=tuple(req.affected_accounts),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: FinancialActionKind, summary: str) -> str:
    verb_map = {
        FinancialActionKind.TRANSACTION:       "post_monetary_transaction",
        FinancialActionKind.WIRE_TRANSFER:     "execute_irrevocable_funds_transfer",
        FinancialActionKind.TRADE:             "execute_security_trade",
        FinancialActionKind.SETTLEMENT:        "settle_outstanding_obligation",
        FinancialActionKind.RECONCILIATION:    "reconcile_account_position",
        FinancialActionKind.LEDGER_ADJUSTMENT: "post_ledger_correction",
        FinancialActionKind.KYC_AML_CHECK:     "screen_party_against_compliance_lists",
        FinancialActionKind.CREDIT_DECISION:   "ascribe_creditworthiness_to_party",
        FinancialActionKind.AUDIT_REVIEW:      "verify_control_evidence",
        FinancialActionKind.DISCLOSURE:        "file_regulatory_disclosure",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "transaction": "closed",
        "account":     "selective",
        "book":        "selective",
        "systemic":    "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: FinancialActionKind) -> str:
    if kind in (
        FinancialActionKind.WIRE_TRANSFER,
        FinancialActionKind.TRADE,
        FinancialActionKind.SETTLEMENT,
        FinancialActionKind.LEDGER_ADJUSTMENT,
        FinancialActionKind.DISCLOSURE,
    ):
        return "irreversible"
    if kind in (
        FinancialActionKind.RECONCILIATION,
        FinancialActionKind.CREDIT_DECISION,
        FinancialActionKind.AUDIT_REVIEW,
        FinancialActionKind.KYC_AML_CHECK,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: FinancialRequest) -> tuple[str, ...]:
    refs: list[str] = ["ledger_entry"]
    if req.requires_dual_control and req.dual_control_satisfied:
        refs.append("maker_checker_signature")
    if req.kind == FinancialActionKind.KYC_AML_CHECK:
        refs.append("compliance_screening_report")
    if req.kind == FinancialActionKind.AUDIT_REVIEW:
        refs.append("control_test_evidence")
    if req.kind == FinancialActionKind.DISCLOSURE:
        refs.append("regulatory_filing_receipt")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: FinancialRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial ledger state for transaction {req.transaction_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply accounting rule and regulatory regime to action")
    if summary.get("decision", 0) > 0:
        steps.append("Decide whether to post the financial action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.requires_dual_control and req.dual_control_satisfied:
        steps.append("Confirm maker-checker dual-control signoff on file")
    elif req.requires_dual_control and not req.dual_control_satisfied:
        steps.append("Block: dual-control signoff missing")
    for approver in req.approver_chain:
        steps.append(f"Approver signoff: {approver}")
    if req.aml_flags:
        steps.append(
            f"Compliance officer: clear AML/sanctions flags ({', '.join(req.aml_flags)})"
        )
    if summary.get("validation", 0) > 0:
        steps.append("Validate posting against acceptance criteria")
    if req.kind == FinancialActionKind.WIRE_TRANSFER:
        steps.append("Transmit wire instruction via SWIFT/Fedwire of record")
    elif req.kind == FinancialActionKind.TRADE:
        steps.append("Route trade ticket to clearing")
    elif req.kind == FinancialActionKind.SETTLEMENT:
        steps.append("Mark obligation settled and release collateral")
    elif req.kind == FinancialActionKind.DISCLOSURE:
        steps.append("File disclosure with applicable regulator")
    elif req.kind == FinancialActionKind.LEDGER_ADJUSTMENT:
        steps.append("Post correcting entry with referenced original")
    if summary.get("execution", 0) > 0:
        steps.append("Persist posted entry to immutable journal")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: FinancialRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("financial_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.requires_dual_control and not req.dual_control_satisfied:
        flags.append(
            "dual_control_required_but_not_satisfied — block until checker signs"
        )
    if req.aml_flags:
        flags.append(
            f"aml_sanctions_flags_present ({', '.join(req.aml_flags)}) — "
            "compliance officer must clear before settlement"
        )
    if req.is_high_value and req.kind in (
        FinancialActionKind.WIRE_TRANSFER,
        FinancialActionKind.TRADE,
        FinancialActionKind.TRANSACTION,
    ):
        flags.append(
            f"high_value_{req.kind.value} — senior approver signoff required"
        )
    if (
        req.kind in (FinancialActionKind.WIRE_TRANSFER, FinancialActionKind.TRADE)
        and not req.approver_chain
    ):
        flags.append(
            f"{req.kind.value}_without_approver_chain — review staffing"
        )
    if req.blast_radius == "systemic":
        flags.append("systemic_blast_radius — impacts beyond single account/book")
    if req.kind in (
        FinancialActionKind.WIRE_TRANSFER,
        FinancialActionKind.TRADE,
        FinancialActionKind.SETTLEMENT,
        FinancialActionKind.LEDGER_ADJUSTMENT,
        FinancialActionKind.DISCLOSURE,
    ):
        flags.append(
            f"{req.kind.value}_irreversible — confirm before execution"
        )
    if req.regulatory_regime and not req.jurisdiction:
        flags.append(
            "regulatory_regime_specified_without_jurisdiction — verify scope"
        )
    return tuple(flags)
