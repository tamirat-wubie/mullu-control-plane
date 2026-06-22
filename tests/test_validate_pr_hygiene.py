"""Tests for the PR hygiene validator.

Purpose: prevent accidental placeholder/temp files and noisy create/delete churn
from reaching merge-ready branches.
Governance scope: source-control hygiene only; no GitHub mutation or runtime
effect authority is granted by these tests.
"""

from __future__ import annotations

import json

import pytest

from scripts.validate_pr_hygiene import PrHygieneError, main, validate_changed_files


def test_validate_pr_hygiene_accepts_small_intended_manifest() -> None:
    receipt = validate_changed_files(
        (
            "A\tscripts/validate_pr_hygiene.py",
            "A\ttests/test_validate_pr_hygiene.py",
            "A\t.github/workflows/pr-hygiene-guard.yml",
        )
    )

    assert receipt["status"] == "passed"
    assert receipt["changed_file_count"] == 3
    assert receipt["violations"] == []
    assert receipt["governance_boundary"]["source_control_hygiene_only"] is True
    assert receipt["governance_boundary"]["github_mutation_allowed"] is False
    assert receipt["governance_boundary"]["runtime_effect_allowed"] is False


def test_validate_pr_hygiene_rejects_placeholder_and_temporary_paths() -> None:
    receipt = validate_changed_files(
        (
            "A\t.tmp-should-not-exist",
            "A\ttmp/generated.txt",
            "A\tdocs/plan.bak",
            "A\tscripts/placeholder_guard.py",
        )
    )

    assert receipt["status"] == "failed"
    violation_ids = [violation["violation_id"] for violation in receipt["violations"]]
    assert violation_ids == [
        "placeholder_or_temporary_file_path",
        "placeholder_or_temporary_file_path",
        "placeholder_or_temporary_file_path",
        "placeholder_or_temporary_file_path",
    ]


def test_validate_pr_hygiene_rejects_create_delete_churn() -> None:
    receipt = validate_changed_files(
        (
            "A\tdocs/decision.md",
            "D\tdocs/decision.md",
        )
    )

    assert receipt["status"] == "failed"
    assert receipt["violations"] == [
        {
            "violation_id": "create_delete_churn_detected",
            "path": "docs/decision.md",
            "detail": "same path appears as both added and deleted in the change manifest",
        }
    ]


def test_validate_pr_hygiene_rejects_too_many_files() -> None:
    receipt = validate_changed_files((f"M\tdocs/file_{index}.md" for index in range(3)), max_changed_files=2)

    assert receipt["status"] == "failed"
    assert receipt["violations"][0]["violation_id"] == "changed_file_count_exceeds_limit"


def test_validate_pr_hygiene_rejects_unsafe_paths() -> None:
    with pytest.raises(PrHygieneError):
        validate_changed_files(("A\t../escape.txt",))

    with pytest.raises(PrHygieneError):
        validate_changed_files(("A",))


def test_validate_pr_hygiene_cli_emits_json_receipt(tmp_path, capsys) -> None:  # noqa: ANN001
    manifest = tmp_path / "changed-files.txt"
    manifest.write_text("A\tscripts/validate_pr_hygiene.py\n", encoding="utf-8")

    exit_code = main(("--changed-files", str(manifest), "--json"))
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["receipt_id"] == "pr_hygiene_guard_receipt_v1"
    assert output["status"] == "passed"
    assert output["changed_files"] == ["scripts/validate_pr_hygiene.py"]
