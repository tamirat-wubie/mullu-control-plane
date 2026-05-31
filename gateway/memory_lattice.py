"""Gateway memory lattice admission.

Purpose: classify memory records by governed use, trust, freshness, and evidence
instead of letting every remembered item enter planning or execution.
Governance scope: raw, episodic, semantic, procedural, policy, preference, risk,
contradiction, and supersession memory admission.
Dependencies: standard-library dataclasses, datetime, hashlib, and JSON serialization.
Invariants:
  - Raw event memory is never directly allowed for planning or execution.
  - Closure-derived memory requires admitted learning before planning use.
  - Execution memory requires evidence, freshness, and no unresolved contradiction.
  - Policy memory requires policy authority evidence.
  - Preference memory remains tenant and owner scoped.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping


MEMORY_CLASSES = (
    "raw_event_memory",
    "episodic_closure_memory",
    "semantic_fact_memory",
    "procedural_runbook_memory",
    "policy_memory",
    "preference_memory",
    "risk_memory",
    "contradiction_memory",
    "supersession_memory",
)
TRUST_CLASSES = ("untrusted", "observed", "admitted", "trusted", "authority", "revoked")
P3_LATTICE_CONTRACT_STATUSES = ("blocked", "ready")
P3_TOPOLOGY_NODE_KINDS = ("nested_mind", "memory", "world_ref", "evidence")
P3_TOPOLOGY_EDGE_KINDS = ("contains", "admits", "observes", "supported_by")
P3_TOPOLOGY_READ_MODEL_DEFAULT_LIMIT = 50
P3_TOPOLOGY_READ_MODEL_MAX_LIMIT = 250


@dataclass(frozen=True, slots=True)
class MemoryLatticeEntry:
    """Memory item whose planning and execution use must be admitted."""

    memory_id: str
    memory_class: str
    source: str
    observed_at: str
    trust_class: str
    evidence_refs: tuple[str, ...]
    valid_from: str = ""
    valid_until: str = ""
    requires_refresh: bool = False
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    learning_admission_status: str = ""
    policy_authority_ref: str = ""
    certified_runbook_ref: str = ""
    tenant_id: str = ""
    owner_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise ValueError("memory_id_required")
        if self.memory_class not in MEMORY_CLASSES:
            raise ValueError("memory_class_invalid")
        if not self.source:
            raise ValueError("source_required")
        if not self.observed_at:
            raise ValueError("observed_at_required")
        if self.trust_class not in TRUST_CLASSES:
            raise ValueError("trust_class_invalid")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "supersedes", tuple(self.supersedes))
        object.__setattr__(self, "contradicts", tuple(self.contradicts))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class MemoryLatticeAdmission:
    """Use decision for one memory lattice entry."""

    memory_id: str
    memory_class: str
    trust_class: str
    allowed_for_planning: bool
    allowed_for_execution: bool
    blocked_reasons: list[str]
    missing_requirements: list[str]
    evidence_refs: list[str]
    assessment_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocked_reasons", list(self.blocked_reasons))
        object.__setattr__(self, "missing_requirements", list(self.missing_requirements))
        object.__setattr__(self, "evidence_refs", list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.memory_class not in MEMORY_CLASSES:
            raise ValueError("memory_class_invalid")
        if self.trust_class not in TRUST_CLASSES:
            raise ValueError("trust_class_invalid")
        if self.allowed_for_execution and not self.allowed_for_planning:
            raise ValueError("execution_requires_planning_admission")
        if self.allowed_for_execution and self.blocked_reasons:
            raise ValueError("execution_cannot_have_blocked_reasons")


class MemoryLatticeGate:
    """Derive planning and execution admission from explicit memory evidence."""

    def assess(self, entry: MemoryLatticeEntry, *, now: str) -> MemoryLatticeAdmission:
        """Assess one memory entry against lattice rules."""
        blocked: list[str] = []
        missing: list[str] = []

        if not entry.evidence_refs:
            missing.append("evidence_refs")
        if entry.trust_class == "revoked":
            blocked.append("memory_revoked")
        if entry.requires_refresh:
            blocked.append("refresh_required")
        if entry.contradicts or entry.memory_class == "contradiction_memory":
            blocked.append("unresolved_contradiction")
        if _is_stale(entry.valid_until, now):
            blocked.append("validity_window_expired")

        planning_allowed, execution_allowed = _class_admission(entry, missing, blocked)
        if missing or blocked:
            execution_allowed = False
        if entry.memory_class == "raw_event_memory":
            planning_allowed = False
            execution_allowed = False

        return _stamp_admission(
            MemoryLatticeAdmission(
                memory_id=entry.memory_id,
                memory_class=entry.memory_class,
                trust_class=entry.trust_class,
                allowed_for_planning=planning_allowed,
                allowed_for_execution=execution_allowed,
                blocked_reasons=blocked,
                missing_requirements=missing,
                evidence_refs=list(entry.evidence_refs),
                metadata={
                    "source": entry.source,
                    "observed_at": entry.observed_at,
                    "valid_from": entry.valid_from,
                    "valid_until": entry.valid_until,
                    "supersedes": list(entry.supersedes),
                    "contradicts": list(entry.contradicts),
                    **entry.metadata,
                },
            )
        )


@dataclass(frozen=True, slots=True)
class MemoryLatticeAdmissionRecord:
    """Stored lattice entry with its latest admission claim."""

    entry: MemoryLatticeEntry
    admission: MemoryLatticeAdmission


@dataclass(frozen=True, slots=True)
class MemoryLatticeStoreStatus:
    """Summary of the in-memory lattice store."""

    tenant_id: str
    entry_count: int
    planning_count: int
    execution_count: int
    contradiction_count: int
    supersession_count: int
    store_hash: str = ""


@dataclass(frozen=True, slots=True)
class P3MemoryLatticeContract:
    """P3 topology claim bound to a verified nested-mind observation chain."""

    contract_id: str
    status: str
    mind_id: str
    plan_id: str
    commit_witness_id: str
    reconciliation_report_id: str
    admitted_memory_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    blocked_reasons: tuple[str, ...] = ()
    contract_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.contract_id:
            raise ValueError("contract_id_required")
        if self.status not in P3_LATTICE_CONTRACT_STATUSES:
            raise ValueError("p3_lattice_contract_status_invalid")
        object.__setattr__(self, "admitted_memory_ids", tuple(self.admitted_memory_ids))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "blocked_reasons", tuple(self.blocked_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))
        _reject_duplicate_refs(self.admitted_memory_ids, "admitted_memory_ids")
        _reject_duplicate_refs(self.evidence_refs, "evidence_refs")
        if self.status == "ready":
            _require_p3_ready_ref(self.mind_id, "mind_id")
            _require_p3_ready_ref(self.plan_id, "plan_id")
            _require_p3_ready_ref(self.commit_witness_id, "commit_witness_id")
            _require_p3_ready_ref(self.reconciliation_report_id, "reconciliation_report_id")
            if not self.admitted_memory_ids:
                raise ValueError("admitted_memory_ids_required")
            if not self.evidence_refs:
                raise ValueError("evidence_refs_required")
            if self.blocked_reasons:
                raise ValueError("ready_contract_cannot_have_blocked_reasons")
            required_refs = {
                self.plan_id,
                self.commit_witness_id,
                self.reconciliation_report_id,
            }
            if not required_refs.issubset(set(self.evidence_refs)):
                raise ValueError("ready_contract_missing_causal_evidence_ref")
        elif not self.blocked_reasons:
            raise ValueError("blocked_reasons_required")


@dataclass(frozen=True, slots=True)
class P3MemoryTopologyNode:
    """Read-only node in the P3 nested-mind memory topology."""

    node_id: str
    node_kind: str
    ref_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("topology_node_id_required")
        if self.node_kind not in P3_TOPOLOGY_NODE_KINDS:
            raise ValueError("topology_node_kind_invalid")
        if not self.ref_id:
            raise ValueError("topology_node_ref_id_required")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class P3MemoryTopologyEdge:
    """Read-only relation between two P3 topology nodes."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_kind: str
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.edge_id:
            raise ValueError("topology_edge_id_required")
        if not self.from_node_id:
            raise ValueError("topology_edge_from_node_id_required")
        if not self.to_node_id:
            raise ValueError("topology_edge_to_node_id_required")
        if self.from_node_id == self.to_node_id:
            raise ValueError("topology_edge_self_reference")
        if self.edge_kind not in P3_TOPOLOGY_EDGE_KINDS:
            raise ValueError("topology_edge_kind_invalid")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))
        _reject_duplicate_refs(self.evidence_refs, "topology_edge_evidence_refs")


