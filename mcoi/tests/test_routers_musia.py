"""HTTP tests for the MUSIA v4.x routers (mfidel, constructs, cognition, ucja).

Each router is mounted standalone in a minimal FastAPI app for these tests
so we don't depend on the full server bootstrap (deps, middleware, etc).
The full-server include is verified separately by import-only smoke.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---- Shared fixture ----


@pytest.fixture
def client() -> TestClient:
    """Build an isolated FastAPI app with all four MUSIA routers mounted."""
    from mcoi_runtime.app.routers.cognition import router as cognition_router
    from mcoi_runtime.app.routers.constructs import (
        reset_registry,
        router as constructs_router,
    )
    from mcoi_runtime.app.routers.mfidel import router as mfidel_router
    from mcoi_runtime.app.routers.ucja import router as ucja_router

    reset_registry()
    app = FastAPI()
    app.include_router(mfidel_router)
    app.include_router(constructs_router)
    app.include_router(cognition_router)
    app.include_router(ucja_router)
    return TestClient(app)


# ---- /mfidel ----


def test_mfidel_grid_summary(client):
    r = client.get("/mfidel/grid")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == 34
    assert body["cols"] == 8
    assert body["total_slots"] == 272
    assert body["non_empty_count"] == 269
    # Three known empty positions
    empties = {(p[0], p[1]) for p in body["empty_positions"]}
    assert empties == {(20, 8), (21, 8), (24, 8)}


def test_mfidel_atom_lookup(client):
    r = client.get("/mfidel/atom/1/1")
    assert r.status_code == 200
    body = r.json()
    assert body["row"] == 1
    assert body["col"] == 1
    assert body["is_empty"] is False
    assert body["kind"] == "consonant"


def test_mfidel_atom_empty_slot(client):
    r = client.get("/mfidel/atom/20/8")
    assert r.status_code == 200
    body = r.json()
    assert body["is_empty"] is True
    assert body["glyph"] == ""


def test_mfidel_atom_out_of_range(client):
    r = client.get("/mfidel/atom/99/1")
    assert r.status_code == 400


def test_mfidel_overlay_for_ha(client):
    """f[1][1] (ሀ) uses f[17][8] overlay per spec exception."""
    r = client.get("/mfidel/overlay/1/1")
    assert r.status_code == 200
    body = r.json()
    assert body["overlay"]["row"] == 17
    assert body["overlay"]["col"] == 8


def test_mfidel_overlay_for_empty_slot_is_null(client):
    r = client.get("/mfidel/overlay/20/8")
    assert r.status_code == 200
    body = r.json()
    assert body["overlay"] is None


# ---- /constructs ----


def test_constructs_create_state(client):
    r = client.post("/constructs/state", json={"configuration": {"x": 1}})
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "state"
    assert body["tier"] == 1
    assert body["fields"]["configuration"] == {"x": 1}


def test_constructs_list_filters_by_tier(client):
    client.post("/constructs/state", json={"configuration": {}})
    client.post("/constructs/boundary", json={"inside_predicate": "scope"})
    r = client.get("/constructs?tier=1")
    body = r.json()
    assert body["total"] == 2
    assert body["by_type"].get("state") == 1
    assert body["by_type"].get("boundary") == 1


def test_constructs_list_filters_by_type(client):
    client.post("/constructs/state", json={"configuration": {}})
    client.post("/constructs/state", json={"configuration": {}})
    client.post("/constructs/boundary", json={"inside_predicate": "scope"})
    r = client.get("/constructs?type_filter=state")
    body = r.json()
    assert body["total"] == 2
    assert all(c["type"] == "state" for c in body["constructs"])


def test_constructs_create_change_resolves_state_refs(client):
    s1 = client.post("/constructs/state", json={"configuration": {"v": 1}}).json()
    s2 = client.post("/constructs/state", json={"configuration": {"v": 2}}).json()
    r = client.post(
        "/constructs/change",
        json={
            "state_before_id": s1["id"],
            "state_after_id": s2["id"],
            "delta_vector": {"d": 1},
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["fields"]["state_before_id"] == s1["id"]
    assert body["fields"]["state_after_id"] == s2["id"]


def test_constructs_create_change_rejects_unknown_state_ref(client):
    r = client.post(
        "/constructs/change",
        json={
            "state_before_id": "00000000-0000-0000-0000-000000000000",
            "delta_vector": {},
        },
    )
    assert r.status_code == 400


def test_constructs_get_by_id(client):
    s = client.post("/constructs/state", json={"configuration": {"x": 1}}).json()
    r = client.get(f"/constructs/{s['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == s["id"]


def test_constructs_get_unknown_id_404(client):
    r = client.get("/constructs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_constructs_dependents_list(client):
    s1 = client.post("/constructs/state", json={"configuration": {}}).json()
    s2 = client.post("/constructs/state", json={"configuration": {}}).json()
    chg = client.post(
        "/constructs/change",
        json={
            "state_before_id": s1["id"],
            "state_after_id": s2["id"],
            "delta_vector": {},
        },
    ).json()
    r = client.get(f"/constructs/{s1['id']}/dependents")
    assert r.status_code == 200
    deps = r.json()
    assert chg["id"] in deps


def test_constructs_delete_with_dependents_rejected(client):
    s1 = client.post("/constructs/state", json={"configuration": {}}).json()
    s2 = client.post("/constructs/state", json={"configuration": {}}).json()
    client.post(
        "/constructs/change",
        json={
            "state_before_id": s1["id"],
            "state_after_id": s2["id"],
            "delta_vector": {},
        },
    )
    r = client.delete(f"/constructs/{s1['id']}")
    assert r.status_code == 409


def test_constructs_delete_orphan_succeeds(client):
    s = client.post("/constructs/state", json={"configuration": {}}).json()
    r = client.delete(f"/constructs/{s['id']}")
    assert r.status_code == 204
    assert client.get(f"/constructs/{s['id']}").status_code == 404


def test_constructs_create_constraint_validates_violation_response(client):
    r = client.post(
        "/constructs/constraint",
        json={
            "domain": "x",
            "restriction": "y",
            "violation_response": "explode",
        },
    )
    assert r.status_code == 400


# ---- Φ_gov on the construct write path ----


def test_constructs_phi_gov_rejects_write_returns_403(client):
    """Install a Φ_agent filter that always blocks at L3, then verify that
    a POST is refused with 403 and the construct is NOT in the registry.
    """
    from mcoi_runtime.app.routers.constructs import (
        _REGISTRY,
        install_phi_agent_filter,
    )
    from mcoi_runtime.substrate.phi_gov import PhiAgentFilter

    install_phi_agent_filter(
        PhiAgentFilter(l3=lambda d, c, a: False)
    )
    pre_size = len(_REGISTRY.constructs)

    r = client.post("/constructs/state", json={"configuration": {"x": 1}})
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["proof_state"] == "fail"
    # The field records the level the filter stopped at — here L3.
    assert detail["phi_agent_level_passed"] == "L3_NORMATIVE"
    # And the registry hasn't grown
    assert len(_REGISTRY.constructs) == pre_size


def test_constructs_phi_gov_approves_write_returns_201(client):
    """Default Φ_agent passes at L5; writes succeed normally."""
    r = client.post("/constructs/state", json={"configuration": {"x": 1}})
    assert r.status_code == 201
    assert r.json()["type"] == "state"


def test_constructs_phi_gov_blocks_change_with_valid_refs(client):
    """States get registered (default permissive); then a Φ_agent block
    refuses the Change. This proves governance happens *after* structural
    validation: the change construct itself is well-formed.
    """
    from mcoi_runtime.app.routers.constructs import install_phi_agent_filter
    from mcoi_runtime.substrate.phi_gov import PhiAgentFilter

    s1 = client.post("/constructs/state", json={"configuration": {"v": 1}}).json()
    s2 = client.post("/constructs/state", json={"configuration": {"v": 2}}).json()

    # Now install a filter that blocks
    install_phi_agent_filter(PhiAgentFilter(l1=lambda d, c, a: False))

    r = client.post(
        "/constructs/change",
        json={
            "state_before_id": s1["id"],
            "state_after_id": s2["id"],
            "delta_vector": {"d": 1},
        },
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["phi_agent_level_passed"] == "L1_IDENTITY"


# ---- /cognition ----


def test_cognition_run_empty_field_converges(client):
    r = client.post("/cognition/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["converged"] is True
    assert body["proof_state"] == "Pass"
    assert body["final_tension"]["total"] == 0.0
    # 15 step records for the single iteration
    assert len(body["step_records"]) == 15


def test_cognition_run_with_pending_validation_runs_to_max_iterations(client):
    """Build a registry with a pending Validation; cycle hits max_iterations."""
    # Set up a target_pattern via a State (Pattern requires UUID for template)
    # Easiest path: use the construct registry's State endpoint then directly
    # register a Pattern + pending Validation via the substrate (the router
    # only exposes Tier 1 writes, so we drop into the registry directly).
    from mcoi_runtime.app.routers.constructs import _REGISTRY
    from mcoi_runtime.substrate.constructs import Pattern, State, Validation

    s = State(configuration={})
    _REGISTRY.register(s)
    p = Pattern(template_state_id=s.id)
    _REGISTRY.register(p)
    v = Validation(
        target_pattern_id=p.id,
        criteria=("c",),
        decision="unknown",
    )
    _REGISTRY.register(v)

    r = client.post(
        "/cognition/run",
        json={"max_iterations": 3, "stable_iterations": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["proof_state"] == "BudgetUnknown"
    assert body["iterations"] == 3


def test_cognition_tension_endpoint(client):
    r = client.get("/cognition/tension")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0.0


def test_cognition_tension_negative_weight_rejected(client):
    r = client.get("/cognition/tension?governance=-1")
    assert r.status_code == 400


def test_cognition_symbol_field_summary(client):
    client.post("/constructs/state", json={"configuration": {}})
    client.post("/constructs/state", json={"configuration": {}})
    client.post("/constructs/boundary", json={"inside_predicate": "scope"})
    r = client.get("/cognition/symbol-field")
    assert r.status_code == 200
    body = r.json()
    assert body["size"] == 3
    assert body["by_type"].get("state") == 2
    assert body["by_type"].get("boundary") == 1


# ---- /ucja ----


def _full_payload() -> dict:
    return {
        "purpose_statement": "fix bug",
        "initial_state_descriptor": {"phase": "broken"},
        "target_state_descriptor": {"phase": "fixed"},
        "boundary_specification": {"inside_predicate": "auth_module"},
        "authority_required": ["repo_write"],
        "acceptance_criteria": ["test_a", "test_b"],
        "blast_radius": "module",
    }


def test_ucja_qualify_passes_complete_request(client):
    r = client.post(
        "/ucja/qualify",
        json={
            "purpose_statement": "fix bug",
            "initial_state_descriptor": {"phase": "broken"},
            "target_state_descriptor": {"phase": "fixed"},
            "boundary_specification": {"inside_predicate": "scope"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["terminal_verdict"] == "pass"


def test_ucja_qualify_rejects_empty_purpose(client):
    r = client.post(
        "/ucja/qualify",
        json={
            "purpose_statement": "",
            "initial_state_descriptor": {"x": 1},
            "target_state_descriptor": {"x": 2},
            "boundary_specification": {"inside_predicate": "s"},
        },
    )
    # FastAPI will reject empty string at the model layer? It accepts since
    # min_length isn't enforced; UCJA L0 then rejects.
    assert r.status_code == 200
    body = r.json()
    assert body["rejected"] is True


def test_ucja_define_job_full_pipeline(client):
    r = client.post("/ucja/define-job", json=_full_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["draft"]["is_complete"] is True
    assert len(body["layer_results"]) == 10
    assert body["draft"]["task_descriptions"] == ["satisfy:test_a", "satisfy:test_b"]
    assert body["draft"]["closure_criteria"] == ["test_a", "test_b"]


def test_ucja_define_job_halts_at_l1_no_authority(client):
    payload = _full_payload()
    payload["authority_required"] = []
    r = client.post("/ucja/define-job", json=payload)
    body = r.json()
    assert body["reclassified"] is True
    assert body["halted_at_layer"] == "L1_purpose_boundary"


def test_ucja_define_job_halts_at_l9_no_acceptance_criteria(client):
    payload = _full_payload()
    payload["acceptance_criteria"] = []
    r = client.post("/ucja/define-job", json=payload)
    body = r.json()
    assert body["reclassified"] is True
    assert body["halted_at_layer"] == "L9_closure"


def test_ucja_define_job_l7_flags_system_blast_radius(client):
    payload = _full_payload()
    payload["blast_radius"] = "system"
    r = client.post("/ucja/define-job", json=payload)
    body = r.json()
    assert body["accepted"] is True
    assert any("system_blast_radius" in risk for risk in body["draft"]["risks"])
