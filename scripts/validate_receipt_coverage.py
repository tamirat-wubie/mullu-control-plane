#!/usr/bin/env python3
"""Validate receipt coverage: every state-mutating HTTP route must produce
a TransitionReceipt via middleware, or carry a documented exclusion.

This enforces the coverage invariant from docs/MAF_RECEIPT_COVERAGE.md:

    Every state-mutating operation invoked through the platform's HTTP
    surface SHALL produce a TransitionReceipt with verdict matching the
    operation's outcome.

The companion document is the spec; this script is the verifier. The two
together follow the same pattern LEDGER_SPEC.md established for the audit
trail: spec defines the claim, executable code makes it externally
verifiable.

Coverage rules (matching the actual deployed middleware filters):

    MIDDLEWARE_API
        Path starts with "/api/" and is not in mcoi GovernanceMiddleware
        EXEMPT_PATHS. Every request is certified by ProofBridge.

    MIDDLEWARE_GATEWAY
        Path starts with "/webhook/" or "/authority/" — covered by
        gateway/receipt_middleware.py::GatewayReceiptMiddleware.

    MIDDLEWARE_MUSIA
        Path starts with a certified prefix in
        mcoi_runtime.app.musia_receipt_middleware::MusiaReceiptMiddleware.

    DIRECT_RECEIPT
        Path is an operator receipt-emission endpoint that directly returns
        and stores a governed receipt as its state transition artifact.

    EXCLUDED
        Path matches an entry in EXCLUSIONS below, with a written
        justification. Excluded routes are read-only-equivalent or
        admin/diagnostic surfaces that have an alternative audit path.

    UNCOVERED
        Anything else. A route in this bucket is either a real coverage
        gap, or is missing from the EXCLUSIONS list. With --strict, any
        UNCOVERED route fails the run.

Methods checked: POST, PUT, PATCH, DELETE. GET/HEAD/OPTIONS are treated
as read-only by convention and not validated.

CLI:
    python scripts/validate_receipt_coverage.py
        Print the coverage report. Always exits 0.

    python scripts/validate_receipt_coverage.py --strict
        Print the coverage report. Exit 1 if any UNCOVERED route exists.

Importable API:
    compute_buckets() -> dict[str, list[tuple[str, str, str]]]
        Returns {bucket_name: [(method, full_path, source_file), ...]}.
        Used by the pytest ratchet test to assert the uncovered count
        matches a known baseline. New uncovered routes fail the test;
        newly-covered routes also fail until the baseline is ratcheted
        downward — making coverage progress reviewer-visible.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTERS_DIR = REPO_ROOT / "mcoi" / "mcoi_runtime" / "app" / "routers"
GATEWAY_FILES = [
    REPO_ROOT / "gateway" / "server.py",
    REPO_ROOT / "gateway" / "capability_worker.py",
]

# Mirrors mcoi/mcoi_runtime/app/middleware.py::EXEMPT_PATHS.
# These paths under /api/ would still be skipped by GovernanceMiddleware.
# (None of them currently match /api/, so this is defensive.)
MCOI_EXEMPT_PATHS = frozenset({"/health", "/ready", "/docs", "/openapi.json", "/redoc"})

# Mirrors gateway/receipt_middleware.py::CERTIFIED_PREFIXES.
GATEWAY_CERTIFIED_PREFIXES = (
    "/webhook/",
    "/authority/",
    "/capability-fabric/",
    "/capability-plans/",
)

# Mirrors the new software receipt prefix in
# mcoi/mcoi_runtime/app/musia_receipt_middleware.py::_CERTIFIED_PREFIXES.
# The pre-existing MUSIA route debt remains intentionally visible in
# UNCOVERED until a dedicated coverage ratchet slice moves it down.
MUSIA_CERTIFIED_PREFIXES = ("/software/receipts/",)

# Direct receipt emitters: route_path -> justification.
# These routes are state-mutating, but their mutation is the governed
# receipt ledger entry they emit and return to the caller.
DIRECT_RECEIPT_ROUTES: dict[str, str] = {
    "/operator/physical-capability-promotion-receipts": (
        "Operator physical capability promotion emits a "
        "PhysicalCapabilityPromotionReceipt, stores it in the in-memory "
        "operator ledger, and returns both receipt_id and receipt payload."
    ),
}

# Methods considered state-mutating. GET/HEAD/OPTIONS are read-only by
# REST convention and produce no governed transition.
MUTATING_METHODS = frozenset({"post", "put", "patch", "delete"})

# Acknowledged exclusions: route_path -> justification.
# A route here is exempt from receipt emission. Add entries only with a
# clear written reason; reviewers should push back on unjustified entries.
EXCLUSIONS: dict[str, str] = {
    "/runtime/self/certify": (
        "Reflex certification is an operator-gated handoff read model that returns "
        "required certification commands and artifacts; it does not issue a "
        "certificate or mutate runtime state."
    ),
    "/runtime/self/diagnose": (
        "Reflex diagnosis is an operator-gated projection over runtime health "
        "evidence; responses carry no mutation and no production promotion."
    ),
    "/runtime/self/evaluate": (
        "Reflex evaluation generates deterministic eval-case projections from "
        "diagnoses; it records no runtime transition and applies no change."
    ),
    "/runtime/self/promote": (
        "Reflex promotion returns a decision projection and explicitly reports "
        "mutation_applied=false; protected surfaces still require human approval."
    ),
    "/runtime/self/propose-upgrade": (
        "Reflex upgrade proposal emits candidate records only; candidates cannot "
        "mutate runtime state without later sandbox, certificate, and approval gates."
    ),
}

# Same patterns proof_coverage_matrix.py uses, kept in sync deliberately.
ROUTE_PATTERN = re.compile(
    r"@(?:router|app)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']"
)
ROUTER_PREFIX_PATTERN = re.compile(
    r"APIRouter\([^)]*prefix\s*=\s*[\"']([^\"']+)[\"']"
)


def collect_source_files() -> list[Path]:
    """Source files to scan for route declarations."""
    files: list[Path] = []
    if ROUTERS_DIR.exists():
        files.extend(sorted(ROUTERS_DIR.glob("*.py")))
    for gw in GATEWAY_FILES:
        if gw.exists():
            files.append(gw)
    return [f for f in files if f.name != "__init__.py"]


def extract_routes(path: Path) -> list[tuple[str, str]]:
    """Return [(method, full_path)] declared in this source file.

    Composes APIRouter(prefix=...) with each @router.<method>("/x") route.
    """
    text = path.read_text(encoding="utf-8")
    prefix_match = ROUTER_PREFIX_PATTERN.search(text)
    prefix = prefix_match.group(1) if prefix_match else ""
    routes: list[tuple[str, str]] = []
    for method, route in ROUTE_PATTERN.findall(text):
        full_path = (prefix + route) if route.startswith("/") else (prefix + "/" + route)
        routes.append((method.lower(), full_path))
    return routes


def classify(method: str, full_path: str) -> str:
    """Return one of the middleware/exclusion/coverage buckets."""
    if full_path in EXCLUSIONS:
        return "EXCLUDED"
    if full_path in DIRECT_RECEIPT_ROUTES:
        return "DIRECT_RECEIPT"
    if full_path.startswith("/api/") and full_path not in MCOI_EXEMPT_PATHS:
        return "MIDDLEWARE_API"
    if any(full_path.startswith(p) for p in GATEWAY_CERTIFIED_PREFIXES):
        return "MIDDLEWARE_GATEWAY"
    if any(full_path.startswith(p) for p in MUSIA_CERTIFIED_PREFIXES):
        return "MIDDLEWARE_MUSIA"
    return "UNCOVERED"


def compute_buckets() -> dict[str, list[tuple[str, str, str]]]:
    """Walk the source tree and classify every state-mutating route.

    Returns {bucket_name: [(METHOD, full_path, source_file), ...]} with
    keys MIDDLEWARE_API, MIDDLEWARE_GATEWAY, MIDDLEWARE_MUSIA,
    EXCLUDED, UNCOVERED. Read-
    only routes (GET/HEAD/OPTIONS) are filtered out.

    This is the import surface used by the pytest ratchet test.
    """
    buckets: dict[str, list[tuple[str, str, str]]] = {
        "MIDDLEWARE_API": [],
        "MIDDLEWARE_GATEWAY": [],
        "MIDDLEWARE_MUSIA": [],
        "DIRECT_RECEIPT": [],
        "EXCLUDED": [],
        "UNCOVERED": [],
    }
    for src in collect_source_files():
        for method, full_path in extract_routes(src):
            if method not in MUTATING_METHODS:
                continue
            bucket = classify(method, full_path)
            buckets[bucket].append((method.upper(), full_path, src.name))
    return buckets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any UNCOVERED route exists. "
             "Default mode is informational and always exits 0.",
    )
    args = parser.parse_args(argv)

    buckets = compute_buckets()
    total_mutating = sum(len(v) for v in buckets.values())

    print(f"Scanned {len(collect_source_files())} source files.")
    print(f"State-mutating routes (POST/PUT/PATCH/DELETE): {total_mutating}\n")

    for name in (
        "MIDDLEWARE_API",
        "MIDDLEWARE_GATEWAY",
        "MIDDLEWARE_MUSIA",
        "DIRECT_RECEIPT",
        "EXCLUDED",
        "UNCOVERED",
    ):
        items = buckets[name]
        print(f"--- {name} ({len(items)}) ---")
        for method, path, src in sorted(items):
            print(f"  {method:6s} {path}  ({src})")
        print()

    uncovered = buckets["UNCOVERED"]
    if uncovered:
        print(
            f"{len(uncovered)} state-mutating route(s) are uncovered "
            "and not in EXCLUSIONS."
        )
        print(
            "Each uncovered route must either: route through a receipt-"
            "emitting middleware, OR be added to EXCLUSIONS in this file "
            "with a written justification."
        )
        if args.strict:
            return 1
        return 0

    print(
        f"OK: all {total_mutating} state-mutating routes are covered "
        f"({len(buckets['MIDDLEWARE_API'])} via /api/, "
        f"{len(buckets['MIDDLEWARE_GATEWAY'])} via gateway, "
        f"{len(buckets['MIDDLEWARE_MUSIA'])} via musia receipt middleware, "
        f"{len(buckets['DIRECT_RECEIPT'])} direct receipt emitter(s), "
        f"{len(buckets['EXCLUDED'])} excluded)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
