"""
Cybersecurity / SecOps Domain Adapter.

Translates security operations actions (incident response, containment,
eradication, recovery, vulnerability remediation, access review, change
review, forensic investigation, threat hunting, breach notification)
into the universal causal framework. Distinct shape:

  - Authority chain: lead analyst + escalation chain (IR manager,
    CISO). Regulators (PCI/HIPAA/GDPR), legal, and law enforcement
    are observer-shaped — incident notification flows to them, but
    they do not authorize the response.
  - Constraints carry acceptance criteria, change-freeze under active
    threat, breach-notification deadlines, severity-based CISO
    engagement, and data-classification-based regulator notification.
    Notably, "active_threat" inverts the usual block/escalate logic:
    routine actions (change_review, access_review) are blocked under
    active threat (don't make changes mid-incident), while response
    actions (containment, eradication, recovery) are unimpeded — they
    are the response.
  - Most security actions are reversible (account unlocked, system
    re-imaged, isolated host returned to network). The exceptions
    are BREACH_NOTIFICATION (regulatory record once filed) and
    irreversible-data ERADICATION steps.
  - Risk flags surface active threat without containment kind, missing
    CISO engagement on critical severity, regulated data without
    notification path, supply-chain blast radius, and unsigned
    forensic chain.

This adapter intentionally does NOT model specific TTPs, IOCs, or
control catalogs — it models the governance shape, and leaves
incident-specific decisions (frameworks like NIST CSF, MITRE ATT&CK,
ISO 27035) to the calling system.
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


class SecOpsActionKind(Enum):
    INCIDENT_RESPONSE = "incident_response"
    CONTAINMENT = "containment"
    ERADICATION = "eradication"
    RECOVERY = "recovery"
    VULNERABILITY_REMEDIATION = "vulnerability_remediation"
    ACCESS_REVIEW = "access_review"
    CHANGE_REVIEW = "change_review"
    FORENSIC_INVESTIGATION = "forensic_investigation"
    THREAT_HUNTING = "threat_hunting"
    BREACH_NOTIFICATION = "breach_notification"


_VALID_SEVERITIES = ("critical", "high", "medium", "low", "informational")


_RESPONSE_KINDS = (
    SecOpsActionKind.INCIDENT_RESPONSE,
    SecOpsActionKind.CONTAINMENT,
    SecOpsActionKind.ERADICATION,
    SecOpsActionKind.RECOVERY,
    SecOpsActionKind.FORENSIC_INVESTIGATION,
    SecOpsActionKind.THREAT_HUNTING,
)


_CHANGE_KINDS = (
    SecOpsActionKind.VULNERABILITY_REMEDIATION,
    SecOpsActionKind.ACCESS_REVIEW,
    SecOpsActionKind.CHANGE_REVIEW,
)


@dataclass
class SecOpsRequest:
    kind: SecOpsActionKind
    summary: str
    incident_id: str
    lead_analyst: str
    escalation_chain: tuple[str, ...] = ()
    affected_assets: tuple[str, ...] = ()
    severity: str = "medium"  # critical | high | medium | low | informational
    cvss_score: Decimal = Decimal("0")  # 0.0 - 10.0
    data_classifications: tuple[str, ...] = ()  # e.g. ("PII","PHI","cardholder")
    regulatory_regime: tuple[str, ...] = ()  # e.g. ("PCI_DSS","HIPAA","GDPR")
    jurisdiction: str = ""  # e.g. "US-FED","EU","US-CA"
    acceptance_criteria: tuple[str, ...] = ()
    active_threat: bool = False  # adversary present in environment
    data_exfil_suspected: bool = False
    is_emergency: bool = False  # major incident
    blast_radius: str = "host"  # host | tenant | enterprise | supply_chain


@dataclass
class SecOpsResult:
    response_protocol: tuple[str, ...]
    required_signoffs: tuple[str, ...]
    risk_flags: tuple[str, ...]
    estimated_blast_radius: str
    active_threat: bool
    is_emergency: bool
    governance_status: str
    audit_trail_id: UUID


# ---- Translation ----


def translate_to_universal(req: SecOpsRequest) -> UniversalRequest:
    if req.severity not in _VALID_SEVERITIES:
        raise ValueError(
            f"severity {req.severity!r} not in {_VALID_SEVERITIES}"
        )
    if req.cvss_score < Decimal("0") or req.cvss_score > Decimal("10"):
        raise ValueError(
            f"cvss_score {req.cvss_score!r} out of [0, 10]"
        )

    purpose = _purpose_from_kind(req.kind, req.summary)

    initial_state = {
        "kind": "secops_state",
        "incident_id": req.incident_id,
        "phase": "pre_action",
        "lead_analyst": req.lead_analyst,
        "severity": req.severity,
        "active_threat": req.active_threat,
    }
    target_state = {
        "kind": "secops_state",
        "incident_id": req.incident_id,
        "phase": "post_action",
        "must_satisfy": list(req.acceptance_criteria),
        "data_exfil_suspected": req.data_exfil_suspected,
    }
    boundary = {
        "inside_predicate": (
            f"incident_id = {req.incident_id} ∧ "
            f"assets ⊆ {{{', '.join(req.affected_assets)}}}"
        ),
        "interface_points": list(req.affected_assets),
        "permeability": _permeability_for_blast_radius(req.blast_radius),
    }

    constraints: list[dict[str, Any]] = [
        {
            "domain": "secops_correctness",
            "restriction": ac,
            "violation_response": "block",
        }
        for ac in req.acceptance_criteria
    ]

    # Active threat governance — invert the usual logic.
    # Routine change kinds (vuln remediation, access review, change
    # review) are BLOCKED under active threat; responders should not
    # introduce further change while adversary is in environment,
    # except via emergency change procedure (escalate).
    # Response kinds are unimpeded — they ARE the response.
    if req.active_threat and req.kind in _CHANGE_KINDS:
        atc_response = "escalate" if req.is_emergency else "block"
        constraints.append(
            {
                "domain": "active_threat_change_freeze",
                "restriction": "no_routine_change_during_active_threat",
                "violation_response": atc_response,
            }
        )

    # Data exfil suspected — escalate. Drives breach notification path.
    if req.data_exfil_suspected:
        constraints.append(
            {
                "domain": "data_exfiltration",
                "restriction": "exfiltration_path_investigated",
                "violation_response": "escalate",
            }
        )

    # Regulatory breach notification — each regime has its own clock.
    # If this is a BREACH_NOTIFICATION action, the regimes are
    # acceptance-criteria-shaped (must complete to ship). If it's a
    # different action with classified data exposure, it escalates.
    if req.regulatory_regime and (
        req.kind == SecOpsActionKind.BREACH_NOTIFICATION
        or req.data_exfil_suspected
    ):
        for regime in req.regulatory_regime:
            constraints.append(
                {
                    "domain": "breach_notification",
                    "restriction": f"notify_within_clock:{regime}",
                    "violation_response": "escalate",
                }
            )

    # CISO engagement on critical severity — escalate if not in
    # escalation chain. Severity-based authority requirement.
    if req.severity == "critical":
        constraints.append(
            {
                "domain": "ciso_engagement",
                "restriction": "ciso_in_escalation_chain",
                "violation_response": "escalate",
            }
        )

    authority = (
        f"analyst:{req.lead_analyst}",
    ) + tuple(f"escalation:{e}" for e in req.escalation_chain)

    observer: tuple[str, ...] = ("soc_audit", "blue_team_log")
    if req.severity in ("critical", "high"):
        observer = observer + ("ciso_attestation",)
    for regime in req.regulatory_regime:
        observer = observer + (f"regulator:{regime}",)
    if req.jurisdiction:
        observer = observer + (f"jurisdiction:{req.jurisdiction}",)
    for cls in req.data_classifications:
        observer = observer + (f"data_class:{cls}",)
    if req.kind == SecOpsActionKind.FORENSIC_INVESTIGATION:
        observer = observer + ("forensic_chain_of_custody",)
    if req.data_exfil_suspected:
        observer = observer + ("legal_counsel",)

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
    original_request: SecOpsRequest,
) -> SecOpsResult:
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
        [f"analyst: {original_request.lead_analyst}"]
        + [f"escalation: {e}" for e in original_request.escalation_chain]
    )

    return SecOpsResult(
        response_protocol=protocol,
        required_signoffs=signoffs,
        risk_flags=risk_flags,
        estimated_blast_radius=original_request.blast_radius,
        active_threat=original_request.active_threat,
        is_emergency=original_request.is_emergency,
        governance_status=governance_status,
        audit_trail_id=universal_result.job_definition_id,
    )


# ---- run_with_ucja ----


def _request_to_ucja_payload(req: SecOpsRequest) -> dict[str, Any]:
    universal_req = translate_to_universal(req)
    return {
        "purpose_statement": universal_req.purpose_statement,
        "initial_state_descriptor": universal_req.initial_state_descriptor,
        "target_state_descriptor": universal_req.target_state_descriptor,
        "boundary_specification": universal_req.boundary_specification,
        "authority_required": list(universal_req.authority_required),
        "acceptance_criteria": list(req.acceptance_criteria),
        "blast_radius": req.blast_radius,
        "causation_mechanism": "secops_action",
    }


def run_with_ucja(
    req: SecOpsRequest,
    *,
    capture: list | None = None,
) -> SecOpsResult:
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
        causation_mechanism="secops_action",
        causation_strength=0.9,
        transformation_energy=1.0,
        transformation_reversibility=_reversibility_for_kind(req.kind),
        validation_evidence_refs=_evidence_refs_for_request(req),
        validation_confidence=0.93,
        observation_sensor="siem_telemetry",
        observation_signal="alerted" if req.active_threat else "monitored",
        observation_confidence=0.95,
        inference_rule="security_playbook",
        inference_certainty=0.85,
        inference_kind="abductive",  # IR is best-explanation reasoning
        decision_criteria=(
            "acceptance_criteria_satisfied",
            "active_threat_aware_action_taken",
        ),
        decision_justification=(
            f"secops action {req.kind.value} for incident {req.incident_id} "
            f"(severity={req.severity}"
            f"{', active threat' if req.active_threat else ''})"
        ),
        execution_plan_prefix=f"execute {req.kind.value} for incident {req.incident_id}",
        execution_resources=tuple(req.affected_assets),
    )
    universal_result = run_default_cycle(
        universal_req, overrides, summary=req.summary, capture=capture,
    )
    return translate_from_universal(universal_result, req)


# ---- Helpers ----


def _purpose_from_kind(kind: SecOpsActionKind, summary: str) -> str:
    verb_map = {
        SecOpsActionKind.INCIDENT_RESPONSE:        "coordinate_response_to_security_event",
        SecOpsActionKind.CONTAINMENT:              "isolate_compromise_to_prevent_spread",
        SecOpsActionKind.ERADICATION:              "remove_adversary_from_environment",
        SecOpsActionKind.RECOVERY:                 "restore_systems_to_known_good_state",
        SecOpsActionKind.VULNERABILITY_REMEDIATION:"close_known_security_weakness",
        SecOpsActionKind.ACCESS_REVIEW:            "verify_principal_authorization",
        SecOpsActionKind.CHANGE_REVIEW:            "evaluate_security_impact_of_change",
        SecOpsActionKind.FORENSIC_INVESTIGATION:   "establish_what_happened_with_evidence",
        SecOpsActionKind.THREAT_HUNTING:           "search_for_undetected_compromise",
        SecOpsActionKind.BREACH_NOTIFICATION:      "notify_affected_parties_and_regulators",
    }
    return f"{verb_map[kind]}: {summary}"


def _permeability_for_blast_radius(blast: str) -> str:
    return {
        "host":         "closed",
        "tenant":       "selective",
        "enterprise":   "selective",
        "supply_chain": "open",
    }.get(blast, "selective")


def _reversibility_for_kind(kind: SecOpsActionKind) -> str:
    if kind == SecOpsActionKind.BREACH_NOTIFICATION:
        return "irreversible"  # regulatory record once filed
    if kind == SecOpsActionKind.ERADICATION:
        return "irreversible"  # may destroy data / rebuild systems
    if kind in (
        SecOpsActionKind.INCIDENT_RESPONSE,
        SecOpsActionKind.CONTAINMENT,
        SecOpsActionKind.RECOVERY,
        SecOpsActionKind.VULNERABILITY_REMEDIATION,
        SecOpsActionKind.ACCESS_REVIEW,
        SecOpsActionKind.CHANGE_REVIEW,
        SecOpsActionKind.FORENSIC_INVESTIGATION,
        SecOpsActionKind.THREAT_HUNTING,
    ):
        return "reversible"
    return "unknown"


def _evidence_refs_for_request(req: SecOpsRequest) -> tuple[str, ...]:
    refs: list[str] = ["siem_event_log"]
    if req.kind == SecOpsActionKind.FORENSIC_INVESTIGATION:
        refs.append("forensic_image")
        refs.append("chain_of_custody_record")
    if req.kind == SecOpsActionKind.BREACH_NOTIFICATION:
        refs.append("notification_letter")
        refs.append("regulatory_filing_receipt")
    if req.kind == SecOpsActionKind.VULNERABILITY_REMEDIATION:
        refs.append("vuln_scan_report")
    if req.active_threat:
        refs.append("ioc_observations")
    if req.data_classifications:
        refs.append("data_classification_inventory")
    return tuple(refs)


def _protocol_from_constructs(
    summary: dict[str, int],
    req: SecOpsRequest,
) -> tuple[str, ...]:
    steps: list[str] = []
    if summary.get("observation", 0) > 0:
        steps.append(f"Capture initial security state for incident {req.incident_id}")
    if summary.get("inference", 0) > 0:
        steps.append("Apply security playbook to current evidence")
    if summary.get("decision", 0) > 0:
        steps.append("Decide on security action")
    if summary.get("transformation", 0) > 0:
        steps.append(f"Execute {req.kind.value}")
    if req.active_threat and req.kind in _CHANGE_KINDS:
        if req.is_emergency:
            steps.append(
                "Emergency change under active threat — invoke ECAB"
            )
        else:
            steps.append(
                "Block: routine change attempted during active threat"
            )
    if req.severity == "critical":
        steps.append("Engage CISO and convene incident bridge")
    elif req.severity == "high":
        steps.append("Notify CISO of incident progression")
    for e in req.escalation_chain:
        steps.append(f"Escalation signoff: {e}")
    if req.data_exfil_suspected:
        steps.append("Engage legal counsel for breach analysis")
    if summary.get("validation", 0) > 0:
        steps.append("Validate response against acceptance criteria")
    if req.kind == SecOpsActionKind.CONTAINMENT:
        steps.append("Isolate affected hosts and rotate credentials")
    elif req.kind == SecOpsActionKind.ERADICATION:
        steps.append("Remove malware and rebuild compromised systems")
    elif req.kind == SecOpsActionKind.RECOVERY:
        steps.append("Restore service from known-good backups and verify integrity")
    elif req.kind == SecOpsActionKind.BREACH_NOTIFICATION:
        steps.append("File breach notification with applicable regulators")
        steps.append("Notify affected data subjects per jurisdiction")
    elif req.kind == SecOpsActionKind.FORENSIC_INVESTIGATION:
        steps.append("Image affected systems and preserve chain of custody")
    if summary.get("execution", 0) > 0:
        steps.append("Persist incident timeline to case management system")
    return tuple(steps)


def _risk_flags_from_result(
    result: UniversalResult,
    req: SecOpsRequest,
) -> tuple[str, ...]:
    flags: list[str] = []
    if result.rejected_deltas:
        flags.append(f"{len(result.rejected_deltas)} change(s) rejected by Φ_gov")
    if not result.converged:
        flags.append("cognitive_cycle_did_not_converge")
    if result.proof_state == "Unknown":
        flags.append("security_evidence_insufficient")
    if result.proof_state == "BudgetUnknown":
        flags.append("decision_budget_exhausted")

    if req.active_threat and req.kind in _CHANGE_KINDS:
        flags.append(
            f"routine_{req.kind.value}_during_active_threat — "
            f"{'emergency change procedure' if req.is_emergency else 'block until contained'}"
        )
    if req.active_threat and req.kind not in _RESPONSE_KINDS + _CHANGE_KINDS:
        flags.append(
            f"active_threat_with_non_response_action_{req.kind.value} — "
            "verify response posture"
        )
    if req.data_exfil_suspected:
        flags.append(
            "data_exfiltration_suspected — engage legal and verify "
            "notification clocks"
        )
    if req.severity == "critical":
        flags.append(
            "critical_severity — CISO engagement and bridge required"
        )
    if (
        req.data_classifications
        and req.kind != SecOpsActionKind.BREACH_NOTIFICATION
        and req.data_exfil_suspected
        and not req.regulatory_regime
    ):
        flags.append(
            f"regulated_data_exposure ({', '.join(req.data_classifications)}) "
            "without_regulatory_regime — verify notification venue"
        )
    if req.is_emergency:
        flags.append(
            "emergency_mode — major incident posture; document factual "
            "predicate"
        )
    if req.blast_radius == "supply_chain":
        flags.append(
            "supply_chain_blast_radius — extends beyond enterprise; "
            "engage upstream/downstream parties"
        )
    if req.kind == SecOpsActionKind.BREACH_NOTIFICATION:
        flags.append(
            "breach_notification_irreversible — once filed, regulatory "
            "record is permanent"
        )
    if req.kind == SecOpsActionKind.ERADICATION:
        flags.append(
            "eradication_may_destroy_evidence — preserve forensics "
            "before rebuild"
        )
    if (
        req.kind == SecOpsActionKind.FORENSIC_INVESTIGATION
        and not req.affected_assets
    ):
        flags.append(
            "forensic_investigation_without_affected_assets — verify "
            "scope"
        )
    return tuple(flags)
