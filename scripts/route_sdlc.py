#!/usr/bin/env python3
"""Route Mullu SDLC requests to governed delivery lanes.

Purpose: deterministically map software delivery request text to SDLC route skills.
Governance scope: OCE route identity, RAG signal-to-skill linkage, CDCV route trace,
CQTE bounded keyword matching, UWMA route receipt, and PRS route closure.
Dependencies: Python standard library.
Invariants:
  - Routing is deterministic and read-only.
  - Short signals match token boundaries, not substrings.
  - Unknown requests route to the router lane instead of silently passing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass


ROUTE_PRIORITY: tuple[str, ...] = (
    "sdlc-requirements-boundary",
    "sdlc-change-impact-audit",
    "sdlc-test-contract-authoring",
    "sdlc-security-review-gate",
    "sdlc-rollback-recovery-plan",
    "sdlc-governance-receipt-auditor",
    "sdlc-pr-readiness-closure",
    "sdlc-ci-failure-triage",
    "sdlc-release-witness-closure",
    "sdlc-documentation-drift-audit",
)

ROUTE_SIGNALS: dict[str, tuple[str, ...]] = {
    "sdlc-requirements-boundary": (
        "requirement",
        "requirements",
        "intent",
        "scope",
        "acceptance criteria",
        "success criteria",
        "feature request",
        "bug report",
    ),
    "sdlc-change-impact-audit": (
        "diff",
        "impact",
        "changed files",
        "invariant",
        "module impact",
        "branch",
        "validator",
        "governance validator",
        "schema impact",
        "contract impact",
    ),
    "sdlc-test-contract-authoring": (
        "test",
        "tests",
        "assertion",
        "assertions",
        "coverage",
        "verification gap",
        "test plan",
        "boundary condition",
    ),
    "sdlc-pr-readiness-closure": (
        "pull request",
        "pr",
        "merge",
        "merge readiness",
        "branch protection",
        "pr template",
        "review",
    ),
    "sdlc-ci-failure-triage": (
        "ci",
        "check failed",
        "failing check",
        "github actions",
        "validator failed",
        "flaky",
        "failure",
    ),
    "sdlc-release-witness-closure": (
        "release",
        "deployment",
        "production claim",
        "witness",
        "public health",
        "runtime conformance",
        "handoff",
    ),
    "sdlc-documentation-drift-audit": (
        "documentation",
        "docs",
        "drift",
        "schema drift",
        "example",
        "examples",
        "validator drift",
        "artifact drift",
    ),
    "sdlc-security-review-gate": (
        "security",
        "secret",
        "secrets",
        "credential",
        "authority",
        "external endpoint",
        "residual risk",
        "threat",
    ),
    "sdlc-rollback-recovery-plan": (
        "rollback",
        "recovery",
        "incident",
        "replay",
        "compensation",
        "restore",
        "accepted risk",
    ),
    "sdlc-governance-receipt-auditor": (
        "receipt",
        "receipts",
        "uao",
        "causal trace",
        "closure",
        "no-bypass",
        "no bypass",
        "governance gate",
        "terminal closure",
    ),
}

DEFAULT_SEQUENCES: dict[str, tuple[str, ...]] = {
    "new_effect_bearing_change": (
        "sdlc-requirements-boundary",
        "sdlc-change-impact-audit",
        "sdlc-test-contract-authoring",
        "sdlc-security-review-gate",
        "sdlc-rollback-recovery-plan",
        "sdlc-governance-receipt-auditor",
        "sdlc-pr-readiness-closure",
    ),
    "failing_pr": (
        "sdlc-ci-failure-triage",
        "sdlc-change-impact-audit",
        "sdlc-test-contract-authoring",
        "sdlc-pr-readiness-closure",
    ),
    "release_or_deployment": (
        "sdlc-release-witness-closure",
        "sdlc-security-review-gate",
        "sdlc-rollback-recovery-plan",
        "sdlc-governance-receipt-auditor",
    ),
    "documentation_or_artifact_drift": (
        "sdlc-documentation-drift-audit",
        "sdlc-change-impact-audit",
        "sdlc-governance-receipt-auditor",
    ),
}


@dataclass(frozen=True, slots=True)
class SkillRoute:
    """One matched route skill and its triggering signals."""

    skill: str
    matched_signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteReceipt:
    """Machine-readable route result."""

    status: str
    request: str
    sequence_name: str | None
    skills: tuple[str, ...]
    routes: tuple[SkillRoute, ...]
    fallback_used: bool


def route_request(request: str) -> RouteReceipt:
    """Route a request string to an ordered SDLC skill sequence."""

    request_text = request.strip()
    matched_routes = _match_routes(request_text)
    sequence_name = _sequence_name(request_text)
    sequenced_skills = list(DEFAULT_SEQUENCES.get(sequence_name or "", ()))
    sequenced_skills.extend(route.skill for route in matched_routes)
    fallback_used = not sequenced_skills
    if fallback_used:
        sequenced_skills.append("sdlc-skill-router")
    return RouteReceipt(
        status="routed",
        request=request_text,
        sequence_name=sequence_name,
        skills=_ordered_unique(sequenced_skills),
        routes=matched_routes,
        fallback_used=fallback_used,
    )


def _match_routes(request: str) -> tuple[SkillRoute, ...]:
    request_lower = request.lower()
    routes: list[SkillRoute] = []
    for skill in ROUTE_PRIORITY:
        signals = tuple(signal for signal in ROUTE_SIGNALS[skill] if _signal_matches(request_lower, signal))
        if signals:
            routes.append(SkillRoute(skill=skill, matched_signals=signals))
    return tuple(routes)


def _sequence_name(request: str) -> str | None:
    request_lower = request.lower()
    if any(_signal_matches(request_lower, signal) for signal in ("ci", "check failed", "failing check", "failed pr")):
        return "failing_pr"
    if any(_signal_matches(request_lower, signal) for signal in ("release", "deployment", "production claim")):
        return "release_or_deployment"
    if any(_signal_matches(request_lower, signal) for signal in ("drift", "documentation", "docs", "artifact drift")):
        return "documentation_or_artifact_drift"
    if any(
        _signal_matches(request_lower, signal)
        for signal in ("new change", "feature", "effect-bearing", "effect bearing", "new validator", "governance validator")
    ):
        return "new_effect_bearing_change"
    return None


def _signal_matches(request_lower: str, signal: str) -> bool:
    signal_lower = signal.lower()
    if signal_lower.replace("-", "").replace(" ", "").isalnum():
        pattern = rf"(?<![a-z0-9]){re.escape(signal_lower)}(?![a-z0-9])"
        return re.search(pattern, request_lower) is not None
    return signal_lower in request_lower


def _ordered_unique(skills: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for skill in skills:
        if skill not in seen:
            ordered.append(skill)
            seen.add(skill)
    return tuple(ordered)


def build_route_payload(receipt: RouteReceipt) -> dict[str, object]:
    """Convert a route receipt to a JSON-ready dictionary."""

    return asdict(receipt)


def main(argv: list[str] | None = None) -> int:
    """Route command-line request text."""

    parser = argparse.ArgumentParser(description="Route a request to governed Mullu SDLC lanes.")
    parser.add_argument("request", nargs="*", help="request text to route")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable route receipt")
    args = parser.parse_args(argv)

    request = " ".join(args.request).strip()
    if not request:
        sys.stderr.write("ERROR: request text is required\n")
        return 2

    receipt = route_request(request)
    if args.json:
        sys.stdout.write(json.dumps(build_route_payload(receipt), indent=2, sort_keys=True) + "\n")
        return 0

    sys.stdout.write(f"STATUS: {receipt.status}\n")
    if receipt.sequence_name:
        sys.stdout.write(f"sequence: {receipt.sequence_name}\n")
    sys.stdout.write("skills:\n")
    for skill in receipt.skills:
        sys.stdout.write(f"- {skill}\n")
    for route in receipt.routes:
        sys.stdout.write(f"matched {route.skill}: {', '.join(route.matched_signals)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
