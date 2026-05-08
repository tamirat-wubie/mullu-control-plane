"""Purpose: verify deterministic proof-route gap triage witnesses.

Governance scope: keeps unclassified route triage derived from the canonical
proof matrix without silently reclassifying any route.
Dependencies: scripts.proof_route_gap_triage, proof coverage fixture.
Invariants: all unclassified routes are preserved, grouped, ranked, and written
as deterministic JSON.
"""

from __future__ import annotations

import json

from scripts.proof_coverage_matrix import CANONICAL_OUTPUT
from scripts.proof_route_gap_triage import (
    RouteDeclaration,
    build_gap_triage_report,
    discover_route_declarations,
    route_family,
    write_gap_triage_report,
)


def test_gap_triage_report_preserves_canonical_unclassified_routes() -> None:
    matrix = json.loads(CANONICAL_OUTPUT.read_text(encoding="utf-8"))
    report = build_gap_triage_report(matrix, discover_route_declarations())

    assert report["schema_version"] == 1
    assert report["generated_by"] == "scripts/proof_route_gap_triage.py"
    assert report["declared_route_count"] == matrix["route_coverage"]["route_count"]
    assert report["total_unclassified_route_count"] == matrix["route_coverage"]["unclassified_route_count"]
    assert sum(family["unclassified_route_count"] for family in report["ranked_families"]) == report[
        "total_unclassified_route_count"
    ]
    assert report["ranked_families"] == sorted(
        report["ranked_families"],
        key=lambda family: (
            -family["unclassified_route_count"],
            {"effect_bearing": 0, "mixed": 1, "read_model": 2}[family["risk_class"]],
            family["route_family"],
        ),
    )


def test_gap_triage_groups_api_family_and_detects_effect_routes() -> None:
    matrix = {
        "generated_by": "fixture",
        "route_coverage": {
            "route_count": 3,
            "unclassified_route_count": 2,
            "routes": [
                {
                    "route": "/api/v1/agent/register",
                    "surface_id": "unclassified_declared_route",
                    "coverage_state": "unproven",
                },
                {
                    "route": "/api/v1/agent/heartbeat",
                    "surface_id": "unclassified_declared_route",
                    "coverage_state": "unproven",
                },
                {
                    "route": "/api/v1/stream",
                    "surface_id": "llm_streaming",
                    "coverage_state": "witnessed",
                },
            ],
        },
    }
    declarations = [
        RouteDeclaration("/api/v1/agent/register", "POST", "mcoi/mcoi_runtime/app/routers/agent.py"),
        RouteDeclaration("/api/v1/agent/heartbeat", "GET", "mcoi/mcoi_runtime/app/routers/agent.py"),
    ]

    report = build_gap_triage_report(matrix, declarations)
    family = report["ranked_families"][0]

    assert report["total_unclassified_route_count"] == 2
    assert family["route_family"] == "/api/v1/agent"
    assert family["unclassified_route_count"] == 2
    assert family["risk_class"] == "effect_bearing"
    assert family["suggested_proof_level"] == "action_proof"
    assert family["closure_candidate_id"] == "classify_agent_routes"
    assert family["source_files"] == ["mcoi/mcoi_runtime/app/routers/agent.py"]


def test_route_family_is_stable_for_api_and_gateway_paths() -> None:
    assert route_family("/api/v1/tenant/{tenant_id}") == "/api/v1/tenant"
    assert route_family("/api/v1/connectors/{connector_id}/enable") == "/api/v1/connectors"
    assert route_family("/authority/operator") == "/authority"
    assert route_family("/commands/{command_id}/closure") == "/commands"


def test_gap_triage_report_writer_uses_sorted_json(tmp_path) -> None:
    matrix = {
        "generated_by": "fixture",
        "route_coverage": {
            "route_count": 1,
            "unclassified_route_count": 1,
            "routes": [
                {
                    "route": "/api/v1/config/update",
                    "surface_id": "unclassified_declared_route",
                    "coverage_state": "unproven",
                }
            ],
        },
    }
    report = build_gap_triage_report(
        matrix,
        [RouteDeclaration("/api/v1/config/update", "POST", "mcoi/mcoi_runtime/app/routers/config.py")],
    )

    output_path = write_gap_triage_report(report, tmp_path / "proof_route_gap_triage.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8").endswith("\n")
    assert payload["ranked_families"][0]["route_family"] == "/api/v1/config"
    assert payload["ranked_families"][0]["suggested_surface_id"] == "config_proof_surface"
