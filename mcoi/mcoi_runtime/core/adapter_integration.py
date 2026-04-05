"""Purpose: adapter integration bridge.
Governance scope: connecting channel adapters and artifact parsers to
    commitment extraction, memory mesh, event spine, and obligation runtime.
Dependencies: ChannelAdapterRegistry, ArtifactParserRegistry,
    CommitmentExtractionEngine, EventSpineEngine, MemoryMeshEngine.
Invariants:
  - Every adapter/parser operation emits an event.
  - Extracted commitments are routed to obligation runtime.
  - All outputs are immutable.
  - Adapter health is surfaced via events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.channel_adapter import (
    AdapterStatus,
    ChannelAdapterFamily,
    NormalizedInbound,
)
from ..contracts.artifact_parser import (
    NormalizedParseOutput,
    ParserFamily,
)
from ..contracts.commitment_extraction import CommitmentSourceType
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .channel_adapters import ChannelAdapterRegistry
from .artifact_parsers import ArtifactParserRegistry
from .commitment_extraction import CommitmentExtractionEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-adapt", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AdapterIntegrationBridge:
    """Connects adapters and parsers to extraction, memory, and event spine."""

    def __init__(
        self,
        channel_registry: ChannelAdapterRegistry,
        parser_registry: ArtifactParserRegistry,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
        extraction_engine: CommitmentExtractionEngine,
    ) -> None:
        if not isinstance(channel_registry, ChannelAdapterRegistry):
            raise RuntimeCoreInvariantError(
                "channel_registry must be a ChannelAdapterRegistry"
            )
        if not isinstance(parser_registry, ArtifactParserRegistry):
            raise RuntimeCoreInvariantError(
                "parser_registry must be a ArtifactParserRegistry"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError(
                "memory_engine must be a MemoryMeshEngine"
            )
        if not isinstance(extraction_engine, CommitmentExtractionEngine):
            raise RuntimeCoreInvariantError(
                "extraction_engine must be a CommitmentExtractionEngine"
            )
        self._channels = channel_registry
        self._parsers = parser_registry
        self._events = event_spine
        self._memory = memory_engine
        self._extraction = extraction_engine

    # ------------------------------------------------------------------
    # Channel adapter operations
    # ------------------------------------------------------------------

    def ingest_via_adapter(
        self, adapter_id: str, raw: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Normalize an inbound message via adapter, emit event, record memory."""
        normalized = self._channels.normalize_inbound(adapter_id, raw)

        event = _emit(self._events, "adapter_inbound_normalized", {
            "adapter_id": adapter_id,
            "family": normalized.family.value,
            "message_id": normalized.message_id,
            "sender": normalized.sender_address,
        }, normalized.message_id)

        # Record in memory
        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-adapt-in", {
                "mid": normalized.message_id, "ts": now,
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=normalized.message_id,
            trust_level=MemoryTrustLevel.UNVERIFIED,
            title="Inbound message",
            content={
                "message_id": normalized.message_id,
                "adapter_id": adapter_id,
                "family": normalized.family.value,
                "sender": normalized.sender_address,
                "body_length": len(normalized.body_text),
            },
            source_ids=(adapter_id,),
            tags=("adapter", "inbound", normalized.family.value),
            confidence=0.8,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        return {"normalized": normalized, "event": event, "memory": mem}

    def ingest_and_extract_commitments(
        self, adapter_id: str, raw: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Normalize inbound, extract commitments, emit events."""
        ingest_result = self.ingest_via_adapter(adapter_id, raw)
        normalized: NormalizedInbound = ingest_result["normalized"]

        # Extract commitments from body text
        extraction_result = self._extraction.extract_from_text(
            normalized.body_text,
            source_type=CommitmentSourceType.MESSAGE,
            source_ref_id=normalized.message_id,
        )

        event = _emit(self._events, "adapter_commitments_extracted", {
            "adapter_id": adapter_id,
            "message_id": normalized.message_id,
            "candidate_count": len(extraction_result.candidates),
        }, normalized.message_id)

        return {
            "normalized": normalized,
            "extraction": extraction_result,
            "ingest_event": ingest_result["event"],
            "extraction_event": event,
            "memory": ingest_result["memory"],
        }

    def send_via_adapter(
        self, adapter_id: str, recipient: str, body: str, **kwargs: Any,
    ) -> dict[str, Any]:
        """Format and emit an outbound message via adapter."""
        outbound = self._channels.format_outbound(adapter_id, recipient, body, **kwargs)

        event = _emit(self._events, "adapter_outbound_sent", {
            "adapter_id": adapter_id,
            "family": outbound.family.value,
            "message_id": outbound.message_id,
            "recipient": recipient,
        }, outbound.message_id)

        return {"outbound": outbound, "event": event}

    def check_adapter_health(
        self, adapter_id: str,
    ) -> dict[str, Any]:
        """Health-check an adapter and emit event."""
        report = self._channels.health_check(adapter_id)

        event = _emit(self._events, "adapter_health_checked", {
            "adapter_id": adapter_id,
            "status": report.status.value,
            "reliability": report.reliability_score,
        }, adapter_id)

        return {"report": report, "event": event}

    def check_all_adapter_health(self) -> dict[str, Any]:
        """Health-check all adapters, emit aggregate event."""
        reports = self._channels.health_check_all()

        statuses = {}
        for r in reports:
            statuses[r.adapter_id] = r.status.value

        event = _emit(self._events, "all_adapters_health_checked", {
            "adapter_count": len(reports),
            "statuses": statuses,
        }, "health-check-all")

        return {"reports": reports, "event": event}

    def route_by_family(
        self, family: ChannelAdapterFamily, recipient: str, body: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Route an outbound message to the best adapter in a family."""
        adapters = self._channels.route_by_family(family)
        if not adapters:
            event = _emit(self._events, "adapter_routing_failed", {
                "family": family.value,
                "reason": "no available adapters",
            }, f"route-{family.value}")
            return {"outbound": None, "event": event, "adapter_count": 0}

        # Use first available adapter (deterministic ordering)
        adapter = adapters[0]
        outbound = adapter.format_outbound(recipient, body, **kwargs)

        event = _emit(self._events, "adapter_routed", {
            "family": family.value,
            "adapter_id": adapter.adapter_id(),
            "message_id": outbound.message_id,
            "recipient": recipient,
        }, outbound.message_id)

        return {
            "outbound": outbound,
            "event": event,
            "adapter_count": len(adapters),
        }

    # ------------------------------------------------------------------
    # Artifact parser operations
    # ------------------------------------------------------------------

    def parse_artifact(
        self, parser_id: str, artifact_id: str, filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Parse an artifact, emit event, record memory."""
        output = self._parsers.parse(parser_id, artifact_id, filename, content)

        event = _emit(self._events, "artifact_parsed", {
            "parser_id": parser_id,
            "artifact_id": artifact_id,
            "family": output.family.value,
            "output_kind": output.output_kind.value,
            "word_count": output.word_count,
        }, artifact_id)

        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-parse", {
                "aid": artifact_id, "ts": now,
            }),
            memory_type=MemoryType.ARTIFACT,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=artifact_id,
            trust_level=MemoryTrustLevel.UNVERIFIED,
            title="Parsed artifact",
            content={
                "artifact_id": artifact_id,
                "parser_id": parser_id,
                "family": output.family.value,
                "output_kind": output.output_kind.value,
                "word_count": output.word_count,
                "page_count": output.page_count,
                "has_images": output.has_images,
                "has_tables": output.has_tables,
            },
            source_ids=(parser_id,),
            tags=("parser", "artifact", output.family.value),
            confidence=0.8,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        return {"output": output, "event": event, "memory": mem}

    def auto_parse_artifact(
        self, artifact_id: str, filename: str, content: bytes,
        mime_type: str = "",
    ) -> dict[str, Any]:
        """Auto-select parser and parse, emit event."""
        output = self._parsers.auto_parse(artifact_id, filename, content, mime_type)

        if output is None:
            event = _emit(self._events, "artifact_parse_no_parser", {
                "artifact_id": artifact_id,
                "filename": filename,
                "mime_type": mime_type,
            }, artifact_id)
            return {"output": None, "event": event}

        event = _emit(self._events, "artifact_auto_parsed", {
            "parser_id": output.parser_id,
            "artifact_id": artifact_id,
            "family": output.family.value,
            "output_kind": output.output_kind.value,
        }, artifact_id)

        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-autoparse", {
                "aid": artifact_id, "ts": now,
            }),
            memory_type=MemoryType.ARTIFACT,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=artifact_id,
            trust_level=MemoryTrustLevel.UNVERIFIED,
            title="Auto-parsed artifact",
            content={
                "artifact_id": artifact_id,
                "parser_id": output.parser_id,
                "family": output.family.value,
                "word_count": output.word_count,
            },
            source_ids=(output.parser_id,),
            tags=("parser", "auto-parsed", output.family.value),
            confidence=0.7,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        return {"output": output, "event": event, "memory": mem}

    def parse_and_extract_commitments(
        self, parser_id: str, artifact_id: str, filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Parse artifact and extract commitments from its text content."""
        parse_result = self.parse_artifact(parser_id, artifact_id, filename, content)
        output: NormalizedParseOutput = parse_result["output"]

        if not output.text_content:
            return {
                "output": output,
                "extraction": None,
                "parse_event": parse_result["event"],
                "memory": parse_result["memory"],
            }

        extraction = self._extraction.extract_from_text(
            output.text_content,
            source_type=CommitmentSourceType.ARTIFACT,
            source_ref_id=artifact_id,
        )

        event = _emit(self._events, "artifact_commitments_extracted", {
            "parser_id": parser_id,
            "artifact_id": artifact_id,
            "candidate_count": len(extraction.candidates),
        }, artifact_id)

        return {
            "output": output,
            "extraction": extraction,
            "parse_event": parse_result["event"],
            "extraction_event": event,
            "memory": parse_result["memory"],
        }

    def check_parser_health(self, parser_id: str) -> dict[str, Any]:
        """Health-check a parser and emit event."""
        report = self._parsers.health_check(parser_id)

        event = _emit(self._events, "parser_health_checked", {
            "parser_id": parser_id,
            "status": report.status.value,
            "reliability": report.reliability_score,
        }, parser_id)

        return {"report": report, "event": event}

    def check_all_parser_health(self) -> dict[str, Any]:
        """Health-check all parsers, emit aggregate event."""
        reports = self._parsers.health_check_all()

        statuses = {}
        for r in reports:
            statuses[r.parser_id] = r.status.value

        event = _emit(self._events, "all_parsers_health_checked", {
            "parser_count": len(reports),
            "statuses": statuses,
        }, "parser-health-check-all")

        return {"reports": reports, "event": event}
