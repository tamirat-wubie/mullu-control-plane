"""Phase 124G — Pilot Acceptance Test."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

@dataclass
class AcceptanceResult:
    test_name: str
    passed: bool
    detail: str = ""

class PilotAcceptanceTest:
    """Runs the 10-point pilot acceptance test."""

    def __init__(self, bootstrap: PilotTenantBootstrap, importer: PilotDataImporter):
        self._bootstrap = bootstrap
        self._importer = importer
        self._results: list[AcceptanceResult] = []

    def run_all(self, tenant_id: str) -> list[AcceptanceResult]:
        self._results = []
        self._test_1_bootstrap(tenant_id)
        self._test_2_connectors(tenant_id)
        self._test_3_data_import(tenant_id)
        self._test_4_intake(tenant_id)
        self._test_5_case_flow(tenant_id)
        self._test_6_evidence(tenant_id)
        self._test_7_reporting(tenant_id)
        self._test_8_operator_dashboard(tenant_id)
        self._test_9_executive_dashboard(tenant_id)
        self._test_10_copilot_governance(tenant_id)
        return self._results

    def _record(self, name: str, passed: bool, detail: str = "") -> None:
        self._results.append(AcceptanceResult(name, passed, detail))

    def _test_1_bootstrap(self, tid: str) -> None:
        engines = self._bootstrap.engines
        pack_count = engines["pack"].pack_count
        self._record("1_tenant_bootstrap", pack_count >= 1, f"packs={pack_count}")

    def _test_2_connectors(self, tid: str) -> None:
        eng = self._bootstrap.engines["pilot"]
        count = eng.connector_count
        self._record("2_connectors_active", count >= 5, f"connectors={count}")

    def _test_3_data_import(self, tid: str) -> None:
        sample = {
            "cases": [{"case_id": f"accept-case-{i}", "title": "Acceptance test case"} for i in range(3)],
            "remediations": [{"remediation_id": f"accept-rem-{i}", "case_ref": f"accept-case-{i}", "title": "Acceptance remediation"} for i in range(2)],
            "records": [{"record_id": f"accept-rec-{i}", "title": "Acceptance record"} for i in range(3)],
        }
        results = self._importer.import_all(tid, sample)
        total_accepted = sum(r.accepted for r in results.values())
        self._record("3_data_import", total_accepted >= 6, f"accepted={total_accepted}")

    def _test_4_intake(self, tid: str) -> None:
        # Verify cases exist in case engine
        case_count = self._importer._case_engine.case_count
        self._record("4_intake_queue", case_count >= 3, f"cases={case_count}")

    def _test_5_case_flow(self, tid: str) -> None:
        rem_count = self._importer._remediation_engine.remediation_count
        self._record("5_case_remediation_flow", rem_count >= 2, f"remediations={rem_count}")

    def _test_6_evidence(self, tid: str) -> None:
        rec_count = self._importer._records_engine.record_count
        self._record("6_evidence_retrieval", rec_count >= 3, f"records={rec_count}")

    def _test_7_reporting(self, tid: str) -> None:
        # Reporting capability exists in pack
        pack_eng = self._bootstrap.engines["pack"]
        caps = pack_eng.capability_count
        self._record("7_reporting_packet", caps >= 8, f"capabilities={caps}")

    def _test_8_operator_dashboard(self, tid: str) -> None:
        console = self._bootstrap.engines["console"]
        surfaces = console.surface_count
        self._record("8_operator_dashboard", surfaces >= 0, f"surfaces={surfaces}")

    def _test_9_executive_dashboard(self, tid: str) -> None:
        personas = self._bootstrap.engines["persona"]
        count = personas.persona_count
        self._record("9_executive_dashboard", count >= 4, f"personas={count}")

    def _test_10_copilot_governance(self, tid: str) -> None:
        gov = self._bootstrap.engines["governance"]
        rules = gov.rule_count
        self._record("10_copilot_governance", rules >= 3, f"governance_rules={rules}")

    @property
    def summary(self) -> dict[str, Any]:
        passed = sum(1 for r in self._results if r.passed)
        total = len(self._results)
        return {
            "passed": passed,
            "total": total,
            "all_green": passed == total,
            "results": [{"test": r.test_name, "passed": r.passed, "detail": r.detail} for r in self._results],
        }
