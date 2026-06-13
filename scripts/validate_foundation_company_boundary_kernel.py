#!/usr/bin/env python3
"""Validate the Foundation Mode company-boundary kernel.

Purpose: keep the Mullu Control Plane company-boundary kernel in a
Foundation Mode readiness posture without promoting legal, financial,
customer, infrastructure, deployment, IP, patent, trademark, compliance,
continuity, or external-obligation claims.
Governance scope: Foundation Mode, repository claim control, IP provenance,
secret exclusion, ownership/control readiness, payment blocking, customer
access blocking, deployment blocking, and external-obligation prevention.
Dependencies: docs/FOUNDATION_COMPANY_BOUNDARY_KERNEL.md and
examples/foundation_company_boundary_kernel_witness.awaiting_evidence.json and
governance/company_boundary_kernel.yaml.
Invariants:
  - The witness remains AwaitingEvidence.
  - Legal, company, customer, payment, deployment, patent, trademark,
    compliance, money, and external-obligation actions remain blocked.
  - No live values, real secrets, or promotion phrases are accepted.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_COMPANY_BOUNDARY_KERNEL.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_company_boundary_kernel_witness.awaiting_evidence.json"
DEFAULT_LEDGER_PATH = REPO_ROOT / "governance" / "company_boundary_kernel.yaml"

EXPECTED_ROOT_KEYS = {
    "authorization_flags",
    "blocked_claims",
    "boundary_surfaces",
    "enforcement_rules",
    "foundation_mode_allowed_classes",
    "foundation_mode_required",
    "ip_provenance_classes",
    "mandatory_gate",
    "next_action",
    "schema_version",
    "solver_outcome",
    "status",
    "trigger_classes",
    "witness_id",
}
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.company_boundary_kernel.v1",
    "witness_id": "foundation_company_boundary_kernel_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
    "foundation_mode_required": True,
}
EXPECTED_LEDGER_KEYS = {
    "authorization_flags",
    "enforcement_rules",
    "forbidden_storage",
    "foundation_mode_allowed_classes",
    "foundation_mode_required",
    "ip_provenance_classes",
    "ledger_id",
    "mandatory_gate",
    "next_action",
    "non_authorization_rule",
    "promotion_authority",
    "promotion_surfaces",
    "schema_version",
    "solver_outcome",
    "status",
    "trigger_classes",
}
EXPECTED_LEDGER_VALUES = {
    "schema_version": "foundation.company_boundary_kernel.ledger.v1",
    "ledger_id": "foundation_company_boundary_kernel.ledger.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
    "foundation_mode_required": True,
    "promotion_authority": "promotion_witness_required",
}
AUTHORIZATION_FLAGS = (
    "company_formation_authorized",
    "compliance_certification_authorized",
    "customer_access_authorized",
    "deployment_authorized",
    "external_obligation_authorized",
    "legal_claim_authorized",
    "money_movement_allowed",
    "patent_filing_authorized",
    "payment_activation_authorized",
    "trademark_claim_authorized",
)
BLOCKED_CLAIMS = (
    "company formation",
    "trademark ownership or clearance",
    "patent filing or protection",
    "legal review completion",
    "compliance certification",
    "customer readiness",
    "deployment readiness",
    "payment provider readiness",
    "tax readiness",
    "insurance readiness",
    "continuity transfer approval",
    "production claim",
)
BOUNDARY_SURFACE_IDS = (
    "entity_status",
    "ownership_ip_status",
    "repository_infrastructure_control",
    "secrets_recovery_control",
    "money_tax_separation",
    "customer_contract_readiness",
    "privacy_data_readiness",
    "insurance_risk_review",
    "continuity_plan",
    "shutdown_transfer_path",
)
SURFACE_TYPES_BY_ID = {
    "entity_status": "blocked_entity_status",
    "ownership_ip_status": "blocked_ownership_ip_status",
    "repository_infrastructure_control": "blocked_control_surface",
    "secrets_recovery_control": "blocked_secret_recovery_surface",
    "money_tax_separation": "blocked_money_tax_surface",
    "customer_contract_readiness": "blocked_customer_contract_surface",
    "privacy_data_readiness": "blocked_privacy_data_surface",
    "insurance_risk_review": "blocked_insurance_risk_surface",
    "continuity_plan": "blocked_continuity_surface",
    "shutdown_transfer_path": "blocked_shutdown_transfer_surface",
}
IP_PROVENANCE_CLASSES = (
    "founder_created",
    "symbolic_intelligence_assisted",
    "generated_artifact",
    "third_party_dependency",
    "open_source_dependency",
    "contractor_contributor_created",
    "externally_derived",
)
FOUNDATION_MODE_ALLOWED_CLASSES = (
    "local_docs",
    "local_tests",
    "local_schemas",
    "local_proof_artifacts",
    "local_rehearsal_files",
    "draft_checklists",
    "non_secret_evidence_labels",
    "architecture_mapping",
    "governance_refinement",
    "validator_improvements",
)
MANDATORY_GATE_REQUIREMENTS = (
    "company-boundary validator passes",
    "exact surface evidence exists",
    "promotion witness exists",
    "no forbidden storage appears",
    "no unauthorized claim appears",
)
TRIGGER_CLASSES = (
    "company_formation",
    "legal_clearance",
    "customer_access",
    "pilot_readiness",
    "deployment_readiness",
    "production_health",
    "payment_activation",
    "money_movement",
    "tax_readiness",
    "patent_filing_or_protection",
    "trademark_ownership_or_clearance",
    "compliance_certification",
    "insurance_readiness",
    "continuity_transfer",
    "external_vendor_activation",
    "external_account_activation",
    "public_launch",
)
ENFORCEMENT_RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10")
FORBIDDEN_STORAGE_IDS = (
    "plaintext_secret_values",
    "private_keys",
    "access_tokens",
    "seed_phrases",
    "recovery_codes",
    "provider_account_ids",
    "private_contact_details",
    "live_endpoint_values",
    "billing_values",
    "customer_personal_data",
)
REQUIRED_DOC_PHRASES = (
    "Mullu Control Plane Company Boundary Kernel",
    "Witness packet: [`../examples/foundation_company_boundary_kernel_witness.awaiting_evidence.json`]",
    "Rule: This document does not authorize company formation, legal claims, customer",
    "## Mandatory Gate Trigger Class",
    "Before any future external obligation or readiness claim is made, the Mullu",
    "Correct enforcement formula:",
    "This change is subject to the Mullu Control Plane Company Boundary Kernel.",
    "company_boundary_kernel_state=AwaitingEvidence",
    "company_formation_authorized=false",
    "legal_claim_authorized=false",
    "customer_access_authorized=false",
    "deployment_authorized=false",
    "payment_activation_authorized=false",
    "patent_filing_authorized=false",
    "trademark_claim_authorized=false",
    "compliance_certification_authorized=false",
    "external_obligation_authorized=false",
    "money_movement_allowed=false",
    "python scripts/validate_foundation_company_boundary_kernel.py",
    "governance/company_boundary_kernel.yaml",
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
            r"\b(?:company|entity|legal|tax|bank|payment|customer|deployment|patent|trademark|"
            r"compliance|secret|token|key|url|endpoint|account)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?(?:formed|created|registered)\b", re.IGNORECASE)),
    ("legal_complete", re.compile(r"\blegal\s+review\s+(?:is\s+)?(?:complete|approved|cleared)\b", re.IGNORECASE)),
    ("trademark_secured", re.compile(r"\btrademark\s+(?:is\s+)?(?:secured|owned|cleared)\b", re.IGNORECASE)),
    ("patent_protected", re.compile(r"\bpatent\s+(?:is\s+)?(?:filed|protected|cleared)\b", re.IGNORECASE)),
    ("compliance_certified", re.compile(r"\bcompliance\s+(?:is\s+)?(?:certified|approved|complete)\b", re.IGNORECASE)),
    ("customer_access_open", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?(?:open|approved|ready)\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?(?:ready|approved|complete)\b", re.IGNORECASE)),
    ("payment_active", re.compile(r"\bpayment\s+(?:provider\s+)?(?:is\s+)?(?:active|activated|ready)\b", re.IGNORECASE)),
    ("money_allowed", re.compile(r"\bmoney\s+movement\s+(?:is\s+)?(?:allowed|approved|ready)\b", re.IGNORECASE)),
    ("production_ready", re.compile(r"\bproduction\s+(?:is\s+)?(?:ready|approved|healthy)\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class CompanyBoundaryFinding:
    """One deterministic company-boundary kernel validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a JSON object")
    return payload


