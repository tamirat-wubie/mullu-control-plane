"""Purpose: capability negotiation and fallback routing engine.
Governance scope: evaluating capabilities, policy, rate limits, health,
    domain-pack preferences, and choosing the best provider/connector with
    deterministic fallback when needed.
Dependencies: external_connectors, channel_adapters, artifact_parsers,
    external_connector contracts, event_spine, core invariants.
Invariants:
  - Negotiation evaluates all governance dimensions before selection.
  - Fallback is deterministic and auditable.
  - Every negotiation emits an event with the decision trace.
  - Returned results are immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.external_connector import (
    ConnectorCapabilityBinding,
    ConnectorHealthState,
    ExternalConnectorDescriptor,
    FallbackStrategy,
)
from ..contracts.channel_adapter import ChannelAdapterFamily
from ..contracts.artifact_parser import ParserFamily
from ..contracts.event import EventRecord, EventSource, EventType
from .external_connectors import ExternalConnector, ExternalConnectorRegistry
from .channel_adapters import ChannelAdapterRegistry
from .artifact_parsers import ArtifactParserRegistry
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-neg", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# ---------------------------------------------------------------------------
# Negotiation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NegotiationResult:
    """Immutable result of a capability negotiation."""
    selected_connector_id: str | None
    selected_adapter_id: str | None
    selected_parser_id: str | None
    candidates_evaluated: int
    candidates_rejected: int
    rejection_reasons: tuple[str, ...]
    fallback_used: bool
    strategy: str
    negotiated_at: str


# ---------------------------------------------------------------------------
# Capability Negotiation Engine
# ---------------------------------------------------------------------------


class CapabilityNegotiationEngine:
    """Evaluates capabilities, policy, rate limits, health, and domain
    preferences to choose the best connector/adapter/parser, with
    deterministic fallback."""

    def __init__(
        self,
        connector_registry: ExternalConnectorRegistry,
        channel_registry: ChannelAdapterRegistry,
        parser_registry: ArtifactParserRegistry,
        event_spine: EventSpineEngine,
    ) -> None:
        if not isinstance(connector_registry, ExternalConnectorRegistry):
            raise RuntimeCoreInvariantError(
                "connector_registry must be an ExternalConnectorRegistry"
            )
        if not isinstance(channel_registry, ChannelAdapterRegistry):
            raise RuntimeCoreInvariantError(
                "channel_registry must be a ChannelAdapterRegistry"
            )
        if not isinstance(parser_registry, ArtifactParserRegistry):
            raise RuntimeCoreInvariantError(
                "parser_registry must be an ArtifactParserRegistry"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        self._connectors = connector_registry
        self._channels = channel_registry
        self._parsers = parser_registry
        self._events = event_spine

    # ------------------------------------------------------------------
    # Channel negotiation
    # ------------------------------------------------------------------

    def negotiate_channel(
        self,
        family: ChannelAdapterFamily,
        *,
        min_reliability: float = 0.0,
        max_latency_ms: float = 0.0,
        required_tags: tuple[str, ...] = (),
        prefer_live: bool = True,
    ) -> NegotiationResult:
        """Negotiate the best channel adapter for a family.

        Evaluates all adapters in the family, checks connector health
        and governance, and returns the best match.
        """
        now = _now_iso()
        adapters = self._channels.route_by_family(family)
        evaluated = 0
        rejected = 0
        reasons: list[str] = []
        selected_adapter_id: str | None = None
        selected_connector_id: str | None = None

        # Score candidates
        candidates: list[tuple[float, str, str | None]] = []

        for adapter in adapters:
            evaluated += 1
            aid = adapter.adapter_id()
            desc = self._channels.get_descriptor(aid)

            # Check required tags
            if required_tags:
                if not all(t in desc.tags for t in required_tags):
                    rejected += 1
                    reasons.append(f"{aid}: missing required tags")
                    continue

            # Check if backed by connector
            bindings = self._connectors.get_bindings_for_adapter(aid)
            if bindings:
                binding = bindings[0]
                cid = binding.connector_id

                # Check connector health
                health = self._connectors.get_health(cid)
                if health and health.health_state not in (
                    ConnectorHealthState.HEALTHY,
                    ConnectorHealthState.DEGRADED,
                ):
                    rejected += 1
                    reasons.append(f"{aid}: connector {cid} unhealthy")
                    continue

                # Check reliability
                if min_reliability > 0 and binding.reliability_score < min_reliability:
                    rejected += 1
                    reasons.append(f"{aid}: reliability {binding.reliability_score} < {min_reliability}")
                    continue

                # Check latency
                if max_latency_ms > 0 and health and health.avg_latency_ms > max_latency_ms:
                    rejected += 1
                    reasons.append(f"{aid}: latency {health.avg_latency_ms} > {max_latency_ms}")
                    continue

                # Check rate limit
                if not self._connectors.check_rate_limit(cid):
                    rejected += 1
                    reasons.append(f"{aid}: rate limited")
                    continue

                # Check quota
                if not self._connectors.check_quota(cid):
                    rejected += 1
                    reasons.append(f"{aid}: quota exhausted")
                    continue

                # Score: live adapters get a boost
                score = binding.reliability_score
                if prefer_live:
                    score += 0.1
                candidates.append((score, aid, cid))
            else:
                # Test/local adapter — no connector governance
                score = 0.5
                if prefer_live:
                    score -= 0.1
                candidates.append((score, aid, None))

        # Select best candidate
        fallback_used = False
        if candidates:
            candidates.sort(key=lambda c: (-c[0], c[1]))
            selected_adapter_id = candidates[0][1]
            selected_connector_id = candidates[0][2]
            if len(candidates) > 1 and candidates[0][0] < candidates[1][0]:
                fallback_used = True

        result = NegotiationResult(
            selected_connector_id=selected_connector_id,
            selected_adapter_id=selected_adapter_id,
            selected_parser_id=None,
            candidates_evaluated=evaluated,
            candidates_rejected=rejected,
            rejection_reasons=tuple(reasons),
            fallback_used=fallback_used,
            strategy="capability_match",
            negotiated_at=now,
        )

        _emit(self._events, "channel_negotiated", {
            "family": family.value,
            "selected_adapter": selected_adapter_id,
            "selected_connector": selected_connector_id,
            "evaluated": evaluated,
            "rejected": rejected,
        }, f"neg-ch-{family.value}")

        return result

    # ------------------------------------------------------------------
    # Parser negotiation
    # ------------------------------------------------------------------

    def negotiate_parser(
        self,
        filename: str,
        mime_type: str = "",
        size_bytes: int = 0,
        *,
        min_reliability: float = 0.0,
        prefer_live: bool = True,
    ) -> NegotiationResult:
        """Negotiate the best parser for a file.

        Evaluates all parsers that can handle the file, checks connector
        health and governance, and returns the best match.
        """
        now = _now_iso()
        parsers = self._parsers.select_for_file(filename, mime_type, size_bytes)
        evaluated = 0
        rejected = 0
        reasons: list[str] = []

        candidates: list[tuple[float, str, str | None]] = []

        for parser in parsers:
            evaluated += 1
            pid = parser.parser_id()

            bindings = self._connectors.get_bindings_for_parser(pid)
            if bindings:
                binding = bindings[0]
                cid = binding.connector_id

                health = self._connectors.get_health(cid)
                if health and health.health_state not in (
                    ConnectorHealthState.HEALTHY,
                    ConnectorHealthState.DEGRADED,
                ):
                    rejected += 1
                    reasons.append(f"{pid}: connector {cid} unhealthy")
                    continue

                if min_reliability > 0 and binding.reliability_score < min_reliability:
                    rejected += 1
                    reasons.append(f"{pid}: reliability too low")
                    continue

                if not self._connectors.check_rate_limit(cid):
                    rejected += 1
                    reasons.append(f"{pid}: rate limited")
                    continue

                score = binding.reliability_score
                if prefer_live:
                    score += 0.1
                candidates.append((score, pid, cid))
            else:
                score = 0.5
                if prefer_live:
                    score -= 0.1
                candidates.append((score, pid, None))

        selected_parser_id: str | None = None
        selected_connector_id: str | None = None
        fallback_used = False

        if candidates:
            candidates.sort(key=lambda c: (-c[0], c[1]))
            selected_parser_id = candidates[0][1]
            selected_connector_id = candidates[0][2]
            if len(candidates) > 1 and candidates[0][0] < candidates[1][0]:
                fallback_used = True

        result = NegotiationResult(
            selected_connector_id=selected_connector_id,
            selected_adapter_id=None,
            selected_parser_id=selected_parser_id,
            candidates_evaluated=evaluated,
            candidates_rejected=rejected,
            rejection_reasons=tuple(reasons),
            fallback_used=fallback_used,
            strategy="capability_match",
            negotiated_at=now,
        )

        _emit(self._events, "parser_negotiated", {
            "filename": filename,
            "selected_parser": selected_parser_id,
            "selected_connector": selected_connector_id,
            "evaluated": evaluated,
            "rejected": rejected,
        }, f"neg-ps-{filename}")

        return result

    # ------------------------------------------------------------------
    # Connector fallback negotiation
    # ------------------------------------------------------------------

    def negotiate_connector_fallback(
        self,
        chain_id: str,
    ) -> NegotiationResult:
        """Walk a fallback chain and return the best available connector."""
        now = _now_iso()
        connector = self._connectors.resolve_fallback(chain_id)
        chain = self._connectors.get_fallback_chain(chain_id)

        evaluated = len(chain.entries) if chain else 0
        selected_id = connector.connector_id() if connector else None

        result = NegotiationResult(
            selected_connector_id=selected_id,
            selected_adapter_id=None,
            selected_parser_id=None,
            candidates_evaluated=evaluated,
            candidates_rejected=evaluated - (1 if selected_id else 0),
            rejection_reasons=(),
            fallback_used=selected_id is not None and evaluated > 1,
            strategy=(chain.strategy.value if chain else "none"),
            negotiated_at=now,
        )

        _emit(self._events, "connector_fallback_negotiated", {
            "chain_id": chain_id,
            "selected_connector": selected_id,
            "evaluated": evaluated,
        }, f"neg-fb-{chain_id}")

        return result

    # ------------------------------------------------------------------
    # Combined negotiation
    # ------------------------------------------------------------------

    def negotiate_outbound(
        self,
        family: ChannelAdapterFamily,
        recipient: str,
        body: str,
        *,
        min_reliability: float = 0.0,
        max_latency_ms: float = 0.0,
        fallback_chain_id: str | None = None,
    ) -> dict[str, Any]:
        """Full outbound negotiation: select adapter, optionally fall back, send."""
        result = self.negotiate_channel(
            family,
            min_reliability=min_reliability,
            max_latency_ms=max_latency_ms,
        )

        if result.selected_adapter_id:
            adapter = self._channels.get_adapter(result.selected_adapter_id)
            outbound = adapter.format_outbound(recipient, body)
            return {
                "negotiation": result,
                "outbound": outbound,
                "success": True,
            }

        # Try fallback chain if provided
        if fallback_chain_id:
            fb_result = self.negotiate_connector_fallback(fallback_chain_id)
            if fb_result.selected_connector_id:
                return {
                    "negotiation": fb_result,
                    "outbound": None,
                    "success": False,
                    "fallback_connector": fb_result.selected_connector_id,
                }

        return {
            "negotiation": result,
            "outbound": None,
            "success": False,
        }

    def negotiate_parse(
        self,
        artifact_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "",
        *,
        min_reliability: float = 0.0,
    ) -> dict[str, Any]:
        """Full parse negotiation: select parser, parse, return result."""
        result = self.negotiate_parser(
            filename, mime_type, len(content),
            min_reliability=min_reliability,
        )

        if result.selected_parser_id:
            output = self._parsers.parse(
                result.selected_parser_id, artifact_id, filename, content,
            )
            return {
                "negotiation": result,
                "output": output,
                "success": True,
            }

        return {
            "negotiation": result,
            "output": None,
            "success": False,
        }
