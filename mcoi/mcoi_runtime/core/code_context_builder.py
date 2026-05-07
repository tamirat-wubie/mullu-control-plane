"""Purpose: build minimal governed code context bundles from RepoMap.
Governance scope: affected-file validation, dependency/test expansion, symbol
    selection, risk inclusion, token estimates, and context receipts.
Dependencies: code_context and code_intelligence contracts plus hashlib.
Invariants:
  - Context selection is read-only and never inspects filesystem content.
  - Affected files must already exist in the provided RepoMap.
  - Selection reasons are explicit and deterministic.
  - Bundle estimates are bounded approximations, not provider invoices.
  - Receipts bind bundle identity to selected evidence without execution power.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import PurePosixPath
from typing import Mapping, Sequence

from mcoi_runtime.contracts.code_context import (
    CodeContextBundle,
    CodeContextReceipt,
    CodeContextRequest,
    ContextEstimate,
    ContextFileSelection,
)
from mcoi_runtime.contracts.code_intelligence import (
    CodeSymbol,
    CodeSymbolKind,
    FileRiskAssessment,
    RepoMap,
)
from mcoi_runtime.core.code_intelligence import assess_file_risk


class CodeContextBuilderError(RuntimeError):
    """Raised when a context bundle cannot be built from the requested boundary."""


_PRIMARY_SYMBOL_KINDS: frozenset[CodeSymbolKind] = frozenset(
    {
        CodeSymbolKind.FASTAPI_ROUTE,
        CodeSymbolKind.PYDANTIC_SCHEMA,
        CodeSymbolKind.DATACLASS_SCHEMA,
        CodeSymbolKind.CLASS,
        CodeSymbolKind.FUNCTION,
        CodeSymbolKind.ASYNC_FUNCTION,
        CodeSymbolKind.METHOD,
        CodeSymbolKind.ASYNC_METHOD,
        CodeSymbolKind.MODULE,
    }
)
_KIND_PRIORITY: Mapping[CodeSymbolKind, int] = {
    CodeSymbolKind.FASTAPI_ROUTE: 0,
    CodeSymbolKind.PYDANTIC_SCHEMA: 1,
    CodeSymbolKind.DATACLASS_SCHEMA: 1,
    CodeSymbolKind.CLASS: 2,
    CodeSymbolKind.FUNCTION: 3,
    CodeSymbolKind.ASYNC_FUNCTION: 3,
    CodeSymbolKind.METHOD: 4,
    CodeSymbolKind.ASYNC_METHOD: 4,
    CodeSymbolKind.MODULE: 5,
}
_DEFAULT_COST_MICROUSD_PER_1K_INPUT_TOKENS = 100
_MODEL_COST_MICROUSD_PER_1K_INPUT_TOKENS: Mapping[str, int] = {
    "unspecified": _DEFAULT_COST_MICROUSD_PER_1K_INPUT_TOKENS,
    "cheap": 20,
    "fast": 50,
    "strong": 300,
    "coding": 500,
}


def build_code_context(repo_map: RepoMap, request: CodeContextRequest) -> CodeContextBundle:
    """Build a prompt-ready context bundle from a repository map and request.

    Error contract:
      - Raises ValueError when inputs are not typed contract records.
      - Raises CodeContextBuilderError when an affected file is absent from RepoMap.
    """
    if not isinstance(repo_map, RepoMap):
        raise ValueError("repo_map must be a RepoMap")
    if not isinstance(request, CodeContextRequest):
        raise ValueError("request must be a CodeContextRequest")

    repo_files = frozenset(repo_map.files)
    affected_files = tuple(sorted({_normalize_path(path) for path in request.affected_files}))
    missing_files = tuple(path for path in affected_files if path not in repo_files)
    if missing_files:
        raise CodeContextBuilderError(
            f"affected files are absent from RepoMap: {', '.join(missing_files)}"
        )

    selected_tests = _select_tests(repo_map, affected_files, request.max_test_count)
    selected_file_reasons = _select_files(repo_map, affected_files, selected_tests)
    selected_file_paths = frozenset(selection.file_path for selection in selected_file_reasons)
    selected_edges = _select_dependency_edges(repo_map, selected_file_paths, request.max_dependency_edges)
    selected_symbols = _select_symbols(repo_map, selected_file_paths, request.max_symbol_count)
    risk_assessments = _select_risk_assessments(repo_map, selected_file_paths, selected_symbols)
    estimate = _estimate_context(request, selected_file_reasons, selected_symbols, selected_tests, selected_edges, risk_assessments)
    bundle_id = _bundle_id(
        repo_map.repository,
        repo_map.commit_sha,
        request.task_summary,
        tuple(selection.file_path for selection in selected_file_reasons),
        selected_tests,
        selected_edges,
    )

    return CodeContextBundle(
        bundle_id=bundle_id,
        repository=repo_map.repository,
        commit_sha=repo_map.commit_sha,
        task_summary=request.task_summary,
        selected_files=selected_file_reasons,
        selected_symbols=selected_symbols,
        selected_tests=selected_tests,
        dependency_edges=selected_edges,
        acceptance_criteria=request.acceptance_criteria,
        risk_assessments=risk_assessments,
        estimate=estimate,
        evidence_refs=(
            f"repo:{repo_map.repository}",
            f"commit:{repo_map.commit_sha}",
            f"affected_files:{len(affected_files)}",
            f"selected_files:{len(selected_file_reasons)}",
            f"selected_symbols:{len(selected_symbols)}",
            f"selected_tests:{len(selected_tests)}",
        ),
        metadata={
            "target_model": request.target_model,
            "selection_algorithm": "affected_plus_one_hop_dependencies_plus_tests_v1",
        },
    )


def create_code_context_receipt(bundle: CodeContextBundle) -> CodeContextReceipt:
    """Create a stable read-only receipt for a context bundle."""
    receipt_material = "|".join(
        (
            bundle.bundle_id,
            bundle.repository,
            bundle.commit_sha,
            str(len(bundle.selected_files)),
            str(len(bundle.selected_symbols)),
            str(len(bundle.selected_tests)),
            str(bundle.estimate.token_estimate),
        )
    )
    return CodeContextReceipt(
        receipt_id=f"code-context-{sha256(receipt_material.encode('utf-8')).hexdigest()[:16]}",
        bundle_id=bundle.bundle_id,
        repository=bundle.repository,
        commit_sha=bundle.commit_sha,
        selected_file_count=len(bundle.selected_files),
        selected_symbol_count=len(bundle.selected_symbols),
        selected_test_count=len(bundle.selected_tests),
        dependency_edge_count=len(bundle.dependency_edges),
        token_estimate=bundle.estimate.token_estimate,
        cost_microusd_estimate=bundle.estimate.cost_microusd_estimate,
        evidence_refs=(
            f"bundle:{bundle.bundle_id}",
            f"repo:{bundle.repository}",
            f"commit:{bundle.commit_sha}",
        ),
    )


def _select_files(
    repo_map: RepoMap,
    affected_files: Sequence[str],
    selected_tests: Sequence[str],
) -> tuple[ContextFileSelection, ...]:
    selections: dict[str, ContextFileSelection] = {}
    affected_set = frozenset(affected_files)
    selected_test_set = frozenset(selected_tests)
    for path in affected_files:
        selections[path] = ContextFileSelection(file_path=path, reason="affected_file", distance=0)

    for test_path in selected_tests:
        selections.setdefault(
            test_path,
            ContextFileSelection(file_path=test_path, reason="mapped_test", distance=1),
        )

    for source_path, target_path in repo_map.dependency_edges:
        if (
            source_path in affected_set
            and not target_path.startswith("external:")
            and (not _is_test_path(target_path) or target_path in selected_test_set)
        ):
            selections.setdefault(
                target_path,
                ContextFileSelection(file_path=target_path, reason="direct_dependency", distance=1),
            )
        if (
            target_path in affected_set
            and not source_path.startswith("external:")
            and (not _is_test_path(source_path) or source_path in selected_test_set)
        ):
            selections.setdefault(
                source_path,
                ContextFileSelection(file_path=source_path, reason="reverse_dependent", distance=1),
            )

    return tuple(sorted(selections.values(), key=lambda item: (item.distance, item.file_path, item.reason)))


def _select_tests(repo_map: RepoMap, affected_files: Sequence[str], max_test_count: int) -> tuple[str, ...]:
    tests: set[str] = set()
    for path in affected_files:
        tests.update(repo_map.test_map.source_to_tests.get(path, ()))
    return tuple(sorted(tests)[:max_test_count])


def _select_dependency_edges(
    repo_map: RepoMap,
    selected_file_paths: frozenset[str],
    max_dependency_edges: int,
) -> tuple[tuple[str, str], ...]:
    edges = tuple(
        sorted(
            edge
            for edge in repo_map.dependency_edges
            if edge[0] in selected_file_paths or edge[1] in selected_file_paths
        )
    )
    return edges[:max_dependency_edges]


def _select_symbols(
    repo_map: RepoMap,
    selected_file_paths: frozenset[str],
    max_symbol_count: int,
) -> tuple[CodeSymbol, ...]:
    symbols = tuple(
        symbol
        for symbol in repo_map.symbols
        if symbol.file_path in selected_file_paths and symbol.kind in _PRIMARY_SYMBOL_KINDS
    )
    ranked_symbols = tuple(
        sorted(
            symbols,
            key=lambda symbol: (
                _KIND_PRIORITY[symbol.kind],
                0 if symbol.referenced_by else 1,
                symbol.file_path,
                symbol.line_start,
                symbol.name,
            ),
        )
    )
    return ranked_symbols[:max_symbol_count]


def _select_risk_assessments(
    repo_map: RepoMap,
    selected_file_paths: frozenset[str],
    selected_symbols: Sequence[CodeSymbol],
) -> tuple[FileRiskAssessment, ...]:
    symbol_map: dict[str, list[CodeSymbol]] = {}
    for symbol in selected_symbols:
        symbol_map.setdefault(symbol.file_path, []).append(symbol)
    existing = {
        assessment.file_path: assessment
        for assessment in repo_map.risk_assessments
        if assessment.file_path in selected_file_paths
    }
    assessments = tuple(
        existing.get(path) or assess_file_risk(path, tuple(symbol_map.get(path, ())))
        for path in sorted(selected_file_paths)
    )
    return assessments


def _estimate_context(
    request: CodeContextRequest,
    selected_files: Sequence[ContextFileSelection],
    selected_symbols: Sequence[CodeSymbol],
    selected_tests: Sequence[str],
    dependency_edges: Sequence[tuple[str, str]],
    risk_assessments: Sequence[FileRiskAssessment],
) -> ContextEstimate:
    estimate_text_parts: list[str] = [
        request.task_summary,
        *request.acceptance_criteria,
        *(f"{selection.file_path}:{selection.reason}:{selection.distance}" for selection in selected_files),
        *(f"{symbol.file_path}:{symbol.kind.value}:{symbol.name}:{symbol.line_start}-{symbol.line_end}" for symbol in selected_symbols),
        *selected_tests,
        *(f"{source}->{target}" for source, target in dependency_edges),
        *(f"{assessment.file_path}:{assessment.risk.value}:{assessment.score}" for assessment in risk_assessments),
    ]
    character_count = sum(len(part) for part in estimate_text_parts)
    token_estimate = max(1, (character_count + 3) // 4)
    cost_rate = _cost_rate_for_request(request)
    cost_microusd_estimate = (token_estimate * cost_rate + 999) // 1000
    return ContextEstimate(
        token_estimate=token_estimate,
        cost_microusd_estimate=cost_microusd_estimate,
        estimation_method=(
            "ceil(total_context_characters/4); "
            f"cost_rate={cost_rate}_microusd_per_1k_input_tokens"
        ),
    )


def _cost_rate_for_request(request: CodeContextRequest) -> int:
    metadata_rate = request.metadata.get("input_cost_microusd_per_1k")
    if isinstance(metadata_rate, int) and not isinstance(metadata_rate, bool) and metadata_rate >= 0:
        return metadata_rate
    return _MODEL_COST_MICROUSD_PER_1K_INPUT_TOKENS.get(
        request.target_model.lower(),
        _DEFAULT_COST_MICROUSD_PER_1K_INPUT_TOKENS,
    )


def _bundle_id(
    repository: str,
    commit_sha: str,
    task_summary: str,
    selected_files: Sequence[str],
    selected_tests: Sequence[str],
    dependency_edges: Sequence[tuple[str, str]],
) -> str:
    material = "|".join(
        (
            repository,
            commit_sha,
            task_summary,
            ",".join(selected_files),
            ",".join(selected_tests),
            ",".join(f"{source}->{target}" for source, target in dependency_edges),
        )
    )
    return f"ctx-{sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        raise ValueError("path must be non-empty")
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ValueError("path must stay inside repository root")
    return normalized


def _is_test_path(path: str) -> bool:
    normalized = _normalize_path(path)
    parts = tuple(part.lower() for part in normalized.split("/"))
    file_name = parts[-1]
    return "tests" in parts or file_name.startswith("test_") or file_name.endswith("_test.py")
