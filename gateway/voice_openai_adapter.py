"""Gateway Voice OpenAI Adapter - concrete voice worker backend.

Purpose: perform speech-to-text and text-to-speech requests through an
OpenAI-compatible client while returning only transcript and synthesis evidence
to the signed voice-worker contract.
Governance scope: no audio persistence, transcript-only tool intent handoff,
provider error containment, and receipt-compatible observations.
Dependencies: gateway.voice_worker contracts and optional OpenAI SDK runtime.
Invariants:
  - The adapter never executes tools or sends messages.
  - Audio bytes are used only inside the provider call and are not stored.
  - Synthesis returns a content hash and evidence reference, not raw audio.
  - Provider failures return explicit unavailable observations.
"""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass
from typing import Any

from gateway.voice_worker import (
    VoiceActionRequest,
    VoiceSynthesisObservation,
    VoiceTranscriptObservation,
)


@dataclass(frozen=True, slots=True)
class OpenAIVoiceAdapterProfile:
    """Runtime profile for one OpenAI-compatible voice adapter."""

    transcription_model: str = "whisper-1"
    speech_model: str = "tts-1"
    speech_voice: str = "alloy"
    speech_format: str = "mp3"

    def __post_init__(self) -> None:
        _require_text(self.transcription_model, "transcription_model")
        _require_text(self.speech_model, "speech_model")
        _require_text(self.speech_voice, "speech_voice")
        if self.speech_format not in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
            raise ValueError("speech_format is unsupported")


class OpenAIVoiceAdapter:
    """Concrete OpenAI-compatible implementation for voice-worker requests."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        profile: OpenAIVoiceAdapterProfile | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client = client
        self._profile = profile or OpenAIVoiceAdapterProfile()
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")

    def transcribe(self, request: VoiceActionRequest, audio_bytes: bytes) -> VoiceTranscriptObservation:
        """Transcribe audio into text without storing audio."""
        if request.transcript_text.strip():
            transcript = request.transcript_text.strip()
            return VoiceTranscriptObservation(
                succeeded=True,
                transcript=transcript,
                confidence=1.0,
                adapter_id="openai:transcript_passthrough",
            )
        if not audio_bytes:
            return VoiceTranscriptObservation(
                succeeded=False,
                adapter_id="openai",
                error="audio input is required for transcription",
            )
        try:
            client = self._resolve_client()
            audio_stream = io.BytesIO(audio_bytes)
            audio_stream.name = str(request.metadata.get("filename", "voice-input.wav"))
            response = client.audio.transcriptions.create(
                model=self._profile.transcription_model,
                file=audio_stream,
                response_format="json",
            )
            transcript = _response_text(response)
            return VoiceTranscriptObservation(
                succeeded=bool(transcript),
                transcript=transcript,
                confidence=1.0 if transcript else 0.0,
                adapter_id=f"openai:{self._profile.transcription_model}",
                error="" if transcript else "transcription response did not contain text",
            )
        except Exception as exc:  # noqa: BLE001
            return VoiceTranscriptObservation(
                succeeded=False,
                adapter_id=f"openai:{self._profile.transcription_model}",
                error=f"voice transcription failed: {type(exc).__name__}",
            )

    def synthesize(self, request: VoiceActionRequest, text: str) -> VoiceSynthesisObservation:
        """Create an ephemeral speech output and return only hash evidence."""
        if not text.strip():
            return VoiceSynthesisObservation(
                succeeded=False,
                adapter_id="openai",
                error="text input is required for synthesis",
            )
        try:
            client = self._resolve_client()
            response = client.audio.speech.create(
                model=self._profile.speech_model,
                voice=self._profile.speech_voice,
                input=text,
                response_format=self._profile.speech_format,
            )
            audio_bytes = _response_bytes(response)
            audio_hash = hashlib.sha256(audio_bytes).hexdigest()
            return VoiceSynthesisObservation(
                succeeded=bool(audio_bytes),
                audio_ref=f"evidence:voice-synthesis:{audio_hash[:16]}.{self._profile.speech_format}",
                audio_hash=audio_hash,
                duration_ms=0,
                adapter_id=f"openai:{self._profile.speech_model}",
                error="" if audio_bytes else "synthesis response did not contain audio",
            )
        except Exception as exc:  # noqa: BLE001
            return VoiceSynthesisObservation(
                succeeded=False,
                adapter_id=f"openai:{self._profile.speech_model}",
                error=f"voice synthesis failed: {type(exc).__name__}",
            )

    def _resolve_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI voice adapter")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAI voice adapter") from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client


def _response_text(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("text", "")).strip()
    return str(getattr(response, "text", "")).strip()


def _response_bytes(response: Any) -> bytes:
    if isinstance(response, bytes):
        return response
    if hasattr(response, "read") and callable(response.read):
        value = response.read()
        return value if isinstance(value, bytes) else bytes(value)
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    return b""


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
