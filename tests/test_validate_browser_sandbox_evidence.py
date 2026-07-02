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
    assert result.evidence_path == evidence_path.name
    assert result.status == "passed"
    assert result.evidence_id.startswith("browser-sandbox-evidence-")
    assert result.receipt_id.startswith("sandbox-receipt-")
    assert result.blockers == ()
    assert "sandbox receipt verified" in result.detail
    assert str(tmp_path) not in result.evidence_path


def test_validate_browser_sandbox_evidence_rejects_missing_file(tmp_path: Path) -> None:
    evidence_path = tmp_path / "missing.json"
    result = validate_browser_sandbox_evidence(evidence_path)

    assert result.valid is False
    assert result.evidence_path == evidence_path.name
    assert result.status == "failed"
    assert result.evidence_id == ""
    assert result.receipt_id == ""
    assert result.blockers == ("browser_sandbox_evidence_unverified",)
    assert "not found" in result.detail
    assert str(tmp_path) not in result.evidence_path


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


def test_validate_browser_sandbox_evidence_rejects_missing_deeper_isolation(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"
    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        runner=_sandbox_success_runner,
        platform_system=lambda: "Linux",
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["receipt"]["capabilities_dropped"] = False
    payload["receipt"]["seccomp_profile_applied"] = "unconfined"
    payload["sandbox_profile"]["drop_all_capabilities"] = False
    payload["sandbox_profile"]["seccomp_profile"] = "unconfined"
    payload["isolation"]["capabilities_dropped"] = False
    payload["isolation"]["seccomp_profile_applied"] = "unconfined"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_browser_sandbox_evidence(evidence_path)

    assert result.valid is False
    assert result.status == "failed"
    assert result.blockers == ("browser_sandbox_evidence_invalid",)
    assert "capabilities_dropped_not_true" in result.detail
    assert "seccomp_profile_unconfined" in result.detail
    assert "sandbox_profile_drop_all_capabilities_not_true" in result.detail


def test_validate_browser_sandbox_evidence_rejects_isolation_summary_mismatch(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"
    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        runner=_sandbox_success_runner,
        platform_system=lambda: "Linux",
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["isolation"]["network_disabled"] = False
    payload["sandbox_profile"]["network"] = "bridge"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_browser_sandbox_evidence(evidence_path)

    assert result.valid is False
    assert result.status == "failed"
    assert result.blockers == ("browser_sandbox_evidence_invalid",)
    assert "sandbox_profile_network_not_none" in result.detail
    assert "isolation_network_disabled_mismatch" in result.detail


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
    assert payload["evidence_path"] == evidence_path.name
    assert payload["status"] == "passed"
    assert payload["evidence_id"].startswith("browser-sandbox-evidence-")
    assert payload["receipt_id"].startswith("sandbox-receipt-")
    assert payload["blockers"] == []
    assert str(tmp_path) not in payload["evidence_path"]


def _sandbox_success_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args[0], 0, stdout="Python 3.13", stderr="")
