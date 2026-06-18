"""Gateway GitHub action execution receipt tests.

Purpose: verify GitHub action execution planning is hash-bound, schema-backed,
and non-live unless external token and execution receipts are bound.
Governance scope: repository identity, token repository boundary, action
payload hash, approval refs, token-exchange refs, response evidence, and secret
absence.
Dependencies: gateway.github_action_execution and action execution schema.
Invariants:
  - Plan-only and dry-run modes do not execute GitHub REST actions.
  - Execute-approved mode requires token-exchange and external execution evidence.
  - Token plan repository identity must match the action repository identity.
  - Raw tokens, JWTs, and private keys are never accepted as receipt evidence.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.github_action_execution import (
    GitHubActionExecution,
    GitHubActionExecutionRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "github_action_execution_receipt.schema.json"
HEX_DIGITS = set("0123456789abcdef")
RESPONSE_HASH = "sha256:" + ("d" * 64)


def test_github_action_execution_plan_only_builds_hash_bound_payload() -> None:
    receipt = GitHubActionExecution().evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.mode == "plan_only"
    assert receipt.action_kind == "check_run_write"
    assert receipt.endpoint == "/repos/tamirat-wubie/mullu-control-plane/check-runs"
    assert receipt.method == "POST"
    assert receipt.request_payload["name"] == "SDLC Governance Gate"
    assert len(receipt.request_payload_hash) == 64
    assert set(receipt.request_payload_hash) <= HEX_DIGITS
    assert len(receipt.receipt_hash) == 64
    assert set(receipt.receipt_hash) <= HEX_DIGITS
    assert receipt.external_execution_admitted is False
    assert receipt.network_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_token_stored is False
    assert receipt.metadata["payload_hash_bound"] is True
    assert receipt.metadata["token_repository_match"] is True


def test_github_action_execution_dry_run_rejects_execution_evidence() -> None:
    receipt = GitHubActionExecution().evaluate(
        replace(
            _request(mode="dry_run"),
            approval_ref="approval://github-action/execute-1",
            token_exchange_receipt_ref="receipt://github-app/token-exchange-1",
            external_execution_receipt_ref="receipt://github/action-execution-1",
            response_status_code=201,
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "non_execute_approval_ref_forbidden" in receipt.blocked_reasons
    assert "non_execute_token_exchange_receipt_forbidden" in receipt.blocked_reasons
    assert "non_execute_external_receipt_forbidden" in receipt.blocked_reasons
    assert "non_execute_response_status_forbidden" in receipt.blocked_reasons
    assert "non_execute_response_payload_hash_forbidden" in receipt.blocked_reasons
    assert "github_action_execution_block" in receipt.required_controls
    assert receipt.external_execution_admitted is False
    assert receipt.metadata["github_api_not_called"] is True


def test_github_action_execute_approved_requires_token_and_external_receipts() -> None:
    receipt = GitHubActionExecution().evaluate(_request(mode="execute_approved"))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "approval_ref_required" in receipt.blocked_reasons
    assert "token_exchange_receipt_ref_required" in receipt.blocked_reasons
    assert "external_execution_receipt_ref_required" in receipt.blocked_reasons
    assert "response_status_code_2xx_required" in receipt.blocked_reasons
    assert "response_payload_hash_required" in receipt.blocked_reasons
    assert "github_app_token_exchange_receipt" in receipt.required_controls
    assert "github_external_action_execution_receipt" in receipt.required_controls
    assert receipt.external_execution_admitted is False


def test_github_action_execute_approved_binds_external_execution_receipt() -> None:
    receipt = GitHubActionExecution().evaluate(
        replace(
            _request(mode="execute_approved"),
            approval_ref="approval://github-action/execute-1",
            token_exchange_receipt_ref="receipt://github-app/token-exchange-1",
            external_execution_receipt_ref="receipt://github/action-execution-1",
            response_status_code=201,
            response_payload_hash=RESPONSE_HASH,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "execution_receipt_bound"
    assert receipt.external_execution_admitted is True
    assert receipt.approval_ref == "approval://github-action/execute-1"
    assert receipt.token_exchange_receipt_ref == "receipt://github-app/token-exchange-1"
    assert receipt.external_execution_receipt_ref == "receipt://github/action-execution-1"
    assert receipt.response_status_code == 201
    assert receipt.response_payload_hash == RESPONSE_HASH
    assert receipt.blocked_reasons == []
    assert receipt.network_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.raw_token_stored is False
    assert receipt.metadata["external_execution_admitted"] is True


def test_github_action_execution_blocks_token_plan_repository_mismatch() -> None:
    receipt = GitHubActionExecution().evaluate(
        replace(_request(), token_repository_name="other-repository")
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "token_plan_repository_mismatch" in receipt.blocked_reasons
    assert receipt.repository_name == "mullu-control-plane"
    assert receipt.token_repository_name == "other-repository"
    assert receipt.external_execution_admitted is False
    assert receipt.metadata["token_repository_match"] is False


def test_github_action_execution_rejects_secret_value_disclosure() -> None:
    receipt = GitHubActionExecution().evaluate(
        replace(
            _request(),
            metadata={"debug_installation_token": "ghs_" + ("a" * 32)},
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "secret_values_disclosed" in receipt.blocked_reasons
    assert receipt.metadata["secret_absence_verified"] is False
    assert receipt.external_execution_admitted is False
    assert receipt.raw_token_stored is False


def test_branch_protection_reconcile_action_is_endpoint_bound() -> None:
    receipt = GitHubActionExecution().evaluate(_branch_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.action_kind == "branch_protection_reconcile"
    assert receipt.method == "PUT"
    assert receipt.branch_name == "main"
    assert receipt.endpoint == "/repos/tamirat-wubie/mullu-control-plane/branches/main/protection"
    assert receipt.request_payload["enforce_admins"] is True
    assert "branch_protection_target_branch" in receipt.required_controls
    assert receipt.external_execution_admitted is False
    assert receipt.metadata["token_repository_match"] is True


def _request(*, mode: str = "plan_only") -> GitHubActionExecutionRequest:
    return GitHubActionExecutionRequest(
        request_id="github-action-execution-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        repository_owner="tamirat-wubie",
        repository_name="mullu-control-plane",
        token_repository_owner="tamirat-wubie",
        token_repository_name="mullu-control-plane",
        token_plan_ref="receipt://github-app/token-plan-1",
        action_kind="check_run_write",
        action_plan_ref="receipt://github/check-run/write-plan-1",
        request_payload={
            "name": "SDLC Governance Gate",
            "head_sha": "a" * 40,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": "SDLC Governance Gate",
                "summary": "All governed SDLC checks passed.",
            },
        },
        mode=mode,
        evidence_refs=["proof://github/action-execution/readiness-1"],
    )


def _branch_request() -> GitHubActionExecutionRequest:
    return replace(
        _request(),
        action_kind="branch_protection_reconcile",
        action_plan_ref="receipt://github/branch-protection/reconcile-plan-1",
        branch_name="main",
        request_payload={
            "required_status_checks": {
                "strict": True,
                "contexts": ["CI - Build Verification"],
            },
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
            },
        },
    )
