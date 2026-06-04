"""Purpose: verify repository-local workspace governance integrity reporting.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.report_workspace_governance_integrity.
Invariants:
  - Current witness artifacts receive deterministic SHA-256 evidence.
  - Missing files and unsafe paths produce explicit issues.
  - Integrity reports are non-terminal closure evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json

from scripts import report_workspace_governance_integrity as reporter


def test_current_integrity_passes() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    integrity = reporter.build_integrity(witness)
    report = reporter.build_integrity_report(integrity)

    assert report["status"] == "passed"
    assert report["artifact_count"] == witness["artifact_count"]
    assert report["artifact_count"] == report["hashed_count"]
    assert report["issue_count"] == 0
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True
    assert any(artifact.name == "sdlc_route_validator" and artifact.sha256 for artifact in integrity)
    assert any(artifact.path == "scripts/route_sdlc.py" and artifact.sha256 for artifact in integrity)
    assert any(artifact.path == "tests/test_validate_sdlc_route.py" and artifact.sha256 for artifact in integrity)


def test_known_artifact_digest_matches_file_bytes() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    integrity = reporter.build_integrity(witness)
    agents_record = next(artifact for artifact in integrity if artifact.path == "AGENTS.md")
    expected_digest = hashlib.sha256((reporter.WORKSPACE_ROOT / "AGENTS.md").read_bytes()).hexdigest()

    assert agents_record.sha256 == expected_digest
    assert agents_record.size_bytes == (reporter.WORKSPACE_ROOT / "AGENTS.md").stat().st_size
    assert agents_record.exists is True
    assert agents_record.issue is None


def test_missing_artifact_is_reported() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"][0]["path"] = "docs/missing-governance-integrity-artifact.json"

    integrity = reporter.build_integrity(invalid_witness)
    report = reporter.build_integrity_report(integrity)

    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1
    assert any(artifact.issue == "referenced file does not exist" for artifact in integrity)


def test_unsafe_artifact_path_is_reported() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"][0]["path"] = "../AGENTS.md"

    integrity = reporter.build_integrity(invalid_witness)
    report = reporter.build_integrity_report(integrity)

    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1
    assert any(artifact.issue == "parent traversal is not allowed" for artifact in integrity)


def test_artifact_count_mismatch_is_reported() -> None:
    witness = reporter.load_witness(reporter.DEFAULT_WITNESS_PATH)
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifact_count"] = invalid_witness["artifact_count"] + 1

    integrity = reporter.build_integrity(invalid_witness)
    report = reporter.build_integrity_report(integrity)

    assert report["status"] == "failed"
    assert report["missing_count"] == 1
    assert report["issue_count"] == 1
    assert any(artifact.issue == "artifact_count must match artifacts length" for artifact in integrity)


def test_cli_json_reports_current_integrity(capsys) -> None:
    exit_code = reporter.main(["--json"])
    streams = capsys.readouterr()
    report = json.loads(streams.out)

    assert exit_code == 0
    assert report["report_id"] == "workspace_governance_integrity"
    assert report["status"] == "passed"
    assert report["artifact_count"] == report["hashed_count"]
    assert streams.err == ""
