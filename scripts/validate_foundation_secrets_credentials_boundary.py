#!/usr/bin/env python3
"""Validate the Foundation Mode secrets/credentials boundary.

Purpose: keep secrets and credentials preparation local while real secret
storage, credential activation, provider binding, key creation, external calls,
and deployment claims remain blocked.
Governance scope: Foundation Mode, secrets posture, credential posture,
public-safe planning witness, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md and
examples/foundation_secrets_credentials_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The witness records local secrets/credentials planning only.
  - No real secret storage, credential activation, provider binding, private
    value, external call, or deployment claim is allowed.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md"
DEFAULT_PACKET_PATH = REPO_ROOT / "examples" / "foundation_secrets_credentials_witness.awaiting_evidence.json"

EXPECTED_WITNESS_ID = "foundation_secrets_credentials_witness.awaiting_evidence.v1"
EXPECTED_BLOCKED_CLAIMS = (
    "real secret storage",
    "credential activation",
    "provider account binding",
    "API key creation",
    "OAuth app creation",
    "service account creation",
    "environment file commit",
    "private key storage",
    "secret rotation readiness",
    "external call readiness",
    "deployment readiness",
)
EXPECTED_SURFACES = (
    ("credential_inventory_draft", "local_draft", "AwaitingEvidence"),
    ("environment_variable_plan", "local_draft", "AwaitingEvidence"),
    ("provider_access_questions", "local_draft", "AwaitingEvidence"),
    ("api_key_questions", "local_draft", "AwaitingEvidence"),
    ("oauth_app_questions", "local_draft", "AwaitingEvidence"),
    ("service_account_questions", "local_draft", "AwaitingEvidence"),
    ("rotation_recovery_questions", "local_draft", "AwaitingEvidence"),
    ("secret_scan_checklist", "local_draft", "AwaitingEvidence"),
)
EXPECTED_ROOT_KEYS = {
    "api_key_creation_allowed",
    "blocked_claims",
    "credential_activation_allowed",
    "credential_surfaces",
    "deployment_allowed",
    "env_file_commit_allowed",
    "external_call_allowed",
    "next_action",
    "oauth_app_creation_allowed",
    "private_key_storage_allowed",
    "provider_account_binding_allowed",
    "real_secret_storage_allowed",
    "schema_version",
    "secret_rotation_claimed",
    "service_account_creation_allowed",
    "solver_outcome",
    "status",
    "witness_id",
}
EXPECTED_SURFACE_KEYS = {
    "evidence_ref",
    "public_safe_note",
    "state",
    "surface_id",
    "surface_type",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Secrets Credentials Boundary",
    "Witness packet: [`../examples/foundation_secrets_credentials_witness.awaiting_evidence.json`]",
    "Rule: Secrets/credentials preparation is a local planning boundary, not permission to store or activate real credentials.",
    "No real-secret storage, credential activation, provider-account binding, API",
    "secrets_credentials_boundary_state=AwaitingEvidence",
    "real_secret_storage_allowed=false",
    "credential_activation_allowed=false",
    "api_key_creation_allowed=false",
    "deployment_allowed=false",
    "python scripts/validate_foundation_secrets_credentials_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("email_value", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("private_path", re.compile(r"\b[A-Za-z]:[\\/]|\\\\", re.IGNORECASE)),
    ("environment_assignment", re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*[^\s,;}]+")),
    ("secret_assignment", re.compile(r"\b(?:password|secret|token|api[_ -]?key|access[_ -]?key|private[_ -]?key|client[_ -]?secret|refresh[_ -]?token)\s*=", re.IGNORECASE)),
    ("bearer_assignment", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)),
    ("common_secret_prefix", re.compile(r"\b(?:sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{8,})")),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
)
FORBIDDEN_PROMOTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("credentials_ready", re.compile(r"\bcredentials[- ]ready\b", re.IGNORECASE)),
    ("secrets_ready", re.compile(r"\bsecrets?\s+(?:are\s+)?ready\b", re.IGNORECASE)),
    ("credential_active", re.compile(r"\bcredential\s+(?:is\s+)?(?:active|enabled|approved)\b", re.IGNORECASE)),
    ("api_key_created", re.compile(r"\bapi\s+key\s+(?:is\s+)?created\b", re.IGNORECASE)),
    ("oauth_app_active", re.compile(r"\boauth\s+app\s+(?:is\s+)?(?:active|enabled|approved)\b", re.IGNORECASE)),
    ("service_account_active", re.compile(r"\bservice\s+account\s+(?:is\s+)?(?:active|enabled|approved)\b", re.IGNORECASE)),
    ("external_calls_enabled", re.compile(r"\bexternal\s+calls?\s+(?:are\s+)?enabled\b", re.IGNORECASE)),
    ("rotation_complete", re.compile(r"\bsecret\s+rotation\s+(?:is\s+)?(?:complete|ready)\b", re.IGNORECASE)),
    ("env_file_committed", re.compile(r"\benv(?:ironment)?\s+file\s+(?:is\s+)?committed\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class SecretsCredentialsFinding:
    """One deterministic secrets/credentials boundary validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[SecretsCredentialsFinding]:
    """Return findings for missing secrets/credentials documentation anchors."""

    findings: list[SecretsCredentialsFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                SecretsCredentialsFinding(
                    "foundation_secrets_credentials_doc_phrase_missing",
                    f"secrets/credentials boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_packet(payload: dict[str, Any]) -> list[SecretsCredentialsFinding]:
    """Return findings for secrets/credentials witness drift."""

    findings: list[SecretsCredentialsFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_credential_surfaces(payload.get("credential_surfaces")))
    findings.extend(validate_forbidden_value_patterns(payload))
    findings.extend(validate_forbidden_promotion_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[SecretsCredentialsFinding]:
    """Return findings for root-level secrets/credentials witness drift."""

    findings: list[SecretsCredentialsFinding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            SecretsCredentialsFinding(
                "secrets_credentials_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "real_secret_storage_allowed": False,
        "credential_activation_allowed": False,
        "provider_account_binding_allowed": False,
        "api_key_creation_allowed": False,
        "oauth_app_creation_allowed": False,
        "service_account_creation_allowed": False,
        "env_file_commit_allowed": False,
        "private_key_storage_allowed": False,
        "secret_rotation_claimed": False,
        "external_call_allowed": False,
        "deployment_allowed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_root_value_invalid",
                    f"{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            SecretsCredentialsFinding(
                "secrets_credentials_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "do not create" not in next_action:
        findings.append(
            SecretsCredentialsFinding(
                "secrets_credentials_next_action_invalid",
                "next_action must preserve the closed credential boundary",
            )
        )
    return findings


def validate_credential_surfaces(credential_surfaces: object) -> list[SecretsCredentialsFinding]:
    """Return findings for secrets/credentials surface witness drift."""

    findings: list[SecretsCredentialsFinding] = []
    if not isinstance(credential_surfaces, list) or not all(
        isinstance(surface, dict) for surface in credential_surfaces
    ):
        return [
            SecretsCredentialsFinding(
                "secrets_credentials_surfaces_invalid",
                "credential_surfaces must be a list of objects",
            )
        ]
    observed_surfaces = tuple(
        (surface.get("surface_id"), surface.get("surface_type"), surface.get("state"))
        for surface in credential_surfaces
    )
    if observed_surfaces != EXPECTED_SURFACES:
        findings.append(
            SecretsCredentialsFinding(
                "secrets_credentials_surface_inventory_invalid",
                "secrets/credentials surface inventory does not match the Foundation Mode credential set",
            )
        )
    surface_ids = [surface.get("surface_id") for surface in credential_surfaces]
    if len(set(surface_ids)) != len(surface_ids):
        findings.append(SecretsCredentialsFinding("secrets_credentials_surface_duplicate", "surface ids must be unique"))
    for surface in credential_surfaces:
        surface_id = str(surface.get("surface_id", "<missing>"))
        if set(surface) != EXPECTED_SURFACE_KEYS:
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_surface_keys_invalid",
                    f"{surface_id} surface keys must be: {', '.join(sorted(EXPECTED_SURFACE_KEYS))}",
                )
            )
        if surface.get("state") != "AwaitingEvidence":
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_surface_state_invalid",
                    f"{surface_id} state must be AwaitingEvidence",
                )
            )
        if surface.get("evidence_ref") != "manual_preparation_pending":
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_surface_evidence_invalid",
                    f"{surface_id} evidence_ref must stay manual_preparation_pending in the committed packet",
                )
            )
        if not isinstance(surface.get("public_safe_note"), str) or not surface["public_safe_note"].strip():
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_surface_note_invalid",
                    f"{surface_id} public_safe_note must be a non-empty string",
                )
            )
    return findings


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[SecretsCredentialsFinding]:
    """Return findings for URL, email, private path, assignment, key, token, or private-key values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SecretsCredentialsFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_forbidden_private_value_pattern",
                    f"secrets/credentials witness contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_forbidden_promotion_patterns(payload: dict[str, Any]) -> list[SecretsCredentialsFinding]:
    """Return findings if the witness drifts into secrets/credentials readiness claims."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[SecretsCredentialsFinding] = []
    for rule_id, pattern in FORBIDDEN_PROMOTION_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                SecretsCredentialsFinding(
                    "secrets_credentials_forbidden_promotion_phrase",
                    f"secrets/credentials witness contains forbidden promotion pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_secrets_credentials_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[SecretsCredentialsFinding]:
    """Validate the Foundation Mode secrets/credentials boundary artifacts."""

    doc_text = load_text(doc_path, "secrets/credentials boundary doc")
    packet_payload = load_json_object(packet_path, "secrets/credentials witness packet")
    return [
        *validate_doc_text(doc_text),
        *validate_packet(packet_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate secrets/credentials boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode secrets/credentials boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_secrets_credentials_boundary(args.doc, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_secrets_credentials_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_secrets_credentials_doc")
    print("[PASS] foundation_secrets_credentials_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
