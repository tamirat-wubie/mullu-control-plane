"""Tests for engineering puzzle universality witness validation.

Purpose: verify the engineering puzzle empirical witness set is encoded and
replayed through the runtime filter-stack contract.
Governance scope: local witness-set validation for survival-before-optimization
universality only.
Dependencies: scripts.validate_engineering_puzzle_universality_witness and the
checked-in example witness set.
Invariants: valid witnesses pass, stale expected levels fail, missing evidence
fails, and CLI reports are deterministic JSON artifacts.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_engineering_puzzle_universality_witness import (
    DEFAULT_WITNESS_PATH,
    REPO_ROOT,
    validate_witness_set,
)


def test_engineering_puzzle_universality_witness_set_passes() -> None:
    report = validate_witness_set(DEFAULT_WITNESS_PATH)

    assert report.passed is True
    assert report.case_count == 5
    assert "software" in report.domains
    assert "runtime_operations" in report.domains
    assert report.errors == ()


def test_engineering_puzzle_witness_rejects_stale_expected_level(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_WITNESS_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(payload)
    mutated["cases"][0]["expected_failed_level"] = "L5_optimization"
    witness_path = tmp_path / "stale_engineering_puzzle_witness.json"
    witness_path.write_text(json.dumps(mutated, indent=2), encoding="utf-8")

    report = validate_witness_set(witness_path)

    assert report.passed is False
    assert report.case_count == 5
    assert any("expected_failed_level must be L2_survival" in error for error in report.errors)
    assert report.report_hash.startswith("sha256:")


def test_engineering_puzzle_witness_requires_observation_evidence(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_WITNESS_PATH.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(payload)
    mutated["cases"][1]["observation_evidence"] = []
    witness_path = tmp_path / "missing_observation_witness.json"
    witness_path.write_text(json.dumps(mutated, indent=2), encoding="utf-8")

    report = validate_witness_set(witness_path)

    assert report.passed is False
    assert report.case_count == 5
    assert any("observation_evidence must be a non-empty text list" in error for error in report.errors)
    assert "physical_engineering" in report.domains


def test_engineering_puzzle_witness_validator_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "engineering_puzzle_universality_witness.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_engineering_puzzle_universality_witness.py"),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert completed.returncode == 0
    assert output_path.exists()
    assert payload["passed"] is True
    assert payload["case_count"] == 5
    assert payload["report_hash"].startswith("sha256:")
