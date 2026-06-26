"""Phase 126B+C — Live Tenant Deployment and Data Loading."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter, ImportResult
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile


def _bounded_deployment_error(summary: str, exc: Exception) -> str:
    return f"{summary} ({type(exc).__name__})"


def _life_meaning_judgment_ref(scope: str, identifier: str) -> str:
    bounded_identifier = identifier.strip()
    if not bounded_identifier:
        raise RuntimeCoreInvariantError("life_meaning_judgment_ref requires a non-empty identifier")
    return f"life-meaning:pilot-{scope}:{bounded_identifier}"


def _normalize_life_meaning_judgment_ref(candidate: str | None, *, scope: str, identifier: str) -> str:
    if candidate is None:
        return _life_meaning_judgment_ref(scope, identifier)
    normalized = candidate.strip()
    if not normalized:
        raise RuntimeCoreInvariantError("life_meaning_judgment_ref must not be blank")
    return normalized


@dataclass
class DeploymentReport:
    tenant_id: str
    bootstrap_status: str = "not_started"
    connectors_activated: int = 0
    personas_created: int = 0
    governance_rules: int = 0
    life_meaning_judgment_required: bool = True
    life_meaning_judgment_ref: str = ""
    import_results: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.life_meaning_judgment_required is not True:
            raise RuntimeCoreInvariantError("life_meaning_judgment_required must be true")
        self.life_meaning_judgment_ref = _normalize_life_meaning_judgment_ref(
            self.life_meaning_judgment_ref or None,
            scope="deployment",
            identifier=self.tenant_id,
        )

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

    def deploy(
        self,
        profile: PilotCustomerProfile,
        *,
        life_meaning_judgment_ref: str | None = None,
    ) -> DeploymentReport:
        judgment_ref = _normalize_life_meaning_judgment_ref(
            life_meaning_judgment_ref,
            scope="deployment",
            identifier=profile.customer_id,
        )
        report = DeploymentReport(
            tenant_id=profile.customer_id,
            life_meaning_judgment_ref=judgment_ref,
        )

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

    def load_data(
        self,
        tenant_id: str,
        dataset: dict[str, list[dict[str, Any]]],
        *,
        life_meaning_judgment_ref: str | None = None,
    ) -> dict[str, ImportResult]:
        judgment_ref = _normalize_life_meaning_judgment_ref(
            life_meaning_judgment_ref,
            scope="data-load",
            identifier=tenant_id,
        )
        return self._importer.import_all(
            tenant_id,
            dataset,
            life_meaning_judgment_ref=judgment_ref,
        )

    @property
    def bootstrap(self) -> PilotTenantBootstrap:
        return self._bootstrap

    @property
    def importer(self) -> PilotDataImporter:
        return self._importer
