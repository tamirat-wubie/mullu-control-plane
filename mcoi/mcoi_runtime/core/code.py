"""Purpose: governed code automation core — inspect, summarize, apply-and-verify, test.
Governance scope: code automation orchestration only.
Dependencies: code contracts, code adapter, invariant helpers.
Invariants:
  - All code operations go through the adapter (no direct filesystem access).
  - Patch application is verified by re-reading the file after apply.
  - Build/test results are typed and carry structured output.
  - Code-changing operations can be gated by autonomy/approval.
"""

from __future__ import annotations

import re
from typing import Callable

from mcoi_runtime.contracts.code import (
    BuildResult,
    BuildStatus,
    CodeReviewRecord,
    PatchApplicationResult,
    PatchProposal,
    PatchStatus,
    ReviewVerdict,
    TestResult,
    TestStatus,
    WorkspaceState,
)
from mcoi_runtime.adapters.code_adapter import LocalCodeAdapter
from mcoi_runtime.governance.protected_paths import (
    DEFAULT_GOVERNANCE_PROTECTED_PATHS,
    ProtectedPathPolicy,
)
from .invariants import stable_identifier


class CodeEngine:
    """Governed code automation: inspect, test, patch, and review.

    All operations use the adapter's workspace containment.
    """

    def __init__(
        self,
        *,
        adapter: LocalCodeAdapter,
        clock: Callable[[], str],
        protected_paths: ProtectedPathPolicy | None = DEFAULT_GOVERNANCE_PROTECTED_PATHS,
    ) -> None:
        self._adapter = adapter
        self._clock = clock
        # Fail-closed protected-path gate. A governed code change must not
        # silently rewrite the control-plane artifacts that constrain it
        # (CI, schemas, capability packs, the governance package,
        # receipt/proof stores, secrets). Pass protected_paths=None to
        # disable, or a custom ProtectedPathPolicy to scope it.
        self._protected_paths = protected_paths

    def inspect(self, repo_id: str, name: str) -> WorkspaceState:
        """Inspect the repository and return workspace state."""
        self._adapter.inspect_repository(repo_id, name)
        return self._adapter.list_files(repo_id)

    def run_tests(self, command: list[str], *, timeout_seconds: int = 60) -> TestResult:
        """Run a test command and return a typed result."""
        test_id = stable_identifier("test", {"command": " ".join(command), "time": self._clock()})
        exit_code, stdout, stderr, duration_ms = self._adapter.run_command(
            test_id, command, timeout_seconds=timeout_seconds,
        )

        if exit_code == -1:
            status = TestStatus.TIMEOUT if stderr == "timeout" else TestStatus.ERROR
        elif exit_code == 0:
            status = TestStatus.ALL_PASSED
        else:
            status = TestStatus.SOME_FAILED

        passed, failed, errors = _parse_test_counts(stdout + "\n" + stderr)

        return TestResult(
            test_id=test_id,
            status=status,
            command=" ".join(command),
            exit_code=exit_code,
            passed=passed,
            failed=failed,
            errors=errors,
            stdout=stdout[:10000],  # Cap output
            stderr=stderr[:10000],
            duration_ms=duration_ms,
        )

    def run_build(self, command: list[str], *, timeout_seconds: int = 120) -> BuildResult:
        """Run a build command and return a typed result."""
        build_id = stable_identifier("build", {"command": " ".join(command), "time": self._clock()})
        exit_code, stdout, stderr, duration_ms = self._adapter.run_command(
            build_id, command, timeout_seconds=timeout_seconds,
        )

        if exit_code == -1:
            status = BuildStatus.TIMEOUT if stderr == "timeout" else BuildStatus.ERROR
        elif exit_code == 0:
            status = BuildStatus.SUCCEEDED
        else:
            status = BuildStatus.FAILED

        return BuildResult(
            build_id=build_id,
            status=status,
            command=" ".join(command),
            exit_code=exit_code,
            stdout=stdout[:10000],
            stderr=stderr[:10000],
            duration_ms=duration_ms,
        )

    def _protected_path_block(
        self, patch_id: str, target_file: str,
    ) -> PatchApplicationResult | None:
        """Return a BLOCKED result if target_file is protected, else None.

        Fail-closed governance gate: refuses to patch governance /
        control-plane artifacts. Disabled when protected_paths is None or
        an empty policy.
        """
        policy = self._protected_paths
        if policy is None or policy.is_empty:
            return None
        verdict = policy.classify(target_file)
        if not verdict.protected:
            return None
        return PatchApplicationResult(
            patch_id=patch_id,
            status=PatchStatus.BLOCKED,
            target_file=target_file,
            error_message="protected path requires elevated authority: " + verdict.reason,
        )

    def apply_patch_and_verify(self, proposal: PatchProposal) -> PatchApplicationResult:
        """Apply a patch and verify the file was changed."""
        # Protected-path gate (fail-closed) runs before any filesystem
        # access. Disabled only when the engine is constructed with
        # protected_paths=None (or an empty policy).
        blocked = self._protected_path_block(proposal.patch_id, proposal.target_file)
        if blocked is not None:
            return blocked

        # Read original content
        original = self._adapter.read_file(proposal.target_file)
        if original is None:
            return PatchApplicationResult(
                patch_id=proposal.patch_id,
                status=PatchStatus.FAILED,
                target_file=proposal.target_file,
                error_message="target file not readable",
            )

        # Apply
        result = self._adapter.apply_patch(
            proposal.patch_id, proposal.target_file, proposal.unified_diff,
        )
        if not result.succeeded:
            return result

        # Verify: file should be different after patch
        after = self._adapter.read_file(proposal.target_file)
        if after is None:
            return PatchApplicationResult(
                patch_id=proposal.patch_id,
                status=PatchStatus.FAILED,
                target_file=proposal.target_file,
                error_message="file not readable after patch",
            )

        if after == original:
            return PatchApplicationResult(
                patch_id=proposal.patch_id,
                status=PatchStatus.FAILED,
                target_file=proposal.target_file,
                error_message="patch had no effect",
            )

        return result

    def generate_review_summary(
        self,
        repo_id: str,
        reviewer_id: str,
        files_reviewed: tuple[str, ...],
        *,
        verdict: ReviewVerdict = ReviewVerdict.APPROVED,
        comments: tuple[str, ...] = (),
    ) -> CodeReviewRecord:
        """Generate a code review summary record."""
        review_id = stable_identifier("code-review", {
            "repo_id": repo_id, "time": self._clock(),
        })
        return CodeReviewRecord(
            review_id=review_id,
            repo_id=repo_id,
            reviewer_id=reviewer_id,
            verdict=verdict,
            files_reviewed=files_reviewed,
            comments=comments,
            reviewed_at=self._clock(),
        )


_TEST_COUNT_RE = re.compile(
    r"(?P<count>\d+)\s+"
    r"(?P<label>passed|failed|errors?|skipped|xfailed|xpassed|deselected|warning|warnings)\b",
    re.IGNORECASE,
)


def _parse_test_counts(output: str) -> tuple[int, int, int]:
    """Parse pytest-style summary counts: bind each digit to its adjacent label.

    Handles lines such as ``1 failed, 2 passed, 3 errors in 0.31s`` where the
    label-after-digit binding matters. Multiple summary fragments are summed.
    """
    passed = failed = errors = 0
    for match in _TEST_COUNT_RE.finditer(output):
        count = int(match.group("count"))
        label = match.group("label").lower()
        if label == "passed":
            passed += count
        elif label == "failed":
            failed += count
        elif label in {"error", "errors"}:
            errors += count
    return passed, failed, errors
