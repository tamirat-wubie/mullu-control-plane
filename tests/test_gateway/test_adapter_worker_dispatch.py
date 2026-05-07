"""Tests for adapter worker capability dispatch.

Purpose: ensure browser, document, and voice capabilities are exposed as
governed dispatcher records while execution remains in signed workers.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.adapter_worker_clients import AdapterWorkerResponse  # noqa: E402
from gateway.skill_dispatch import (  # noqa: E402
    SkillDispatcher,
    SkillIntent,
    build_skill_dispatcher_from_platform,
    register_browser_capabilities,
    register_document_capabilities,
    register_email_calendar_capabilities,
    register_voice_capabilities,
)


class RecordingAdapterWorkerClient:
    """Worker client fixture that records request payloads."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def execute(self, payload):
        self.payloads.append(dict(payload))
        capability_id = str(payload["capability_id"])
        request_id = str(payload["request_id"])
        return AdapterWorkerResponse(
            request_id=request_id,
            status="succeeded",
            result={"observed": capability_id},
            receipt={
                "request_id": request_id,
                "tenant_id": str(payload["tenant_id"]),
                "capability_id": capability_id,
                "verification_status": "passed",
                "evidence_refs": [f"{capability_id}:test"],
            },
            error="",
            raw={},
        )


class PlatformWithAdapterWorkerClients:
    """Platform fixture exposing adapter worker clients directly."""

    def __init__(self) -> None:
        self.browser_worker_client = RecordingAdapterWorkerClient()
        self.document_worker_client = RecordingAdapterWorkerClient()
        self.voice_worker_client = RecordingAdapterWorkerClient()
        self.email_calendar_worker_client = RecordingAdapterWorkerClient()


def test_browser_capability_dispatches_through_signed_worker_client() -> None:
    worker_client = RecordingAdapterWorkerClient()
    dispatcher = SkillDispatcher()
    register_browser_capabilities(dispatcher, browser_worker_client=worker_client)

    result = dispatcher.dispatch(
        SkillIntent("browser", "extract_text", {"url": "https://docs.mullusi.com/guide"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
        command_id="cmd-browser-1",
    )

    assert result is not None
    assert result["capability_id"] == "browser.extract_text"
    assert result["receipt_status"] == "succeeded"
    assert result["verification_status"] == "passed"
    assert worker_client.payloads[0]["action"] == "browser.extract_text"
    assert worker_client.payloads[0]["tenant_id"] == "tenant-1"


def test_document_capability_dispatches_document_payload() -> None:
    worker_client = RecordingAdapterWorkerClient()
    dispatcher = SkillDispatcher()
    register_document_capabilities(dispatcher, document_worker_client=worker_client)

    result = dispatcher.dispatch(
        SkillIntent("spreadsheet", "generate", {"rows": [{"name": "A", "value": 1}], "title": "Report"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["capability_id"] == "spreadsheet.generate"
    assert result["worker_receipt"]["capability_id"] == "spreadsheet.generate"
    assert worker_client.payloads[0]["rows"] == [{"name": "A", "value": 1}]
    assert worker_client.payloads[0]["title"] == "Report"
    assert worker_client.payloads[0]["metadata"]["identity_id"] == "identity-1"


def test_voice_capability_dispatches_transcript_only_intent() -> None:
    worker_client = RecordingAdapterWorkerClient()
    dispatcher = SkillDispatcher()
    register_voice_capabilities(dispatcher, voice_worker_client=worker_client)

    result = dispatcher.dispatch(
        SkillIntent("voice", "intent_classification", {"transcript": "send a status message"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
        conversation_id="conv-1",
    )

    assert result is not None
    assert result["capability_id"] == "voice.intent_classification"
    assert result["receipt_status"] == "succeeded"
    assert worker_client.payloads[0]["session_id"] == "conv-1"
    assert worker_client.payloads[0]["transcript_text"] == "send a status message"
    assert worker_client.payloads[0]["metadata"]["conversation_id"] == "conv-1"


def test_email_calendar_capability_dispatches_communication_payload() -> None:
    worker_client = RecordingAdapterWorkerClient()
    dispatcher = SkillDispatcher()
    register_email_calendar_capabilities(dispatcher, email_calendar_worker_client=worker_client)

    result = dispatcher.dispatch(
        SkillIntent(
            "email",
            "send.with_approval",
            {
                "connector_id": "gmail",
                "recipients": ["user@example.com"],
                "subject": "Status",
                "body": "Ready",
                "approval_id": "approval-1",
            },
        ),
        tenant_id="tenant-1",
        identity_id="identity-1",
        command_id="cmd-email-1",
    )

    assert result is not None
    assert result["capability_id"] == "email.send.with_approval"
    assert result["receipt_status"] == "succeeded"
    assert worker_client.payloads[0]["connector_id"] == "gmail"
    assert worker_client.payloads[0]["recipients"] == ["user@example.com"]
    assert worker_client.payloads[0]["approval_id"] == "approval-1"
    assert worker_client.payloads[0]["metadata"]["command_id"] == "cmd-email-1"


def test_adapter_capability_fails_closed_without_worker_client() -> None:
    dispatcher = SkillDispatcher()
    register_browser_capabilities(dispatcher)

    result = dispatcher.dispatch(
        SkillIntent("browser", "extract_text", {"url": "https://docs.mullusi.com/guide"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["capability_id"] == "browser.extract_text"
    assert result["receipt_status"] == "worker_unavailable"
    assert result["worker_status"] == "unavailable"
    assert result["worker_plane"] == "browser"


def test_platform_builder_registers_adapter_worker_clients(monkeypatch) -> None:
    monkeypatch.delenv("MULLU_BROWSER_WORKER_URL", raising=False)
    monkeypatch.delenv("MULLU_BROWSER_WORKER_SECRET", raising=False)
    monkeypatch.delenv("MULLU_DOCUMENT_WORKER_URL", raising=False)
    monkeypatch.delenv("MULLU_DOCUMENT_WORKER_SECRET", raising=False)
    monkeypatch.delenv("MULLU_VOICE_WORKER_URL", raising=False)
    monkeypatch.delenv("MULLU_VOICE_WORKER_SECRET", raising=False)
    monkeypatch.delenv("MULLU_EMAIL_CALENDAR_WORKER_URL", raising=False)
    monkeypatch.delenv("MULLU_EMAIL_CALENDAR_WORKER_SECRET", raising=False)
    platform = PlatformWithAdapterWorkerClients()
    dispatcher = build_skill_dispatcher_from_platform(platform)

    result = dispatcher.dispatch(
        SkillIntent("browser", "open", {"url": "https://docs.mullusi.com"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert result is not None
    assert result["capability_id"] == "browser.open"
    assert result["receipt_status"] == "succeeded"
    assert platform.browser_worker_client.payloads[0]["url"] == "https://docs.mullusi.com"
    assert platform.document_worker_client.payloads == []
    assert platform.voice_worker_client.payloads == []
    assert platform.email_calendar_worker_client.payloads == []

    email_result = dispatcher.dispatch(
        SkillIntent("email", "draft", {"recipients": ["user@example.com"], "body": "hello"}),
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert email_result is not None
    assert email_result["capability_id"] == "email.draft"
    assert email_result["receipt_status"] == "succeeded"
    assert platform.email_calendar_worker_client.payloads[0]["connector_id"] == "gmail"
