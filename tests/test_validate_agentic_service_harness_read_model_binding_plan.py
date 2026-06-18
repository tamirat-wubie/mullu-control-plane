"""Tests for the Agentic Service Harness readiness-map and binding validators.

Purpose: prove the post-readiness harness map and binding plan remain
planning-only, read-only, and complete before any UI, mutation endpoint, or
external adapter implementation begins.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_readiness_map and
scripts.validate_agentic_service_harness_read_model_binding_plan.
Invariants:
  - The default readiness map contains all required sections, statuses,
    denial statements, partial symbols, and ordered next PR markers.
  - The default plan contains all required symbols, source refs, false flags,
    non-goals, and ordered next PR markers.
  - Mutation route strings and missing symbols fail closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_read_model_binding_plan import (  # noqa: E402
    REQUIRED_FALSE_FLAGS,
    REQUIRED_NON_GOALS,
    REQUIRED_SECTIONS,
    REQUIRED_SYMBOLS,
    main,
    validate_read_model_binding_plan,
)
from scripts.validate_agentic_service_harness_readiness_map import (  # noqa: E402
    REQUIRED_DENIALS,
    REQUIRED_PARTIAL_SYMBOLS,
    REQUIRED_READY_SYMBOLS,
    REQUIRED_SECTIONS as REQUIRED_MAP_SECTIONS,
    REQUIRED_STATUSES,
    main as readiness_map_main,
    validate_readiness_map,
)


def test_readiness_map_accepts_default_artifact() -> None:
    validation = validate_readiness_map()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.map_path == "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md"
    assert validation.required_section_count == len(REQUIRED_MAP_SECTIONS)
    assert validation.required_status_count == len(REQUIRED_STATUSES)
    assert validation.required_ready_symbol_count == len(REQUIRED_READY_SYMBOLS)
    assert validation.required_partial_symbol_count == len(REQUIRED_PARTIAL_SYMBOLS)
    assert validation.required_denial_count == len(REQUIRED_DENIALS)


def test_readiness_map_rejects_missing_repository_connection_ready_row(
    tmp_path: Path,
) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "| RepositoryConnection | READY |",
            "| RepositoryConnection | PARTIAL |",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing ready row: RepositoryConnection read model" in serialized_errors


def test_readiness_map_rejects_missing_agent_run_first_pr(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        map_text.replace(
            "1. `harness(agent-run): add lifecycle read model`",
            "1. `harness(approval): bind approval request projection`",
        ),
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing first next PR: AgentRun lifecycle read model" in serialized_errors


def test_readiness_map_rejects_mutation_route_string(tmp_path: Path) -> None:
    map_text = Path("MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md").read_text(
        encoding="utf-8"
    )
    map_path = tmp_path / "readiness-map.md"
    map_path.write_text(
        f"{map_text}\nForbidden route: POST /api/harness/tasks\n",
        encoding="utf-8",
    )

    validation = validate_readiness_map(map_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden mutation_route" in serialized_errors


def test_readiness_map_cli_json_reports_valid(capsys) -> None:
    exit_code = readiness_map_main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["required_ready_symbol_count"] == len(REQUIRED_READY_SYMBOLS)
    assert payload["required_partial_symbol_count"] == len(REQUIRED_PARTIAL_SYMBOLS)


def test_read_model_binding_plan_accepts_default_artifact() -> None:
    validation = validate_read_model_binding_plan()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.plan_path == "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"
    assert validation.required_section_count == len(REQUIRED_SECTIONS)
    assert validation.required_symbol_count == len(REQUIRED_SYMBOLS)
    assert validation.required_false_flag_count == len(REQUIRED_FALSE_FLAGS)
    assert validation.required_non_goal_count == len(REQUIRED_NON_GOALS)


def test_read_model_binding_plan_rejects_missing_required_symbol(tmp_path: Path) -> None:
    plan_text = Path(
        "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"
    ).read_text(encoding="utf-8")
    plan_path = tmp_path / "binding-plan.md"
    plan_path.write_text(
        plan_text.replace("RepositoryConnection", "RepoBinding"),
        encoding="utf-8",
    )

    validation = validate_read_model_binding_plan(plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing symbol: RepositoryConnection" in serialized_errors


def test_read_model_binding_plan_rejects_mutation_route_string(tmp_path: Path) -> None:
    plan_text = Path(
        "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_MODEL_BINDING_PLAN.md"
    ).read_text(encoding="utf-8")
    plan_path = tmp_path / "binding-plan.md"
    plan_path.write_text(
        f"{plan_text}\nForbidden route: POST /api/harness/tasks\n",
        encoding="utf-8",
    )

    validation = validate_read_model_binding_plan(plan_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden mutation_route" in serialized_errors


def test_read_model_binding_plan_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["required_symbol_count"] == len(REQUIRED_SYMBOLS)
