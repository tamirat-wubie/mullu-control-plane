"""Read-only repository inspection worker.

Purpose: provide the first Foundation Mode worker path for local repository
inspection without mutation, network, secrets, external tenant resources, or
spend.
Governance scope: worker lease authority, repository path containment, bounded
scan limits, deterministic traversal, and secret redaction.
Dependencies: pathlib, fnmatch, re, command-spine hashing, and worker mesh
contracts.
Invariants:
  - Only repository-relative paths are accepted.
  - Requests containing mutation, network, or secret-bearing inputs fail closed.
  - Traversal is sorted and bounded by max file and byte limits.
  - Output excerpts are redacted before receipt publication.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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


REPOSITORY_INSPECT_CAPABILITY = "repository.inspect_read_only"
REPOSITORY_INSPECT_OPERATION = "inspect"
DEFAULT_MAX_FILES = 200
DEFAULT_MAX_BYTES_PER_FILE = 262_144
_MUTATION_KEYS = frozenset(
    {
        "write",
        "writes",
        "mutation",
        "mutations",
        "patch",
        "delete",
        "remove",
        "move",
        "rename",
        "command",
        "shell",
    }
)
_NETWORK_KEYS = frozenset({"url", "urls", "network", "network_targets", "endpoint", "host"})
_SECRET_KEYS = frozenset({"secret", "secrets", "token", "tokens", "password", "api_key", "private_key"})
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)\b([a-z0-9_-]*(?:api[_-]?key|secret|token|password|private[_-]?key)[a-z0-9_-]*)\b\s*[:=]\s*[^,\s]+"
)


@dataclass(frozen=True, slots=True)
class RepositoryInspectionBounds:
    """Bounded scan settings for repository inspection."""

    max_files: int = DEFAULT_MAX_FILES
    max_bytes_per_file: int = DEFAULT_MAX_BYTES_PER_FILE

    def __post_init__(self) -> None:
        if not isinstance(self.max_files, int) or isinstance(self.max_files, bool):
            raise ValueError("max_files_integer_required")
        if self.max_files <= 0:
            raise ValueError("max_files_positive_required")
        if not isinstance(self.max_bytes_per_file, int) or isinstance(self.max_bytes_per_file, bool):
            raise ValueError("max_bytes_per_file_integer_required")
        if self.max_bytes_per_file <= 0:
            raise ValueError("max_bytes_per_file_positive_required")


def build_read_only_repository_inspection_lease(
    *,
    tenant_id: str,
    lease_id: str,
    issued_at: str,
    expires_at: str,
    worker_id: str = "repository-inspect-read-only-worker",
    max_operations: int = 10,
    repository_ref: str = "repository:local",
) -> WorkerLease:
    """Build the worker mesh lease for read-only repository inspection."""
    return WorkerLease(
        worker_id=worker_id,
        capability=REPOSITORY_INSPECT_CAPABILITY,
        tenant_id=tenant_id,
        lease_id=lease_id,
        allowed_operations=[REPOSITORY_INSPECT_OPERATION],
        forbidden_operations=["write", "delete", "move", "network", "shell"],
        budget=WorkerLeaseBudget(max_operations=max_operations, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=[repository_ref],
            data_classes=["repository_metadata", "repository_text_excerpt"],
            network_allowlist=[],
        ),
        timeout_seconds=30,
        sandbox="local-read-only-repository",
        policy_refs=["policy:foundation-mode:read-only-repository-worker"],
        receipt_schema_ref=WORKER_MESH_SCHEMA_REF,
        verification_ref="verification:repository-inspect-read-only",
        recovery_ref="recovery:operator-review",
        expires_at=expires_at,
        issued_at=issued_at,
        metadata={
            "mutation_allowed": False,
            "external_network_allowed": False,
            "secrets_required": False,
            "spend_required": False,
        },
    )


def create_read_only_repository_inspection_handler(
    repository_root: Path,
) -> WorkerHandler:
    """Return a worker mesh handler bound to a repository root."""
    resolved_root = repository_root.resolve()

    def handler(request: WorkerDispatchRequest) -> WorkerHandlerResult:
        return inspect_repository_request(resolved_root, request)

    return handler


def inspect_repository_request(
    repository_root: Path,
    request: WorkerDispatchRequest,
) -> WorkerHandlerResult:
    """Inspect repository files from a worker mesh request payload."""
    payload = dict(request.payload)
    denial = _payload_denial(payload)
    if denial:
        return WorkerHandlerResult(status="failed", error=denial)

    try:
        bounds = _bounds_from_payload(payload)
        relative_paths = _string_list(payload.get("paths", ["."]), "paths")
        patterns = _string_list(payload.get("patterns", ["*"]), "patterns")
        query = _optional_text(payload.get("query", ""))
        files = _collect_files(
            repository_root=repository_root,
            relative_paths=relative_paths,
            patterns=patterns,
            max_files=bounds.max_files,
        )
    except ValueError as exc:
        return WorkerHandlerResult(status="failed", error=str(exc))

    findings = []
    scanned = 0
    truncated_files = 0
    for file_path in files:
        scanned += 1
        file_result = _inspect_file(
            repository_root=repository_root,
            file_path=file_path,
            query=query,
            max_bytes_per_file=bounds.max_bytes_per_file,
        )
        if file_result["truncated"] is True:
            truncated_files += 1
        if file_result["matches"]:
            findings.append(file_result)

    output = {
        "capability_id": REPOSITORY_INSPECT_CAPABILITY,
        "operation": REPOSITORY_INSPECT_OPERATION,
        "repository_root_hash": canonical_hash(str(repository_root)),
        "request_payload_hash": canonical_hash(payload),
        "files_considered": len(files),
        "files_scanned": scanned,
        "truncated_files": truncated_files,
        "match_file_count": len(findings),
        "findings": findings,
        "bounds": {
            "max_files": bounds.max_files,
            "max_bytes_per_file": bounds.max_bytes_per_file,
        },
        "proof_obligations": [
            "no_write_operation",
            "no_external_network",
            "path_boundary",
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
            f"repository-inspect:boundary:{canonical_hash({'root': str(repository_root), 'paths': relative_paths})[:16]}",
            f"repository-inspect:result:{output_hash[:16]}",
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
    return ""


def _bounds_from_payload(payload: dict[str, Any]) -> RepositoryInspectionBounds:
    max_files = payload.get("max_files", DEFAULT_MAX_FILES)
    max_bytes_per_file = payload.get("max_bytes_per_file", DEFAULT_MAX_BYTES_PER_FILE)
    return RepositoryInspectionBounds(
        max_files=_positive_int(max_files, "max_files"),
        max_bytes_per_file=_positive_int(max_bytes_per_file, "max_bytes_per_file"),
    )


def _positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}_integer_required")
    if value <= 0:
        raise ValueError(f"{field_name}_positive_required")
    return value


def _collect_files(
    *,
    repository_root: Path,
    relative_paths: list[str],
    patterns: list[str],
    max_files: int,
) -> list[Path]:
    collected: list[Path] = []
    for relative_path in relative_paths:
        base_path = _resolve_repository_relative_path(repository_root, relative_path)
        candidates = [base_path] if base_path.is_file() else _iter_repository_files(base_path)
        for candidate in candidates:
            if _is_internal_repository_path(candidate):
                continue
            relative_candidate = candidate.relative_to(repository_root).as_posix()
            if any(fnmatch.fnmatch(relative_candidate, pattern) for pattern in patterns):
                collected.append(candidate)
    unique_sorted = sorted(set(collected), key=lambda path: path.relative_to(repository_root).as_posix())
    return unique_sorted[:max_files]


def _resolve_repository_relative_path(repository_root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("path_boundary_violation")
    resolved = (repository_root / relative_path).resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError("path_boundary_violation") from exc
    if not resolved.exists():
        raise ValueError("path_not_found")
    return resolved


def _iter_repository_files(base_path: Path) -> Iterable[Path]:
    if not base_path.is_dir():
        return ()
    return (path for path in base_path.rglob("*") if path.is_file())


def _is_internal_repository_path(path: Path) -> bool:
    return any(part in {".git", ".hg", ".svn", "__pycache__"} for part in path.parts)


def _inspect_file(
    *,
    repository_root: Path,
    file_path: Path,
    query: str,
    max_bytes_per_file: int,
) -> dict[str, Any]:
    raw_bytes = file_path.read_bytes()
    truncated = len(raw_bytes) > max_bytes_per_file
    bounded_bytes = raw_bytes[:max_bytes_per_file]
    try:
        text = bounded_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = bounded_bytes.decode("utf-8", errors="replace")
    matches = _line_matches(text, query)
    return {
        "relative_path": file_path.relative_to(repository_root).as_posix(),
        "size_bytes": len(raw_bytes),
        "content_hash": canonical_hash(raw_bytes.hex()),
        "truncated": truncated,
        "matches": matches,
    }


def _line_matches(text: str, query: str) -> list[dict[str, Any]]:
    if not query:
        return []
    findings: list[dict[str, Any]] = []
    query_lower = query.lower()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if query_lower in line.lower():
            findings.append(
                {
                    "line": line_number,
                    "excerpt": _redacted_excerpt(line),
                }
            )
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
    return result


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("text_value_required")
    return value.strip()
