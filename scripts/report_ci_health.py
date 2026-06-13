#!/usr/bin/env python3
"""Report GitHub CI health for the control-plane repository.

Purpose: collect a bounded, read-only GitHub Actions and PR check summary so
failed CI is visible before merge or release work continues.
Governance scope: CI monitoring, PR readiness sensing, and mainline witness
checks.
Dependencies: Python standard library and GitHub CLI for live collection.
Invariants:
  - The evaluator is deterministic for a supplied payload.
  - Live collection is read-only and does not dispatch workflows or mutate PRs.
  - Token values, secret values, and log bodies are never printed.
  - Exit code 1 is reserved for failed or unsettled CI evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import subprocess
import sys
from typing import Any


DEFAULT_REPOSITORY = "tamirat-wubie/mullu-control-plane"
DEFAULT_BRANCH = "main"
FAILING_STATES = frozenset({"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"})
PENDING_STATES = frozenset({"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED", "EXPECTED"})
SUCCESS_STATES = frozenset({"SUCCESS", "PASSED", "COMPLETED"})


@dataclass(frozen=True)
class CiHealthFinding:
    """One bounded CI health finding."""

    severity: str
    scope: str
    title: str
    detail: str
    url: str | None = None


@dataclass(frozen=True)
class CiWorkflowRunSummary:
    """Bounded workflow run metadata retained in the CI snapshot."""

    workflow_name: str
    state: str
    head_branch: str
    head_sha: str | None
    database_id: int | None
    display_title: str
    url: str | None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serializable workflow summary."""

        return {
            "workflow_name": self.workflow_name,
            "state": self.state,
            "head_branch": self.head_branch,
            "head_sha": self.head_sha,
            "database_id": self.database_id,
            "display_title": self.display_title,
            "url": self.url,
        }


@dataclass(frozen=True)
class CiStaleFailureSummary:
    """One failed workflow on a branch without an open PR."""

    workflow_name: str
    state: str
    head_branch: str
    head_sha: str | None
    database_id: int | None
    display_title: str
    url: str | None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serializable stale failure summary."""

        return {
            "workflow_name": self.workflow_name,
            "state": self.state,
            "head_branch": self.head_branch,
            "head_sha": self.head_sha,
            "database_id": self.database_id,
            "display_title": self.display_title,
            "url": self.url,
        }


@dataclass(frozen=True)
class CiHealthReport:
    """CI health report with deterministic summary counts."""

    status: str
    repository: str
    branch: str
    open_pr_count: int
    main_workflow_count: int
    findings: tuple[CiHealthFinding, ...]
    latest_main_runs: tuple[CiWorkflowRunSummary, ...] = ()
    stale_failures: tuple[CiStaleFailureSummary, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serializable report."""

        active_failed_count = sum(1 for finding in self.findings if finding.severity == "failed")
        active_pending_count = sum(1 for finding in self.findings if finding.severity == "pending")
        active_warning_count = sum(1 for finding in self.findings if finding.severity == "warning")
        payload = {
            "schema_version": 1,
            "snapshot_type": "ci_health_snapshot",
            "status": self.status,
            "repository": self.repository,
            "branch": self.branch,
            "open_pr_count": self.open_pr_count,
            "main_workflow_count": self.main_workflow_count,
            "finding_count": len(self.findings),
            "active_failed_count": active_failed_count,
            "active_pending_count": active_pending_count,
            "active_warning_count": active_warning_count,
            "stale_failure_count": len(self.stale_failures),
            "latest_main_runs": [run.to_json() for run in self.latest_main_runs],
            "stale_failures": [failure.to_json() for failure in self.stale_failures],
            "findings": [
                {
                    "severity": finding.severity,
                    "scope": finding.scope,
                    "title": finding.title,
                    "detail": finding.detail,
                    "url": finding.url,
                }
                for finding in self.findings
            ],
            "evidence_refs": _evidence_refs(self),
        }
        payload["snapshot_id"] = _snapshot_id(payload)
        return payload


