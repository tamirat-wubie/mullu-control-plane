#!/usr/bin/env python3
"""Status-claim receipts: a status assertion is admitted only with captured evidence.

Purpose: the finding gate (scripts/verify_findings.py, #862) verifies *findings*;
the merge gate (scripts/gate_merge.py, #866) verifies *merges*. This closes the
remaining gap: free-floating *status assertions* such as "CI is green", "HEAD is
<sha>", "the PR is merged", "72 checks passed". Those were the failure mode
observed 2026-05-30 -- written before the capture that would confirm them.

A claim is admitted (SUPPORTED) only when a capture command is run by THIS tool
and the asserted value is EXTRACTED from the captured output and matches. The
value is never typed alongside the claim as the source of truth; it is compared
against live capture. Each evaluated claim yields a receipt -- the captured
evidence plus the verdict -- so a status report can be rendered FROM receipts and
is impossible to state without one.

Governance scope: the status-assertion gate for governed self-enhancement.
Dependencies: the capture command's own dependencies (e.g. gh, git); the
decision core is pure given a captured-output string.
Invariants: deterministic given the same captured output; admits a claim only
when the extracted value matches the asserted value; argv-only (no shell), like
the finding gate.

Extraction modes (claim["check"]["mode"]):
  equals          captured stdout (stripped) == value
  contains        value is a substring of captured stdout
  sha_equals      first whitespace token of stdout, prefix-compared to value
                  (so a 40-char tip matches an asserted 8-char short sha and v.v.)
  count_from_json json-parse stdout, follow check["path"] (dotted), == int(value)
  state_all       json-parse stdout (a list), every item[check["field"]] == value
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COMMAND_TIMEOUT_SECONDS = 60
_ALLOWED_EXECUTABLES = frozenset({"python", "python3", "py", "git", "gh", Path(sys.executable).name})
_REJECTED_TOKENS = frozenset({";", "&&", "||", "|", ">", ">>", "<", "<<"})
_REJECTED_SUBSTRINGS = ("$(", "`")


@dataclass
class ClaimReceipt:
    claim_id: str
    assertion: str
    supported: bool
    captured: str         # the live output the verdict was computed from
    detail: str           # human-readable reason
    extras: dict = field(default_factory=dict)


def _normalize_command(value: Any) -> list[str]:
    if isinstance(value, str):
        raise ValueError("capture_command must be an argv array, not a shell string")
    if not isinstance(value, list) or not value:
        raise ValueError("capture_command must be a non-empty argv array")
    argv: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"capture_command[{i}] must be a non-empty string")
        if item in _REJECTED_TOKENS:
            raise ValueError(f"rejected shell control token at argv[{i}]")
        if any(m in item for m in _REJECTED_SUBSTRINGS):
            raise ValueError(f"rejected shell substitution token at argv[{i}]")
        argv.append(item)
    if Path(argv[0]).name not in _ALLOWED_EXECUTABLES:
        raise ValueError(f"executable not allowed: {Path(argv[0]).name}")
    return argv


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def _check_extracted(mode: str, check: dict, captured: str) -> tuple[bool, str]:
    value = check.get("value", "")
    stripped = captured.replace("\r\n", "\n").strip()
    if mode == "equals":
        return stripped == value, f"equals: {'match' if stripped == value else 'MISMATCH'} (got {stripped[:40]!r})"
    if mode == "contains":
        return value in captured, f"contains: {'found' if value in captured else 'MISSING'} {value!r}"
    if mode == "sha_equals":
        token = stripped.split()[0] if stripped.split() else ""
        ok = bool(token) and bool(value) and (token.startswith(value) or value.startswith(token))
        return ok, f"sha_equals: captured {token[:12]!r} vs asserted {value!r} -> {'match' if ok else 'MISMATCH'}"
    if mode == "count_from_json":
        try:
            n = _dig(json.loads(stripped), check.get("path", ""))
        except Exception as exc:  # noqa: BLE001
            return False, f"count_from_json: parse/path error: {exc}"
        ok = int(n) == int(value)
        return ok, f"count_from_json[{check.get('path','')}]: got {n} vs asserted {value} -> {'match' if ok else 'MISMATCH'}"
    if mode == "state_all":
        try:
            items = json.loads(stripped)
            field_name = check["field"]
        except Exception as exc:  # noqa: BLE001
            return False, f"state_all: parse error: {exc}"
        if not isinstance(items, list) or not items:
            return False, "state_all: captured output is not a non-empty JSON list"
        bad = [it for it in items if str(it.get(field_name)) != value]
        return not bad, f"state_all[{field_name}=={value!r}]: {len(items)-len(bad)}/{len(items)} match" + (f", {len(bad)} not" if bad else "")
    return False, f"unknown mode: {mode!r}"


def evaluate_claim(claim: dict, cwd: Path) -> ClaimReceipt:
    cid = claim.get("id", "?")
    assertion = claim.get("assertion", "")
    check = claim.get("check")
    cmd = claim.get("capture_command")
    if not isinstance(check, dict) or cmd is None:
        return ClaimReceipt(cid, assertion, False, "", "malformed: missing capture_command or check")
    try:
        argv = _normalize_command(cmd)
        proc = subprocess.run(argv, shell=False, cwd=str(cwd), capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS)
        captured = (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return ClaimReceipt(cid, assertion, False, "", f"capture failed: {exc}")
    ok, detail = _check_extracted(check.get("mode", ""), check, captured)
    return ClaimReceipt(cid, assertion, ok, captured.strip()[:500], detail)


def verify_file(path: Path, strict: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    claims = data.get("claims", [])
    cwd = path.parent
    supported, unsupported = [], []
    print(f"== verify {path.name}: {len(claims)} claim(s) ==")
    for claim in claims:
        r = evaluate_claim(claim, cwd)
        (supported if r.supported else unsupported).append(r)
        print(f"  [{'SUPPORTED' if r.supported else 'UNSUPPORTED'}] {r.claim_id:<24} {r.assertion[:54]}")
        print(f"             {r.detail}")
    print(f"-- {len(supported)} supported, {len(unsupported)} unsupported")
    if strict and unsupported:
        print("STRICT: unsupported claim(s) present -> confabulation signal -> FAIL")
        return 1
    return 0


def calibrate(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("calibration", [])
    cwd = path.parent
    mismatches = []
    print(f"== calibrate {path.name}: {len(cases)} known case(s) ==")
    for case in cases:
        expected = case["expected_verdict"]  # SUPPORTED | UNSUPPORTED
        r = evaluate_claim(case["claim"], cwd)
        actual = "SUPPORTED" if r.supported else "UNSUPPORTED"
        match = actual == expected
        print(f"  [{'ok  ' if match else 'FAIL'}] {case['claim'].get('id','?'):<26} expected={expected:<11} actual={actual:<11}")
        if not match:
            mismatches.append((case["claim"].get("id"), expected, actual, r.detail))
    if mismatches:
        print(f"CALIBRATION FAIL: {len(mismatches)} mismatch(es) -> verifier is UNTRUSTED")
        for cid, exp, act, detail in mismatches:
            print(f"    {cid}: expected {exp} got {act} ({detail})")
        return 2
    print("CALIBRATION PASS: verifier reproduces all known verdicts -> trusted")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify status-claim receipts against captured evidence.")
    p.add_argument("file", type=Path, help="claims JSON (or calibration corpus with --calibrate)")
    p.add_argument("--calibrate", action="store_true", help="run as a known-verdict calibration corpus")
    p.add_argument("--strict", action="store_true", help="fail (exit 1) if any claim is unsupported")
    args = p.parse_args(argv)
    if not args.file.exists():
        print(f"no such file: {args.file}")
        return 3
    return calibrate(args.file) if args.calibrate else verify_file(args.file, args.strict)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
