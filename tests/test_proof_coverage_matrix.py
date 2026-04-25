"""Purpose: verify the generated proof coverage matrix witness.

Governance scope: prevents drift between route surfaces and the proof coverage
closure ledger.
Dependencies: scripts.proof_coverage_matrix, canonical JSON fixture, repository
source tree.
Invariants: coverage levels are bounded, evidence files exist, runtime witnesses
are explicit, and canonical fixture content is generated from code.
"""

from __future__ import annotations

import json

from scripts.proof_coverage_matrix import (
    ASSURANCE_OUTPUT,
    CANONICAL_OUTPUT,
    REPO_ROOT,
    discover_declared_routes,
    proof_coverage_matrix,
    validate_matrix_routes,
)


def _load_fixture() -> dict:
    return json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))


def test_fixture_contract_is_canonical() -> None:
    matrix = _load_fixture()

    assert matrix == proof_coverage_matrix()
    assert matrix["schema_version"] == 1
    assert matrix["generated_by"] == "scripts/proof_coverage_matrix.py"
    assert len(matrix["surfaces"]) >= 3


def test_coverage_levels_are_bounded() -> None:
    matrix = _load_fixture()
    coverage_levels = set(matrix["coverage_levels"])

    assert {"gap", "request_proof", "action_proof", "audit_chain"} <= coverage_levels
    assert all(surface["request_proof"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["action_proof"] in coverage_levels for surface in matrix["surfaces"])
    assert all(surface["audit"] in coverage_levels for surface in matrix["surfaces"])


def test_gateway_runtime_witnesses_bind_closure_invariants() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    gateway_surface = surfaces["gateway_capability_fabric"]
    witnesses = set(gateway_surface["runtime_witnesses"])

    assert gateway_surface["action_proof"] == "action_proof"
    assert "/commands/{command_id}/closure" in gateway_surface["representative_paths"]
    assert "command_lifecycle_events_are_hash_linked" in witnesses
    assert "terminal_closure_requires_evidence_refs" in witnesses
    assert "successful_response_is_bound_to_response_evidence_closure" in witnesses


def test_governed_session_request_envelope_is_covered() -> None:
    matrix = _load_fixture()
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}
    session_surface = surfaces["governed_session"]

    assert session_surface["request_proof"] == "request_proof"
    assert session_surface["action_proof"] == "action_proof"
    assert "GovernedSession.llm" in session_surface["representative_paths"]
    assert "mcoi/tests/test_governed_session.py" in session_surface["evidence_files"]


def test_gaps_have_closure_actions() -> None:
    matrix = _load_fixture()
    closure_surfaces = {
        surface_id
        for action in matrix["closure_actions"]
        for surface_id in action["surfaces"]
        if action["status"] == "open"
    }
    gap_surfaces = {
        surface["surface_id"]
        for surface in matrix["surfaces"]
        if "gap" in {surface["request_proof"], surface["action_proof"], surface["audit"]}
    }

    assert gap_surfaces <= closure_surfaces
    closure_actions = {action["action_id"]: action for action in matrix["closure_actions"]}
    surfaces = {surface["surface_id"]: surface for surface in matrix["surfaces"]}

    assert closure_actions["bind_tool_arguments_to_capability_policy_receipts"]["status"] == "closed"
    assert closure_actions["normalize_gateway_request_receipt_envelopes"]["status"] == "closed"
    assert surfaces["gateway_capability_fabric"]["request_proof"] == "request_proof"
    assert surfaces["tool_invocation"]["action_proof"] == "action_proof"
    assert all(action["surfaces"] for action in matrix["closure_actions"])


def test_evidence_files_exist() -> None:
    matrix = _load_fixture()
    evidence_files = {evidence_file for surface in matrix["surfaces"] for evidence_file in surface["evidence_files"]}

    assert "mcoi/mcoi_runtime/app/streaming.py" in evidence_files
    assert "gateway/server.py" in evidence_files
    assert all((REPO_ROOT / evidence_file).exists() for evidence_file in evidence_files)


def test_representative_http_paths_are_declared() -> None:
    matrix = _load_fixture()
    routes = discover_declared_routes()

    assert "/api/v1/stream" in routes
    assert "/api/v1/chat/stream" in routes
    assert validate_matrix_routes(matrix, routes) == []


def test_generated_assurance_copy_matches_when_present() -> None:
    matrix = _load_fixture()

    assert CANONICAL_OUTPUT.exists()
    assert matrix["surfaces"]
    if ASSURANCE_OUTPUT.exists():
        assurance = json.loads(ASSURANCE_OUTPUT.read_text(encoding="utf-8"))
        assert [surface["surface_id"] for surface in assurance["surfaces"]] == [
            surface["surface_id"] for surface in matrix["surfaces"]
        ]
