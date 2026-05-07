"""Purpose: read-only lineage query resolution for governed outputs and traces.

Governance scope: parses lineage URIs, projects replay traces and command
events into causal nodes, and exposes unresolved ancestors explicitly without
mutating runtime state.
Dependencies: execution replay recorder contracts, command ledger read
interfaces, and stdlib URI parsing.
Invariants: lineage queries are read-only; missing sources are explicit; tenant
context is always present; verification state is bounded.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse


DEFAULT_INCLUDE = ("policy", "model", "tenant", "budget", "tool", "replay")
SUPPORTED_INCLUDE = frozenset(DEFAULT_INCLUDE)
SUPPORTED_REF_TYPES = frozenset({"trace", "output", "command"})
MAX_DEPTH = 100
MAX_TRACE_INDEX_SCAN = 1000


class ReplayTraceSource(Protocol):
    """Read-only subset required from a replay recorder."""

    def get_trace(self, trace_id: str) -> Any | None:
        """Return a completed replay trace when present."""

    def list_traces(self, limit: int = 50) -> list[Any]:
        """Return a bounded slice of completed replay traces."""


class CommandLineageSource(Protocol):
    """Read-only command ledger subset required for command lineage."""

    def get(self, command_id: str) -> Any | None:
        """Return a command envelope when present."""

    def events_for(self, command_id: str) -> list[Any]:
        """Return hash-linked command events for a command."""


@dataclass(frozen=True, slots=True)
class LineageRef:
    """Parsed lineage URI reference."""

    ref_type: str
    ref_id: str

    def __post_init__(self) -> None:
        if self.ref_type not in SUPPORTED_REF_TYPES:
            raise ValueError("unsupported lineage ref_type")
        if not self.ref_id:
            raise ValueError("lineage ref_id is required")


@dataclass(frozen=True, slots=True)
class LineageQuery:
    """Bounded lineage query envelope."""

    uri: str
    ref: LineageRef
    depth: int = 25
    include: tuple[str, ...] = DEFAULT_INCLUDE
    verify: bool = True

    def __post_init__(self) -> None:
        if not self.uri:
            raise ValueError("lineage uri is required")
        if self.depth < 1:
            raise ValueError("depth must be at least 1")
        if self.depth > MAX_DEPTH:
            raise ValueError(f"depth must be at most {MAX_DEPTH}")
        unsupported_include = tuple(
            include_item for include_item in self.include if include_item not in SUPPORTED_INCLUDE
        )
        if unsupported_include:
            raise ValueError("unsupported lineage include value")


@dataclass(frozen=True, slots=True)
class LineageNode:
    """Single causal lineage node."""

    node_id: str
    node_type: str
    parent_node_ids: tuple[str, ...]
    trace_id: str
    policy_version: str
    model_version: str
    tenant_id: str
    budget_ref: str
    proof_id: str
    state_hash: str
    timestamp: str
    unresolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "parent_node_ids": list(self.parent_node_ids),
            "trace_id": self.trace_id,
            "policy_version": self.policy_version,
            "model_version": self.model_version,
            "tenant_id": self.tenant_id,
            "budget_ref": self.budget_ref,
            "proof_id": self.proof_id,
            "state_hash": self.state_hash,
            "timestamp": self.timestamp,
            "unresolved": self.unresolved,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LineageEdge:
    """Directed causal edge between lineage nodes."""

    from_node_id: str
    to_node_id: str
    relation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "relation": self.relation,
        }


@dataclass(frozen=True, slots=True)
class PolicyVersionProjection:
    """Top-level read-model projection for lineage policy versions."""

    policy_version: str
    node_ids: tuple[str, ...]
    tenant_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "node_count": len(self.node_ids),
            "node_ids": list(self.node_ids),
            "tenant_ids": list(self.tenant_ids),
        }


def parse_lineage_uri(uri: str) -> LineageQuery:
    """Parse a lineage URI into a bounded query envelope."""
    parsed = urlparse(uri)
    if parsed.scheme != "lineage":
        raise ValueError("lineage uri must use lineage scheme")
    ref_type = parsed.netloc
    ref_id = parsed.path.lstrip("/")
    query = parse_qs(parsed.query)
    raw_depth = query.get("depth", ["25"])[0]
    try:
        depth = int(raw_depth)
    except (TypeError, ValueError) as exc:
        raise ValueError("depth must be an integer") from exc
    include_raw = query.get("include", [",".join(DEFAULT_INCLUDE)])[0]
    include = _normalize_include(include_raw)
    verify = query.get("verify", ["true"])[0].lower() != "false"
    return LineageQuery(
        uri=uri,
        ref=LineageRef(ref_type=ref_type, ref_id=ref_id),
        depth=depth,
        include=include or DEFAULT_INCLUDE,
        verify=verify,
    )


def _normalize_include(include_raw: str) -> tuple[str, ...]:
    """Return bounded include values in caller order without duplicates."""
    include: list[str] = []
    for raw_part in include_raw.split(","):
        include_item = raw_part.strip()
        if include_item and include_item not in include:
            include.append(include_item)
    return tuple(include) or DEFAULT_INCLUDE


def resolve_lineage_query(
    query: LineageQuery,
    *,
    replay_source: ReplayTraceSource,
    clock: Any,
    command_source: CommandLineageSource | None = None,
) -> dict[str, Any]:
    """Resolve a lineage query against read-only replay trace state."""
    if query.ref.ref_type == "command" and command_source is not None:
        command = command_source.get(query.ref.ref_id)
        if command is not None:
            nodes = tuple(_nodes_from_command(command, command_source.events_for(query.ref.ref_id), depth=query.depth))
            edges = tuple(_edges_from_nodes(nodes))
            reason_codes = _verify_graph(nodes, edges) if query.verify else ()
            verified = not reason_codes
            return _document(query, nodes=nodes, edges=edges, verified=verified, reason_codes=reason_codes)

    trace_id, trace = _trace_for_ref(query.ref, replay_source)
    if trace is None:
        node = _unresolved_node(query, trace_id=trace_id, timestamp=clock())
        return _document(query, nodes=(node,), edges=(), verified=False, reason_codes=("trace_not_found",))

    nodes = tuple(_nodes_from_replay_trace(trace, depth=query.depth))
    edges = tuple(_edges_from_nodes(nodes))
    reason_codes = _verify_graph(nodes, edges) if query.verify else ()
    verified = not reason_codes
    return _document(query, nodes=nodes, edges=edges, verified=verified, reason_codes=reason_codes)


def resolve_lineage_uri(
    uri: str,
    *,
    replay_source: ReplayTraceSource,
    clock: Any,
    command_source: CommandLineageSource | None = None,
) -> dict[str, Any]:
    """Parse and resolve a lineage URI."""
    return resolve_lineage_query(
        parse_lineage_uri(uri),
        replay_source=replay_source,
        clock=clock,
        command_source=command_source,
    )


def _trace_id_for_ref(ref: LineageRef) -> str:
    if ref.ref_type == "trace":
        return ref.ref_id
    return f"{ref.ref_type}:{ref.ref_id}"


def _trace_for_ref(ref: LineageRef, replay_source: ReplayTraceSource) -> tuple[str, Any | None]:
    direct_trace_id = _trace_id_for_ref(ref)
    direct_trace = replay_source.get_trace(direct_trace_id)
    if direct_trace is not None or ref.ref_type == "trace":
        return direct_trace_id, direct_trace

    indexed_trace = _find_trace_by_frame_ref(ref, replay_source)
    if indexed_trace is None:
        return direct_trace_id, None
    return str(getattr(indexed_trace, "trace_id")), indexed_trace


def _find_trace_by_frame_ref(ref: LineageRef, replay_source: ReplayTraceSource) -> Any | None:
    list_traces = getattr(replay_source, "list_traces", None)
    if not callable(list_traces):
        return None
    ref_key = f"{ref.ref_type}_id"
    for trace in reversed(tuple(list_traces(MAX_TRACE_INDEX_SCAN))):
        for frame in tuple(getattr(trace, "frames", ())):
            input_data = dict(getattr(frame, "input_data", {}) or {})
            output_data = dict(getattr(frame, "output_data", {}) or {})
            if input_data.get(ref_key) == ref.ref_id or output_data.get(ref_key) == ref.ref_id:
                return trace
    return None


def _nodes_from_replay_trace(trace: Any, *, depth: int) -> list[LineageNode]:
    nodes: list[LineageNode] = []
    for frame in tuple(trace.frames)[:depth]:
        parent_node_ids = (nodes[-1].node_id,) if nodes else ()
        input_data = dict(getattr(frame, "input_data", {}) or {})
        output_data = dict(getattr(frame, "output_data", {}) or {})
        nodes.append(
            LineageNode(
                node_id=getattr(frame, "frame_id"),
                node_type=str(getattr(frame, "operation")),
                parent_node_ids=parent_node_ids,
                trace_id=getattr(trace, "trace_id"),
                policy_version=str(input_data.get("policy_version") or output_data.get("policy_version") or "unknown"),
                model_version=str(input_data.get("model_version") or output_data.get("model_version") or "unknown"),
                tenant_id=str(input_data.get("tenant_id") or output_data.get("tenant_id") or "unknown"),
                budget_ref=str(input_data.get("budget_id") or output_data.get("budget_id") or "unknown"),
                proof_id=str(output_data.get("proof_id") or input_data.get("proof_id") or getattr(frame, "frame_hash")),
                state_hash=str(getattr(frame, "frame_hash")),
                timestamp=str(getattr(trace, "recorded_at")),
                metadata={
                    "sequence": getattr(frame, "sequence"),
                    "duration_ms": getattr(frame, "duration_ms"),
                },
            )
        )
    return nodes


def _nodes_from_command(command: Any, events: list[Any], *, depth: int) -> list[LineageNode]:
    command_id = str(getattr(command, "command_id"))
    root = LineageNode(
        node_id=f"command:{command_id}",
        node_type="command.envelope",
        parent_node_ids=(),
        trace_id=str(getattr(command, "trace_id")),
        policy_version=str(getattr(command, "policy_version")),
        model_version="unknown",
        tenant_id=str(getattr(command, "tenant_id")),
        budget_ref="unknown",
        proof_id=str(getattr(command, "payload_hash")),
        state_hash=str(getattr(command, "payload_hash")),
        timestamp=str(getattr(command, "created_at")),
        metadata={
            "actor_id": str(getattr(command, "actor_id")),
            "source": str(getattr(command, "source")),
            "intent": str(getattr(command, "intent")),
            "state": str(getattr(getattr(command, "state"), "value", getattr(command, "state"))),
        },
    )
    nodes = [root]
    for event in tuple(events)[: max(depth - 1, 0)]:
        parent_node_ids = (nodes[-1].node_id,)
        nodes.append(
            LineageNode(
                node_id=f"command-event:{getattr(event, 'event_id')}",
                node_type=f"command.{getattr(getattr(event, 'next_state'), 'value', getattr(event, 'next_state'))}",
                parent_node_ids=parent_node_ids,
                trace_id=str(getattr(event, "trace_id") or getattr(command, "trace_id")),
                policy_version=str(getattr(event, "policy_version")),
                model_version="unknown",
                tenant_id=str(getattr(event, "tenant_id")),
                budget_ref=str(getattr(event, "budget_decision") or "unknown"),
                proof_id=str(getattr(event, "event_hash")),
                state_hash=str(getattr(event, "event_hash")),
                timestamp=str(getattr(event, "timestamp")),
                metadata={
                    "command_id": command_id,
                    "previous_state": str(
                        getattr(getattr(event, "previous_state"), "value", getattr(event, "previous_state"))
                    ),
                    "next_state": str(getattr(getattr(event, "next_state"), "value", getattr(event, "next_state"))),
                    "prev_event_hash": str(getattr(event, "prev_event_hash")),
                    "risk_tier": str(getattr(event, "risk_tier")),
                    "approval_id": str(getattr(event, "approval_id")),
                    "tool_name": str(getattr(event, "tool_name")),
                },
            )
        )
    return nodes


def _edges_from_nodes(nodes: tuple[LineageNode, ...]) -> list[LineageEdge]:
    edges: list[LineageEdge] = []
    for node in nodes:
        for parent_id in node.parent_node_ids:
            edges.append(LineageEdge(from_node_id=parent_id, to_node_id=node.node_id, relation="caused"))
    return edges


def _unresolved_node(query: LineageQuery, *, trace_id: str, timestamp: str) -> LineageNode:
    return LineageNode(
        node_id=f"unresolved:{query.ref.ref_type}:{query.ref.ref_id}",
        node_type="unresolved_node",
        parent_node_ids=(),
        trace_id=trace_id,
        policy_version="unknown",
        model_version="unknown",
        tenant_id="unknown",
        budget_ref="unknown",
        proof_id="unresolved",
        state_hash="unresolved",
        timestamp=timestamp,
        unresolved=True,
        metadata={"reason": "trace_not_found"},
    )


def _verify_graph(nodes: tuple[LineageNode, ...], edges: tuple[LineageEdge, ...]) -> tuple[str, ...]:
    """Verify bounded lineage graph integrity."""
    if not nodes:
        return ("empty_lineage",)
    reason_codes: list[str] = []
    unresolved = [node.node_id for node in nodes if node.unresolved]
    if unresolved:
        reason_codes.append("unresolved_nodes")
    missing_tenant = [node.node_id for node in nodes if not node.tenant_id or node.tenant_id == "unknown"]
    if missing_tenant:
        reason_codes.append("tenant_context_missing")
    node_ids = {node.node_id for node in nodes}
    missing_edge_nodes = [
        edge
        for edge in edges
        if edge.from_node_id not in node_ids or edge.to_node_id not in node_ids
    ]
    if missing_edge_nodes:
        reason_codes.append("edge_endpoint_missing")
    declared_parent_edges = {
        (parent_id, node.node_id)
        for node in nodes
        for parent_id in node.parent_node_ids
    }
    actual_edges = {(edge.from_node_id, edge.to_node_id) for edge in edges}
    if declared_parent_edges != actual_edges:
        reason_codes.append("parent_edge_mismatch")
    return tuple(reason_codes)


def _policy_version_projection(nodes: tuple[LineageNode, ...]) -> list[PolicyVersionProjection]:
    policy_index: dict[str, dict[str, set[str]]] = {}
    for node in nodes:
        policy_version = node.policy_version or "unknown"
        entry = policy_index.setdefault(policy_version, {"node_ids": set(), "tenant_ids": set()})
        entry["node_ids"].add(node.node_id)
        if node.tenant_id:
            entry["tenant_ids"].add(node.tenant_id)
    return [
        PolicyVersionProjection(
            policy_version=policy_version,
            node_ids=tuple(sorted(entry["node_ids"])),
            tenant_ids=tuple(sorted(entry["tenant_ids"])),
        )
        for policy_version, entry in sorted(policy_index.items())
    ]


def _document(
    query: LineageQuery,
    *,
    nodes: tuple[LineageNode, ...],
    edges: tuple[LineageEdge, ...],
    verified: bool,
    reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    unresolved_nodes = [node.node_id for node in nodes if node.unresolved]
    document = {
        "schema_version": 1,
        "lineage_uri": query.uri,
        "root_ref": {"ref_type": query.ref.ref_type, "ref_id": query.ref.ref_id},
        "permalink": f"lineage://{query.ref.ref_type}/{query.ref.ref_id}",
        "depth": query.depth,
        "include": list(query.include),
        "verified": verified,
        "verification": {
            "reason_codes": list(reason_codes),
            "checked_nodes": len(nodes),
            "checked_edges": len(edges),
        },
        "policy_versions": [projection.to_dict() for projection in _policy_version_projection(nodes)],
        "nodes": [node.to_dict() for node in nodes],
        "edges": [edge.to_dict() for edge in edges],
        "unresolved_nodes": unresolved_nodes,
        "governed": True,
    }
    document_hash = _document_hash(document)
    return {
        **document,
        "document_id": f"lineage-doc:{document_hash[:16]}",
        "document_hash": f"sha256:{document_hash}",
    }


def _document_hash(document: dict[str, Any]) -> str:
    """Return a deterministic hash over the lineage document body."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
