#!/usr/bin/env python3
"""Shared Personal Assistant source digest helpers.

Purpose: compute stable digests for checked-in Personal Assistant evidence
sources without serializing source payloads into aggregate receipts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: pathlib and hashlib from the Python standard library.
Invariants:
  - Text source digests are stable across LF and CRLF checkouts.
  - The helper performs no Unicode decomposition, recomposition, or meaning substitution.
  - The helper reads source bytes only and returns a bounded SHA-256 hex digest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

TEXT_SOURCE_SUFFIXES = frozenset({".json", ".md", ".py", ".yaml", ".yml"})


def canonical_source_sha256(path: Path) -> str:
    """Return a newline-stable SHA-256 digest for checked-in text sources."""
    raw_bytes = path.read_bytes()
    if path.suffix.casefold() not in TEXT_SOURCE_SUFFIXES:
        return hashlib.sha256(raw_bytes).hexdigest()
    try:
        source_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"failed to decode Personal Assistant text source: {path.as_posix()}") from exc
    newline_stable_text = source_text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(newline_stable_text.encode("utf-8")).hexdigest()
