"""Receipt-coverage ratchet: holds the count of uncovered state-mutating
routes at a known baseline and fails any change that drifts away from it.

The companion validator script is `scripts/validate_receipt_coverage.py`.
That script enumerates every state-mutating HTTP route declared in
`mcoi/mcoi_runtime/app/routers/` and `gateway/server.py` +
`gateway/capability_worker.py`, then classifies each as
MIDDLEWARE_API, MIDDLEWARE_GATEWAY, MIDDLEWARE_MUSIA, DIRECT_RECEIPT,
EXCLUDED, or UNCOVERED.

The ratchet here pins UNCOVERED count to `EXPECTED_UNCOVERED_BASELINE`.
Any drift fails:

  - A new uncovered route is added → count exceeds baseline → fail.
    The contributor must either route through middleware, add an
    EXCLUSIONS entry with justification, or (only with reviewer
    consent and an explanation in the PR) bump the baseline upward.

  - An uncovered route gets covered → count below baseline → fail.
    The contributor ratchets the baseline DOWN by the number of newly-
    covered routes. This makes coverage progress visible at review.

The baseline is intentionally pinned to a single integer. It is the
debt counter the spec's coverage-invariant section refers to.

This closes the "Coverage invariant not CI-enforced" gap from
`docs/MAF_RECEIPT_COVERAGE.md`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# scripts/ is not a package, so add it to sys.path for import.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_receipt_coverage import compute_buckets  # noqa: E402

# Baseline established at 2026-04-28 by the first run of the validator.
# All baseline routes are MUSIA surfaces (cognition, constructs, domains,
# musia/governance, musia/tenants, ucja) plus gateway/capability_worker.
# These routes do not flow through GovernanceMiddleware (which filters on
# /api/) and are not covered by GatewayReceiptMiddleware (which filters
# on /webhook/ and /authority/).
#
# Resolution paths (any of):
#   1. Move the routes under /api/ — covers them via GovernanceMiddleware.
#   2. Add a MUSIA-side receipt middleware that mirrors GovernanceMiddleware.
#   3. Add explicit EXCLUSIONS entries in scripts/validate_receipt_coverage.py
#      with per-route justification.
#
# Whatever path is taken, the baseline ratchets DOWN as routes move out
# of UNCOVERED. The number can only fall toward zero through code review.
EXPECTED_UNCOVERED_BASELINE = 23


def test_uncovered_count_matches_baseline():
    """Pinned ratchet: uncovered count must equal the baseline exactly."""
    buckets = compute_buckets()
    actual = len(buckets["UNCOVERED"])
    if actual == EXPECTED_UNCOVERED_BASELINE:
        return

    if actual > EXPECTED_UNCOVERED_BASELINE:
        new_routes = [
            f"{method} {path} ({src})"
            for method, path, src in sorted(buckets["UNCOVERED"])
        ]
        raise AssertionError(
            f"Receipt coverage regressed: {actual} uncovered state-mutating "
            f"routes found, expected baseline {EXPECTED_UNCOVERED_BASELINE}.\n"
            f"\nNew uncovered route(s) must be addressed before merge:\n"
            f"  - Cover via middleware (preferred), OR\n"
            f"  - Add to EXCLUSIONS in scripts/validate_receipt_coverage.py\n"
            f"    with a written justification, OR\n"
            f"  - (Only with reviewer sign-off and PR explanation) bump\n"
            f"    EXPECTED_UNCOVERED_BASELINE in this test upward.\n"
            f"\nFull current uncovered list ({actual} routes):\n"
            + "\n".join(f"  {r}" for r in new_routes)
        )

    # actual < baseline: progress! force ratchet update so it's visible.
    raise AssertionError(
        f"Receipt coverage improved: {actual} uncovered routes, "
        f"baseline pinned at {EXPECTED_UNCOVERED_BASELINE}.\n"
        f"\nRatchet the baseline DOWN by editing this file:\n"
        f"    EXPECTED_UNCOVERED_BASELINE = {actual}\n"
        f"\nThis is the intended way to record coverage progress."
    )


def test_baseline_is_finite_and_non_negative():
    """Sanity guard against a typo turning the ratchet off."""
    assert isinstance(EXPECTED_UNCOVERED_BASELINE, int)
    assert EXPECTED_UNCOVERED_BASELINE >= 0


def test_covered_buckets_have_routes():
    """Sanity: the validator finds routes via both middleware paths.
    Catches a regression where the regex stops matching, which would
    silently drop the uncovered count to zero."""
    buckets = compute_buckets()
    assert len(buckets["MIDDLEWARE_API"]) > 0, (
        "No /api/ routes found — likely regex break in validator. "
        "If this fails, scripts/validate_receipt_coverage.py is no longer "
        "extracting routes correctly and the ratchet is meaningless."
    )
    assert len(buckets["MIDDLEWARE_GATEWAY"]) > 0, (
        "No gateway /webhook/ or /authority/ routes found — likely regex "
        "break in validator."
    )
