"""Tests for PR readiness bundle validation.

Purpose: prove the Foundation fixture remains blocked and hash checked.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_pr_readiness_bundle.
Invariants: readiness fixture does not execute or overclaim external effects.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_pr_readiness_bundle import (
    DEFAULT_OUTPUT,
    validate_pr_readiness_bundle,
    write_pr_readiness_bundle_validation,
)


def test_pr_readiness_bundle_fixture_validates(tmp_path: Path) -> None:
    validation = validate_pr_readiness_bundle()
    written = write_pr_readiness_bundle_validation(validation, tmp_path / "validation.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.readiness_status == "awaiting_sandbox_receipts"
    assert validation.ready_for_external_pr_execution is False
    assert validation.errors == ()
    assert payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "pr_readiness_bundle_validation.json"


def test_pr_readiness_bundle_rejects_executed_claim(tmp_path: Path) -> None:
    bundle = json.loads(Path("examples/pr_readiness_bundle.foundation.json").read_text(encoding="utf-8"))
    bundle["execution_performed"] = True
    bundle["preview_only"] = False
    bundle_path = tmp_path / "readiness.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_pr_readiness_bundle(bundle_path=bundle_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "$.preview_only: expected const True" in serialized_errors
    assert "$.execution_performed: expected const False" in serialized_errors
    assert "preview_only_must_be_true" in serialized_errors
    assert "execution_performed_must_be_false" in serialized_errors
    assert "bundle_hash_mismatch" in serialized_errors
