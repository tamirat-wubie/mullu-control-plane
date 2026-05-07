"""Verifies that .change_assurance/test_inventory.json is structurally
sound and consistent with itself.

Closes the "Test-count claim not machine-derived" reflection gap from
STATUS.md. The companion script `scripts/generate_test_inventory.py`
generates the artifact; this test is the safety net that catches a
hand-edited or corrupted inventory.

The actual *freshness* check (does the committed inventory match the
current code?) is intentionally NOT done here — running pytest
--collect-only from within pytest is reentrant and slow. CI runs

    python scripts/generate_test_inventory.py --check

as a separate step. This test only verifies that the committed JSON
file has a valid shape and self-consistent counts, which catches the
common "someone hand-edited the file" failure mode.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = REPO_ROOT / ".change_assurance" / "test_inventory.json"


@pytest.fixture(scope="module")
def inventory() -> dict:
    """Load the committed test-inventory artifact, or skip if absent.

    The artifact lives under `.change_assurance/`, which is gitignored
    by repo convention (matching `proof_coverage_matrix.json` and other
    runtime witnesses). CI generates it before running pytest:

        python scripts/generate_test_inventory.py
        python -m pytest

    Local pytest runs that haven't generated the artifact yet skip the
    inventory tests rather than fail — running the generator is one
    command and these tests are observability, not correctness gates.
    Drift detection (CI's actual enforcement) is the separate command
    `python scripts/generate_test_inventory.py --check`, which exits
    nonzero when the committed inventory is stale relative to the code.
    """
    if not ARTIFACT_PATH.exists():
        pytest.skip(
            f"{ARTIFACT_PATH.relative_to(REPO_ROOT)} not present. "
            "Run `python scripts/generate_test_inventory.py` to generate "
            "the runtime witness, then re-run these tests. CI generates "
            "the artifact automatically; this skip is for local runs only."
        )
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


class TestArtifactShape:
    """The artifact must have the schema documented in
    scripts/generate_test_inventory.py."""

    def test_schema_version_is_one(self, inventory: dict):
        assert inventory["schema_version"] == 1

    def test_has_iso_timestamp(self, inventory: dict):
        ts = inventory["generated_at"]
        assert isinstance(ts, str)
        # ISO-8601 UTC: YYYY-MM-DDTHH:MM:SSZ
        assert len(ts) == 20
        assert ts.endswith("Z")
        assert ts[10] == "T"

    def test_python_block_present(self, inventory: dict):
        py = inventory["python"]
        assert isinstance(py["mcoi_tests"], int)
        assert isinstance(py["root_tests"], int)
        assert isinstance(py["total"], int)

    def test_rust_block_present(self, inventory: dict):
        rust = inventory["rust"]
        assert isinstance(rust["maf_kernel_tests"], int)
        assert isinstance(rust["total"], int)

    def test_tooling_block_records_commands(self, inventory: dict):
        tooling = inventory["tooling"]
        assert "pytest" in tooling["pytest_command"]
        assert "cargo" in tooling["cargo_command"]


class TestArtifactSelfConsistency:
    """The artifact's totals must match the sum of its parts. A hand-edit
    that bumps `total_tests` without bumping the breakdown — or vice
    versa — is the failure mode this catches."""

    def test_python_total_matches_breakdown(self, inventory: dict):
        py = inventory["python"]
        assert py["total"] == py["mcoi_tests"] + py["root_tests"], (
            f"python.total ({py['total']}) != "
            f"mcoi_tests ({py['mcoi_tests']}) + root_tests ({py['root_tests']}). "
            "Regenerate with `python scripts/generate_test_inventory.py`."
        )

    def test_rust_total_matches_breakdown(self, inventory: dict):
        rust = inventory["rust"]
        assert rust["total"] == rust["maf_kernel_tests"], (
            f"rust.total ({rust['total']}) != "
            f"maf_kernel_tests ({rust['maf_kernel_tests']}). "
            "Regenerate with `python scripts/generate_test_inventory.py`."
        )

    def test_grand_total_matches_python_plus_rust(self, inventory: dict):
        expected = inventory["python"]["total"] + inventory["rust"]["total"]
        assert inventory["total_tests"] == expected, (
            f"total_tests ({inventory['total_tests']}) != "
            f"python.total ({inventory['python']['total']}) + "
            f"rust.total ({inventory['rust']['total']}). "
            "Regenerate with `python scripts/generate_test_inventory.py`."
        )


class TestArtifactNonZero:
    """Sanity guard: a regression that silently zeros the counts is
    catastrophic — the artifact would claim zero tests exist. Catch
    that here rather than letting a downstream consumer believe it."""

    def test_python_count_is_substantial(self, inventory: dict):
        # mcoi alone has tens of thousands of tests by historical record.
        # If this assertion ever fails legitimately (e.g., huge cleanup),
        # update the floor; do NOT silently lower it to mask a regression.
        assert inventory["python"]["mcoi_tests"] > 1000, (
            f"mcoi_tests = {inventory['python']['mcoi_tests']} — "
            "implausibly low. Either the script is miscounting "
            "(see scripts/generate_test_inventory.py::_count_pytest) "
            "or a large amount of test code was removed. Investigate "
            "before lowering this floor."
        )

    def test_rust_count_is_nonzero(self, inventory: dict):
        assert inventory["rust"]["total"] > 0, (
            "Zero Rust tests detected. Either cargo test --list failed "
            "(no toolchain in the run environment?) or maf-kernel lost "
            "its tests."
        )
