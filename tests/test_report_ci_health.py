"""Tests for the read-only CI health reporter.

Purpose: prove CI health classification works without live GitHub access.
Governance scope: PR check triage, mainline workflow sensing, and CLI output.
Dependencies: scripts.report_ci_health.
Invariants: tests use synthetic payloads only and never call GitHub.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import report_ci_health as reporter  # noqa: E402


def _success_main_runs() -> list[dict[str, object]]:
    return [
        {
            "workflowName": "CI - Build Verification",
            "status": "completed",
            "conclusion": "success",
            "displayTitle": "green main",
            "url": "https://example.invalid/runs/1",
        },
        {
            "workflowName": "GitHub App Token Format Boundary",
            "status": "completed",
            "conclusion": "success",
            "displayTitle": "green token boundary",
            "url": "https://example.invalid/runs/2",
        },
    ]


def test_clean_state_passes_without_findings() -> None:
    report = reporter.evaluate_ci_health([], _success_main_runs(), repository="owner/repo", branch="main")
    payload = report.to_json()

    assert report.status == "passed"
    assert report.open_pr_count == 0
    assert report.main_workflow_count == 2
    assert report.findings == ()
    assert payload["snapshot_type"] == "ci_health_snapshot"
    assert payload["snapshot_id"].startswith("ci-health-")
    assert payload["latest_main_runs"][0]["workflow_name"] == "CI - Build Verification"


def test_failed_open_pr_check_blocks_health() -> None:
    pull_requests = [
        {
            "number": 42,
            "title": "governance change",
            "url": "https://example.invalid/pull/42",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [
                {
                    "name": "SDLC Governance Gate",
                    "workflowName": "CI - Build Verification",
                    "status": "COMPLETED",
                    "conclusion": "FAILURE",
                },
                {
                    "name": "Rust Tests",
                    "workflowName": "CI - Build Verification",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                },
            ],
        }
    ]

    report = reporter.evaluate_ci_health(pull_requests, _success_main_runs())

    assert report.status == "failed"
    assert len(report.findings) == 1
    assert report.findings[0].severity == "failed"
    assert "SDLC Governance Gate" in report.findings[0].detail


def test_pending_pr_check_blocks_health_before_claiming_green() -> None:
    pull_requests = [
        {
            "number": 7,
            "title": "runtime witness",
            "url": "https://example.invalid/pull/7",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [
                {
                    "name": "Build Verification",
                    "workflowName": "CI - Build Verification",
                    "status": "IN_PROGRESS",
                    "conclusion": "",
                },
                {
                    "name": "Build Verification",
                    "workflowName": "CI - Build Verification",
                    "status": "IN_PROGRESS",
                    "conclusion": "",
                }
            ],
        }
    ]

    report = reporter.evaluate_ci_health(pull_requests, _success_main_runs())

    assert report.status == "failed"
    assert report.findings[0].severity == "pending"
    assert "unsettled checks" in report.findings[0].title
    assert report.findings[0].detail == "CI - Build Verification: Build Verification"


def test_latest_main_run_per_workflow_suppresses_stale_older_failure() -> None:
    runs = [
        {
            "workflowName": "CI - Build Verification",
            "status": "completed",
            "conclusion": "success",
            "displayTitle": "new green run",
            "url": "https://example.invalid/runs/new",
        },
        {
            "workflowName": "CI - Build Verification",
            "status": "completed",
            "conclusion": "failure",
            "displayTitle": "old failed run",
            "url": "https://example.invalid/runs/old",
        },
    ]

    report = reporter.evaluate_ci_health([], runs)

    assert report.status == "passed"
    assert report.main_workflow_count == 1
    assert report.findings == ()


def test_stale_branch_failure_is_recorded_but_does_not_block_health() -> None:
    recent_runs = [
        {
            "workflowName": "CI - Build Verification",
            "headBranch": "closed/superseded",
            "status": "completed",
            "conclusion": "failure",
            "displayTitle": "old closed branch",
            "databaseId": 99,
            "url": "https://example.invalid/runs/stale",
        },
        {
            "workflowName": "CI - Build Verification",
            "headBranch": "main",
            "status": "completed",
            "conclusion": "success",
            "displayTitle": "green main",
            "databaseId": 100,
            "url": "https://example.invalid/runs/main",
        },
    ]

    report = reporter.evaluate_ci_health([], _success_main_runs(), recent_runs)
    payload = report.to_json()

    assert report.status == "passed"
    assert len(report.stale_failures) == 1
    assert payload["stale_failure_count"] == 1
    assert payload["stale_failures"][0]["head_branch"] == "closed/superseded"
    assert "https://example.invalid/runs/stale" in payload["evidence_refs"]


def test_open_pr_branch_failure_remains_active_not_stale() -> None:
    pull_requests = [
        {
            "number": 9,
            "title": "active branch",
            "headRefName": "active/pr",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [],
        }
    ]
    recent_runs = [
        {
            "workflowName": "CI - Build Verification",
            "headBranch": "active/pr",
            "status": "completed",
            "conclusion": "failure",
            "displayTitle": "active failed branch",
            "databaseId": 101,
            "url": "https://example.invalid/runs/active",
        }
    ]

    report = reporter.evaluate_ci_health(pull_requests, _success_main_runs(), recent_runs)

    assert report.status == "passed"
    assert report.stale_failures == ()
    assert report.to_json()["stale_failure_count"] == 0


def test_json_snapshot_matches_public_schema() -> None:
    schema = json.loads((REPO_ROOT / "schemas" / "ci_health_snapshot.schema.json").read_text(encoding="utf-8"))
    report = reporter.evaluate_ci_health([], _success_main_runs(), repository="owner/repo", branch="main")

    Draft202012Validator(schema).validate(report.to_json())


def test_cli_json_and_text_use_injected_collector(monkeypatch, capsys) -> None:
    def fake_collect(repository: str, branch: str, pr_limit: int, run_limit: int):
        assert repository == "owner/repo"
        assert branch == "main"
        assert pr_limit == 3
        assert run_limit == 4
        return [], _success_main_runs(), []

    monkeypatch.setattr(reporter, "collect_ci_health_inputs", fake_collect)

    json_exit = reporter.main(["--repo", "owner/repo", "--branch", "main", "--pr-limit", "3", "--run-limit", "4", "--json"])
    json_output = capsys.readouterr().out
    payload = json.loads(json_output.split("\nSTATUS:")[0])
    text_exit = reporter.main(["--repo", "owner/repo", "--branch", "main", "--pr-limit", "3", "--run-limit", "4"])
    text_output = capsys.readouterr().out

    assert json_exit == 0
    assert payload["status"] == "passed"
    assert payload["schema_version"] == 1
    assert payload["finding_count"] == 0
    assert payload["stale_failure_count"] == 0
    assert text_exit == 0
    assert "findings: none" in text_output
    assert "STATUS: passed" in text_output
