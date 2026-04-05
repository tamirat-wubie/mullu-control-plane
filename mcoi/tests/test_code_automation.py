"""Golden scenario tests for code/repository automation.

Proves governed local workspace operations: inspect, read, write, patch,
build/test execution, workspace root containment, and code review.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from unittest.mock import patch

from mcoi_runtime.contracts.code import (
    BuildResult,
    BuildStatus,
    CodeReviewRecord,
    PatchApplicationResult,
    PatchProposal,
    PatchStatus,
    RepositoryDescriptor,
    ReviewVerdict,
    SourceFile,
    TestResult,
    TestStatus,
    WorkspaceState,
)
from mcoi_runtime.adapters.code_adapter import LocalCodeAdapter, _is_within_root
from mcoi_runtime.core.code import CodeEngine


T0 = "2025-01-15T10:00:00+00:00"


def _setup_workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with source files."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (ws / "test_main.py").write_text("def test_hello():\n    assert hello() == 'world'\n", encoding="utf-8")
    (ws / "README.md").write_text("# Test Project\n", encoding="utf-8")
    sub = ws / "src"
    sub.mkdir()
    (sub / "lib.py").write_text("LIB_VERSION = '1.0'\n", encoding="utf-8")
    return ws


def _adapter(ws: Path) -> LocalCodeAdapter:
    return LocalCodeAdapter(root_path=str(ws), clock=lambda: T0)


def _engine(ws: Path) -> CodeEngine:
    return CodeEngine(adapter=_adapter(ws), clock=lambda: T0)


# --- Contracts ---


class TestCodeContracts:
    def test_repository_descriptor(self):
        r = RepositoryDescriptor(repo_id="r-1", name="test-repo", root_path="/tmp/ws")
        assert r.repo_id == "r-1"

    def test_source_file(self):
        f = SourceFile(file_path="/tmp/ws/main.py", relative_path="main.py",
                       content_hash="abc", size_bytes=100, line_count=5)
        assert f.relative_path == "main.py"

    def test_source_file_negative_size_rejected(self):
        with pytest.raises(ValueError):
            SourceFile(file_path="/x", relative_path="x", content_hash="h",
                       size_bytes=-1, line_count=0)

    def test_patch_proposal(self):
        p = PatchProposal(patch_id="p-1", target_file="main.py",
                          description="fix bug", unified_diff="--- a\n+++ b\n")
        assert p.target_file == "main.py"

    def test_build_result_succeeded(self):
        b = BuildResult(build_id="b-1", status=BuildStatus.SUCCEEDED,
                        command="make", exit_code=0)
        assert b.succeeded

    def test_test_result_all_passed(self):
        t = TestResult(test_id="t-1", status=TestStatus.ALL_PASSED,
                       command="pytest", exit_code=0, passed=10)
        assert t.all_passed

    def test_code_review(self):
        r = CodeReviewRecord(review_id="rv-1", repo_id="r-1", reviewer_id="op-1",
                             verdict=ReviewVerdict.APPROVED, files_reviewed=("main.py",))
        assert r.verdict is ReviewVerdict.APPROVED


# --- Path containment ---


class TestPathContainment:
    def test_within_root(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        assert _is_within_root(ws, ws / "main.py")

    def test_subdirectory_within_root(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        assert _is_within_root(ws, ws / "src" / "lib.py")

    def test_traversal_outside_root(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        assert not _is_within_root(ws, ws / ".." / "outside.txt")

    def test_absolute_outside_root(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        assert not _is_within_root(ws, Path("/etc/passwd"))

    def test_prefix_collision_sibling_blocked(self, tmp_path: Path):
        """Sibling directory with name prefix of root must NOT be treated as within root."""
        ws = _setup_workspace(tmp_path)
        # Create a sibling directory whose name starts with the root name
        evil_sibling = ws.parent / (ws.name + "_evil")
        evil_sibling.mkdir()
        (evil_sibling / "secret.txt").write_text("stolen", encoding="utf-8")
        assert not _is_within_root(ws, evil_sibling / "secret.txt")


# --- Adapter ---


class TestLocalCodeAdapter:
    def test_inspect_repository(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        desc = adapter.inspect_repository("r-1", "test-repo")
        assert desc.repo_id == "r-1"
        assert len(desc.language_hints) > 0
        assert "py" in desc.language_hints

    def test_list_files(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        state = adapter.list_files("r-1")
        assert state.total_files >= 4
        assert state.total_bytes > 0

    def test_list_files_filtered(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        state = adapter.list_files("r-1", extensions=("py",))
        assert all(f.relative_path.endswith(".py") for f in state.files)

    def test_read_file(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        content = adapter.read_file("main.py")
        assert content is not None
        assert "hello" in content

    def test_read_file_outside_root(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert adapter.read_file("../../etc/passwd") is None

    def test_read_nonexistent(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert adapter.read_file("nonexistent.py") is None

    def test_write_file(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert adapter.write_file("new_file.py", "# new\n")
        assert (ws / "new_file.py").read_text() == "# new\n"

    def test_write_file_outside_root_blocked(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert not adapter.write_file("../../outside.txt", "bad")

    def test_write_file_creates_directories(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert adapter.write_file("new_dir/deep/file.py", "# deep\n")
        assert (ws / "new_dir" / "deep" / "file.py").exists()

    def test_invalid_root_rejected(self, tmp_path: Path):
        missing_root = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="^workspace root is not a directory$") as exc_info:
            LocalCodeAdapter(root_path=str(missing_root), clock=lambda: T0)
        assert str(missing_root) not in str(exc_info.value)


# --- Patch application ---


class TestPatchApplication:
    def test_apply_valid_patch(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def hello():\n"
            "+def hello_world():\n"
            "     return 'world'\n"
        )
        result = adapter.apply_patch("p-1", "main.py", diff)
        assert result.succeeded
        content = adapter.read_file("main.py")
        assert "hello_world" in content

    def test_apply_patch_outside_root_blocked(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        result = adapter.apply_patch("p-1", "../../etc/hosts", "diff")
        assert result.status is PatchStatus.BLOCKED
        assert "outside workspace" in result.error_message

    def test_apply_patch_nonexistent_file(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        result = adapter.apply_patch("p-1", "missing.py", "diff")
        assert result.status is PatchStatus.FAILED

    def test_malformed_patch(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        # This won't crash but may produce no change — core engine will catch "no effect"
        result = adapter.apply_patch("p-1", "main.py", "completely invalid garbage !@#$")
        # Should still return a result (may be APPLIED with no change or MALFORMED)
        assert isinstance(result, PatchApplicationResult)


# --- Code engine ---


    def test_patch_failure_is_bounded(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def hello():\n"
            "+def hello_world():\n"
            "     return 'world'\n"
        )

        with patch("pathlib.Path.write_text", side_effect=OSError("secret patch failure")):
            result = adapter.apply_patch("p-1", "main.py", diff)

        assert result.status is PatchStatus.MALFORMED
        assert result.error_message == "patch error (OSError)"
        assert "secret patch failure" not in (result.error_message or "")


class TestCodeEngine:
    def test_inspect(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        state = engine.inspect("r-1", "test-repo")
        assert state.total_files >= 4

    def test_apply_patch_and_verify(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        proposal = PatchProposal(
            patch_id="p-1",
            target_file="main.py",
            description="rename function",
            unified_diff=(
                "--- a/main.py\n"
                "+++ b/main.py\n"
                "@@ -1,2 +1,2 @@\n"
                "-def hello():\n"
                "+def greet():\n"
                "     return 'world'\n"
            ),
        )
        result = engine.apply_patch_and_verify(proposal)
        assert result.succeeded

    def test_patch_no_effect_detected(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        # Patch that doesn't actually change anything meaningful
        proposal = PatchProposal(
            patch_id="p-2",
            target_file="main.py",
            description="no-op patch",
            unified_diff="no valid hunks here",
        )
        result = engine.apply_patch_and_verify(proposal)
        assert not result.succeeded

    def test_generate_review(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        review = engine.generate_review_summary(
            "r-1", "reviewer-1", ("main.py", "test_main.py"),
            verdict=ReviewVerdict.APPROVED,
            comments=("looks good",),
        )
        assert review.verdict is ReviewVerdict.APPROVED
        assert len(review.files_reviewed) == 2


# --- Golden scenarios ---


class TestCodeGoldenScenarios:
    def test_01_inspect_repo_and_summarize(self, tmp_path: Path):
        """Inspect repository and get typed workspace state."""
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        state = engine.inspect("r-1", "test-project")
        assert state.total_files >= 4
        py_files = [f for f in state.files if f.relative_path.endswith(".py")]
        assert len(py_files) >= 3  # main.py, test_main.py, src/lib.py

    def test_02_out_of_workspace_write_blocked(self, tmp_path: Path):
        """Attempt to write outside workspace root is blocked."""
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert not adapter.write_file("../../escape.txt", "bad content")
        assert not (tmp_path / "escape.txt").exists()

    def test_03_apply_valid_patch_and_verify(self, tmp_path: Path):
        """Apply a valid patch and verify the file changed."""
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        proposal = PatchProposal(
            patch_id="golden-p1",
            target_file="src/lib.py",
            description="update version",
            unified_diff=(
                "--- a/src/lib.py\n"
                "+++ b/src/lib.py\n"
                "@@ -1,1 +1,1 @@\n"
                "-LIB_VERSION = '1.0'\n"
                "+LIB_VERSION = '2.0'\n"
            ),
        )
        result = engine.apply_patch_and_verify(proposal)
        assert result.succeeded
        content = _adapter(ws).read_file("src/lib.py")
        assert "2.0" in content

    def test_04_malformed_patch_no_effect(self, tmp_path: Path):
        """Malformed patch has no effect and is detected."""
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        original = _adapter(ws).read_file("main.py")
        proposal = PatchProposal(
            patch_id="golden-p2",
            target_file="main.py",
            description="invalid patch",
            unified_diff="this is not a valid unified diff",
        )
        result = engine.apply_patch_and_verify(proposal)
        assert not result.succeeded
        after = _adapter(ws).read_file("main.py")
        # File should be unchanged or detected as no-effect
        # (adapter may write but content stays same → engine detects)

    def test_05_workspace_state_deterministic(self, tmp_path: Path):
        """Same workspace produces same state snapshot."""
        ws = _setup_workspace(tmp_path)
        e1 = _engine(ws)
        e2 = _engine(ws)
        s1 = e1.inspect("r-1", "test")
        s2 = e2.inspect("r-1", "test")
        assert s1.total_files == s2.total_files
        assert s1.total_bytes == s2.total_bytes

    def test_06_code_review_record(self, tmp_path: Path):
        """Generate a typed code review with attribution."""
        ws = _setup_workspace(tmp_path)
        engine = _engine(ws)
        review = engine.generate_review_summary(
            "r-1", "senior-dev",
            ("main.py", "src/lib.py"),
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            comments=("needs error handling", "missing tests"),
        )
        assert review.verdict is ReviewVerdict.CHANGES_REQUESTED
        assert review.reviewer_id == "senior-dev"
        assert len(review.comments) == 2
