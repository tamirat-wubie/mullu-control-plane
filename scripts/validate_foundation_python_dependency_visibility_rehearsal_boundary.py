#!/usr/bin/env python3
"""Validate the Foundation Mode Python dependency-visibility rehearsal boundary.

Purpose: keep Python interpreter and package-visibility rehearsal public-safe
while dependency visibility, package install, environment mutation, FastAPI
readiness, full preflight closure, runtime readiness, source-control
publication, external publication, deployment, customer access, legal
clearance, company formation, patent action, money movement, secret
publication, and private-path recording remain blocked.
Governance scope: Foundation Mode, Python dependency visibility, interpreter
labels, user-site visibility labels, optional dependency group labels,
import-probe labels, sandbox/elevated preflight labels, repair-option labels,
validation command pairing, stop-rule rehearsal, private-value exclusion, and
external-action blocking.
Dependencies:
docs/FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md and
examples/foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json.
Invariants:
  - The witness records public-safe dependency-visibility rehearsal labels only.
  - Every dependency-visibility rehearsal surface remains AwaitingEvidence.
  - No install, environment mutation, runtime, publication, deployment,
    customer, legal, company, patent, money, secret, or private-path claim is
    accepted.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md"
DEFAULT_PACKET_PATH = (
    REPO_ROOT / "examples" / "foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json"
)

REQUIRED_ROOT_KEYS = (
    "blocked_claims",
    "company_formation_claimed",
    "customer_access_allowed",
    "deferral_labels",
    "dependency_install_allowed",
    "dependency_visibility_claimed",
    "deployment_allowed",
    "environment_mutation_allowed",
    "external_publication_allowed",
    "fastapi_readiness_claimed",
    "interpreter_path_recording_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "next_action",
    "package_install_allowed",
    "patent_action_allowed",
    "preflight_closure_claimed",
    "private_path_recording_allowed",
    "runtime_readiness_claimed",
    "schema_version",
    "secret_publication_allowed",
    "solver_outcome",
    "source_control_publication_allowed",
    "status",
    "surfaces",
    "witness_id",
)
EXPECTED_ROOT_VALUES = {
    "schema_version": "foundation.python_dependency_visibility_rehearsal.v1",
    "witness_id": "foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.v1",
    "status": "AwaitingEvidence",
    "solver_outcome": "AwaitingEvidence",
}
FALSE_FLAGS = (
    "company_formation_claimed",
    "customer_access_allowed",
    "dependency_install_allowed",
    "dependency_visibility_claimed",
    "deployment_allowed",
    "environment_mutation_allowed",
    "external_publication_allowed",
    "fastapi_readiness_claimed",
    "interpreter_path_recording_allowed",
    "legal_clearance_claimed",
    "money_movement_allowed",
    "package_install_allowed",
    "patent_action_allowed",
    "preflight_closure_claimed",
    "private_path_recording_allowed",
    "runtime_readiness_claimed",
    "secret_publication_allowed",
    "source_control_publication_allowed",
)
DEFERRAL_LABELS = (
    "interpreter_label_rehearsal",
    "user_site_visibility_rehearsal",
    "optional_dependency_group_rehearsal",
    "import_probe_label_rehearsal",
    "sandbox_boundary_rehearsal",
    "elevated_preflight_label_rehearsal",
    "dependency_gap_note_rehearsal",
    "repair_option_label_rehearsal",
    "validation_command_pairing_rehearsal",
    "stop_rule_rehearsal",
)
BLOCKED_CLAIMS = (
    "dependency visibility",
    "dependency install",
    "interpreter path recording",
    "private path recording",
    "package install",
    "environment mutation",
    "FastAPI readiness",
    "full preflight closure",
    "runtime readiness",
    "source-control publication",
    "external publication",
    "deployment readiness",
    "customer access",
    "legal clearance",
    "company formation",
    "patent action",
    "money movement",
    "secret publication",
)
SURFACE_NOTES_BY_ID = {
    "interpreter_label_rehearsal": (
        "Interpreter-label rehearsal only; real interpreter paths and interpreter verification are not recorded."
    ),
    "user_site_visibility_rehearsal": (
        "User-site visibility rehearsal only; site-package paths and dependency-visibility claims are not recorded."
    ),
    "optional_dependency_group_rehearsal": (
        "Optional dependency group rehearsal only; package installs and dependency-group completeness are not approved."
    ),
    "import_probe_label_rehearsal": "Import-probe label rehearsal only; FastAPI readiness and package readiness are not claimed.",
    "sandbox_boundary_rehearsal": (
        "Sandbox-boundary rehearsal only; sandbox bypass and elevated-environment readiness are not approved."
    ),
    "elevated_preflight_label_rehearsal": (
        "Elevated-preflight label rehearsal only; full preflight closure and CI parity are not claimed."
    ),
    "dependency_gap_note_rehearsal": (
        "Dependency-gap note rehearsal only; private paths, versions, endpoints, and account identifiers are not recorded."
    ),
    "repair_option_label_rehearsal": (
        "Repair-option label rehearsal only; environment mutation, package install, and profile changes are not approved."
    ),
    "validation_command_pairing_rehearsal": (
        "Validation-command pairing rehearsal only; command pairing is not test readiness or runtime readiness."
    ),
    "stop_rule_rehearsal": (
        "Stop-rule rehearsal only; source-control publication, deployment, spending, secret handling, customer access, legal, company, and patent actions are not approved."
    ),
}
SURFACE_TYPES_BY_ID = {
    "interpreter_label_rehearsal": "local_interpreter_label",
    "user_site_visibility_rehearsal": "local_user_site_visibility_label",
    "optional_dependency_group_rehearsal": "local_optional_dependency_label",
    "import_probe_label_rehearsal": "local_import_probe_label",
    "sandbox_boundary_rehearsal": "local_sandbox_boundary_label",
    "elevated_preflight_label_rehearsal": "local_preflight_visibility_label",
    "dependency_gap_note_rehearsal": "local_dependency_gap_label",
    "repair_option_label_rehearsal": "local_repair_option_label",
    "validation_command_pairing_rehearsal": "local_validation_pairing_label",
    "stop_rule_rehearsal": "local_stop_rule_label",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Python Dependency Visibility Rehearsal Boundary",
    "Witness packet: [`../examples/foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json`]",
    "Rule: Python dependency-visibility rehearsal is a local Foundation Mode",
    "No dependency-visibility claim, dependency-install approval, interpreter path",
    "python_dependency_visibility_rehearsal_boundary_state=AwaitingEvidence",
    "dependency_visibility_claimed=false",
    "dependency_install_allowed=false",
    "interpreter_path_recording_allowed=false",
    "private_path_recording_allowed=false",
    "package_install_allowed=false",
    "environment_mutation_allowed=false",
    "fastapi_readiness_claimed=false",
    "preflight_closure_claimed=false",
    "runtime_readiness_claimed=false",
    "source_control_publication_allowed=false",
    "external_publication_allowed=false",
    "deployment_allowed=false",
    "customer_access_allowed=false",
    "legal_clearance_claimed=false",
    "company_formation_claimed=false",
    "patent_action_allowed=false",
    "money_movement_allowed=false",
    "secret_publication_allowed=false",
    "python scripts/validate_foundation_python_dependency_visibility_rehearsal_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS = (
    ("url", re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/|\\\\[^\\]+\\)", re.IGNORECASE)),
    ("secret_material", re.compile(r"\b(?:sk|pk|ghp|github_pat|AKIA)[A-Za-z0-9_-]{8,}\b")),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "assignment_shape",
        re.compile(
            r"\b(?:interpreter|python|path|site|package|fastapi|dependency|pip|venv|"
            r"env|environment|token|secret|endpoint|account|customer|legal|company|"
            r"patent|payment|deploy|deployment|production)\w*\s*=",
            re.IGNORECASE,
        ),
    ),
)
FORBIDDEN_PROMOTION_PATTERNS = (
    ("dependency_visible", re.compile(r"\bdependency\s+(?:is\s+)?visible\b", re.IGNORECASE)),
    ("dependency_ready", re.compile(r"\bdependency\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("package_installed", re.compile(r"\bpackage\s+(?:is\s+)?installed\b", re.IGNORECASE)),
    ("fastapi_ready", re.compile(r"\bfastapi\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("preflight_closed", re.compile(r"\bpreflight\s+(?:is\s+)?(?:closed|complete|passed)\b", re.IGNORECASE)),
    ("runtime_ready", re.compile(r"\bruntime\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("environment_ready", re.compile(r"\benvironment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("source_control_published", re.compile(r"\bsource\s+control\s+(?:is\s+)?published\b", re.IGNORECASE)),
    ("deployment_ready", re.compile(r"\bdeployment\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("customer_access_ready", re.compile(r"\bcustomer\s+access\s+(?:is\s+)?ready\b", re.IGNORECASE)),
    ("legal_clearance", re.compile(r"\blegal\s+clearance\s+(?:is\s+)?(?:ready|complete|approved)\b", re.IGNORECASE)),
    ("company_formed", re.compile(r"\bcompany\s+(?:is\s+)?formed\b", re.IGNORECASE)),
    ("patent_filed", re.compile(r"\bpatent\s+(?:is\s+)?filed\b", re.IGNORECASE)),
    ("money_moved", re.compile(r"\bmoney\s+(?:is\s+)?moved\b", re.IGNORECASE)),
    ("secret_cleared", re.compile(r"\bsecret\s+(?:is\s+)?cleared\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic dependency-visibility rehearsal validation finding."""

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


