#!/usr/bin/env python3
"""Settled-merge barrier: refuse to merge a PR until its state is verified-settled.

Purpose: a merge must not proceed on an assumption that CI is green or that the
branch is unchanged. This gate makes "mergeable" unreachable unless a freshly
captured PR state proves ALL of:
  1. the PR is OPEN (not already merged/closed),
  2. GitHub reports it MERGEABLE,
  3. the commit CI ran on equals the live remote branch tip (no moved branch),
  4. the commit being merged equals the commit the operator verified (no drift
     since the human/agent looked),
  5. zero checks are IN_PROGRESS or QUEUED (CI has settled), and
  6. zero checks are FAILURE/ERROR/CANCELLED/TIMED_OUT (CI is green).

Governance scope: the merge-admission gate for governed self-enhancement. It
encodes the failure modes observed 2026-05-30 (premature "green" while CI still
running; a branch that moved under the operator via an external push; declaring
a merge done before confirming) as hard, checkable preconditions.
Dependencies: GitHub CLI (`gh`) for the live CLI path; the decision core itself
is pure and offline-testable.
Invariants: deterministic given the same state object; allows a merge only when
every precondition holds. No network access in the decision core.

CLI:
  python scripts/gate_merge.py --pr 862 --repo owner/name --expected-head <sha>
      Capture live state via gh, evaluate the gate, print the decision.
      Exit 0 = ALLOWED, 1 = BLOCKED, 2 = capture/usage error.
  python scripts/gate_merge.py --pr 862 --repo owner/name --expected-head <sha> --merge
      Additionally run `gh pr merge --squash --delete-branch` IFF allowed.

Importable API:
  evaluate_merge_gate(state: dict) -> MergeGateDecision
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

# Check conclusions that count as "not green".
FAILING_STATES = frozenset({"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE"})
# Check states that count as "not settled yet".
PENDING_STATES = frozenset({"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED"})


@dataclass
class MergeGateDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)  # why blocked (empty if allowed)
    summary: dict[str, Any] = field(default_factory=dict)


def evaluate_merge_gate(state: dict) -> MergeGateDecision:
    """Pure decision: given a captured PR state, decide whether merge may proceed.

    Expected `state` shape (all fields required; this is the contract the live
    capture must satisfy):
      {
        "pr_state": "OPEN" | "MERGED" | "CLOSED",
        "mergeable": "MERGEABLE" | "CONFLICTING" | "UNKNOWN",
        "pr_head": "<sha CI ran on, per the PR object>",
        "remote_tip": "<live `git ls-remote` tip of the PR branch>",
        "expected_head": "<sha the operator verified and intends to merge>",
        "checks": [ {"name": str, "state": "SUCCESS"|"IN_PROGRESS"|...}, ... ]
      }
    """
    reasons: list[str] = []

    required = ("pr_state", "mergeable", "pr_head", "remote_tip", "expected_head", "checks")
    missing = [k for k in required if k not in state]
    if missing:
        return MergeGateDecision(False, [f"malformed state: missing {missing}"], {})

    if state["pr_state"] != "OPEN":
        reasons.append(f"pr_state is {state['pr_state']!r}, not OPEN (already merged/closed?)")

    if state["mergeable"] != "MERGEABLE":
        reasons.append(f"mergeable is {state['mergeable']!r}, not MERGEABLE")

    pr_head = state["pr_head"]
    remote_tip = state["remote_tip"]
    expected = state["expected_head"]
    if pr_head != remote_tip:
        reasons.append(f"branch moved: PR head {pr_head[:12]} != remote tip {remote_tip[:12]} (CI may be for a stale commit)")
    if expected != pr_head:
        reasons.append(f"drift since verification: expected_head {expected[:12]} != PR head {pr_head[:12]}")
    if expected != remote_tip:
        reasons.append(f"drift since verification: expected_head {expected[:12]} != remote tip {remote_tip[:12]}")

    checks = state["checks"]
    if not isinstance(checks, list) or not checks:
        reasons.append("no checks present — refusing to merge a PR with zero CI signal")
        checks = []

    pending = [c["name"] for c in checks if str(c.get("state", "")).upper() in PENDING_STATES]
    failing = [c["name"] for c in checks if str(c.get("state", "")).upper() in FAILING_STATES]
    if pending:
        reasons.append(f"CI not settled: {len(pending)} pending check(s) e.g. {sorted(set(pending))[:3]}")
    if failing:
        reasons.append(f"CI not green: {len(failing)} failing check(s) e.g. {sorted(set(failing))[:3]}")

    summary = {
        "pr_state": state["pr_state"],
        "mergeable": state["mergeable"],
        "head_consistent": pr_head == remote_tip == expected,
        "checks_total": len(checks),
        "checks_pending": len(pending),
        "checks_failing": len(failing),
    }
    return MergeGateDecision(allowed=not reasons, reasons=reasons, summary=summary)


def _gh_json(args: list[str]) -> Any:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def capture_live_state(pr: int, repo: str, expected_head: str) -> dict:
    """Capture PR state from GitHub. Never types values by hand."""
    view = _gh_json(["pr", "view", str(pr), "--repo", repo, "--json", "state,mergeable,headRefOid,headRefName"])
    branch = view["headRefName"]
    ls = subprocess.run(["git", "ls-remote", f"https://github.com/{repo}.git", branch],
                        capture_output=True, text=True, timeout=60)
    remote_tip = ls.stdout.split("\t")[0].strip() if ls.stdout.strip() else ""
    checks = _gh_json(["pr", "checks", str(pr), "--repo", repo, "--json", "name,state"]) or []
    return {
        "pr_state": view["state"],
        "mergeable": view["mergeable"],
        "pr_head": view["headRefOid"],
        "remote_tip": remote_tip,
        "expected_head": expected_head,
        "checks": checks,
    }


def calibrate(path: str) -> int:
    data = json.loads(open(path, encoding="utf-8").read())
    cases = data.get("calibration", [])
    mismatches = []
    print(f"== calibrate {path}: {len(cases)} known case(s) ==")
    for case in cases:
        expected = case["expected_decision"]  # ALLOW | BLOCK
        decision = evaluate_merge_gate(case["state"])
        actual = "ALLOW" if decision.allowed else "BLOCK"
        match = actual == expected
        print(f"  [{'ok  ' if match else 'FAIL'}] {case.get('id','?'):<28} expected={expected:<5} actual={actual:<5}")
        if not match:
            mismatches.append((case.get("id"), expected, actual, decision.reasons))
    if mismatches:
        print(f"CALIBRATION FAIL: {len(mismatches)} mismatch(es) -> gate is UNTRUSTED")
        for cid, exp, act, reasons in mismatches:
            print(f"    {cid}: expected {exp} got {act} :: {reasons}")
        return 2
    print("CALIBRATION PASS: gate reproduces all known decisions -> trusted")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Settled-merge barrier for governed self-enhancement.")
    parser.add_argument("--pr", type=int, help="PR number")
    parser.add_argument("--repo", help="owner/name")
    parser.add_argument("--expected-head", help="commit SHA the operator verified and intends to merge")
    parser.add_argument("--merge", action="store_true", help="run gh pr merge --squash --delete-branch IFF allowed")
    parser.add_argument("--calibrate", help="path to a calibration corpus JSON; evaluate known decisions and exit")
    args = parser.parse_args(argv)

    if args.calibrate:
        return calibrate(args.calibrate)

    if not (args.pr and args.repo and args.expected_head):
        print("usage: --pr N --repo owner/name --expected-head <sha> [--merge]  (or --calibrate FILE)")
        return 2

    try:
        state = capture_live_state(args.pr, args.repo, args.expected_head)
    except Exception as exc:  # noqa: BLE001
        print(f"capture failed: {exc}")
        return 2

    decision = evaluate_merge_gate(state)
    print(json.dumps({"summary": decision.summary, "allowed": decision.allowed, "reasons": decision.reasons}, indent=2))
    if not decision.allowed:
        print("BLOCKED: merge preconditions not met.")
        return 1
    print("ALLOWED: all merge preconditions met.")
    if args.merge:
        merge = subprocess.run(
            ["gh", "pr", "merge", str(args.pr), "--repo", args.repo, "--squash", "--delete-branch"],
            capture_output=True, text=True, timeout=120,
        )
        if merge.returncode != 0:
            print(f"merge command failed: {merge.stderr.strip()}")
            return 1
        print("merged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
