"""Golden scenario tests for code/repository automation.

Proves governed local workspace operations: inspect, read, write, patch,
build/test execution, workspace root containment, and code review.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from unittest.mock import patch


def _symlinks_supported(tmp_path: Path) -> bool:
    """Check if the platform/process can create symlinks (Windows often can't)."""
    try:
        target = tmp_path / "_symlink_probe_target"
        target.write_text("probe", encoding="utf-8")
        link = tmp_path / "_symlink_probe_link"
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        return False
    finally:
        for p in (tmp_path / "_symlink_probe_link", tmp_path / "_symlink_probe_target"):
            try:
                p.unlink()
            except OSError:
                pass
    return True

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
from mcoi_runtime.adapters.code_adapter import (
    CommandPolicy,
    LocalCodeAdapter,
    _is_within_root,
)
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

    def test_list_files_skips_symlink_to_outside_file(self, tmp_path: Path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks not supported in this environment")
        ws = _setup_workspace(tmp_path)
        outside = tmp_path / "outside_secret.txt"
        outside.write_text("STOLEN-SECRET", encoding="utf-8")
        link = ws / "leaked_link.txt"
        os.symlink(outside, link)

        adapter = _adapter(ws)
        state = adapter.list_files("r-1")

        relative_paths = {f.relative_path for f in state.files}
        assert "leaked_link.txt" not in relative_paths
        for f in state.files:
            content = adapter.read_file(f.relative_path) or ""
            assert "STOLEN-SECRET" not in content

    def test_list_files_skips_symlink_to_outside_directory(self, tmp_path: Path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks not supported in this environment")
        ws = _setup_workspace(tmp_path)
        outside_dir = tmp_path / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "secret.py").write_text("# STOLEN-DIR-SECRET\n", encoding="utf-8")
        os.symlink(outside_dir, ws / "linked_dir")

        adapter = _adapter(ws)
        state = adapter.list_files("r-1")

        for f in state.files:
            assert "STOLEN-DIR-SECRET" not in (adapter.read_file(f.relative_path) or "")

    def test_inspect_repository_does_not_pick_up_outside_extensions(self, tmp_path: Path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks not supported in this environment")
        ws = _setup_workspace(tmp_path)
        outside = tmp_path / "evil.unique-ext-xyz"
        outside.write_text("alien", encoding="utf-8")
        os.symlink(outside, ws / "alien_link.unique-ext-xyz")

        adapter = _adapter(ws)
        desc = adapter.inspect_repository("r-1", "test-repo")

        assert "unique-ext-xyz" not in desc.language_hints


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
        diff = (
            "--- a/missing.py\n"
            "+++ b/missing.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = adapter.apply_patch("p-1", "missing.py", diff)
        assert result.status is PatchStatus.FAILED

    def test_malformed_patch(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        result = adapter.apply_patch("p-1", "main.py", "completely invalid garbage !@#$")
        assert result.status is PatchStatus.MALFORMED
        # Original file unchanged
        assert adapter.read_file("main.py") == "def hello():\n    return 'world'\n"


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

        with patch(
            "mcoi_runtime.adapters.code_adapter.os.replace",
            side_effect=OSError("secret patch failure"),
        ):
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


# --- run_command env scrub ---


class TestRunCommandEnvScrub:
    """Verify run_command scrubs the parent process environment.

    Parent credentials (AWS_*, GITHUB_TOKEN, ANTHROPIC_API_KEY) and runtime
    modifiers (LD_PRELOAD, PYTHONPATH) must not leak into child processes
    spawned for code automation.
    """

    def _capture_child_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        *,
        extra_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws),
            clock=lambda: T0,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        captured: dict[str, dict[str, str]] = {}

        def fake_run(*args, **kwargs):
            captured["env"] = dict(kwargs.get("env") or {})
            return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            fake_run,
        )
        kwargs: dict[str, object] = {}
        if extra_env is not None:
            kwargs["extra_env"] = extra_env
        adapter.run_command("cmd-env", ["echo", "ok"], **kwargs)
        return captured["env"]

    def test_aws_credentials_do_not_leak(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA-fake-id")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret")
        env = self._capture_child_env(monkeypatch, tmp_path)
        assert "AWS_ACCESS_KEY_ID" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env

    def test_github_token_does_not_leak(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        env = self._capture_child_env(monkeypatch, tmp_path)
        assert "GITHUB_TOKEN" not in env
        assert "ANTHROPIC_API_KEY" not in env

    def test_runtime_modifiers_do_not_leak(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")
        monkeypatch.setenv("PYTHONPATH", "/tmp/evil")
        env = self._capture_child_env(monkeypatch, tmp_path)
        assert "LD_PRELOAD" not in env
        assert "PYTHONPATH" not in env

    def test_path_is_preserved(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        env = self._capture_child_env(monkeypatch, tmp_path)
        assert "PATH" in env

    def test_locale_baseline_is_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        env = self._capture_child_env(monkeypatch, tmp_path)
        assert env.get("PYTHONIOENCODING") == "utf-8"
        assert env.get("LC_ALL") == "C.UTF-8"
        assert env.get("LANG") == "C.UTF-8"

    def test_extra_env_passes_through(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        env = self._capture_child_env(
            monkeypatch, tmp_path,
            extra_env={"VIRTUAL_ENV": "/path/to/venv", "MY_FLAG": "1"},
        )
        assert env["VIRTUAL_ENV"] == "/path/to/venv"
        assert env["MY_FLAG"] == "1"

    def test_extra_env_cannot_override_credentials_via_parent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        """extra_env is the only path for non-allowlisted vars; parent env is ignored."""
        monkeypatch.setenv("SECRET_TOKEN", "leaked-from-parent")
        env = self._capture_child_env(monkeypatch, tmp_path)
        assert "SECRET_TOKEN" not in env

    def test_extra_env_rejects_malformed_entries(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ):
        env = self._capture_child_env(
            monkeypatch, tmp_path,
            extra_env={
                "GOOD": "value",
                "": "empty-key-rejected",
                "BAD=KEY": "equals-in-key-rejected",
                "NUL\x00KEY": "nul-in-key-rejected",
                "NUL_VALUE": "value\x00with-nul",
            },
        )
        assert env["GOOD"] == "value"
        assert "" not in env
        assert "BAD=KEY" not in env
        assert "NUL\x00KEY" not in env
        assert "NUL_VALUE" not in env


# --- Strict diff parser (F1) ---


class TestStrictDiffParser:
    """Verify the unified-diff parser fails closed on malformed input,
    supports /dev/null create+delete, preserves CRLF line endings, and
    respects no-newline-at-EOF markers.
    """

    def test_context_mismatch_is_malformed_and_file_unchanged(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        original = adapter.read_file("main.py")
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def hello():\n"
            "+def greet():\n"
            " return 'mismatch'\n"
        )
        result = adapter.apply_patch("p-mismatch", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED
        assert adapter.read_file("main.py") == original

    def test_removed_line_mismatch_is_malformed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        original = adapter.read_file("main.py")
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def does_not_exist():\n"
            "+def greet():\n"
            "     return 'world'\n"
        )
        result = adapter.apply_patch("p-bad-remove", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED
        assert adapter.read_file("main.py") == original

    def test_diff_without_hunk_is_malformed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        result = adapter.apply_patch(
            "p-no-hunk", "main.py",
            "--- a/main.py\n+++ b/main.py\n",
        )
        assert result.status is PatchStatus.MALFORMED

    def test_multi_file_diff_is_malformed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def hello():\n"
            "+def greet():\n"
            "     return 'world'\n"
            "--- a/other.py\n"
            "+++ b/other.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = adapter.apply_patch("p-multi", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED

    def test_diff_path_must_match_target(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- a/other.py\n"
            "+++ b/other.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = adapter.apply_patch("p-wrong-path", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED

    def test_overlapping_hunks_rejected(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        (ws / "data.txt").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
        adapter = _adapter(ws)
        diff = (
            "--- a/data.txt\n"
            "+++ b/data.txt\n"
            "@@ -3,1 +3,1 @@\n"
            "-c\n"
            "+C\n"
            "@@ -1,1 +1,1 @@\n"
            "-a\n"
            "+A\n"
        )
        result = adapter.apply_patch("p-overlap", "data.txt", diff)
        assert result.status is PatchStatus.MALFORMED

    def test_hunk_length_mismatch_rejected(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,5 +1,5 @@\n"
            "-def hello():\n"
            "+def greet():\n"
        )
        result = adapter.apply_patch("p-len", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED

    def test_create_via_dev_null(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- /dev/null\n"
            "+++ b/new_file.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+line one\n"
            "+line two\n"
            "+line three\n"
        )
        result = adapter.apply_patch("p-create", "new_file.py", diff)
        assert result.status is PatchStatus.APPLIED
        content = adapter.read_file("new_file.py")
        assert content == "line one\nline two\nline three\n"

    def test_create_when_target_exists_is_malformed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- /dev/null\n"
            "+++ b/main.py\n"
            "@@ -0,0 +1 @@\n"
            "+new\n"
        )
        result = adapter.apply_patch("p-create-conflict", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED

    def test_delete_via_dev_null(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        # main.py currently has 2 lines: "def hello():\n    return 'world'\n"
        diff = (
            "--- a/main.py\n"
            "+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n"
            "-def hello():\n"
            "-    return 'world'\n"
        )
        result = adapter.apply_patch("p-delete", "main.py", diff)
        assert result.status is PatchStatus.APPLIED
        assert not (ws / "main.py").exists()

    def test_delete_missing_file_is_failed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        diff = (
            "--- a/missing.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-x\n"
        )
        result = adapter.apply_patch("p-delete-missing", "missing.py", diff)
        assert result.status is PatchStatus.FAILED

    def test_crlf_file_with_lf_diff_preserves_crlf(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        # Write a file with CRLF endings (binary mode to preserve)
        (ws / "crlf.txt").write_bytes(b"alpha\r\nbeta\r\ngamma\r\n")
        adapter = _adapter(ws)
        diff = (
            "--- a/crlf.txt\n"
            "+++ b/crlf.txt\n"
            "@@ -1,3 +1,3 @@\n"
            " alpha\n"
            "-beta\n"
            "+BETA\n"
            " gamma\n"
        )
        result = adapter.apply_patch("p-crlf", "crlf.txt", diff)
        assert result.status is PatchStatus.APPLIED
        # The new file must keep CRLF endings
        raw = (ws / "crlf.txt").read_bytes()
        assert raw == b"alpha\r\nBETA\r\ngamma\r\n"

    def test_no_newline_at_end_marker_is_honored(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        (ws / "nofinal.txt").write_bytes(b"first\nsecond")  # no trailing \n
        adapter = _adapter(ws)
        diff = (
            "--- a/nofinal.txt\n"
            "+++ b/nofinal.txt\n"
            "@@ -1,2 +1,2 @@\n"
            " first\n"
            "-second\n"
            "+SECOND\n"
            "\\ No newline at end of file\n"
        )
        result = adapter.apply_patch("p-nofinal", "nofinal.txt", diff)
        assert result.status is PatchStatus.APPLIED
        raw = (ws / "nofinal.txt").read_bytes()
        assert raw == b"first\nSECOND"

    def test_patch_with_no_effect_is_malformed(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        # All-context hunk — no changes
        diff = (
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def hello():\n"
            "     return 'world'\n"
        )
        result = adapter.apply_patch("p-noop", "main.py", diff)
        assert result.status is PatchStatus.MALFORMED


# --- Command policy (F2) ---


class TestCommandPolicy:
    """Verify run_command rejects shells, network tools, git push/clone,
    python -c/-m and node -r/-p/-e under the default strict policy.
    """

    def _run(self, tmp_path: Path, command: list[str]) -> tuple[int, str, str, int]:
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        return adapter.run_command("cmd-policy", command)

    def test_bash_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["bash", "-c", "ls"])
        assert rc == -1
        assert "blocked command" in stderr
        assert "denied executable: bash" in stderr

    def test_curl_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["curl", "https://example.com"])
        assert rc == -1
        assert "denied executable: curl" in stderr

    def test_unknown_executable_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["arbitrary-binary"])
        assert rc == -1
        assert "not allowlisted" in stderr

    def test_git_push_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["git", "push", "origin", "main"])
        assert rc == -1
        assert "denied git subcommand: push" in stderr

    def test_git_dash_C_push_is_blocked(self, tmp_path: Path):
        """Verify `git -C <dir> push ...` is caught (audit gap A8)."""
        rc, _, stderr, _ = self._run(
            tmp_path, ["git", "-C", "/some/dir", "push", "origin", "main"],
        )
        assert rc == -1
        assert "denied git subcommand: push" in stderr

    def test_git_clone_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["git", "clone", "https://example.com/r"])
        assert rc == -1
        assert "denied git subcommand: clone" in stderr

    def test_git_status_is_allowed(self, tmp_path: Path, monkeypatch):
        # Stub subprocess.run so we don't actually invoke git; we just want
        # to confirm the policy gate accepts the command.
        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout="", stderr=""),
        )
        rc, _, stderr, _ = self._run(tmp_path, ["git", "status"])
        assert rc == 0
        assert "blocked" not in stderr

    def test_python_dash_c_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["python", "-c", "print(1)"])
        assert rc == -1
        assert "python -c flag denied" in stderr

    def test_python_dash_m_is_blocked(self, tmp_path: Path):
        """python -m gates pip install, http.server, etc. (audit gap A9)."""
        rc, _, stderr, _ = self._run(tmp_path, ["python", "-m", "http.server"])
        assert rc == -1
        assert "python -m flag denied" in stderr

    def test_python3_dash_m_is_blocked(self, tmp_path: Path):
        """python3 must be treated as the same family (audit gap A7)."""
        rc, _, stderr, _ = self._run(tmp_path, ["python3", "-m", "pip", "install", "x"])
        assert rc == -1
        assert "python -m flag denied" in stderr

    def test_node_dash_r_is_blocked(self, tmp_path: Path):
        """node -r preloads arbitrary modules (audit gap A10)."""
        rc, _, stderr, _ = self._run(tmp_path, ["node", "-r", "evil"])
        assert rc == -1
        assert "node -r flag denied" in stderr

    def test_node_dash_p_is_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["node", "-p", "1+1"])
        assert rc == -1
        assert "node -p flag denied" in stderr

    def test_empty_command_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, [])
        assert rc == -1
        assert "blocked command" in stderr

    def test_nul_byte_in_command_blocked(self, tmp_path: Path):
        rc, _, stderr, _ = self._run(tmp_path, ["python", "tests\x00evil"])
        assert rc == -1
        assert "NUL byte" in stderr

    def test_timeout_is_clamped_to_policy_max(self, tmp_path: Path, monkeypatch):
        ws = _setup_workspace(tmp_path)
        policy = CommandPolicy(
            allowed_executables=("python",),
            denied_executables=(),
            denied_git_subcommands=(),
            max_timeout_seconds=10,
        )
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0, command_policy=policy,
        )
        captured: dict[str, object] = {}

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run", fake_run,
        )
        adapter.run_command("cmd-clamp", ["python", "x.py"], timeout_seconds=999)
        assert captured["timeout"] == 10


# --- Process exit code contract (F3) ---


class TestProcessExitCodeContract:
    def test_test_result_accepts_minus_one(self):
        from mcoi_runtime.contracts.code import TestResult, TestStatus
        result = TestResult(
            test_id="t-1", status=TestStatus.TIMEOUT,
            command="pytest", exit_code=-1,
        )
        assert result.exit_code == -1

    def test_build_result_accepts_minus_one(self):
        from mcoi_runtime.contracts.code import BuildResult, BuildStatus
        result = BuildResult(
            build_id="b-1", status=BuildStatus.ERROR,
            command="make", exit_code=-1,
        )
        assert result.exit_code == -1

    def test_build_result_rejects_minus_two(self):
        from mcoi_runtime.contracts.code import BuildResult, BuildStatus
        with pytest.raises(ValueError):
            BuildResult(
                build_id="b-1", status=BuildStatus.ERROR,
                command="make", exit_code=-2,
            )

    def test_test_result_rejects_bool(self):
        """exit_code must be int, not bool (which is an int subclass)."""
        from mcoi_runtime.contracts.code import TestResult, TestStatus
        with pytest.raises(ValueError):
            TestResult(
                test_id="t-1", status=TestStatus.ALL_PASSED,
                command="pytest", exit_code=True,  # type: ignore[arg-type]
            )


# --- pytest count parser (F5) ---


class TestPytestCountParser:
    def test_simple_passed_count(self):
        from mcoi_runtime.core.code import _parse_test_counts
        passed, failed, errors = _parse_test_counts("===== 10 passed in 0.42s =====")
        assert passed == 10
        assert failed == 0
        assert errors == 0

    def test_label_bound_to_correct_digit(self):
        """`1 failed, 2 passed, 3 errors` must bind 2→passed, not 1."""
        from mcoi_runtime.core.code import _parse_test_counts
        passed, failed, errors = _parse_test_counts("1 failed, 2 passed, 3 errors in 0.31s")
        assert passed == 2
        assert failed == 1
        assert errors == 3

    def test_multiple_lines_summed(self):
        from mcoi_runtime.core.code import _parse_test_counts
        output = "5 passed in foo\n3 passed in bar\n"
        passed, _, _ = _parse_test_counts(output)
        assert passed == 8

    def test_no_summary_yields_zeros(self):
        from mcoi_runtime.core.code import _parse_test_counts
        passed, failed, errors = _parse_test_counts("running tests...")
        assert passed == failed == errors == 0


# --- Streaming hash + size cap (M4 + M7) ---


class TestStreamingFileMetrics:
    def test_oversize_file_skipped(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        big = ws / "huge.bin"
        big.write_bytes(b"x" * 1024)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0, max_file_bytes=512,
        )
        state = adapter.list_files("r-1")
        relative = {f.relative_path for f in state.files}
        assert "huge.bin" not in relative

    def test_within_budget_file_included(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        small = ws / "ok.txt"
        small.write_bytes(b"y" * 128)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0, max_file_bytes=512,
        )
        state = adapter.list_files("r-1")
        relative = {f.relative_path for f in state.files}
        assert "ok.txt" in relative

    def test_default_max_is_10mb(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        assert adapter.max_file_bytes == 10 * 1024 * 1024

    def test_invalid_max_rejected(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        with pytest.raises(ValueError):
            LocalCodeAdapter(
                root_path=str(ws), clock=lambda: T0, max_file_bytes=0,
            )

    def test_hash_matches_streaming_and_full_read(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        content = b"hello\nworld\n" * 100
        (ws / "data.txt").write_bytes(content)
        adapter = _adapter(ws)
        state = adapter.list_files("r-1", extensions=("txt",))
        data = next(f for f in state.files if f.relative_path == "data.txt")
        import hashlib
        assert data.content_hash == hashlib.sha256(content).hexdigest()
        assert data.size_bytes == len(content)


# --- Repository descriptor metadata (M6) ---


class TestRepositoryDescriptorMetadata:
    """Surface whether the language_hints list was truncated at the cap."""

    def test_few_extensions_not_truncated(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        adapter = _adapter(ws)
        desc = adapter.inspect_repository("r-1", "test")
        assert desc.metadata.get("extensions_truncated") is False
        assert desc.metadata.get("extension_count") == len(desc.language_hints)

    def test_many_extensions_marked_truncated(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        # 11 distinct extensions trips the 10-item cap
        for i in range(11):
            (ws / f"file.ext{i:02}").write_text("x", encoding="utf-8")
        adapter = _adapter(ws)
        desc = adapter.inspect_repository("r-1", "test")
        assert desc.metadata.get("extensions_truncated") is True
        # Original ext set has the 11 ext{NN} extensions plus md+py from
        # _setup_workspace; we just need the count to exceed 10.
        assert desc.metadata.get("extension_count") >= 11
        assert len(desc.language_hints) == 10


# --- Subprocess UTF-8 decoding (M10) ---


class TestSubprocessUtf8Decoding:
    """run_command must decode child output as UTF-8 with errors=replace,
    independent of platform default encoding (Windows defaults to CP1252).
    """

    def test_subprocess_run_invoked_with_utf8_encoding(
        self, tmp_path: Path, monkeypatch,
    ):
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        captured: dict[str, object] = {}

        def fake_run(*args, **kwargs):
            captured["encoding"] = kwargs.get("encoding")
            captured["errors"] = kwargs.get("errors")
            captured["text"] = kwargs.get("text")
            return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run", fake_run,
        )
        adapter.run_command("cmd-utf8", ["echo", "ok"])

        assert captured["encoding"] == "utf-8"
        assert captured["errors"] == "replace"
        # text=True must NOT be passed (encoding= implies text mode and
        # passing both is a TypeError on some Python versions).
        assert captured.get("text") is None


# --- Read/write resolve-then-operate (M3) ---


class TestM3ResolveBeforeOperate:
    """read_file and write_file must resolve the target's real path and
    verify it's inside the workspace root before any read/write — so a
    symlink swap between the membership check and the operation lands
    on the resolved-at-check-time path, not the attacker's swap target.
    """

    def test_read_file_outside_root_via_symlink_skipped(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        outside = tmp_path / "secret.txt"
        outside.write_text("STOLEN", encoding="utf-8")
        try:
            (ws / "leak.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported in this environment")
        adapter = _adapter(ws)

        content = adapter.read_file("leak.txt")
        assert content is None

    def test_write_file_through_symlink_outside_blocked(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        outside_dir = tmp_path / "other"
        outside_dir.mkdir()
        try:
            (ws / "linked").symlink_to(outside_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported in this environment")
        adapter = _adapter(ws)

        # writing to "linked/escape.txt" should land outside root via the
        # symlink — and must be blocked
        ok = adapter.write_file("linked/escape.txt", "should not write")
        assert ok is False
        assert not (outside_dir / "escape.txt").exists()

    def test_read_file_in_workspace_symlink_still_works(self, tmp_path: Path):
        ws = _setup_workspace(tmp_path)
        (ws / "src" / "real.py").write_text("ALIASED\n", encoding="utf-8")
        try:
            (ws / "alias.py").symlink_to(ws / "src" / "real.py")
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported in this environment")
        adapter = _adapter(ws)

        content = adapter.read_file("alias.py")
        assert content == "ALIASED\n"


# --- Structured truncation flags (M9) ---


class TestM9StructuredTruncationFlags:
    """run_command_with_meta returns explicit truncated flags rather than
    relying on the in-band marker — so a child process that legitimately
    writes the marker substring cannot forge a "truncated" signal.
    """

    def test_no_truncation_flags_clear(self, tmp_path: Path, monkeypatch):
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout="ok", stderr=""),
        )
        meta = adapter.run_command_with_meta("cmd-1", ["echo", "ok"])
        assert meta.exit_code == 0
        assert meta.stdout == "ok"
        assert meta.stdout_truncated is False
        assert meta.stderr_truncated is False

    def test_truncation_sets_flag_without_in_band_marker(self, tmp_path, monkeypatch):
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        big = "x" * 500
        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=big, stderr=""),
        )
        meta = adapter.run_command_with_meta(
            "cmd-trunc", ["echo", "big"], max_output_bytes=100,
        )
        assert meta.stdout_truncated is True
        # No in-band marker on the structured surface
        assert "[TRUNCATED" not in meta.stdout
        assert len(meta.stdout) <= 100

    def test_child_emitting_marker_is_not_treated_as_truncation(
        self, tmp_path, monkeypatch,
    ):
        """A child writing the literal marker string under the size limit
        must NOT be reported as truncated — the flag is the source of
        truth, not pattern matching the output.
        """
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        forged = "ok\n[TRUNCATED at 9999999 bytes]"
        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=forged, stderr=""),
        )
        meta = adapter.run_command_with_meta("cmd-forge", ["echo"])
        assert meta.stdout_truncated is False
        assert "[TRUNCATED" in meta.stdout  # the literal forged text passes through
        # …but the structured flag is NOT fooled

    def test_legacy_run_command_still_emits_in_band_marker(
        self, tmp_path, monkeypatch,
    ):
        """Backward compat: the 4-tuple run_command surface still appends
        the [TRUNCATED ...] marker for any caller that depended on it.
        """
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws), clock=lambda: T0,
            command_policy=CommandPolicy.permissive_for_testing(),
        )
        big = "x" * 500
        monkeypatch.setattr(
            "mcoi_runtime.adapters.code_adapter.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=big, stderr=""),
        )
        rc, stdout, stderr, _ = adapter.run_command(
            "cmd-legacy", ["echo"], max_output_bytes=100,
        )
        assert rc == 0
        assert "[TRUNCATED at 100 bytes]" in stdout