def validate_witness_shape(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for dependency-visibility rehearsal witness shape drift."""

    findings: list[Finding] = []
    if tuple(payload.keys()) != REQUIRED_ROOT_KEYS:
        findings.append(Finding("witness_root_keys", "witness root keys drifted"))
    for key, expected_value in EXPECTED_ROOT_VALUES.items():
        if payload.get(key) != expected_value:
            findings.append(Finding("witness_root_value", f"{key} must equal {expected_value!r}"))
    for flag in FALSE_FLAGS:
        if payload.get(flag) is not False:
            findings.append(Finding("witness_false_flag", f"{flag} must remain false"))
    if tuple(payload.get("deferral_labels", ())) != DEFERRAL_LABELS:
        findings.append(Finding("witness_deferral_labels", "deferral labels drifted"))
    if tuple(payload.get("blocked_claims", ())) != BLOCKED_CLAIMS:
        findings.append(Finding("witness_blocked_claims", "blocked claims drifted"))
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        findings.append(Finding("witness_surfaces_type", "surfaces must be a list"))
        return findings
    observed_surface_ids: list[str] = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            findings.append(Finding("witness_surface_type", "each surface must be an object"))
            continue
        surface_id = surface.get("surface_id")
        observed_surface_ids.append(str(surface_id))
        if surface.get("state") != "AwaitingEvidence":
            findings.append(Finding("surface_state", f"{surface_id} must remain AwaitingEvidence"))
        if surface.get("surface_type") != SURFACE_TYPES_BY_ID.get(surface_id):
            findings.append(Finding("surface_type", f"{surface_id} surface type drifted"))
        if surface.get("public_safe_note") != SURFACE_NOTES_BY_ID.get(surface_id):
            findings.append(Finding("surface_note", f"{surface_id} surface note drifted"))
    if tuple(observed_surface_ids) != DEFERRAL_LABELS:
        findings.append(Finding("surface_inventory", "surface inventory drifted"))
    return findings


def validate_forbidden_values(payload: dict[str, Any]) -> list[Finding]:
    """Return findings for private values or premature readiness phrases."""

    findings: list[Finding] = []
    for text_value in iter_strings(payload):
        for label, pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text_value):
                findings.append(Finding("forbidden_value_pattern", f"forbidden value pattern: {label}"))
        for label, pattern in FORBIDDEN_PROMOTION_PATTERNS:
            if pattern.search(text_value):
                findings.append(Finding("forbidden_promotion_pattern", f"forbidden promotion pattern: {label}"))
    return findings


def validate_artifacts(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[Finding]:
    """Validate the dependency-visibility rehearsal doc and witness."""

    doc_text = load_text(doc_path, "Python dependency-visibility rehearsal doc")
    payload = load_json_object(packet_path, "Python dependency-visibility rehearsal witness")
    findings: list[Finding] = []
    findings.extend(validate_doc_text(doc_text))
    findings.extend(validate_witness_shape(payload))
    findings.extend(validate_forbidden_values(payload))
    return findings


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run validation and print deterministic status lines."""

    args = build_parser().parse_args(argv)
    findings = validate_artifacts(args.doc, args.packet)
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_python_dependency_visibility_rehearsal_doc")
    print("[PASS] foundation_python_dependency_visibility_rehearsal_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
