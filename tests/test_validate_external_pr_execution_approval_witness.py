"""Tests for external PR execution approval witness validation.

Purpose: prove the fixture remains pending and hash checked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_external_pr_execution_approval_witness.
Invariants: pending witness blocks external PR effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_external_pr_execution_approval_witness import (
    DEFAULT_OUTPUT,
    validate_external_pr_execution_approval_witness,
    write_external_pr_execution_approval_witness_validation,
)


def test_external_pr_execution_approval_witness_fixture_validates(tmp_path: Path) -> None:
    validation = validate_external_pr_execution_approval_witness()
    written = write_external_pr_execution_approval_witness_validation(validation, tmp_path / "validation.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.approval_status == "pending"
    assert validation.execution_status == "awaiting_local_pr_tool_admission"
    assert validation.external_effects_allowed is False
    assert validation.errors == ()
    assert payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "external_pr_execution_approval_witness_validation.json"


def test_external_pr_execution_approval_witness_rejects_hash_mismatch(tmp_path: Path) -> None:
    witness = json.loads(Path("examples/external_pr_execution_approval_witness.foundation.json").read_text(encoding="utf-8"))
    witness["external_effects_allowed"] = True
    witness["pr_creation_allowed"] = True
    witness["branch_push_allowed"] = True
    witness["approved_external_effects"] = ["push_branch", "open_external_pr"]
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_external_pr_execution_approval_witness(witness_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effects_allowed_mismatch" in serialized_errors
    assert "pr_creation_allowed_mismatch" in serialized_errors
    assert "branch_push_allowed_mismatch" in serialized_errors
    assert "approved_external_effects_mismatch" in serialized_errors
    assert "witness_hash_mismatch" in serialized_errors
