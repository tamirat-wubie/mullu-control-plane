"""Purpose: local document loading adapter for text, markdown, and JSON files.
Governance scope: document ingestion adapter only — no execution, no mutation.
Dependencies: document contracts, document core.
Invariants:
  - Only reads local files. No network access.
  - Unknown formats are reported explicitly, not rejected silently.
  - File read failures are typed, not swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mcoi_runtime.contracts.document import DocumentContent
from mcoi_runtime.core.document import ingest_document
from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


def _bounded_document_error(summary: str, exc: Exception) -> str:
    """Return a stable document-load failure without raw filesystem detail."""
    return f"{summary} ({type(exc).__name__})"


class DocumentLoadStatus(StrEnum):
    LOADED = "loaded"
    NOT_FOUND = "not_found"
    READ_ERROR = "read_error"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class DocumentLoadResult:
    """Result of attempting to load a document from disk."""

    status: DocumentLoadStatus
    document: DocumentContent | None = None
    error_message: str | None = None


class LocalDocumentAdapter:
    """Loads local text, markdown, and JSON files as DocumentContent artifacts.

    Supported formats: .txt, .md, .markdown, .json
    """

    SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".json"})

    def load(self, source_path: str) -> DocumentLoadResult:
        """Load a document from a local file path."""
        ensure_non_empty_text("source_path", source_path)
        path = Path(source_path)

        if not path.exists():
            return DocumentLoadResult(
                status=DocumentLoadStatus.NOT_FOUND,
                error_message="file not found",
            )

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return DocumentLoadResult(
                status=DocumentLoadStatus.UNSUPPORTED,
                error_message=f"unsupported extension: {ext}",
            )

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return DocumentLoadResult(
                status=DocumentLoadStatus.READ_ERROR,
                error_message=_bounded_document_error("read error", exc),
            )

        document_id = stable_identifier("doc", {
            "path": str(path.resolve()),
        })

        document = ingest_document(document_id, source_path, content)

        return DocumentLoadResult(
            status=DocumentLoadStatus.LOADED,
            document=document,
        )
