#!/usr/bin/env python3
"""Run bounded MCOI pytest shards.

Purpose: provide one deterministic entry point for the large MCOI runtime test
surface so local runs and CI use the same shard boundaries.
Governance scope: local pytest execution, marker isolation, shard inventory,
and machine-readable execution receipts.
Dependencies: Python, pytest, and the repository-local mcoi/tests tree.
Invariants:
  - Default execution excludes soak, live-provider, PostgreSQL, and SMTP lanes.
  - Soak execution remains explicit and still excludes live/infra lanes.
  - Shard targets are deterministic and bounded by directory or filename prefix.
  - Oversized filename prefixes are split into deterministic sub-shards.
  - No shell command construction is used for test execution.
  - The ``--serial-full`` lane runs the whole tests/ tree in one process with
    the same non-soak/non-infra/non-live marker, to catch cross-test and
    global-state pollution that per-shard isolation structurally hides.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
MCOI_TESTS = MCOI_ROOT / "tests"

LOCAL_INFRA_EXCLUSION = "not live_provider and not infra_pg and not infra_smtp"
DEFAULT_MARKER = f"not soak and {LOCAL_INFRA_EXCLUSION}"
SOAK_MARKER = f"soak and {LOCAL_INFRA_EXCLUSION}"
DEFAULT_PYTEST_FLAGS = ("-q", "--tb=short", "--maxfail=1")


@dataclass(frozen=True, slots=True)
class ShardSpec:
    """One deterministic MCOI shard boundary."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ShardRun:
    """Machine-readable result for one shard execution."""

    shard: str
    command: tuple[str, ...]
    target_count: int
    returncode: int
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str
    dry_run: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "shard": self.shard,
            "command": list(self.command),
            "target_count": self.target_count,
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "dry_run": self.dry_run,
        }


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


SHARDS: tuple[ShardSpec, ...] = (
    ShardSpec("intent_substrate", "intent substrate tests under tests/intent_substrate"),
    ShardSpec("a-c", "top-level tests with filenames test_a* through test_c*"),
    ShardSpec("d", "top-level tests with filenames test_d*"),
    ShardSpec("e", "top-level tests with filenames test_e*"),
    ShardSpec("f", "top-level tests with filenames test_f*"),
    ShardSpec("g", "top-level tests with filenames test_g*"),
    ShardSpec("h", "top-level tests with filenames test_h*"),
    ShardSpec("i", "top-level tests with filenames test_i*"),
    ShardSpec("j", "top-level tests with filenames test_j*"),
    ShardSpec("k", "top-level tests with filenames test_k*"),
    ShardSpec("l", "top-level tests with filenames test_l*"),
    ShardSpec("m", "top-level tests with filenames test_m*"),
    ShardSpec("n", "top-level tests with filenames test_n*"),
    ShardSpec("o", "top-level tests with filenames test_o*"),
    ShardSpec("pa-pe", "top-level tests with filenames test_pa* through test_pe*"),
    ShardSpec("ph-pl", "top-level tests with filenames test_ph* through test_pl*"),
    ShardSpec("po", "top-level tests with filenames test_po*"),
    ShardSpec("pr", "top-level tests with filenames test_pr*"),
    ShardSpec("pu", "top-level tests with filenames test_pu*"),
    ShardSpec("q", "top-level tests with filenames test_q*"),
    ShardSpec("r", "top-level tests with filenames test_r*"),
    ShardSpec("s", "top-level tests with filenames test_s*"),
    ShardSpec("t", "top-level tests with filenames test_t*"),
    ShardSpec("u", "top-level tests with filenames test_u*"),
    ShardSpec("v", "top-level tests with filenames test_v*"),
    ShardSpec("w", "top-level tests with filenames test_w*"),
)
SHARD_BY_NAME = {shard.name: shard for shard in SHARDS}
PREFIX_SHARD_FILTERS: dict[str, tuple[str, ...]] = {
    "pa-pe": ("pa", "pb", "pc", "pd", "pe"),
    "ph-pl": ("ph", "pi", "pj", "pk", "pl"),
    "po": ("po",),
    "pr": ("pr",),
    "pu": ("pu",),
}


