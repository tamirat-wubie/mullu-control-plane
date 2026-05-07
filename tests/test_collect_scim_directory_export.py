"""SCIM directory export collector tests.

Purpose: verify live SCIM Users/Groups collection without network access.
Governance scope: bounded pagination, bearer-token handling, JSON persistence,
and credential-safe failure reporting.
"""

from __future__ import annotations

import json
from typing import Any
import urllib.error

from scripts.collect_scim_directory_export import (
    _bounded_error_reason,
    collect_scim_directory_export,
    main,
    write_scim_export,
)


class StubHttpResponse:
    """Context-managed urllib response fixture."""

    def __init__(self, *, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_collect_scim_directory_export_paginates_users_and_groups(monkeypatch) -> None:
    seen_authorization: list[str] = []

    def fake_urlopen(request, timeout):
        seen_authorization.append(request.headers["Authorization"])
        url = request.full_url
        if url.endswith("/Users?startIndex=1&count=1"):
            return StubHttpResponse(payload={
                "Resources": [{"id": "user-1", "userName": "one@example.com"}],
                "itemsPerPage": 1,
                "totalResults": 2,
            })
        if url.endswith("/Users?startIndex=2&count=1"):
            return StubHttpResponse(payload={
                "Resources": [{"id": "user-2", "userName": "two@example.com"}],
                "itemsPerPage": 1,
                "totalResults": 2,
            })
        if url.endswith("/Groups?startIndex=1&count=1"):
            return StubHttpResponse(payload={
                "Resources": [{"id": "group-1", "displayName": "finance_ops"}],
                "itemsPerPage": 1,
                "totalResults": 1,
            })
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = collect_scim_directory_export(
        base_url="https://directory.example.com/scim/v2/",
        bearer_token=" secret-token ",
        page_size=1,
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    assert payload["source_system"] == "scim_api"
    assert payload["source_ref"] == "scim://directory.example.com/export/2026-04-29T12:00:00+00:00"
    assert len(payload["Users"]) == 2
    assert len(payload["Groups"]) == 1
    assert payload["summary"]["page_count"] == 3
    assert seen_authorization == ["Bearer secret-token", "Bearer secret-token", "Bearer secret-token"]


def test_collect_scim_directory_export_rejects_non_http_base_url() -> None:
    try:
        collect_scim_directory_export(
            base_url="file:///tmp/scim",
            bearer_token="secret-token",
            clock=lambda: "2026-04-29T12:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "base_url must be http or https"
        assert "file" not in str(exc)
        assert "tmp" not in str(exc)
    else:
        raise AssertionError("expected non-http SCIM base URL to be rejected")


def test_collect_scim_directory_export_reports_bounded_pagination_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return StubHttpResponse(payload={
            "Resources": [{"id": "user-1"}],
            "itemsPerPage": "secret-token",
            "totalResults": 1,
        })

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    try:
        collect_scim_directory_export(
            base_url="https://directory.example.com/scim/v2",
            bearer_token="secret-token",
            clock=lambda: "2026-04-29T12:00:00+00:00",
        )
    except ValueError as exc:
        assert str(exc) == "SCIM pagination field must be integer"
        assert str(exc).startswith("SCIM pagination")
        assert "secret-token" not in str(exc)
    else:
        raise AssertionError("expected malformed SCIM pagination field to be rejected")


def test_collect_scim_directory_export_writes_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_empty_directory)
    payload = collect_scim_directory_export(
        base_url="https://directory.example.com/scim/v2",
        bearer_token="secret-token",
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    written = write_scim_export(payload, tmp_path / "scim-export.json")
    loaded = json.loads(written.read_text(encoding="utf-8"))

    assert written.name == "scim-export.json"
    assert loaded["summary"]["user_count"] == 0
    assert loaded["summary"]["group_count"] == 0
    assert loaded["Users"] == []


def test_collect_scim_directory_export_cli_writes_output(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _urlopen_for_empty_directory)
    output = tmp_path / "scim-export.json"

    exit_code = main([
        "--base-url", "https://directory.example.com/scim/v2",
        "--bearer-token", "secret-token",
        "--output", str(output),
    ])
    captured = capsys.readouterr()
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "SCIM directory export written" in captured.out
    assert loaded["source_system"] == "scim_api"
    assert "secret-token" not in captured.out


def test_collect_scim_directory_export_reports_bounded_http_error(tmp_path, monkeypatch, capsys) -> None:
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized secret-token", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    exit_code = main([
        "--base-url", "https://directory.example.com/scim/v2",
        "--bearer-token", "secret-token",
        "--output", str(tmp_path / "scim-export.json"),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "SCIM directory export failed: SCIM endpoint returned HTTP 401" in captured.err
    assert "secret-token" not in captured.err
    assert captured.out == ""


def test_scim_directory_export_bounds_unrecognized_error_reason() -> None:
    reason = _bounded_error_reason(ValueError("secret-scim-export-token"))

    assert reason == "invalid_scim_directory_export"
    assert "secret-scim-export-token" not in reason
    assert reason != "secret-scim-export-token"


def _urlopen_for_empty_directory(request, timeout):
    if request.full_url.endswith("/Users?startIndex=1&count=100"):
        return StubHttpResponse(payload={"Resources": [], "itemsPerPage": 0, "totalResults": 0})
    if request.full_url.endswith("/Groups?startIndex=1&count=100"):
        return StubHttpResponse(payload={"Resources": [], "itemsPerPage": 0, "totalResults": 0})
    raise AssertionError(f"unexpected url: {request.full_url}")
