"""Tests for TeamOps terminal closure anchor receipt validation.

Purpose: prove TeamOps anchor receipt wrappers remain bound to ready preflight,
source bundle, projected artifacts, and signed trust-ledger anchor receipts.
Governance scope: TeamOps anchor receipt validation, no-effect metadata,
signature verification, and drift rejection.
Dependencies: scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_receipt.
Invariants:
  - Validation accepts only ready local pending anchor receipts.
  - Validation rejects signature drift, effect claims, and source drift.
  - Validation emits a bounded receipt for CLI use.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from scripts.validate_team_ops_shared_inbox_terminal_closure_anchor_receipt import (
    main,
    validate_team_ops_shared_inbox_terminal_closure_anchor_receipt,
)

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_produce_team_ops_shared_inbox_terminal_closure_anchor_receipt import (  # noqa: E402
    ANCHOR_SECRET,
    SIGNING_SECRET,
    _write_ready_preflight,
)
from scripts.produce_team_ops_shared_inbox_terminal_closure_anchor_receipt import (  # noqa: E402
    produce_team_ops_shared_inbox_terminal_closure_anchor_receipt,
    write_team_ops_shared_inbox_terminal_closure_anchor_receipt,
)


def test_team_ops_terminal_closure_anchor_receipt_validation_accepts_ready_receipt(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path, receipt_path = _write_ready_receipt(tmp_path)

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        receipt_path=receipt_path,
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        require_ready=True,
    )

    assert validation.valid is True
    assert validation.ready is True
    assert validation.errors == ()
    assert validation.anchor_receipt_id.startswith("trust-anchor-receipt-")
    assert validation.artifact_count >= 4
    assert validation.next_action.startswith("operator may run")


def test_team_ops_terminal_closure_anchor_receipt_validation_rejects_wrong_anchor_secret(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path, receipt_path = _write_ready_receipt(tmp_path)

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        receipt_path=receipt_path,
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret="wrong-anchor-secret",
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "trust-ledger anchor receipt must verify: anchor_signature_mismatch" in validation.errors
    assert validation.source_preflight_receipt_id.startswith("teamops-shared-inbox-terminal-anchor-preflight-")
    assert validation.next_action.startswith("repair TeamOps")


def test_team_ops_terminal_closure_anchor_receipt_validation_rejects_artifact_drift(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path, receipt_path = _write_ready_receipt(tmp_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["artifact_hash"] = f"sha256:{'f' * 64}"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        receipt_path=receipt_path,
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "artifacts must match deterministic source-bundle projection" in validation.errors
    assert "artifacts must match TeamOps anchor preflight" in validation.errors
    assert "trust-ledger anchor receipt must verify: artifact_root_hash_mismatch" in validation.errors


def test_team_ops_terminal_closure_anchor_receipt_validation_rejects_effect_claim(
    tmp_path: Path,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path, receipt_path = _write_ready_receipt(tmp_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["metadata"]["remote_submit_executed"] = True
    payload["metadata"]["production_ready_claimed"] = True
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        receipt_path=receipt_path,
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert "metadata.remote_submit_executed must be false" in validation.errors
    assert "metadata.production_ready_claimed must be false" in validation.errors
    assert validation.next_action.startswith("repair TeamOps")


def test_team_ops_terminal_closure_anchor_receipt_validation_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    bundle_path, certificate_path, review_path, preflight_path, receipt_path = _write_ready_receipt(tmp_path)
    output_path = tmp_path / "team_ops_anchor_receipt_validation.json"

    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--preflight",
            str(preflight_path),
            "--bundle",
            str(bundle_path),
            "--certificate",
            str(certificate_path),
            "--source-review-packet",
            str(review_path),
            "--bundle-signing-secret",
            SIGNING_SECRET,
            "--anchor-signing-secret",
            ANCHOR_SECRET,
            "--output",
            str(output_path),
            "--require-ready",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 0
    assert file_payload["valid"] is True
    assert stdout_payload["ready"] is True
    assert file_payload["errors"] == []
    assert captured.err == ""


def _write_ready_receipt(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    bundle_path, certificate_path, review_path, preflight_path = _write_ready_preflight(tmp_path)
    receipt = produce_team_ops_shared_inbox_terminal_closure_anchor_receipt(
        preflight_path=preflight_path,
        bundle_path=bundle_path,
        certificate_path=certificate_path,
        source_review_packet_path=review_path,
        bundle_signing_secret=SIGNING_SECRET,
        anchor_signing_secret=ANCHOR_SECRET,
        created_at="2026-06-14T00:00:00+00:00",
    )
    receipt_path = tmp_path / "team_ops_shared_inbox_terminal_closure_anchor_receipt.json"
    write_team_ops_shared_inbox_terminal_closure_anchor_receipt(receipt, receipt_path)
    return bundle_path, certificate_path, review_path, preflight_path, receipt_path
