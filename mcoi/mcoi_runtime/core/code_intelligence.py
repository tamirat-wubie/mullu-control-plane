"""Purpose: read-only repository intelligence for governed software work.
Governance scope: repository file inventory, Python AST symbol extraction,
    dependency edges, source-test mapping, risk scoring, and receipt emission.
Dependencies: code_intelligence contracts plus Python ast, pathlib, os,
    subprocess, dataclasses, hashlib, and standard typing.
Invariants:
  - Indexing is read-only and never executes repository code.
  - File paths are emitted as repository-relative POSIX strings.
  - Python syntax and file-read failures fail closed with causal context.
  - Dependency, test, and risk relationships are deterministic and sorted.
  - Receipts summarize evidence but do not grant execution authority.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Mapping, Sequence

from mcoi_runtime.contracts.code_intelligence import (
    CodeFileRisk,
    CodeSymbol,
    CodeSymbolKind,
    FileRiskAssessment,
    RepoIntelligenceReceipt,
    RepoMap,
    TestMap,
)


class CodeIntelligenceError(RuntimeError):
    """Raised when repository indexing cannot produce a complete read-only map."""


_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tmp",
        ".tmp_test_outputs",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "tmp",
        "venv",
    }
)
_SKIP_FILE_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".pyd")
_PYTHON_SUFFIXES: tuple[str, ...] = (".py", ".pyi")
_HTTP_ROUTE_DECORATORS: Mapping[str, tuple[str, ...]] = {
    "get": ("GET",),
    "post": ("POST",),
    "put": ("PUT",),
    "patch": ("PATCH",),
    "delete": ("DELETE",),
    "options": ("OPTIONS",),
    "head": ("HEAD",),
    "websocket": ("WEBSOCKET",),
}
_SCHEMA_SYMBOL_KINDS: frozenset[CodeSymbolKind] = frozenset(
    {CodeSymbolKind.PYDANTIC_SCHEMA, CodeSymbolKind.DATACLASS_SCHEMA}
)


def build_repo_map(
    repository_root: str | Path,
    *,
    repository_name: str | None = None,
    commit_sha: str | None = None,
) -> RepoMap:
    """Build a deterministic read-only map for a repository.

    Error contract:
      - Raises ValueError when the repository root is absent or not a directory.
      - Raises CodeIntelligenceError when a Python file cannot be read or parsed.
      - Falls back to a filesystem walk only when git file discovery is unavailable.
    """
    root_path = _require_repository_root(repository_root)
    repository_files = _discover_repository_files(root_path)
    python_files = tuple(path for path in repository_files if path.endswith(_PYTHON_SUFFIXES))
    module_path_index = _build_module_path_index(python_files)
    parsed_modules = {
        relative_path: _parse_python_file(root_path, relative_path)
        for relative_path in python_files
    }
    file_imports = {
        relative_path: _collect_imports(parsed_tree, relative_path, module_path_index)
        for relative_path, parsed_tree in parsed_modules.items()
    }
    symbols_by_file = {
        relative_path: tuple(_collect_symbols(relative_path, parsed_tree, file_imports[relative_path]))
        for relative_path, parsed_tree in parsed_modules.items()
    }
    symbols = _attach_references(parsed_modules, symbols_by_file)
    dependency_edges = _build_dependency_edges(file_imports, module_path_index)
    test_map = _build_test_map(repository_files, file_imports, module_path_index)
    risk_assessments = tuple(
        assess_file_risk(relative_path, tuple(symbols_by_file.get(relative_path, ())))
        for relative_path in repository_files
    )

    return RepoMap(
        repository=repository_name or root_path.name,
        commit_sha=commit_sha or _resolve_commit_sha(root_path),
        files=repository_files,
        symbols=symbols,
        test_map=test_map,
        dependency_edges=dependency_edges,
        risk_assessments=risk_assessments,
    )


def create_repo_intelligence_receipt(repo_map: RepoMap) -> RepoIntelligenceReceipt:
    """Create a stable read-only receipt for a repository map."""
    risk_counts: dict[str, int] = {risk.value: 0 for risk in CodeFileRisk}
    for assessment in repo_map.risk_assessments:
        risk_counts[assessment.risk.value] = risk_counts.get(assessment.risk.value, 0) + 1
    route_count = sum(1 for symbol in repo_map.symbols if symbol.kind is CodeSymbolKind.FASTAPI_ROUTE)
    schema_count = sum(1 for symbol in repo_map.symbols if symbol.kind in _SCHEMA_SYMBOL_KINDS)
    source_mapping_count = len(repo_map.test_map.source_to_tests)
    receipt_material = "|".join(
        (
            repo_map.repository,
            repo_map.commit_sha,
            str(len(repo_map.files)),
            str(len(repo_map.symbols)),
            str(len(repo_map.dependency_edges)),
            str(source_mapping_count),
        )
    )
    return RepoIntelligenceReceipt(
        receipt_id=f"repo-intel-{sha256(receipt_material.encode('utf-8')).hexdigest()[:16]}",
        repository=repo_map.repository,
        commit_sha=repo_map.commit_sha,
        file_count=len(repo_map.files),
        symbol_count=len(repo_map.symbols),
        test_mapping_count=source_mapping_count,
        dependency_edge_count=len(repo_map.dependency_edges),
        route_count=route_count,
        schema_count=schema_count,
        risk_counts=risk_counts,
        evidence_refs=(
            f"repo:{repo_map.repository}",
            f"commit:{repo_map.commit_sha}",
            f"files:{len(repo_map.files)}",
            f"symbols:{len(repo_map.symbols)}",
        ),
    )


def assess_changed_file_risks(repo_map: RepoMap, changed_files: Sequence[str]) -> tuple[FileRiskAssessment, ...]:
    """Assess changed files using existing RepoMap assessments when available."""
    existing_assessments = {
        assessment.file_path: assessment
        for assessment in repo_map.risk_assessments
    }
    normalized_paths = tuple(sorted({_normalize_relative_path(path) for path in changed_files}))
    return tuple(
        existing_assessments.get(relative_path) or assess_file_risk(relative_path, ())
        for relative_path in normalized_paths
    )


def assess_file_risk(
    relative_path: str,
    symbols: Sequence[CodeSymbol] = (),
) -> FileRiskAssessment:
    """Assign a deterministic file risk score with causal reasons."""
    path_text = _normalize_relative_path(relative_path)
    path_lower = path_text.lower()
    reasons: list[str] = []
    score = 15

    if path_lower.startswith(("docs/", "tests/")) or "/tests/" in path_lower:
        reasons.append("test_or_documentation_surface")
        score = max(score, 20)
    if path_lower.endswith((".json", ".yaml", ".yml", ".toml", ".ini")):
        reasons.append("configuration_surface")
        score = max(score, 30)
    if path_lower.startswith("schemas/") or path_lower.endswith(".schema.json") or "/contracts/" in path_lower:
        reasons.append("schema_or_contract_surface")
        score = max(score, 75)
    if "migration" in path_lower or path_lower.startswith("migrations/"):
        reasons.append("migration_surface")
        score = max(score, 90)
    if any(token in path_lower for token in ("approval", "authority", "rbac", "policy", "governance")):
        reasons.append("authority_or_policy_surface")
        score = max(score, 92)
    if any(token in path_lower for token in ("secret", "credential", "token", "keyring")):
        reasons.append("secret_or_credential_surface")
        score = max(score, 95)
    if any(symbol.kind is CodeSymbolKind.FASTAPI_ROUTE for symbol in symbols):
        reasons.append("route_surface")
        score = max(score, 65)
    if any(symbol.kind in _SCHEMA_SYMBOL_KINDS for symbol in symbols):
        reasons.append("typed_schema_surface")
        score = max(score, 70)
    if path_lower.endswith(_PYTHON_SUFFIXES) and not reasons:
        reasons.append("ordinary_python_source_surface")
        score = max(score, 35)
    if not reasons:
        reasons.append("ordinary_repository_surface")

    if score >= 90:
        risk = CodeFileRisk.CRITICAL
    elif score >= 70:
        risk = CodeFileRisk.HIGH
    elif score >= 40:
        risk = CodeFileRisk.MEDIUM
    else:
        risk = CodeFileRisk.LOW

    return FileRiskAssessment(
        file_path=path_text,
        risk=risk,
        score=score,
        reasons=tuple(sorted(set(reasons))),
    )


def _require_repository_root(repository_root: str | Path) -> Path:
    root_path = Path(repository_root).resolve()
    if not root_path.exists():
        raise ValueError("repository_root must exist")
    if not root_path.is_dir():
        raise ValueError("repository_root must be a directory")
    return root_path


def _discover_repository_files(root_path: Path) -> tuple[str, ...]:
    git_files = _git_file_list(root_path)
    if git_files is not None:
        return git_files

    discovered_files: list[str] = []

    def fail_on_walk_error(error: OSError) -> None:
        raise CodeIntelligenceError(f"failed to walk repository path: {error}") from error

    for current_root, directory_names, file_names in os.walk(root_path, onerror=fail_on_walk_error):
        directory_names[:] = sorted(
            directory_name
            for directory_name in directory_names
            if directory_name not in _SKIP_DIR_NAMES
        )
        current_path = Path(current_root)
        for file_name in sorted(file_names):
            absolute_file_path = current_path / file_name
            relative_path = _relative_posix_path(root_path, absolute_file_path)
            if _should_index_relative_path(relative_path):
                discovered_files.append(relative_path)
    return tuple(sorted(discovered_files))


# Bound every git subprocess so a hung git cannot hang code indexing indefinitely.
_GIT_TIMEOUT_SECONDS = 30


def _git_file_list(root_path: Path) -> tuple[str, ...] | None:
    try:
        process = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if process.returncode != 0:
        return None
    relative_paths = tuple(
        sorted(
            {
                _normalize_relative_path(line.strip())
                for line in process.stdout.splitlines()
                if line.strip() and _should_index_relative_path(line.strip())
            }
        )
    )
    return relative_paths or None


def _resolve_commit_sha(root_path: Path) -> str:
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if process.returncode != 0:
        return "unknown"
    commit_sha = process.stdout.strip()
    return commit_sha or "unknown"


def _should_index_relative_path(relative_path: str) -> bool:
    normalized_path = _normalize_relative_path(relative_path)
    path_parts = PurePosixPath(normalized_path).parts
    if any(part in _SKIP_DIR_NAMES for part in path_parts[:-1]):
        return False
    return not normalized_path.endswith(_SKIP_FILE_SUFFIXES)


def _relative_posix_path(root_path: Path, absolute_file_path: Path) -> str:
    return _normalize_relative_path(absolute_file_path.relative_to(root_path).as_posix())


def _normalize_relative_path(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        raise ValueError("relative path must be non-empty")
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ValueError("relative path must stay inside repository root")
    return normalized


def _parse_python_file(root_path: Path, relative_path: str) -> ast.AST:
    file_path = root_path / relative_path
    try:
        source_text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CodeIntelligenceError(f"failed to read Python file {relative_path}: {exc}") from exc
    try:
        return ast.parse(source_text, filename=relative_path)
    except SyntaxError as exc:
        raise CodeIntelligenceError(
            f"failed to parse Python file {relative_path} at line {exc.lineno}: {exc.msg}"
        ) from exc


def _build_module_path_index(python_files: Sequence[str]) -> Mapping[str, str]:
    module_paths: dict[str, str] = {}
    for relative_path in python_files:
        module_name = _module_name_from_path(relative_path)
        if module_name:
            module_paths[module_name] = relative_path
    return module_paths


def _module_name_from_path(relative_path: str) -> str:
    normalized_path = _normalize_relative_path(relative_path)
    if not normalized_path.endswith(_PYTHON_SUFFIXES):
        return ""
    without_suffix = normalized_path.rsplit(".", 1)[0]
    path_parts = without_suffix.split("/")
    if path_parts[-1] == "__init__":
        path_parts = path_parts[:-1]
    return ".".join(part for part in path_parts if part)


def _collect_imports(
    parsed_tree: ast.AST,
    relative_path: str,
    module_path_index: Mapping[str, str],
) -> tuple[str, ...]:
    imports: set[str] = set()
    for node in ast.walk(parsed_tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.update(_import_from_module_names(node, relative_path, module_path_index))
    return tuple(sorted(imports))


def _import_from_module_names(
    node: ast.ImportFrom,
    relative_path: str,
    module_path_index: Mapping[str, str],
) -> tuple[str, ...]:
    base_module = _resolve_import_from_base(node, relative_path)
    if not base_module:
        return tuple(sorted(alias.name for alias in node.names if alias.name != "*"))
    module_names: set[str] = set()
    for alias in node.names:
        candidate_module = f"{base_module}.{alias.name}"
        if candidate_module in module_path_index:
            module_names.add(candidate_module)
        else:
            module_names.add(base_module)
    return tuple(sorted(module_names))


def _resolve_import_from_base(node: ast.ImportFrom, relative_path: str) -> str:
    if node.level == 0:
        return node.module or ""

    current_module = _module_name_from_path(relative_path)
    current_parts = current_module.split(".") if current_module else []
    if relative_path.endswith("__init__.py"):
        package_parts = current_parts
    else:
        package_parts = current_parts[:-1]
    if node.level > 1:
        package_parts = package_parts[: max(0, len(package_parts) - (node.level - 1))]
    module_tail = (node.module or "").split(".") if node.module else []
    return ".".join(part for part in (*package_parts, *module_tail) if part)


def _collect_symbols(
    relative_path: str,
    parsed_tree: ast.AST,
    imports: Sequence[str],
) -> tuple[CodeSymbol, ...]:
    collector = _SymbolCollector(relative_path, tuple(imports))
    collector.visit(parsed_tree)
    module_line_end = getattr(parsed_tree, "end_lineno", 1) or 1
    module_symbol = CodeSymbol(
        name=_module_name_from_path(relative_path) or relative_path,
        kind=CodeSymbolKind.MODULE,
        file_path=relative_path,
        line_start=1,
        line_end=max(1, module_line_end),
        imports=tuple(imports),
        referenced_by=(),
    )
    return (module_symbol, *collector.symbols)


class _SymbolCollector(ast.NodeVisitor):
    """AST visitor for first-pass Python symbols."""

    def __init__(self, relative_path: str, imports: tuple[str, ...]) -> None:
        self.relative_path = relative_path
        self.imports = imports
        self.symbols: list[CodeSymbol] = []
        self.scope: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified_name = ".".join((*self.scope, node.name))
        self.symbols.append(
            CodeSymbol(
                name=qualified_name,
                kind=_class_symbol_kind(node),
                file_path=self.relative_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno) or node.lineno,
                imports=self.imports,
                referenced_by=(),
            )
        )
        self.scope.append(node.name)
        for child_node in node.body:
            if isinstance(child_node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child_node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool) -> None:
        qualified_name = ".".join((*self.scope, node.name))
        if self.scope:
            kind = CodeSymbolKind.ASYNC_METHOD if is_async else CodeSymbolKind.METHOD
        else:
            kind = CodeSymbolKind.ASYNC_FUNCTION if is_async else CodeSymbolKind.FUNCTION
        self.symbols.append(
            CodeSymbol(
                name=qualified_name,
                kind=kind,
                file_path=self.relative_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno) or node.lineno,
                imports=self.imports,
                referenced_by=(),
            )
        )
        for route_method, route_path in _route_decorators(node):
            self.symbols.append(
                CodeSymbol(
                    name=f"{route_method} {route_path} -> {qualified_name}",
                    kind=CodeSymbolKind.FASTAPI_ROUTE,
                    file_path=self.relative_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno) or node.lineno,
                    imports=self.imports,
                    referenced_by=(),
                    metadata={
                        "handler": qualified_name,
                        "http_method": route_method,
                        "route_path": route_path,
                    },
                )
            )


def _class_symbol_kind(node: ast.ClassDef) -> CodeSymbolKind:
    base_names = {_node_name(base) for base in node.bases}
    decorator_names = {_node_name(decorator) for decorator in node.decorator_list}
    if "BaseModel" in base_names or "pydantic.BaseModel" in base_names:
        return CodeSymbolKind.PYDANTIC_SCHEMA
    if "dataclass" in decorator_names or "dataclasses.dataclass" in decorator_names:
        return CodeSymbolKind.DATACLASS_SCHEMA
    return CodeSymbolKind.CLASS


def _route_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[tuple[str, str], ...]:
    route_pairs: list[tuple[str, str]] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        decorator_name = _node_name(decorator.func)
        decorator_tail = decorator_name.rsplit(".", 1)[-1].lower()
        route_path = _route_path_from_call(decorator)
        if route_path is None:
            continue
        if decorator_tail in _HTTP_ROUTE_DECORATORS:
            for method_name in _HTTP_ROUTE_DECORATORS[decorator_tail]:
                route_pairs.append((method_name, route_path))
        elif decorator_tail in {"route", "api_route"}:
            for method_name in _route_methods_from_call(decorator):
                route_pairs.append((method_name, route_path))
    return tuple(route_pairs)


def _route_path_from_call(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    for keyword in node.keywords:
        if keyword.arg in {"path", "rule"} and isinstance(keyword.value, ast.Constant):
            if isinstance(keyword.value.value, str):
                return keyword.value.value
    return None


def _route_methods_from_call(node: ast.Call) -> tuple[str, ...]:
    for keyword in node.keywords:
        if keyword.arg != "methods":
            continue
        value = keyword.value
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            methods = tuple(
                element.value.upper()
                for element in value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
            return methods or ("ANY",)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return (value.value.upper(),)
    return ("ANY",)


def _node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = _node_name(node.value)
        return f"{parent_name}.{node.attr}" if parent_name else node.attr
    if isinstance(node, ast.Call):
        return _node_name(node.func)
    if isinstance(node, ast.Subscript):
        return _node_name(node.value)
    return ""


def _attach_references(
    parsed_modules: Mapping[str, ast.AST],
    symbols_by_file: Mapping[str, tuple[CodeSymbol, ...]],
) -> tuple[CodeSymbol, ...]:
    identifiers_by_file = {
        relative_path: _collect_reference_identifiers(parsed_tree)
        for relative_path, parsed_tree in parsed_modules.items()
    }
    all_symbols = tuple(
        symbol
        for relative_symbols in symbols_by_file.values()
        for symbol in relative_symbols
    )
    attached_symbols: list[CodeSymbol] = []
    for symbol in all_symbols:
        if symbol.kind is CodeSymbolKind.FASTAPI_ROUTE:
            attached_symbols.append(symbol)
            continue
        base_name = symbol.name.rsplit(".", 1)[-1]
        referencing_files = tuple(
            sorted(
                relative_path
                for relative_path, identifiers in identifiers_by_file.items()
                if relative_path != symbol.file_path and base_name in identifiers
            )
        )
        attached_symbols.append(replace(symbol, referenced_by=referencing_files))
    return tuple(sorted(attached_symbols, key=lambda item: (item.file_path, item.line_start, item.name, item.kind.value)))


def _collect_reference_identifiers(parsed_tree: ast.AST) -> frozenset[str]:
    identifiers: set[str] = set()
    for node in ast.walk(parsed_tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    return frozenset(identifiers)


def _build_dependency_edges(
    file_imports: Mapping[str, tuple[str, ...]],
    module_path_index: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    edges: set[tuple[str, str]] = set()
    for source_file, imports in file_imports.items():
        for imported_module in imports:
            target = _resolve_import_to_target(imported_module, module_path_index)
            if target != source_file:
                edges.add((source_file, target))
    return tuple(sorted(edges))


def _resolve_import_to_target(imported_module: str, module_path_index: Mapping[str, str]) -> str:
    if imported_module in module_path_index:
        return module_path_index[imported_module]
    parts = imported_module.split(".")
    while parts:
        candidate_module = ".".join(parts)
        if candidate_module in module_path_index:
            return module_path_index[candidate_module]
        parts.pop()
    external_root = imported_module.split(".", 1)[0] if imported_module else "unknown"
    return f"external:{external_root}"


def _build_test_map(
    repository_files: Sequence[str],
    file_imports: Mapping[str, tuple[str, ...]],
    module_path_index: Mapping[str, str],
) -> TestMap:
    source_files = tuple(path for path in repository_files if path.endswith(_PYTHON_SUFFIXES) and not _is_test_file(path))
    test_files = tuple(path for path in repository_files if path.endswith(_PYTHON_SUFFIXES) and _is_test_file(path))
    source_to_tests: dict[str, set[str]] = defaultdict(set)
    test_to_sources: dict[str, set[str]] = defaultdict(set)

    for test_file in test_files:
        mapped_sources: set[str] = set()
        for imported_module in file_imports.get(test_file, ()):
            target_path = _resolve_import_to_target(imported_module, module_path_index)
            if not target_path.startswith("external:") and not _is_test_file(target_path):
                mapped_sources.add(target_path)
        mapped_sources.update(_filename_heuristic_sources(test_file, source_files))
        for source_file in mapped_sources:
            source_to_tests[source_file].add(test_file)
            test_to_sources[test_file].add(source_file)

    return TestMap(
        source_to_tests={
            source_file: tuple(sorted(test_files_for_source))
            for source_file, test_files_for_source in sorted(source_to_tests.items())
        },
        test_to_sources={
            test_file: tuple(sorted(source_files_for_test))
            for test_file, source_files_for_test in sorted(test_to_sources.items())
        },
    )


def _is_test_file(relative_path: str) -> bool:
    normalized_path = _normalize_relative_path(relative_path)
    path_parts = PurePosixPath(normalized_path).parts
    file_name = path_parts[-1]
    return (
        "tests" in path_parts
        or file_name.startswith("test_")
        or file_name.endswith("_test.py")
    )


def _filename_heuristic_sources(test_file: str, source_files: Sequence[str]) -> tuple[str, ...]:
    file_name = PurePosixPath(test_file).name
    if file_name.startswith("test_") and file_name.endswith(".py"):
        source_stem = file_name[5:-3]
    elif file_name.endswith("_test.py"):
        source_stem = file_name[:-8]
    else:
        return ()
    return tuple(
        sorted(
            source_file
            for source_file in source_files
            if PurePosixPath(source_file).stem == source_stem
        )
    )
