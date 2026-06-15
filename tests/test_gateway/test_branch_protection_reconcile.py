"""Gateway branch-protection reconcile receipt tests.

Purpose: verify GitHub branch-protection reconciliation is hash-bound,
schema-backed, and non-live unless external token and action receipts are bound.
Governance scope: protected-branch policy, observed drift, REST payload hash,
approval refs, token-exchange refs, action-execution refs, response evidence,
and secret absence.
Dependencies: gateway.branch_protection_reconcile and reconcile receipt schema.
Invariants:
  - Plan-only and dry-run modes do not mutate GitHub branch protection.
  - Apply-approved mode requires token-exchange and action-execution evidence.
  - Policy drift is explicit and hash-bound into the reconcile plan.
  - Raw tokens, JWTs, and private keys are never accepted as receipt evidence.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.branch_protection_reconcile import (
    BranchProtectionObservedState,
    BranchProtectionPolicy,
    BranchProtectionReconcileRequest,
    BranchProtectionReconciler,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "github_branch_protection_reconcile_receipt.schema.json"
HEX_DIGITS = set("0123456789abcdef")
RESPONSE_HASH = "sha256:" + ("e" * 64)


def test_branch_protection_reconcile_noop_is_hash_bound() -> None:
    receipt = BranchProtectionReconciler().evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "noop"
    assert receipt.mode == "plan_only"
    assert receipt.endpoint == "/repos/tamirat-wubie/mullu-control-plane/branches/main/protection"
    assert receipt.method == "PUT"
    assert receipt.drift == []
    assert receipt.required_actions == ["noop_observed_protection_satisfies_policy"]
    assert len(receipt.policy_hash) == 64
    assert set(receipt.policy_hash) <= HEX_DIGITS
    assert len(receipt.request_payload_hash) == 64
    assert set(receipt.request_payload_hash) <= HEX_DIGITS
    assert len(receipt.plan_hash) == 64
    assert len(receipt.receipt_hash) == 64
    assert receipt.external_apply_admitted is False
    assert receipt.network_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_token_stored is False
    assert receipt.metadata["policy_hash_bound"] is True
    assert receipt.metadata["payload_hash_bound"] is True
    assert receipt.metadata["plan_hash_bound"] is True
    assert receipt.metadata["drift_detected"] is False


def test_branch_protection_reconcile_plan_reports_observed_drift() -> None:
    receipt = BranchProtectionReconciler().evaluate(
        replace(
            _request(),
            observed_state=_observed_drift(),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.missing_required_checks == [
        "Python Tests (ubuntu-latest, Python 3.13)",
        "SDLC Governance Gate",
        "Schema Validation",
    ]
    assert "missing_required_status_checks" in receipt.drift
    assert "admin_enforcement_disabled" in receipt.drift
    assert "insufficient_required_approving_reviews" in receipt.drift
    assert "code_owner_review_requirement_disabled" in receipt.drift
    assert "conversation_resolution_requirement_disabled" in receipt.drift
    assert "linear_history_requirement_disabled" in receipt.drift
    assert receipt.required_actions == [
        "put_branch_protection",
        "verify_branch_protection_after_apply",
        "retain_branch_protection_response_receipt",
    ]
    assert receipt.metadata["drift_detected"] is True
    assert receipt.external_apply_admitted is False


def test_branch_protection_reconcile_plan_marks_missing_observed_state() -> None:
    receipt = BranchProtectionReconciler().evaluate(replace(_request(), observed_state=None))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.observed_state is None
    assert receipt.missing_required_checks == _policy().required_status_checks
    assert receipt.drift == ["observed_branch_protection_state_missing"]
    assert "branch_protection_observed_state_gap" in receipt.required_controls
    assert receipt.metadata["observed_state_present"] is False
    assert receipt.metadata["drift_detected"] is True
    assert receipt.external_apply_admitted is False


def test_branch_protection_reconcile_dry_run_rejects_apply_evidence() -> None:
    receipt = BranchProtectionReconciler().evaluate(
        replace(
            _request(mode="dry_run"),
            approval_ref="approval://github/branch-protection/apply-1",
            token_exchange_receipt_ref="receipt://github-app/token-exchange-1",
            action_execution_receipt_ref="receipt://github/action-execution-1",
            response_status_code=200,
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "non_apply_approval_ref_forbidden" in receipt.blocked_reasons
    assert "non_apply_token_exchange_receipt_forbidden" in receipt.blocked_reasons
    assert "non_apply_action_execution_receipt_forbidden" in receipt.blocked_reasons
    assert "non_apply_response_status_forbidden" in receipt.blocked_reasons
    assert "non_apply_response_payload_hash_forbidden" in receipt.blocked_reasons
    assert "branch_protection_reconcile_block" in receipt.required_controls
    assert receipt.external_apply_admitted is False
    assert receipt.metadata["github_api_not_called"] is True


def test_branch_protection_apply_approved_requires_external_receipts() -> None:
    receipt = BranchProtectionReconciler().evaluate(
        replace(_request(mode="apply_approved"), observed_state=_observed_drift())
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "approval_ref_required" in receipt.blocked_reasons
    assert "token_exchange_receipt_ref_required" in receipt.blocked_reasons
    assert "action_execution_receipt_ref_required" in receipt.blocked_reasons
    assert "response_status_code_2xx_required" in receipt.blocked_reasons
    assert "response_payload_hash_required" in receipt.blocked_reasons
    assert "github_app_token_exchange_receipt" in receipt.required_controls
    assert "github_action_execution_receipt" in receipt.required_controls
    assert receipt.external_apply_admitted is False


def test_branch_protection_apply_approved_binds_external_action_receipt() -> None:
    receipt = BranchProtectionReconciler().evaluate(
        replace(
            _request(mode="apply_approved"),
            observed_state=_observed_drift(),
            approval_ref="approval://github/branch-protection/apply-1",
            token_exchange_receipt_ref="receipt://github-app/token-exchange-1",
            action_execution_receipt_ref="receipt://github/action-execution-1",
            response_status_code=200,
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "apply_receipt_bound"
    assert receipt.external_apply_admitted is True
    assert receipt.approval_ref == "approval://github/branch-protection/apply-1"
    assert receipt.token_exchange_receipt_ref == "receipt://github-app/token-exchange-1"
    assert receipt.action_execution_receipt_ref == "receipt://github/action-execution-1"
    assert receipt.response_status_code == 200
    assert receipt.response_payload_hash == RESPONSE_HASH
    assert receipt.blocked_reasons == []
    assert receipt.network_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_token_stored is False
    assert receipt.metadata["external_apply_admitted"] is True


def test_branch_protection_apply_approved_blocks_noop_apply() -> None:
    receipt = BranchProtectionReconciler().evaluate(
        replace(
            _request(mode="apply_approved"),
            approval_ref="approval://github/branch-protection/apply-1",
            token_exchange_receipt_ref="receipt://github-app/token-exchange-1",
            action_execution_receipt_ref="receipt://github/action-execution-1",
            response_status_code=200,
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.drift == []
    assert "branch_protection_drift_required_for_apply" in receipt.blocked_reasons
    assert "branch_protection_reconcile_block" in receipt.required_controls
    assert receipt.external_apply_admitted is False
    assert receipt.metadata["external_apply_admitted"] is False


def test_branch_protection_reconcile_rejects_secret_value_disclosure() -> None:
    receipt = BranchProtectionReconciler().evaluate(
        replace(
            _request(),
            metadata={"debug_installation_token": "ghs_" + ("b" * 32)},
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "secret_values_disclosed" in receipt.blocked_reasons
    assert receipt.metadata["secret_absence_verified"] is False
    assert receipt.external_apply_admitted is False
    assert receipt.raw_token_stored is False


def test_branch_protection_payload_uses_checks_objects() -> None:
    receipt = BranchProtectionReconciler().evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.request_payload["required_status_checks"]["strict"] is True
    assert receipt.request_payload["required_status_checks"]["checks"] == [
        {"context": "Python Tests (ubuntu-latest, Python 3.13)"},
        {"context": "Rust Tests"},
        {"context": "SDLC Governance Gate"},
        {"context": "Schema Validation"},
    ]
    assert receipt.request_payload["enforce_admins"] is True
    assert receipt.request_payload["required_pull_request_reviews"]["require_code_owner_reviews"] is True
    assert receipt.request_payload["allow_force_pushes"] is False
    assert receipt.request_payload["allow_deletions"] is False
    assert receipt.receipt_schema_ref == "urn:mullusi:schema:github-branch-protection-reconcile-receipt:1"


def _request(*, mode: str = "plan_only") -> BranchProtectionReconcileRequest:
    return BranchProtectionReconcileRequest(
        request_id="branch-protection-reconcile-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        policy=_policy(),
        observed_state=_observed_compliant(),
        mode=mode,
        evidence_refs=["proof://github/branch-protection/readiness-1"],
    )


def _policy() -> BranchProtectionPolicy:
    return BranchProtectionPolicy(
        policy_id="policy-main-protection-1",
        repository_owner="tamirat-wubie",
        repository_name="mullu-control-plane",
        branch_name="main",
        required_status_checks=[
            "Rust Tests",
            "Schema Validation",
            "Python Tests (ubuntu-latest, Python 3.13)",
            "SDLC Governance Gate",
        ],
    )


def _observed_compliant() -> BranchProtectionObservedState:
    return BranchProtectionObservedState(
        required_status_checks=[
            "Rust Tests",
            "Schema Validation",
            "Python Tests (ubuntu-latest, Python 3.13)",
            "SDLC Governance Gate",
        ],
        enforce_admins=True,
        required_approving_review_count=1,
        require_code_owner_reviews=True,
        require_conversation_resolution=True,
        require_linear_history=True,
    )


def _observed_drift() -> BranchProtectionObservedState:
    return BranchProtectionObservedState(
        required_status_checks=["Rust Tests"],
        enforce_admins=False,
        required_approving_review_count=0,
        require_code_owner_reviews=False,
        require_conversation_resolution=False,
        require_linear_history=False,
    )
