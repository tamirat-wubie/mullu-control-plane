"""Gateway GitHub check-run write receipt tests.

Purpose: verify check-run write planning is hash-bound, schema-backed, and
non-live unless an external GitHub App execution receipt is bound.
Governance scope: repository/head identity, readiness evidence, payload hash,
approval refs, GitHub App installation boundary, response evidence, and secret
absence.
Dependencies: gateway.github_check_run_writer and check-run receipt schema.
Invariants:
  - Plan-only and dry-run modes do not write GitHub checks.
  - Write-approved mode requires external execution evidence.
  - The planner does not call GitHub or authenticate a request.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from gateway.github_check_run_writer import (
    GitHubCheckRunWriter,
    GitHubCheckRunWriteRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "github_check_run_write_receipt.schema.json"
HEAD_SHA = "a" * 40
HEX_DIGITS = set("0123456789abcdef")


def test_github_check_run_plan_only_builds_hash_bound_payload() -> None:
    receipt = GitHubCheckRunWriter().evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "planned"
    assert receipt.mode == "plan_only"
    assert receipt.endpoint == "/repos/tamirat-wubie/mullu-control-plane/check-runs"
    assert receipt.method == "POST"
    assert receipt.request_payload["name"] == "SDLC Governance Gate"
    assert receipt.request_payload["head_sha"] == HEAD_SHA
    assert receipt.request_payload["conclusion"] == "success"
    assert receipt.request_payload_hash
    assert len(receipt.request_payload_hash) == 64
    assert set(receipt.request_payload_hash) <= HEX_DIGITS
    assert len(receipt.receipt_hash) == 64
    assert set(receipt.receipt_hash) <= HEX_DIGITS
    assert receipt.external_write_admitted is False
    assert receipt.network_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.metadata["payload_hash_bound"] is True


def test_github_check_run_dry_run_rejects_response_evidence() -> None:
    receipt = GitHubCheckRunWriter().evaluate(
        replace(
            _request(mode="dry_run"),
            execution_receipt_ref="receipt://github/check-run/execution-1",
            response_check_run_id="12345",
            response_payload_hash="sha256:" + ("b" * 64),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "non_write_execution_receipt_forbidden" in receipt.blocked_reasons
    assert "non_write_response_check_run_id_forbidden" in receipt.blocked_reasons
    assert "non_write_response_payload_hash_forbidden" in receipt.blocked_reasons
    assert "github_check_run_write_block" in receipt.required_controls
    assert receipt.external_write_admitted is False
    assert receipt.metadata["github_api_not_called"] is True


def test_github_check_run_write_approved_requires_github_app_execution_receipt() -> None:
    receipt = GitHubCheckRunWriter().evaluate(_request(mode="write_approved"))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "approval_ref_required" in receipt.blocked_reasons
    assert "installation_id_required" in receipt.blocked_reasons
    assert "execution_receipt_ref_required" in receipt.blocked_reasons
    assert "response_check_run_id_required" in receipt.blocked_reasons
    assert "response_payload_hash_required" in receipt.blocked_reasons
    assert "github_app_execution_receipt" in receipt.required_controls
    assert receipt.external_write_admitted is False


def test_github_check_run_write_approved_binds_external_execution_receipt() -> None:
    receipt = GitHubCheckRunWriter().evaluate(
        replace(
            _request(mode="write_approved"),
            installation_id="987654",
            approval_ref="approval://github-check-run/write-1",
            execution_receipt_ref="receipt://github-app/check-run/write-1",
            response_check_run_id="12345",
            response_payload_hash="sha256:" + ("c" * 64),
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "write_receipt_bound"
    assert receipt.external_write_admitted is True
    assert receipt.approval_ref == "approval://github-check-run/write-1"
    assert receipt.installation_id == "987654"
    assert receipt.execution_receipt_ref == "receipt://github-app/check-run/write-1"
    assert receipt.response_check_run_id == "12345"
    assert receipt.response_payload_hash == "sha256:" + ("c" * 64)
    assert len(receipt.receipt_hash) == 64
    assert set(receipt.receipt_hash) <= HEX_DIGITS
    assert receipt.blocked_reasons == []
    assert receipt.network_call_performed is False
    assert receipt.request_authentication_performed is False
    assert receipt.metadata["external_write_admitted"] is True


def test_github_check_run_rejects_secret_value_disclosure() -> None:
    receipt = GitHubCheckRunWriter().evaluate(
        replace(
            _request(),
            metadata={"debug_token": "ghp_" + ("a" * 32)},
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "secret_values_disclosed" in receipt.blocked_reasons
    assert receipt.metadata["secret_absence_verified"] is False
    assert receipt.external_write_admitted is False
    assert receipt.network_call_performed is False


def test_github_check_run_completed_status_requires_conclusion() -> None:
    receipt = GitHubCheckRunWriter().evaluate(replace(_request(), conclusion=""))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert "completed_check_run_conclusion_required" in receipt.blocked_reasons
    assert receipt.request_payload["status"] == "completed"
    assert "conclusion" not in receipt.request_payload
    assert receipt.external_write_admitted is False


def _request(*, mode: str = "plan_only") -> GitHubCheckRunWriteRequest:
    return GitHubCheckRunWriteRequest(
        request_id="github-check-run-write-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        repository_owner="tamirat-wubie",
        repository_name="mullu-control-plane",
        head_sha=HEAD_SHA,
        check_name="SDLC Governance Gate",
        check_status="completed",
        conclusion="success",
        output_title="SDLC Governance Gate",
        output_summary="All governed SDLC checks passed.",
        output_text="Evidence refs are bound in the receipt.",
        mode=mode,
        evidence_refs=["proof://sdlc/governance-gate/receipt-1"],
        details_url="https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/1",
        external_id="sdlc-governance-gate-command-1",
    )
