"""Tests for browser sandbox evidence validation.

Purpose: prove sandbox evidence is independently admissible before browser
live receipt production.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_browser_sandbox_evidence.
Invariants:
  - Passing evidence validates.
  - Missing evidence fails closed.
  - Non-browser evidence fails closed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.produce_browser_sandbox_evidence import produce_browser_sandbox_evidence
from scripts.validate_browser_sandbox_evidence import main, validate_browser_sandbox_evidence


def test_validate_browser_sandbox_evidence_accepts_produced_receipt(tmp_path: Path) -> None:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"

    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        runner=_sandbox_success_runner,
        platform_system=lambda: "Linux",
    )
    result = validate_browser_sandbox_evidence(evidence_path)

    assert result.valid is True
    assert result.status == "passed"
    assert result.evidence_id.startswith("browser-sandbox-evidence-")
    assert result.receipt_id.startswith("sandbox-receipt-")
    assert result.blockers == ()
    assert "sandbox receipt verified" in result.detail


def test_validate_browser_sandbox_evidence_rejects_missing_file(tmp_path: Path) -> None:
    result = validate_browser_sandbox_evidence(tmp_path / "missing.json")

    assert result.valid is False
    assert result.status == "failed"
    assert result.evidence_id == ""
    assert result.receipt_id == ""
    assert result.blockers == ("browser_sandbox_evidence_unverified",)
    assert "not found" in result.detail


def test_validate_browser_sandbox_evidence_rejects_non_browser_receipt(tmp_path: Path) -> None:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"
    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        capability_id="document.parse",
        runner=_sandbox_success_runner,
        platform_system=lambda: "Linux",
    )

    result = validate_browser_sandbox_evidence(evidence_path)

    assert result.valid is False
    assert result.status == "failed"
    assert result.evidence_id.startswith("browser-sandbox-evidence-")
    assert result.receipt_id.startswith("sandbox-receipt-")
    assert result.blockers == ("browser_sandbox_evidence_invalid",)
    assert "capability_id_not_browser" in result.detail


def test_validate_browser_sandbox_evidence_rejects_workspace_mutation(tmp_path: Path) -> None:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"

    def mutating_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        (tmp_path / "browser-output.txt").write_text("unexpected", encoding="utf-8")
        return subprocess.CompletedProcess(args[0], 0, stdout="Python 3.13", stderr="")

    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        runner=mutating_runner,
        platform_system=lambda: "Linux",
    )

    result = validate_browser_sandbox_evidence(evidence_path)

    assert result.valid is False
    assert result.status == "failed"
    assert result.blockers == ("browser_sandbox_evidence_invalid",)
    assert "changed_file_count_not_zero" in result.detail
    assert "changed_file_refs_not_empty" in result.detail


def test_validate_browser_sandbox_evidence_cli_outputs_json(tmp_path: Path, capsys) -> None:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"
    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        runner=_sandbox_success_runner,
        platform_system=lambda: "Linux",
    )

    exit_code = main(["--evidence", str(evidence_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["status"] == "passed"
    assert payload["evidence_id"].startswith("browser-sandbox-evidence-")
    assert payload["receipt_id"].startswith("sandbox-receipt-")
    assert payload["blockers"] == []


def _sandbox_success_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args[0], 0, stdout="Python 3.13", stderr="")
