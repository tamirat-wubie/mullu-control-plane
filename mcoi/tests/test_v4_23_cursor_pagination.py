"""v4.23.0 — cursor pagination on /constructs.

Closes the "cursor pagination missing" gap noted in v4.14 release notes.
v4.14 ships offset pagination via ``page=`` + ``page_size=``. Offset
pagination drifts under concurrent inserts/deletes — items can appear
twice or be skipped during long iterations. v4.23 adds cursor
pagination via ``cursor=`` + ``limit=`` as an additive option:

- ``cursor=<opaque-string>`` carries the boundary id from the previous response
- ``limit=N`` bounds the page size (max ``PAGE_SIZE_MAX``)
- Items are sorted by UUID lexicographically — stable under
  insert/delete, deterministic across requests
- ``next_cursor`` in the response is None when no more items remain

The two modes are mutually exclusive in practice: when ``limit`` or
``cursor`` is provided, offset params are ignored and offset response
fields stay None.
"""
from __future__ import annotations

import base64
import json
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    PAGE_SIZE_MAX,
    _decode_cursor,
    _encode_cursor,
    _paginate_cursor,
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    app = FastAPI()
    app.include_router(constructs_router)
    yield TestClient(app)
    reset_registry()


def _seed_constructs(client: TestClient, n: int, tenant: str = "acme") -> list[str]:
    ids = []
    for i in range(n):
        r = client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": tenant},
            json={"configuration": {"i": i}},
        )
        ids.append(r.json()["id"])
    return ids


# ============================================================
# Cursor encoding / decoding (unit)
# ============================================================


def test_encode_decode_round_trip():
    cursor = _encode_cursor("11111111-1111-1111-1111-111111111111")
    assert _decode_cursor(cursor) == "11111111-1111-1111-1111-111111111111"


def test_encoded_cursor_is_url_safe():
    cursor = _encode_cursor("11111111-1111-1111-1111-111111111111")
    # urlsafe base64 uses - and _ (no + or /); padding stripped
    assert "+" not in cursor
    assert "/" not in cursor
    assert "=" not in cursor


def test_encoded_cursor_is_opaque():
    """The cursor's internal format is implementation-private. Verify
    callers can't trivially reconstruct it from outside."""
    cursor = _encode_cursor("aaaa-bbbb")
    # Not a plain UUID, not a plain integer — opaque
    assert cursor != "aaaa-bbbb"
    # But round-trip works
    assert _decode_cursor(cursor) == "aaaa-bbbb"


# ============================================================
# _paginate_cursor (unit)
# ============================================================


class _FakeConstruct:
    """Minimal stand-in for ConstructBase — _paginate_cursor only needs .id."""
    def __init__(self, uid: str):
        self.id = uid


def _seed_fake(ids: list[str]) -> list[_FakeConstruct]:
    return [_FakeConstruct(uid) for uid in ids]


