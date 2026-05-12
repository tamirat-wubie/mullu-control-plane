"""Offset and cursor pagination helpers for /constructs/* listings."""
from __future__ import annotations

import base64
import json

from fastapi import HTTPException

from mcoi_runtime.substrate.constructs import ConstructBase


PAGE_SIZE_MAX = 1000


# ---- Offset pagination (v4.14.0) ----


def _validate_pagination(
    page: int | None,
    page_size: int | None,
) -> tuple[int | None, int | None]:
    """Coerce + validate pagination params. Returns (page, page_size) or (None, None).

    Pagination is "active" iff page_size is not None. page defaults to 1.
    """
    if page_size is None:
        return None, None
    if page_size < 1 or page_size > PAGE_SIZE_MAX:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_page_size", "max": PAGE_SIZE_MAX},
        )
    if page is None:
        page = 1
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    return page, page_size


def _paginate_slice(
    items: list,
    page: int | None,
    page_size: int | None,
) -> tuple[list, int | None, bool | None]:
    """Slice items by page. Returns (slice, total_pages, has_more) or (items, None, None) when not paginated."""
    if page is None or page_size is None:
        return items, None, None
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = items[start:end]
    has_more = end < total
    return sliced, total_pages, has_more


# ---- Cursor pagination (v4.23.0) ----
#
# Offset pagination drifts when items are inserted/deleted between
# requests: a client iterating page=1, page=2, page=3 may see the same
# item twice (after an insert near the start) or miss items (after a
# delete). Cursor pagination is stable: the cursor is an opaque token
# carrying the boundary item's id, and "next page" means
# "items strictly after this id, sorted by id." Inserts and deletes
# anywhere in the list don't corrupt the iteration.
#
# Trade-off: items are sorted lexicographically by UUID (not by
# insertion order). This is fine because:
#   1. The list endpoint contract doesn't promise insertion order
#   2. Clients using cursor pagination care about consistency, not order
#   3. UUIDs are random, so the order is deterministic per item set


def _encode_cursor(after_id: str) -> str:
    """Encode a boundary id as an opaque cursor string."""
    payload = json.dumps({"after_id": after_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> str:
    """Decode an opaque cursor. Returns the boundary id.

    Raises HTTPException(400, invalid_cursor) on any decode/parse error.
    Cursor is meant to be opaque to clients — they always pass back
    exactly what the server emitted, so corruption indicates client
    bug or intentional tampering.
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode())
        payload = json.loads(decoded)
        after_id = payload["after_id"]
        if not isinstance(after_id, str) or not after_id:
            raise ValueError("empty after_id")
        return after_id
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_cursor"},
        )


def _validate_cursor_limit(limit: int | None) -> int | None:
    """Coerce + validate the cursor-mode ``limit`` param."""
    if limit is None:
        return None
    if limit < 1 or limit > PAGE_SIZE_MAX:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_limit", "max": PAGE_SIZE_MAX},
        )
    return limit


def _paginate_cursor(
    items: list[ConstructBase],
    cursor: str | None,
    limit: int,
) -> tuple[list[ConstructBase], str | None]:
    """Apply cursor pagination to a list of constructs.

    Items are sorted by UUID lexicographically; the slice is the first
    ``limit`` items strictly greater than the cursor's boundary id.
    Returns (page_items, next_cursor) where next_cursor is None when
    the page is the last one.
    """
    sorted_items = sorted(items, key=lambda c: str(c.id))
    if cursor is not None:
        after_id = _decode_cursor(cursor)
        sorted_items = [c for c in sorted_items if str(c.id) > after_id]
    page = sorted_items[:limit]
    if len(page) < limit:
        next_cursor = None  # no more items
    else:
        last_id = str(page[-1].id)
        next_cursor = (
            _encode_cursor(last_id)
            if any(str(c.id) > last_id for c in sorted_items)
            else None
        )
    return page, next_cursor