def shard_names() -> tuple[str, ...]:
    """Return the canonical non-soak shard names in execution order."""
    return tuple(shard.name for shard in SHARDS)


def resolve_shard_files(shard_name: str) -> tuple[Path, ...]:
    """Resolve one shard name to repository-local pytest target files."""
    if shard_name not in SHARD_BY_NAME:
        raise ValueError(f"unknown MCOI shard: {shard_name}")
    if shard_name == "intent_substrate":
        return _relative_paths(sorted((MCOI_TESTS / "intent_substrate").glob("test_*.py")))
    if shard_name in PREFIX_SHARD_FILTERS:
        prefixes = PREFIX_SHARD_FILTERS[shard_name]
        files = [
            path
            for path in sorted(MCOI_TESTS.glob("test_*.py"))
            if _filename_stem(path).startswith(prefixes)
        ]
        return _relative_paths(files)
    allowed_letters = _letters_for_shard(shard_name)
    files = [
        path
        for path in sorted(MCOI_TESTS.glob("test_*.py"))
        if _filename_letter(path) in allowed_letters
    ]
    return _relative_paths(files)


def build_shard_command(
    shard_name: str,
    *,
    extra_pytest_args: Sequence[str] = (),
) -> tuple[str, ...]:
    """Build the exact pytest command for one non-soak shard."""
    targets = tuple(str(path).replace("\\", "/") for path in resolve_shard_files(shard_name))
    if not targets:
        raise ValueError(f"MCOI shard has no targets: {shard_name}")
    return (
        sys.executable,
        "-m",
        "pytest",
        *targets,
        *DEFAULT_PYTEST_FLAGS,
        "-m",
        DEFAULT_MARKER,
        *extra_pytest_args,
    )


def build_soak_command(*, extra_pytest_args: Sequence[str] = ()) -> tuple[str, ...]:
    """Build the explicit local soak pytest command."""
    return (
        sys.executable,
        "-m",
        "pytest",
        "tests",
        *DEFAULT_PYTEST_FLAGS,
        "-m",
        SOAK_MARKER,
        *extra_pytest_args,
    )


def build_serial_full_command(*, extra_pytest_args: Sequence[str] = ()) -> tuple[str, ...]:
    """Build the single-process, whole-suite pytest command.

    Runs the entire ``mcoi/tests`` tree in ONE pytest process with the same
    non-soak / non-infra / non-live marker the shards use. Unlike the shards
    (which split by filename and run in separate processes / CI jobs), this lane
    deliberately co-executes every test in one process so that cross-test,
    global-singleton, and module-state pollution is exercised -- the class of
    bug the sharded PR gate structurally cannot see (a polluter and its victim
    land in different shards). ``--maxfail`` is intentionally omitted so the run
    reports the complete failure list rather than stopping at the first.
    """
    return (
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "-m",
        DEFAULT_MARKER,
        *extra_pytest_args,
    )


def run_shards(
    selected_shards: Iterable[str],
    *,
    include_soak: bool = False,
    soak_only: bool = False,
    extra_pytest_args: Sequence[str] = (),
    dry_run: bool = False,
    emit_progress: bool = True,
    runner: CommandRunner = subprocess.run,
) -> tuple[ShardRun, ...]:
    """Run selected MCOI shards and return execution receipts."""
    runs: list[ShardRun] = []
    shard_sequence = () if soak_only else tuple(selected_shards)
    for shard_name in shard_sequence:
        command = build_shard_command(shard_name, extra_pytest_args=extra_pytest_args)
        runs.append(
            _execute_command(
                shard_name,
                command,
                len(resolve_shard_files(shard_name)),
                dry_run,
                runner,
                emit_progress=emit_progress,
            )
        )
        if runs[-1].returncode != 0:
            return tuple(runs)
    if include_soak or soak_only:
        command = build_soak_command(extra_pytest_args=extra_pytest_args)
        runs.append(_execute_command("soak", command, 1, dry_run, runner, emit_progress=emit_progress))
    return tuple(runs)


