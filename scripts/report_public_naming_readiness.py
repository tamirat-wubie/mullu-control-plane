"""Report the Mullu public naming readiness state.

Purpose: print a concise operator-readable summary of the public naming gate.
Governance scope: product naming, launch allowance, open clearance gates,
domain candidates, and official search status.
Dependencies: docs/public-naming-readiness.json and docs/mullu-name-clearance-draft.json.
Invariants: this report never changes launch state; it only reads witnesses.
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
READINESS_PATH = REPO_ROOT / "docs" / "public-naming-readiness.json"
CLEARANCE_PATH = REPO_ROOT / "docs" / "mullu-name-clearance-draft.json"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _print_list(title: str, values: list[object]) -> None:
    print(title)
    for value in values:
        print(f"  - {value}")


def main() -> int:
    readiness = _read_json(READINESS_PATH)
    clearance = _read_json(CLEARANCE_PATH)

    print("Mullu Public Naming Readiness")
    print("=============================")
    print(f"Product: {readiness['product_name']}")
    print(f"Company: {readiness['company_brand']}")
    print(f"First reference: {readiness['first_reference']}")
    print(f"Status: {readiness['status']}")
    print(f"Paid public launch allowed: {readiness['public_paid_launch_allowed']}")
    print(f"Final clearance decision: {clearance['final_decision']}")
    print(f"Closed gate count: {len(readiness['closed_gates'])}")
    print(f"Open gate count: {len(readiness['open_gates'])}")
    print(f"Evidence artifact count: {len(readiness['evidence_docs'])}")
    print()

    _print_list("Open gates:", list(readiness["open_gates"]))
    print()

    print("Official searches:")
    for search in clearance["official_searches"]:
        print(f"  - {search['source']}: {search['status']} ({search['url']})")
    print()

    print("Domain candidates:")
    for domain in clearance["domain_candidates"]:
        print(
            "  - "
            f"{domain['domain']} [{domain['priority']}]: "
            f"{domain['role']} -- {domain['status']}"
        )
    print()

    _print_list("Required next actions:", list(clearance["required_next_actions"]))
    print()
    print("STATUS: blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
