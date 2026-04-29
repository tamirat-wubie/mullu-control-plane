#!/usr/bin/env python3
"""Collect a bounded SCIM directory export.

Purpose: fetch SCIM Users and Groups resources from a live directory endpoint
and write a local export consumed by scripts/scim_authority_directory_adapter.py.
Governance scope: source evidence, bounded pagination, credential-safe errors,
and separation between identity evidence collection and authority mapping.
Dependencies: standard-library HTTP client, JSON, argparse, pathlib.
Invariants:
  - Bearer tokens are never printed or written to the export.
  - Only Users and Groups are collected.
  - Pagination terminates when totalResults is reached or no resources remain.
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

DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "scim_directory_export.json"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
MAX_PAGES = 100


@dataclass(frozen=True, slots=True)
class ScimCollectionSummary:
    """Bounded summary for one SCIM export collection."""

    source_ref: str
    collected_at: str
    user_count: int
    group_count: int
    page_count: int


def collect_scim_directory_export(
    *,
    base_url: str,
    bearer_token: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    clock: Any | None = None,
) -> dict[str, Any]:
    """Collect SCIM Users and Groups into one local export payload."""
    normalized_base = base_url.rstrip("/")
    parsed_base = urllib.parse.urlparse(normalized_base)
    if not normalized_base:
        raise ValueError("base_url is required")
    if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
        raise ValueError("base_url must be http or https")
    normalized_token = bearer_token.strip()
    if not normalized_token:
        raise ValueError("bearer_token is required")
    bounded_page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    collected_at = (clock or _utc_now)()

    users, user_pages = _collect_resource_pages(
        base_url=normalized_base,
        resource_path="Users",
        bearer_token=normalized_token,
        page_size=bounded_page_size,
    )
    groups, group_pages = _collect_resource_pages(
        base_url=normalized_base,
        resource_path="Groups",
        bearer_token=normalized_token,
        page_size=bounded_page_size,
    )
    summary = ScimCollectionSummary(
        source_ref=f"scim://{urllib.parse.urlparse(normalized_base).netloc or 'directory'}/export/{collected_at}",
        collected_at=collected_at,
        user_count=len(users),
        group_count=len(groups),
        page_count=user_pages + group_pages,
    )
    return {
        "source_system": "scim_api",
        "source_ref": summary.source_ref,
        "collected_at": summary.collected_at,
        "summary": asdict(summary),
        "Users": tuple(users),
        "Groups": tuple(groups),
    }


def write_scim_export(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one SCIM export JSON document."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _collect_resource_pages(
    *,
    base_url: str,
    resource_path: str,
    bearer_token: str,
    page_size: int,
) -> tuple[tuple[dict[str, Any], ...], int]:
    resources: list[dict[str, Any]] = []
    start_index = 1
    page_count = 0
    while page_count < MAX_PAGES:
        page_count += 1
        url = _resource_page_url(base_url, resource_path, start_index=start_index, count=page_size)
        payload = _get_json(url, bearer_token=bearer_token)
        page_resources = payload.get("Resources", ())
        if not isinstance(page_resources, list):
            raise ValueError(f"SCIM {resource_path} response Resources must be list")
        if not all(isinstance(item, dict) for item in page_resources):
            raise ValueError(f"SCIM {resource_path} response Resources entries must be objects")
        resources.extend(dict(item) for item in page_resources)
        total_results = _bounded_int(payload.get("totalResults", len(resources)))
        items_per_page = _bounded_int(payload.get("itemsPerPage", len(page_resources)))
        if not page_resources or len(resources) >= total_results:
            return tuple(resources), page_count
        start_index += max(items_per_page, len(page_resources), 1)
    raise ValueError(f"SCIM {resource_path} pagination exceeded page limit")


def _resource_page_url(base_url: str, resource_path: str, *, start_index: int, count: int) -> str:
    query = urllib.parse.urlencode({"startIndex": start_index, "count": count})
    return f"{base_url}/{resource_path}?{query}"


def _get_json(url: str, *, bearer_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/scim+json, application/json",
            "Authorization": f"Bearer {bearer_token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"SCIM endpoint returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError("SCIM endpoint unavailable") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("SCIM endpoint returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("SCIM endpoint JSON root must be mapping")
    return payload


def _bounded_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("SCIM pagination field must be integer") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the SCIM export collector CLI contract."""
    parser = argparse.ArgumentParser(description="Collect SCIM Users and Groups into a local export JSON.")
    parser.add_argument("--base-url", required=True, help="SCIM base URL, for example https://example.com/scim/v2")
    parser.add_argument("--bearer-token", default=os.environ.get("MULLU_SCIM_BEARER_TOKEN", ""))
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for live SCIM export collection."""
    args = parse_args(argv)
    try:
        payload = collect_scim_directory_export(
            base_url=args.base_url,
            bearer_token=args.bearer_token,
            page_size=args.page_size,
        )
        written = write_scim_export(payload, args.output)
        print(f"SCIM directory export written: {written}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"SCIM directory export failed: {_bounded_error_reason(exc)}", file=sys.stderr)
        return 2


def _bounded_error_reason(exc: OSError | ValueError) -> str:
    if isinstance(exc, OSError):
        return "output_unavailable"
    return str(exc) or "invalid_scim_directory_export"


if __name__ == "__main__":
    raise SystemExit(main())
