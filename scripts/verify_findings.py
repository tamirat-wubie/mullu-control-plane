#!/usr/bin/env python3
"""Independently re-verify self-audit findings before they are admitted.

Purpose: a self-audit "finding" must not be admitted on the finder's word. Each
finding carries a reproducible_command plus an explicit, checkable expectation of
what that command shows IF the claim is true. This tool re-runs the command in a
fresh subprocess and confirms the expectation holds. Findings whose evidence does
not reproduce are DROPPED -- which is how a confabulated finding (a claim with no
real evidence behind it) is caught before it reaches a diff or a reviewer.
Governance scope: the finding-admission gate for governed self-enhancement.
`--strict` makes any dropped finding fail CI (a confabulation signal); `--calibrate`
runs a known-verdict corpus and fails if this verifier cannot reproduce it (a
detector that fails its own baseline is untrusted, not a finding).
Dependencies: repository source tree; JSON findings/corpus files.
Invariants: deterministic given the same tree; admits a finding only when its
declared evidence command reproduces its declared expectation.

Expectation modes (finding["expect"]["mode"]):
  exit_zero            command exit code == 0
  exit_nonzero         command exit code != 0
  stdout_contains      value is a substring of combined stdout+stderr
  stdout_not_contains  value is NOT a substring of combined stdout+stderr
  stdout_sha256        sha256 of normalized output == value
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND_TIMEOUT_SECONDS = 60


def _run(command: str, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def evaluate(finding: dict, cwd: Path) -> tuple[bool, str]:
    """Return (reproduced, reason). reproduced=True means the evidence holds."""
    command = finding.get("reproducible_command")
    expect = finding.get("expect")
    if not command or not isinstance(expect, dict):
        return False, "malformed: missing reproducible_command or expect"
    mode = expect.get("mode")
    value = expect.get("value", "")
    try:
        code, out = _run(command, cwd)
    except Exception as exc:  # noqa: BLE001 - any run failure is non-reproduction
        return False, f"command failed to run: {exc}"

    if mode == "exit_zero":
        return code == 0, f"exit={code} (want 0)"
    if mode == "exit_nonzero":
        return code != 0, f"exit={code} (want !=0)"
    if mode == "stdout_contains":
        return value in out, f"substring {'found' if value in out else 'MISSING'}: {value!r}"
    if mode == "stdout_not_contains":
        return value not in out, f"substring {'absent' if value not in out else 'PRESENT'}: {value!r}"
    if mode == "stdout_sha256":
        actual = hashlib.sha256(_normalize(out).encode()).hexdigest()
        return actual == value, f"sha256 {'match' if actual == value else 'MISMATCH'} ({actual[:12]})"
    return False, f"unknown expect mode: {mode!r}"


def verify_file(path: Path, strict: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    findings = data.get("findings", [])
    cwd = path.parent
    admitted: list[dict] = []
    dropped: list[dict] = []
    print(f"== verify {path.name}: {len(findings)} finding(s) ==")
    for finding in findings:
        ok, reason = evaluate(finding, cwd)
        (admitted if ok else dropped).append(finding)
        tag = "ADMITTED" if ok else "DROPPED "
        print(f"  [{tag}] {finding.get('id', '?'):<24} {finding.get('claim', '')[:60]}")
        print(f"             evidence: {reason}")
    print(f"-- {len(admitted)} admitted, {len(dropped)} dropped (evidence did not reproduce)")
    if strict and dropped:
        print("STRICT: dropped finding(s) present -> confabulation signal -> FAIL")
        return 1
    return 0


def calibrate(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("calibration", [])
    cwd = path.parent
    mismatches: list[tuple[str, str, str, str]] = []
    print(f"== calibrate {path.name}: {len(cases)} known case(s) ==")
    for case in cases:
        expected = case["expected_verdict"]  # VERIFIED | REJECTED
        finding = case["finding"]
        ok, reason = evaluate(finding, cwd)
        actual = "VERIFIED" if ok else "REJECTED"
        match = actual == expected
        print(f"  [{'ok  ' if match else 'FAIL'}] {finding.get('id', '?'):<28} "
              f"expected={expected:<8} actual={actual:<8}")
        if not match:
            mismatches.append((finding.get("id", "?"), expected, actual, reason))
    if mismatches:
        print(f"CALIBRATION FAIL: {len(mismatches)} mismatch(es) -> verifier is UNTRUSTED")
        for fid, exp, act, reason in mismatches:
            print(f"    {fid}: expected {exp} got {act} ({reason})")
        return 2
    print("CALIBRATION PASS: verifier reproduces all known verdicts -> trusted")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently re-verify self-audit findings.")
    parser.add_argument("file", type=Path, help="findings JSON (or calibration corpus with --calibrate)")
    parser.add_argument("--calibrate", action="store_true", help="run as a known-verdict calibration corpus")
    parser.add_argument("--strict", action="store_true", help="fail (exit 1) if any finding is dropped")
    args = parser.parse_args(argv)
    if not args.file.exists():
        print(f"no such file: {args.file}")
        return 3
    return calibrate(args.file) if args.calibrate else verify_file(args.file, args.strict)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
