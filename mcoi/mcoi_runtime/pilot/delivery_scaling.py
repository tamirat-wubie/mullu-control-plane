"""Phase 133E+F — Delivery Scaling and Pack-Specific Pricing."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from mcoi_runtime.pilot.deployment_factory import DeploymentTemplate, REGULATED_OPS_TEMPLATE
from mcoi_runtime.pilot.enterprise_service_pack import ENTERPRISE_SERVICE_TEMPLATE
from mcoi_runtime.pilot.financial_control_pack import FINANCIAL_CONTROL_TEMPLATE
from mcoi_runtime.pilot.factory_quality_pack import FACTORY_QUALITY_TEMPLATE

# All deployment profiles (133E)
DEPLOYMENT_PROFILES = {
    "regulated_ops": REGULATED_OPS_TEMPLATE,
    "enterprise_service": ENTERPRISE_SERVICE_TEMPLATE,
    "financial_control": FINANCIAL_CONTROL_TEMPLATE,
    "factory_quality": FACTORY_QUALITY_TEMPLATE,
}

CONNECTOR_BUNDLES = {
    "regulated_ops": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
    "enterprise_service": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
    "financial_control": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
    "factory_quality": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
}

SUPPORT_RUNBOOKS = {
    "regulated_ops": ("connector_failure", "degraded_mode", "backup_restore", "tenant_support", "rollback"),
    "enterprise_service": ("connector_failure", "degraded_mode", "backup_restore", "tenant_support", "rollback", "sla_breach_response"),
    "financial_control": ("connector_failure", "degraded_mode", "backup_restore", "tenant_support", "rollback", "settlement_reconciliation"),
    "factory_quality": ("connector_failure", "degraded_mode", "backup_restore", "tenant_support", "rollback", "production_line_halt", "quality_hold"),
}

# Pack-specific pricing (133F)
@dataclass(frozen=True)
class PackPricing:
    pack_domain: str
    entry_monthly: float
    standard_monthly: float
    enterprise_monthly: float
    industrial_premium: float = 0.0  # factory only

PACK_PRICING = {
    "regulated_ops": PackPricing("regulated_ops", 0.0, 2500.0, 7500.0),
    "enterprise_service": PackPricing("enterprise_service", 0.0, 2500.0, 7500.0),
    "financial_control": PackPricing("financial_control", 0.0, 3000.0, 9000.0),
    "factory_quality": PackPricing("factory_quality", 0.0, 4000.0, 12000.0, industrial_premium=2000.0),
}

ADDON_PRICING = {
    "copilot": 500.0,
    "multimodal_voice": 1000.0,
    "self_tuning": 750.0,
    "blockchain_settlement": 500.0,
    "robotics_control": 1500.0,
    "process_simulation": 1000.0,
    "advanced_governance": 750.0,
}
