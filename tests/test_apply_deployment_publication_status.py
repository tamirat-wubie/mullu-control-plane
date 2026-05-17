"""Tests for evidence-gated deployment publication status application.

Purpose: prove public production health status is not mutated without a
published deployment witness and operator approval.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.apply_deployment_publication_status.
Invariants:
  - Dry-run validates without writing.
  - Status mutation requires operator approval.
  - Status mutation requires a schema-valid published witness.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.apply_deployment_publication_status import (
    apply_deployment_publication_status,
    main,
    write_deployment_publication_status_application,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_apply_deployment_publication_status_updates_verified_claim(tmp_path: Path) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    deployment_status.write_text(_deployment_status(), encoding="utf-8")
    witness_path.write_text(json.dumps(_published_witness()), encoding="utf-8")

    application = apply_deployment_publication_status(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
        operator_approval_ref="approval://deployment/publication/001",
        audited_at="2026-05-15",
    )
    updated_status = deployment_status.read_text(encoding="utf-8")

    assert application.errors == ()
    assert application.updated is True
    assert "**Deployment witness state:** `published`" in updated_status
    assert "**Public production health endpoint:** `https://gateway.example/health`" in updated_status
    assert "**Last audited:** 2026-05-15" in updated_status


def test_apply_deployment_publication_status_blocks_missing_approval(
    tmp_path: Path,
) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    original_status = _deployment_status()
    deployment_status.write_text(original_status, encoding="utf-8")
    witness_path.write_text(json.dumps(_published_witness()), encoding="utf-8")

    application = apply_deployment_publication_status(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
        operator_approval_ref="",
        audited_at="2026-05-15",
    )

    assert application.updated is False
    assert application.errors == ("operator approval reference required",)
    assert deployment_status.read_text(encoding="utf-8") == original_status
    assert application.public_health_endpoint == ""


def test_apply_deployment_publication_status_blocks_unpublished_witness(
    tmp_path: Path,
) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    deployment_status.write_text(_deployment_status(), encoding="utf-8")
    witness = _published_witness()
    witness["deployment_claim"] = "not-published"
    witness["steps"][1]["passed"] = False
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    application = apply_deployment_publication_status(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
        operator_approval_ref="approval://deployment/publication/001",
        audited_at="2026-05-15",
    )

    assert application.updated is False
    assert any("deployment_claim 'not-published' != 'published'" in error for error in application.errors)
    assert any("witness step failed" in error for error in application.errors)
    assert "**Deployment witness state:** `not-published`" in deployment_status.read_text(
        encoding="utf-8",
    )


def test_apply_deployment_publication_status_dry_run_does_not_write(
    tmp_path: Path,
) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    original_status = _deployment_status()
    deployment_status.write_text(original_status, encoding="utf-8")
    witness_path.write_text(json.dumps(_published_witness()), encoding="utf-8")

    application = apply_deployment_publication_status(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
        operator_approval_ref="approval://deployment/publication/001",
        audited_at="2026-05-15",
        dry_run=True,
    )

    assert application.errors == ()
    assert application.updated is False
    assert application.dry_run is True
    assert deployment_status.read_text(encoding="utf-8") == original_status


def test_apply_deployment_publication_status_writes_receipt(tmp_path: Path) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    receipt_path = tmp_path / "public_production_health_declaration.json"
    deployment_status.write_text(_deployment_status(), encoding="utf-8")
    witness_path.write_text(json.dumps(_published_witness()), encoding="utf-8")

    application = apply_deployment_publication_status(
        deployment_status_path=deployment_status,
        witness_path=witness_path,
        operator_approval_ref="approval://deployment/publication/001",
        audited_at="2026-05-15",
        dry_run=True,
    )
    write_deployment_publication_status_application(application, receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema = _load_schema(Path("schemas/public_production_health_declaration.schema.json"))

    assert _validate_schema_instance(schema, receipt) == []
    assert receipt["errors"] == []
    assert receipt["dry_run"] is True
    assert receipt["public_health_endpoint"] == "https://gateway.example/health"
    assert receipt["operator_approval_ref"] == "approval://deployment/publication/001"


def test_apply_deployment_publication_status_cli_json(tmp_path: Path, capsys) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    witness_path = tmp_path / "deployment_witness.json"
    deployment_status.write_text(_deployment_status(), encoding="utf-8")
    witness_path.write_text(json.dumps(_published_witness()), encoding="utf-8")

    exit_code = main(
        [
            "--deployment-status",
            str(deployment_status),
            "--witness",
            str(witness_path),
            "--operator-approval-ref",
            "approval://deployment/publication/001",
            "--audited-at",
            "2026-05-15",
            "--dry-run",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["errors"] == []
    assert payload["dry_run"] is True
    assert payload["deployment_witness_state"] == "published"


def _deployment_status() -> str:
    return "\n".join(
        (
            "# Deployment Status Witness",
            "",
            "**Last audited:** 2026-05-01",
            "**Deployment witness state:** `not-published`",
            "**Public production health endpoint:** `not-declared`",
            "",
        )
    )


def _published_witness() -> dict[str, object]:
    return {
        "witness_id": "deployment-witness-0123456789abcdef",
        "collected_at": "2026-05-15T00:00:00+00:00",
        "gateway_url": "https://gateway.example",
        "public_health_endpoint": "https://gateway.example/health",
        "health_http_status": 200,
        "health_response_digest": (
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        "deployment_claim": "published",
        "health_status": "healthy",
        "runtime_witness_status": "healthy",
        "signature_status": "verified",
        "conformance_status": "conformant",
        "conformance_signature_status": "verified",
        "latest_conformance_certificate_id": "conf-001",
        "latest_terminal_certificate_id": "terminal-001",
        "latest_command_event_hash": "event-hash-001",
        "runtime_witness_id": "runtime-witness-001",
        "runtime_environment": "pilot",
        "runtime_signature_key_id": "runtime-key-001",
        "runtime_responsibility_debt_clear": True,
        "authority_responsibility_debt_clear": True,
        "authority_pending_approval_chain_count": 0,
        "authority_overdue_approval_chain_count": 0,
        "authority_open_obligation_count": 0,
        "authority_overdue_obligation_count": 0,
        "authority_escalated_obligation_count": 0,
        "authority_unowned_high_risk_capability_count": 0,
        "steps": [
            {"name": "gateway health", "passed": True, "detail": "ok"},
            {"name": "gateway runtime witness", "passed": True, "detail": "ok"},
            {"name": "runtime conformance signature", "passed": True, "detail": "ok"},
        ],
        "errors": [],
    }
