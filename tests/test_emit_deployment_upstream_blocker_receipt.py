"""Tests for deployment upstream blocker receipt emission.

Purpose: prove upstream API/DNS blockers are captured without mutating DNS.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.emit_deployment_upstream_blocker_receipt.
Invariants:
  - Blocked receipts carry explicit blockers and next actions.
  - Ready receipts require no blockers and explicit API/DNS allowance.
  - Malformed gateway targets fail without serializing hidden state.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_deployment_upstream_blocker_receipt import (  # noqa: E402
    emit_deployment_upstream_blocker_receipt,
    main,
    write_deployment_upstream_blocker_receipt,
)


def test_deployment_upstream_blocker_receipt_records_awaiting_evidence(tmp_path: Path) -> None:
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
    output_path = tmp_path / "deployment_upstream_blocker_receipt.json"

    written = write_deployment_upstream_blocker_receipt(receipt, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert receipt.receipt_id.startswith("deployment-upstream-blocker-")
    assert receipt.ready is False
    assert receipt.target_gateway_host == "api.mullusi.com"
    assert receipt.blockers == ("private_recovery_inventory_missing", "runtime_host_not_provisioned")
    assert payload["checked_at_utc"] == "2026-05-24T12:00:00Z"


def test_deployment_upstream_blocker_receipt_records_ready_gate() -> None:
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

    assert receipt.ready is True
    assert receipt.api_provisioning_allowed is True
    assert receipt.dns_publication_allowed is True
    assert receipt.blockers == ()


def test_deployment_upstream_blocker_receipt_rejects_bad_gateway_url() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        emit_deployment_upstream_blocker_receipt(
            target_gateway_url="http://api.mullusi.com/path",
            upstream_repository="mullusi/mullusi-site",
            upstream_gate="api-production-readiness-gate",
            upstream_state="AwaitingEvidence",
            api_provisioning_allowed=False,
            dns_publication_allowed=False,
            blockers=("private_recovery_inventory_missing",),
            evidence_refs=("issue-330-comment-4530008851",),
            next_actions=("complete private recovery inventory outside Git",),
        )

    assert "https scheme" in str(excinfo.value)
    assert "api-production-readiness-gate" not in str(excinfo.value)
    assert "private_recovery_inventory_missing" not in str(excinfo.value)


def test_deployment_upstream_blocker_cli_writes_blocked_receipt(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "deployment_upstream_blocker_receipt.json"

    exit_code = main(
        [
            "--target-gateway-url",
            "https://api.mullusi.com",
            "--output",
            str(output_path),
            "--json",
        ],
        now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert output_path.exists()
    assert payload["ready"] is False
    assert "private_recovery_inventory_missing" in payload["blockers"]


def test_deployment_upstream_blocker_cli_can_emit_ready_receipt(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "deployment_upstream_blocker_receipt.json"

    exit_code = main(
        [
            "--target-gateway-url",
            "https://api.mullusi.com",
            "--upstream-state",
            "SolvedVerified",
            "--api-provisioning-allowed",
            "--dns-publication-allowed",
            "--output",
            str(output_path),
            "--json",
        ],
        now_utc=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ready"] is True
    assert payload["blockers"] == []
    assert payload["next_actions"] == ["continue with gateway DNS target binding and resolution receipts"]
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""
