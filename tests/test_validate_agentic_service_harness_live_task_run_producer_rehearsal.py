"""Tests for Agentic Service Harness local task/run producer rehearsal.

Purpose: prove the live producer evidence fixture can be projected into a
local dry-run report without granting live execution or mutation authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_task_run_producer and
scripts.validate_agentic_service_harness_live_task_run_producer_rehearsal.
Invariants:
  - The default rehearsal validates.
  - Authority, route, and secret drift fail closed.
  - Written validation receipts remain non-terminal.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_task_run_producer import (  # noqa: E402
    DEFAULT_EVIDENCE_FIXTURE_PATH,
    REHEARSAL_REPORT_ID,
    project_evidence_fixture_to_rehearsal,
)
from scripts.validate_agentic_service_harness_live_task_run_producer_rehearsal import (  # noqa: E402
    FALSE_EFFECT_FLAGS,
    main,
    validate_live_task_run_producer_rehearsal,
    write_live_task_run_producer_rehearsal_validation,
)


def _default_fixture() -> dict:
    return json.loads(DEFAULT_EVIDENCE_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_live_task_run_producer_rehearsal_accepts_default_fixture() -> None:
    validation, report = validate_live_task_run_producer_rehearsal()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_task_run_producer_evidence.local.json"
    assert validation.report_id == REHEARSAL_REPORT_ID
    assert validation.producer_state == "local_dry_run_ready"
    assert validation.effect_denial_count == len(FALSE_EFFECT_FLAGS)
    assert report["planning_only"] is True
    assert report["live_producer_implemented"] is False
    assert report["terminal_closure"] is False


def test_live_task_run_producer_rehearsal_projects_fixture_without_effects() -> None:
    fixture = _default_fixture()
    report = project_evidence_fixture_to_rehearsal(fixture, "test://fixture")

    assert report["source_fixture_id"] == fixture["fixture_id"]
    assert report["scope"]["tenant_id"] == fixture["scope"]["tenant_id"]
    assert report["task_projection"]["task_id"] == fixture["task_intake_evidence"]["task_id"]
    assert report["run_projection"]["run_id"] == fixture["run_projection_evidence"]["run_id"]
    assert report["run_projection"]["executes_adapter"] is False
    assert report["run_projection"]["creates_branch"] is False
    assert report["effect_boundary"]["network_policy"] == "none"
    assert all(report["effect_boundary"][flag_name] is False for flag_name in FALSE_EFFECT_FLAGS)


def test_live_task_run_producer_rehearsal_rejects_authority_enablement(tmp_path: Path) -> None:
    fixture = _default_fixture()
    fixture["authority_denials"]["external_adapter_integrated"] = True
    fixture_path = tmp_path / "producer-evidence.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    validation, report = validate_live_task_run_producer_rehearsal(fixture_path=fixture_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_adapter_integrated" in serialized_errors
    assert report["effect_boundary"]["external_adapter_integrated"] is False
    assert validation.fixture_path == "producer-evidence.json"


def test_live_task_run_producer_rehearsal_rejects_mutation_route_ref(tmp_path: Path) -> None:
    fixture = _default_fixture()
    fixture["status_publication_evidence"]["validator_refs"].append("POST /api/v1/harness/tasks")
    fixture_path = tmp_path / "producer-evidence.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    validation, report = validate_live_task_run_producer_rehearsal(fixture_path=fixture_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert report["status_publication_projection"]["read_only"] is True
    assert report["terminal_closure"] is False


def test_live_task_run_producer_rehearsal_writer_records_non_terminal_report(tmp_path: Path) -> None:
    validation, report = validate_live_task_run_producer_rehearsal()
    output_path = tmp_path / "rehearsal-validation.json"
    written = write_live_task_run_producer_rehearsal_validation(validation, report, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert payload["ok"] is True
    assert payload["rehearsal_report"]["report_id"] == REHEARSAL_REPORT_ID
    assert payload["rehearsal_report"]["report_is_not_terminal_closure"] is True
    assert payload["rehearsal_report"]["effect_boundary"]["runtime_state_written"] is False


def test_live_task_run_producer_rehearsal_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["producer_state"] == "local_dry_run_ready"
    assert payload["rehearsal_report"]["live_producer_implemented"] is False
