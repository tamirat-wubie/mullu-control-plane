"""Tests for governed swarm, note-memory, and simple package metadata.

Purpose: verify control-plane package metadata exposes guarded console entry
points without widening package discovery.
Governance scope: packaging must not bypass CLI rejection handling or include
unrelated workspace packages.
Dependencies: mcoi/pyproject.toml, mcoi/README.md, and control-plane handoff
docs.
Invariants: console entry points target guarded boundaries and package
discovery remains bounded to mcoi_runtime.
"""

from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_governed_console_entry_points_are_guarded() -> None:
    metadata = tomllib.loads((ROOT / "mcoi" / "pyproject.toml").read_text(encoding="utf-8"))

    scripts = metadata["project"]["scripts"]
    assert scripts["mcoi"] == "mcoi_runtime.app.cli:main"
    assert scripts["mcoi-migrate-proofs"] == "mcoi_runtime.migration.runner:main"
    assert scripts["mullu"] == "mcoi_runtime.core.simple_cli:guarded_main"
    assert scripts["mcoi-swarm"] == "mcoi_runtime.swarm.cli:guarded_main"
    assert scripts["mcoi-notes"] == "mcoi_runtime.core.note_memory_cli:guarded_main"
    assert metadata["project"]["name"] == "mcoi-runtime"
    assert metadata["tool"]["setuptools"]["packages"]["find"]["include"] == ["mcoi_runtime*"]
    assert "fastapi>=0.115" in metadata["project"]["optional-dependencies"]["gateway"]


def test_control_plane_docs_record_swarm_and_note_memory_surfaces() -> None:
    note_text = (ROOT / "docs" / "governed-note-memory-control-plane-handoff.md").read_text(encoding="utf-8")
    swarm_text = (ROOT / "docs" / "governed-swarm-invoice.md").read_text(encoding="utf-8")

    assert "MULLU_NOTE_MEMORY_ENABLED=true" in note_text
    assert "MULLU_NOTE_MEMORY_STORE_PATH" in note_text
    assert "POST /api/v1/notes/events" in note_text
    assert "promotion receipts" in note_text
    assert "invoice_closed.json" in swarm_text
    assert "/api/v1/swarm/invoice-runs" in swarm_text
    assert "No specialist receives side-effect authority" in swarm_text


def test_package_readme_documents_simple_platform_surface() -> None:
    text = (ROOT / "mcoi" / "README.md").read_text(encoding="utf-8")

    assert "Governance scope" in text
    assert "mullu check" in text
    assert "mullu start --json" in text
    assert "mullu actions" in text
    assert "mullu outcomes" in text
    assert "mullu task review-docs" in text
    assert "Ready" in text
    assert "Needs review" in text
    assert "Blocked" in text
    assert "mount_simple_platform_router_from_env" in text
    assert "MULLU_SIMPLE_PLATFORM_ENABLED" in text
    assert "SimplePlatformRuntime" in text
    assert "create_simple_platform_fastapi_router" in text
    assert "GET /api/v1/simple/home" in text
    assert "GET /api/v1/simple/start" in text
    assert "POST /api/v1/simple/actions/check" in text
    assert "POST /api/v1/simple/tasks/check" in text
    assert "POST /api/v1/simple/workflows/check" in text
    assert "mullu workflow docs-update" in text
    assert "simple_action_summaries" in text
    assert "simple_workflow_summaries" in text
    assert "simple_start_guide" in text
    assert "simple_home_summary" in text
    assert "status_label" in text
    assert "count_summary" in text
    assert "next_action" in text
    assert "action_items" in text
    assert "command_guidance" in text
    assert "start_here" in text
    assert "OperationalDashboardRuntime" in text
    assert "mount_operational_dashboard_router_from_env" in text
    assert "MULLU_DASHBOARD_ENABLED" in text
    assert "GET /api/v1/dashboard/home" in text
    assert "GET /api/v1/dashboard/state" in text
