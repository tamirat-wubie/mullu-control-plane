#!/usr/bin/env python3
"""Validate the Foundation Mode company-formation deferral boundary.

Purpose: keep company formation, entity registration, tax identifiers,
business accounts, payment processors, payroll, contracts, investor agreements,
ownership/equity claims, accounting/insurance readiness, legal clearance,
money movement, customer access, external publication, and deployment blocked.
Governance scope: Foundation Mode, local company-formation deferral,
entity-registration blocking, private-value exclusion, obligation blocking,
money-movement blocking, customer-access blocking, publication blocking, and
deployment blocking.
Dependencies: docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md and
examples/foundation_company_formation_deferral_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe deferral labels only.
  - No entity names, identifiers, addresses, bank values, tax values, contracts, investor records, ownership records, or readiness claims are recorded.
  - Every company-formation deferral surface remains AwaitingEvidence.
  - Money movement, customer access, publication, and deployment remain blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_company_formation_deferral_witness.awaiting_evidence.json"

REQUIRED_ROOT_KEYS = (
    "accounting_readiness_claimed",
    "blocked_claims",
    "business_address_recorded",
    "business_bank_account_allowed",
    "company_formation_claimed",
    "contractor_agreement_allowed",
    "customer_access_allowed",
    "deferral_labels",
    "deployment_allowed",
    "entity_name_reserved",
    "entity_registration_allowed",
    "external_publication_allowed",
    "insurance_readiness_claimed",
    "investor_agreement_allowed",
    "legal_clearance_claimed",
    "legal_entity_identifier_recorded",
    "money_movement_allowed",
    "next_action",
    "ownership_equity_allocation_claimed",
    "payment_processor_account_allowed",
    "payroll_setup_allowed",
    "registered_agent_recorded",
    "schema_version",
    "solver_outcome",
    "status",
    "surfaces",
    "tax_identifier_recorded",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.company_formation_deferral.v1",
    "witness_id": "foundation_company_formation_deferral_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "accounting_readiness_claimed",
    "business_address_recorded",
    "business_bank_account_allowed",
    "company_formation_claimed",
    "contractor_agreement_allowed",
    "customer_access_allowed",
    "deployment_allowed",
    "entity_name_reserved",
    "entity_registration_allowed",
    "external_publication_allowed",
    "insurance_readiness_claimed",
    "investor_agreement_allowed",
    "legal_clearance_claimed",
    "legal_entity_identifier_recorded",
    "money_movement_allowed",
    "ownership_equity_allocation_claimed",
    "payment_processor_account_allowed",
    "payroll_setup_allowed",
    "registered_agent_recorded",
    "tax_identifier_recorded",
)
DEFERRAL_LABELS = (
    "formation_scope_gate",
    "entity_registration_gate",
    "entity_name_reservation_gate",
    "legal_entity_identifier_gate",
    "tax_identifier_gate",
    "registered_agent_address_gate",
    "business_bank_account_gate",
    "payment_processor_account_gate",
    "payroll_setup_gate",
    "contractor_agreement_gate",
    "investor_agreement_gate",
    "ownership_equity_gate",
    "accounting_readiness_gate",
    "insurance_readiness_gate",
    "legal_clearance_gate",
    "money_movement_gate",
    "customer_access_gate",
    "publication_deployment_gate",
    "operator_reassessment_gate",
)
BLOCKED_CLAIMS = (
    "company formation",
    "entity registration",
    "entity name reservation",
    "legal entity identifier",
    "tax identifier recording",
    "registered agent record",
    "business address record",
    "business bank account",
    "payment processor account",
    "payroll setup",
    "contractor agreement",
    "investor agreement",
    "ownership/equity allocation",
    "accounting readiness",
    "insurance readiness",
    "legal clearance",
    "money movement",
    "customer access",
    "external publication",
    "deployment readiness",
)
SURFACE_NOTES_BY_ID = {
    "formation_scope_gate": "Formation scope gate only; formation scope closure is not claimed.",
    "entity_registration_gate": "Entity registration gate only; entity registration is not performed or claimed.",
    "entity_name_reservation_gate": "Entity name reservation gate only; entity names are not reserved or recorded.",
    "legal_entity_identifier_gate": "Legal entity identifier gate only; legal-entity identifiers are not recorded.",
    "tax_identifier_gate": "Tax identifier gate only; tax identifiers are not recorded.",
    "registered_agent_address_gate": "Registered-agent/address gate only; registered-agent and business-address facts are not recorded.",
    "business_bank_account_gate": "Business bank account gate only; business bank accounts are not opened or claimed.",
    "payment_processor_account_gate": "Payment processor account gate only; payment processor accounts are not activated or claimed.",
    "payroll_setup_gate": "Payroll setup gate only; payroll setup is not allowed.",
    "contractor_agreement_gate": "Contractor agreement gate only; contractor agreements are not allowed.",
    "investor_agreement_gate": "Investor agreement gate only; investor agreements are not allowed.",
    "ownership_equity_gate": "Ownership/equity gate only; ownership and equity allocation closure is not claimed.",
    "accounting_readiness_gate": "Accounting readiness gate only; accounting readiness is not claimed.",
    "insurance_readiness_gate": "Insurance readiness gate only; insurance readiness is not claimed.",
    "legal_clearance_gate": "Legal clearance gate only; legal clearance is not claimed.",
    "money_movement_gate": "Money movement gate only; money movement is not allowed.",
    "customer_access_gate": "Customer access gate only; customer access is not allowed.",
    "publication_deployment_gate": "Publication/deployment gate only; external publication and deployment are not allowed.",
    "operator_reassessment_gate": "Operator reassessment gate only; company-formation promotion is not approved.",
}
SURFACE_TYPES_BY_ID = {
    "formation_scope_gate": "blocked_formation_scope_label",
    "entity_registration_gate": "blocked_entity_registration_label",
    "entity_name_reservation_gate": "blocked_entity_name_label",
    "legal_entity_identifier_gate": "blocked_legal_entity_identifier_label",
    "tax_identifier_gate": "blocked_tax_identifier_label",
    "registered_agent_address_gate": "blocked_registered_agent_address_label",
    "business_bank_account_gate": "blocked_business_bank_account_label",
    "payment_processor_account_gate": "blocked_payment_processor_account_label",
    "payroll_setup_gate": "blocked_payroll_setup_label",
    "contractor_agreement_gate": "blocked_contractor_agreement_label",
    "investor_agreement_gate": "blocked_investor_agreement_label",
    "ownership_equity_gate": "blocked_ownership_equity_label",
    "accounting_readiness_gate": "blocked_accounting_readiness_label",
    "insurance_readiness_gate": "blocked_insurance_readiness_label",
    "legal_clearance_gate": "blocked_legal_clearance_label",
    "money_movement_gate": "blocked_money_movement_label",
    "customer_access_gate": "blocked_customer_access_label",
    "publication_deployment_gate": "blocked_publication_deployment_label",
    "operator_reassessment_gate": "local_gate_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Company Formation Deferral Boundary",
    "Witness packet: [`../examples/foundation_company_formation_deferral_witness.awaiting_evidence.json`]",
    "Rule: Company-formation deferral is a local stop-rule packet",
    "No company formation claim, entity registration, entity-name reservation,",
    "company_formation_deferral_state=AwaitingEvidence",
    "company_formation_claimed=false",
    "entity_registration_allowed=false",
    "entity_name_reserved=false",
    "legal_entity_identifier_recorded=false",
    "tax_identifier_recorded=false",
    "registered_agent_recorded=false",
    "business_address_recorded=false",
    "business_bank_account_allowed=false",
    "payment_processor_account_allowed=false",
    "payroll_setup_allowed=false",
    "contractor_agreement_allowed=false",
    "investor_agreement_allowed=false",
    "ownership_equity_allocation_claimed=false",
    "accounting_readiness_claimed=false",
    "insurance_readiness_claimed=false",
    "legal_clearance_claimed=false",
    "money_movement_allowed=false",
    "customer_access_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_company_formation_deferral_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("timestamp", re.compile(r"\b20\d{2}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d")),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("hash_like_value", re.compile(r"\b[a-f0-9]{32,}\b", re.IGNORECASE)),
    ("currency_amount", re.compile(r"(?:\$|USD\s*)\d+(?:[,\d]*(?:\.\d{2})?)?", re.IGNORECASE)),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:company|entity|llc|inc|formation|registration|registered|agent|address|"
            r"legal|identifier|tax|ein|bank|routing|account|processor|payment|stripe|"
            r"payroll|contractor|contract|investor|equity|ownership|accounting|insurance|"
            r"customer|secret|token|key|url|endpoint)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?(?:formed|created|registered)\b", re.IGNORECASE)),
    ("entity_registered", re.compile(r"\bentity\s+(?:is\s+)?(?:registered|created|formed)\b", re.IGNORECASE)),
    ("name_reserved", re.compile(r"\b(?:entity|company)\s+name\s+(?:is\s+)?reserved\b", re.IGNORECASE)),
    ("identifier_recorded", re.compile(r"\b(?:legal entity|tax)\s+identifier\s+(?:is\s+)?recorded\b", re.IGNORECASE)),
    ("tax_ready", re.compile(r"\btax\s+(?:is\s+)?(?:ready|approved|cleared)\b", re.IGNORECASE)),
    ("bank_open", re.compile(r"\bbusiness bank account\s+(?:is\s+)?(?:open|opened|ready)\b", re.IGNORECASE)),
    ("processor_enabled", re.compile(r"\bpayment processor\s+(?:is\s+)?(?:enabled|active|ready)\b", re.IGNORECASE)),
    ("payroll_ready", re.compile(r"\bpayroll\s+(?:is\s+)?(?:ready|active|set up)\b", re.IGNORECASE)),
    ("contractor_approved", re.compile(r"\bcontractor\s+(?:is\s+)?(?:approved|engaged|ready)\b", re.IGNORECASE)),
    ("investor_signed", re.compile(r"\binvestor agreement\s+(?:is\s+)?(?:signed|approved|ready)\b", re.IGNORECASE)),
    ("equity_approved", re.compile(r"\bequity\s+(?:is\s+)?(?:allocated|approved|promised)\b", re.IGNORECASE)),
    ("accounting_ready", re.compile(r"\baccounting\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("insurance_ready", re.compile(r"\binsurance\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_clearance_approved", re.compile(r"\blegal clearance\s+(?:is\s+)?(?:approved|granted|secured)\b", re.IGNORECASE)),
    ("money_movement_allowed", re.compile(r"\bmoney movement\s+(?:is\s+)?(?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer access\s+(?:is\s+)?(?:open|allowed|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic company-formation deferral validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, artifact_label: str) -> str:
    """Load one UTF-8 text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one JSON object artifact with explicit type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def iter_strings(value: object) -> list[str]:
    """Return every string nested under a JSON-like value."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(iter_strings(nested_value))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for nested_value in value:
            strings.extend(iter_strings(nested_value))
        return strings
    return []


def validate_doc_text(doc_text: str) -> list[Finding]:
    """Return findings for required boundary documentation drift."""

    findings: list[Finding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(Finding("doc_required_phrase", f"doc missing required phrase: {phrase}"))
    return findings


def validate_forbidden_text(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for private values or promotion phrases in the witness."""

    findings: list[Finding] = []
    for text in iter_strings(payload):
        for pattern_name, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_value_pattern", f"forbidden value pattern: {pattern_name}"))
        for pattern_name, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text):
                findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {pattern_name}"))
    return findings


