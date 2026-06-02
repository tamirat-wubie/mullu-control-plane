#!/usr/bin/env python3
"""Validate the Foundation Mode private recovery boundary.

Purpose: keep recovery readiness public-safe while the owner prepares private
account-recovery evidence outside Git.
Governance scope: Foundation Mode, account recovery, secret exclusion,
deployment blockers, DNS publication blockers, and public-safe witness shape.
Dependencies: docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md,
examples/foundation_private_recovery_inventory.redacted.json, and
examples/foundation_recovery_witness.awaiting_evidence.json.
Invariants:
  - Validation is read-only.
  - The committed example is a redacted checklist, not a private inventory.
  - Provisioning, deployment, and DNS publication remain blocked.
  - Secret-shaped or provider-private fields are rejected.
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
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md"
DEFAULT_EXAMPLE_PATH = REPO_ROOT / "examples" / "foundation_private_recovery_inventory.redacted.json"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "foundation_recovery_witness.awaiting_evidence.json"

EXPECTED_INVENTORY_ID = "foundation_private_recovery_inventory.redacted.v1"
EXPECTED_WITNESS_ID = "foundation_recovery_witness.awaiting_evidence.v1"
EXPECTED_PRIVATE_LOCATION_REF = "outside_git_private_operator_record"
EXPECTED_ENTRY_IDS = (
    "cloud_account_recovery",
    "source_account_recovery",
    "workspace_email_recovery",
    "domain_registrar_recovery",
    "dns_provider_recovery",
    "password_manager_recovery",
    "offline_backup_recovery",
    "billing_renewal_recovery",
)
EXPECTED_PROMOTION_BLOCKERS = (
    "private_recovery_inventory_missing",
    "cloud_account_recovery_awaiting_evidence",
    "source_account_recovery_awaiting_evidence",
    "workspace_email_recovery_awaiting_evidence",
    "domain_registrar_recovery_awaiting_evidence",
    "dns_provider_recovery_awaiting_evidence",
    "password_manager_recovery_awaiting_evidence",
    "offline_backup_recovery_awaiting_evidence",
    "billing_renewal_recovery_awaiting_evidence",
)
EXPECTED_ROOT_KEYS = {
    "entries",
    "inventory_id",
    "must_not_store_in_git",
    "next_action",
    "private_inventory_location_ref",
    "promotion_rule",
    "schema_version",
    "scope",
    "solver_outcome",
    "status",
}
EXPECTED_WITNESS_ROOT_KEYS = {
    "api_provisioning_allowed",
    "confirmed_at_utc",
    "deployment_allowed",
    "dns_publication_allowed",
    "manual_confirmation_required",
    "next_action",
    "private_inventory_content_stored_in_git",
    "private_inventory_state",
    "promotion_blockers",
    "schema_version",
    "solver_outcome",
    "status",
    "witness_id",
    "witnesses",
}
EXPECTED_ENTRY_KEYS = {
    "evidence_state",
    "item_id",
    "next_action",
    "private_value_stored_outside_git",
    "public_label",
    "public_safe_note",
}
EXPECTED_WITNESS_ENTRY_KEYS = {
    "private_value_present",
    "public_evidence_ref",
    "state",
    "witness_id",
}
EXPECTED_PROMOTION_RULE_KEYS = {
    "api_provisioning_allowed",
    "deployment_allowed",
    "dns_publication_allowed",
    "ready_status",
    "requires_all_entries_confirmed",
}
REQUIRED_MUST_NOT_STORE = {
    "recovery_code_values",
    "password_values",
    "provider_account_ids",
    "dns_target_values",
    "billing_details",
    "private_storage_paths",
    "api_tokens",
    "session_exports",
    "private_keys",
}
REQUIRED_DOC_PHRASES = (
    "Foundation Private Recovery Boundary",
    "Descriptor: [`../examples/foundation_private_recovery_inventory.redacted.json`]",
    "Public-safe witness: [`../examples/foundation_recovery_witness.awaiting_evidence.json`]",
    "Rule: Recovery evidence is a prerequisite for deployment, not deployment evidence.",
    "No secret values are permitted in Git.",
    "Private inventory remains outside this repository.",
    "Do not store recovery codes, passwords, provider account IDs, DNS targets,",
    "Public-safe state is `AwaitingEvidence` until the operator completes the private",
    "The committed public-safe witness is an AwaitingEvidence template, not",
    "python scripts/validate_foundation_private_recovery_boundary.py",
)
FORBIDDEN_VALUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url_value", re.compile(r"https?://", re.IGNORECASE)),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]+")),
    ("cloud_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key_material", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("assignment_secret", re.compile(r"\b(?:password|secret|token|api[_-]?key)\s*=", re.IGNORECASE)),
    ("card_shaped_value", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
)


@dataclass(frozen=True, slots=True)
class PrivateRecoveryFinding:
    """One deterministic private recovery boundary validation finding."""

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
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_doc_text(text: str) -> list[PrivateRecoveryFinding]:
    """Return findings for missing private recovery documentation anchors."""

    findings: list[PrivateRecoveryFinding] = []
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in text:
            findings.append(
                PrivateRecoveryFinding(
                    "foundation_private_recovery_doc_phrase_missing",
                    f"private recovery boundary doc missing required phrase: {phrase}",
                )
            )
    return findings


def validate_inventory(payload: dict[str, Any]) -> list[PrivateRecoveryFinding]:
    """Return findings for redacted private recovery inventory violations."""

    findings: list[PrivateRecoveryFinding] = []
    findings.extend(validate_root_contract(payload))
    findings.extend(validate_entry_contract(payload.get("entries")))
    findings.extend(validate_promotion_rule(payload.get("promotion_rule")))
    findings.extend(validate_must_not_store(payload.get("must_not_store_in_git")))
    findings.extend(validate_forbidden_value_patterns(payload))
    return findings


def validate_recovery_witness(payload: dict[str, Any]) -> list[PrivateRecoveryFinding]:
    """Return findings for public-safe recovery witness violations."""

    findings: list[PrivateRecoveryFinding] = []
    findings.extend(validate_witness_root_contract(payload))
    findings.extend(validate_witness_entries(payload.get("witnesses")))
    findings.extend(validate_forbidden_value_patterns(payload))
    return findings


def validate_root_contract(payload: dict[str, Any]) -> list[PrivateRecoveryFinding]:
    """Return findings for root-level public-safe inventory contract drift."""

    findings: list[PrivateRecoveryFinding] = []
    observed_keys = set(payload)
    if observed_keys != EXPECTED_ROOT_KEYS:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )
    if payload.get("inventory_id") != EXPECTED_INVENTORY_ID:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_inventory_id_invalid",
                f"inventory_id must be {EXPECTED_INVENTORY_ID}",
            )
        )
    if payload.get("schema_version") != 1:
        findings.append(PrivateRecoveryFinding("private_recovery_schema_version_invalid", "schema_version must be 1"))
    if payload.get("scope") != "public_safe_recovery_boundary":
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_scope_invalid",
                "scope must be public_safe_recovery_boundary",
            )
        )
    if payload.get("status") != "AwaitingEvidence":
        findings.append(PrivateRecoveryFinding("private_recovery_status_invalid", "status must be AwaitingEvidence"))
    if payload.get("solver_outcome") != "AwaitingEvidence":
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_solver_outcome_invalid",
                "solver_outcome must be AwaitingEvidence",
            )
        )
    if payload.get("private_inventory_location_ref") != EXPECTED_PRIVATE_LOCATION_REF:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_location_ref_invalid",
                f"private_inventory_location_ref must be {EXPECTED_PRIVATE_LOCATION_REF}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "outside Git" not in next_action:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_next_action_invalid",
                "next_action must point the operator outside Git",
            )
        )
    return findings


def validate_witness_root_contract(payload: dict[str, Any]) -> list[PrivateRecoveryFinding]:
    """Return findings for public-safe witness root contract drift."""

    findings: list[PrivateRecoveryFinding] = []
    if set(payload) != EXPECTED_WITNESS_ROOT_KEYS:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_witness_root_keys_invalid",
                f"witness root keys must be: {', '.join(sorted(EXPECTED_WITNESS_ROOT_KEYS))}",
            )
        )
    expected_values = {
        "witness_id": EXPECTED_WITNESS_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "private_inventory_state": "AwaitingEvidence",
        "private_inventory_content_stored_in_git": False,
        "manual_confirmation_required": True,
        "api_provisioning_allowed": False,
        "deployment_allowed": False,
        "dns_publication_allowed": False,
        "confirmed_at_utc": None,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_witness_value_invalid",
                    f"witness.{key} must be {expected_value!r}",
                )
            )
    if tuple(payload.get("promotion_blockers", ())) != EXPECTED_PROMOTION_BLOCKERS:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_witness_blockers_invalid",
                f"promotion_blockers must be: {', '.join(EXPECTED_PROMOTION_BLOCKERS)}",
            )
        )
    next_action = payload.get("next_action")
    if not isinstance(next_action, str) or "outside Git" not in next_action:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_witness_next_action_invalid",
                "witness.next_action must point the operator outside Git",
            )
        )
    return findings


def validate_entry_contract(entries: object) -> list[PrivateRecoveryFinding]:
    """Return findings for redacted inventory entry contract drift."""

    findings: list[PrivateRecoveryFinding] = []
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return [PrivateRecoveryFinding("private_recovery_entries_invalid", "entries must be a list of objects")]
    observed_entry_ids = tuple(entry.get("item_id") for entry in entries)
    if observed_entry_ids != EXPECTED_ENTRY_IDS:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_entry_ids_invalid",
                f"entry ids must be: {', '.join(EXPECTED_ENTRY_IDS)}",
            )
        )
    if len(set(observed_entry_ids)) != len(observed_entry_ids):
        findings.append(PrivateRecoveryFinding("private_recovery_entry_duplicate", "entry ids must be unique"))
    for entry in entries:
        entry_id = str(entry.get("item_id", "<missing>"))
        if set(entry) != EXPECTED_ENTRY_KEYS:
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_entry_keys_invalid",
                    f"{entry_id} entry keys must be: {', '.join(sorted(EXPECTED_ENTRY_KEYS))}",
                )
            )
        if entry.get("evidence_state") != "AwaitingEvidence":
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_entry_state_invalid",
                    f"{entry_id} evidence_state must be AwaitingEvidence",
                )
            )
        if entry.get("private_value_stored_outside_git") is not False:
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_private_value_state_invalid",
                    f"{entry_id} private_value_stored_outside_git must be false in the redacted example",
                )
            )
        for text_field in ("public_label", "public_safe_note", "next_action"):
            if not isinstance(entry.get(text_field), str) or not entry[text_field].strip():
                findings.append(
                    PrivateRecoveryFinding(
                        "private_recovery_entry_text_invalid",
                        f"{entry_id} {text_field} must be a non-empty string",
                    )
                )
    return findings


def validate_witness_entries(witnesses: object) -> list[PrivateRecoveryFinding]:
    """Return findings for public-safe witness entry drift."""

    findings: list[PrivateRecoveryFinding] = []
    if not isinstance(witnesses, list) or not all(isinstance(witness, dict) for witness in witnesses):
        return [PrivateRecoveryFinding("private_recovery_witness_entries_invalid", "witnesses must be a list of objects")]
    observed_witness_ids = tuple(witness.get("witness_id") for witness in witnesses)
    if observed_witness_ids != EXPECTED_ENTRY_IDS:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_witness_ids_invalid",
                f"witness ids must be: {', '.join(EXPECTED_ENTRY_IDS)}",
            )
        )
    if len(set(observed_witness_ids)) != len(observed_witness_ids):
        findings.append(PrivateRecoveryFinding("private_recovery_witness_duplicate", "witness ids must be unique"))
    for witness in witnesses:
        witness_id = str(witness.get("witness_id", "<missing>"))
        if set(witness) != EXPECTED_WITNESS_ENTRY_KEYS:
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_witness_entry_keys_invalid",
                    f"{witness_id} witness keys must be: {', '.join(sorted(EXPECTED_WITNESS_ENTRY_KEYS))}",
                )
            )
        if witness.get("state") != "AwaitingEvidence":
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_witness_state_invalid",
                    f"{witness_id} state must be AwaitingEvidence",
                )
            )
        if witness.get("private_value_present") is not False:
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_witness_private_value_invalid",
                    f"{witness_id} private_value_present must be false",
                )
            )
        if witness.get("public_evidence_ref") != "outside_git_manual_confirmation_pending":
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_witness_evidence_ref_invalid",
                    f"{witness_id} public_evidence_ref must stay pending in the committed template",
                )
            )
    return findings


def validate_promotion_rule(promotion_rule: object) -> list[PrivateRecoveryFinding]:
    """Return findings for blocked promotion rule contract drift."""

    if not isinstance(promotion_rule, dict):
        return [PrivateRecoveryFinding("private_recovery_promotion_rule_invalid", "promotion_rule must be an object")]
    findings: list[PrivateRecoveryFinding] = []
    if set(promotion_rule) != EXPECTED_PROMOTION_RULE_KEYS:
        findings.append(
            PrivateRecoveryFinding(
                "private_recovery_promotion_rule_keys_invalid",
                f"promotion_rule keys must be: {', '.join(sorted(EXPECTED_PROMOTION_RULE_KEYS))}",
            )
        )
    expected_values = {
        "api_provisioning_allowed": False,
        "deployment_allowed": False,
        "dns_publication_allowed": False,
        "ready_status": "ReadyForProvisioning",
        "requires_all_entries_confirmed": True,
    }
    for key, expected_value in expected_values.items():
        if promotion_rule.get(key) != expected_value:
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_promotion_rule_value_invalid",
                    f"promotion_rule.{key} must be {expected_value!r}",
                )
            )
    return findings


def validate_must_not_store(values: object) -> list[PrivateRecoveryFinding]:
    """Return findings for missing forbidden private material classes."""

    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return [
            PrivateRecoveryFinding(
                "private_recovery_must_not_store_invalid",
                "must_not_store_in_git must be a list of strings",
            )
        ]
    observed = set(values)
    missing_values = sorted(REQUIRED_MUST_NOT_STORE - observed)
    if missing_values:
        return [
            PrivateRecoveryFinding(
                "private_recovery_must_not_store_missing",
                f"must_not_store_in_git missing values: {', '.join(missing_values)}",
            )
        ]
    return []


def validate_forbidden_value_patterns(payload: dict[str, Any]) -> list[PrivateRecoveryFinding]:
    """Return findings for URL, token, card, or key-shaped values."""

    serialized_payload = json.dumps(payload, sort_keys=True)
    findings: list[PrivateRecoveryFinding] = []
    for rule_id, pattern in FORBIDDEN_VALUE_PATTERNS:
        if pattern.search(serialized_payload):
            findings.append(
                PrivateRecoveryFinding(
                    "private_recovery_forbidden_value_pattern",
                    f"redacted inventory contains forbidden value pattern: {rule_id}",
                )
            )
    return findings


def validate_foundation_private_recovery_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    example_path: Path = DEFAULT_EXAMPLE_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[PrivateRecoveryFinding]:
    """Validate the Foundation Mode private recovery boundary artifacts."""

    doc_text = load_text(doc_path, "private recovery boundary doc")
    example_payload = load_json_object(example_path, "redacted private recovery inventory")
    witness_payload = load_json_object(witness_path, "public-safe recovery witness")
    return [
        *validate_doc_text(doc_text),
        *validate_inventory(example_payload),
        *validate_recovery_witness(witness_payload),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate private recovery boundary artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Foundation Mode private recovery boundary artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_private_recovery_boundary(args.doc, args.example, args.witness)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] foundation_private_recovery_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] foundation_private_recovery_doc")
    print("[PASS] foundation_private_recovery_inventory")
    print("[PASS] foundation_private_recovery_witness")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