def evaluate_ci_health(
    open_pull_requests: list[dict[str, Any]],
    main_runs: list[dict[str, Any]],
    recent_runs: list[dict[str, Any]] | None = None,
    *,
    repository: str = DEFAULT_REPOSITORY,
    branch: str = DEFAULT_BRANCH,
) -> CiHealthReport:
    """Evaluate CI health from already-collected GitHub payloads."""

    findings: list[CiHealthFinding] = []
    for pull_request in open_pull_requests:
        findings.extend(_evaluate_pull_request(pull_request))
    latest_runs = _latest_runs_by_workflow(main_runs)
    for run in latest_runs:
        finding = _evaluate_main_run(run, branch)
        if finding is not None:
            findings.append(finding)
    status = "passed" if not any(f.severity in {"failed", "pending"} for f in findings) else "failed"
    stale_failures = _stale_failures(recent_runs or [], branch, open_pull_requests)
    return CiHealthReport(
        status=status,
        repository=repository,
        branch=branch,
        open_pr_count=len(open_pull_requests),
        main_workflow_count=len(latest_runs),
        findings=tuple(findings),
        latest_main_runs=tuple(_workflow_run_summary(run, branch) for run in latest_runs),
        stale_failures=stale_failures,
    )


def _evaluate_pull_request(pull_request: dict[str, Any]) -> tuple[CiHealthFinding, ...]:
    """Return findings for one open PR rollup."""

    number = pull_request.get("number", "?")
    title = str(pull_request.get("title", "")).strip() or "untitled"
    url = _optional_string(pull_request.get("url"))
    prefix = f"PR #{number}: {title}"
    findings: list[CiHealthFinding] = []

    checks = pull_request.get("statusCheckRollup") or []
    if not isinstance(checks, list):
        checks = []
    failed_checks = sorted({_check_name(check) for check in checks if _check_state(check) in FAILING_STATES})
    pending_checks = sorted({_check_name(check) for check in checks if _check_state(check) in PENDING_STATES})
    unknown_checks = sorted({_check_name(check) for check in checks if _check_state(check) == "UNKNOWN"})

    if failed_checks:
        findings.append(
            CiHealthFinding(
                severity="failed",
                scope="pull_request",
                title=f"{prefix} has failed checks",
                detail=", ".join(failed_checks[:8]),
                url=url,
            )
        )
    if pending_checks:
        findings.append(
            CiHealthFinding(
                severity="pending",
                scope="pull_request",
                title=f"{prefix} has unsettled checks",
                detail=", ".join(pending_checks[:8]),
                url=url,
            )
        )
    if unknown_checks:
        findings.append(
            CiHealthFinding(
                severity="warning",
                scope="pull_request",
                title=f"{prefix} has checks with unknown state",
                detail=", ".join(unknown_checks[:8]),
                url=url,
            )
        )
    merge_state = str(pull_request.get("mergeStateStatus") or "").upper()
    if merge_state and merge_state not in {"CLEAN", "HAS_HOOKS", "UNKNOWN"}:
        findings.append(
            CiHealthFinding(
                severity="warning",
                scope="pull_request",
                title=f"{prefix} is not merge-clean",
                detail=f"mergeStateStatus={merge_state}",
                url=url,
            )
        )
    return tuple(findings)


def _evaluate_main_run(run: dict[str, Any], branch: str) -> CiHealthFinding | None:
    """Return a finding when the latest run for one workflow is not green."""

    workflow_name = str(run.get("workflowName") or "unknown workflow")
    state = _workflow_run_state(run)
    url = _optional_string(run.get("url"))
    title = str(run.get("displayTitle") or "")
    if state in SUCCESS_STATES:
        return None
    severity = "pending" if state in PENDING_STATES else "failed"
    return CiHealthFinding(
        severity=severity,
        scope="main",
        title=f"{branch} {workflow_name} is not green",
        detail=f"state={state}; title={title}",
        url=url,
    )


