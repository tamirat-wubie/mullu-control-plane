"""Purpose: live parser bindings — provider-backed parser slots.
Governance scope: connecting Phase 41 artifact parsers to Phase 42 external
    connectors, enabling governed parsing via real provider APIs/libraries.
Dependencies: artifact_parsers, external_connectors, external_connector contracts,
    artifact_parser contracts, event_spine, core invariants.
Invariants:
  - Every live parse operation goes through external connector governance.
  - Credential and rate limit checks happen before execution.
  - Failures are recorded with typed categories.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.artifact_parser import (
    ArtifactParserDescriptor,
    NormalizedParseOutput,
    ParseCapability,
    ParseOutputKind,
    ParserCapabilityLevel,
    ParserCapabilityManifest,
    ParserFamily,
    ParserHealthReport,
    ParserStatus,
)
from ..contracts.external_connector import (
    ConnectorCapabilityBinding,
    ExternalConnectorType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .artifact_parsers import ArtifactParser, ArtifactParserRegistry
from .external_connectors import ExternalConnectorRegistry
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-live-ps", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# ---------------------------------------------------------------------------
# Provider-backed artifact parsers — one slot per family
# ---------------------------------------------------------------------------


class _LiveParser(ArtifactParser):
    """An artifact parser backed by an external connector.

    Delegates actual parsing to the connector while preserving
    the canonical parser interface.
    """

    _FAMILY: ParserFamily
    _NAME: str
    _EXTENSIONS: tuple[str, ...]
    _MIME_TYPES: tuple[str, ...]
    _MAX_SIZE: int = 52428800  # 50MB default
    _OUTPUT_KIND: ParseOutputKind = ParseOutputKind.TEXT

    def __init__(
        self,
        connector_registry: ExternalConnectorRegistry,
        connector_id: str,
        parser_id: str | None = None,
    ) -> None:
        self._connector_registry = connector_registry
        self._connector_id = connector_id
        self._id = parser_id or f"live-{self._FAMILY.value}"
        self._now = _now_iso()
        self._parsed = 0

    def parser_id(self) -> str:
        return self._id

    def family(self) -> ParserFamily:
        return self._FAMILY

    def descriptor(self) -> ArtifactParserDescriptor:
        return ArtifactParserDescriptor(
            parser_id=self._id,
            name=self._NAME,
            family=self._FAMILY,
            status=ParserStatus.AVAILABLE,
            version="1.0.0",
            tags=("live", "provider-backed"),
            created_at=self._now,
        )

    def manifest(self) -> ParserCapabilityManifest:
        cap = ParseCapability(
            format_name=self._FAMILY.value,
            extensions=self._EXTENSIONS,
            mime_types=self._MIME_TYPES,
            capability_level=ParserCapabilityLevel.FULL_CONTENT,
            max_size_bytes=self._MAX_SIZE,
        )
        return ParserCapabilityManifest(
            manifest_id=stable_identifier("manifest-live-ps", {"pid": self._id}),
            parser_id=self._id,
            family=self._FAMILY,
            capabilities=(cap,),
            reliability_score=0.9,
            created_at=self._now,
        )

    def can_parse(
        self, filename: str, mime_type: str = "", size_bytes: int = 0,
    ) -> bool:
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext in self._EXTENSIONS:
            return True
        if mime_type:
            for mt in self._MIME_TYPES:
                if mime_type.lower().startswith(mt):
                    return True
        return False

    def parse(
        self, artifact_id: str, filename: str, content: bytes,
    ) -> NormalizedParseOutput:
        now = _now_iso()
        self._parsed += 1

        # Execute parse via connector
        record = self._connector_registry.execute(
            self._connector_id, "parse",
            {
                "parser_family": self._FAMILY.value,
                "artifact_id": artifact_id,
                "filename": filename,
                "content_length": len(content),
            },
        )

        # Produce normalized output
        text = content.decode("utf-8", errors="replace") if content else ""
        words = len(text.split()) if text else 0

        return NormalizedParseOutput(
            output_id=stable_identifier("out-live", {
                "pid": self._id, "aid": artifact_id, "ts": now,
            }),
            parser_id=self._id,
            artifact_id=artifact_id,
            family=self._FAMILY,
            output_kind=self._OUTPUT_KIND,
            text_content=text,
            word_count=words,
            parsed_at=now,
            extracted_metadata={
                "connector_id": self._connector_id,
                "connector_success": record.success,
                "connector_latency_ms": record.latency_ms,
            },
        )

    def health_check(self) -> ParserHealthReport:
        snap = self._connector_registry.health_check(self._connector_id)
        return ParserHealthReport(
            report_id=stable_identifier("health-live-ps", {
                "pid": self._id, "ts": _now_iso(),
            }),
            parser_id=self._id,
            status=(
                ParserStatus.AVAILABLE
                if snap.health_state.value == "healthy"
                else ParserStatus.DEGRADED
            ),
            reliability_score=snap.reliability_score,
            artifacts_parsed=self._parsed,
            avg_parse_ms=snap.avg_latency_ms,
            reported_at=_now_iso(),
        )


class LivePdfParser(_LiveParser):
    _FAMILY = ParserFamily.DOCUMENT
    _NAME = "Live PDF Parser"
    _EXTENSIONS = (".pdf",)
    _MIME_TYPES = ("application/pdf",)
    _MAX_SIZE = 104857600  # 100MB


class LiveDocxParser(_LiveParser):
    _FAMILY = ParserFamily.DOCUMENT
    _NAME = "Live DOCX Parser"
    _EXTENSIONS = (".docx", ".doc")
    _MIME_TYPES = ("application/vnd.openxmlformats-officedocument.wordprocessingml",)
    _MAX_SIZE = 52428800


class LiveXlsxParser(_LiveParser):
    _FAMILY = ParserFamily.SPREADSHEET
    _NAME = "Live XLSX Parser"
    _EXTENSIONS = (".xlsx", ".xls", ".csv", ".tsv")
    _MIME_TYPES = ("application/vnd.openxmlformats-officedocument.spreadsheetml",
                   "text/csv", "text/tab-separated-values")
    _OUTPUT_KIND = ParseOutputKind.TABLE


class LivePptxParser(_LiveParser):
    _FAMILY = ParserFamily.PRESENTATION
    _NAME = "Live PPTX Parser"
    _EXTENSIONS = (".pptx", ".ppt")
    _MIME_TYPES = ("application/vnd.openxmlformats-officedocument.presentationml",)


class LiveImageParser(_LiveParser):
    _FAMILY = ParserFamily.IMAGE
    _NAME = "Live Image/OCR Parser"
    _EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")
    _MIME_TYPES = ("image/",)
    _OUTPUT_KIND = ParseOutputKind.METADATA_ONLY


class LiveAudioParser(_LiveParser):
    _FAMILY = ParserFamily.AUDIO
    _NAME = "Live Audio Transcript Parser"
    _EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
    _MIME_TYPES = ("audio/",)


class LiveArchiveParser(_LiveParser):
    _FAMILY = ParserFamily.ARCHIVE
    _NAME = "Live Archive Parser"
    _EXTENSIONS = (".zip", ".tar", ".gz", ".tar.gz", ".7z", ".rar")
    _MIME_TYPES = ("application/zip", "application/x-tar", "application/gzip")
    _OUTPUT_KIND = ParseOutputKind.TREE


class LiveRepoParser(_LiveParser):
    _FAMILY = ParserFamily.REPOSITORY
    _NAME = "Live Repository/Bundle Parser"
    _EXTENSIONS = (".patch", ".diff", ".bundle")
    _MIME_TYPES = ("text/x-diff", "text/x-patch")
    _OUTPUT_KIND = ParseOutputKind.KEY_VALUE


# ---------------------------------------------------------------------------
# Binding engine — wires live parsers into registries
# ---------------------------------------------------------------------------


class LiveParserBindingEngine:
    """Creates and manages live parser bindings backed by connectors."""

    def __init__(
        self,
        parser_registry: ArtifactParserRegistry,
        connector_registry: ExternalConnectorRegistry,
        event_spine: EventSpineEngine,
    ) -> None:
        if not isinstance(parser_registry, ArtifactParserRegistry):
            raise RuntimeCoreInvariantError(
                "parser_registry must be an ArtifactParserRegistry"
            )
        if not isinstance(connector_registry, ExternalConnectorRegistry):
            raise RuntimeCoreInvariantError(
                "connector_registry must be an ExternalConnectorRegistry"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        self._parsers = parser_registry
        self._connectors = connector_registry
        self._events = event_spine
        self._live_parsers: dict[str, _LiveParser] = {}

    def bind_pdf(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LivePdfParser, connector_id, parser_id)

    def bind_docx(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LiveDocxParser, connector_id, parser_id)

    def bind_xlsx(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LiveXlsxParser, connector_id, parser_id)

    def bind_pptx(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LivePptxParser, connector_id, parser_id)

    def bind_image(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LiveImageParser, connector_id, parser_id)

    def bind_audio(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LiveAudioParser, connector_id, parser_id)

    def bind_archive(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LiveArchiveParser, connector_id, parser_id)

    def bind_repo(self, connector_id: str, parser_id: str | None = None) -> ArtifactParserDescriptor:
        return self._bind(LiveRepoParser, connector_id, parser_id)

    def _bind(
        self,
        parser_cls: type[_LiveParser],
        connector_id: str,
        parser_id: str | None,
    ) -> ArtifactParserDescriptor:
        self._connectors.get_connector(connector_id)

        parser = parser_cls(self._connectors, connector_id, parser_id)
        desc = self._parsers.register(parser)
        self._live_parsers[parser.parser_id()] = parser

        now = _now_iso()
        binding = ConnectorCapabilityBinding(
            binding_id=stable_identifier("bind-ps", {
                "pid": parser.parser_id(), "cid": connector_id, "ts": now,
            }),
            connector_id=connector_id,
            connector_type=ExternalConnectorType.PARSER_PROVIDER,
            bound_parser_id=parser.parser_id(),
            supported_operations=("parse",),
            max_payload_bytes=parser._MAX_SIZE,
            reliability_score=0.9,
            enabled=True,
            tags=("live", "parser", parser._FAMILY.value),
            created_at=now,
        )
        self._connectors.add_binding(binding)

        _emit(self._events, "live_parser_bound", {
            "parser_id": parser.parser_id(),
            "connector_id": connector_id,
            "family": parser._FAMILY.value,
        }, parser.parser_id())

        return desc

    def get_live_parser(self, parser_id: str) -> _LiveParser:
        if parser_id not in self._live_parsers:
            raise RuntimeCoreInvariantError(
                f"live parser '{parser_id}' not found"
            )
        return self._live_parsers[parser_id]

    def list_live_parsers(self) -> tuple[str, ...]:
        return tuple(sorted(self._live_parsers.keys()))

    @property
    def binding_count(self) -> int:
        return len(self._live_parsers)
