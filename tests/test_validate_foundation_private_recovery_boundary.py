"""Tests for the Foundation Mode private recovery boundary validator.

Purpose: prove recovery readiness stays public-safe while the owner prepares
private account-recovery evidence outside Git.
Governance scope: Foundation Mode, account recovery, secret exclusion,
deployment blockers, and public-safe witness shape.
Dependencies: scripts.validate_foundation_private_recovery_boundary.
Invariants: the redacted example keeps provisioning blocked and rejects secret
fields, private paths, URL values, token-shaped values, and promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_private_recovery_boundary import (  # noqa: E402
    DEFAULT_EXAMPLE_PATH,
    DEFAULT_WITNESS_PATH,
    EXPECTED_ENTRY_IDS,
    EXPECTED_INVENTORY_ID,
    EXPECTED_PROMOTION_BLOCKERS,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_private_recovery_boundary,
    validate_inventory,
    validate_recovery_witness,
)


def test_foundation_private_recovery_boundary_artifacts_pass() -> None:
    assert validate_foundation_private_recovery_boundary() == []


def test_redacted_inventory_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_EXAMPLE_PATH, "redacted inventory")

    assert payload["inventory_id"] == EXPECTED_INVENTORY_ID
    assert tuple(entry["item_id"] for entry in payload["entries"]) == EXPECTED_ENTRY_IDS
    assert payload["promotion_rule"]["api_provisioning_allowed"] is False
    assert payload["promotion_rule"]["dns_publication_allowed"] is False
    assert payload["promotion_rule"]["deployment_allowed"] is False


def test_recovery_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "recovery witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(witness["witness_id"] for witness in payload["witnesses"]) == EXPECTED_ENTRY_IDS
    assert tuple(payload["promotion_blockers"]) == EXPECTED_PROMOTION_BLOCKERS
    assert payload["api_provisioning_allowed"] is False
    assert payload["dns_publication_allowed"] is False
    assert payload["deployment_allowed"] is False


def test_inventory_rejects_secret_field_addition() -> None:
    payload = load_json_object(DEFAULT_EXAMPLE_PATH, "redacted inventory")
    candidate = deepcopy(payload)
    candidate["entries"][0]["password"] = "do-not-store"

    findings = validate_inventory(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_entry_keys_invalid" for finding in findings)


def test_inventory_rejects_private_location_path() -> None:
    payload = load_json_object(DEFAULT_EXAMPLE_PATH, "redacted inventory")
    candidate = deepcopy(payload)
    candidate["private_inventory_location_ref"] = "C:/Users/operator/private/recovery.md"

    findings = validate_inventory(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_location_ref_invalid" for finding in findings)


def test_inventory_rejects_url_value() -> None:
    payload = load_json_object(DEFAULT_EXAMPLE_PATH, "redacted inventory")
    candidate = deepcopy(payload)
    candidate["entries"][0]["public_safe_note"] = "Store at https://private.example/recovery."

    findings = validate_inventory(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_forbidden_value_pattern" for finding in findings)


def test_inventory_rejects_token_shaped_value() -> None:
    payload = load_json_object(DEFAULT_EXAMPLE_PATH, "redacted inventory")
    candidate = deepcopy(payload)
    candidate["next_action"] = "do not store ghp_1234567890abcdef in Git"

    findings = validate_inventory(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_forbidden_value_pattern" for finding in findings)


def test_inventory_rejects_promotion_drift() -> None:
    payload = load_json_object(DEFAULT_EXAMPLE_PATH, "redacted inventory")
    candidate = deepcopy(payload)
    candidate["promotion_rule"]["api_provisioning_allowed"] = True

    findings = validate_inventory(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_promotion_rule_value_invalid" for finding in findings)


def test_witness_rejects_ready_status_without_validator_promotion() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "recovery witness")
    candidate = deepcopy(payload)
    candidate["status"] = "ReadyForProvisioning"

    findings = validate_recovery_witness(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_witness_value_invalid" for finding in findings)


def test_witness_rejects_private_evidence_ref() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "recovery witness")
    candidate = deepcopy(payload)
    candidate["witnesses"][0]["public_evidence_ref"] = "C:/Users/operator/private/recovery.md"

    findings = validate_recovery_witness(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_witness_evidence_ref_invalid" for finding in findings)


def test_witness_rejects_private_value_present() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "recovery witness")
    candidate = deepcopy(payload)
    candidate["witnesses"][0]["private_value_present"] = True

    findings = validate_recovery_witness(candidate)

    assert findings
    assert any(finding.rule_id == "private_recovery_witness_private_value_invalid" for finding in findings)