def _latest_runs_by_workflow(runs: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Return the first observed run for each workflow, preserving gh order."""

    observed: set[str] = set()
    latest: list[dict[str, Any]] = []
    for run in runs:
        workflow_name = str(run.get("workflowName") or "unknown workflow")
        if workflow_name in observed:
            continue
        observed.add(workflow_name)
        latest.append(run)
    return tuple(latest)


def _latest_runs_by_branch_and_workflow(runs: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Return the first observed run for each branch/workflow pair."""

    observed: set[tuple[str, str]] = set()
    latest: list[dict[str, Any]] = []
    for run in runs:
        key = (
            str(run.get("headBranch") or ""),
            str(run.get("workflowName") or "unknown workflow"),
        )
        if key in observed:
            continue
        observed.add(key)
        latest.append(run)
    return tuple(latest)


def _stale_failures(
    recent_runs: list[dict[str, Any]],
    branch: str,
    open_pull_requests: list[dict[str, Any]],
) -> tuple[CiStaleFailureSummary, ...]:
    """Return failed latest branch runs that are not active PR or main blockers."""

    open_pr_heads = {
        str(pull_request.get("headRefName") or "")
        for pull_request in open_pull_requests
        if pull_request.get("headRefName")
    }
    stale: list[CiStaleFailureSummary] = []
    for run in _latest_runs_by_branch_and_workflow(recent_runs):
        head_branch = str(run.get("headBranch") or "")
        if not head_branch or head_branch == branch or head_branch in open_pr_heads:
            continue
        state = _workflow_run_state(run)
        if state not in FAILING_STATES:
            continue
        stale.append(_stale_failure_summary(run, head_branch, state))
    return tuple(stale)


def _workflow_run_state(run: dict[str, Any]) -> str:
    """Normalize a workflow run status/conclusion pair."""

    status = str(run.get("status") or "").upper()
    conclusion = str(run.get("conclusion") or "").upper()
    if status and status != "COMPLETED":
        return status
    if conclusion:
        return "SUCCESS" if conclusion == "SUCCESS" else conclusion
    return "UNKNOWN"


def _workflow_run_summary(run: dict[str, Any], fallback_branch: str) -> CiWorkflowRunSummary:
    """Create bounded summary metadata for one workflow run."""

    return CiWorkflowRunSummary(
        workflow_name=str(run.get("workflowName") or "unknown workflow"),
        state=_workflow_run_state(run),
        head_branch=str(run.get("headBranch") or fallback_branch),
        head_sha=_optional_string(run.get("headSha")),
        database_id=_optional_int(run.get("databaseId")),
        display_title=str(run.get("displayTitle") or ""),
        url=_optional_string(run.get("url")),
    )


def _stale_failure_summary(run: dict[str, Any], head_branch: str, state: str) -> CiStaleFailureSummary:
    """Create bounded summary metadata for one stale failed branch run."""

    return CiStaleFailureSummary(
        workflow_name=str(run.get("workflowName") or "unknown workflow"),
        state=state,
        head_branch=head_branch,
        head_sha=_optional_string(run.get("headSha")),
        database_id=_optional_int(run.get("databaseId")),
        display_title=str(run.get("displayTitle") or ""),
        url=_optional_string(run.get("url")),
    )


def _check_state(check: dict[str, Any]) -> str:
    """Normalize a PR check rollup state."""

    conclusion = str(check.get("conclusion") or "").upper()
    status = str(check.get("status") or "").upper()
    state = str(check.get("state") or "").upper()
    if conclusion:
        return "SUCCESS" if conclusion == "SUCCESS" else conclusion
    if status and status != "COMPLETED":
        return status
    if state:
        return state
    if status == "COMPLETED":
        return "UNKNOWN"
    return "UNKNOWN"


def _check_name(check: dict[str, Any]) -> str:
    """Return a stable check name."""

    name = str(check.get("name") or check.get("context") or "unnamed check")
    workflow = str(check.get("workflowName") or "")
    return f"{workflow}: {name}" if workflow else name


def _optional_string(value: object) -> str | None:
    """Return a string or None for empty values."""

    if value is None:
        return None
    text = str(value)
    return text or None


def _optional_int(value: object) -> int | None:
    """Return an integer or None for empty values."""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _evidence_refs(report: CiHealthReport) -> list[str]:
    """Return unique bounded evidence references for the snapshot."""

    refs: list[str] = []
    for run in report.latest_main_runs:
        if run.url:
            refs.append(run.url)
    for finding in report.findings:
        if finding.url:
            refs.append(finding.url)
    for failure in report.stale_failures:
        if failure.url:
            refs.append(failure.url)
    return sorted(set(refs))


def _snapshot_id(payload: dict[str, Any]) -> str:
    """Derive a stable snapshot id from bounded payload content."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"ci-health-{digest[:16]}"


def collect_ci_health_inputs(repository: str, branch: str, pr_limit: int, run_limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect read-only PR and main workflow payloads through GitHub CLI."""

    pull_requests = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repository,
            "--state",
            "open",
            "--limit",
            str(pr_limit),
            "--json",
            "number,title,url,isDraft,headRefName,mergeStateStatus,statusCheckRollup",
        ]
    )
    runs = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repository,
            "--branch",
            branch,
            "--limit",
            str(run_limit),
            "--json",
            "databaseId,displayTitle,workflowName,status,conclusion,headSha,url,createdAt",
        ]
    )
    recent_runs = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repository,
            "--limit",
            str(run_limit),
            "--json",
            "databaseId,displayTitle,workflowName,status,conclusion,headSha,headBranch,url,createdAt,event",
        ]
    )
    if not isinstance(pull_requests, list):
        raise ValueError("GitHub PR list response must be an array")
    if not isinstance(runs, list):
        raise ValueError("GitHub run list response must be an array")
    if not isinstance(recent_runs, list):
        raise ValueError("GitHub recent run list response must be an array")
    return pull_requests, runs, recent_runs


