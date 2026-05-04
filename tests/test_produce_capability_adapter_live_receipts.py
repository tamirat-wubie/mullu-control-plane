"""Tests for live capability adapter receipt production.

Purpose: prove live receipts are generated from governed worker responses and
remain blocked when required evidence is absent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.produce_capability_adapter_live_receipts.
Invariants:
  - Browser receipts cannot pass without sandbox evidence.
  - Document receipts require all production parser families.
  - Voice receipts require audio input and successful STT/TTS worker receipts.
  - Communication receipts require a successful read-only email/calendar worker probe.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_MCOI_ROOT = _ROOT / "mcoi"
if str(_MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCOI_ROOT))

from gateway.browser_worker import (  # noqa: E402
    BrowserActionObservation,
    BrowserActionRequest,
    BrowserWorkerPolicy,
    execute_browser_request,
)
from gateway.email_calendar_worker import (  # noqa: E402
    EmailCalendarActionObservation,
    EmailCalendarActionRequest,
    EmailCalendarWorkerPolicy,
    execute_email_calendar_request,
)
from gateway.voice_worker import (  # noqa: E402
    VoiceActionRequest,
    VoiceSynthesisObservation,
    VoiceTranscriptObservation,
    VoiceWorkerPolicy,
    execute_voice_request,
)
from scripts.collect_capability_adapter_evidence import (  # noqa: E402
    collect_capability_adapter_evidence,
)
from scripts.produce_capability_adapter_live_receipts import (  # noqa: E402
    produce_browser_live_receipt,
    produce_document_live_receipt,
    produce_email_calendar_live_receipt,
    produce_voice_live_receipt,
)
from scripts.produce_browser_sandbox_evidence import produce_browser_sandbox_evidence  # noqa: E402


def test_browser_live_receipt_passes_with_sandbox_evidence_and_worker_response(tmp_path: Path) -> None:
    output_path = tmp_path / "browser_live_receipt.json"
    sandbox_evidence = _write_browser_sandbox_evidence(tmp_path)

    result = produce_browser_live_receipt(
        output_path=output_path,
        sandbox_evidence_ref=str(sandbox_evidence),
        executor=_browser_executor(),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert payload["status"] == "passed"
    assert payload["adapter_id"] == "browser.playwright"
    assert payload["sandboxed_worker"] is True
    assert payload["sandbox_evidence_status"] == "passed"
    assert payload["sandbox_evidence_id"].startswith("browser-sandbox-evidence-")
    assert payload["sandbox_receipt_id"].startswith("sandbox-receipt-")
    assert payload["worker_receipt"]["verification_status"] == "passed"
    assert payload["network_requests"] == ["https://docs.mullusi.com/reference"]


def test_browser_live_receipt_bounds_malformed_sandbox_evidence_detail(tmp_path: Path) -> None:
    output_path = tmp_path / "browser_live_receipt.json"
    sandbox_evidence = tmp_path / "sandbox-evidence.json"
    sandbox_evidence.write_text('{"evidence_id": "secret-sandbox-evidence"', encoding="utf-8")

    result = produce_browser_live_receipt(
        output_path=output_path,
        sandbox_evidence_ref=str(sandbox_evidence),
        executor=_browser_executor(),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert payload["sandbox_evidence_detail"] == "sandbox evidence unreadable"
    assert "secret-sandbox-evidence" not in json.dumps(payload, sort_keys=True)


def test_browser_live_receipt_fails_without_sandbox_evidence(tmp_path: Path) -> None:
    output_path = tmp_path / "browser_live_receipt.json"

    result = produce_browser_live_receipt(
        output_path=output_path,
        sandbox_evidence_ref="",
        executor=_browser_executor(),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert payload["status"] == "failed"
    assert payload["sandboxed_worker"] is False
    assert payload["sandbox_evidence_id"] == ""
    assert payload["sandbox_receipt_id"] == ""
    assert "browser_sandbox_evidence_missing" in payload["blockers"]
    assert "browser_sandbox_evidence_missing" in result.blockers


def test_browser_live_receipt_rejects_opaque_sandbox_evidence(tmp_path: Path) -> None:
    output_path = tmp_path / "browser_live_receipt.json"

    result = produce_browser_live_receipt(
        output_path=output_path,
        sandbox_evidence_ref="sandbox:browser-worker-live",
        executor=_browser_executor(),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert payload["status"] == "failed"
    assert payload["sandboxed_worker"] is False
    assert payload["sandbox_evidence_status"] == "failed"
    assert payload["sandbox_evidence_id"] == ""
    assert payload["sandbox_receipt_id"] == ""
    assert "browser_sandbox_evidence_unverified" in payload["blockers"]


def test_document_live_receipt_passes_with_required_parser_probe(tmp_path: Path) -> None:
    output_path = tmp_path / "document_live_receipt.json"

    result = produce_document_live_receipt(
        output_path=output_path,
        parser_probe=lambda: (
            "production-pdf",
            "production-docx",
            "production-xlsx",
            "production-pptx",
        ),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert payload["status"] == "passed"
    assert payload["adapter_id"] == "document.production_parsers"
    assert set(payload["parser_ids"]) == {
        "production-pdf",
        "production-docx",
        "production-xlsx",
        "production-pptx",
    }
    assert payload["blockers"] == []


def test_document_live_receipt_blocks_missing_parser_family(tmp_path: Path) -> None:
    output_path = tmp_path / "document_live_receipt.json"

    result = produce_document_live_receipt(
        output_path=output_path,
        parser_probe=lambda: ("production-pdf", "production-docx"),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is False
    assert payload["status"] == "failed"
    assert "document_parser_missing:production-pptx" in payload["blockers"]
    assert "document_parser_missing:production-xlsx" in payload["blockers"]


def test_voice_live_receipt_passes_with_audio_and_worker_responses(tmp_path: Path) -> None:
    output_path = tmp_path / "voice_live_receipt.json"
    audio_path = tmp_path / "voice.wav"
    audio_path.write_bytes(b"audio-bytes")

    result = produce_voice_live_receipt(
        output_path=output_path,
        audio_path=audio_path,
        executor=_voice_executor(),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert payload["status"] == "passed"
    assert payload["adapter_id"] == "voice.openai"
    assert payload["speech_to_text_status"] == "passed"
    assert payload["text_to_speech_status"] == "passed"
    assert payload["speech_receipt"]["verification_status"] == "passed"
    assert payload["synthesis_receipt"]["verification_status"] == "passed"


def test_email_calendar_live_receipt_passes_with_read_only_worker_response(tmp_path: Path) -> None:
    output_path = tmp_path / "email_calendar_live_receipt.json"

    result = produce_email_calendar_live_receipt(
        output_path=output_path,
        executor=_email_calendar_executor(),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert payload["status"] == "passed"
    assert payload["adapter_id"] == "communication.email_calendar_worker"
    assert payload["external_write"] is False
    assert payload["worker_receipt"]["verification_status"] == "passed"
    assert payload["worker_receipt"]["capability_id"] == "email.search"


def test_generated_receipts_satisfy_adapter_evidence_collector(tmp_path: Path) -> None:
    browser_path = tmp_path / "browser.json"
    document_path = tmp_path / "document.json"
    voice_path = tmp_path / "voice.json"
    email_calendar_path = tmp_path / "email-calendar.json"
    audio_path = tmp_path / "voice.wav"
    sandbox_evidence = _write_browser_sandbox_evidence(tmp_path)
    audio_path.write_bytes(b"audio-bytes")
    produce_browser_live_receipt(
        output_path=browser_path,
        sandbox_evidence_ref=str(sandbox_evidence),
        executor=_browser_executor(),
    )
    produce_document_live_receipt(
        output_path=document_path,
        parser_probe=lambda: (
            "production-pdf",
            "production-docx",
            "production-xlsx",
            "production-pptx",
        ),
    )
    produce_voice_live_receipt(
        output_path=voice_path,
        audio_path=audio_path,
        executor=_voice_executor(),
    )
    produce_email_calendar_live_receipt(
        output_path=email_calendar_path,
        executor=_email_calendar_executor(),
    )

    report = collect_capability_adapter_evidence(
        repo_root=_ROOT,
        browser_receipt_path=browser_path,
        document_receipt_path=document_path,
        voice_receipt_path=voice_path,
        email_calendar_receipt_path=email_calendar_path,
        module_available=lambda name: True,
        env_reader=lambda name: "configured",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert all(adapter.closed for adapter in report.adapters)


class FakeBrowserAdapter:
    """Deterministic browser observation fixture."""

    def perform(self, request: BrowserActionRequest) -> BrowserActionObservation:
        return BrowserActionObservation(
            succeeded=True,
            url_before=request.url,
            url_after=request.url,
            screenshot_before_ref="evidence:before",
            screenshot_after_ref="evidence:after",
            extracted_text="Mullu docs",
            network_requests=("https://docs.mullusi.com/reference",),
        )


class FakeVoiceAdapter:
    """Deterministic voice observation fixture."""

    def transcribe(self, request: VoiceActionRequest, audio_bytes: bytes) -> VoiceTranscriptObservation:
        return VoiceTranscriptObservation(
            succeeded=True,
            transcript="governed voice transcript",
            confidence=0.99,
            adapter_id="openai:fake-stt",
        )

    def synthesize(self, request: VoiceActionRequest, text: str) -> VoiceSynthesisObservation:
        return VoiceSynthesisObservation(
            succeeded=True,
            audio_ref="evidence:voice-synthesis:fake.mp3",
            audio_hash="f" * 64,
            duration_ms=100,
            adapter_id="openai:fake-tts",
        )


class FakeEmailCalendarAdapter:
    """Deterministic email/calendar observation fixture."""

    def perform(self, request: EmailCalendarActionRequest) -> EmailCalendarActionObservation:
        return EmailCalendarActionObservation(
            succeeded=True,
            connector_id=request.connector_id,
            provider_operation=request.action,
            resource_id="email-search-live",
            response_digest="email-search-digest",
            external_write=False,
        )


def _browser_executor():
    adapter = FakeBrowserAdapter()
    policy = BrowserWorkerPolicy()

    def execute(request: BrowserActionRequest):
        return execute_browser_request(request, adapter=adapter, policy=policy)

    return execute


def _voice_executor():
    adapter = FakeVoiceAdapter()
    policy = VoiceWorkerPolicy()

    def execute(request: VoiceActionRequest):
        return execute_voice_request(request, adapter=adapter, policy=policy)

    return execute


def _email_calendar_executor():
    adapter = FakeEmailCalendarAdapter()
    policy = EmailCalendarWorkerPolicy()

    def execute(request: EmailCalendarActionRequest):
        return execute_email_calendar_request(request, adapter=adapter, policy=policy)

    return execute


def _write_browser_sandbox_evidence(tmp_path: Path) -> Path:
    evidence_path = tmp_path / "browser-sandbox-evidence.json"
    produce_browser_sandbox_evidence(
        output_path=evidence_path,
        workspace_root=tmp_path,
        runner=_sandbox_success_runner,
        platform_system=lambda: "Linux",
    )
    return evidence_path


def _sandbox_success_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args[0], 0, stdout="Python 3.13", stderr="")
