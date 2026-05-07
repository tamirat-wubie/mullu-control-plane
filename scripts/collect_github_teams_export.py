#!/usr/bin/env python3
"""Collect a bounded GitHub organization teams export.

Purpose: fetch GitHub organization members, teams, and team memberships into a
local export consumed by scripts/github_teams_authority_directory_adapter.py.
Governance scope: source evidence, bounded pagination, credential-safe errors,
and separation between GitHub identity evidence and authority mapping.
Dependencies: standard-library HTTP client, JSON, argparse, pathlib.
Invariants:
  - GitHub tokens are never printed or written to the export.
  - Only organization members, teams, and team memberships are collected.
  - Pagination terminates on short/empty pages or a hard page limit.
  - The collector writes identity evidence only; it never creates authority.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API_BASE = "https://api.github.com"
DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "github_teams_export.json"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100
MAX_PAGES = 100


@dataclass(frozen=True, slots=True)
class GitHubTeamsCollectionSummary:
    """Bounded summary for one GitHub teams export collection."""

    source_ref: str
    collected_at: str
    organization: str
    member_count: int
    team_count: int
    page_count: int


def collect_github_teams_export(
    *,
    organization: str,
    token: str,
    api_base: str = DEFAULT_API_BASE,
    page_size: int = DEFAULT_PAGE_SIZE,
    clock: Any | None = None,
) -> dict[str, Any]:
    """Collect GitHub organization members and teams into one export payload."""
    org = organization.strip()
    if not org:
        raise ValueError("organization is required")
    normalized_token = token.strip()
    if not normalized_token:
        raise ValueError("github token is required")
    normalized_api_base = api_base.rstrip("/")
    parsed_base = urllib.parse.urlparse(normalized_api_base)
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise ValueError("api_base must be http or https")
    bounded_page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    collected_at = (clock or _utc_now)()

    members, member_pages = _collect_list_pages(
        url_template=f"{normalized_api_base}/orgs/{urllib.parse.quote(org)}/members",
        token=normalized_token,
        page_size=bounded_page_size,
        required_login_label="GitHub member",
    )
    teams_raw, team_pages = _collect_list_pages(
        url_template=f"{normalized_api_base}/orgs/{urllib.parse.quote(org)}/teams",
        token=normalized_token,
        page_size=bounded_page_size,
    )
    teams: list[dict[str, Any]] = []
    membership_pages = 0
    for team in teams_raw:
        slug = str(team.get("slug", "")).strip()
        if not slug:
            raise ValueError("GitHub team response requires slug")
        team_members, pages = _collect_list_pages(
            url_template=(
                f"{normalized_api_base}/orgs/{urllib.parse.quote(org)}/teams/"
                f"{urllib.parse.quote(slug)}/members"
            ),
            token=normalized_token,
            page_size=bounded_page_size,
            required_login_label="GitHub team member",
        )
        membership_pages += pages
        teams.append({
            "slug": slug,
            "name": str(team.get("name", slug)),
            "id": team.get("id", ""),
            "privacy": str(team.get("privacy", "")),
            "members": _github_member_logins(team_members),
        })
    summary = GitHubTeamsCollectionSummary(
        source_ref=f"github://{org}/teams/export/{collected_at}",
        collected_at=collected_at,
        organization=org,
        member_count=len(members),
        team_count=len(teams),
        page_count=member_pages + team_pages + membership_pages,
    )
    return {
        "source_system": "github_api",
        "source_ref": summary.source_ref,
        "collected_at": summary.collected_at,
        "organization": org,
        "summary": asdict(summary),
        "members": tuple({
            "login": str(member["login"]),
            "name": str(member.get("name", member["login"])),
            "id": member.get("id", ""),
        } for member in _github_member_records(members)),
        "teams": tuple(teams),
    }


def write_github_teams_export(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one GitHub teams export JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _collect_list_pages(
    *,
    url_template: str,
    token: str,
    page_size: int,
    required_login_label: str = "",
) -> tuple[tuple[dict[str, Any], ...], int]:
    records: list[dict[str, Any]] = []
    page = 1
    page_count = 0
    while page_count < MAX_PAGES:
        page_count += 1
        url = _page_url(url_template, page=page, per_page=page_size)
        payload = _get_json(url, token=token)
        if not isinstance(payload, list):
            raise ValueError("GitHub list endpoint response must be array")
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("GitHub list endpoint entries must be objects")
        if required_login_label:
            _require_logins(payload, required_login_label)
        records.extend(dict(item) for item in payload)
        if len(payload) < page_size:
            return tuple(records), page_count
        page += 1
    raise ValueError("GitHub pagination exceeded page limit")


def _page_url(url_template: str, *, page: int, per_page: int) -> str:
    query = urllib.parse.urlencode({"per_page": per_page, "page": page})
    return f"{url_template}?{query}"


def _require_logins(records: list[dict[str, Any]], label: str) -> None:
    for index, record in enumerate(records):
        if not str(record.get("login", "")).strip():
            raise ValueError(f"{label} at index {index} requires login")


def _get_json(url: str, *, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GitHub endpoint returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError("GitHub endpoint unavailable") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub endpoint returned invalid JSON") from exc


def _github_member_records(raw_records: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    accepted: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not str(record.get("login", "")).strip():
            raise ValueError(f"GitHub member at index {index} requires login")
        accepted.append(dict(record))
    return tuple(accepted)


def _github_member_logins(raw_records: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    logins: list[str] = []
    for index, record in enumerate(raw_records):
        login = str(record.get("login", "")).strip()
        if not login:
            raise ValueError(f"GitHub team member at index {index} requires login")
        logins.append(login)
    return tuple(logins)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the GitHub teams export collector CLI contract."""
    parser = argparse.ArgumentParser(description="Collect GitHub organization members and teams into a local export JSON.")
    parser.add_argument("--organization", required=True)
    parser.add_argument("--token", default=os.environ.get("MULLU_GITHUB_TOKEN", ""))
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for live GitHub teams export collection."""
    args = parse_args(argv)
    try:
        payload = collect_github_teams_export(
            organization=args.organization,
            token=args.token,
            api_base=args.api_base,
            page_size=args.page_size,
        )
        written = write_github_teams_export(payload, args.output)
        print(f"GitHub teams export written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"GitHub teams export failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "output_unavailable"
    message = str(exc)
    if message.startswith("GitHub endpoint returned HTTP "):
        return message
    if message in {
        "GitHub endpoint unavailable",
        "GitHub endpoint returned invalid JSON",
    }:
        return message
    if message.startswith("GitHub team member at index ") and message.endswith(" requires login"):
        return message
    if message.startswith("GitHub member at index ") and message.endswith(" requires login"):
        return message
    return "invalid_github_teams_export"


if __name__ == "__main__":
    raise SystemExit(main())
