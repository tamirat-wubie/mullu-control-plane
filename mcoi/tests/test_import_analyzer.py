"""Phase 4A — Import Cycle Detector tests.

Tests: AST-based import analysis, cycle detection, depth computation,
    TYPE_CHECKING awareness, relative import resolution, summary reporting.
"""

import os
import tempfile

import pytest
from mcoi_runtime.core.import_analyzer import (
    AnalysisResult,
    ImportAnalyzer,
    ImportCycle,
    ImportEdge,
)


def _write_file(tmpdir: str, rel_path: str, content: str) -> str:
    full = os.path.join(tmpdir, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return full


# ═══ ImportEdge ═══


class TestImportEdge:
    def test_edge_fields(self):
        edge = ImportEdge(source="a.b", target="a.c", is_type_checking=False, line_number=5)
        assert edge.source == "a.b"
        assert edge.target == "a.c"
        assert edge.line_number == 5

    def test_type_checking_edge(self):
        edge = ImportEdge(source="a", target="b", is_type_checking=True)
        assert edge.is_type_checking


# ═══ ImportCycle ═══


class TestImportCycle:
    def test_cycle_summary(self):
        cycle = ImportCycle(modules=("a", "b", "c", "a"), length=3)
        assert cycle.summary == "a -> b -> c -> a"
        assert cycle.length == 3


# ═══ Single File Analysis ═══


class TestSingleFileAnalysis:
    def test_detect_absolute_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "import pkg.b")
            _write_file(tmpdir, "pkg/b.py", "")
            analyzer = ImportAnalyzer(root_package="pkg")
            edges = analyzer.analyze_module(
                os.path.join(tmpdir, "pkg/a.py"), "pkg.a"
            )
            assert len(edges) == 1
            assert edges[0].target == "pkg.b"

    def test_detect_from_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import something")
            _write_file(tmpdir, "pkg/b.py", "")
            analyzer = ImportAnalyzer(root_package="pkg")
            edges = analyzer.analyze_module(
                os.path.join(tmpdir, "pkg/a.py"), "pkg.a"
            )
            assert len(edges) == 1
            assert edges[0].target == "pkg.b"

    def test_ignore_external_imports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "import os\nimport json\nfrom pathlib import Path")
            analyzer = ImportAnalyzer(root_package="pkg")
            edges = analyzer.analyze_module(
                os.path.join(tmpdir, "pkg/a.py"), "pkg.a"
            )
            assert len(edges) == 0


# ═══ Directory Analysis ═══


class TestDirectoryAnalysis:
    def test_no_cycles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", "X = 1")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert not result.has_cycles

    def test_detects_simple_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", "from pkg.a import Y")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert result.has_cycles
            assert len(result.cycles) >= 1

    def test_detects_transitive_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", "from pkg.c import Y")
            _write_file(tmpdir, "pkg/c.py", "from pkg.a import Z")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert result.has_cycles
            cycle_lengths = [c.length for c in result.cycles]
            assert any(l >= 3 for l in cycle_lengths)

    def test_type_checking_imports_excluded_from_cycles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from pkg.a import Y\n"
            ))
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert not result.has_cycles  # TYPE_CHECKING import excluded

    def test_module_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "")
            _write_file(tmpdir, "pkg/b.py", "")
            _write_file(tmpdir, "pkg/sub/__init__.py", "")
            _write_file(tmpdir, "pkg/sub/c.py", "")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert result.module_count >= 4  # pkg, pkg.a, pkg.b, pkg.sub, pkg.sub.c

    def test_analysis_result_properties(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", "")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert result.module_count >= 2
            assert result.edge_count >= 1
            assert not result.has_cycles


# ═══ Depth Computation ═══


class TestDepthComputation:
    def test_linear_chain_depth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", "from pkg.c import Y")
            _write_file(tmpdir, "pkg/c.py", "")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            assert result.max_depth >= 2


# ═══ Summary Report ═══


class TestSummaryReport:
    def test_summary_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(tmpdir, "pkg/__init__.py", "")
            _write_file(tmpdir, "pkg/a.py", "from pkg.b import X")
            _write_file(tmpdir, "pkg/b.py", "")
            analyzer = ImportAnalyzer(root_package="pkg")
            result = analyzer.analyze_directory(os.path.join(tmpdir, "pkg"))
            summary = analyzer.dependency_summary(result)
            assert "module_count" in summary
            assert "edge_count" in summary
            assert "cycle_count" in summary
            assert "has_cycles" in summary
            assert "max_depth" in summary
            assert "depth_distribution" in summary


# ═══ Real Codebase Analysis ═══


class TestRealCodebase:
    def test_mcoi_runtime_no_import_cycles(self):
        """Verify the actual mcoi_runtime has no import cycles.

        This is the key validation — if this fails, we have a circular
        import that needs to be fixed.
        """
        import mcoi_runtime
        runtime_dir = os.path.dirname(os.path.dirname(mcoi_runtime.__file__))
        mcoi_dir = os.path.join(runtime_dir, "mcoi_runtime")
        if not os.path.isdir(mcoi_dir):
            pytest.skip("mcoi_runtime source directory not found")
        analyzer = ImportAnalyzer(root_package="mcoi_runtime")
        result = analyzer.analyze_directory(mcoi_dir)
        summary = analyzer.dependency_summary(result)
        assert not result.has_cycles, (
            f"Import cycles detected: {summary['cycles']}"
        )
        # Should have many modules
        assert result.module_count > 100