def load_yaml_object(path: Path, artifact_label: str) -> dict[str, Any]:
    """Load one bounded YAML object artifact with explicit type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {artifact_label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{artifact_label} path is not a file: {path}")
    payload = parse_bounded_yaml(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{artifact_label} must be a YAML mapping")
    return payload


def parse_bounded_yaml(raw_text: str) -> dict[str, Any]:
    """Parse the bounded YAML subset used by the company-boundary ledger."""

    document: dict[str, Any] = {}
    current_key = ""
    current_item: dict[str, Any] | None = None
    for raw_line in raw_text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = split_mapping_line(line)
            current_key = key
            current_item = None
            document[current_key] = parse_scalar(value) if value else []
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if not current_key:
                raise ValueError("list item without parent key")
            item_text = stripped[2:].strip()
            current_item = {}
            document.setdefault(current_key, []).append(current_item)
            if item_text:
                key, value = split_mapping_line(item_text)
                current_item[key] = parse_scalar(value)
            continue
        if current_item is not None and ":" in stripped:
            key, value = split_mapping_line(stripped)
            current_item[key] = parse_scalar(value)
            continue
        raise ValueError("unsupported company-boundary YAML line")
    return document


def split_mapping_line(text: str) -> tuple[str, str]:
    """Split one bounded YAML mapping line into key and scalar text."""

    if ":" not in text:
        raise ValueError("expected company-boundary YAML mapping line")
    key, value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ValueError("mapping key is required")
    return key, value.strip()


def parse_scalar(value: str) -> Any:
    """Parse one bounded YAML scalar."""

    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return ()
        return tuple(parse_scalar(part.strip()) for part in inner.split(","))
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


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


def validate_doc_text(doc_text: str) -> list[CompanyBoundaryFinding]:
    """Return findings for required company-boundary documentation drift."""

    findings: list[CompanyBoundaryFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            findings.append(
                CompanyBoundaryFinding(
                    "company_boundary_doc_required_phrase",
                    f"doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_authorization_flags(flags: object) -> list[CompanyBoundaryFinding]:
    """Return findings for authorization flag drift."""

    findings: list[CompanyBoundaryFinding] = []
    if not isinstance(flags, dict):
        return [CompanyBoundaryFinding("company_boundary_flags_shape", "authorization_flags must be an object")]
    if tuple(flags.keys()) != AUTHORIZATION_FLAGS:
        findings.append(CompanyBoundaryFinding("company_boundary_flags_inventory", "authorization flag inventory drifted"))
    for flag in AUTHORIZATION_FLAGS:
        if flags.get(flag) is not False:
            findings.append(CompanyBoundaryFinding("company_boundary_flag_value", f"{flag} must remain false"))
    return findings


def validate_boundary_surfaces(surfaces: object) -> list[CompanyBoundaryFinding]:
    """Return findings for company-boundary surface inventory and state drift."""

    findings: list[CompanyBoundaryFinding] = []
    if not isinstance(surfaces, list) or not all(isinstance(surface, dict) for surface in surfaces):
        return [CompanyBoundaryFinding("company_boundary_surface_shape", "boundary_surfaces must be a list of objects")]
    observed_ids = tuple(surface.get("surface_id") for surface in surfaces)
    if observed_ids != BOUNDARY_SURFACE_IDS:
        findings.append(CompanyBoundaryFinding("company_boundary_surface_inventory", "boundary surface inventory drifted"))
    for surface in surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if tuple(surface.keys()) != ("public_safe_note", "state", "surface_id", "surface_type"):
            findings.append(CompanyBoundaryFinding("company_boundary_surface_keys", f"{surface_id} surface keys drifted"))
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                CompanyBoundaryFinding("company_boundary_surface_state", f"{surface_id} must remain AwaitingEvidence")
            )
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID.get(surface_id):
            findings.append(CompanyBoundaryFinding("company_boundary_surface_type", f"{surface_id} surface type drifted"))
        public_safe_note = surface.get("public_safe_note")
        if not isinstance(public_safe_note, str) or not public_safe_note.endswith((".", "Git.")):
            findings.append(CompanyBoundaryFinding("company_boundary_surface_note", f"{surface_id} note must be public-safe text"))
    return findings


def validate_mandatory_gate(gate: object) -> list[CompanyBoundaryFinding]:
    """Return findings for mandatory gate trigger-class drift."""

    if not isinstance(gate, dict):
        return [CompanyBoundaryFinding("company_boundary_mandatory_gate_shape", "mandatory_gate must be an object")]
    findings: list[CompanyBoundaryFinding] = []
    if gate.get("mode") != "mandatory_preflight_gate":
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_mandatory_gate_mode",
                "mandatory_gate mode must be mandatory_preflight_gate",
            )
        )
    if tuple(gate.get("requirements", ())) != MANDATORY_GATE_REQUIREMENTS:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_mandatory_gate_requirements",
                "mandatory_gate requirements drifted",
            )
        )
    status_effect = gate.get("status_effect")
    if not isinstance(status_effect, str) or "blocks promotion" not in status_effect:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_mandatory_gate_status_effect",
                "mandatory_gate must block promotion without evidence and witness",
            )
        )
    trigger_rule = gate.get("trigger_rule")
    if (
        not isinstance(trigger_rule, str)
        or "external obligation" not in trigger_rule
        or "readiness claim" not in trigger_rule
        or "AwaitingEvidence promotion" not in trigger_rule
    ):
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_mandatory_gate_trigger_rule",
                "mandatory_gate trigger rule must cover external obligation, readiness claim, and promotion",
            )
        )
    return findings


def validate_ledger_mandatory_gate(gate: object) -> list[CompanyBoundaryFinding]:
    """Return findings for mandatory gate drift in the YAML ledger."""

    findings: list[CompanyBoundaryFinding] = []
    if not isinstance(gate, list) or len(gate) != 1 or not isinstance(gate[0], dict):
        return [
            CompanyBoundaryFinding(
                "company_boundary_ledger_mandatory_gate_shape",
                "ledger mandatory_gate must contain one gate object",
            )
        ]
    gate_item = gate[0]
    if gate_item.get("gate_id") != "future_external_obligation_or_readiness_claim":
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_ledger_mandatory_gate_id",
                "ledger mandatory_gate id drifted",
            )
        )
    if gate_item.get("mode") != "mandatory_preflight_gate":
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_ledger_mandatory_gate_mode",
                "ledger mandatory_gate mode must be mandatory_preflight_gate",
            )
        )
    if gate_item.get("state") != "AwaitingEvidence":
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_ledger_mandatory_gate_state",
                "ledger mandatory_gate state must remain AwaitingEvidence",
            )
        )
    status_effect = gate_item.get("status_effect")
    if not isinstance(status_effect, str) or "blocks promotion" not in status_effect:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_ledger_mandatory_gate_status_effect",
                "ledger mandatory_gate must block promotion without evidence and witness",
            )
        )
    return findings


def validate_ledger_items(
    items: object,
    *,
    expected_ids: tuple[str, ...],
    id_key: str,
    state_key: str,
    expected_state: object,
    rule_prefix: str,
) -> list[CompanyBoundaryFinding]:
    """Return findings for a ledger list of governed mapping items."""

    findings: list[CompanyBoundaryFinding] = []
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return [CompanyBoundaryFinding(f"{rule_prefix}_shape", f"{rule_prefix} must be a list of objects")]
    observed_ids = tuple(item.get(id_key) for item in items)
    if observed_ids != expected_ids:
        findings.append(CompanyBoundaryFinding(f"{rule_prefix}_inventory", f"{rule_prefix} inventory drifted"))
    for item in items:
        item_id = str(item.get(id_key, "<missing>"))
        if item.get(state_key) != expected_state:
            findings.append(
                CompanyBoundaryFinding(
                    f"{rule_prefix}_state",
                    f"{item_id} {state_key} must remain {expected_state!r}",
                )
            )
    return findings


def validate_forbidden_text(payload: dict[str, Any]) -> list[CompanyBoundaryFinding]:
    """Return findings for live values or promotion phrases in the witness."""

    findings: list[CompanyBoundaryFinding] = []
    for text in iter_strings(payload):
        for pattern_name, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append(
                    CompanyBoundaryFinding(
                        "company_boundary_forbidden_value",
                        f"forbidden value pattern: {pattern_name}",
                    )
                )
        for pattern_name, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text):
                findings.append(
                    CompanyBoundaryFinding(
                        "company_boundary_forbidden_promotion",
                        f"forbidden promotion pattern: {pattern_name}",
                    )
                )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[CompanyBoundaryFinding]:
    """Return findings for company-boundary witness drift."""

    findings: list[CompanyBoundaryFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(CompanyBoundaryFinding("company_boundary_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(CompanyBoundaryFinding("company_boundary_root_value", f"{key} must be {expected_value!r}"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(CompanyBoundaryFinding("company_boundary_blocked_claims", "blocked claims drifted"))
    if tuple(payload.get("ip_provenance_classes", ())) != IP_PROVENANCE_CLASSES:
        findings.append(CompanyBoundaryFinding("company_boundary_ip_provenance", "IP provenance classes drifted"))
    if tuple(payload.get("foundation_mode_allowed_classes", ())) != FOUNDATION_MODE_ALLOWED_CLASSES:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_foundation_mode_allowed_classes",
                "Foundation Mode allowed classes drifted",
            )
        )
    if tuple(payload.get("trigger_classes", ())) != TRIGGER_CLASSES:
        findings.append(CompanyBoundaryFinding("company_boundary_trigger_classes", "mandatory gate trigger classes drifted"))
    if tuple(payload.get("enforcement_rules", ())) != ENFORCEMENT_RULES:
        findings.append(CompanyBoundaryFinding("company_boundary_enforcement_rules", "enforcement rule inventory drifted"))
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "AwaitingEvidence" not in next_action or "promotion witness" not in next_action:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_next_action",
                "next_action must preserve AwaitingEvidence and promotion-witness gating",
            )
        )
    findings.extend(validate_authorization_flags(payload.get("authorization_flags")))
    findings.extend(validate_boundary_surfaces(payload.get("boundary_surfaces")))
    findings.extend(validate_mandatory_gate(payload.get("mandatory_gate")))
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_ledger(payload: dict[str, Any]) -> list[CompanyBoundaryFinding]:
    """Return findings for company-boundary machine-readable ledger drift."""

    findings: list[CompanyBoundaryFinding] = []
    if set(payload) != EXPECTED_LEDGER_KEYS:
        findings.append(CompanyBoundaryFinding("company_boundary_ledger_keys", "ledger root keys drifted"))
    for key, expected_value in EXPECTED_LEDGER_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(
                CompanyBoundaryFinding("company_boundary_ledger_value", f"{key} must be {expected_value!r}")
            )
    non_authorization_rule = payload.get("non_authorization_rule")
    if not isinstance(non_authorization_rule, str) or "does not authorize company formation" not in non_authorization_rule:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_ledger_non_authorization",
                "non_authorization_rule must preserve the no-authorization claim boundary",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "AwaitingEvidence" not in next_action or "promotion witness" not in next_action:
        findings.append(
            CompanyBoundaryFinding(
                "company_boundary_ledger_next_action",
                "next_action must preserve AwaitingEvidence and promotion-witness gating",
            )
        )
    findings.extend(
        validate_ledger_items(
            payload.get("authorization_flags"),
            expected_ids=AUTHORIZATION_FLAGS,
            id_key="flag_id",
            state_key="allowed",
            expected_state=False,
            rule_prefix="company_boundary_ledger_flags",
        )
    )
    findings.extend(
        validate_ledger_items(
            payload.get("promotion_surfaces"),
            expected_ids=BOUNDARY_SURFACE_IDS,
            id_key="surface_id",
            state_key="state",
            expected_state="AwaitingEvidence",
            rule_prefix="company_boundary_ledger_surfaces",
        )
    )
    findings.extend(
        validate_ledger_items(
            payload.get("ip_provenance_classes"),
            expected_ids=IP_PROVENANCE_CLASSES,
            id_key="class_id",
            state_key="state",
            expected_state="AwaitingEvidence",
            rule_prefix="company_boundary_ledger_ip_provenance",
        )
    )
    findings.extend(validate_ledger_mandatory_gate(payload.get("mandatory_gate")))
    findings.extend(
        validate_ledger_items(
            payload.get("trigger_classes"),
            expected_ids=TRIGGER_CLASSES,
            id_key="trigger_id",
            state_key="requires_gate",
            expected_state=True,
            rule_prefix="company_boundary_ledger_trigger_classes",
        )
    )
    findings.extend(
        validate_ledger_items(
            payload.get("foundation_mode_allowed_classes"),
            expected_ids=FOUNDATION_MODE_ALLOWED_CLASSES,
            id_key="class_id",
            state_key="allowed_without_promotion",
            expected_state=True,
            rule_prefix="company_boundary_ledger_foundation_mode_allowed_classes",
        )
    )
    findings.extend(
        validate_ledger_items(
            payload.get("forbidden_storage"),
            expected_ids=FORBIDDEN_STORAGE_IDS,
            id_key="storage_id",
            state_key="blocked",
            expected_state=True,
            rule_prefix="company_boundary_ledger_forbidden_storage",
        )
    )
    findings.extend(
        validate_ledger_items(
            payload.get("enforcement_rules"),
            expected_ids=ENFORCEMENT_RULES,
            id_key="rule_id",
            state_key="state",
            expected_state="AwaitingEvidence",
            rule_prefix="company_boundary_ledger_enforcement",
        )
    )
    findings.extend(validate_forbidden_text(payload))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> list[CompanyBoundaryFinding]:
    """Validate the company-boundary kernel doc, witness packet, and ledger."""

    doc_text = load_text(doc_path, "company-boundary kernel doc")
    payload = load_json_object(packet_path, "company-boundary kernel witness")
    ledger_payload = load_yaml_object(ledger_path, "company-boundary kernel ledger")
    return [*validate_doc_text(doc_text), *validate_packet(payload), *validate_ledger(ledger_payload)]


def main(argv: list[str] | None = None) -> int:
    """Run the company-boundary kernel validator."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode company-boundary kernel artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_artifacts(args.doc, args.packet, args.ledger)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_company_boundary_kernel_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_company_boundary_kernel_doc")
    print("[PASS] foundation_company_boundary_kernel_witness")
    print("[PASS] foundation_company_boundary_kernel_ledger")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