@dataclass(frozen=True, slots=True)
class P3MemoryTopologyMap:
    """Read-only topology map derived from a ready P3 memory-lattice contract."""

    topology_id: str
    contract_id: str
    status: str
    mind_id: str
    nodes: tuple[P3MemoryTopologyNode, ...]
    edges: tuple[P3MemoryTopologyEdge, ...]
    blocked_reasons: tuple[str, ...] = ()
    topology_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.topology_id:
            raise ValueError("topology_id_required")
        if not self.contract_id:
            raise ValueError("topology_contract_id_required")
        if self.status not in P3_LATTICE_CONTRACT_STATUSES:
            raise ValueError("topology_status_invalid")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "blocked_reasons", tuple(self.blocked_reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.status == "ready":
            if not self.mind_id:
                raise ValueError("topology_mind_id_required")
            if self.blocked_reasons:
                raise ValueError("ready_topology_cannot_have_blocked_reasons")
            if not self.nodes:
                raise ValueError("ready_topology_nodes_required")
            if not self.edges:
                raise ValueError("ready_topology_edges_required")
            _validate_topology_graph(self.nodes, self.edges)
        else:
            if not self.blocked_reasons:
                raise ValueError("topology_blocked_reasons_required")
            if self.nodes or self.edges:
                raise ValueError("blocked_topology_cannot_have_nodes_or_edges")


class InMemoryMemoryLatticeStore:
    """Tenant-scoped memory lattice store with governed projections."""

    def __init__(self, *, gate: MemoryLatticeGate | None = None) -> None:
        self._gate = gate or MemoryLatticeGate()
        self._records: dict[str, MemoryLatticeAdmissionRecord] = {}

    def admit(self, entry: MemoryLatticeEntry, *, now: str) -> MemoryLatticeAdmission:
        """Assess and store one memory entry."""
        admission = self._gate.assess(entry, now=now)
        self._records[entry.memory_id] = MemoryLatticeAdmissionRecord(entry=entry, admission=admission)
        return admission

    def get(self, memory_id: str) -> MemoryLatticeAdmissionRecord | None:
        """Return one stored record by memory id."""
        return self._records.get(memory_id)

    def planning_projection(self, *, tenant_id: str) -> tuple[MemoryLatticeEntry, ...]:
        """Return memory entries currently admitted for planning."""
        return tuple(
            record.entry
            for record in sorted(self._records.values(), key=lambda item: item.entry.memory_id)
            if _record_tenant(record) == tenant_id and record.admission.allowed_for_planning
        )

    def execution_projection(self, *, tenant_id: str) -> tuple[MemoryLatticeEntry, ...]:
        """Return memory entries currently admitted for execution."""
        return tuple(
            record.entry
            for record in sorted(self._records.values(), key=lambda item: item.entry.memory_id)
            if _record_tenant(record) == tenant_id and record.admission.allowed_for_execution
        )

    def contradictions_for(self, memory_id: str) -> tuple[MemoryLatticeEntry, ...]:
        """Return contradiction entries that block or reference one memory id."""
        return tuple(
            record.entry
            for record in sorted(self._records.values(), key=lambda item: item.entry.memory_id)
            if memory_id in record.entry.contradicts or record.entry.memory_class == "contradiction_memory"
        )

    def superseded_by(self, memory_id: str) -> tuple[MemoryLatticeEntry, ...]:
        """Return entries that supersede the supplied memory id."""
        return tuple(
            record.entry
            for record in sorted(self._records.values(), key=lambda item: item.entry.memory_id)
            if memory_id in record.entry.supersedes
        )

    def status(self, *, tenant_id: str) -> MemoryLatticeStoreStatus:
        """Return tenant-scoped lattice counts."""
        records = [record for record in self._records.values() if _record_tenant(record) == tenant_id]
        status = MemoryLatticeStoreStatus(
            tenant_id=tenant_id,
            entry_count=len(records),
            planning_count=sum(record.admission.allowed_for_planning for record in records),
            execution_count=sum(record.admission.allowed_for_execution for record in records),
            contradiction_count=sum(record.entry.memory_class == "contradiction_memory" for record in records),
            supersession_count=sum(record.entry.memory_class == "supersession_memory" for record in records),
        )
        return _stamp_store_status(status)


def build_p3_memory_lattice_contract(
    readiness: Mapping[str, Any],
    admissions: tuple[MemoryLatticeAdmission, ...],
    *,
    contract_id: str,
) -> P3MemoryLatticeContract:
    """Build the P3 memory-lattice contract from readiness and admission claims."""
    if readiness.get("status") != "ready":
        blockers = _readiness_blockers(readiness)
        return _stamp_p3_contract(
            P3MemoryLatticeContract(
                contract_id=contract_id,
                status="blocked",
                mind_id=_readiness_optional_text(readiness, "mind_id"),
                plan_id=_readiness_optional_text(readiness, "plan_id"),
                commit_witness_id=_readiness_optional_text(readiness, "commit_witness_id"),
                reconciliation_report_id=_readiness_optional_text(readiness, "reconciliation_report_id"),
                admitted_memory_ids=(),
                evidence_refs=(),
                blocked_reasons=blockers,
            )
        )

    admitted_memory_ids = tuple(
        sorted(
            admission.memory_id
            for admission in admissions
            if admission.allowed_for_planning or admission.allowed_for_execution
        )
    )
    plan_id = _readiness_required_text(readiness, "plan_id")
    mind_id = _readiness_required_text(readiness, "mind_id")
    commit_witness_id = _readiness_required_text(readiness, "commit_witness_id")
    reconciliation_report_id = _readiness_required_text(readiness, "reconciliation_report_id")
    evidence_refs = tuple(
        sorted(
            {
                plan_id,
                commit_witness_id,
                reconciliation_report_id,
                *(
                    evidence_ref
                    for admission in admissions
                    for evidence_ref in admission.evidence_refs
                ),
            }
        )
    )
    return _stamp_p3_contract(
        P3MemoryLatticeContract(
            contract_id=contract_id,
            status="ready",
            mind_id=mind_id,
            plan_id=plan_id,
            commit_witness_id=commit_witness_id,
            reconciliation_report_id=reconciliation_report_id,
            admitted_memory_ids=admitted_memory_ids,
            evidence_refs=evidence_refs,
        )
    )


def build_p3_memory_topology_map(
    contract: P3MemoryLatticeContract,
    entries: tuple[MemoryLatticeEntry, ...],
    *,
    topology_id: str,
) -> P3MemoryTopologyMap:
    """Build a read-only topology map from a P3 contract and admitted entries."""
    if not isinstance(contract, P3MemoryLatticeContract):
        raise ValueError("contract_must_be_p3_memory_lattice_contract")
    if contract.status != "ready":
        return _stamp_p3_topology(
            P3MemoryTopologyMap(
                topology_id=topology_id,
                contract_id=contract.contract_id,
                status="blocked",
                mind_id=contract.mind_id,
                nodes=(),
                edges=(),
                blocked_reasons=contract.blocked_reasons or ("p3_contract_not_ready",),
            )
        )

    entry_by_id = {entry.memory_id: entry for entry in entries}
    missing = tuple(memory_id for memory_id in contract.admitted_memory_ids if memory_id not in entry_by_id)
    if missing:
        return _stamp_p3_topology(
            P3MemoryTopologyMap(
                topology_id=topology_id,
                contract_id=contract.contract_id,
                status="blocked",
                mind_id=contract.mind_id,
                nodes=(),
                edges=(),
                blocked_reasons=tuple(f"admitted_memory_entry_missing:{memory_id}" for memory_id in missing),
            )
        )

    nodes: list[P3MemoryTopologyNode] = [
        P3MemoryTopologyNode(
            node_id=f"mind:{contract.mind_id}",
            node_kind="nested_mind",
            ref_id=contract.mind_id,
            metadata={"contract_id": contract.contract_id},
        )
    ]
    edges: list[P3MemoryTopologyEdge] = []
    for memory_id in contract.admitted_memory_ids:
        entry = entry_by_id[memory_id]
        memory_node_id = f"memory:{memory_id}"
        nodes.append(
            P3MemoryTopologyNode(
                node_id=memory_node_id,
                node_kind="memory",
                ref_id=memory_id,
                metadata={"memory_class": entry.memory_class, "trust_class": entry.trust_class},
            )
        )
        edges.append(
            P3MemoryTopologyEdge(
                edge_id=f"edge:{contract.mind_id}:admits:{memory_id}",
                from_node_id=f"mind:{contract.mind_id}",
                to_node_id=memory_node_id,
                edge_kind="admits",
                evidence_refs=tuple(entry.evidence_refs),
            )
        )
        for world_ref in _entry_world_refs(entry):
            world_node_id = f"world:{world_ref}"
            nodes.append(P3MemoryTopologyNode(node_id=world_node_id, node_kind="world_ref", ref_id=world_ref))
            edges.append(
                P3MemoryTopologyEdge(
                    edge_id=f"edge:{memory_id}:observes:{world_ref}",
                    from_node_id=memory_node_id,
                    to_node_id=world_node_id,
                    edge_kind="observes",
                    evidence_refs=tuple(entry.evidence_refs),
                )
            )
    for evidence_ref in contract.evidence_refs:
        evidence_node_id = f"evidence:{evidence_ref}"
        nodes.append(P3MemoryTopologyNode(node_id=evidence_node_id, node_kind="evidence", ref_id=evidence_ref))
        edges.append(
            P3MemoryTopologyEdge(
                edge_id=f"edge:{contract.contract_id}:supported_by:{evidence_ref}",
                from_node_id=f"mind:{contract.mind_id}",
                to_node_id=evidence_node_id,
                edge_kind="supported_by",
                evidence_refs=(evidence_ref,),
            )
        )

    return _stamp_p3_topology(
        P3MemoryTopologyMap(
            topology_id=topology_id,
            contract_id=contract.contract_id,
            status="ready",
            mind_id=contract.mind_id,
            nodes=_dedupe_nodes(nodes),
            edges=tuple(edges),
        )
    )


def build_p3_memory_topology_read_model(
    topology: P3MemoryTopologyMap,
    *,
    node_limit: int = P3_TOPOLOGY_READ_MODEL_DEFAULT_LIMIT,
    edge_limit: int = P3_TOPOLOGY_READ_MODEL_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Build a bounded operator read model for a P3 memory topology map."""
    if not isinstance(topology, P3MemoryTopologyMap):
        raise ValueError("topology_must_be_p3_memory_topology_map")

    bounded_node_limit = _read_model_limit(node_limit, "node_limit")
    bounded_edge_limit = _read_model_limit(edge_limit, "edge_limit")
    sorted_nodes = tuple(sorted(topology.nodes, key=lambda node: node.node_id))
    sorted_edges = tuple(sorted(topology.edges, key=lambda edge: edge.edge_id))
    nodes = sorted_nodes[:bounded_node_limit]
    edges = sorted_edges[:bounded_edge_limit]

    return {
        "surface": "p3_memory_topology",
        "read_model_only": True,
        "operator_projection": True,
        "raw_topology_metadata_exposed": False,
        "raw_memory_metadata_exposed": False,
        "live_write_enabled": False,
        "execution_authority_granted": False,
        "topology_id": topology.topology_id,
        "contract_id": topology.contract_id,
        "status": topology.status,
        "mind_id": topology.mind_id,
        "topology_hash": topology.topology_hash,
        "blocked_reasons": list(topology.blocked_reasons),
        "node_count": len(sorted_nodes),
        "edge_count": len(sorted_edges),
        "node_kind_counts": _topology_node_kind_counts(sorted_nodes),
        "edge_kind_counts": _topology_edge_kind_counts(sorted_edges),
        "node_page": {
            "limit": bounded_node_limit,
            "returned": len(nodes),
            "omitted": len(sorted_nodes) - len(nodes),
        },
        "edge_page": {
            "limit": bounded_edge_limit,
            "returned": len(edges),
            "omitted": len(sorted_edges) - len(edges),
        },
        "nodes": [
            {
                "node_id": node.node_id,
                "node_kind": node.node_kind,
                "ref_id": node.ref_id,
            }
            for node in nodes
        ],
        "edges": [
            {
                "edge_id": edge.edge_id,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "edge_kind": edge.edge_kind,
                "evidence_refs": list(edge.evidence_refs),
            }
            for edge in edges
        ],
    }


def _class_admission(
    entry: MemoryLatticeEntry,
    missing: list[str],
    blocked: list[str],
) -> tuple[bool, bool]:
    evidence_ready = not missing and not blocked
    if entry.memory_class == "episodic_closure_memory":
        _require_learning_admission(entry, missing)
        return entry.learning_admission_status == "admit" and not blocked, False
    if entry.memory_class == "semantic_fact_memory":
        _require_learning_admission(entry, missing)
        admitted = entry.learning_admission_status == "admit" and entry.trust_class in {"admitted", "trusted"}
        return admitted and not blocked, admitted and evidence_ready
    if entry.memory_class == "procedural_runbook_memory":
        _require_learning_admission(entry, missing)
        if not entry.certified_runbook_ref:
            missing.append("certified_runbook_ref")
        admitted = entry.learning_admission_status == "admit" and bool(entry.certified_runbook_ref)
        return admitted and not blocked, admitted and evidence_ready
    if entry.memory_class == "policy_memory":
        if not entry.policy_authority_ref:
            missing.append("policy_authority_ref")
        admitted = entry.trust_class == "authority" and bool(entry.policy_authority_ref)
        return admitted and not blocked, admitted and evidence_ready
    if entry.memory_class == "preference_memory":
        if not entry.tenant_id:
            missing.append("tenant_id")
        if not entry.owner_id:
            missing.append("owner_id")
        admitted = entry.trust_class in {"observed", "admitted", "trusted"} and entry.tenant_id and entry.owner_id
        return bool(admitted and not blocked), False
    if entry.memory_class in {"risk_memory", "supersession_memory"}:
        admitted = entry.trust_class in {"observed", "admitted", "trusted", "authority"}
        return admitted and not blocked, admitted and evidence_ready
    if entry.memory_class == "contradiction_memory":
        return False, False
    return False, False


def _require_learning_admission(entry: MemoryLatticeEntry, missing: list[str]) -> None:
    if entry.learning_admission_status != "admit":
        missing.append("learning_admission_decision")


def _is_stale(valid_until: str, now: str) -> bool:
    if not valid_until:
        return False
    return _parse_time(valid_until) < _parse_time(now)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _stamp_admission(admission: MemoryLatticeAdmission) -> MemoryLatticeAdmission:
    payload = asdict(replace(admission, assessment_hash=""))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return replace(admission, assessment_hash=hashlib.sha256(encoded).hexdigest())


def _record_tenant(record: MemoryLatticeAdmissionRecord) -> str:
    return record.entry.tenant_id or str(record.entry.metadata.get("tenant_id", ""))


def _stamp_store_status(status: MemoryLatticeStoreStatus) -> MemoryLatticeStoreStatus:
    payload = asdict(replace(status, store_hash=""))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return replace(status, store_hash=hashlib.sha256(encoded).hexdigest())


def _stamp_p3_contract(contract: P3MemoryLatticeContract) -> P3MemoryLatticeContract:
    payload = asdict(replace(contract, contract_hash=""))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return replace(contract, contract_hash=hashlib.sha256(encoded).hexdigest())


def _stamp_p3_topology(topology: P3MemoryTopologyMap) -> P3MemoryTopologyMap:
    payload = asdict(replace(topology, topology_hash=""))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return replace(topology, topology_hash=hashlib.sha256(encoded).hexdigest())


def _require_p3_ready_ref(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name}_required")


def _readiness_required_text(readiness: Mapping[str, Any], field_name: str) -> str:
    value = readiness.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"p3_readiness_{field_name}_required")
    text = value.strip()
    if not text:
        raise ValueError(f"p3_readiness_{field_name}_required")
    return text


def _readiness_optional_text(readiness: Mapping[str, Any], field_name: str) -> str:
    value = readiness.get(field_name, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"p3_readiness_{field_name}_invalid")
    return value.strip()


def _readiness_blockers(readiness: Mapping[str, Any]) -> tuple[str, ...]:
    raw_blockers = readiness.get("blockers", ())
    if raw_blockers is None:
        return ("p3_readiness_not_ready",)
    if isinstance(raw_blockers, str):
        blocker = raw_blockers.strip()
        return (blocker,) if blocker else ("p3_readiness_not_ready",)
    if not isinstance(raw_blockers, (list, tuple)):
        raise ValueError("p3_readiness_blockers_invalid")
    blockers = tuple(raw_blockers)
    normalized = tuple(_readiness_blocker_text(blocker) for blocker in blockers)
    return normalized or ("p3_readiness_not_ready",)


def _readiness_blocker_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("p3_readiness_blocker_required")
    text = value.strip()
    if not text:
        raise ValueError("p3_readiness_blocker_required")
    return text


def _reject_duplicate_refs(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name}_duplicate")
    if any(not value for value in values):
        raise ValueError(f"{field_name}_empty")


def _entry_world_refs(entry: MemoryLatticeEntry) -> tuple[str, ...]:
    raw_refs = entry.metadata.get("world_refs", ())
    if "world_ref" in entry.metadata:
        single_ref = _world_ref_text(entry.metadata["world_ref"], "world_ref")
        if isinstance(raw_refs, str):
            raw_refs = (_world_ref_text(raw_refs, "world_refs[0]"), single_ref)
        elif isinstance(raw_refs, (list, tuple)):
            raw_refs = (*_world_ref_tuple(raw_refs), single_ref)
        else:
            raise ValueError("world_refs_must_be_array")
    if isinstance(raw_refs, str):
        refs = (_world_ref_text(raw_refs, "world_refs[0]"),)
    elif isinstance(raw_refs, (list, tuple)):
        refs = _world_ref_tuple(raw_refs)
    else:
        raise ValueError("world_refs_must_be_array")
    _reject_duplicate_refs(refs, "world_refs")
    return refs


def _world_ref_tuple(values: tuple[Any, ...] | list[Any]) -> tuple[str, ...]:
    return tuple(_world_ref_text(value, f"world_refs[{index}]") for index, value in enumerate(values))


def _world_ref_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}_must_be_non_empty_text")
    if value.strip() != value:
        raise ValueError(f"{field_name}_must_be_trimmed_text")
    return value


def _dedupe_nodes(nodes: list[P3MemoryTopologyNode]) -> tuple[P3MemoryTopologyNode, ...]:
    deduped: dict[str, P3MemoryTopologyNode] = {}
    for node in nodes:
        existing = deduped.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError("topology_node_id_conflict")
        deduped[node.node_id] = node
    return tuple(deduped[node_id] for node_id in sorted(deduped))


def _validate_topology_graph(
    nodes: tuple[P3MemoryTopologyNode, ...],
    edges: tuple[P3MemoryTopologyEdge, ...],
) -> None:
    node_ids = [node.node_id for node in nodes]
    edge_ids = [edge.edge_id for edge in edges]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("topology_node_id_duplicate")
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("topology_edge_id_duplicate")
    node_id_set = set(node_ids)
    for edge in edges:
        if edge.from_node_id not in node_id_set or edge.to_node_id not in node_id_set:
            raise ValueError("topology_edge_endpoint_missing")


def _read_model_limit(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name}_must_be_integer")
    if value < 0:
        raise ValueError(f"{field_name}_must_be_non_negative")
    return min(value, P3_TOPOLOGY_READ_MODEL_MAX_LIMIT)


def _topology_node_kind_counts(nodes: tuple[P3MemoryTopologyNode, ...]) -> dict[str, int]:
    return {
        node_kind: sum(node.node_kind == node_kind for node in nodes)
        for node_kind in P3_TOPOLOGY_NODE_KINDS
        if any(node.node_kind == node_kind for node in nodes)
    }


def _topology_edge_kind_counts(edges: tuple[P3MemoryTopologyEdge, ...]) -> dict[str, int]:
    return {
        edge_kind: sum(edge.edge_kind == edge_kind for edge in edges)
        for edge_kind in P3_TOPOLOGY_EDGE_KINDS
        if any(edge.edge_kind == edge_kind for edge in edges)
    }
