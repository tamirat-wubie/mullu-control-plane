#!/usr/bin/env python3
"""Nightly Tamper Drill — exercises the audit ledger verifier against
real exported ledgers and known-tampered variants.

Purpose: G3.7 — convert "the verifier works" into "the verifier works
continuously". A future refactor that breaks the verifier's tamper
detection would otherwise go unnoticed until a real audit. This drill
is the canonical regression catch.

Steps (each must produce the documented outcome — any divergence is a
hard failure):

  1. Build a real chain of N governed-equivalent entries.
  2. Export to JSONL.
  3. Run `mcoi verify-ledger` → assert exit 0.
  4. Mutate one byte in a detail field → assert exit 1, failure_field=entry_hash.
  5. Delete a middle entry without rewriting → assert exit 1, failure_field=sequence.
  6. Append entry with schema_version=999 → assert exit 3, failure_field=schema.
  7. Drop a required field → assert exit 3, failure_field=schema.
  8. Tamper with previous_hash → assert exit 1, failure_field=previous_hash.
  9. Slice without anchor (entries 5-10) → must NOT pass.
  10. Slice WITH correct anchor → must pass.

Exit code: 0 if all 10 scenarios produce the expected outcome, 1 otherwise.

Usage:
  python scripts/nightly_tamper_drill.py
  python scripts/nightly_tamper_drill.py --entries 200  # default 50
  python scripts/nightly_tamper_drill.py --verbose

CI: see .github/workflows/nightly_tamper_drill.yml
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"
sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.core.audit_trail import (  # noqa: E402
    AuditTrail,
    LEDGER_SCHEMA_VERSION_MAX,
    _canonical_hash_v1,
)


def _clock() -> str:
    return "2026-04-26T12:00:00Z"


def _build_chain(n: int) -> list[dict]:
    """Build a real audit chain via the writer."""
    trail = AuditTrail(clock=_clock)
    for i in range(n):
        trail.record(
            action=f"action.{i % 5}",
            actor_id=f"actor-{i % 3}",
            tenant_id=f"tenant-{i % 2}",
            target=f"resource/{i}",
            outcome="success" if i % 7 != 0 else "denied",
            detail={"index": i, "payload": "x" * (i % 50)},
        )
    return [asdict(e) for e in trail.query(limit=n + 100)]


def _write_jsonl(entries: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _run_verifier(input_path: Path, *extra_args: str) -> tuple[int, str]:
    """Invoke `mcoi verify-ledger` as a subprocess (the way operators do).

    Returns (exit_code, stdout). Stderr is captured into stdout for
    simpler asserting.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(MCOI_PATH), env.get("PYTHONPATH", "")])
    )
    cmd = [
        sys.executable, "-m", "mcoi_runtime.app.cli",
        "verify-ledger", str(input_path), *extra_args,
    ]
    proc = subprocess.run(
        cmd, env=env, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


class DrillFailure(Exception):
    pass


def _assert(cond: bool, scenario: str, detail: str = "") -> None:
    if not cond:
        raise DrillFailure(f"[{scenario}] {detail}")


def _expect(scenario: str, exit_code: int, output: str,
            *, expected_exit: int, expected_field: str | None = None,
            verbose: bool = False) -> None:
    if verbose:
        print(f"  {scenario}: exit={exit_code}")
    _assert(
        exit_code == expected_exit, scenario,
        f"expected exit {expected_exit}, got {exit_code}\n--output--\n{output}",
    )
    if expected_field is not None:
        marker = f"failure_field: {expected_field}"
        _assert(
            marker in output, scenario,
            f"expected '{marker}' in output\n--output--\n{output}",
        )


def run_drill(num_entries: int = 50, verbose: bool = False) -> int:
    """Run all 10 tamper-drill scenarios. Returns 0 on full success, 1 otherwise."""
    print(f"=== Nightly Tamper Drill ({num_entries} entries) ===")
    tmpdir = Path(tempfile.mkdtemp(prefix="tamper_drill_"))
    path = tmpdir / "ledger.jsonl"
    failures: list[str] = []

    def scenario(name: str):
        if verbose:
            print(f"  -> {name}")

    try:
        # ── Build real chain ──
        scenario("building chain")
        entries = _build_chain(num_entries)
        _write_jsonl(entries, path)

        # 1. Valid → 0
        scenario("1. valid chain")
        try:
            code, out = _run_verifier(path)
            _expect("1.valid", code, out, expected_exit=0, verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 2. Mutate one byte in detail → 1, entry_hash
        scenario("2. byte tamper in detail")
        try:
            tampered = copy.deepcopy(entries)
            tampered[len(tampered) // 2]["detail"] = {"tampered": True}
            _write_jsonl(tampered, path)
            code, out = _run_verifier(path)
            _expect("2.entry_hash", code, out,
                    expected_exit=1, expected_field="entry_hash", verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 3. Delete middle entry without rewriting → 1, sequence (G3.2)
        scenario("3. delete middle entry")
        try:
            gapped = copy.deepcopy(entries)
            del gapped[len(gapped) // 2]
            _write_jsonl(gapped, path)
            code, out = _run_verifier(path)
            _expect("3.sequence_gap", code, out,
                    expected_exit=1, expected_field="sequence", verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 4. Future schema version → 3, schema (G3.3)
        scenario("4. future schema version")
        try:
            future = copy.deepcopy(entries)
            future[0]["schema_version"] = LEDGER_SCHEMA_VERSION_MAX + 99
            _write_jsonl(future, path)
            code, out = _run_verifier(path)
            _expect("4.future_version", code, out,
                    expected_exit=3, expected_field="schema", verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 5. Drop required field → 3, schema (G3.5 split)
        scenario("5. drop required field")
        try:
            broken = copy.deepcopy(entries)
            del broken[0]["entry_hash"]
            _write_jsonl(broken, path)
            code, out = _run_verifier(path)
            _expect("5.schema_drop", code, out,
                    expected_exit=3, expected_field="schema", verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 6. Tamper previous_hash → 1, previous_hash
        scenario("6. tamper previous_hash")
        try:
            link_break = copy.deepcopy(entries)
            link_break[1]["previous_hash"] = "f" * 64
            _write_jsonl(link_break, path)
            code, out = _run_verifier(path)
            _expect("6.previous_hash", code, out,
                    expected_exit=1, expected_field="previous_hash", verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 7. Bare slice without anchor → must NOT pass (G3.4)
        scenario("7. bare slice without anchor")
        try:
            mid = num_entries // 2
            _write_jsonl(entries, path)
            code, out = _run_verifier(
                path, "--from-sequence", str(mid),
            )
            _expect("7.bare_slice", code, out,
                    expected_exit=1, verbose=verbose)
            # Warning must be present
            _assert(
                "warning:" in out.lower(),
                "7.bare_slice",
                "expected slice-without-anchor warning",
            )
        except DrillFailure as e:
            failures.append(str(e))

        # 8. Anchored slice → must pass (G3.4)
        scenario("8. anchored slice")
        try:
            mid = num_entries // 2
            anchor = entries[mid - 1]["entry_hash"]
            _write_jsonl(entries, path)
            code, out = _run_verifier(
                path,
                "--from-sequence", str(mid + 1),
                "--anchor-hash", anchor,
            )
            _expect("8.anchored_slice", code, out,
                    expected_exit=0, verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 9. Anchored slice with WRONG anchor → must fail
        scenario("9. anchored slice with wrong anchor")
        try:
            mid = num_entries // 2
            _write_jsonl(entries, path)
            code, out = _run_verifier(
                path,
                "--from-sequence", str(mid + 1),
                "--anchor-hash", "0" * 64,
            )
            _expect("9.wrong_anchor", code, out,
                    expected_exit=1, expected_field="previous_hash", verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

        # 10. Empty file → 0 (empty chain is trivially valid)
        scenario("10. empty file")
        try:
            empty_path = tmpdir / "empty.jsonl"
            empty_path.touch()
            code, out = _run_verifier(empty_path)
            _expect("10.empty", code, out, expected_exit=0, verbose=verbose)
        except DrillFailure as e:
            failures.append(str(e))

    finally:
        # Cleanup
        for f in tmpdir.iterdir():
            f.unlink()
        tmpdir.rmdir()

    print()
    if failures:
        print(f"FAIL — {len(failures)} of 10 scenarios failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"OK — all 10 scenarios produced expected outcomes")
    print(f"     verifier proves: tamper-evidence under internal consistency")
    print(f"     verifier does NOT prove: event authenticity (see LEDGER_SPEC.md)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nightly tamper drill against the audit ledger verifier",
    )
    parser.add_argument(
        "--entries", type=int, default=50,
        help="Number of entries to build in the test chain (default: 50)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print each scenario as it runs",
    )
    args = parser.parse_args()
    return run_drill(num_entries=args.entries, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
