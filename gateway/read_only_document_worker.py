"""Read-only document inspection worker.

Purpose: provide a Foundation Mode worker path for local document inspection
without mutation, network, secrets, external tenant resources, or spend.
Governance scope: worker lease authority, document path containment, supported
format boundaries, bounded reads, deterministic traversal, and secret redaction.
Dependencies: pathlib, re, command-spine hashing, and worker mesh contracts.
Invariants:
  - Only document-root-relative paths are accepted.
  - Unsupported binary or rich document formats fail closed.
  - Requests containing mutation, network, or secret-bearing inputs fail closed.
  - Output excerpts are bounded and redacted before receipt publication.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.worker_mesh import (
    WORKER_MESH_SCHEMA_REF,
    WorkerDispatchRequest,
    WorkerHandler,
    WorkerHandlerResult,
    WorkerLease,
    WorkerLeaseBudget,
    WorkerLeaseScope,
)


DOCUMENT_INSPECT_CAPABILITY = "document.inspect_read_only"
DOCUMENT_INSPECT_OPERATION = "inspect"
DEFAULT_MAX_DOCUMENTS = 25
DEFAULT_MAX_BYTES_PER_DOCUMENT = 262_144
SUPPORTED_TEXT_EXTENSIONS = frozenset(
    {".txt", ".md", ".markdown", ".rst", ".json", ".yaml", ".yml", ".csv", ".tsv"}
)
_MUTATION_KEYS = frozenset(
    {"write", "writes", "mutation", "mutations", "patch", "delete", "remove", "move", "rename", "command", "shell"}
)
_NETWORK_KEYS = frozenset({"url", "urls", "network", "network_targets", "endpoint", "host"})
_SECRET_KEYS = frozenset({"secret", "secrets", "token", "tokens", "password", "api_key", "private_key"})
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:api[_-]?key|secret|token|password|private[_-]?key)[a-z0-9_-]*)\b\s*[:=]\s*[^,\s]+"
)


@dataclass(frozen=True, slots=True)
class DocumentInspectionBounds:
    """Bounded scan settings for document inspection."""

    max_documents: int = DEFAULT_MAX_DOCUMENTS
    max_bytes_per_document: int = DEFAULT_MAX_BYTES_PER_DOCUMENT

    def __post_init__(self) -> None:
        if not isinstance(self.max_documents, int) or isinstance(self.max_documents, bool):
            raise ValueError("max_documents_integer_required")
        if self.max_documents <= 0:
            raise ValueError("max_documents_positive_required")
        if not isinstance(self.max_bytes_per_document, int) or isinstance(self.max_bytes_per_document, bool):
            raise ValueError("max_bytes_per_document_integer_required")
        if self.max_bytes_per_document <= 0:
            raise ValueError("max_bytes_per_document_positive_required")


def build_read_only_document_inspection_lease(
    *,
    tenant_id: str,
    lease_id: str,
    issued_at: str,
    expires_at: str,
    worker_id: str = "document-inspect-read-only-worker",
    max_operations: int = 10,
    document_root_ref: str = "documents:local",
) -> WorkerLease:
    """Build the worker mesh lease for read-only document inspection."""
    return WorkerLease(
        worker_id=worker_id,
        capability=DOCUMENT_INSPECT_CAPABILITY,
        tenant_id=tenant_id,
        lease_id=lease_id,
        allowed_operations=[DOCUMENT_INSPECT_OPERATION],
        forbidden_operations=["write", "delete", "move", "network", "shell", "rich_parse"],
        budget=WorkerLeaseBudget(max_operations=max_operations, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=[document_root_ref],
            data_classes=["document_metadata", "document_text_excerpt"],
            network_allowlist=[],
        ),
        timeout_seconds=30,
        sandbox="local-read-only-document",
        policy_refs=["policy:foundation-mode:read-only-document-worker"],
        receipt_schema_ref=WORKER_MESH_SCHEMA_REF,
        verification_ref="verification:document-inspect-read-only",
        recovery_ref="recovery:operator-review",
        expires_at=expires_at,
        issued_at=issued_at,
        metadata={
            "mutation_allowed": False,
            "external_network_allowed": False,
            "secrets_required": False,
            "spend_required": False,
            "supported_extensions": sorted(SUPPORTED_TEXT_EXTENSIONS),
            "rich_document_parsing_allowed": False,
        },
    )


def create_read_only_document_inspection_handler(document_root: Path) -> WorkerHandler:
    """Return a worker mesh handler bound to a document root."""
    resolved_root = document_root.resolve()

    def handler(request: WorkerDispatchRequest) -> WorkerHandlerResult:
        return inspect_document_request(resolved_root, request)

    return handler


def inspect_document_request(
    document_root: Path,
    request: WorkerDispatchRequest,
) -> WorkerHandlerResult:
    """Inspect local text-like documents from a worker mesh request payload."""
    payload = dict(request.payload)
    denial = _payload_denial(payload)
    if denial:
        return WorkerHandlerResult(status="failed", error=denial)

    try:
        bounds = _bounds_from_payload(payload)
        relative_documents = _string_list(payload.get("documents", []), "documents")
        query = _optional_text(payload.get("query", ""))
        documents = _resolve_documents(
            document_root=document_root,
            relative_documents=relative_documents,
            max_documents=bounds.max_documents,
        )
    except ValueError as exc:
        return WorkerHandlerResult(status="failed", error=str(exc))

    inspected_documents = []
    truncated_documents = 0
    for document_path in documents:
        try:
            document_result = _inspect_document(
                document_root=document_root,
                document_path=document_path,
                query=query,
                max_bytes_per_document=bounds.max_bytes_per_document,
            )
        except ValueError as exc:
            return WorkerHandlerResult(status="failed", error=str(exc))
        if document_result["truncated"] is True:
            truncated_documents += 1
        inspected_documents.append(document_result)

    output = {
        "capability_id": DOCUMENT_INSPECT_CAPABILITY,
        "operation": DOCUMENT_INSPECT_OPERATION,
        "document_root_hash": canonical_hash(str(document_root)),
        "request_payload_hash": canonical_hash(payload),
        "documents_considered": len(documents),
        "documents_inspected": len(inspected_documents),
        "truncated_documents": truncated_documents,
        "match_document_count": sum(1 for document in inspected_documents if document["matches"]),
        "documents": inspected_documents,
        "supported_extensions": sorted(SUPPORTED_TEXT_EXTENSIONS),
        "bounds": {
            "max_documents": bounds.max_documents,
            "max_bytes_per_document": bounds.max_bytes_per_document,
        },
        "proof_obligations": [
            "no_write_operation",
            "no_external_network",
            "document_path_boundary",
            "format_allowlist",
            "scan_bounds",
            "secret_redaction",
            "deterministic_traversal",
        ],
    }
    output_hash = canonical_hash(output)
    return WorkerHandlerResult(
        status="succeeded",
        output=output,
        evidence_refs=[
            f"document-inspect:boundary:{canonical_hash({'root': str(document_root), 'documents': relative_documents})[:16]}",
            f"document-inspect:result:{output_hash[:16]}",
        ],
        cost=0.0,
    )


def _payload_denial(payload: dict[str, Any]) -> str:
    keys = {str(key).strip().lower() for key in payload}
    if keys.intersection(_MUTATION_KEYS):
        return "mutation_input_forbidden"
    if keys.intersection(_NETWORK_KEYS):
        return "network_input_forbidden"
    if keys.intersection(_SECRET_KEYS):
        return "secret_input_forbidden"
    if _contains_secret_like_value(payload):
        return "secret_input_forbidden"
    return ""


def _contains_secret_like_value(value: Any) -> bool:
    if isinstance(value, str):
        return _SECRET_VALUE_PATTERN.search(value) is not None
    if isinstance(value, list):
        return any(_contains_secret_like_value(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_secret_like_value(item) for item in value.values())
    return False


def _bounds_from_payload(payload: dict[str, Any]) -> DocumentInspectionBounds:
    return DocumentInspectionBounds(
        max_documents=_positive_int(payload.get("max_documents", DEFAULT_MAX_DOCUMENTS), "max_documents"),
        max_bytes_per_document=_positive_int(
            payload.get("max_bytes_per_document", DEFAULT_MAX_BYTES_PER_DOCUMENT),
            "max_bytes_per_document",
        ),
    )


def _positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}_integer_required")
    if value <= 0:
        raise ValueError(f"{field_name}_positive_required")
    return value


def _resolve_documents(
    *,
    document_root: Path,
    relative_documents: list[str],
    max_documents: int,
) -> list[Path]:
    resolved_documents = []
    for relative_document in relative_documents:
        document_path = _resolve_document_relative_path(document_root, relative_document)
        if document_path.is_dir():
            raise ValueError("document_file_required")
        if document_path.suffix.lower() not in SUPPORTED_TEXT_EXTENSIONS:
            raise ValueError("document_format_not_supported")
        resolved_documents.append(document_path)
    unique_sorted = sorted(set(resolved_documents), key=lambda path: path.relative_to(document_root).as_posix())
    return unique_sorted[:max_documents]


def _resolve_document_relative_path(document_root: Path, relative_document: str) -> Path:
    if not relative_document or Path(relative_document).is_absolute():
        raise ValueError("document_path_boundary_violation")
    resolved = (document_root / relative_document).resolve()
    try:
        resolved.relative_to(document_root)
    except ValueError as exc:
        raise ValueError("document_path_boundary_violation") from exc
    if not resolved.exists():
        raise ValueError("document_not_found")
    return resolved


def _inspect_document(
    *,
    document_root: Path,
    document_path: Path,
    query: str,
    max_bytes_per_document: int,
) -> dict[str, Any]:
    raw_bytes = document_path.read_bytes()
    truncated = len(raw_bytes) > max_bytes_per_document
    bounded_bytes = raw_bytes[:max_bytes_per_document]
    try:
        text = bounded_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("document_text_decode_failed") from exc
    return {
        "relative_path": document_path.relative_to(document_root).as_posix(),
        "extension": document_path.suffix.lower(),
        "size_bytes": len(raw_bytes),
        "content_hash": canonical_hash(raw_bytes.hex()),
        "truncated": truncated,
        "line_count": len(text.splitlines()),
        "matches": _line_matches(text, query),
    }


def _line_matches(text: str, query: str) -> list[dict[str, Any]]:
    if not query:
        return []
    findings: list[dict[str, Any]] = []
    query_lower = query.lower()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if query_lower in line.lower():
            findings.append({"line": line_number, "excerpt": _redacted_excerpt(line)})
    return findings


def _redacted_excerpt(line: str) -> str:
    redacted = _SECRET_VALUE_PATTERN.sub(r"\1=[REDACTED]", line.strip())
    if len(redacted) > 160:
        return f"{redacted[:157]}..."
    return redacted


def _string_list(value: Any, field_name: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError(f"{field_name}_list_required")
    result = []
    for item in values:
        text = _optional_text(item)
        if not text:
            raise ValueError(f"{field_name}_item_required")
        result.append(text)
    if not result:
        raise ValueError(f"{field_name}_required")
    return result


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("text_value_required")
    return value.strip()
