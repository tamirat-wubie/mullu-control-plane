"""OpenAI voice adapter tests.

Purpose: prove the concrete voice adapter returns governed transcript and
synthesis observations without storing raw audio.
Governance scope: provider response normalization, no audio persistence, and
fail-closed provider errors.
Dependencies: gateway.voice_openai_adapter.
Invariants:
  - Transcript passthrough avoids provider calls.
  - Provider audio responses are represented by hash evidence only.
  - Missing provider credentials fail with explicit observations.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.voice_openai_adapter import OpenAIVoiceAdapter  # noqa: E402
from gateway.voice_worker import VoiceActionRequest  # noqa: E402


def test_openai_voice_adapter_transcribes_audio_with_injected_client() -> None:
    client = FakeOpenAIClient(transcript="governed transcript", audio_bytes=b"speech")
    adapter = OpenAIVoiceAdapter(client=client)
    request = VoiceActionRequest(
        request_id="voice-openai-transcribe",
        tenant_id="tenant-1",
        capability_id="voice.speech_to_text",
        action="voice.speech_to_text",
        session_id="session-1",
        audio_base64=base64.b64encode(b"audio").decode("ascii"),
        metadata={"filename": "input.wav"},
    )

    observation = adapter.transcribe(request, b"audio")

    assert observation.succeeded is True
    assert observation.transcript == "governed transcript"
    assert observation.confidence == 1.0
    assert observation.adapter_id == "openai:whisper-1"
    assert client.audio.transcriptions.calls[0]["model"] == "whisper-1"
    assert client.audio.transcriptions.calls[0]["filename"] == "input.wav"


def test_openai_voice_adapter_synthesizes_hash_reference_only() -> None:
    client = FakeOpenAIClient(transcript="unused", audio_bytes=b"audio-result")
    adapter = OpenAIVoiceAdapter(client=client)
    request = VoiceActionRequest(
        request_id="voice-openai-synthesize",
        tenant_id="tenant-1",
        capability_id="voice.text_to_speech",
        action="voice.text_to_speech",
        session_id="session-1",
        response_text="Hello",
    )

    observation = adapter.synthesize(request, "Hello")

    assert observation.succeeded is True
    assert observation.audio_hash
    assert observation.audio_ref.startswith("evidence:voice-synthesis:")
    assert observation.audio_ref.endswith(".mp3")
    assert observation.adapter_id == "openai:tts-1"
    assert client.audio.speech.calls[0]["input"] == "Hello"


def test_openai_voice_adapter_reports_missing_credentials() -> None:
    adapter = OpenAIVoiceAdapter(api_key="")
    request = VoiceActionRequest(
        request_id="voice-openai-missing-key",
        tenant_id="tenant-1",
        capability_id="voice.speech_to_text",
        action="voice.speech_to_text",
        session_id="session-1",
    )

    observation = adapter.transcribe(request, b"audio")

    assert observation.succeeded is False
    assert observation.transcript == ""
    assert observation.confidence == 0.0
    assert observation.adapter_id == "openai:whisper-1"
    assert "RuntimeError" in observation.error


class FakeOpenAIClient:
    def __init__(self, *, transcript: str, audio_bytes: bytes) -> None:
        self.audio = FakeAudioNamespace(transcript=transcript, audio_bytes=audio_bytes)


class FakeAudioNamespace:
    def __init__(self, *, transcript: str, audio_bytes: bytes) -> None:
        self.transcriptions = FakeTranscriptions(transcript)
        self.speech = FakeSpeech(audio_bytes)


class FakeTranscriptions:
    def __init__(self, transcript: str) -> None:
        self._transcript = transcript
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, file: object, response_format: str) -> dict[str, str]:
        self.calls.append(
            {
                "model": model,
                "filename": getattr(file, "name", ""),
                "response_format": response_format,
            }
        )
        return {"text": self._transcript}


class FakeSpeech:
    def __init__(self, audio_bytes: bytes) -> None:
        self._audio_bytes = audio_bytes
        self.calls: list[dict[str, str]] = []

    def create(
        self,
        *,
        model: str,
        voice: str,
        input: str,
        response_format: str,
    ) -> "FakeSpeechResponse":
        self.calls.append(
            {
                "model": model,
                "voice": voice,
                "input": input,
                "response_format": response_format,
            }
        )
        return FakeSpeechResponse(self._audio_bytes)


class FakeSpeechResponse:
    def __init__(self, audio_bytes: bytes) -> None:
        self.content = audio_bytes
