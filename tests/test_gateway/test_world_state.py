"""Gateway world-state graph tests.

Purpose: verify governed admission, append-only history, relation integrity,
    contradiction blocking, and public schema compatibility.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.world_state and schemas/world_state.schema.json.
Invariants:
  - No assertion is admitted without evidence.
  - Relations require admitted same-tenant entities.
  - Contradicted claims are blocked from planning and execution.
  - Materialized world state validates against the public schema shape.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gateway.world_state import (
    Contradiction,
    EvidenceRef,
    InMemoryWorldStateStore,
    ValidityWindow,
    WorldClaim,
    WorldEntity,
    WorldEvent,
    WorldRelation,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "world_state.schema.json"
NOW = "2026-05-04T12:00:00Z"


def test_world_state_store_admits_entity_and_materializes_projection() -> None:
    store = InMemoryWorldStateStore(clock=lambda: NOW)

    admission = store.add_entity(_entity(entity_id="vendor-a"))
    state = store.materialize(tenant_id="tenant-1")
    history = store.history(tenant_id="tenant-1")

    assert admission.accepted is True
    assert admission.object_id == "vendor-a"
    assert admission.object_hash
    assert state.entity_count == 1
    assert state.state_id.startswith("world-state-")
    assert len(history) == 1
    assert history[0]["object_type"] == "entity"


def test_world_state_store_rejects_unsourced_assertion() -> None:
    store = InMemoryWorldStateStore(clock=lambda: NOW)

    admission = store.add_entity(_entity(entity_id="vendor-a", source=""))
    state = store.materialize(tenant_id="tenant-1")
    history = store.history()

    assert admission.accepted is False
    assert admission.reason == "source_required"
    assert admission.object_id == "vendor-a"
    assert state.entity_count == 0
    assert state.open_contradiction_count == 0
    assert history == ()


def test_world_state_relation_requires_admitted_same_tenant_entities() -> None:
    store = InMemoryWorldStateStore(clock=lambda: NOW)
    store.add_entity(_entity(entity_id="vendor-a"))

    missing = store.add_relation(_relation(relation_id="rel-1", target_entity_id="invoice-9"))
    store.add_entity(_entity(entity_id="invoice-9", entity_type="invoice"))
    admitted = store.add_relation(_relation(relation_id="rel-1", target_entity_id="invoice-9"))

    assert missing.accepted is False
    assert missing.reason == "relation_entities_required"
    assert admitted.accepted is True
    assert admitted.object_id == "rel-1"
    assert store.materialize(tenant_id="tenant-1").relation_count == 1
    assert len(store.history(tenant_id="tenant-1")) == 3


def test_world_state_contradiction_blocks_planning_and_execution_claims() -> None:
    store = InMemoryWorldStateStore(clock=lambda: NOW)
    store.add_entity(_entity(entity_id="vendor-a"))
    store.add_claim(_claim(claim_id="claim-bank-x", object_value="bank-x", allowed_for_execution=True))
    store.add_claim(_claim(claim_id="claim-bank-y", object_value="bank-y", allowed_for_execution=True))

    contradiction = store.add_contradiction(
        _contradiction(refs=("claim-bank-x", "claim-bank-y"))
    )
    state = store.materialize(tenant_id="tenant-1")
    planning_claims = store.planning_claims(tenant_id="tenant-1")
    execution_claims = store.execution_claims(tenant_id="tenant-1")

    assert contradiction.accepted is True
    assert state.claim_count == 2
    assert state.contradiction_count == 1
    assert state.open_contradiction_count == 1
    assert planning_claims == ()
    assert execution_claims == ()


def test_world_state_event_requires_resolved_references() -> None:
    store = InMemoryWorldStateStore(clock=lambda: NOW)

    denied = store.add_event(_event(event_id="evt-1", entity_refs=("vendor-a",)))
    store.add_entity(_entity(entity_id="vendor-a"))
    admitted = store.add_event(_event(event_id="evt-1", entity_refs=("vendor-a",)))
    state = store.materialize(tenant_id="tenant-1")

    assert denied.accepted is False
    assert denied.reason == "event_refs_required"
    assert admitted.accepted is True
    assert admitted.object_hash
    assert state.event_count == 1
    assert len(store.history(tenant_id="tenant-1")) == 2


def test_world_state_schema_accepts_canonical_projection() -> None:
    schema = _load_schema(SCHEMA_PATH)
    projection = _schema_projection()

    errors = _validate_schema_instance(schema, projection)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:world-state:1"
    assert projection["entities"][0]["evidence_refs"][0]["evidence_id"] == "evidence-1"
    assert projection["claims"][0]["allowed_for_planning"] is True
    assert projection["contradictions"] == []
    assert projection["state_hash"] == "state-hash-1"


def test_world_state_schema_rejects_entity_without_evidence() -> None:
    schema = _load_schema(SCHEMA_PATH)
    projection = _schema_projection()
    projection["entities"][0]["evidence_refs"] = []

    errors = _validate_schema_instance(schema, projection)

    assert len(errors) == 1
    assert "$.entities[0].evidence_refs" in errors[0]
    assert "at least 1 item" in errors[0]
    assert projection["tenant_id"] == "tenant-1"
    assert projection["entities"][0]["entity_id"] == "vendor-a"
    assert projection["relations"] == []


def _evidence() -> EvidenceRef:
    return EvidenceRef(
        evidence_id="evidence-1",
        evidence_type="document",
        source="invoice_pdf",
        observed_at=NOW,
        content_hash="sha256:evidence",
    )


def _validity() -> ValidityWindow:
    return ValidityWindow(valid_from=NOW, valid_until="", requires_refresh=False)


def _entity(**overrides: Any) -> WorldEntity:
    payload = {
        "entity_id": "vendor-a",
        "tenant_id": "tenant-1",
        "entity_type": "vendor",
        "display_name": "Vendor A",
        "evidence_refs": (_evidence(),),
        "source": "invoice_pdf",
        "observed_at": NOW,
        "validity": _validity(),
        "attributes": {"country": "US"},
        "trust_class": "observed",
        "allowed_for_planning": True,
        "allowed_for_execution": False,
    }
    payload.update(overrides)
    return WorldEntity(**payload)


def _relation(**overrides: Any) -> WorldRelation:
    payload = {
        "relation_id": "rel-1",
        "tenant_id": "tenant-1",
        "relation_type": "has_invoice",
        "source_entity_id": "vendor-a",
        "target_entity_id": "invoice-9",
        "evidence_refs": (_evidence(),),
        "source": "invoice_pdf",
        "observed_at": NOW,
        "validity": _validity(),
        "attributes": {"amount": "850.00"},
        "trust_class": "observed",
        "allowed_for_planning": True,
        "allowed_for_execution": False,
    }
    payload.update(overrides)
    return WorldRelation(**payload)


def _event(**overrides: Any) -> WorldEvent:
    payload = {
        "event_id": "evt-1",
        "tenant_id": "tenant-1",
        "event_type": "invoice_observed",
        "occurred_at": NOW,
        "evidence_refs": (_evidence(),),
        "source": "invoice_pdf",
        "entity_refs": (),
        "attributes": {"amount": "850.00"},
    }
    payload.update(overrides)
    return WorldEvent(**payload)


def _claim(**overrides: Any) -> WorldClaim:
    payload = {
        "claim_id": "claim-bank-x",
        "tenant_id": "tenant-1",
        "subject_ref": "vendor-a",
        "predicate": "bank_account",
        "object_value": "bank-x",
        "evidence_refs": (_evidence(),),
        "source": "invoice_pdf",
        "observed_at": NOW,
        "validity": _validity(),
        "confidence": 0.9,
        "trust_class": "source_claim",
        "freshness_window_days": 30,
        "domain_risk": "high",
        "allowed_for_planning": True,
        "allowed_for_execution": False,
    }
    payload.update(overrides)
    return WorldClaim(**payload)


def _contradiction(**overrides: Any) -> Contradiction:
    payload = {
        "contradiction_id": "contradiction-1",
        "tenant_id": "tenant-1",
        "refs": ("claim-bank-x", "claim-bank-y"),
        "reason": "Vendor bank account changed before payment.",
        "evidence_refs": (_evidence(),),
        "source": "invoice_review",
        "observed_at": NOW,
        "severity": "high",
        "status": "open",
    }
    payload.update(overrides)
    return Contradiction(**payload)


def _schema_projection() -> dict[str, Any]:
    entity = _json_object(asdict(_entity(created_at=NOW, state_hash="entity-hash-1")))
    claim = _json_object(asdict(_claim(created_at=NOW, claim_hash="claim-hash-1")))
    event = _json_object(
        asdict(_event(created_at=NOW, event_hash="event-hash-1", entity_refs=("vendor-a",)))
    )
    return {
        "tenant_id": "tenant-1",
        "state_id": "world-state-1",
        "entities": [entity],
        "relations": [],
        "events": [event],
        "claims": [claim],
        "contradictions": [],
        "projected_at": NOW,
        "state_hash": "state-hash-1",
    }


def _json_object(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))
