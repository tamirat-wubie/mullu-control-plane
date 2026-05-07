"""Phase 129A — Deployment Factory for repeatable customer deployments."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile
from mcoi_runtime.pilot.live_deployment import LivePilotDeployment, DeploymentReport

@dataclass(frozen=True)
class DeploymentTemplate:
    template_id: str
    name: str
    pack_domain: str
    connector_recipes: tuple[str, ...] = ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")
    persona_presets: tuple[str, ...] = ("operator", "executive", "investigator", "compliance")
    governance_presets: tuple[str, ...] = ("no_unauthorized_access", "require_evidence_for_closure", "restrict_external_execution")
    workspace_count: int = 1

REGULATED_OPS_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-regulated-ops-v1",
    name="Regulated Operations Control Tower",
    pack_domain="regulated_ops",
)

@dataclass
class FactoryDeployment:
    customer_id: str
    template_id: str
    report: DeploymentReport | None = None
    verification_passed: bool = False
    deployment_time_minutes: float = 0.0

class DeploymentFactory:
    """Repeatable deployment factory — deploy customers from templates."""

    def __init__(self):
        self._templates: dict[str, DeploymentTemplate] = {"tmpl-regulated-ops-v1": REGULATED_OPS_TEMPLATE}
        self._deployments: list[FactoryDeployment] = []

    def register_template(self, template: DeploymentTemplate) -> None:
        self._templates[template.template_id] = template

    def deploy_customer(self, profile: PilotCustomerProfile, template_id: str = "tmpl-regulated-ops-v1") -> FactoryDeployment:
        if template_id not in self._templates:
            raise ValueError("unknown template")
        deployment = LivePilotDeployment()
        report = deployment.deploy(profile)
        fd = FactoryDeployment(
            customer_id=profile.customer_id,
            template_id=template_id,
            report=report,
            verification_passed=report.is_ready,
        )
        self._deployments.append(fd)
        return fd

    @property
    def deployment_count(self) -> int:
        return len(self._deployments)

    @property
    def success_rate(self) -> float:
        if not self._deployments:
            return 1.0
        passed = sum(1 for d in self._deployments if d.verification_passed)
        return passed / len(self._deployments)

    def summary(self) -> dict[str, Any]:
        return {
            "templates": len(self._templates),
            "deployments": self.deployment_count,
            "success_rate": round(self.success_rate, 3),
            "customers": [d.customer_id for d in self._deployments],
        }
