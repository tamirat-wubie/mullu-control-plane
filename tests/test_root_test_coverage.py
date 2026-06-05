"""Purpose: keep the repo-root ``tests/`` CI-coverage gap tracked and ratcheted.
Governance scope: which root test files run in *some* GitHub Actions workflow.
Dependencies: .github/workflows/*.yml, .github/workflows/*.yaml, tests/_root_test_coverage_waiver.txt.
Invariants:
  - Every root ``tests/`` file is either run by a workflow OR explicitly waived.
  - A NEW ungated root test fails this test until it is gated (added to a
    ci.yml pytest step) or consciously waived -- the gap cannot grow silently.
  - A previously-ungated test that becomes gated must be removed from the
    waiver -- the baseline ratchets down toward zero.
  - The coverage-contract tests (this one + test_run_mcoi_shards.py +
    test_run_workspace_governance_checks.py) are
    themselves referenced in a workflow, so they actually run in CI. (They
    historically did not, which is how the missing-`q`-shard gap persisted.)

Context: ci.yml runs ``mcoi/tests`` sharded + ``tests/test_gateway`` + ~10
named validators. The remaining root ``tests/`` files run in no workflow. A
naive nightly ``pytest tests`` lane is born-red (env/fixture-dependent finance
integration tests + checked-in-OpenAPI drift), so the gap is tracked here
rather than blindly gated. Closing it is an owner decision (env harness +
which tests deserve gating); this test makes the decision explicit and the
debt visible, and prevents regression.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WAIVER_PATH = REPO_ROOT / "tests" / "_root_test_coverage_waiver.txt"
WORKFLOW_GLOBS = ("*.yml", "*.yaml")

# The coverage-contract tests that MUST run in CI to be effective.
COVERAGE_CONTRACT_TESTS = (
    "tests/test_root_test_coverage.py",
    "tests/test_run_mcoi_shards.py",
    "tests/test_run_workspace_governance_checks.py",
)


def _all_root_test_files() -> set[str]:
    return {
        p.replace("\\", "/")
        for p in glob.glob(str(REPO_ROOT / "tests" / "**" / "test_*.py"), recursive=True)
        for p in [Path(p).resolve().relative_to(REPO_ROOT).as_posix()]
    }


def _workflow_pytest_targets() -> list[str]:
    targets: list[str] = []
    for workflow_glob in WORKFLOW_GLOBS:
        workflow_paths = glob.glob(str(REPO_ROOT / ".github" / "workflows" / workflow_glob))
        for wf in workflow_paths:
            text = Path(wf).read_text(encoding="utf-8")
            for match in re.finditer(r"pytest ([^\n|]+)", text):
                for token in match.group(1).split():
                    if token.startswith("tests/"):
                        targets.append(token)
    return targets


def _workflow_files() -> set[str]:
    workflow_files: set[str] = set()
    for workflow_glob in WORKFLOW_GLOBS:
        workflow_files.update(
            Path(path).resolve().relative_to(REPO_ROOT).as_posix()
            for path in glob.glob(str(REPO_ROOT / ".github" / "workflows" / workflow_glob))
        )
    return workflow_files


def _workflow_covered_files(all_tests: set[str]) -> set[str]:
    covered: set[str] = set()
    for target in _workflow_pytest_targets():
        if glob.has_magic(target):
            covered.update(
                Path(path).resolve().relative_to(REPO_ROOT).as_posix()
                for path in glob.glob(str(REPO_ROOT / target), recursive=True)
                if Path(path).resolve().relative_to(REPO_ROOT).as_posix() in all_tests
            )
        elif target.endswith(".py"):
            covered.add(target)
        else:  # directory target covers everything beneath it
            prefix = target.rstrip("/") + "/"
            covered.update(p for p in all_tests if p.startswith(prefix))
    return covered


def _ungated_root_tests() -> set[str]:
    all_tests = _all_root_test_files()
    return all_tests - _workflow_covered_files(all_tests)


def _load_waiver() -> set[str]:
    lines = WAIVER_PATH.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")}


def test_ungated_root_tests_match_waiver_baseline() -> None:
    ungated = _ungated_root_tests()
    waiver = _load_waiver()

    newly_ungated = sorted(ungated - waiver)
    newly_gated = sorted(waiver - ungated)

    assert not newly_ungated, (
        "New root test(s) run in NO workflow (CI-invisible). Either gate them "
        "(add to a ci.yml pytest step) or, if intentionally ungated, append "
        f"them to {WAIVER_PATH.name}:\n  " + "\n  ".join(newly_ungated)
    )
    assert not newly_gated, (
        "Previously-ungated root test(s) are now gated -- ratchet the baseline "
        f"DOWN by removing them from {WAIVER_PATH.name}:\n  " + "\n  ".join(newly_gated)
    )


def test_workflow_inventory_includes_supported_github_extensions() -> None:
    workflow_files = _workflow_files()

    assert ".github/workflows/ci.yml" in workflow_files
    assert all(path.endswith((".yml", ".yaml")) for path in workflow_files)
    assert WORKFLOW_GLOBS == ("*.yml", "*.yaml")


def test_waiver_entries_all_exist() -> None:
    """The waiver must not reference deleted files (keeps it honest)."""
    missing = sorted(f for f in _load_waiver() if not (REPO_ROOT / f).exists())
    assert not missing, (
        f"Waiver lists files that no longer exist -- remove them from "
        f"{WAIVER_PATH.name}:\n  " + "\n  ".join(missing)
    )


def test_coverage_contract_tests_run_in_ci() -> None:
    """Meta-guard: the coverage-contract tests must themselves be in a workflow.

    If they aren't run, the coverage invariants are unenforced -- exactly the
    blind spot that let the missing `q` shard reach main.
    """
    targets = set(_workflow_pytest_targets())
    missing = [t for t in COVERAGE_CONTRACT_TESTS if t not in targets]
    assert not missing, (
        "Coverage-contract test(s) are not referenced by any workflow, so the "
        "coverage invariants would not run in CI. Add them to a ci.yml pytest "
        "step:\n  " + "\n  ".join(missing)
    )


def test_foundation_validator_tests_run_in_ci_and_are_not_waived() -> None:
    all_tests = _all_root_test_files()
    covered = _workflow_covered_files(all_tests)
    waiver = _load_waiver()
    foundation_validator_tests = {
        path
        for path in all_tests
        if path == "tests/test_validate_foundation_mode.py"
        or path == "tests/test_validate_foundation_local_proof_thread.py"
        or (
            path.startswith("tests/test_validate_foundation_")
            and path.endswith("_boundary.py")
        )
    }

    missing = sorted(foundation_validator_tests - covered)
    waived = sorted(foundation_validator_tests & waiver)

    assert foundation_validator_tests
    assert not missing, (
        "Foundation validator test(s) are not CI-gated. Add them to the "
        "Foundation validator pytest step:\n  " + "\n  ".join(missing)
    )
    assert not waived, (
        "Foundation validator test(s) must be CI-gated, not waived:\n  "
        + "\n  ".join(waived)
    )
