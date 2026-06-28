"""Tests for Developer Workflow sandbox receipt attachment packet building.

Purpose: prove the attachment packet is derived from existing sandbox-to-PR
and receipt-bundle evidence without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_developer_workflow_sandbox_receipt_attachment_packet.
Invariants:
  - Builder is projection-only.
  - Attachment rows preserve canonical order and action hints.
  - Attached status follows the sandbox receipt bundle.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_developer_workflow_sandbox_receipt_attachment_packet import (
    build_developer_workflow_sandbox_receipt_attachment_packet,
    main,
    write_developer_workflow_sandbox_receipt_attachment_packet,
)
from scripts.validate_developer_workflow_sandbox_receipt_attachment_packet import (
    validate_developer_workflow_sandbox_receipt_attachment_packet,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture(name: str) -> dict[str, object]:
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def test_attachment_packet_builder_projects_pending_fixture(tmp_path: Path) -> None:
    sandbox_to_pr_path = ROOT / "examples" / "sandbox_to_pr_preparation_packet.foundation.json"
    bundle_path = ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"

    packet = build_developer_workflow_sandbox_receipt_attachment_packet(
        sandbox_to_pr_packet=_fixture("sandbox_to_pr_preparation_packet.foundation.json"),
        sandbox_to_pr_packet_path=sandbox_to_pr_path,
        sandbox_receipt_bundle=_fixture("developer_workflow_sandbox_receipt_bundle.foundation.json"),
        sandbox_receipt_bundle_path=bundle_path,
    )
    packet_path = write_developer_workflow_sandbox_receipt_attachment_packet(packet, tmp_path / "packet.json")
    validation = validate_developer_workflow_sandbox_receipt_attachment_packet(packet_path=packet_path)

    assert validation.ok is True
    assert packet["external_effects_allowed"] is False
    assert packet["packet_status"] == "awaiting_attachments"
    assert packet["completed_count"] == 0
    assert packet["next_attachment"]["receipt_id"] == "sandbox_patch_receipt"  # type: ignore[index]
    assert [item["receipt_id"] for item in packet["attachments"]] == [  # type: ignore[index]
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    ]


def test_attachment_packet_builder_marks_complete_bundle_attached(tmp_path: Path) -> None:
    sandbox_to_pr = _fixture("sandbox_to_pr_preparation_packet.foundation.json")
    bundle = _fixture("developer_workflow_sandbox_receipt_bundle.foundation.json")
    for receipt in bundle["receipts"]:  # type: ignore[index]
        receipt["status"] = "complete"
        receipt["before_state_hash"] = f"before-{receipt['receipt_id']}"
        receipt["after_state_hash"] = f"after-{receipt['receipt_id']}"
        receipt["diff_hash"] = f"diff-{receipt['receipt_id']}"
        receipt["command"] = "local proof command"
        receipt["rollback_command"] = "local rollback command"
        receipt["evidence_refs"] = [f"proof://{receipt['receipt_id']}"]
    bundle["bundle_status"] = "receipts_complete"
    bundle["completed_count"] = 4

    packet = build_developer_workflow_sandbox_receipt_attachment_packet(
        sandbox_to_pr_packet=sandbox_to_pr,
        sandbox_to_pr_packet_path=tmp_path / "sandbox_to_pr.json",
        sandbox_receipt_bundle=bundle,
        sandbox_receipt_bundle_path=tmp_path / "bundle.json",
    )
    packet_path = write_developer_workflow_sandbox_receipt_attachment_packet(packet, tmp_path / "packet.json")
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sandbox_to_pr_path = tmp_path / "sandbox_to_pr.json"
    sandbox_to_pr_path.write_text(json.dumps(sandbox_to_pr, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = validate_developer_workflow_sandbox_receipt_attachment_packet(
        packet_path=packet_path,
        sandbox_to_pr_packet_path=sandbox_to_pr_path,
        sandbox_receipt_bundle_path=bundle_path,
    )

    assert validation.ok is True
    assert packet["packet_status"] == "attachments_complete"
    assert packet["completed_count"] == 4
    assert packet["next_attachment"]["receipt_id"] == "none"  # type: ignore[index]
    assert all(item["status"] == "attached" for item in packet["attachments"])  # type: ignore[index]


def test_attachment_packet_builder_cli_writes_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "attachment-packet.json"

    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.exists()
    assert "developer_workflow_sandbox_receipt_attachment_packet.v1" in captured.out