def test_paginate_cursor_no_cursor_returns_first_limit():
    items = _seed_fake([
        "33333333-3333-3333-3333-333333333333",
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    page, next_cursor = _paginate_cursor(items, None, limit=2)
    # Sorted by UUID: 1, 2, 3 — first 2 are 1 and 2
    assert [str(c.id) for c in page] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    # next_cursor points past 2; one more item (3) remains
    assert next_cursor is not None
    assert _decode_cursor(next_cursor) == "22222222-2222-2222-2222-222222222222"


def test_paginate_cursor_with_cursor_skips_to_after():
    items = _seed_fake([
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
    ])
    cursor = _encode_cursor("11111111-1111-1111-1111-111111111111")
    page, next_cursor = _paginate_cursor(items, cursor, limit=10)
    assert [str(c.id) for c in page] == [
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
    ]
    assert next_cursor is None  # no more items


def test_paginate_cursor_last_page_returns_none_cursor():
    items = _seed_fake([
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    page, next_cursor = _paginate_cursor(items, None, limit=10)
    assert len(page) == 2
    assert next_cursor is None


def test_paginate_cursor_exact_limit_returns_none_cursor_when_no_more():
    """When the page exactly equals the remaining items, next_cursor is None."""
    items = _seed_fake([
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ])
    page, next_cursor = _paginate_cursor(items, None, limit=2)
    assert len(page) == 2
    assert next_cursor is None  # exhausted


def test_paginate_cursor_stable_after_delete_between_pages():
    """Insert/delete between pages doesn't corrupt iteration. Get
    the first page, delete an item not on the page, get the second
    page — should not skip or repeat."""
    items = _seed_fake([
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444444",
    ])
    # Page 1: items 1, 2
    page_1, next_cursor = _paginate_cursor(items, None, limit=2)
    assert [str(c.id) for c in page_1] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    # Simulate delete of item-1 (already returned, not on next page)
    items_after_delete = [c for c in items if str(c.id) != "11111111-1111-1111-1111-111111111111"]
    # Page 2 with same cursor: should give items 3, 4
    page_2, _ = _paginate_cursor(items_after_delete, next_cursor, limit=2)
    assert [str(c.id) for c in page_2] == [
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444444",
    ]


def test_paginate_cursor_stable_after_insert_between_pages():
    """A new item inserted between pages with id < cursor doesn't
    show up on subsequent pages (it's behind the cursor)."""
    items = _seed_fake([
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444444",
    ])
    page_1, next_cursor = _paginate_cursor(items, None, limit=1)
    # Page 1: item 3
    assert [str(c.id) for c in page_1] == ["33333333-3333-3333-3333-333333333333"]
    # Insert item-2 (id < cursor) between requests
    items.append(_FakeConstruct("22222222-2222-2222-2222-222222222222"))
    # Page 2 with cursor: skips item-2 (correct — it was inserted "before" the cursor)
    page_2, _ = _paginate_cursor(items, next_cursor, limit=10)
    assert [str(c.id) for c in page_2] == ["44444444-4444-4444-4444-444444444444"]


# ============================================================
# HTTP endpoint
# ============================================================


def test_cursor_pagination_walks_all_items(client):
    """Sequential cursor walk visits every item exactly once."""
    seeded_ids = _seed_constructs(client, 10)
    seen_ids: set[str] = set()
    cursor = None
    pages = 0
    while True:
        params = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        r = client.get("/constructs", headers={"X-Tenant-ID": "acme"}, params=params)
        body = r.json()
        for c in body["constructs"]:
            seen_ids.add(c["id"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
        if pages > 20:
            pytest.fail("infinite loop suspected")
    assert seen_ids == set(seeded_ids)
    # 10 items / 3 per page → 4 pages (3+3+3+1)
    assert pages == 4


def test_cursor_response_excludes_offset_fields(client):
    _seed_constructs(client, 5)
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"limit": 2},
    )
    body = r.json()
    # Cursor mode: offset fields stay None
    assert body["page"] is None
    assert body["page_size"] is None
    assert body["total_pages"] is None
    # next_cursor populated for partial walks
    assert body["next_cursor"] is not None


def test_cursor_takes_precedence_over_offset(client):
    """Both pagination modes specified → cursor wins, offset ignored."""
    _seed_constructs(client, 5)
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"limit": 2, "page": 99, "page_size": 2},
    )
    body = r.json()
    # Cursor mode active; offset fields ignored (stay None)
    assert body["page"] is None
    assert body["page_size"] is None
    assert len(body["constructs"]) == 2


def test_cursor_only_no_limit_returns_default_page_size(client):
    """Just ``cursor`` with no ``limit`` falls back to PAGE_SIZE_MAX."""
    _seed_constructs(client, 5)
    cursor = _encode_cursor("00000000-0000-0000-0000-000000000000")
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"cursor": cursor},
    )
    assert r.status_code == 200
    # All 5 items fit under PAGE_SIZE_MAX, so all returned
    assert len(r.json()["constructs"]) == 5


def test_invalid_cursor_returns_400(client):
    _seed_constructs(client, 5)
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"cursor": "this-is-not-base64-json"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_cursor"


def test_invalid_limit_returns_400(client):
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"limit": 0},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_limit"


def test_limit_above_max_returns_400(client):
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"limit": PAGE_SIZE_MAX + 1},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_limit"
    assert r.json()["detail"]["max"] == PAGE_SIZE_MAX


def test_cursor_returns_total_unfiltered_count(client):
    """Total reflects the FULL match set, not just the page."""
    _seed_constructs(client, 7)
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"limit": 3},
    )
    body = r.json()
    assert body["total"] == 7  # full count
    assert len(body["constructs"]) == 3  # but page is sliced


def test_cursor_empty_registry_returns_no_pages(client):
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "fresh"},
        params={"limit": 10},
    )
    body = r.json()
    assert body["total"] == 0
    assert body["constructs"] == []
    assert body["next_cursor"] is None


def test_cursor_with_filters(client):
    """Cursor pagination respects the existing tier/type filters."""
    _seed_constructs(client, 10)
    # All seeded constructs are Tier 1 (state); a tier=2 filter yields 0
    r = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"tier": 2, "limit": 3},
    )
    body = r.json()
    assert body["total"] == 0
    assert body["next_cursor"] is None


def test_cursor_offset_paths_yield_same_total_count(client):
    """Both pagination modes report the same ``total`` for the same registry."""
    _seed_constructs(client, 12)
    r_offset = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"page_size": 5},
    ).json()
    r_cursor = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
        params={"limit": 5},
    ).json()
    assert r_offset["total"] == r_cursor["total"] == 12
