"""Tests for capability adapter evidence collection.

Purpose: prove adapter production closure is represented by dependency checks
and live receipts, not by adapter code presence alone.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.collect_capability_adapter_evidence.
Invariants:
  - Missing dependencies and receipts block adapter closure.
  - Complete dependencies and receipts produce a ready evidence report.
  - CLI writes a deterministic report and preserves strict exit behavior.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_capability_adapter_evidence import (  # noqa: E402
    collect_capability_adapter_evidence,
    main,
)


def test_adapter_evidence_blocks_without_dependencies_or_receipts(tmp_path: Path) -> None:
    report = collect_capability_adapter_evidence(
        repo_root=_ROOT,
        browser_receipt_path=tmp_path / "missing-browser.json",
        document_receipt_path=tmp_path / "missing-document.json",
        voice_receipt_path=tmp_path / "missing-voice.json",
        email_calendar_receipt_path=tmp_path / "missing-email-calendar.json",
        module_available=lambda name: False,
        env_reader=lambda name: "",
    )

    assert report.ready is False
    assert "browser_dependency_missing:playwright" in report.blockers
    assert "document_dependency_missing:pypdf" in report.blockers
    assert "document_dependency_missing:docx" in report.blockers
    assert "voice_dependency_missing:openai" in report.blockers
    assert "voice_dependency_missing:OPENAI_API_KEY" in report.blockers
    assert "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN" in report.blockers
    assert "browser_live_evidence_missing" in report.blockers
    assert "document_live_evidence_missing" in report.blockers
    assert "voice_live_evidence_missing" in report.blockers
    assert "email_calendar_live_evidence_missing" in report.blockers


def test_adapter_evidence_accepts_dependencies_and_live_receipts(tmp_path: Path) -> None:
    browser_receipt = tmp_path / "browser.json"
    document_receipt = tmp_path / "document.json"
    voice_receipt = tmp_path / "voice.json"
    email_calendar_receipt = tmp_path / "email-calendar.json"
    browser_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "adapter_id": "browser.playwright",
                "sandboxed_worker": True,
                "sandbox_evidence_id": "browser-sandbox-evidence-test",
                "sandbox_receipt_id": "sandbox-receipt-test",
                "url_before": "https://docs.mullusi.com/",
                "url_after": "https://docs.mullusi.com/",
                "screenshot_before_ref": "evidence:browser:before",
                "screenshot_after_ref": "evidence:browser:after",
                "network_requests": ["https://docs.mullusi.com/reference"],
                "worker_receipt": {"verification_status": "passed"},
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )
    document_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "parser_ids": [
                    "production-pdf",
                    "production-docx",
                    "production-xlsx",
                    "production-pptx",
                ],
            }
        ),
        encoding="utf-8",
    )
    voice_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "speech_to_text_status": "passed",
                "text_to_speech_status": "passed",
            }
        ),
        encoding="utf-8",
    )
    email_calendar_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "adapter_id": "communication.email_calendar_worker",
                "external_write": False,
            }
        ),
        encoding="utf-8",
    )

    report = collect_capability_adapter_evidence(
        repo_root=_ROOT,
        browser_receipt_path=browser_receipt,
        document_receipt_path=document_receipt,
        voice_receipt_path=voice_receipt,
        email_calendar_receipt_path=email_calendar_receipt,
        module_available=lambda name: True,
        env_reader=lambda name: "configured-secret",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert {adapter.adapter_id for adapter in report.adapters} == {
        "browser.playwright",
        "document.production_parsers",
        "voice.openai",
        "communication.email_calendar_worker",
    }
    assert all(adapter.closed for adapter in report.adapters)
    browser_evidence = next(adapter for adapter in report.adapters if adapter.adapter_id == "browser.playwright")
    assert browser_evidence.receipt_check.evidence_refs == (
        "browser-sandbox-evidence-test",
        "sandbox-receipt-test",
    )
    assert "browser-sandbox-evidence-test" in browser_evidence.evidence_refs
    assert "sandbox-receipt-test" in browser_evidence.evidence_refs
    assert report.report_id.startswith("capability-adapter-evidence-")


def test_adapter_evidence_rejects_browser_receipt_without_action_evidence(tmp_path: Path) -> None:
    browser_receipt = tmp_path / "browser.json"
    document_receipt = tmp_path / "document.json"
    voice_receipt = tmp_path / "voice.json"
    email_calendar_receipt = tmp_path / "email-calendar.json"
    browser_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "adapter_id": "browser.playwright",
                "sandboxed_worker": True,
                "sandbox_evidence_id": "browser-sandbox-evidence-test",
                "sandbox_receipt_id": "sandbox-receipt-test",
            }
        ),
        encoding="utf-8",
    )
    document_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "parser_ids": [
                    "production-pdf",
                    "production-docx",
                    "production-xlsx",
                    "production-pptx",
                ],
            }
        ),
        encoding="utf-8",
    )
    voice_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "speech_to_text_status": "passed",
                "text_to_speech_status": "passed",
            }
        ),
        encoding="utf-8",
    )
    email_calendar_receipt.write_text(
        json.dumps(
            {
                "status": "passed",
                "adapter_id": "communication.email_calendar_worker",
                "external_write": False,
            }
        ),
        encoding="utf-8",
    )

    report = collect_capability_adapter_evidence(
        repo_root=_ROOT,
        browser_receipt_path=browser_receipt,
        document_receipt_path=document_receipt,
        voice_receipt_path=voice_receipt,
        email_calendar_receipt_path=email_calendar_receipt,
        module_available=lambda name: True,
        env_reader=lambda name: "configured-secret",
    )
    browser_evidence = next(adapter for adapter in report.adapters if adapter.adapter_id == "browser.playwright")

    assert report.ready is False
    assert browser_evidence.closed is False
    assert browser_evidence.receipt_check.passed is False
    assert "browser_live_evidence_missing" in report.blockers
    assert "worker receipt" in browser_evidence.receipt_check.detail


def test_adapter_evidence_cli_writes_report_and_honors_strict(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "adapter-evidence.json"

    exit_code = main(
        [
            "--repo-root",
            str(_ROOT),
            "--browser-receipt",
            str(tmp_path / "missing-browser.json"),
            "--document-receipt",
            str(tmp_path / "missing-document.json"),
            "--voice-receipt",
            str(tmp_path / "missing-voice.json"),
            "--email-calendar-receipt",
            str(tmp_path / "missing-email-calendar.json"),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    written_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["ready"] is False
    assert written_payload["report_id"] == payload["report_id"]
    assert "browser_live_evidence_missing" in payload["blockers"]
    assert "email_calendar_live_evidence_missing" in payload["blockers"]
    assert captured.err == ""
