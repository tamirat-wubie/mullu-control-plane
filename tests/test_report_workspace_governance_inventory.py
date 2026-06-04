"""Purpose: verify repository-local workspace governance inventory reporting.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.report_workspace_governance_inventory.
Invariants:
  - Witness artifact paths remain repository-relative.
  - Missing files and unsafe paths produce explicit issues.
  - Current witness inventory passes without writing files.
"""

from __future__ import annotations

import copy
import json

from scripts import report_workspace_governance_inventory as reporter


def test_current_inventory_passes() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    inventory = reporter.build_inventory(witness)
    report = reporter.build_inventory_report(inventory)

    assert report["status"] == "passed"
    assert report["artifact_count"] == witness["artifact_count"]
    assert report["artifact_count"] >= 30
    assert report["missing_count"] == 0
    assert report["issue_count"] == 0
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True
    assert any(artifact.name == "sdlc_route_validator" for artifact in inventory)
    assert any(artifact.path == "tests/test_validate_sdlc_route.py" for artifact in inventory)
    assert any(artifact.name == "sdlc_route_helper" for artifact in inventory)


def test_missing_artifact_is_reported() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"][0]["path"] = "docs/missing-governance-artifact.json"

    inventory = reporter.build_inventory(invalid_witness)
    report = reporter.build_inventory_report(inventory)

    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1
    assert any(artifact.issue == "referenced file does not exist" for artifact in inventory)


def test_unsafe_artifact_path_is_reported() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"][0]["path"] = "../AGENTS.md"

    inventory = reporter.build_inventory(invalid_witness)
    report = reporter.build_inventory_report(inventory)

    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1
    assert any(artifact.issue == "parent traversal is not allowed" for artifact in inventory)


def test_artifact_count_mismatch_is_reported() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifact_count"] = invalid_witness["artifact_count"] + 1

    inventory = reporter.build_inventory(invalid_witness)
    report = reporter.build_inventory_report(inventory)

    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1
    assert any(artifact.issue == "artifact_count must match artifacts length" for artifact in inventory)


def test_cli_json_reports_current_inventory(capsys) -> None:
    exit_code = reporter.main(["--json"])
    streams = capsys.readouterr()
    report = json.loads(streams.out)

    assert exit_code == 0
    assert report["report_id"] == "workspace_governance_inventory"
    assert report["status"] == "passed"
    assert report["artifact_count"] >= 30
    assert report["terminal_closure_required"] is True
    assert streams.err == ""
