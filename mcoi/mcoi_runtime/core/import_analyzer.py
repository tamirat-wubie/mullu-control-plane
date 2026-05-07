"""Phase 4A — Import Cycle Detector & Dependency Analyzer.

Purpose: Static analysis of Python import dependencies to detect circular
    imports, measure import depth, and validate dependency order.
    Uses AST parsing — no actual imports executed.
Governance scope: build-time analysis only — never modifies code.
Dependencies: stdlib (ast, pathlib, os).
Invariants:
  - Analysis is AST-based (no execution side effects).
  - Cycle detection uses DFS with back-edge detection.
  - Results are deterministic for the same source tree.
  - Module names are dot-qualified (e.g., "mcoi_runtime.governance.auth.jwt").
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ImportEdge:
    """A directed import dependency: source imports target."""

    source: str  # e.g., "mcoi_runtime.governance.auth.jwt"
    target: str  # e.g., "mcoi_runtime.contracts.llm"
    is_type_checking: bool = False  # Inside TYPE_CHECKING block
    line_number: int = 0


@dataclass(frozen=True, slots=True)
class ImportCycle:
    """A detected circular import chain."""

    modules: tuple[str, ...]  # Cycle path: A -> B -> C -> A
    length: int

    @property
    def summary(self) -> str:
        return " -> ".join(self.modules)


@dataclass(frozen=True)
class AnalysisResult:
    """Result of import dependency analysis."""

    modules: tuple[str, ...]
    edges: tuple[ImportEdge, ...]
    cycles: tuple[ImportCycle, ...]
    max_depth: int
    module_depths: dict[str, int] = field(default_factory=dict)

    @property
    def has_cycles(self) -> bool:
        return len(self.cycles) > 0

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class ImportAnalyzer:
    """Analyzes Python import dependencies via AST parsing.

    Builds a directed dependency graph from source files, then
    detects cycles and computes import depths.
    """

    def __init__(self, root_package: str = "mcoi_runtime") -> None:
        self._root_package = root_package
        self._edges: list[ImportEdge] = []
        self._modules: set[str] = set()
        self._adjacency: dict[str, set[str]] = {}

    def analyze_directory(self, directory: str | Path) -> AnalysisResult:
        """Analyze all .py files in a directory tree."""
        directory = Path(directory)
        self._edges = []
        self._modules = set()
        self._adjacency = {}

        for py_file in sorted(directory.rglob("*.py")):
            rel = py_file.relative_to(directory.parent)
            module_name = self._path_to_module(rel)
            if module_name and module_name.startswith(self._root_package):
                self._modules.add(module_name)
                self._analyze_file(py_file, module_name)

        # Build adjacency list (excluding TYPE_CHECKING imports)
        for edge in self._edges:
            if not edge.is_type_checking and edge.target in self._modules:
                self._adjacency.setdefault(edge.source, set()).add(edge.target)

        cycles = self._detect_cycles()
        depths = self._compute_depths()
        max_depth = max(depths.values()) if depths else 0

        return AnalysisResult(
            modules=tuple(sorted(self._modules)),
            edges=tuple(self._edges),
            cycles=tuple(cycles),
            max_depth=max_depth,
            module_depths=depths,
        )

    def analyze_module(self, file_path: str | Path, module_name: str) -> list[ImportEdge]:
        """Analyze a single Python file for import edges."""
        self._edges = []
        self._modules = {module_name}
        self._analyze_file(Path(file_path), module_name)
        return list(self._edges)

    def _path_to_module(self, rel_path: Path) -> str:
        """Convert a relative file path to a Python module name."""
        parts = list(rel_path.parts)
        if not parts:
            return ""
        # Remove .py extension
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        # __init__ becomes the package name
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            return ""
        return ".".join(parts)

    def _analyze_file(self, file_path: Path, module_name: str) -> None:
        """Parse a file's AST and extract import edges."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return

        # Detect TYPE_CHECKING blocks
        type_checking_ranges = self._find_type_checking_ranges(tree)

        for node in ast.walk(tree):
            is_tc = any(start <= getattr(node, "lineno", 0) <= end for start, end in type_checking_ranges)

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(self._root_package):
                        self._edges.append(ImportEdge(
                            source=module_name,
                            target=alias.name,
                            is_type_checking=is_tc,
                            line_number=node.lineno,
                        ))

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(self._root_package):
                    self._edges.append(ImportEdge(
                        source=module_name,
                        target=node.module,
                        is_type_checking=is_tc,
                        line_number=node.lineno,
                    ))
                elif node.level and node.level > 0:
                    # Relative import — resolve to absolute
                    resolved = self._resolve_relative(module_name, node.module or "", node.level)
                    if resolved and resolved.startswith(self._root_package):
                        self._edges.append(ImportEdge(
                            source=module_name,
                            target=resolved,
                            is_type_checking=is_tc,
                            line_number=node.lineno,
                        ))

    def _resolve_relative(self, current_module: str, target: str, level: int) -> str:
        """Resolve a relative import to an absolute module name."""
        parts = current_module.split(".")
        # Go up `level` packages
        if level > len(parts):
            return ""
        base = ".".join(parts[:-level]) if level <= len(parts) else ""
        if target:
            return f"{base}.{target}" if base else target
        return base

    def _find_type_checking_ranges(self, tree: ast.Module) -> list[tuple[int, int]]:
        """Find line ranges inside 'if TYPE_CHECKING:' blocks."""
        ranges = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                    start = node.lineno
                    end = max(getattr(n, "end_lineno", start) or start for n in ast.walk(node))
                    ranges.append((start, end))
                elif isinstance(test, ast.Attribute) and getattr(test, "attr", "") == "TYPE_CHECKING":
                    start = node.lineno
                    end = max(getattr(n, "end_lineno", start) or start for n in ast.walk(node))
                    ranges.append((start, end))
        return ranges

    def _detect_cycles(self) -> list[ImportCycle]:
        """Detect all import cycles using DFS with back-edge detection."""
        cycles: list[ImportCycle] = []
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        def dfs(node: str) -> None:
            if node in path_set:
                # Found a cycle
                idx = path.index(node)
                cycle_path = tuple(path[idx:]) + (node,)
                cycles.append(ImportCycle(modules=cycle_path, length=len(cycle_path) - 1))
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in sorted(self._adjacency.get(node, set())):
                dfs(neighbor)
            path.pop()
            path_set.discard(node)

        for module in sorted(self._modules):
            if module not in visited:
                dfs(module)

        return cycles

    def _compute_depths(self) -> dict[str, int]:
        """Compute import depth for each module (longest path from a root)."""
        # Topological-ish depth: modules with no inbound edges are depth 0
        inbound: dict[str, set[str]] = {m: set() for m in self._modules}
        for src, targets in self._adjacency.items():
            for tgt in targets:
                if tgt in inbound:
                    inbound[tgt].add(src)

        depths: dict[str, int] = {}
        # Roots: modules with no inbound edges
        queue = [m for m, deps in inbound.items() if not deps]
        for m in queue:
            depths[m] = 0

        # BFS to compute max depth
        visited = set(queue)
        while queue:
            current = queue.pop(0)
            for neighbor in sorted(self._adjacency.get(current, set())):
                new_depth = depths[current] + 1
                if neighbor not in depths or new_depth > depths[neighbor]:
                    depths[neighbor] = new_depth
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # Assign depth 0 to any unvisited modules
        for m in self._modules:
            if m not in depths:
                depths[m] = 0

        return depths

    def dependency_summary(self, result: AnalysisResult) -> dict[str, Any]:
        """Generate a summary report from analysis results."""
        return {
            "module_count": result.module_count,
            "edge_count": result.edge_count,
            "cycle_count": len(result.cycles),
            "has_cycles": result.has_cycles,
            "max_depth": result.max_depth,
            "cycles": [c.summary for c in result.cycles],
            "depth_distribution": self._depth_distribution(result.module_depths),
        }

    def _depth_distribution(self, depths: dict[str, int]) -> dict[int, int]:
        """Count modules at each depth level."""
        dist: dict[int, int] = {}
        for d in depths.values():
            dist[d] = dist.get(d, 0) + 1
        return dict(sorted(dist.items()))
