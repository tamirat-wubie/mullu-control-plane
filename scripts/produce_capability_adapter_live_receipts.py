#!/usr/bin/env python3
"""Produce live capability adapter receipts.

Purpose: write browser, document, voice, and communication live receipts
consumed by the capability adapter evidence collector.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: governed browser/document/voice/email-calendar workers and
optional production adapter runtimes.
Invariants:
  - Browser closure requires explicit sandbox evidence before it can pass.
  - Document closure requires all production parser families to be registered.
  - Voice closure requires real audio input for speech-to-text and synthesis.
  - Communication closure probes the signed email/calendar worker with a
    read-only action; connector adapter production closure is separately gated.
  - Failed probes still write receipts with explicit blockers.
  - Provider credentials and raw audio are never written to receipts.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

DEFAULT_BROWSER_RECEIPT = REPO_ROOT / ".change_assurance" / "browser_live_receipt.json"
DEFAULT_DOCUMENT_RECEIPT = REPO_ROOT / ".change_assurance" / "document_live_receipt.json"
DEFAULT_VOICE_RECEIPT = REPO_ROOT / ".change_assurance" / "voice_live_receipt.json"
DEFAULT_EMAIL_CALENDAR_RECEIPT = REPO_ROOT / ".change_assurance" / "email_calendar_live_receipt.json"
REQUIRED_DOCUMENT_PARSERS = frozenset(
    {
        "production-pdf",
        "production-docx",
        "production-xlsx",
        "production-pptx",
    }
)


class BrowserExecutor(Protocol):
    """Callable browser execution contract used by tests and live probes."""

    def __call__(self, request: Any) -> Any:
        """Execute a browser request and return a worker response."""


class VoiceExecutor(Protocol):
    """Callable voice execution contract used by tests and live probes."""

    def __call__(self, request: Any) -> Any:
        """Execute a voice request and return a worker response."""


class EmailCalendarExecutor(Protocol):
    """Callable email/calendar execution contract used by tests and live probes."""

    def __call__(self, request: Any) -> Any:
        """Execute an email/calendar request and return a worker response."""


DocumentParserProbe = Callable[[], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class LiveReceiptWrite:
    """One live receipt write result."""

    adapter_id: str
    status: str
    output_path: str
    blockers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether the receipt passed."""
        return self.status == "passed" and not self.blockers

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt write summary."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LiveReceiptRun:
    """Summary of a live receipt production run."""

    status: str
    checked_at: str
    writes: tuple[LiveReceiptWrite, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready run summary."""
        return {
            "status": self.status,
            "checked_at": self.checked_at,
            "writes": [write.as_dict() for write in self.writes],
            "blockers": list(self.blockers),
        }


def produce_browser_live_receipt(
    *,
    output_path: Path = DEFAULT_BROWSER_RECEIPT,
    target_url: str = "https://docs.mullusi.com/",
    sandbox_evidence_ref: str = "",
    executor: BrowserExecutor | None = None,
    clock: Callable[[], str] | None = None,
) -> LiveReceiptWrite:
    """Produce one browser live receipt."""
    checked_at = (clock or _validation_clock)()
    sandbox_evidence = _validate_browser_sandbox_evidence(sandbox_evidence_ref)
    blockers: list[str] = list(sandbox_evidence["blockers"])
    try:
        from gateway.browser_worker import BrowserActionRequest

        resolved_executor = executor or _default_browser_executor()
        request = BrowserActionRequest(
            request_id="browser-live-receipt",
            tenant_id="tenant-adapter-evidence",
            capability_id="browser.extract_text",
            action="browser.extract_text",
            url=target_url,
        )
        response = resolved_executor(request)
        worker_receipt = asdict(response.receipt)
        status = "passed" if response.status == "succeeded" and not blockers else "failed"
        if response.status != "succeeded":
            blockers.append("browser_worker_probe_failed")
        payload = {
            "receipt_id": _receipt_id("browser", checked_at, worker_receipt),
            "adapter_id": "browser.playwright",
            "status": status,
            "verification_status": "passed" if status == "passed" else "failed",
            "checked_at": checked_at,
            "sandboxed_worker": sandbox_evidence["passed"],
            "sandbox_evidence_ref": sandbox_evidence_ref,
            "sandbox_evidence_status": sandbox_evidence["status"],
            "sandbox_evidence_detail": sandbox_evidence["detail"],
            "sandbox_evidence_id": sandbox_evidence["evidence_id"],
            "sandbox_receipt_id": sandbox_evidence["receipt_id"],
            "url_before": response.receipt.url_before,
            "url_after": response.receipt.url_after,
            "screenshot_before_ref": response.receipt.screenshot_before_ref,
            "screenshot_after_ref": response.receipt.screenshot_after_ref,
            "network_requests": list(response.receipt.network_requests),
            "worker_receipt": _json_ready(worker_receipt),
            "blockers": blockers,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"browser_probe_exception:{type(exc).__name__}")
        payload = _failed_payload(
            adapter_id="browser.playwright",
            checked_at=checked_at,
            blockers=blockers,
            error=str(exc),
        )
        payload.update(
            {
                "sandboxed_worker": sandbox_evidence["passed"],
                "sandbox_evidence_ref": sandbox_evidence_ref,
                "sandbox_evidence_status": sandbox_evidence["status"],
                "sandbox_evidence_detail": sandbox_evidence["detail"],
                "sandbox_evidence_id": sandbox_evidence["evidence_id"],
                "sandbox_receipt_id": sandbox_evidence["receipt_id"],
            }
        )
    _write_json(output_path, payload)
    return LiveReceiptWrite(
        adapter_id="browser.playwright",
        status=str(payload["status"]),
        output_path=str(output_path),
        blockers=tuple(blockers),
    )


def produce_document_live_receipt(
    *,
    output_path: Path = DEFAULT_DOCUMENT_RECEIPT,
    parser_probe: DocumentParserProbe | None = None,
    clock: Callable[[], str] | None = None,
) -> LiveReceiptWrite:
    """Produce one document parser live receipt."""
    checked_at = (clock or _validation_clock)()
    blockers: list[str] = []
    try:
        parser_ids = tuple(parser_probe() if parser_probe is not None else _production_parser_ids())
        missing_parsers = tuple(sorted(REQUIRED_DOCUMENT_PARSERS - set(parser_ids)))
        blockers.extend(f"document_parser_missing:{parser_id}" for parser_id in missing_parsers)
        status = "passed" if not blockers else "failed"
        payload = {
            "receipt_id": _receipt_id("document", checked_at, parser_ids),
            "adapter_id": "document.production_parsers",
            "status": status,
            "verification_status": "passed" if status == "passed" else "failed",
            "checked_at": checked_at,
            "parser_ids": list(parser_ids),
            "production_parser_ids": list(parser_ids),
            "required_parser_ids": sorted(REQUIRED_DOCUMENT_PARSERS),
            "blockers": blockers,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"document_probe_exception:{type(exc).__name__}")
        payload = _failed_payload(
            adapter_id="document.production_parsers",
            checked_at=checked_at,
            blockers=blockers,
            error=str(exc),
        )
    _write_json(output_path, payload)
    return LiveReceiptWrite(
        adapter_id="document.production_parsers",
        status=str(payload["status"]),
        output_path=str(output_path),
        blockers=tuple(blockers),
    )


def produce_voice_live_receipt(
    *,
    output_path: Path = DEFAULT_VOICE_RECEIPT,
    audio_path: Path | None = None,
    synthesis_text: str = "Mullu governed voice adapter receipt.",
    executor: VoiceExecutor | None = None,
    clock: Callable[[], str] | None = None,
) -> LiveReceiptWrite:
    """Produce one voice live receipt."""
    checked_at = (clock or _validation_clock)()
    blockers: list[str] = []
    try:
        audio_bytes = _read_audio(audio_path)
        if not audio_bytes:
            blockers.append("voice_audio_input_missing")
        resolved_executor = executor or _default_voice_executor()
        from gateway.voice_worker import VoiceActionRequest

        speech_response = resolved_executor(
            VoiceActionRequest(
                request_id="voice-live-stt-receipt",
                tenant_id="tenant-adapter-evidence",
                capability_id="voice.speech_to_text",
                action="voice.speech_to_text",
                session_id="voice-live-session",
                audio_base64=base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else "",
                metadata={"filename": audio_path.name if audio_path else ""},
            )
        )
        synthesis_response = resolved_executor(
            VoiceActionRequest(
                request_id="voice-live-tts-receipt",
                tenant_id="tenant-adapter-evidence",
                capability_id="voice.text_to_speech",
                action="voice.text_to_speech",
                session_id="voice-live-session",
                response_text=synthesis_text,
            )
        )
        speech_status = "passed" if speech_response.status == "succeeded" else "failed"
        synthesis_status = "passed" if synthesis_response.status == "succeeded" else "failed"
        if speech_status != "passed":
            blockers.append("voice_speech_to_text_failed")
        if synthesis_status != "passed":
            blockers.append("voice_text_to_speech_failed")
        status = "passed" if not blockers else "failed"
        payload = {
            "receipt_id": _receipt_id(
                "voice",
                checked_at,
                {
                    "speech_receipt": speech_response.receipt.receipt_id,
                    "synthesis_receipt": synthesis_response.receipt.receipt_id,
                },
            ),
            "adapter_id": "voice.openai",
            "status": status,
            "verification_status": "passed" if status == "passed" else "failed",
            "checked_at": checked_at,
            "speech_to_text_status": speech_status,
            "text_to_speech_status": synthesis_status,
            "audio_input_hash": hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else "",
            "speech_receipt": _json_ready(asdict(speech_response.receipt)),
            "synthesis_receipt": _json_ready(asdict(synthesis_response.receipt)),
            "blockers": blockers,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"voice_probe_exception:{type(exc).__name__}")
        payload = _failed_payload(
            adapter_id="voice.openai",
            checked_at=checked_at,
            blockers=blockers,
            error=str(exc),
        )
    _write_json(output_path, payload)
    return LiveReceiptWrite(
        adapter_id="voice.openai",
        status=str(payload["status"]),
        output_path=str(output_path),
        blockers=tuple(blockers),
    )


def produce_email_calendar_live_receipt(
    *,
    output_path: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    connector_id: str = "gmail",
    query: str = "newer_than:1d",
    executor: EmailCalendarExecutor | None = None,
    clock: Callable[[], str] | None = None,
) -> LiveReceiptWrite:
    """Produce one email/calendar worker live receipt."""
    checked_at = (clock or _validation_clock)()
    blockers: list[str] = []
    try:
        from gateway.email_calendar_worker import EmailCalendarActionRequest

        resolved_executor = executor or _default_email_calendar_executor()
        response = resolved_executor(
            EmailCalendarActionRequest(
                request_id="email-calendar-live-receipt",
                tenant_id="tenant-adapter-evidence",
                capability_id="email.search",
                action="email.search",
                connector_id=connector_id,
                query=query,
            )
        )
        if response.status != "succeeded":
            blockers.append("email_calendar_worker_probe_failed")
        external_write = bool(getattr(response.receipt, "external_write", True))
        if external_write:
            blockers.append("email_calendar_probe_observed_external_write")
        status = "passed" if not blockers else "failed"
        worker_receipt = asdict(response.receipt)
        payload = {
            "receipt_id": _receipt_id("email-calendar", checked_at, worker_receipt),
            "adapter_id": "communication.email_calendar_worker",
            "status": status,
            "verification_status": "passed" if status == "passed" else "failed",
            "checked_at": checked_at,
            "connector_id": response.receipt.connector_id,
            "provider_operation": response.receipt.provider_operation,
            "resource_id": response.receipt.resource_id,
            "response_digest": response.receipt.response_digest,
            "external_write": external_write,
            "worker_receipt": _json_ready(worker_receipt),
            "blockers": blockers,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"email_calendar_probe_exception:{type(exc).__name__}")
        payload = _failed_payload(
            adapter_id="communication.email_calendar_worker",
            checked_at=checked_at,
            blockers=blockers,
            error=str(exc),
        )
        payload["external_write"] = True
    _write_json(output_path, payload)
    return LiveReceiptWrite(
        adapter_id="communication.email_calendar_worker",
        status=str(payload["status"]),
        output_path=str(output_path),
        blockers=tuple(blockers),
    )


def produce_live_receipts(
    *,
    target: str,
    browser_output: Path = DEFAULT_BROWSER_RECEIPT,
    document_output: Path = DEFAULT_DOCUMENT_RECEIPT,
    voice_output: Path = DEFAULT_VOICE_RECEIPT,
    email_calendar_output: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    browser_url: str = "https://docs.mullusi.com/",
    browser_sandbox_evidence: str = "",
    voice_audio_path: Path | None = None,
    voice_text: str = "Mullu governed voice adapter receipt.",
    clock: Callable[[], str] | None = None,
) -> LiveReceiptRun:
    """Produce requested live receipts and return a run summary."""
    resolved_clock = clock or _validation_clock
    writes: list[LiveReceiptWrite] = []
    if target in {"all", "browser"}:
        writes.append(
            produce_browser_live_receipt(
                output_path=browser_output,
                target_url=browser_url,
                sandbox_evidence_ref=browser_sandbox_evidence,
                clock=resolved_clock,
            )
        )
    if target in {"all", "document"}:
        writes.append(produce_document_live_receipt(output_path=document_output, clock=resolved_clock))
    if target in {"all", "voice"}:
        writes.append(
            produce_voice_live_receipt(
                output_path=voice_output,
                audio_path=voice_audio_path,
                synthesis_text=voice_text,
                clock=resolved_clock,
            )
        )
    if target in {"all", "email-calendar"}:
        writes.append(produce_email_calendar_live_receipt(output_path=email_calendar_output, clock=resolved_clock))
    blockers = tuple(blocker for write in writes for blocker in write.blockers)
    return LiveReceiptRun(
        status="passed" if not blockers else "failed",
        checked_at=resolved_clock(),
        writes=tuple(writes),
        blockers=blockers,
    )


def _default_browser_executor() -> BrowserExecutor:
    from gateway.browser_playwright_adapter import PlaywrightBrowserAdapter
    from gateway.browser_worker import BrowserActionRequest, BrowserActionResponse, BrowserWorkerPolicy, execute_browser_request

    adapter = PlaywrightBrowserAdapter()
    policy = BrowserWorkerPolicy()

    def execute(request: BrowserActionRequest) -> BrowserActionResponse:
        return execute_browser_request(request, adapter=adapter, policy=policy)

    return execute


def _validate_browser_sandbox_evidence(sandbox_evidence_ref: str) -> dict[str, Any]:
    ref = sandbox_evidence_ref.strip()
    if not ref:
        return {
            "passed": False,
            "status": "failed",
            "detail": "missing sandbox evidence reference",
            "evidence_id": "",
            "receipt_id": "",
            "blockers": ("browser_sandbox_evidence_missing",),
        }

    evidence_path = Path(ref)
    if not evidence_path.is_absolute():
        evidence_path = REPO_ROOT / evidence_path
    if not evidence_path.exists():
        return {
            "passed": False,
            "status": "failed",
            "detail": f"sandbox evidence file not found: {ref}",
            "evidence_id": "",
            "receipt_id": "",
            "blockers": ("browser_sandbox_evidence_unverified",),
        }

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "status": "failed",
            "detail": f"sandbox evidence unreadable: {type(exc).__name__}",
            "evidence_id": "",
            "receipt_id": "",
            "blockers": ("browser_sandbox_evidence_unverified",),
        }
    if not isinstance(payload, dict):
        return {
            "passed": False,
            "status": "failed",
            "detail": "sandbox evidence root must be an object",
            "evidence_id": "",
            "receipt_id": "",
            "blockers": ("browser_sandbox_evidence_unverified",),
        }

    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else payload
    evidence_id = str(payload.get("evidence_id", "")).strip()
    receipt_id = str(receipt.get("receipt_id", "")).strip()
    errors: list[str] = []
    if not receipt_id:
        errors.append("receipt_id_missing")
    if not str(receipt.get("sandbox_id", "")).strip():
        errors.append("sandbox_id_missing")
    capability_id = str(receipt.get("capability_id", "")).strip()
    if not capability_id.startswith("browser."):
        errors.append("capability_id_not_browser")
    if receipt.get("verification_status") != "passed":
        errors.append("verification_status_not_passed")
    if receipt.get("network_disabled") is not True:
        errors.append("network_disabled_not_true")
    if receipt.get("read_only_rootfs") is not True:
        errors.append("read_only_rootfs_not_true")
    if receipt.get("workspace_mount") != "/workspace":
        errors.append("workspace_mount_not_workspace")
    if receipt.get("forbidden_effects_observed") is not False:
        errors.append("forbidden_effects_observed_not_false")
    if receipt.get("changed_file_count", 0) != 0:
        errors.append("changed_file_count_not_zero")
    if receipt.get("changed_file_refs", ()) not in ((), []):
        errors.append("changed_file_refs_not_empty")

    if errors:
        return {
            "passed": False,
            "status": "failed",
            "detail": ",".join(errors),
            "evidence_id": evidence_id,
            "receipt_id": receipt_id,
            "blockers": ("browser_sandbox_evidence_invalid",),
        }
    return {
        "passed": True,
        "status": "passed",
        "detail": f"sandbox receipt verified: {receipt_id}",
        "evidence_id": evidence_id,
        "receipt_id": receipt_id,
        "blockers": (),
    }


def _default_voice_executor() -> VoiceExecutor:
    from gateway.voice_openai_adapter import OpenAIVoiceAdapter
    from gateway.voice_worker import VoiceActionRequest, VoiceActionResponse, VoiceWorkerPolicy, execute_voice_request

    adapter = OpenAIVoiceAdapter()
    policy = VoiceWorkerPolicy()

    def execute(request: VoiceActionRequest) -> VoiceActionResponse:
        return execute_voice_request(request, adapter=adapter, policy=policy)

    return execute


def _default_email_calendar_executor() -> EmailCalendarExecutor:
    from gateway.email_calendar_connector_adapters import build_email_calendar_adapter_from_env
    from gateway.email_calendar_worker import (
        EmailCalendarActionRequest,
        EmailCalendarActionResponse,
        EmailCalendarWorkerPolicy,
        UnavailableEmailCalendarAdapter,
        execute_email_calendar_request,
    )

    adapter = build_email_calendar_adapter_from_env() or UnavailableEmailCalendarAdapter()
    policy = EmailCalendarWorkerPolicy()

    def execute(request: EmailCalendarActionRequest) -> EmailCalendarActionResponse:
        return execute_email_calendar_request(request, adapter=adapter, policy=policy)

    return execute


def _production_parser_ids() -> tuple[str, ...]:
    from gateway.document_production_parsers import register_optional_production_parsers
    from mcoi_runtime.core.artifact_parsers import ArtifactParserRegistry

    registry = ArtifactParserRegistry()
    register_optional_production_parsers(registry)
    return tuple(descriptor.parser_id for descriptor in registry.list_parsers())


def _read_audio(audio_path: Path | None) -> bytes:
    if audio_path is None:
        return b""
    return audio_path.read_bytes()


def _failed_payload(
    *,
    adapter_id: str,
    checked_at: str,
    blockers: list[str],
    error: str,
) -> dict[str, Any]:
    return {
        "receipt_id": _receipt_id(adapter_id, checked_at, {"error": error, "blockers": blockers}),
        "adapter_id": adapter_id,
        "status": "failed",
        "verification_status": "failed",
        "checked_at": checked_at,
        "error": error,
        "blockers": blockers,
    }


def _receipt_id(prefix: str, checked_at: str, material: Any) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {"prefix": prefix, "checked_at": checked_at, "material": _json_ready(material)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{prefix}-live-receipt-{digest[:16]}"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value


def _validation_clock() -> str:
    return "2026-05-01T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse live receipt producer arguments."""
    parser = argparse.ArgumentParser(description="Produce governed capability adapter live receipts.")
    parser.add_argument(
        "--target",
        choices=("all", "browser", "document", "voice", "email-calendar"),
        default="all",
    )
    parser.add_argument("--browser-output", default=str(DEFAULT_BROWSER_RECEIPT))
    parser.add_argument("--document-output", default=str(DEFAULT_DOCUMENT_RECEIPT))
    parser.add_argument("--voice-output", default=str(DEFAULT_VOICE_RECEIPT))
    parser.add_argument("--email-calendar-output", default=str(DEFAULT_EMAIL_CALENDAR_RECEIPT))
    parser.add_argument("--browser-url", default="https://docs.mullusi.com/")
    parser.add_argument(
        "--browser-sandbox-evidence",
        default="",
        help="Evidence reference proving the browser probe ran in the sandboxed worker.",
    )
    parser.add_argument("--voice-audio-path", default="")
    parser.add_argument("--voice-text", default="Mullu governed voice adapter receipt.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON run output.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any requested receipt fails.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for live receipt production."""
    args = parse_args(argv)
    run = produce_live_receipts(
        target=args.target,
        browser_output=Path(args.browser_output),
        document_output=Path(args.document_output),
        voice_output=Path(args.voice_output),
        email_calendar_output=Path(args.email_calendar_output),
        browser_url=args.browser_url,
        browser_sandbox_evidence=args.browser_sandbox_evidence,
        voice_audio_path=Path(args.voice_audio_path) if args.voice_audio_path else None,
        voice_text=args.voice_text,
    )
    if args.json:
        print(json.dumps(run.as_dict(), indent=2, sort_keys=True))
    elif run.status == "passed":
        print("CAPABILITY ADAPTER LIVE RECEIPTS PASSED")
    else:
        print(f"CAPABILITY ADAPTER LIVE RECEIPTS FAILED blockers={list(run.blockers)}")
    return 0 if run.status == "passed" or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
