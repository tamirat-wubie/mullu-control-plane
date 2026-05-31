#!/usr/bin/env python3
"""No-float-in-decision-modules lint (spec invariant I-PRED-17).

Spec mapping: I-PRED-17 — "no float in decision-affecting ops". The
prediction/judgement determinism guarantee (bit-deterministic replay)
depends on decision paths using integer / bounded arithmetic, never
IEEE-754 floats whose rounding is platform-sensitive.

This is a RATCHET lint, not a clean-slate one. The gateway's decision
modules are float-clean except for a small, fully-enumerated set of
``confidence`` occurrences. ``confidence`` is informational metadata on an
operational claim; it is never read by a closure, commit, or admission
decision — those gate on booleans (verified / succeeded / reconciled). Each
known occurrence is listed in ALLOWLIST with justification. The lint fails
on any NEW float token introduced into a decision module that is not
explicitly allowlisted, so the float footprint can only shrink, never grow,
without a deliberate, reviewed allowlist edit.

Usage:
  python scripts/check_no_float_in_decision_modules.py    # exit 1 on violation
"""

from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
GATEWAY_DIR = REPO_ROOT / "gateway"

# Decision-affecting modules: the governance / prediction / judgement
# surfaces whose arithmetic must stay deterministic.
DECISION_MODULES: tuple[str, ...] = (
    "causal_closure_kernel.py",
    "command_spine.py",
    "plan_ledger.py",
    "audit_trace_verifier.py",
    "conformance.py",
    "authority_obligation_mesh.py",
)

# Float tokens of interest. The decimal-literal arm uses a negative
# lookbehind so attribute chains / dotted version strings (e.g.
# ``schema/2020-12``) do not produce false positives — only bare numeric
# literals like ``1.0`` / ``0.5`` match.
_FLOAT_TOKEN = re.compile(
    r":\s*float\b"            # type annotation:  x: float
    r"|\bfloat\s*\("          # builtin call:     float(...)
    r"|(?<![\w.])\d+\.\d+"    # decimal literal:  1.0, 0.5
    r"|\bf32\b|\bf64\b"       # rust-style float widths
)

# Allowlisted occurrences: stripped source lines permitted to carry a float
# token, each justified below. A line matches only if its stripped content
# is exactly one of these strings, so a NEW float on a different line is
# never silently accepted.
#
# Justification — every entry is the ``confidence`` field of an operational
# claim. ``confidence`` is informational provenance metadata; no closure
# certificate, commit decision, or capability-admission gate reads it. The
# kernel's gating predicates are booleans (verified / succeeded /
# reconciled). These occurrences are therefore outside the I-PRED-17
# decision-path scope. Converting ``confidence`` to fixed-point is tracked
# separately; until then it is pinned here so it cannot proliferate.
ALLOWLIST: dict[str, set[str]] = {
    "causal_closure_kernel.py": {
        "confidence=0.0,",
    },
    "command_spine.py": {
        "confidence: float",
        "confidence: float = 1.0,",
        "if confidence < 0.0 or confidence > 1.0:",
        'confidence=float(raw_claim["confidence"]),',
    },
}


def _strip_comment(line: str) -> str:
    # Conservative: drop a trailing comment only when '#' is not inside a
    # string. Sufficient for these modules — no decision line embeds '#' in
    # a string literal alongside a float token.
    if "#" in line:
        return line.split("#", 1)[0]
    return line


def find_violations() -> list[str]:
    """Return human-readable violation strings (empty list == clean)."""
    violations: list[str] = []
    for module in DECISION_MODULES:
        path = GATEWAY_DIR / module
        if not path.exists():
            violations.append(f"{module}: MISSING decision module (expected at {path})")
            continue
        allow = ALLOWLIST.get(module, set())
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not _FLOAT_TOKEN.search(_strip_comment(raw)):
                continue
            if raw.strip() in allow:
                continue
            violations.append(
                f"{module}:{lineno}: float token in decision module: {raw.strip()}"
            )
    return violations


def main() -> int:
    violations = find_violations()
    if not violations:
        print(f"no-float lint: OK ({len(DECISION_MODULES)} decision modules clean)")
        return 0
    print("no-float lint: FAIL - float tokens in decision modules (I-PRED-17):")
    for violation in violations:
        print(f"  {violation}")
    print(
        "\nIf a float is genuinely required and does NOT gate a decision, add the "
        "exact stripped line to ALLOWLIST in "
        "scripts/check_no_float_in_decision_modules.py with a justification."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
