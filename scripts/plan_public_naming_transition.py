"""Plan the remaining transition steps for Mullu Govern public naming launch.

Purpose: derive the evidence still required before the naming witness may move
to `cleared_for_public_launch`.
Governance scope: open gates, official searches, domain candidates, legal review,
and forbidden launch-state mutation.
Dependencies: docs/public-naming-readiness.json and docs/mullu-name-clearance-draft.json.
Invariants: this script is read-only and must not mutate launch evidence.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
READINESS_PATH = REPO_ROOT / "docs" / "public-naming-readiness.json"
CLEARANCE_PATH = REPO_ROOT / "docs" / "mullu-name-clearance-draft.json"


GATE_ACTIONS = {
    "uspto_search": "Run USPTO exact/similar searches and attach evidence.",
    "wipo_search": "Run WIPO Global Brand Database searches and attach evidence.",
    "euipo_tmview_search": "Run EUIPO eSearch plus and TMview searches and attach evidence.",
    "close_variant_review": "Complete legal confusion analysis for close-variant MULU records.",
    "domain_ownership": "Acquire or verify the product domain/subdomain and record DNS ownership.",
    "legal_review": "Record legal/trademark reviewer decision in the clearance packet.",
    "homepage_update": "Apply approved launch copy only after clearance closes or keep foundation-stage proof-boundary copy with no access invitation.",
    "website_deployment_verification": "Verify mullusi.com and product routes are live and not site-not-found.",
    "app_title_update": "Update product-facing app title to Mullu Govern after launch authorization.",
    "sdk_api_stability_review": "Confirm technical contracts keep Mullu Platform where required.",
}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _print_gate_requirement(gate: str, requirements: dict[str, object]) -> None:
    requirement = requirements.get(gate)
    if not isinstance(requirement, dict):
        print("    evidence: missing structured closure requirement")
        return

    print(f"    authority: {requirement['closure_authority']}")
    print(f"    blocker: {requirement['closure_blocker']}")
    print("    evidence:")
    for evidence in requirement["required_evidence"]:
        print(f"      * {evidence}")


def main() -> int:
    readiness = _read_json(READINESS_PATH)
    clearance = _read_json(CLEARANCE_PATH)

    open_gates = list(readiness["open_gates"])
    official_searches = list(clearance["official_searches"])
    domain_candidates = list(clearance["domain_candidates"])
    gate_closure_requirements = dict(clearance.get("gate_closure_requirements", {}))

    print("Mullu Govern Public Naming Transition Plan")
    print("==========================================")
    print(f"Product: {readiness['product_name']}")
    print(f"Suite/family: {readiness['suite_family']}")
    print(f"Current state: {readiness['status']}")
    print(f"Launch allowed: {readiness['public_paid_launch_allowed']}")
    print(f"Final decision: {clearance['final_decision']}")
    print(f"Closed gate count: {len(readiness['closed_gates'])}")
    print(f"Open gate count: {len(readiness['open_gates'])}")
    print(f"Evidence artifact count: {len(readiness['evidence_docs'])}")
    print()

    print("Required gate closures:")
    for gate in open_gates:
        print(f"  - {gate}: {GATE_ACTIONS.get(gate, 'Record closure evidence.')}")
        if isinstance(gate, str):
            _print_gate_requirement(gate, gate_closure_requirements)
    print()

    print("Official search evidence still required:")
    for search in official_searches:
        if search["status"] != "complete":
            print(f"  - {search['source']}: {search['status']} -> {search['url']}")
    print()

    print("Domain evidence still required:")
    for domain in domain_candidates:
        if domain["status"] not in {"owned", "verified", "site_route_verified", "not_selected"}:
            print(f"  - {domain['domain']}: {domain['status']} ({domain['role']})")
    print()

    print("Forbidden until complete:")
    print("  - Set public_paid_launch_allowed to true")
    print("  - Set status to cleared_for_public_launch")
    print("  - Publish paid public product copy")
    print("  - Route paid product traffic to a domain without ownership evidence")
    print()
    print("STATUS: transition_blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
