"""Purpose: verify deterministic proof-route gap triage witnesses.

Governance scope: keeps unclassified route triage derived from the canonical
proof matrix without silently reclassifying any route.
Dependencies: scripts.proof_route_gap_triage, proof coverage fixture.
Invariants: all unclassified routes are preserved, grouped, ranked, and written
as deterministic JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.proof_coverage_matrix import CANONICAL_OUTPUT
from scripts.proof_route_gap_triage import (
    RouteDeclaration,
    build_gap_triage_report,
    discover_route_declarations,
    route_family,
    write_gap_triage_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_unclassified_routes_grouped_by_family() -> None:
    matrix = _matrix_with_unclassified_routes(
        "/api/v1/agent/register",
        "/api/v1/agent/heartbeat",
        "/api/v1/config",
    )
    declarations = [
        RouteDeclaration("/api/v1/agent/register", "POST", "mcoi/mcoi_runtime/app/routers/agent.py"),
        RouteDeclaration("/api/v1/agent/heartbeat", "GET", "mcoi/mcoi_runtime/app/routers/agent.py"),
        RouteDeclaration("/api/v1/config", "GET", "mcoi/mcoi_runtime/app/routers/ops/config.py"),
    ]

    report = build_gap_triage_report(matrix, declarations)
    family_counts = {
        family["route_family"]: family["unclassified_route_count"]
        for family in report["ranked_families"]
    }

    assert report["total_unclassified_route_count"] == 3
    assert report["route_family_count"] == 2
    assert family_counts == {"/api/v1/agent": 2, "/api/v1/config": 1}
    assert report["status"] == "open"


def test_route_gap_triage_binds_source_files_and_methods() -> None:
    matrix = _matrix_with_unclassified_routes(
        "/api/v1/agent/register",
        "/api/v1/agent/heartbeat",
    )
    declarations = [
        RouteDeclaration("/api/v1/agent/register", "POST", "mcoi/mcoi_runtime/app/routers/agent.py"),
        RouteDeclaration("/api/v1/agent/heartbeat", "GET", "mcoi/mcoi_runtime/app/routers/agent.py"),
    ]

    report = build_gap_triage_report(matrix, declarations)
    family = report["ranked_families"][0]

    assert family["route_family"] == "/api/v1/agent"
    assert family["http_methods"] == ["GET", "POST"]
    assert family["source_files"] == ["mcoi/mcoi_runtime/app/routers/agent.py"]
    assert family["sample_routes"] == ["/api/v1/agent/heartbeat", "/api/v1/agent/register"]


def test_closure_candidates_ranked_deterministically() -> None:
    matrix = _matrix_with_unclassified_routes(
        "/api/v1/search/stats",
        "/api/v1/agent/register",
        "/api/v1/agent/heartbeat",
        "/api/v1/search/history",
    )
    declarations = [
        RouteDeclaration("/api/v1/search/stats", "GET", "mcoi/mcoi_runtime/app/routers/data/search.py"),
        RouteDeclaration("/api/v1/agent/register", "POST", "mcoi/mcoi_runtime/app/routers/agent.py"),
        RouteDeclaration("/api/v1/agent/heartbeat", "GET", "mcoi/mcoi_runtime/app/routers/agent.py"),
        RouteDeclaration("/api/v1/search/history", "GET", "mcoi/mcoi_runtime/app/routers/data/search.py"),
    ]

    first_report = build_gap_triage_report(matrix, declarations)
    second_report = build_gap_triage_report(matrix, list(reversed(declarations)))
    ranked_families = first_report["ranked_families"]

    assert first_report == second_report
    assert [family["route_family"] for family in ranked_families] == ["/api/v1/agent", "/api/v1/search"]
    assert [family["risk_class"] for family in ranked_families] == ["effect_bearing", "read_model"]
    assert ranked_families[0]["closure_candidate_id"] == "classify_agent_routes"


def test_triage_report_check_detects_stale_output(tmp_path) -> None:
    matrix_path = tmp_path / "matrix.json"
    output_path = tmp_path / "proof_route_gap_triage.json"
    matrix_path.write_text(
        json.dumps(_matrix_with_unclassified_routes("/api/v1/config/update"), sort_keys=True),
        encoding="utf-8",
    )
    output_path.write_text("{}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "proof_route_gap_triage.py"),
            "--matrix",
            str(matrix_path),
            "--output",
            str(output_path),
            "--check",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "is stale" in result.stderr
    assert str(output_path) in result.stderr
    assert output_path.read_text(encoding="utf-8") == "{}\n"


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


def _matrix_with_unclassified_routes(*routes: str) -> dict:
    return {
        "generated_by": "fixture",
        "route_coverage": {
            "route_count": len(routes),
            "unclassified_route_count": len(routes),
            "routes": [
                {
                    "route": route,
                    "surface_id": "unclassified_declared_route",
                    "coverage_state": "unproven",
                }
                for route in routes
            ],
        },
    }
