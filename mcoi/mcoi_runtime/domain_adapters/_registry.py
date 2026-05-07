"""
Adapter registry — single source of truth for the 15 adapters.

Used by:
  - tests/test_domain_adapter_invariants.py  (parametrized invariant tests)
  - tools/audit_constraint_matrix.py         (constraint matrix generator)

When adding a 16th adapter:
  1. Create domain_adapters/<name>.py
  2. Register imports in domain_adapters/__init__.py
  3. Add a ``_<name>()`` builder + an ``AdapterEntry`` to ``ADAPTERS`` below
  4. Add an HTTP endpoint in app/routers/domains.py
  5. Regenerate CONSTRAINT_MATRIX.md (`python -m mcoi_runtime.domain_adapters._registry`
     is not the right runner; use `python -m mcoi.tools.audit_constraint_matrix`)

The cross-adapter invariants in test_domain_adapter_invariants.py will
then automatically run against the new adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from mcoi_runtime.domain_adapters import (
    UniversalRequest,
    UniversalResult,
    # software_dev
    SoftwareRequest,
    SoftwareWorkKind,
    software_run_with_ucja,
    software_translate_from_universal,
    software_translate_to_universal,
    # business_process
    BusinessActionKind,
    BusinessRequest,
    business_run_with_ucja,
    business_translate_from_universal,
    business_translate_to_universal,
    # scientific_research
    ResearchActionKind,
    ResearchRequest,
    research_run_with_ucja,
    research_translate_from_universal,
    research_translate_to_universal,
    # manufacturing
    ManufacturingActionKind,
    ManufacturingRequest,
    manufacturing_run_with_ucja,
    manufacturing_translate_from_universal,
    manufacturing_translate_to_universal,
    # healthcare
    ClinicalActionKind,
    ClinicalRequest,
    healthcare_run_with_ucja,
    healthcare_translate_from_universal,
    healthcare_translate_to_universal,
    # education
    EducationActionKind,
    EducationRequest,
    education_run_with_ucja,
    education_translate_from_universal,
    education_translate_to_universal,
    # finance
    FinancialActionKind,
    FinancialRequest,
    finance_run_with_ucja,
    finance_translate_from_universal,
    finance_translate_to_universal,
    # legal
    LegalActionKind,
    LegalRequest,
    legal_run_with_ucja,
    legal_translate_from_universal,
    legal_translate_to_universal,
    # public_sector
    CivicActionKind,
    CivicRequest,
    public_sector_run_with_ucja,
    public_sector_translate_from_universal,
    public_sector_translate_to_universal,
    # logistics
    LogisticsActionKind,
    LogisticsRequest,
    logistics_run_with_ucja,
    logistics_translate_from_universal,
    logistics_translate_to_universal,
    # energy
    EnergyActionKind,
    EnergyRequest,
    energy_run_with_ucja,
    energy_translate_from_universal,
    energy_translate_to_universal,
    # cybersecurity
    SecOpsActionKind,
    SecOpsRequest,
    cybersecurity_run_with_ucja,
    cybersecurity_translate_from_universal,
    cybersecurity_translate_to_universal,
    # insurance
    InsuranceActionKind,
    InsuranceRequest,
    insurance_run_with_ucja,
    insurance_translate_from_universal,
    insurance_translate_to_universal,
    # environmental
    EnvironmentalActionKind,
    EnvironmentalRequest,
    environmental_run_with_ucja,
    environmental_translate_from_universal,
    environmental_translate_to_universal,
    # construction
    ConstructionActionKind,
    ConstructionRequest,
    construction_run_with_ucja,
    construction_translate_from_universal,
    construction_translate_to_universal,
)


@dataclass
class AdapterEntry:
    """One row in the adapter registry: name + types + canonical builder + funcs."""

    name: str
    request_cls: type
    action_kind_cls: type
    build: Callable[[], Any]
    translate_to_universal: Callable[[Any], UniversalRequest]
    translate_from_universal: Callable[[UniversalResult, Any], Any]
    run_with_ucja: Callable[[Any], Any]


# ---- Minimal-valid request builders, one per adapter ----


def _software() -> SoftwareRequest:
    return SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="fix off-by-one in pagination",
        repository="acme/svc",
        affected_files=("svc/page.py",),
        acceptance_criteria=("regression_test_added",),
    )


def _business() -> BusinessRequest:
    return BusinessRequest(
        kind=BusinessActionKind.APPROVAL,
        summary="vendor onboarding",
        process_id="PROC-001",
        initiator="alice",
        approval_chain=("bob",),
        affected_systems=("vendor-mgmt",),
        acceptance_criteria=("vendor_kyc_complete",),
    )


def _research() -> ResearchRequest:
    return ResearchRequest(
        kind=ResearchActionKind.ANALYSIS,
        summary="analysis of correlation X~Y",
        study_id="STUDY-001",
        principal_investigator="dr-pi",
        peer_reviewers=("dr-rev",),
        affected_corpus=("dataset-A",),
        acceptance_criteria=("p_lt_005",),
    )


def _manufacturing() -> ManufacturingRequest:
    return ManufacturingRequest(
        kind=ManufacturingActionKind.ASSEMBLY,
        summary="assemble unit batch",
        line_id="LINE-A",
        operator_id="op-alice",
        quality_engineer="qe-bob",
        iso_certifications=("ISO_9001",),
        affected_part_numbers=("PN-001",),
        acceptance_criteria=("yield_above_target",),
    )


def _healthcare() -> ClinicalRequest:
    return ClinicalRequest(
        kind=ClinicalActionKind.PRESCRIPTION,
        summary="ACE inhibitor",
        encounter_id="enc-001",
        primary_clinician="dr-smith",
        consulting_specialists=("dr-cardio",),
        patient_consented=True,
        consent_kind="written",
        affected_records=("mrn-1",),
        acceptance_criteria=("indication_present",),
    )


def _education() -> EducationRequest:
    return EducationRequest(
        kind=EducationActionKind.ASSESSMENT_DESIGN,
        summary="design midterm assessment",
        course_id="MATH-101",
        instructor="prof-alice",
        curriculum_committee=("prof-bob",),
        affected_learners=("learner-1",),
        learning_objectives=("define_limit",),
        acceptance_criteria=("rubric_passed",),
    )


def _finance() -> FinancialRequest:
    return FinancialRequest(
        kind=FinancialActionKind.WIRE_TRANSFER,
        summary="vendor payment",
        transaction_id="TX-001",
        responsible_officer="alice",
        approver_chain=("bob",),
        amount=Decimal("100"),
        currency="USD",
        jurisdiction="US",
        regulatory_regime=("SOX",),
        affected_accounts=("1001",),
        acceptance_criteria=("balance_sufficient",),
    )


def _legal() -> LegalRequest:
    return LegalRequest(
        kind=LegalActionKind.CASE_FILING,
        summary="breach of contract",
        matter_id="M-001",
        lead_counsel="alice",
        co_counsel=("bob",),
        client="acme",
        opposing_party="widget",
        jurisdiction="US-NY-FED",
        court="SDNY",
        acceptance_criteria=("jurisdiction_proper",),
    )


def _public_sector() -> CivicRequest:
    return CivicRequest(
        kind=CivicActionKind.PERMIT_ISSUANCE,
        summary="construction permit",
        case_id="P-001",
        responsible_official="alice",
        reviewer_chain=("bob",),
        agency="DBI-SF",
        statute_authority=("CODE",),
        jurisdiction="US-CA-SF",
        affected_records=("parcel-1",),
        acceptance_criteria=("zoning_ok",),
        due_process_required=True,
        due_process_completed=True,
    )


def _logistics() -> LogisticsRequest:
    return LogisticsRequest(
        kind=LogisticsActionKind.SHIPMENT_DISPATCH,
        summary="domestic shipment",
        shipment_id="SHIP-001",
        responsible_dispatcher="alice",
        carrier_chain=("ups",),
        shipper="acme",
        consignee="widget",
        origin="US",
        destination="US",
        modes=("road",),
        affected_skus=("SKU-1",),
        acceptance_criteria=("manifest_signed",),
    )


def _energy() -> EnergyRequest:
    return EnergyRequest(
        kind=EnergyActionKind.GENERATION_DISPATCH,
        summary="ramp Unit 3",
        operation_id="OP-001",
        responsible_operator="alice",
        approver_chain=("sup",),
        balancing_authority="CAISO",
        service_territory="PG&E",
        jurisdiction="FERC",
        regulatory_regime=("NERC_BAL",),
        affected_assets=("GEN-3",),
        megawatts=Decimal("50"),
        acceptance_criteria=("frequency_within_band",),
        reliability_critical=True,
    )


def _cybersecurity() -> SecOpsRequest:
    return SecOpsRequest(
        kind=SecOpsActionKind.INCIDENT_RESPONSE,
        summary="lateral movement alert",
        incident_id="INC-001",
        lead_analyst="alice",
        escalation_chain=("ir-mgr",),
        affected_assets=("host-001",),
        severity="medium",
        cvss_score=Decimal("5.5"),
        acceptance_criteria=("playbook_followed",),
    )


def _insurance() -> InsuranceRequest:
    return InsuranceRequest(
        kind=InsuranceActionKind.UNDERWRITING,
        summary="auto policy review",
        case_id="POL-001",
        responsible_agent="alice",
        approver_chain=("senior-uw",),
        policyholder="john-doe",
        line_of_business="auto",
        jurisdiction="US-CA",
        regulatory_regime=("CA-DOI",),
        policy_number="POL-001",
        sum_insured=Decimal("25000"),
        affected_policies=("POL-001",),
        acceptance_criteria=("risk_acceptable",),
        sanctions_screened=True,
    )


def _environmental() -> EnvironmentalRequest:
    return EnvironmentalRequest(
        kind=EnvironmentalActionKind.PERMIT_COMPLIANCE_CHECK,
        summary="quarterly permit check",
        facility_id="FAC-001",
        responsible_officer="alice",
        reviewer_chain=("internal-audit",),
        operator="acme-mfg",
        regulatory_authority="EPA",
        regulatory_regime=("CAA",),
        jurisdiction="US-FED",
        affected_media=("air",),
        acceptance_criteria=("permit_terms_met",),
    )


def _construction() -> ConstructionRequest:
    return ConstructionRequest(
        kind=ConstructionActionKind.RFI,
        summary="clarification on beam dimension",
        project_id="PROJ-001",
        project_manager="alice",
        approver_chain=("super",),
        general_contractor="acme-build",
        owner="dev-corp",
        permit_authority="DBI-SF",
        jurisdiction="US-CA-SF",
        trades_involved=("structural",),
        affected_drawings=("S-101",),
        acceptance_criteria=("response_time_within_sla",),
        permit_on_file=True,
    )


ADAPTERS: list[AdapterEntry] = [
    AdapterEntry(
        "software_dev", SoftwareRequest, SoftwareWorkKind, _software,
        software_translate_to_universal, software_translate_from_universal,
        software_run_with_ucja,
    ),
    AdapterEntry(
        "business_process", BusinessRequest, BusinessActionKind, _business,
        business_translate_to_universal, business_translate_from_universal,
        business_run_with_ucja,
    ),
    AdapterEntry(
        "scientific_research", ResearchRequest, ResearchActionKind, _research,
        research_translate_to_universal, research_translate_from_universal,
        research_run_with_ucja,
    ),
    AdapterEntry(
        "manufacturing", ManufacturingRequest, ManufacturingActionKind,
        _manufacturing,
        manufacturing_translate_to_universal,
        manufacturing_translate_from_universal,
        manufacturing_run_with_ucja,
    ),
    AdapterEntry(
        "healthcare", ClinicalRequest, ClinicalActionKind, _healthcare,
        healthcare_translate_to_universal,
        healthcare_translate_from_universal,
        healthcare_run_with_ucja,
    ),
    AdapterEntry(
        "education", EducationRequest, EducationActionKind, _education,
        education_translate_to_universal,
        education_translate_from_universal,
        education_run_with_ucja,
    ),
    AdapterEntry(
        "finance", FinancialRequest, FinancialActionKind, _finance,
        finance_translate_to_universal, finance_translate_from_universal,
        finance_run_with_ucja,
    ),
    AdapterEntry(
        "legal", LegalRequest, LegalActionKind, _legal,
        legal_translate_to_universal, legal_translate_from_universal,
        legal_run_with_ucja,
    ),
    AdapterEntry(
        "public_sector", CivicRequest, CivicActionKind, _public_sector,
        public_sector_translate_to_universal,
        public_sector_translate_from_universal,
        public_sector_run_with_ucja,
    ),
    AdapterEntry(
        "logistics", LogisticsRequest, LogisticsActionKind, _logistics,
        logistics_translate_to_universal,
        logistics_translate_from_universal,
        logistics_run_with_ucja,
    ),
    AdapterEntry(
        "energy", EnergyRequest, EnergyActionKind, _energy,
        energy_translate_to_universal,
        energy_translate_from_universal,
        energy_run_with_ucja,
    ),
    AdapterEntry(
        "cybersecurity", SecOpsRequest, SecOpsActionKind, _cybersecurity,
        cybersecurity_translate_to_universal,
        cybersecurity_translate_from_universal,
        cybersecurity_run_with_ucja,
    ),
    AdapterEntry(
        "insurance", InsuranceRequest, InsuranceActionKind, _insurance,
        insurance_translate_to_universal,
        insurance_translate_from_universal,
        insurance_run_with_ucja,
    ),
    AdapterEntry(
        "environmental", EnvironmentalRequest, EnvironmentalActionKind,
        _environmental,
        environmental_translate_to_universal,
        environmental_translate_from_universal,
        environmental_run_with_ucja,
    ),
    AdapterEntry(
        "construction", ConstructionRequest, ConstructionActionKind,
        _construction,
        construction_translate_to_universal,
        construction_translate_from_universal,
        construction_run_with_ucja,
    ),
]
