"""Purpose: verify the durable Gmail connector runtime planning boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_durable_gmail_connector_runtime_plan.
Invariants:
  - Durable OAuth read-only probing requires provider witnesses and freshness.
  - Tenant/mailbox binding requires its own redacted account-binding receipt.
  - Repository artifacts do not serialize secret values.
  - Write-capable Gmail operations remain approval-gated.
"""

from __future__ import annotations

import copy
import json

from scripts import validate_durable_gmail_connector_runtime_plan as validator
from scripts.validate_sdlc_artifact import load_json_object, validate_artifact_record


def test_durable_gmail_connector_runtime_plan_validates() -> None:
    report = validator.build_validation_report()

    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["error_count"] == 0
    assert report["check_count"] == 13
    assert report["plan_path"] == "docs/64_durable_gmail_connector_runtime_plan.md"


def test_requirement_artifact_keeps_external_mutation_out_of_scope() -> None:
    requirement_record = load_json_object(validator.REQUIREMENT_PATH, "durable Gmail requirement")
    errors = validate_artifact_record("requirement", requirement_record)

    assert errors == []
    assert requirement_record["risk_class"] == "high"
    assert "no Google Cloud credential creation in this change" in requirement_record["non_goals"]
    assert "no OAuth consent-screen publication in this change" in requirement_record["non_goals"]
    assert "Google Cloud OAuth consent and credentials" in requirement_record["affected_surfaces"]
    assert any("narrowest documented scope" in item for item in requirement_record["constraints"])


def test_security_review_blocks_release_until_oauth_witnesses_exist() -> None:
    security_review_record = load_json_object(validator.SECURITY_REVIEW_PATH, "durable Gmail security review")
    errors = validate_artifact_record("security_review", security_review_record)
    finding_ids = {finding["finding_id"] for finding in security_review_record["findings"]}

    assert errors == []
    assert security_review_record["release_blocked"] is True
    assert security_review_record["residual_risk"] == "high"
    assert validator.BLOCKING_FINDING_ID in finding_ids
    assert {"auth", "external_api", "secrets", "policy", "receipts", "audit"}.issubset(
        set(security_review_record["impact_categories"])
    )


def test_validator_rejects_release_unblock_overclaim() -> None:
    security_review_record = load_json_object(validator.SECURITY_REVIEW_PATH, "durable Gmail security review")
    invalid_security_review = copy.deepcopy(security_review_record)
    invalid_security_review["release_blocked"] = False
    invalid_security_review["residual_risk"] = "low"
    invalid_security_review["findings"] = []

    errors = validator._validate_security_boundary(invalid_security_review)

    assert "security review must block release until durable OAuth witnesses exist" in errors
    assert "security review residual risk must remain high while provider witnesses are missing" in errors
    assert any(validator.BLOCKING_FINDING_ID in error for error in errors)
    assert len(errors) >= 3


def test_validator_rejects_serialized_secret_markers() -> None:
    requirement_record = load_json_object(validator.REQUIREMENT_PATH, "durable Gmail requirement")
    security_review_record = load_json_object(validator.SECURITY_REVIEW_PATH, "durable Gmail security review")
    poisoned_requirement = copy.deepcopy(requirement_record)
    poisoned_requirement["constraints"].append("client_secret=must-not-appear")
    plan_text = validator.PLAN_PATH.read_text(encoding="utf-8")

    errors = validator._validate_no_secret_markers(plan_text, poisoned_requirement, security_review_record)
    serialized_payload = json.dumps(poisoned_requirement, sort_keys=True)

    assert "serialized secret marker is prohibited: client_secret=" in errors
    assert "client_secret=must-not-appear" in serialized_payload
    assert len(errors) == 1


def test_plan_terms_require_freshness_gate() -> None:
    plan_text = validator.PLAN_PATH.read_text(encoding="utf-8")
    stale_plan_text = plan_text.replace("validate_durable_gmail_oauth_live_receipt_freshness.py", "")
    stale_plan_text = stale_plan_text.replace("Evidence freshness", "")

    errors = validator._validate_plan_terms(stale_plan_text)

    assert "plan missing required term: validate_durable_gmail_oauth_live_receipt_freshness.py" in errors
    assert "plan missing required term: Evidence freshness" in errors
    assert len(errors) == 2


