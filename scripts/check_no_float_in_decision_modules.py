#!/usr/bin/env python3
"""No-float-in-decision-modules lint (spec invariant I-PRED-17).

Spec mapping: I-PRED-17 — "no float in decision-affecting ops". The
prediction/judgement determinism guarantee depends on decision paths using
integer / bounded arithmetic, never IEEE-754 floats whose rounding is
platform-sensitive and breaks bit-deterministic replay.

This is a RATCHET lint, not a clean-slate one. The gateway's decision
modules are float-clean except for a small, documented set of informational
confidence fields that do not gate any decision (the closure kernel gates on
booleans: verified / succeeded / reconciled). Those known occurrences are
listed in ALLOWLIST with justification. The lint fails on any NEW float
token introduced into a decision module that is not explicitly allowlisted —
so the float footprint can only shrink, never grow, without a deliberate,
reviewed allowlist edit.

Usage:
  python scripts/check_no_float_in_decision_modules.py        # exit 1 on violation
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GATEWAY_DIR = REPO_ROOT / "gateway"

# Decision-affecting modules. These are the governance / prediction /
# judgement surfaces whose arithmetic must stay deterministic.
DECISION_MODULES: tuple[str, ...] = (
    "causal_closure_kernel.py",
    "command_spine.py",
    "plan_ledger.py",
    "audit_trace_verifier.py",
    "conformance.py",
    "authority_obligation_mesh.py",
)

# Float tokens we care about: float type annotations, the float() builtin,
# decimal literals, and Rust-style f32/f64 (defensive, for any embedded
# contract stubs).
_FLOAT_TOKEN = re.compile(
    r":\s*float\b"        # type annotation:  x: float
    r"|\bfloat\s*\("      # builtin call:     float(...)
    r"|(?<![\w.])\d+\.\d+"  # decimal literal: 1.0, 0.5  (not x.1.2 attribute chains)
    r"|\bf32\b|\bf64\b"   # rust-style float widths
)

# Allowlisted occurrences: stripped source lines that are permitted to carry
# a float token, each with a justification. A line matches only if its
# stripped content is exactly one of these strings, so a NEW float on a
# different line is never silently accepted.
#
# Justification for the entries below:
#   command_spine.py — `confidence: float = 1.0` appears on the
#   record_operational_claim / claim-construction signatures. `confidence`
#   is informational metadata attached to an operational claim; no closure,
#   commit, or admission decision reads it. The kernel's gating predicates
#   are booleans (verified / succeeded / reconciled). The field is therefore
#   outside the I-PRED-17 decision-path scope.
ALLOWLIST: dict[str, set[str]] = {
    "command_spine.py": {
        "confidence: float = 1.0,",
    },
}


def _strip_comment(line: str) -> str:
    # Conservative: drop a trailing "# ..." comment only when the '#' is not
    # inside a string. For these modules a naive split is sufficient because
    # no decision line embeds '#' in a string literal alongside a float.
    if "#" in line:
        return line.split("#", 1)[0]
    return line


def find_violations() -> list[str]:
    """Return a list of human-readable violation strings (empty == clean)."""
    violations: list[str] = []
    for module in DECISION_MODULES:
        path = GATEWAY_DIR / module
        if not path.exists():
            violations.append(f"{module}: MISSING decision module (expected at {path})")
            continue
        allow = ALLOWLIST.get(module, set())
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            code = _strip_comment(raw)
            if not _FLOAT_TOKEN.search(code):
                continue
            if raw.strip() in allow:
                continue
            violations.append(f"{module}:{lineno}: float token in decision module: {raw.strip()}")
    return violations


def main() -> int:
    violations = find_violations()
    if not violations:
        print(f"no-float lint: OK ({len(DECISION_MODULES)} decision modules clean)")
        return 0
    print("no-float lint: FAIL — float tokens in decision modules (I-PRED-17):")
    for violation in violations:
        print(f"  {violation}")
    print(
        "\nIf a float is genuinely required and does NOT gate a decision, add the "
        "exact stripped line to ALLOWLIST in scripts/check_no_float_in_decision_modules.py "
        "with a justification."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
