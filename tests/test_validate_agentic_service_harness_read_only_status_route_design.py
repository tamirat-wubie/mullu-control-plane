"""Tests for Agentic Service Harness read-only status route design validation.

Purpose: prove the first harness status route artifact stays design-only,
read-only, and free of route implementations, mutation endpoints, UI,
external adapters, and high-risk authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_read_only_status_route_design.
Invariants:
  - The default design contains all required route, response, blocker, and
    false-flag symbols.
  - Route implementation snippets, mutation route strings, and enablement
    flags fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_agentic_service_harness_read_only_status_route_design import (  # noqa: E402
    REQUIRED_FALSE_FLAGS,
    REQUIRED_RESPONSE_FIELDS,
    REQUIRED_SECTIONS,
    REQUIRED_SOURCE_REFS,
    main,
    validate_read_only_status_route_design,
)


DEFAULT_DESIGN = ROOT / "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_ONLY_STATUS_ROUTE_DESIGN.md"


def test_read_only_status_route_design_accepts_default_artifact() -> None:
    validation = validate_read_only_status_route_design()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.design_path == "MULLUSI_AGENTIC_SERVICE_HARNESS_READ_ONLY_STATUS_ROUTE_DESIGN.md"
    assert validation.required_section_count == len(REQUIRED_SECTIONS)
    assert validation.required_source_ref_count == len(REQUIRED_SOURCE_REFS)
    assert validation.required_response_field_count == len(REQUIRED_RESPONSE_FIELDS)
    assert validation.required_false_flag_count == len(REQUIRED_FALSE_FLAGS)


def test_read_only_status_route_design_rejects_missing_route_path(tmp_path: Path) -> None:
    design_path = _write_design(
        tmp_path,
        DEFAULT_DESIGN.read_text(encoding="utf-8").replace(
            "`/api/v1/harness/status`",
            "`/api/v1/harness/other-status`",
        ),
    )

    validation = validate_read_only_status_route_design(design_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing route_term: `/api/v1/harness/status`" in serialized_errors
    assert "route path must appear exactly once, observed 0" in serialized_errors


def test_read_only_status_route_design_rejects_mutation_route_string(tmp_path: Path) -> None:
    design_path = _write_design(
        tmp_path,
        DEFAULT_DESIGN.read_text(encoding="utf-8")
        + "\nForbidden mutation route: POST /api/v1/harness/tasks\n",
    )

    validation = validate_read_only_status_route_design(design_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden mutation_route_string" in serialized_errors
    assert "route path must appear exactly once" not in serialized_errors


def test_read_only_status_route_design_rejects_route_registration(tmp_path: Path) -> None:
    design_path = _write_design(
        tmp_path,
        DEFAULT_DESIGN.read_text(encoding="utf-8")
        + '\nForbidden implementation: router.get("/api/v1/harness/other-status")\n',
    )

    validation = validate_read_only_status_route_design(design_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "forbidden route_registration" in serialized_errors
    assert "route path must appear exactly once" not in serialized_errors


def test_read_only_status_route_design_rejects_enablement_flag(tmp_path: Path) -> None:
    design_path = _write_design(
        tmp_path,
        DEFAULT_DESIGN.read_text(encoding="utf-8").replace(
            "route_implemented=false",
            "route_implemented=true",
        ),
    )

    validation = validate_read_only_status_route_design(design_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing false_flag: route_implemented=false" in serialized_errors
    assert "forbidden route_implementation_enablement" in serialized_errors


def test_read_only_status_route_design_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["required_response_field_count"] == len(REQUIRED_RESPONSE_FIELDS)


def _write_design(tmp_path: Path, design_text: str) -> Path:
    design_path = tmp_path / "read-only-status-route-design.md"
    design_path.write_text(design_text, encoding="utf-8")
    return design_path