def test_plan_terms_require_account_binding_gate() -> None:
    plan_text = validator.PLAN_PATH.read_text(encoding="utf-8")
    stale_plan_text = plan_text.replace("produce_durable_gmail_account_binding_receipt.py", "")
    stale_plan_text = stale_plan_text.replace("validate_durable_gmail_account_binding_receipt.py", "")
    stale_plan_text = stale_plan_text.replace("source live receipt", "")
    stale_plan_text = stale_plan_text.replace("Tenant/mailbox binding", "")
    stale_plan_text = stale_plan_text.replace("account binding", "")

    errors = validator._validate_plan_terms(stale_plan_text)

    assert "plan missing required term: produce_durable_gmail_account_binding_receipt.py" in errors
    assert "plan missing required term: validate_durable_gmail_account_binding_receipt.py" in errors
    assert "plan missing required term: source live receipt" in errors
    assert "plan missing required term: Tenant/mailbox binding" in errors
    assert "plan missing required term: account binding" in errors


def test_plan_terms_require_revocation_recovery_rehearsal_gate() -> None:
    plan_text = validator.PLAN_PATH.read_text(encoding="utf-8")
    stale_plan_text = plan_text.replace("produce_durable_gmail_revocation_recovery_rehearsal_receipt.py", "")
    stale_plan_text = stale_plan_text.replace("validate_durable_gmail_revocation_recovery_rehearsal_receipt.py", "")

    errors = validator._validate_plan_terms(stale_plan_text)

    assert "plan missing required term: produce_durable_gmail_revocation_recovery_rehearsal_receipt.py" in errors
    assert "plan missing required term: validate_durable_gmail_revocation_recovery_rehearsal_receipt.py" in errors


def test_plan_terms_require_write_authority_rehearsal_gate() -> None:
    plan_text = validator.PLAN_PATH.read_text(encoding="utf-8")
    stale_plan_text = plan_text.replace("produce_durable_gmail_write_authority_rehearsal_receipt.py", "")
    stale_plan_text = stale_plan_text.replace("validate_durable_gmail_write_authority_rehearsal_receipt.py", "")
    stale_plan_text = stale_plan_text.replace("Gmail write-authority rehearsal", "")
    stale_plan_text = stale_plan_text.replace("send_without_approval_blocked", "")
    stale_plan_text = stale_plan_text.replace("draft/send split", "")

    errors = validator._validate_plan_terms(stale_plan_text)

    assert "plan missing required term: produce_durable_gmail_write_authority_rehearsal_receipt.py" in errors
    assert "plan missing required term: validate_durable_gmail_write_authority_rehearsal_receipt.py" in errors
    assert "plan missing required term: Gmail write-authority rehearsal" in errors
    assert "plan missing required term: send_without_approval_blocked" in errors
    assert "plan missing required term: draft/send split" in errors


def test_plan_terms_require_live_write_operator_input_request_gate() -> None:
    plan_text = validator.PLAN_PATH.read_text(encoding="utf-8")
    stale_plan_text = plan_text.replace("durable_gmail_live_write_operator_input_request.schema.json", "")
    stale_plan_text = stale_plan_text.replace("emit_durable_gmail_live_write_operator_input_request.py", "")
    stale_plan_text = stale_plan_text.replace("validate_durable_gmail_live_write_operator_input_request.py", "")
    stale_plan_text = stale_plan_text.replace("live write operator input request", "")

    errors = validator._validate_plan_terms(stale_plan_text)

    assert "plan missing required term: durable_gmail_live_write_operator_input_request.schema.json" in errors
    assert "plan missing required term: emit_durable_gmail_live_write_operator_input_request.py" in errors
    assert "plan missing required term: validate_durable_gmail_live_write_operator_input_request.py" in errors
    assert "plan missing required term: live write operator input request" in errors