def _execute_command(
    shard_name: str,
    command: tuple[str, ...],
    target_count: int,
    dry_run: bool,
    runner: CommandRunner,
    *,
    emit_progress: bool,
) -> ShardRun:
    started = time.perf_counter()
    if emit_progress:
        mode = "DRY-RUN" if dry_run else "RUN"
        print(f"[{mode}] {shard_name}: targets={target_count}", flush=True)
    if dry_run:
        return ShardRun(
            shard=shard_name,
            command=command,
            target_count=target_count,
            returncode=0,
            elapsed_seconds=0.0,
            stdout_tail="",
            stderr_tail="",
            dry_run=True,
        )
    completed = runner(
        list(command),
        cwd=str(MCOI_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if emit_progress:
        status = "PASS" if completed.returncode == 0 else "FAIL"
        print(f"[{status}] {shard_name}: elapsed={elapsed:.2f}s", flush=True)
    return ShardRun(
        shard=shard_name,
        command=command,
        target_count=target_count,
        returncode=int(completed.returncode),
        elapsed_seconds=elapsed,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _letters_for_shard(shard_name: str) -> frozenset[str]:
    if "-" not in shard_name:
        return frozenset({shard_name})
    start, end = shard_name.split("-", 1)
    if len(start) != 1 or len(end) != 1:
        raise ValueError(f"invalid letter shard: {shard_name}")
    return frozenset(chr(code) for code in range(ord(start), ord(end) + 1))


def _filename_letter(path: Path) -> str:
    stem = _filename_stem(path)
    if not stem:
        return ""
    return stem[0]


def _filename_stem(path: Path) -> str:
    stem = path.stem.lower()
    if not stem.startswith("test_") or len(stem) <= len("test_"):
        return ""
    return stem[len("test_"):]


def _relative_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    return tuple(path.relative_to(MCOI_ROOT) for path in paths)


def _tail(value: str, *, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def _print_text_summary(runs: Sequence[ShardRun]) -> None:
    for run in runs:
        status = "PASS" if run.returncode == 0 else "FAIL"
        dry = " dry-run" if run.dry_run else ""
        print(
            f"[{status}] {run.shard}{dry}: targets={run.target_count} "
            f"elapsed={run.elapsed_seconds:.2f}s"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--shard", action="append", choices=shard_names(), help="Run one shard; repeatable.")
    parser.add_argument("--include-soak", action="store_true", help="Run local soak after non-soak shards.")
    parser.add_argument("--soak-only", action="store_true", help="Run only local soak tests.")
    parser.add_argument(
        "--serial-full",
        action="store_true",
        help="Run the whole tests/ tree in ONE process (catches cross-shard "
        "pollution the sharded gate cannot). Ignores --shard.",
    )
    parser.add_argument("--pytest-arg", action="append", default=[], help="Append an extra pytest argument.")
    parser.add_argument("--list", action="store_true", help="List canonical shard names and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned commands without executing tests.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable run receipts.")
    args = parser.parse_args(argv)

    if args.serial_full:
        command = build_serial_full_command(extra_pytest_args=tuple(args.pytest_arg))
        run = _execute_command(
            "serial-full",
            command,
            target_count=1,
            dry_run=bool(args.dry_run),
            runner=subprocess.run,
            emit_progress=not bool(args.json),
        )
        if args.json:
            print(json.dumps([run.as_dict()], indent=2, sort_keys=True))
        return 0 if run.returncode == 0 else 1

    if args.list:
        payload = [{"name": shard.name, "description": shard.description} for shard in SHARDS]
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for shard in SHARDS:
                print(f"{shard.name}: {shard.description}")
        return 0

    selected = tuple(args.shard) if args.shard else shard_names()
    runs = run_shards(
        selected,
        include_soak=bool(args.include_soak),
        soak_only=bool(args.soak_only),
        extra_pytest_args=tuple(args.pytest_arg),
        dry_run=bool(args.dry_run),
        emit_progress=not bool(args.json),
    )
    if args.json:
        print(json.dumps([run.as_dict() for run in runs], indent=2, sort_keys=True))
    return 0 if all(run.returncode == 0 for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