def validate_surfaces(surfaces: object) -> list[Finding]:
    """Return findings for company-formation deferral surface inventory and state drift."""

    findings: list[Finding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [Finding("surface_shape", "surfaces must be a list of objects")]
    observed_ids = tuple(surface.get("surface_id") for surface in surfaces)
    if observed_ids != DEFERRAL_LABELS:
        findings.append(Finding("surface_inventory", "surface inventory drifted"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        expected_keys = ("public_safe_note", "state", "surface_id", "surface_type")
        if tuple(surface.keys()) != expected_keys:
            findings.append(Finding("surface_keys", f"{surface_id} surface keys drifted"))
        if surface.get("state") != "AwaitingEvidence":
            findings.append(Finding("surface_state", f"{surface_id} must remain AwaitingEvidence"))
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID.get(surface_id):
            findings.append(Finding("surface_type", f"{surface_id} surface type drifted"))
        if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID.get(surface_id):
            findings.append(Finding("surface_note", f"{surface_id} surface note drifted"))
    return findings


def validate_packet(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for company-formation deferral packet drift."""

    findings: list[Finding] = []
    if tuple(payload.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(Finding("witness_root_value", f"{key} must be {expected_value!r}"))
    for flag in FALSE_FLAGS:
        if payload.get(flag) is not False:
            findings.append(Finding("witness_false_flag", f"{flag} must remain false"))
    if tuple(payload.get("deferral_labels", ())) != DEFERRAL_LABELS:
        findings.append(Finding("witness_label_inventory", "deferral label inventory drifted"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "blocked claims drifted"))
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "company-formation deferral" not in next_action:
        findings.append(Finding("witness_next_action", "next_action must preserve company-formation deferral"))
    findings.extend(validate_surfaces(payload.get("surfaces")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the company-formation deferral doc and witness packet."""

    doc_text = load_text(doc_path, "company-formation deferral doc")
    payload = load_json_object(packet_path, "company-formation deferral witness")
    return [*validate_doc_text(doc_text), *validate_packet(payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the company-formation deferral validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode company-formation deferral artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_company_formation_deferral_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_company_formation_deferral_doc")
    print("[PASS] foundation_company_formation_deferral_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
