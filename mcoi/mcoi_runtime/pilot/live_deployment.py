"""Phase 126B+C — Live Tenant Deployment and Data Loading."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter, ImportResult
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile


def _bounded_deployment_error(summary: str, exc: Exception) -> str:
    return f"{summary} ({type(exc).__name__})"

@dataclass
class DeploymentReport:
    tenant_id: str
    bootstrap_status: str = "not_started"
    connectors_activated: int = 0
    personas_created: int = 0
    governance_rules: int = 0
    import_results: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        return (self.bootstrap_status == "ready" and
                self.connectors_activated >= 5 and
                self.personas_created >= 4 and
                self.governance_rules >= 3 and
                not self.issues)

class LivePilotDeployment:
    """Manages the deployment of a real pilot for a real customer."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = PilotTenantBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy(self, profile: PilotCustomerProfile) -> DeploymentReport:
        report = DeploymentReport(tenant_id=profile.customer_id)

        # Bootstrap
        try:
            result = self._bootstrap.bootstrap(profile.customer_id)
            report.bootstrap_status = result["status"]
            report.connectors_activated = len(result.get("connectors_activated", []))
            report.personas_created = len(result.get("personas", []))
            report.governance_rules = len(result.get("governance_rules", []))
        except Exception as exc:
            report.bootstrap_status = "failed"
            report.issues.append(_bounded_deployment_error("bootstrap failed", exc))

        return report

    def load_data(self, tenant_id: str, dataset: dict[str, list[dict[str, Any]]]) -> dict[str, ImportResult]:
        return self._importer.import_all(tenant_id, dataset)

    @property
    def bootstrap(self) -> PilotTenantBootstrap:
        return self._bootstrap

    @property
    def importer(self) -> PilotDataImporter:
        return self._importer
