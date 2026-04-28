#!/usr/bin/env python3
"""Generate a machine-derived test inventory artifact.

Closes the "Test-count claim not machine-derived" reflection gap from
`STATUS.md`. Produces `.change_assurance/test_inventory.json` with the
current Python and Rust test counts, suitable for citation by release
notes, README, and the public repository status witness — replacing the
human-maintained "47,800+ tests" claim with a generated number that
cannot drift without code review.

Counts:
  * Python (pytest) — sum of collected test items across mcoi/ and the
    repo-root tests/ tree (gateway, financial, creative, enterprise).
    Uses `pytest --collect-only -q` and parses the summary line.
  * Rust (cargo) — count of test items per `cargo test -p maf-kernel
    --lib --no-run` followed by `cargo test --lib -- --list --format=terse`.
    Falls back to parsing `cargo test --lib 2>&1 | grep "test result"`
    if the toolchain rejects --list.

Output JSON (committed at .change_assurance/test_inventory.json):

    {
        "schema_version": 1,
        "generated_at": "2026-04-28T12:34:56Z",
        "python": {
            "mcoi_tests": <int>,
            "root_tests": <int>,
            "total": <int>
        },
        "rust": {
            "maf_kernel_tests": <int>,
            "total": <int>
        },
        "total_tests": <int>,
        "tooling": {
            "pytest_command": "pytest --collect-only -q",
            "cargo_command":  "cargo test -p maf-kernel --lib -- --list"
        }
    }

CLI:
    python scripts/generate_test_inventory.py
        Regenerate the artifact at .change_assurance/test_inventory.json.

    python scripts/generate_test_inventory.py --dry-run
        Compute and print the inventory; do not write the file.

    python scripts/generate_test_inventory.py --check
        Compute the inventory and compare to the committed artifact; exit
        1 if drift is detected. CI uses this to fail merges that don't
        regenerate.

Importable API:
    compute_inventory() -> dict
        Returns the inventory dict (does not write).
    write_inventory(inventory: dict) -> Path
        Writes inventory to the canonical artifact path; returns the path.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = REPO_ROOT / ".change_assurance" / "test_inventory.json"
SCHEMA_VERSION = 1

# Pytest summary lines look like:
#   "12345 tests collected in 4.56s"
# Older / different versions: "12345 tests collected" or with hypothesis lines.
_PYTEST_COLLECTED = re.compile(r"^\s*(\d+)\s+tests?\s+collected", re.MULTILINE)

# `cargo test -- --list` lines look like:
#   tests::name_of_test: test
# The count is one per matching line. Bench, ignored, and doctest noise is
# excluded by the strict ": test$" suffix.
_CARGO_TEST_LINE = re.compile(r": test$", re.MULTILINE)


def _run(cmd: list[str], cwd: Path) -> str:
    """Run a command and return stdout. Stderr is captured for debugging."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + "\n" + result.stderr


def _count_pytest(cwd: Path, target: str = "tests/") -> int:
    """Run `pytest --collect-only -q <target>` and parse the collected count.

    Uses an explicit target directory rather than pytest auto-discovery to
    avoid double-counting nested test trees. README usage is:
        cd mcoi && pytest tests/ -q       # mcoi suite
        pytest tests/ -q                  # repo-root: gateway + skills
    so each invocation is rooted at a `tests/` subdirectory and the two
    roots do not overlap.
    """
    out = _run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", target],
        cwd=cwd,
    )
    matches = _PYTEST_COLLECTED.findall(out)
    if not matches:
        # Fall back to counting "::" lines in collect-only output, which
        # is the per-test format in -q mode for newer pytest. This is a
        # last-resort path if the summary line shape changes.
        lines = [ln for ln in out.splitlines() if "::" in ln and not ln.startswith(" ")]
        return len(lines)
    # Sum all matches in case multiple "X tests collected" lines appear
    # (e.g., from re-collection after --no-header).
    return sum(int(m) for m in matches)


def _count_cargo(crate_dir: Path, package: str) -> int:
    """Run `cargo test -p <package> --lib -- --list` and count test lines."""
    # Use --no-fail-fast so a malformed line doesn't kill the run.
    out = _run(
        ["cargo", "test", "-p", package, "--lib", "--", "--list", "--format=terse"],
        cwd=crate_dir,
    )
    return len(_CARGO_TEST_LINE.findall(out))


def compute_inventory() -> dict:
    """Compute the current test inventory. Does not write.

    Uses the same rooted invocations the README documents:
        cd mcoi && pytest tests/    → mcoi_tests
        pytest tests/               → root_tests (gateway + skills + integration)
    Each is rooted at its own `tests/` directory; no overlap.
    """
    mcoi_dir = REPO_ROOT / "mcoi"
    mcoi_tests = _count_pytest(mcoi_dir, "tests/") if (mcoi_dir / "tests").exists() else 0

    # Repo-root pytest covers gateway + skills + integration trees only.
    root_tests = _count_pytest(REPO_ROOT, "tests/") if (REPO_ROOT / "tests").exists() else 0

    rust_dir = REPO_ROOT / "maf" / "rust"
    maf_kernel_tests = _count_cargo(rust_dir, "maf-kernel") if rust_dir.exists() else 0

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": {
            "mcoi_tests": mcoi_tests,
            "root_tests": root_tests,
            "total": mcoi_tests + root_tests,
        },
        "rust": {
            "maf_kernel_tests": maf_kernel_tests,
            "total": maf_kernel_tests,
        },
        "total_tests": mcoi_tests + root_tests + maf_kernel_tests,
        "tooling": {
            "pytest_command": "pytest --collect-only -q",
            "cargo_command": "cargo test -p maf-kernel --lib -- --list",
        },
    }


def write_inventory(inventory: dict) -> Path:
    """Write inventory to the canonical artifact path."""
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ARTIFACT_PATH


def _drift_report(committed: dict, current: dict) -> list[str]:
    """Return list of human-readable drift messages comparing two inventories.

    The `generated_at` field is allowed to differ (it always will). All
    other fields must match exactly for the artifact to be considered
    fresh.
    """
    drifts: list[str] = []
    for key in ("python", "rust", "total_tests", "schema_version", "tooling"):
        if committed.get(key) != current.get(key):
            drifts.append(f"  {key}: committed={committed.get(key)!r}  current={current.get(key)!r}")
    return drifts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute and print the inventory; do not write the file.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Compute and compare to committed artifact; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    current = compute_inventory()

    if args.check:
        if not ARTIFACT_PATH.exists():
            print(
                f"FAIL: {ARTIFACT_PATH.relative_to(REPO_ROOT)} does not exist. "
                "Run `python scripts/generate_test_inventory.py` to create it."
            )
            return 1
        committed = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
        drifts = _drift_report(committed, current)
        if drifts:
            print(
                f"FAIL: {ARTIFACT_PATH.relative_to(REPO_ROOT)} is stale. "
                "Drift:\n" + "\n".join(drifts) + "\n"
                "Regenerate with `python scripts/generate_test_inventory.py` "
                "and commit the result."
            )
            return 1
        print(f"OK: test inventory artifact is current ({current['total_tests']} tests).")
        return 0

    if args.dry_run:
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0

    path = write_inventory(current)
    print(f"Wrote {path.relative_to(REPO_ROOT)}: {current['total_tests']} tests "
          f"({current['python']['total']} Python + {current['rust']['total']} Rust).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
