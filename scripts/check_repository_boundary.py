"""Purpose: verify that full-platform work is running in the canonical repository checkout.

Governance scope: repository identity, local checkout role, deployment extraction detection, and push-safety evidence.
Dependencies: pathlib, subprocess, argparse, json.
Invariants: the guard is read-only, never rewrites Git configuration, and never prints secrets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

CANONICAL_REPO = "tamirat-wubie/mullu-control-plane"
DEPLOYMENT_EXTRACTION_REPO = "mullusi/mullusi-control-plane"
CANONICAL_REQUIRED_PATHS = ("gateway", "governance", "capabilities", "mcoi", "maf")
EXTRACTION_INDICATOR_PATHS = ("apps/api", "apps/dashboard")

RepositoryBoundary = Literal["canonical", "deployment_extraction", "unknown"]


@dataclass(frozen=True, slots=True)
class RepositoryBoundaryReport:
    """Input contract: repository facts. Output contract: bounded boundary report. Error contract: none."""

    boundary: RepositoryBoundary
    root: str
    origin: str
    canonical_repo: str
    deployment_extraction_repo: str
    missing_canonical_paths: tuple[str, ...]
    extraction_indicators: tuple[str, ...]
    push_allowed_for_full_platform: bool
    required_action: str


def normalize_remote_url(remote_url: str) -> str:
    """Input contract: Git remote URL. Output contract: owner/repo slug if recognized. Error contract: none."""

    normalized = remote_url.strip().removesuffix(".git")
    for prefix in ("https://github.com/", "git@github.com:"):
        if normalized.startswith(prefix):
            return normalized.removeprefix(prefix)
    return normalized


def read_origin_url(root: Path) -> str:
    """Input contract: repository root. Output contract: origin URL or empty string. Error contract: none."""

    completed = subprocess.run(
        ("git", "remote", "get-url", "origin"),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def read_remote_urls(root: Path) -> tuple[str, ...]:
    """Input contract: repository root. Output contract: unique fetch URLs. Error contract: none."""

    completed = subprocess.run(
        ("git", "remote", "-v"),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ()

    remote_urls: list[str] = []
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] != "(fetch)":
            continue
        remote_url = parts[1]
        if remote_url not in remote_urls:
            remote_urls.append(remote_url)
    return tuple(remote_urls)


def classify_repository(
    root: Path, remote_urls: str | Sequence[str]
) -> RepositoryBoundaryReport:
    """Input contract: root and remote URL evidence. Output contract: boundary report."""

    if isinstance(remote_urls, str):
        remote_url_evidence = (remote_urls,)
    else:
        remote_url_evidence = tuple(remote_urls)
    remote_slugs = {normalize_remote_url(remote_url) for remote_url in remote_url_evidence}
    missing_canonical_paths = tuple(
        relative_path
        for relative_path in CANONICAL_REQUIRED_PATHS
        if not (root / relative_path).exists()
    )
    extraction_indicators = tuple(
        relative_path
        for relative_path in EXTRACTION_INDICATOR_PATHS
        if (root / relative_path).exists()
    )

    if CANONICAL_REPO in remote_slugs and not missing_canonical_paths:
        boundary: RepositoryBoundary = "canonical"
        required_action = "Continue full-platform work in this checkout."
    elif DEPLOYMENT_EXTRACTION_REPO in remote_slugs or extraction_indicators:
        boundary = "deployment_extraction"
        required_action = (
            "Stop full-platform work here. Switch to the canonical checkout before pushing."
        )
    else:
        boundary = "unknown"
        required_action = "Inspect remotes and top-level paths before pushing."

    return RepositoryBoundaryReport(
        boundary=boundary,
        root=str(root),
        origin="\n".join(remote_url_evidence),
        canonical_repo=CANONICAL_REPO,
        deployment_extraction_repo=DEPLOYMENT_EXTRACTION_REPO,
        missing_canonical_paths=missing_canonical_paths,
        extraction_indicators=extraction_indicators,
        push_allowed_for_full_platform=boundary == "canonical",
        required_action=required_action,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the repository boundary guard and return a deterministic exit code."""

    parser = argparse.ArgumentParser(description="Check the Mullusi repository boundary.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-noncanonical", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    remote_urls = read_remote_urls(root)
    if not remote_urls:
        remote_urls = (read_origin_url(root),)
    report = classify_repository(root, remote_urls)
    payload = {
        "repository_boundary": report.boundary,
        "root": report.root,
        "origin": report.origin,
        "canonical_repo": report.canonical_repo,
        "deployment_extraction_repo": report.deployment_extraction_repo,
        "missing_canonical_paths": list(report.missing_canonical_paths),
        "extraction_indicators": list(report.extraction_indicators),
        "push_allowed_for_full_platform": report.push_allowed_for_full_platform,
        "required_action": report.required_action,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"repository_boundary={report.boundary}")
        print(f"canonical_repo={report.canonical_repo}")
        print(f"origin={report.origin}")
        print(f"push_allowed_for_full_platform={str(report.push_allowed_for_full_platform).lower()}")
        print(f"required_action={report.required_action}")

    if report.boundary == "canonical" or args.allow_noncanonical:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
