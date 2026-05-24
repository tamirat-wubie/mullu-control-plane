"""Purpose: contract tests for the MCOI shard runner.
Governance scope: deterministic shard inventory, local marker isolation, and
dry-run command receipts.
Dependencies: scripts.run_mcoi_shards and repository-local mcoi tests.
Invariants:
  - Default shards exclude known empty letter prefixes.
  - Non-soak commands exclude soak and live/infra markers.
  - Soak commands remain explicit and still exclude live/infra markers.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_mcoi_shards  # noqa: E402


def test_shard_inventory_is_deterministic_and_excludes_empty_prefixes() -> None:
    names = run_mcoi_shards.shard_names()

    assert names[:2] == ("intent_substrate", "a-c")
    assert names[-4:] == ("t", "u", "v", "w")
    assert "p" not in names
    assert {"pa-pe", "ph-pl", "po", "pr", "pu"}.issubset(set(names))
    assert "q" not in names
    assert "x" not in names
    assert "y" not in names
    assert "z" not in names


def test_non_soak_shards_cover_each_top_level_mcoi_file_once() -> None:
    shard_paths = [
        path
        for shard_name in run_mcoi_shards.shard_names()
        if shard_name != "intent_substrate"
        for path in run_mcoi_shards.resolve_shard_files(shard_name)
    ]
    top_level_paths = tuple(
        path.relative_to(run_mcoi_shards.MCOI_ROOT)
        for path in sorted(run_mcoi_shards.MCOI_TESTS.glob("test_*.py"))
    )

    assert sorted(shard_paths) == sorted(top_level_paths)
    assert len(shard_paths) == len(set(shard_paths))
    assert any(path.name.startswith("test_postgres") for path in run_mcoi_shards.resolve_shard_files("po"))


def test_non_soak_shard_command_has_local_marker_boundary() -> None:
    command = run_mcoi_shards.build_shard_command("n")
    targets = run_mcoi_shards.resolve_shard_files("n")

    assert command[:3] == (sys.executable, "-m", "pytest")
    assert run_mcoi_shards.DEFAULT_MARKER in command
    marker = command[command.index(run_mcoi_shards.DEFAULT_MARKER)]
    assert "not soak" in marker
    assert "not live_provider" in marker
    assert targets
    assert all(path.name.startswith("test_n") for path in targets)


def test_soak_command_keeps_live_and_infra_markers_excluded() -> None:
    command = run_mcoi_shards.build_soak_command()

    assert "tests" in command
    assert run_mcoi_shards.SOAK_MARKER in command
    marker = command[command.index(run_mcoi_shards.SOAK_MARKER)]
    assert "soak and not live_provider" in marker
    assert "not infra_pg" in marker
    assert "not infra_smtp" in marker


def test_dry_run_returns_receipts_without_invoking_runner() -> None:
    def blocked_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("dry-run must not invoke subprocess")

    runs = run_mcoi_shards.run_shards(("n",), dry_run=True, runner=blocked_runner)

    assert len(runs) == 1
    assert runs[0].dry_run is True
    assert runs[0].returncode == 0
    assert runs[0].target_count == len(run_mcoi_shards.resolve_shard_files("n"))
