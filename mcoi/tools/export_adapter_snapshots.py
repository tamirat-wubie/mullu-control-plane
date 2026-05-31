"""
Purpose: export deterministic golden output snapshots for domain adapters.
Governance scope: adapter output drift detection and review evidence.
Dependencies: domain adapter registry, dataclasses, and json.
Invariants: audit UUIDs are excluded and adapter output order is preserved.

The cross-adapter invariants check *structure* (every adapter emits a
non-empty authority tuple, valid permeability, canonical
violation_responses). The constraint matrix checks the *constraint
vocabulary* each adapter emits. Neither pins the *exact output
values* - so a changed purpose verb, a reordered observer, a flipped
violation_response on one constraint, or a different protocol step
would pass all existing tests silently.

This tool captures a deterministic snapshot of each adapter's full
output for its canonical minimal request: the UniversalRequest from
``translate_to_universal`` plus the governance-relevant fields of the
``run_with_ucja`` result. The non-deterministic ``audit_trail_id``
(a fresh UUID per run) is excluded.

The companion test ``tests/test_domain_adapter_golden.py`` compares
live output to the committed golden and fails on any drift, forcing
a deliberate regeneration when adapter behavior changes.

Run::

    python -m mcoi.tools.export_adapter_snapshots          # writes golden
    python -m mcoi.tools.export_adapter_snapshots --print  # to stdout
    python -m mcoi.tools.export_adapter_snapshots --check  # CI staleness
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mcoi_runtime.domain_adapters._registry import ADAPTERS, AdapterEntry


# Result-dataclass field names that hold the ordered protocol / plan.
# Each adapter uses a domain-specific name (e.g. care_protocol,
# settlement_protocol, response_protocol); we harvest whichever is
# present rather than coupling this tool to all 15 result classes.
_PROTOCOL_FIELD_NAMES: tuple[str, ...] = (
    "work_plan",
    "workflow_steps",
    "research_protocol",
    "production_protocol",
    "care_protocol",
    "instructional_protocol",
    "settlement_protocol",
    "case_protocol",
    "civic_protocol",
    "fulfillment_protocol",
    "operating_protocol",
    "response_protocol",
    "handling_protocol",
    "stewardship_protocol",
    "project_protocol",
)


def _harvest_protocol(result: Any) -> list[str]:
    for name in _PROTOCOL_FIELD_NAMES:
        steps = getattr(result, name, None)
        if steps:
            return list(steps)
    return []


def snapshot_for_adapter(entry: AdapterEntry) -> dict[str, Any]:
    """Build the deterministic snapshot for one adapter. Order is
    preserved as-emitted (authority order, observer order, protocol
    order are all governance-meaningful and worth pinning)."""
    request = entry.build()

    uni = entry.translate_to_universal(request)
    translate_snapshot = {
        "purpose_statement": uni.purpose_statement,
        "authority_required": list(uni.authority_required),
        "observer_required": list(uni.observer_required),
        "constraint_set": [
            {
                "domain": c["domain"],
                "restriction": c["restriction"],
                "violation_response": c.get("violation_response", "block"),
            }
            for c in uni.constraint_set
        ],
        "boundary": {
            "inside_predicate": uni.boundary_specification.get(
                "inside_predicate", ""
            ),
            "permeability": uni.boundary_specification.get(
                "permeability", "selective"
            ),
        },
    }

    result = entry.run_with_ucja(request)
    run_snapshot = {
        # audit_trail_id deliberately excluded (random UUID per run)
        "governance_status": result.governance_status,
        "protocol": _harvest_protocol(result),
        "risk_flags": list(result.risk_flags),
    }

    return {"translate": translate_snapshot, "run": run_snapshot}


def generate_snapshots() -> dict[str, Any]:
    """Full golden document: meta header + per-adapter snapshots,
    keyed by adapter name in registry order."""
    return {
        "_meta": {
            "adapter_count": len(ADAPTERS),
            "note": (
                "Golden output snapshots. Regenerate with "
                "`python -m mcoi.tools.export_adapter_snapshots` when "
                "an adapter's behavior changes deliberately. "
                "audit_trail_id is excluded (non-deterministic UUID)."
            ),
        },
        "adapters": {
            entry.name: snapshot_for_adapter(entry) for entry in ADAPTERS
        },
    }


def render() -> str:
    return json.dumps(generate_snapshots(), indent=2, ensure_ascii=False) + "\n"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def artifact_path() -> Path:
    return repo_root() / "mcoi" / "tests" / "golden" / "domain_adapter_snapshots.json"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="Export golden output snapshots for every adapter.",
    )
    parser.add_argument("--print", action="store_true",
                        help="Write to stdout instead of disk.")
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if the golden file is stale.")
    args = parser.parse_args(argv)

    doc = render()

    if args.print:
        sys.stdout.write(doc)
        return 0

    target = artifact_path()
    if args.check:
        if not target.exists():
            sys.stderr.write(
                f"golden snapshot file missing at {target}; "
                "run without --check to generate.\n"
            )
            return 1
        if target.read_text(encoding="utf-8") != doc:
            sys.stderr.write(
                "domain_adapter_snapshots.json is stale. If the change is "
                "intentional, regenerate with "
                "`python -m mcoi.tools.export_adapter_snapshots`.\n"
            )
            return 1
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")
    sys.stdout.write(f"wrote {target}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
