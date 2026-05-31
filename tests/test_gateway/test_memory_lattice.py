"""Gateway memory lattice tests.

Purpose: verify governed memory admission by class, trust, freshness, and evidence.
Governance scope: raw, closure, semantic, policy, preference, contradiction, and schema admission.
Dependencies: gateway.memory_lattice and schemas/memory_lattice.schema.json.
Invariants:
  - Raw memory never enters planning directly.
  - Learning admission gates closure and semantic memory.
  - Policy memory requires authority evidence.
  - Contradictions and stale entries block execution.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from gateway.memory_lattice import (
    InMemoryMemoryLatticeStore,
    MemoryLatticeAdmission,
    MemoryLatticeEntry,
    MemoryLatticeGate,
    P3MemoryLatticeContract,
    P3MemoryTopologyEdge,
    P3MemoryTopologyMap,
    P3MemoryTopologyNode,
    build_p3_memory_lattice_contract,
    build_p3_memory_topology_map,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "memory_lattice.schema.json"
NOW = "2026-05-04T16:00:00Z"


def test_raw_event_memory_is_never_directly_admitted() -> None:
    admission = MemoryLatticeGate().assess(_entry("raw_event_memory", "observed"), now=NOW)

    assert admission.allowed_for_planning is False
    assert admission.allowed_for_execution is False
    assert admission.missing_requirements == []


def test_semantic_memory_requires_admitted_learning_decision() -> None:
    blocked = MemoryLatticeGate().assess(_entry("semantic_fact_memory", "trusted"), now=NOW)
    admitted = MemoryLatticeGate().assess(
        _entry("semantic_fact_memory", "trusted", learning_admission_status="admit"),
        now=NOW,
    )

    assert blocked.allowed_for_planning is False
    assert "learning_admission_decision" in blocked.missing_requirements
    assert admitted.allowed_for_planning is True
    assert admitted.allowed_for_execution is True


def test_policy_memory_requires_policy_authority_ref() -> None:
    blocked = MemoryLatticeGate().assess(_entry("policy_memory", "authority"), now=NOW)
    admitted = MemoryLatticeGate().assess(
        _entry("policy_memory", "authority", policy_authority_ref="policy-authority:root"),
        now=NOW,
    )

    assert blocked.allowed_for_execution is False
    assert "policy_authority_ref" in blocked.missing_requirements
    assert admitted.allowed_for_planning is True
    assert admitted.allowed_for_execution is True


def test_preference_memory_is_tenant_owner_scoped_and_not_execution_authority() -> None:
    blocked = MemoryLatticeGate().assess(_entry("preference_memory", "observed", tenant_id="tenant-a"), now=NOW)
    admitted = MemoryLatticeGate().assess(
        _entry("preference_memory", "observed", tenant_id="tenant-a", owner_id="user-1"),
        now=NOW,
    )

    assert "owner_id" in blocked.missing_requirements
    assert admitted.allowed_for_planning is True
    assert admitted.allowed_for_execution is False


def test_contradiction_and_stale_memory_block_execution() -> None:
    admission = MemoryLatticeGate().assess(
        _entry(
            "risk_memory",
            "trusted",
            valid_until="2026-05-04T15:59:00Z",
            contradicts=("claim:old-risk",),
        ),
        now=NOW,
    )

    assert admission.allowed_for_planning is False
    assert admission.allowed_for_execution is False
    assert "unresolved_contradiction" in admission.blocked_reasons
    assert "validity_window_expired" in admission.blocked_reasons


def test_memory_lattice_schema_exposes_admission_claim() -> None:
    admission = MemoryLatticeGate().assess(
        _entry("procedural_runbook_memory", "trusted", learning_admission_status="admit", certified_runbook_ref="runbook:cert-1"),
        now=NOW,
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(asdict(admission))
    assert schema["$id"] == "urn:mullusi:schema:memory-lattice:1"
    assert admission.allowed_for_execution is True
    assert admission.assessment_hash


def test_invalid_execution_without_planning_is_rejected() -> None:
    try:
        MemoryLatticeAdmission("mem-1", "risk_memory", "trusted", False, True, [], [], ["evidence:1"])
    except ValueError as exc:
        assert str(exc) == "execution_requires_planning_admission"
    else:
        raise AssertionError("invalid execution claim was accepted")


def test_memory_lattice_store_projects_admitted_planning_and_execution_memory() -> None:
    store = InMemoryMemoryLatticeStore()
    semantic = _entry(
        "semantic_fact_memory",
        "trusted",
        memory_id="memory:semantic:vendor-bank",
        tenant_id="tenant-a",
        learning_admission_status="admit",
    )
    preference = _entry(
        "preference_memory",
        "observed",
        memory_id="memory:preference:owner",
        tenant_id="tenant-a",
        owner_id="user-1",
    )

    store.admit(semantic, now=NOW)
    store.admit(preference, now=NOW)

    assert [entry.memory_id for entry in store.planning_projection(tenant_id="tenant-a")] == [
        "memory:preference:owner",
        "memory:semantic:vendor-bank",
    ]
    assert [entry.memory_id for entry in store.execution_projection(tenant_id="tenant-a")] == [
        "memory:semantic:vendor-bank"
    ]
    assert store.status(tenant_id="tenant-a").planning_count == 2
    assert store.status(tenant_id="tenant-a").execution_count == 1


def test_memory_lattice_store_tracks_supersession_and_contradiction_refs() -> None:
    store = InMemoryMemoryLatticeStore()
    old_entry = _entry("semantic_fact_memory", "trusted", memory_id="memory:bank:old", tenant_id="tenant-a")
    supersession = _entry(
        "supersession_memory",
        "trusted",
        memory_id="memory:bank:new",
        tenant_id="tenant-a",
        supersedes=("memory:bank:old",),
    )
    contradiction = _entry(
        "contradiction_memory",
        "observed",
        memory_id="memory:bank:contradiction",
        tenant_id="tenant-a",
        contradicts=("memory:bank:old",),
    )

    store.admit(old_entry, now=NOW)
    store.admit(supersession, now=NOW)
    store.admit(contradiction, now=NOW)

    assert store.superseded_by("memory:bank:old")[0].memory_id == "memory:bank:new"
    assert store.contradictions_for("memory:bank:old")[0].memory_id == "memory:bank:contradiction"
    assert store.status(tenant_id="tenant-a").supersession_count == 1
    assert store.status(tenant_id="tenant-a").contradiction_count == 1


def test_p3_memory_lattice_contract_binds_ready_chain_to_admitted_memory() -> None:
    admission = MemoryLatticeGate().assess(
        _entry("semantic_fact_memory", "trusted", learning_admission_status="admit"),
        now=NOW,
    )
    readiness = {
        "status": "ready",
        "plan_id": "plan-1",
        "mind_id": "root",
        "commit_witness_id": "witness-1",
        "reconciliation_report_id": "reconciliation-1",
    }

    contract = build_p3_memory_lattice_contract(
        readiness,
        (admission,),
        contract_id="p3-contract-1",
    )

    assert contract.status == "ready"
    assert contract.admitted_memory_ids == ("memory:semantic_fact_memory",)
    assert {"plan-1", "witness-1", "reconciliation-1"}.issubset(set(contract.evidence_refs))
    assert contract.contract_hash


def test_p3_memory_lattice_contract_blocks_without_ready_evidence_chain() -> None:
    contract = build_p3_memory_lattice_contract(
        {
            "status": "blocked",
            "blockers": ("verified_reconciliation_missing",),
            "mind_id": "root",
        },
        (),
        contract_id="p3-contract-blocked",
    )

    assert contract.status == "blocked"
    assert contract.admitted_memory_ids == ()
    assert contract.blocked_reasons == ("verified_reconciliation_missing",)
    assert contract.contract_hash


def test_p3_contract_builder_preserves_single_blocker_reason_token() -> None:
    contract = build_p3_memory_lattice_contract(
        {
            "status": "blocked",
            "blockers": "verified_reconciliation_missing",
            "mind_id": None,
        },
        (),
        contract_id="p3-contract-single-blocker",
    )

    assert contract.status == "blocked"
    assert contract.blocked_reasons == ("verified_reconciliation_missing",)
    assert contract.mind_id == ""
    assert contract.contract_hash


def test_p3_ready_contract_rejects_unbound_causal_refs() -> None:
    try:
        P3MemoryLatticeContract(
            contract_id="p3-contract-invalid",
            status="ready",
            mind_id="root",
            plan_id="plan-1",
            commit_witness_id="witness-1",
            reconciliation_report_id="reconciliation-1",
            admitted_memory_ids=("memory:semantic_fact_memory",),
            evidence_refs=("plan-1", "witness-1"),
        )
    except ValueError as exc:
        assert str(exc) == "ready_contract_missing_causal_evidence_ref"
    else:
        raise AssertionError("unbound P3 ready contract was accepted")


def test_p3_ready_contract_rejects_duplicate_memory_ids() -> None:
    try:
        P3MemoryLatticeContract(
            contract_id="p3-contract-duplicate",
            status="ready",
            mind_id="root",
            plan_id="plan-1",
            commit_witness_id="witness-1",
            reconciliation_report_id="reconciliation-1",
            admitted_memory_ids=("memory:semantic_fact_memory", "memory:semantic_fact_memory"),
            evidence_refs=("plan-1", "witness-1", "reconciliation-1"),
        )
    except ValueError as exc:
        assert str(exc) == "admitted_memory_ids_duplicate"
    else:
        raise AssertionError("duplicate P3 memory ids were accepted")


def test_p3_contract_builder_rejects_incomplete_ready_readiness() -> None:
    admission = MemoryLatticeGate().assess(
        _entry("semantic_fact_memory", "trusted", learning_admission_status="admit"),
        now=NOW,
    )

    try:
        build_p3_memory_lattice_contract(
            {"status": "ready", "plan_id": "plan-1", "mind_id": "root"},
            (admission,),
            contract_id="p3-contract-incomplete",
        )
    except ValueError as exc:
        assert str(exc) == "p3_readiness_commit_witness_id_required"
    else:
        raise AssertionError("incomplete P3 readiness was accepted")


def test_p3_contract_builder_rejects_non_text_ready_references() -> None:
    admission = MemoryLatticeGate().assess(
        _entry("semantic_fact_memory", "trusted", learning_admission_status="admit"),
        now=NOW,
    )
    invalid_cases = (
        (
            {
                "status": "ready",
                "plan_id": None,
                "mind_id": "root",
                "commit_witness_id": "witness-1",
                "reconciliation_report_id": "reconciliation-1",
            },
            "p3_readiness_plan_id_required",
        ),
        (
            {
                "status": "ready",
                "plan_id": "plan-1",
                "mind_id": "root",
                "commit_witness_id": "",
                "reconciliation_report_id": "reconciliation-1",
            },
            "p3_readiness_commit_witness_id_required",
        ),
    )
    errors: list[str] = []

    for readiness, expected_error in invalid_cases:
        try:
            build_p3_memory_lattice_contract(
                readiness,
                (admission,),
                contract_id=f"p3-contract-invalid-{len(errors)}",
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            raise AssertionError(f"{expected_error} was not raised")

    assert errors == ["p3_readiness_plan_id_required", "p3_readiness_commit_witness_id_required"]
    assert len(errors) == len(invalid_cases)
    assert admission.allowed_for_planning is True


def test_p3_contract_builder_rejects_invalid_blocker_shapes() -> None:
    invalid_cases = (
        ({"status": "blocked", "blockers": ("verified_reconciliation_missing", None)}, "p3_readiness_blocker_required"),
        ({"status": "blocked", "blockers": 42}, "p3_readiness_blockers_invalid"),
        ({"status": "blocked", "blockers": {"reason": "verified_reconciliation_missing"}}, "p3_readiness_blockers_invalid"),
        ({"status": "blocked", "blockers": {"verified_reconciliation_missing"}}, "p3_readiness_blockers_invalid"),
    )
    errors: list[str] = []

    for readiness, expected_error in invalid_cases:
        try:
            build_p3_memory_lattice_contract(readiness, (), contract_id=f"p3-contract-blocker-{len(errors)}")
        except ValueError as exc:
            errors.append(str(exc))
        else:
            raise AssertionError(f"{expected_error} was not raised")

    assert errors == [
        "p3_readiness_blocker_required",
        "p3_readiness_blockers_invalid",
        "p3_readiness_blockers_invalid",
        "p3_readiness_blockers_invalid",
    ]
    assert len(errors) == len(invalid_cases)
    assert all(error.startswith("p3_readiness_") for error in errors)


def test_p3_topology_map_binds_mind_memory_world_and_evidence_refs() -> None:
    entry = _entry(
        "semantic_fact_memory",
        "trusted",
        learning_admission_status="admit",
        metadata={"world_refs": ("world:runtime-target",)},
    )
    admission = MemoryLatticeGate().assess(entry, now=NOW)
    contract = build_p3_memory_lattice_contract(_ready_readiness(), (admission,), contract_id="p3-contract-1")

    topology = build_p3_memory_topology_map(contract, (entry,), topology_id="topology-1")
    node_ids = {node.node_id for node in topology.nodes}
    edge_kinds = {edge.edge_kind for edge in topology.edges}

    assert topology.status == "ready"
    assert "mind:root" in node_ids
    assert "memory:memory:semantic_fact_memory" in node_ids
    assert "world:world:runtime-target" in node_ids
    assert {"admits", "observes", "supported_by"}.issubset(edge_kinds)
    assert topology.topology_hash


def test_p3_topology_map_blocks_when_contract_is_not_ready() -> None:
    contract = build_p3_memory_lattice_contract(
        {"status": "blocked", "blockers": ("verified_reconciliation_missing",), "mind_id": "root"},
        (),
        contract_id="p3-contract-blocked",
    )

    topology = build_p3_memory_topology_map(contract, (), topology_id="topology-blocked")

    assert topology.status == "blocked"
    assert topology.nodes == ()
    assert topology.edges == ()
    assert topology.blocked_reasons == ("verified_reconciliation_missing",)
    assert topology.topology_hash


def test_p3_topology_map_blocks_missing_admitted_entry() -> None:
    entry = _entry("semantic_fact_memory", "trusted", learning_admission_status="admit")
    admission = MemoryLatticeGate().assess(entry, now=NOW)
    contract = build_p3_memory_lattice_contract(_ready_readiness(), (admission,), contract_id="p3-contract-1")

    topology = build_p3_memory_topology_map(contract, (), topology_id="topology-missing")

    assert topology.status == "blocked"
    assert topology.blocked_reasons == ("admitted_memory_entry_missing:memory:semantic_fact_memory",)
    assert topology.topology_hash


def test_p3_topology_map_rejects_dangling_edge_endpoint() -> None:
    try:
        P3MemoryTopologyMap(
            topology_id="topology-invalid",
            contract_id="p3-contract-1",
            status="ready",
            mind_id="root",
            nodes=(_topology_node("mind:root", "nested_mind", "root"),),
            edges=(
                P3MemoryTopologyEdge(
                    edge_id="edge-1",
                    from_node_id="mind:root",
                    to_node_id="missing-b",
                    edge_kind="admits",
                    evidence_refs=("evidence:1",),
                ),
            ),
        )
    except ValueError as exc:
        assert str(exc) == "topology_edge_endpoint_missing"
    else:
        raise AssertionError("topology with a dangling edge endpoint was accepted")


def test_p3_topology_map_rejects_duplicate_edge_ids() -> None:
    try:
        P3MemoryTopologyMap(
            topology_id="topology-duplicate-edge",
            contract_id="p3-contract-1",
            status="ready",
            mind_id="root",
            nodes=(
                _topology_node("mind:root", "nested_mind", "root"),
                _topology_node("memory:1", "memory", "memory:1"),
            ),
            edges=(
                P3MemoryTopologyEdge("edge-1", "mind:root", "memory:1", "admits", ("evidence:1",)),
                P3MemoryTopologyEdge("edge-1", "mind:root", "memory:1", "admits", ("evidence:2",)),
            ),
        )
    except ValueError as exc:
        assert str(exc) == "topology_edge_id_duplicate"
    else:
        raise AssertionError("duplicate topology edge ids were accepted")


def test_blocked_p3_topology_map_rejects_nodes_and_edges() -> None:
    try:
        P3MemoryTopologyMap(
            topology_id="topology-blocked-invalid",
            contract_id="p3-contract-1",
            status="blocked",
            mind_id="root",
            nodes=(_topology_node("mind:root", "nested_mind", "root"),),
            edges=(),
            blocked_reasons=("verified_reconciliation_missing",),
        )
    except ValueError as exc:
        assert str(exc) == "blocked_topology_cannot_have_nodes_or_edges"
    else:
        raise AssertionError("blocked topology with nodes was accepted")


def _entry(
    memory_class: str,
    trust_class: str,
    **overrides: object,
) -> MemoryLatticeEntry:
    payload = {
        "memory_id": f"memory:{memory_class}",
        "memory_class": memory_class,
        "source": "terminal_closure:case-1",
        "observed_at": "2026-05-04T15:00:00Z",
        "trust_class": trust_class,
        "evidence_refs": ("evidence:closure-1",),
    }
    payload.update(overrides)
    return MemoryLatticeEntry(**payload)


def _ready_readiness() -> dict[str, str]:
    return {
        "status": "ready",
        "plan_id": "plan-1",
        "mind_id": "root",
        "commit_witness_id": "witness-1",
        "reconciliation_report_id": "reconciliation-1",
    }


def _topology_node(node_id: str, node_kind: str, ref_id: str) -> P3MemoryTopologyNode:
    return P3MemoryTopologyNode(node_id=node_id, node_kind=node_kind, ref_id=ref_id)
