"""Tests for deployment upstream blocker receipt validation.

Purpose: prove upstream API/DNS blocker receipts are schema-backed and fail closed.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_deployment_upstream_blocker_receipt.
Invariants:
  - Public schema accepts ready and blocked receipts.
  - require-ready blocks AwaitingEvidence receipts.
  - Validation reports preserve bounded errors and next action.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_deployment_upstream_blocker_receipt import (  # noqa: E402
    emit_deployment_upstream_blocker_receipt,
    write_deployment_upstream_blocker_receipt,
)
from scripts.validate_deployment_upstream_blocker_receipt import (  # noqa: E402
    validate_deployment_upstream_blocker_receipt,
    write_deployment_upstream_blocker_validation_report,
)


def test_deployment_upstream_blocker_receipt_matches_public_schema(tmp_path: Path) -> None:
    receipt_path = _write_blocked_receipt(tmp_path)

    validation = validate_deployment_upstream_blocker_receipt(receipt_path=receipt_path)

    assert validation.valid is True
    assert validation.ready is False
    assert validation.errors == ()
    assert validation.next_action == "complete private recovery inventory outside Git"


def test_deployment_upstream_blocker_validation_can_require_ready(tmp_path: Path) -> None:
    receipt_path = _write_blocked_receipt(tmp_path)

    validation = validate_deployment_upstream_blocker_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "require ready: not-ready" in validation.errors
    assert "complete private recovery inventory outside Git" == validation.next_action


def test_deployment_upstream_blocker_validation_accepts_ready_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "deployment_upstream_blocker_receipt.json"
    receipt = emit_deployment_upstream_blocker_receipt(
        target_gateway_url="https://api.mullusi.com",
        upstream_repository="mullusi/mullusi-site",
        upstream_gate="api-production-readiness-gate",
        upstream_state="SolvedVerified",
        api_provisioning_allowed=True,
        dns_publication_allowed=True,
        blockers=(),
        evidence_refs=("upstream-recovery-witness",),
        next_actions=("continue with DNS target binding",),
        now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    write_deployment_upstream_blocker_receipt(receipt, receipt_path)

    validation = validate_deployment_upstream_blocker_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.errors == ()


def test_deployment_upstream_blocker_validation_rejects_url_host_drift(tmp_path: Path) -> None:
    receipt_path = _write_blocked_receipt(tmp_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["target_gateway_url"] = "https://gateway.mullusi.com"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_upstream_blocker_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert any("target_gateway_url" in error for error in validation.errors)
    assert any("schema" not in error.lower() for error in validation.errors)


def test_deployment_upstream_blocker_validation_report_writes_json(tmp_path: Path) -> None:
    receipt_path = _write_blocked_receipt(tmp_path)
    validation_path = tmp_path / "deployment_upstream_blocker_receipt_validation.json"
    validation = validate_deployment_upstream_blocker_receipt(receipt_path=receipt_path)

    written = write_deployment_upstream_blocker_validation_report(validation, validation_path)
    payload = json.loads(validation_path.read_text(encoding="utf-8"))

    assert written == validation_path
    assert payload["valid"] is True
    assert payload["ready"] is False
    assert payload["errors"] == []


def _write_blocked_receipt(tmp_path: Path) -> Path:
    receipt_path = tmp_path / "deployment_upstream_blocker_receipt.json"
    receipt = emit_deployment_upstream_blocker_receipt(
        target_gateway_url="https://api.mullusi.com",
        upstream_repository="mullusi/mullusi-site",
        upstream_gate="api-production-readiness-gate",
        upstream_state="AwaitingEvidence",
        api_provisioning_allowed=False,
        dns_publication_allowed=False,
        blockers=("private_recovery_inventory_missing", "runtime_host_not_provisioned"),
        evidence_refs=("issue-330-comment-4530008851",),
        next_actions=("complete private recovery inventory outside Git",),
        now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    write_deployment_upstream_blocker_receipt(receipt, receipt_path)
    return receipt_path
