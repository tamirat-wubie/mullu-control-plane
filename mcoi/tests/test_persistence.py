"""Persistence — JSON snapshots per tenant, full round-trip across all 25 constructs."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.cognition import router as cognition_router
from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_tenants import router as musia_tenants_router
from mcoi_runtime.substrate.cascade import DependencyGraph
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    Composition,
    Conservation,
    Constraint,
    Coupling,
    Decision,
    Emergence,
    Equilibrium,
    Evolution,
    Execution,
    Inference,
    Integrity,
    Interaction,
    Learning,
    MfidelSignature,
    Observation,
    Pattern,
    Resonance,
    Source,
    State,
    Synchronization,
    Binding,
    Transformation,
    Validation,
)
from mcoi_runtime.substrate.persistence import (
    FileBackedPersistence,
    construct_to_dict,
    dict_to_construct,
    restore_graph,
    snapshot_graph,
)
from mcoi_runtime.substrate.registry_store import (
    STORE,
    configure_persistence,
)


# ---- Fixtures ----


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path / "musia-snapshots"


@pytest.fixture
def backend(tmp_dir: Path) -> FileBackedPersistence:
    return FileBackedPersistence(tmp_dir)


@pytest.fixture
def populated_graph() -> DependencyGraph:
    """Build a graph with one construct from every tier."""
    g = DependencyGraph()

    # Tier 1
    s1 = State(configuration={"x": 1})
    s2 = State(configuration={"x": 2})
    chg = Change(
        state_before_id=s1.id,
        state_after_id=s2.id,
        delta_vector={"d": 1},
    )
    cause = Causation(
        cause_id=s1.id,
        effect_id=chg.id,
        mechanism="ambient_cooling",
        strength=0.85,
    )
    constr = Constraint(domain="thermo", restriction="temp <= 0")
    bnd = Boundary(
        inside_predicate="contained",
        interface_points=("wall", "lid"),
        permeability="closed",
    )

    # Tier 2
    p = Pattern(
        template_state_id=s2.id,
        instance_state_ids=(s2.id,),
        similarity_threshold=0.9,
        variation_tolerance=("color",),
    )
    t = Transformation(
        initial_state_id=s1.id,
        target_state_id=s2.id,
        change_id=chg.id,
        causation_id=cause.id,
        boundary_id=bnd.id,
        energy_estimate=10.5,
        reversibility="reversible",
    )

    for c in (s1, s2, chg, cause, constr, bnd, p, t):
        g.constructs[c.id] = c

    # Edges
    g.dependents[s1.id] = {chg.id, cause.id, t.id}
    g.dependents[s2.id] = {chg.id, p.id, t.id}
    g.dependents[chg.id] = {cause.id, t.id}

    return g


# ---- Construct serialization round-trip ----


def test_state_round_trip():
    s = State(configuration={"x": 1, "phase": "liquid"})
    d = construct_to_dict(s)
    restored = dict_to_construct(d)
    assert isinstance(restored, State)
    assert restored.id == s.id
    assert restored.configuration == s.configuration
    assert restored.tier == s.tier
    assert restored.invariants == s.invariants


def test_causation_round_trip_preserves_uuid_refs():
    cause_id = uuid4()
    effect_id = uuid4()
    c = Causation(
        cause_id=cause_id,
        effect_id=effect_id,
        mechanism="m",
        strength=0.7,
    )
    d = construct_to_dict(c)
    # Verify the serialized form uses string UUIDs (JSON-friendly)
    assert isinstance(d["cause_id"], str)
    assert isinstance(d["effect_id"], str)
    restored = dict_to_construct(d)
    assert restored.cause_id == cause_id
    assert restored.effect_id == effect_id
    assert restored.strength == 0.7


def test_transformation_round_trip_with_5_uuid_refs():
    t = Transformation(
        initial_state_id=uuid4(),
        target_state_id=uuid4(),
        change_id=uuid4(),
        causation_id=uuid4(),
        boundary_id=uuid4(),
        energy_estimate=42.0,
        reversibility="irreversible",
    )
    d = construct_to_dict(t)
    restored = dict_to_construct(d)
    for attr in (
        "initial_state_id", "target_state_id", "change_id",
        "causation_id", "boundary_id",
    ):
        assert getattr(restored, attr) == getattr(t, attr)
    assert restored.reversibility == "irreversible"


def test_pattern_round_trip_with_uuid_tuple():
    instances = (uuid4(), uuid4(), uuid4())
    p = Pattern(
        template_state_id=uuid4(),
        instance_state_ids=instances,
        similarity_threshold=0.5,
        variation_tolerance=("hue", "saturation"),
    )
    d = construct_to_dict(p)
    restored = dict_to_construct(d)
    assert restored.instance_state_ids == instances
    assert restored.variation_tolerance == ("hue", "saturation")


def test_interaction_round_trip_with_distinct_participants():
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    inter = Interaction(
        participant_state_ids=(p1, p2, p3),
        causation_ids=(c1, c2, c3),
        coupling_strength=0.8,
        feedback_kind="negative",
    )
    d = construct_to_dict(inter)
    restored = dict_to_construct(d)
    assert restored.participant_state_ids == (p1, p2, p3)
    assert restored.feedback_kind == "negative"


def test_validation_round_trip_with_string_tuples():
    v = Validation(
        target_pattern_id=uuid4(),
        criteria=("c1", "c2"),
        evidence_refs=("e1",),
        confidence=0.9,
        decision="pass",
    )
    d = construct_to_dict(v)
    restored = dict_to_construct(d)
    assert restored.criteria == ("c1", "c2")
    assert restored.evidence_refs == ("e1",)
    assert restored.decision == "pass"


def test_construct_with_mfidel_signature_round_trip():
    sig = MfidelSignature(coords=((1, 1), (17, 8)))
    s = State(configuration={"a": 1}, mfidel_signature=sig)
    d = construct_to_dict(s)
    restored = dict_to_construct(d)
    assert restored.mfidel_signature is not None
    assert restored.mfidel_signature.coords == ((1, 1), (17, 8))


@pytest.mark.parametrize("ctor,kwargs", [
    (State, {"configuration": {}}),
    (Constraint, {"domain": "x", "restriction": "y"}),
    (Boundary, {"inside_predicate": "scope"}),
    (Pattern, {"template_state_id": uuid4()}),
    (Coupling, {"source_id": uuid4(), "target_id": uuid4()}),
    (Synchronization, {"pattern_ids": (uuid4(), uuid4()), "frequency": 1.0}),
    (Resonance, {"pattern_id": uuid4()}),
    (Equilibrium, {"attractor_state_ids": (uuid4(),)}),
    (
        Source,
        {
            "origin_identifier": "x",
            "scope_description": "y",
            "legitimacy_basis": "z",
        },
    ),
    (
        Binding,
        {
            "agent_identifier": "a",
            "action_description": "b",
            "consequence_change_id": uuid4(),
        },
    ),
    (
        Validation,
        {
            "target_pattern_id": uuid4(),
            "criteria": ("c",),
        },
    ),
])
def test_all_construct_types_round_trip(ctor, kwargs):
    """Every construct type must survive a round-trip with no information loss."""
    c = ctor(**kwargs)
    d = construct_to_dict(c)
    restored = dict_to_construct(d)
    assert type(restored) is type(c)
    assert restored.id == c.id
    assert restored.tier == c.tier
    assert restored.type == c.type


# ---- Graph snapshot/restore ----


def test_snapshot_graph_contains_schema_and_tenant(populated_graph):
    snap = snapshot_graph("acme-corp", populated_graph)
    assert snap["schema_version"] == "1"
    assert snap["tenant_id"] == "acme-corp"
    assert len(snap["constructs"]) == 8
    assert snap["dependents"]  # non-empty


def test_snapshot_round_trip_preserves_constructs(populated_graph):
    snap = snapshot_graph("acme-corp", populated_graph)
    g2 = restore_graph(snap)
    assert len(g2.constructs) == len(populated_graph.constructs)
    for cid, c in populated_graph.constructs.items():
        assert cid in g2.constructs
        assert g2.constructs[cid].type == c.type


def test_snapshot_round_trip_preserves_dependents(populated_graph):
    snap = snapshot_graph("acme-corp", populated_graph)
    g2 = restore_graph(snap)
    for src, deps in populated_graph.dependents.items():
        assert g2.dependents.get(src) == deps


def test_restore_unsupported_schema_rejected():
    payload = {
        "schema_version": "999",
        "tenant_id": "x",
        "constructs": [],
        "dependents": {},
    }
    with pytest.raises(ValueError, match="schema_version"):
        restore_graph(payload)


# ---- File backend ----


def test_file_backend_save_creates_atomic_file(backend, populated_graph, tmp_dir):
    path = backend.save("acme-corp", populated_graph)
    assert path.exists()
    assert path.parent == tmp_dir
    # File is valid JSON
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["tenant_id"] == "acme-corp"


def test_file_backend_round_trip(backend, populated_graph):
    backend.save("acme-corp", populated_graph)
    restored = backend.load("acme-corp")
    assert restored is not None
    assert len(restored.constructs) == len(populated_graph.constructs)


def test_file_backend_load_missing_returns_none(backend):
    assert backend.load("never-saved") is None


def test_file_backend_list_tenants(backend, populated_graph):
    backend.save("acme-corp", populated_graph)
    backend.save("foo-llc", populated_graph)
    tenants = backend.list_tenants()
    assert "acme-corp" in tenants
    assert "foo-llc" in tenants


def test_file_backend_delete(backend, populated_graph):
    backend.save("acme-corp", populated_graph)
    assert backend.delete("acme-corp") is True
    assert backend.delete("acme-corp") is False
    assert backend.load("acme-corp") is None


def test_file_backend_rejects_empty_tenant_id(backend):
    with pytest.raises(ValueError):
        backend.path_for("")


# ---- Store integration ----


def test_configure_persistence_attaches_backend(tmp_dir):
    configure_persistence(str(tmp_dir))
    assert STORE.persistence is not None
    configure_persistence(None)
    assert STORE.persistence is None


def test_store_snapshot_then_load_round_trip(tmp_dir):
    configure_persistence(str(tmp_dir))
    try:
        STORE.reset_all()
        state = STORE.get_or_create("acme-corp")
        s = State(configuration={"a": 1})
        state.graph.register(s)

        STORE.snapshot_tenant("acme-corp")

        # Drop in-memory state, then reload
        STORE.reset_all()
        assert STORE.get("acme-corp") is None

        loaded = STORE.load_tenant("acme-corp")
        assert loaded is True
        reloaded = STORE.get("acme-corp")
        assert reloaded is not None
        assert s.id in reloaded.graph.constructs
    finally:
        configure_persistence(None)
        STORE.reset_all()


def test_store_load_all_restores_every_tenant(tmp_dir):
    configure_persistence(str(tmp_dir))
    try:
        STORE.reset_all()
        for tid in ("a", "b", "c"):
            state = STORE.get_or_create(tid)
            state.graph.register(State(configuration={}))
        STORE.snapshot_all()

        STORE.reset_all()
        loaded = STORE.load_all()
        assert set(loaded) == {"a", "b", "c"}
    finally:
        configure_persistence(None)
        STORE.reset_all()


def test_store_persistence_methods_require_attached_backend():
    # Ensure detached
    configure_persistence(None)
    STORE.reset_all()
    state = STORE.get_or_create("x")
    state.graph.register(State(configuration={}))
    with pytest.raises(RuntimeError, match="no persistence backend"):
        STORE.snapshot_tenant("x")


# ---- HTTP endpoints ----


@pytest.fixture
def client(tmp_dir) -> TestClient:
    reset_registry()
    configure_persistence(str(tmp_dir))
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(cognition_router)
    app.include_router(musia_tenants_router)
    yield TestClient(app)
    configure_persistence(None)
    reset_registry()


def test_snapshot_endpoint_writes_file(client, tmp_dir):
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme-corp"},
        json={"configuration": {"x": 1}},
    )
    r = client.post("/musia/tenants/acme-corp/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "acme-corp"
    assert body["construct_count"] == 1
    assert Path(body["path"]).exists()


def test_load_endpoint_restores_in_memory_state(client, tmp_dir):
    # 1) Create + snapshot
    s_resp = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme-corp"},
        json={"configuration": {"x": 1}},
    )
    state_id = s_resp.json()["id"]
    client.post("/musia/tenants/acme-corp/snapshot")

    # 2) Drop in-memory state
    client.delete("/musia/tenants/acme-corp")
    assert client.get("/musia/tenants/acme-corp").status_code == 404

    # 3) Load from disk
    r = client.post("/musia/tenants/acme-corp/load")
    assert r.status_code == 200
    assert r.json()["loaded"] is True

    # 4) Construct is back
    r = client.get(
        f"/constructs/{state_id}",
        headers={"X-Tenant-ID": "acme-corp"},
    )
    assert r.status_code == 200


def test_load_endpoint_returns_loaded_false_when_no_snapshot(client):
    r = client.post("/musia/tenants/never-saved/load")
    assert r.status_code == 200
    assert r.json()["loaded"] is False


def test_delete_snapshot_endpoint(client, tmp_dir):
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme-corp"},
        json={"configuration": {}},
    )
    client.post("/musia/tenants/acme-corp/snapshot")

    # File exists
    snapshot_path = tmp_dir / "registry-acme-corp.json"
    assert snapshot_path.exists()

    r = client.delete("/musia/tenants/acme-corp/snapshot")
    assert r.status_code == 204
    assert not snapshot_path.exists()


def test_delete_snapshot_404_when_no_file(client):
    r = client.delete("/musia/tenants/never-saved/snapshot")
    assert r.status_code == 404


def test_persistence_endpoints_409_when_unconfigured(tmp_dir):
    """If persistence is not configured, the endpoints fail cleanly."""
    reset_registry()
    configure_persistence(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(musia_tenants_router)
    client = TestClient(app)

    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme-corp"},
        json={"configuration": {}},
    )
    r = client.post("/musia/tenants/acme-corp/snapshot")
    assert r.status_code == 409
    assert "persistence not configured" in r.json()["detail"]
