"""Purpose: document automation core — ingest, fingerprint, extract, verify.
Governance scope: document processing core logic only.
Dependencies: document contracts, invariant helpers.
Invariants:
  - Fingerprinting is deterministic for identical content.
  - Extraction never fabricates values — missing fields are explicit.
  - Verification compares against declared expectations, never guesses.
  - All operations are local and side-effect free (no network, no mutation).
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.document import (
    DocumentContent,
    DocumentDescriptor,
    DocumentFingerprint,
    DocumentFormat,
    DocumentVerificationResult,
    DocumentVerificationStatus,
    ExtractionField,
    ExtractionResult,
    ExtractionStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


def compute_fingerprint(document_id: str, content: str) -> DocumentFingerprint:
    """Compute a deterministic fingerprint for document content."""
    ensure_non_empty_text("document_id", document_id)
    content_bytes = content.encode("utf-8")
    content_hash = sha256(content_bytes).hexdigest()
    line_count = content.count("\n") + (1 if content else 0)

    fingerprint_id = stable_identifier("fp", {
        "document_id": document_id,
        "content_hash": content_hash,
    })

    return DocumentFingerprint(
        fingerprint_id=fingerprint_id,
        document_id=document_id,
        content_hash=content_hash,
        byte_length=len(content_bytes),
        line_count=line_count,
    )


def detect_format(source_path: str) -> DocumentFormat:
    """Detect document format from file extension."""
    lower = source_path.lower()
    if lower.endswith(".txt"):
        return DocumentFormat.TEXT
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return DocumentFormat.MARKDOWN
    if lower.endswith(".json"):
        return DocumentFormat.JSON
    return DocumentFormat.UNKNOWN


def ingest_document(document_id: str, source_path: str, content: str) -> DocumentContent:
    """Ingest a document: fingerprint and wrap as DocumentContent."""
    ensure_non_empty_text("document_id", document_id)
    ensure_non_empty_text("source_path", source_path)

    fmt = detect_format(source_path)
    fingerprint = compute_fingerprint(document_id, content)

    return DocumentContent(
        document_id=document_id,
        format=fmt,
        text=content,
        source_path=source_path,
        fingerprint=fingerprint,
    )


def extract_fields(
    document: DocumentContent,
    field_specs: Mapping[str, Callable[[str], Any] | None],
) -> ExtractionResult:
    """Extract typed fields from document content.

    field_specs maps field names to extractor callables.
    Each extractor receives the full text and returns a value, or raises on failure.
    If extractor is None, the field is marked as missing.
    """
    ensure_non_empty_text("document_id", document.document_id)

    fields: list[ExtractionField] = []
    extracted = 0
    missing = 0
    malformed = 0

    for field_name, extractor in sorted(field_specs.items()):
        if extractor is None:
            fields.append(ExtractionField(
                field_name=field_name,
                status=ExtractionStatus.MISSING,
            ))
            missing += 1
            continue

        try:
            value = extractor(document.text)
            if value is None:
                fields.append(ExtractionField(
                    field_name=field_name,
                    status=ExtractionStatus.MISSING,
                ))
                missing += 1
            else:
                fields.append(ExtractionField(
                    field_name=field_name,
                    status=ExtractionStatus.EXTRACTED,
                    value=value,
                ))
                extracted += 1
        except Exception:
            fields.append(ExtractionField(
                field_name=field_name,
                status=ExtractionStatus.MALFORMED,
            ))
            malformed += 1

    extraction_id = stable_identifier("extract", {
        "document_id": document.document_id,
        "field_count": len(field_specs),
    })

    return ExtractionResult(
        extraction_id=extraction_id,
        document_id=document.document_id,
        fields=tuple(fields),
        extracted_count=extracted,
        missing_count=missing,
        malformed_count=malformed,
    )


def extract_json_fields(
    document: DocumentContent,
    expected_keys: tuple[str, ...],
) -> ExtractionResult:
    """Extract fields from a JSON document by key lookup."""
    if document.format is not DocumentFormat.JSON:
        # Return all fields as malformed if not JSON
        fields = tuple(
            ExtractionField(field_name=k, status=ExtractionStatus.MALFORMED)
            for k in expected_keys
        )
        extraction_id = stable_identifier("extract", {
            "document_id": document.document_id,
            "field_count": len(expected_keys),
        })
        return ExtractionResult(
            extraction_id=extraction_id,
            document_id=document.document_id,
            fields=fields,
            extracted_count=0,
            missing_count=0,
            malformed_count=len(expected_keys),
        )

    try:
        data = json.loads(document.text)
    except json.JSONDecodeError:
        fields = tuple(
            ExtractionField(field_name=k, status=ExtractionStatus.MALFORMED)
            for k in expected_keys
        )
        extraction_id = stable_identifier("extract", {
            "document_id": document.document_id,
            "field_count": len(expected_keys),
        })
        return ExtractionResult(
            extraction_id=extraction_id,
            document_id=document.document_id,
            fields=fields,
            extracted_count=0,
            missing_count=0,
            malformed_count=len(expected_keys),
        )

    if not isinstance(data, dict):
        data = {}

    fields_list: list[ExtractionField] = []
    extracted = 0
    missing = 0

    for key in sorted(expected_keys):
        if key in data:
            fields_list.append(ExtractionField(
                field_name=key,
                status=ExtractionStatus.EXTRACTED,
                value=data[key],
            ))
            extracted += 1
        else:
            fields_list.append(ExtractionField(
                field_name=key,
                status=ExtractionStatus.MISSING,
            ))
            missing += 1

    extraction_id = stable_identifier("extract", {
        "document_id": document.document_id,
        "field_count": len(expected_keys),
    })

    return ExtractionResult(
        extraction_id=extraction_id,
        document_id=document.document_id,
        fields=tuple(fields_list),
        extracted_count=extracted,
        missing_count=missing,
        malformed_count=0,
    )


def verify_extraction(
    extraction: ExtractionResult,
    expected_fields: tuple[str, ...],
    expected_values: Mapping[str, Any] | None = None,
) -> DocumentVerificationResult:
    """Verify extraction against expected fields and optional expected values."""
    field_map = {f.field_name: f for f in extraction.fields}

    matched: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []

    for field_name in sorted(expected_fields):
        ef = field_map.get(field_name)
        if ef is None or ef.status is not ExtractionStatus.EXTRACTED:
            missing.append(field_name)
            continue

        if expected_values and field_name in expected_values:
            if ef.value != expected_values[field_name]:
                mismatched.append(field_name)
                continue

        matched.append(field_name)

    # Determine status
    if not missing and not mismatched:
        status = DocumentVerificationStatus.PASS
    elif matched and (missing or mismatched):
        status = DocumentVerificationStatus.PARTIAL
    else:
        status = DocumentVerificationStatus.FAIL

    verification_id = stable_identifier("docverify", {
        "extraction_id": extraction.extraction_id,
        "expected_count": len(expected_fields),
    })

    reason = None
    if missing:
        reason = f"missing fields: {', '.join(missing)}"
    if mismatched:
        mismatch_msg = f"mismatched fields: {', '.join(mismatched)}"
        reason = f"{reason}; {mismatch_msg}" if reason else mismatch_msg

    return DocumentVerificationResult(
        verification_id=verification_id,
        document_id=extraction.document_id,
        extraction_id=extraction.extraction_id,
        status=status,
        expected_fields=tuple(sorted(expected_fields)),
        matched_fields=tuple(matched),
        missing_fields=tuple(missing),
        mismatched_fields=tuple(mismatched),
        reason=reason,
    )
