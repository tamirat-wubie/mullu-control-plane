#!/usr/bin/env python3
"""Generate local-only public CI window operator commands.

Purpose: produce an auditable command packet for temporary public GitHub
Actions windows without mutating repository visibility.
Governance scope: Foundation Mode source-control visibility, public CI
window evidence, manual operator execution boundary, and no-execute safety.
Dependencies: Python standard library and GitHub CLI command conventions.
Invariants:
  - This script never executes generated commands.
  - Public visibility is not public readiness.
  - Visibility mutation commands are marked live_effect_possible.
  - No raw secrets or credentials are accepted or emitted.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
import sys
from typing import Any


EXPECTED_REPO = "tamirat-wubie/mullu-control-plane"
GENERATOR_ID = "foundation_public_ci_window_operator_commands.v1"
BLOCKED_CLAIMS = (
    "public readiness",
    "public launch",
    "customer access",
    "production deployment",
    "legal filing",
    "fundraising readiness",
    "raw secret exposure",
)
SECRET_SHAPED_FRAGMENTS = (
    "-----begin",
    "private key",
    "access_token",
    "refresh_token",
    "client_secret",
    "github_token",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
)


@dataclass(frozen=True)
class CommandStep:
    """One generated operator command with explicit execution boundary."""

    step_id: str
    phase: str
    command: str
    purpose: str
    live_effect_possible: bool
    operator_execution_required: bool


def _contains_secret_shaped_text(values: tuple[str, ...]) -> bool:
    text = json.dumps(values, sort_keys=True).casefold()
    return any(fragment in text for fragment in SECRET_SHAPED_FRAGMENTS)


def _is_hex_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _pull_request_number(value: str) -> str | None:
    match = re.fullmatch(r"https://github\.com/tamirat-wubie/mullu-control-plane/pull/([0-9]+)|([0-9]+)", value)
    if match is None:
        return None
    return match.group(1) or match.group(2)


def _is_branch_name(value: str) -> bool:
    return bool(value.strip()) and not value.startswith("-") and ".." not in value and any(char.isalnum() for char in value)


def _window_date(now: datetime) -> str:
    observed = now.astimezone(timezone.utc)
    return observed.strftime("%Y%m%d")


def build_public_ci_window_operator_packet(
    *,
    pull_request: str,
    branch: str,
    head_sha: str,
    observed_at: datetime | None = None,
    repo: str = EXPECTED_REPO,
) -> dict[str, Any]:
    """Build a no-execute public CI window command packet."""

    observed_at = observed_at or datetime.now(timezone.utc)
    pr_number = _pull_request_number(pull_request)
    if pr_number is None:
        raise ValueError("pull_request must be a repository PR number or URL")
    if repo != EXPECTED_REPO:
        raise ValueError(f"repo must be {EXPECTED_REPO}")
    if not _is_branch_name(branch):
        raise ValueError("branch must be a non-empty branch name")
    if not _is_hex_sha(head_sha):
        raise ValueError("head_sha must be a 40-character lowercase hex SHA")
    if _contains_secret_shaped_text((pull_request, branch, head_sha, repo)):
        raise ValueError("inputs must not contain raw secret-shaped text")

    pr_url = f"https://github.com/{repo}/pull/{pr_number}"
    window_id = f"foundation_public_ci_window.{_window_date(observed_at)}.pr{pr_number}"
    receipt_path = f".change_assurance/public-ci-window-{pr_number}-receipt.json"
    steps = (
        CommandStep(
            "01_preflight_public_surface",
            "pre-window",
            "python scripts/validate_public_repository_surface.py --local-only",
            "Validate public-safe repository surface before any visibility change.",
            False,
            False,
        ),
        CommandStep(
            "02_preflight_proprietary_boundary",
            "pre-window",
            "python scripts/validate_proprietary_boundary.py",
            "Validate proprietary boundary before any visibility change.",
            False,
            False,
        ),
        CommandStep(
            "03_preflight_release_status",
            "pre-window",
            "python scripts/validate_release_status.py",
            "Confirm no release or public-readiness claim is implied by the window.",
            False,
            False,
        ),
        CommandStep(
            "04_open_visibility_manual",
            "open-window",
            f"gh repo edit {repo} --visibility public",
            "Manual operator command to open temporary public visibility for GitHub Actions only.",
            True,
            True,
        ),
        CommandStep(
            "05_observe_pr_checks",
            "execution-window",
            f"gh pr checks {pr_number}",
            "Observe PR checks created during the public CI window.",
            False,
            False,
        ),
        CommandStep(
            "06_observe_ci_health",
            "execution-window",
            f"python scripts/report_ci_health.py --repo {repo} --branch {branch} --json",
            "Record CI health for the branch under verification.",
            False,
            False,
        ),
        CommandStep(
            "07_close_visibility_manual",
            "close-window",
            f"gh repo edit {repo} --visibility private",
            "Manual operator command to restore private visibility after CI evidence is captured.",
            True,
            True,
        ),
        CommandStep(
            "08_verify_private_surface",
            "post-window receipt",
            "python scripts/validate_public_repository_surface.py --local-only",
            "Re-check local public-safe surface after visibility restoration.",
            False,
            False,
        ),
    )
    return {
        "generator_id": GENERATOR_ID,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "no_execute": True,
        "repo": repo,
        "pull_request": pr_url,
        "branch": branch,
        "head_sha": head_sha,
        "window_id": window_id,
        "receipt_path": receipt_path,
        "blocked_claims": list(BLOCKED_CLAIMS),
        "commands": [asdict(step) for step in steps],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate public CI window operator command packet.")
    parser.add_argument("--pull-request", required=True, help="Repository PR number or URL.")
    parser.add_argument("--branch", required=True, help="Branch under CI verification.")
    parser.add_argument("--head-sha", required=True, help="40-character lowercase commit SHA.")
    args = parser.parse_args(argv)

    try:
        packet = build_public_ci_window_operator_packet(
            pull_request=args.pull_request,
            branch=args.branch,
            head_sha=args.head_sha,
        )
    except ValueError as exc:
        print(f"[FAIL] public_ci_window_operator_commands: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    print(json.dumps(packet, indent=2, sort_keys=True))
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
