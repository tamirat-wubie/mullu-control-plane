"""Gateway code-intelligence operator read model.

Purpose: project repository intelligence and bounded code context receipts into
    a read-only operator surface.
Governance scope: repository map summaries, file risk counts, route/schema
    counts, selected-context receipts, and no-effect software work planning.
Dependencies: MCOI code_intelligence and code_context read-only builders.
Invariants:
  - The surface never returns source file contents.
  - The surface never grants execution, patch, shell, or filesystem mutation authority.
  - Affected files must already exist in the repository map before context selection.
  - Context bundles are bounded by explicit request limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from mcoi_runtime.contracts.code_context import CodeContextRequest
from mcoi_runtime.core.code_context_builder import (
    build_code_context,
    create_code_context_receipt,
)
from mcoi_runtime.core.code_intelligence import (
    build_repo_map,
    create_repo_intelligence_receipt,
)


def build_code_intelligence_operator_read_model(
    *,
    repository_root: str | Path,
    repository_name: str | None = None,
    task_summary: str = "",
    affected_files: Sequence[str] = (),
    max_symbol_count: int = 40,
    max_test_count: int = 20,
    max_dependency_edges: int = 60,
    target_model: str = "unspecified",
) -> dict[str, Any]:
    """Build a read-only repository intelligence projection for operators."""
    repo_map = build_repo_map(
        repository_root,
        repository_name=repository_name,
    )
    repo_receipt = create_repo_intelligence_receipt(repo_map)
    payload: dict[str, Any] = {
        "enabled": True,
        "surface": "read_only_repository_intelligence",
        "raw_source_content_exposed": False,
        "raw_filesystem_write_exposed": False,
        "execution_authority_granted": False,
        "repository": repo_map.repository,
        "commit_sha": repo_map.commit_sha,
        "file_count": len(repo_map.files),
        "symbol_count": len(repo_map.symbols),
        "test_mapping_count": len(repo_map.test_map.source_to_tests),
        "dependency_edge_count": len(repo_map.dependency_edges),
        "route_count": repo_receipt.route_count,
        "schema_count": repo_receipt.schema_count,
        "risk_counts": repo_receipt.to_json_dict()["risk_counts"],
        "repo_receipt": repo_receipt.to_json_dict(),
        "context": None,
    }
    normalized_affected_files = _normalize_affected_files(affected_files)
    if normalized_affected_files:
        context_request = CodeContextRequest(
            task_summary=task_summary.strip() or "Build bounded code context",
            affected_files=normalized_affected_files,
            max_symbol_count=max_symbol_count,
            max_test_count=max_test_count,
            max_dependency_edges=max_dependency_edges,
            target_model=target_model,
        )
        context_bundle = build_code_context(repo_map, context_request)
        context_receipt = create_code_context_receipt(context_bundle)
        payload["context"] = {
            "bundle_id": context_bundle.bundle_id,
            "selected_files": [
                selection.to_json_dict()
                for selection in context_bundle.selected_files
            ],
            "selected_symbols": [
                symbol.to_json_dict()
                for symbol in context_bundle.selected_symbols
            ],
            "selected_tests": list(context_bundle.selected_tests),
            "dependency_edges": [
                {"source": source, "target": target}
                for source, target in context_bundle.dependency_edges
            ],
            "risk_assessments": [
                assessment.to_json_dict()
                for assessment in context_bundle.risk_assessments
            ],
            "estimate": context_bundle.estimate.to_json_dict(),
            "receipt": context_receipt.to_json_dict(),
        }
    return payload


def parse_affected_files(affected_files: str) -> tuple[str, ...]:
    """Parse comma-separated repository-relative affected file paths."""
    return _normalize_affected_files(
        tuple(item for item in affected_files.split(",") if item.strip())
    )


def _normalize_affected_files(affected_files: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for path in affected_files:
        path_text = str(path).replace("\\", "/").strip()
        while path_text.startswith("./"):
            path_text = path_text[2:]
        if path_text:
            normalized.append(path_text)
    return tuple(dict.fromkeys(normalized))
