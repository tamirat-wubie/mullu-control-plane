#!/usr/bin/env python3
"""Validate finance approval packet pilot readiness.

Purpose: report whether the finance approval packet pilot is proof-ready and
whether live document/email adapter evidence is closed.
Governance scope: finance packet routes, proof schema, runbook, document parser
evidence, email/calendar connector evidence, and explicit production blockers.
Dependencies: capability adapter evidence, proof coverage matrix, protocol
manifest, and finance pilot artifacts.
Invariants:
  - Proof pilot readiness requires local contracts, routes, schema, and docs.
  - Live handoff readiness requires closed document and email/calendar evidence.
  - Missing evidence is reported as a blocker, never converted to success.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADAPTER_EVIDENCE = REPO_ROOT / ".change_assurance" / "capability_adapter_evidence.json"
PROOF_COVERAGE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"
PROTOCOL_MANIFEST = REPO_ROOT / "schemas" / "mullu_governance_protocol.manifest.json"
RUNBOOK = REPO_ROOT / "docs" / "63_finance_approval_packet_pilot.md"
PROOF_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_packet_proof.schema.json"


@dataclass(frozen=True, slots=True)
class FinancePilotReadiness:
    """Machine-readable finance pilot readiness report."""

    ready: bool
    readiness_level: str
    blockers: tuple[str, ...]
    checks: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "readiness_level": self.readiness_level,
            "blockers": list(self.blockers),
            "checks": [dict(check) for check in self.checks],
        }


def validate_finance_approval_pilot(
    *,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
) -> FinancePilotReadiness:
    """Return finance approval pilot readiness without mutating evidence."""
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add_check(name: str, passed: bool, detail: str, evidence_refs: list[str]) -> None:
        checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": detail,
                "evidence_refs": evidence_refs,
            }
        )
        if not passed:
            blockers.append(name)

    proof_schema_present = PROOF_SCHEMA.exists()
    add_check(
        "finance proof schema present",
        proof_schema_present,
        "finance approval packet proof schema exists" if proof_schema_present else "schema missing",
        [str(PROOF_SCHEMA)],
    )

    runbook_present = RUNBOOK.exists()
    add_check(
        "finance pilot runbook present",
        runbook_present,
        "finance approval packet pilot runbook exists" if runbook_present else "runbook missing",
        [str(RUNBOOK)],
    )

    manifest_ok = _manifest_indexes_finance_schema()
    add_check(
        "finance proof schema indexed",
        manifest_ok,
        "protocol manifest indexes finance-approval-packet-proof"
        if manifest_ok
        else "protocol manifest missing finance-approval-packet-proof",
        [str(PROTOCOL_MANIFEST)],
    )

    route_ok = _proof_coverage_classifies_finance_routes()
    add_check(
        "finance routes classified",
        route_ok,
        "proof coverage classifies finance approval packet routes"
        if route_ok
        else "proof coverage missing finance approval packet route classification",
        [str(PROOF_COVERAGE_FIXTURE)],
    )

    adapter_evidence = _load_json(adapter_evidence_path)
    document_adapter = _adapter(adapter_evidence, "document.production_parsers")
    document_closed = document_adapter.get("status") == "closed" and not document_adapter.get("blockers")
    add_check(
        "document parser evidence closed",
        document_closed,
        "document parser adapter evidence is closed"
        if document_closed
        else f"document parser blockers: {document_adapter.get('blockers', [])}",
        [str(adapter_evidence_path), *[str(ref) for ref in document_adapter.get("evidence_refs", [])]],
    )

    email_adapter = _adapter(adapter_evidence, "communication.email_calendar_worker")
    email_blockers = tuple(str(item) for item in email_adapter.get("blockers", ()))
    email_closed = email_adapter.get("status") == "closed" and not email_blockers
    add_check(
        "email calendar evidence closed",
        email_closed,
        "email/calendar adapter evidence is closed"
        if email_closed
        else f"email/calendar blockers: {list(email_blockers)}",
        [str(adapter_evidence_path), *[str(ref) for ref in email_adapter.get("evidence_refs", [])]],
    )

    proof_ready = all(
        check["passed"]
        for check in checks
        if check["name"]
        in {
            "finance proof schema present",
            "finance pilot runbook present",
            "finance proof schema indexed",
            "finance routes classified",
            "document parser evidence closed",
        }
    )
    live_ready = proof_ready and email_closed
    readiness_level = "live-email-handoff-ready" if live_ready else "proof-pilot-ready" if proof_ready else "not-ready"
    return FinancePilotReadiness(
        ready=live_ready,
        readiness_level=readiness_level,
        blockers=tuple(blockers),
        checks=tuple(checks),
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _adapter(report: dict[str, Any], adapter_id: str) -> dict[str, Any]:
    for adapter in report.get("adapters", []):
        if isinstance(adapter, dict) and adapter.get("adapter_id") == adapter_id:
            return adapter
    return {"adapter_id": adapter_id, "status": "missing", "blockers": ["adapter_evidence_missing"]}


def _manifest_indexes_finance_schema() -> bool:
    manifest = _load_json(PROTOCOL_MANIFEST)
    return any(
        entry.get("schema_id") == "finance-approval-packet-proof"
        and entry.get("path") == "schemas/finance_approval_packet_proof.schema.json"
        for entry in manifest.get("schemas", [])
        if isinstance(entry, dict)
    )


def _proof_coverage_classifies_finance_routes() -> bool:
    matrix = _load_json(PROOF_COVERAGE_FIXTURE)
    routes = matrix.get("route_coverage", {}).get("routes", [])
    required = {
        "/api/v1/finance/approval-packets",
        "/api/v1/finance/approval-packets/operator/read-model",
        "/api/v1/finance/approval-packets/{case_id}",
        "/api/v1/finance/approval-packets/{case_id}/approval",
        "/api/v1/finance/approval-packets/{case_id}/proof",
    }
    classified = {
        route.get("route")
        for route in routes
        if isinstance(route, dict)
        and route.get("surface_id") == "finance_approval_packets"
        and route.get("coverage_state") == "witnessed"
    }
    return required <= classified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--output", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = validate_finance_approval_pilot(adapter_evidence_path=Path(args.adapter_evidence))
    payload = report.as_dict()
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"finance approval pilot readiness: {report.readiness_level}")
        if report.blockers:
            print(f"blockers: {', '.join(report.blockers)}")
    return 0 if report.readiness_level != "not-ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
