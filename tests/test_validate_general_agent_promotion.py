"""Tests for governed general-agent promotion validation.

Purpose: prove the repo can report pilot governed core readiness while blocking
production promotion until required closure evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_general_agent_promotion.
Invariants:
  - Governed capability records are present before promotion checks.
  - Current adapter gaps remain explicit promotion blockers.
  - Published deployment evidence can satisfy the witness checks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_MCOI_ROOT = _ROOT / "mcoi"
if str(_MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCOI_ROOT))

from scripts.validate_general_agent_promotion import (  # noqa: E402
    evaluate_deployment_publication,
    main,
    validate_general_agent_promotion,
    write_general_agent_promotion_readiness,
)


def test_current_repo_blocks_full_general_agent_claim() -> None:
    readiness = validate_general_agent_promotion(repo_root=_ROOT)

    assert readiness.ready is False
    assert readiness.readiness_level == "pilot-governed-core"
    assert readiness.capability_count >= 30
    assert readiness.capsule_count >= 7
    assert "browser_adapter_not_closed" in readiness.blockers
    assert "document_adapter_not_closed" in readiness.blockers
    assert "voice_adapter_not_closed" in readiness.blockers
    assert "email_calendar_adapter_not_closed" in readiness.blockers
    assert "adapter_evidence_not_closed" in readiness.blockers
    assert "deployment_witness_not_published" in readiness.blockers
    assert "production_health_not_declared" in readiness.blockers


def test_governed_record_surface_check_passes_before_adapter_closure() -> None:
    readiness = validate_general_agent_promotion(repo_root=_ROOT)
    checks_by_name = {check.name: check for check in readiness.checks}
    governed_surface = checks_by_name["tenant governed capability record surface"]
    mcp_manifest = checks_by_name["MCP governed import manifest"]
    sandbox_contract = checks_by_name["sandboxed computer/code runner contract"]
    email_calendar_adapter = checks_by_name["real email/calendar adapter closure"]

    assert governed_surface.passed is True
    assert "governed capability records" in governed_surface.detail
    assert mcp_manifest.passed is True
    assert "governed capability imports" in mcp_manifest.detail
    assert sandbox_contract.passed is True
    assert "no-network" in sandbox_contract.detail
    assert email_calendar_adapter.passed is False
    assert "concrete_adapter=True" in email_calendar_adapter.detail


def test_promotion_consumes_closed_adapter_evidence(tmp_path: Path) -> None:
    adapter_evidence_path = tmp_path / "capability_adapter_evidence.json"
    adapter_evidence_path.write_text(
        json.dumps(
            {
                "ready": True,
                "blockers": [],
                "adapters": [
                    {"adapter_id": "browser.playwright"},
                    {"adapter_id": "document.production_parsers"},
                    {"adapter_id": "voice.openai"},
                    {"adapter_id": "communication.email_calendar_worker"},
                ],
            }
        ),
        encoding="utf-8",
    )

    readiness = validate_general_agent_promotion(
        repo_root=_ROOT,
        adapter_evidence_path=adapter_evidence_path,
    )
    checks_by_name = {check.name: check for check in readiness.checks}
    adapter_evidence = checks_by_name["capability adapter closure evidence"]

    assert adapter_evidence.passed is True
    assert adapter_evidence.blocker_id == ""
    assert "browser, document, voice, and communication" in adapter_evidence.detail
    assert "adapter_evidence_not_closed" not in readiness.blockers


def test_deployment_publication_checks_accept_published_witness(tmp_path: Path) -> None:
    deployment_status = tmp_path / "DEPLOYMENT_STATUS.md"
    deployment_witness = tmp_path / "deployment_witness.json"
    deployment_status.write_text(
        _deployment_status("published", "https://gateway.example/health"),
        encoding="utf-8",
    )
    deployment_witness.write_text(json.dumps(_published_witness()), encoding="utf-8")

    witness_check, health_check = evaluate_deployment_publication(
        deployment_status_path=deployment_status,
        deployment_witness_path=deployment_witness,
    )

    assert witness_check.passed is True
    assert witness_check.blocker_id == ""
    assert "published" in witness_check.detail
    assert health_check.passed is True
    assert health_check.blocker_id == ""
    assert "https://gateway.example/health" in health_check.detail


def test_cli_strict_json_blocks_current_repo(tmp_path: Path, capsys) -> None:
    missing_witness = tmp_path / "missing_deployment_witness.json"

    exit_code = main(
        [
            "--repo-root",
            str(_ROOT),
            "--deployment-witness",
            str(missing_witness),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["ready"] is False
    assert payload["readiness_level"] == "pilot-governed-core"
    assert "browser_adapter_not_closed" in payload["blockers"]
    assert "email_calendar_adapter_not_closed" in payload["blockers"]
    assert "production_health_not_declared" in payload["blockers"]
    assert captured.err == ""


def test_write_general_agent_promotion_readiness_persists_report(tmp_path: Path) -> None:
    readiness = validate_general_agent_promotion(repo_root=_ROOT)
    output_path = tmp_path / "general_agent_promotion_readiness.json"

    written = write_general_agent_promotion_readiness(readiness, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload["ready"] is False
    assert payload["readiness_level"] == "pilot-governed-core"
    assert payload["capability_count"] == readiness.capability_count
    assert "deployment_witness_not_published" in payload["blockers"]


def test_cli_output_writes_readiness_artifact(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "general_agent_promotion_readiness.json"

    exit_code = main(
        [
            "--repo-root",
            str(_ROOT),
            "--output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "promotion_readiness_written:" in captured.out
    assert payload["ready"] is False
    assert payload["capability_count"] >= 52
    assert "production_health_not_declared" in payload["blockers"]


def _deployment_status(state: str, public_health_endpoint: str) -> str:
    return "\n".join(
        (
            "# Deployment Status Witness",
            "",
            f"**Deployment witness state:** `{state}`",
            f"**Public production health endpoint:** `{public_health_endpoint}`",
            "",
        )
    )


def _published_witness() -> dict[str, object]:
    return {
        "witness_id": "deployment-witness-001",
        "gateway_url": "https://gateway.example",
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
        "steps": (
            {"name": "gateway health", "passed": True, "detail": "ok"},
            {"name": "gateway runtime witness", "passed": True, "detail": "ok"},
            {"name": "runtime conformance signature", "passed": True, "detail": "ok"},
        ),
        "errors": (),
    }
