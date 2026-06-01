"""Tests for terminal approval receipt validation.

Purpose: prove terminal certificate gate approvals are schema-backed and
secret-safe before admission.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_general_agent_promotion_terminal_approvals.
Invariants:
  - Approval refs are scoped to terminal_certificate_gate.
  - Serialized values fail closed.
  - Duplicate action approvals fail closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_general_agent_promotion_terminal_approvals import (  # noqa: E402
    main,
    validate_general_agent_promotion_terminal_approvals,
)


def test_terminal_approvals_validator_accepts_schema_valid_refs(tmp_path: Path) -> None:
    receipt_path = _write_receipt(
        tmp_path,
        approvals={
            "deploy-publish": "approval://deployment/publish",
            "portfolio-review": "approval://portfolio/review",
        },
    )

    result = validate_general_agent_promotion_terminal_approvals(receipt_path=receipt_path)

    assert result.valid is True
    assert result.present is True
    assert result.receipt_path == "general_agent_promotion_terminal_approvals.json"
    assert result.schema_path == "schemas/general_agent_promotion_terminal_approvals.schema.json"
    assert result.approval_count == 2
    assert result.approved_count == 2
    assert result.approved_refs_by_action["deploy-publish"] == "approval://deployment/publish"
    assert result.errors == ()


def test_terminal_approvals_validator_rejects_serialized_values(tmp_path: Path) -> None:
    receipt_path = _write_receipt(
        tmp_path,
        approvals={"deploy-publish": "approval://deployment/publish"},
        value_serialized=True,
    )

    result = validate_general_agent_promotion_terminal_approvals(receipt_path=receipt_path)

    assert result.valid is False
    assert result.present is True
    assert result.approval_count == 1
    assert result.approved_count == 0
    assert result.approved_refs_by_action == {}
    assert "approval_receipt_entry_1_value_serialized_must_be_false" in result.errors
    assert str(tmp_path) not in json.dumps(result.as_dict())


def test_terminal_approvals_validator_rejects_duplicate_action_ids(tmp_path: Path) -> None:
    receipt_path = tmp_path / "general_agent_promotion_terminal_approvals.json"
    payload = _receipt_payload(
        approvals={
            "deploy-publish": "approval://deployment/publish",
        }
    )
    payload["approvals"].append(
        {
            "source_action_id": "deploy-publish",
            "approval_ref": "approval://deployment/publish-second",
            "approved": True,
            "scope": "terminal_certificate_gate",
            "value_serialized": False,
        }
    )
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_terminal_approvals(receipt_path=receipt_path)

    assert result.valid is False
    assert result.approval_count == 2
    assert result.approved_count == 0
    assert result.duplicate_source_action_ids == ("deploy-publish",)
    assert "approval_receipt_entry_2_duplicate_source_action_id:deploy-publish" in result.errors


def test_terminal_approvals_cli_reports_missing_with_allow_missing(tmp_path: Path, capsys) -> None:
    missing_path = tmp_path / "missing-terminal-approvals.json"

    exit_code = main(["--receipt", str(missing_path), "--allow-missing", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["present"] is False
    assert payload["valid"] is False
    assert payload["receipt_path"] == "missing-terminal-approvals.json"
    assert payload["schema_path"] == "schemas/general_agent_promotion_terminal_approvals.schema.json"
    assert payload["approval_count"] == 0
    assert payload["errors"] == []
    assert str(tmp_path) not in json.dumps(payload)


def test_terminal_approvals_malformed_receipt_uses_bounded_path_labels(tmp_path: Path) -> None:
    receipt_path = tmp_path / "bad-terminal-approvals.json"
    receipt_path.write_text('{"receipt_id": "secret-approval-token"', encoding="utf-8")

    result = validate_general_agent_promotion_terminal_approvals(receipt_path=receipt_path)
    payload = result.as_dict()

    assert result.valid is False
    assert result.present is True
    assert result.receipt_path == "bad-terminal-approvals.json"
    assert result.schema_path == "schemas/general_agent_promotion_terminal_approvals.schema.json"
    assert result.errors == ("approval_receipt_invalid",)
    assert str(tmp_path) not in json.dumps(payload)


def _write_receipt(
    tmp_path: Path,
    *,
    approvals: dict[str, str],
    value_serialized: bool = False,
) -> Path:
    receipt_path = tmp_path / "general_agent_promotion_terminal_approvals.json"
    receipt_path.write_text(
        json.dumps(_receipt_payload(approvals=approvals, value_serialized=value_serialized)),
        encoding="utf-8",
    )
    return receipt_path


def _receipt_payload(
    *,
    approvals: dict[str, str],
    value_serialized: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_id": "general-agent-promotion-terminal-approvals-v1",
        "checked_at": "2026-05-01T12:00:00+00:00",
        "secret_serialization": "forbidden",
        "approvals": [
            {
                "source_action_id": source_action_id,
                "approval_ref": approval_ref,
                "approved": True,
                "scope": "terminal_certificate_gate",
                "value_serialized": value_serialized,
            }
            for source_action_id, approval_ref in approvals.items()
        ],
        "metadata": {
            "gate_is_not_execution": True,
            "secret_values_serialized": False,
            "approval_values_are_refs": True,
            "terminal_certificate_gate_schema_id": (
                "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
            ),
        },
    }