def _gh_json(args: list[str]) -> Any:
    """Run one read-only gh JSON command."""

    completed = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if completed.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {_bounded_error(completed.stderr)}")
    if not completed.stdout.strip():
        return None
    return json.loads(completed.stdout)


def _bounded_error(message: str) -> str:
    """Return a bounded, single-line error message."""

    return " ".join(message.strip().split())[:300] or "no error text"


def render_text_report(report: CiHealthReport) -> str:
    """Render a concise human-readable report."""

    lines = [
        f"CI health: {report.status}",
        f"repository: {report.repository}",
        f"branch: {report.branch}",
        f"open_pr_count: {report.open_pr_count}",
        f"main_workflow_count: {report.main_workflow_count}",
    ]
    if not report.findings:
        lines.append("findings: none")
    else:
        lines.append("findings:")
        for finding in report.findings:
            url = f" ({finding.url})" if finding.url else ""
            lines.append(f"- [{finding.severity}] {finding.scope}: {finding.title} - {finding.detail}{url}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for CI health reporting."""

    parser = argparse.ArgumentParser(description="Report bounded GitHub CI health for this repository.")
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="GitHub repository in owner/name form")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="mainline branch to inspect")
    parser.add_argument("--pr-limit", type=int, default=50, help="maximum open PRs to inspect")
    parser.add_argument("--run-limit", type=int, default=20, help="maximum mainline workflow runs to inspect")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        pull_requests, runs, recent_runs = collect_ci_health_inputs(args.repo, args.branch, args.pr_limit, args.run_limit)
        report = evaluate_ci_health(pull_requests, runs, recent_runs, repository=args.repo, branch=args.branch)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"CI health collection failed: {_bounded_error(str(exc))}\nSTATUS: failed\n")
        return 2

    if args.json:
        sys.stdout.write(json.dumps(report.to_json(), indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_text_report(report) + "\n")
    sys.stdout.write(f"STATUS: {report.status}\n")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
