"""GitHub teams export collector tests.

Purpose: verify live GitHub organization team collection without network access.
Governance scope: bounded pagination, token handling, JSON persistence, and
credential-safe failure reporting.
"""

from __future__ import annotations

import json
from typing import Any
import urllib.error

from scripts.collect_github_teams_export import (
    collect_github_teams_export,
    main,
    write_github_teams_export,
)


class StubHttpResponse:
    """Context-managed urllib response fixture."""

    def __init__(self, *, payload: Any) -> None:
        self._body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_collect_github_teams_export_collects_members_teams_and_memberships(monkeypatch) -> None:
    seen_authorization: list[str] = []

    def fake_urlopen(request, timeout):
        seen_authorization.append(request.headers["Authorization"])
        url = request.full_url
        if url.endswith("/orgs/mullusi/members?per_page=1&page=1"):
            return StubHttpResponse(payload=[{"login": "finance-manager", "name": "Finance Manager"}])
        if url.endswith("/orgs/mullusi/members?per_page=1&page=2"):
            return StubHttpResponse(payload=[])
        if url.endswith("/orgs/mullusi/teams?per_page=1&page=1"):
            return StubHttpResponse(payload=[{"slug": "finance-ops", "name": "Finance Ops"}])
        if url.endswith("/orgs/mullusi/teams?per_page=1&page=2"):
            return StubHttpResponse(payload=[])
        if url.endswith("/orgs/mullusi/teams/finance-ops/members?per_page=1&page=1"):
            return StubHttpResponse(payload=[{"login": "finance-manager"}])
        if url.endswith("/orgs/mullusi/teams/finance-ops/members?per_page=1&page=2"):
            return StubHttpResponse(payload=[])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = collect_github_teams_export(
        organization="mullusi",
        token=" secret-token ",
        api_base="https://api.github.test",
        page_size=1,
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    assert payload["source_system"] == "github_api"
    assert payload["source_ref"] == "github://mullusi/teams/export/2026-04-29T12:00:00+00:00"
    assert payload["members"][0]["login"] == "finance-manager"
    assert payload["teams"][0]["slug"] == "finance-ops"
    assert payload["teams"][0]["members"] == ("finance-manager",)
    assert payload["summary"]["page_count"] == 6
    assert seen_authorization == ["Bearer secret-token"] * 6


def test_collect_github_teams_export_rejects_non_http_api_base() -> None:
    try:
        collect_github_teams_export(
            organization="mullusi",
            token="secret-token",
            api_base="file:///tmp/github",
            clock=lambda: "2026-04-29T12:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "api_base must be http or https"
        assert "file" not in str(exc)
        assert "tmp" not in str(exc)
    else:
        raise AssertionError("expected non-http GitHub API base to be rejected")


def test_collect_github_teams_export_rejects_member_without_login(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        url = request.full_url
        if url.endswith("/orgs/mullusi/members?per_page=1&page=1"):
            return StubHttpResponse(payload=[{"login": "finance-manager"}])
        if url.endswith("/orgs/mullusi/members?per_page=1&page=2"):
            return StubHttpResponse(payload=[])
        if url.endswith("/orgs/mullusi/teams?per_page=1&page=1"):
            return StubHttpResponse(payload=[{"slug": "finance-ops"}])
        if url.endswith("/orgs/mullusi/teams?per_page=1&page=2"):
            return StubHttpResponse(payload=[])
        if url.endswith("/orgs/mullusi/teams/finance-ops/members?per_page=1&page=1"):
            return StubHttpResponse(payload=[{"id": "missing-login"}])
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    try:
        collect_github_teams_export(
            organization="mullusi",
            token="secret-token",
            api_base="https://api.github.test",
            page_size=1,
            clock=lambda: "2026-04-29T12:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "GitHub team member at index 0 requires login"
        assert "missing-login" not in str(exc)
        assert "secret-token" not in str(exc)
    else:
        raise AssertionError("expected GitHub team member without login to be rejected")


def test_collect_github_teams_export_writes_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_empty_org)
    payload = collect_github_teams_export(
        organization="mullusi",
        token="secret-token",
        api_base="https://api.github.test",
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    written = write_github_teams_export(payload, tmp_path / "github-teams.json")
    loaded = json.loads(written.read_text(encoding="utf-8"))

    assert written.name == "github-teams.json"
    assert loaded["summary"]["member_count"] == 0
    assert loaded["summary"]["team_count"] == 0
    assert loaded["members"] == []


def test_collect_github_teams_export_cli_writes_output(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_empty_org)
    output = tmp_path / "github-teams.json"

    exit_code = main([
        "--organization", "mullusi",
        "--token", "secret-token",
        "--api-base", "https://api.github.test",
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "GitHub teams export written" in captured.out
    assert loaded["source_system"] == "github_api"
    assert "secret-token" not in captured.out


def test_collect_github_teams_export_reports_bounded_http_error(tmp_path, monkeypatch, capsys) -> None:
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden secret-token", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    exit_code = main([
        "--organization", "mullusi",
        "--token", "secret-token",
        "--api-base", "https://api.github.test",
        "--output", str(tmp_path / "github-teams.json"),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "GitHub teams export failed: GitHub endpoint returned HTTP 403" in captured.err
    assert "secret-token" not in captured.err
    assert captured.out == ""


def _urlopen_for_empty_org(request, timeout):
    if request.full_url.endswith("/orgs/mullusi/members?per_page=100&page=1"):
        return StubHttpResponse(payload=[])
    if request.full_url.endswith("/orgs/mullusi/teams?per_page=100&page=1"):
        return StubHttpResponse(payload=[])
    raise AssertionError(f"unexpected url: {request.full_url}")
