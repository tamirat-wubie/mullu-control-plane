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
