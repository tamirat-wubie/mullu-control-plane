"""Phase 125B — Demo Tenant Generator. One command to create a convincing demo."""
from __future__ import annotations
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

class DemoTenantGenerator:
    """Creates a fully seeded demo tenant for sales/evaluation."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = PilotTenantBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "demo-tenant-001") -> dict[str, Any]:
        """Generate complete demo tenant with seeded data."""
        result: dict[str, Any] = {"tenant_id": tenant_id, "sections": []}

        # 1. Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result
        result["sections"].append("bootstrap")

        # 2. Seed cases (mix of statuses)
        demo_cases = [
            {"case_id": f"demo-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Annual compliance review - Q4 findings", "high"),
                ("Customer data access audit", "medium"),
                ("Vendor security assessment overdue", "high"),
                ("Policy update required - new regulation", "critical"),
                ("Internal control gap - AP process", "medium"),
                ("Third-party risk assessment pending", "high"),
                ("Incident response drill results", "low"),
                ("Board reporting package preparation", "medium"),
                ("Regulatory examination follow-up", "critical"),
                ("Employee training compliance check", "low"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, demo_cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}
        result["sections"].append("cases")

        # 3. Seed remediations
        demo_remediations = [
            {"remediation_id": f"demo-rem-{i:03d}", "case_ref": f"demo-case-{i:03d}", "title": f"Remediate: {demo_cases[i]['title']}"}
            for i in range(5)
        ]
        rem_result = self._importer.import_remediations(tenant_id, demo_remediations)
        result["remediations"] = {"imported": rem_result.accepted, "total": rem_result.total_records}
        result["sections"].append("remediations")

        # 4. Seed evidence records
        demo_records = [
            {"record_id": f"demo-rec-{i:03d}", "title": title, "record_type": rtype}
            for i, (title, rtype) in enumerate([
                ("Q4 Compliance Report", "report"),
                ("Access Log Extract - November", "evidence"),
                ("Vendor SOC2 Certificate", "certificate"),
                ("Policy Document v3.2", "policy"),
                ("Control Test Results", "test_result"),
                ("Board Minutes - December", "minutes"),
                ("Incident Report IR-2024-047", "incident_report"),
                ("Training Completion Matrix", "matrix"),
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, demo_records)
        result["records"] = {"imported": rec_result.accepted, "total": rec_result.total_records}
        result["sections"].append("records")

        result["status"] = "demo_ready"
        result["total_seeded_items"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> PilotTenantBootstrap:
        return self._bootstrap

    @property
    def importer(self) -> PilotDataImporter:
        return self._importer
