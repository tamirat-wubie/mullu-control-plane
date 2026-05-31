"""Voice worker PII-coverage tests.

Tests: the voice transcript redactor masks card, SSN, and IP values in addition
to email and phone, so spoken secrets do not survive into transcripts, receipts,
or responses. Guards the governance claim that the voice worker redacts PII.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.voice_worker import (  # noqa: E402
    VoiceActionRequest,
    VoiceSynthesisObservation,
    VoiceTranscriptObservation,
    VoiceWorkerPolicy,
    _redact_pii,
    execute_voice_request,
    voice_action_request_from_mapping,
)


class _FakeVoiceAdapter:
    def transcribe(self, request: VoiceActionRequest, audio_bytes: bytes) -> VoiceTranscriptObservation:
        return VoiceTranscriptObservation(
            succeeded=True, transcript="", confidence=0.9, adapter_id="fake-stt",
        )

    def synthesize(self, request: VoiceActionRequest, text: str) -> VoiceSynthesisObservation:
        return VoiceSynthesisObservation(
            succeeded=True, audio_ref="voice-artifact:x", audio_hash="x",
            duration_ms=1, adapter_id="fake-tts",
        )


def _request(transcript_text: str) -> VoiceActionRequest:
    return voice_action_request_from_mapping({
        "request_id": "voice-pii-1",
        "tenant_id": "tenant-1",
        "capability_id": "voice.intent_classification",
        "action": "voice.intent_classification",
        "session_id": "voice-session-1",
        "audio_base64": "",
        "transcript_text": transcript_text,
        "response_text": "",
        "approval_id": "",
        "metadata": {},
    })


# --- Unit: redactor coverage ---


class TestRedactPii:
    def test_card_number_masked(self):
        out = _redact_pii("my card is 4111 1111 1111 1111 ok")
        assert "4111" not in out
        assert "[redacted-card]" in out

    def test_card_number_dashed_masked(self):
        assert "4111" not in _redact_pii("4111-1111-1111-1111")

    def test_ssn_masked(self):
        out = _redact_pii("ssn 123-45-6789 please")
        assert "123-45-6789" not in out
        assert "[redacted-ssn]" in out

    def test_ip_masked(self):
        out = _redact_pii("connect to 192.168.10.20 now")
        assert "192.168.10.20" not in out
        assert "[redacted-ip]" in out

    def test_email_still_masked(self):
        assert _redact_pii("mail a@b.com") == "mail [redacted-email]"

    def test_phone_still_masked(self):
        assert _redact_pii("call 555-010-2222") == "call [redacted-phone]"

    def test_card_not_split_into_phone(self):
        # The longer card number must be masked as a card, not partially as phone.
        out = _redact_pii("4111 1111 1111 1111")
        assert "[redacted-phone]" not in out
        assert out == "[redacted-card]"

    def test_plain_text_unchanged(self):
        text = "Please summarize the support case."
        assert _redact_pii(text) == text


# --- Integration: redacted transcript flows through the worker ---


class TestVoiceWorkerIntegration:
    def test_spoken_card_is_redacted_in_response(self):
        request = _request("charge my card 4111 1111 1111 1111 today")
        response = execute_voice_request(
            request, adapter=_FakeVoiceAdapter(), policy=VoiceWorkerPolicy(),
        )
        assert "4111" not in response.result["transcript"]
        assert "[redacted-card]" in response.result["transcript"]
        assert response.status == "succeeded"

    def test_spoken_ssn_is_redacted_in_response(self):
        request = _request("my social is 123-45-6789")
        response = execute_voice_request(
            request, adapter=_FakeVoiceAdapter(), policy=VoiceWorkerPolicy(),
        )
        assert "123-45-6789" not in response.result["transcript"]
        assert "[redacted-ssn]" in response.result["transcript"]
