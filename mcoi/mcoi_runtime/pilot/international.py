"""Phase 150 — International / Multi-Region Expansion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 150A — Region Model
@dataclass(frozen=True)
class RegionProfile:
    region_id: str
    country: str
    subregion: str  # "north_america", "europe", "apac", "latam", "mena", "africa"
    jurisdiction: str  # "us", "eu_gdpr", "uk", "singapore", "australia", "brazil_lgpd", "uae"
    data_residency: str  # "us_east", "eu_west", "ap_southeast", "local_sovereign"
    currency: str  # "USD", "EUR", "GBP", "SGD", "AUD", "BRL", "AED"
    timezone: str  # "America/New_York", "Europe/London", "Asia/Singapore", etc.
    language: str  # "en", "es", "fr", "de", "pt", "ar", "zh"

REGIONS = {
    "us": RegionProfile("us", "United States", "north_america", "us", "us_east", "USD", "America/New_York", "en"),
    "eu": RegionProfile("eu", "European Union", "europe", "eu_gdpr", "eu_west", "EUR", "Europe/Berlin", "en"),
    "uk": RegionProfile("uk", "United Kingdom", "europe", "uk", "eu_west", "GBP", "Europe/London", "en"),
    "sg": RegionProfile("sg", "Singapore", "apac", "singapore", "ap_southeast", "SGD", "Asia/Singapore", "en"),
    "au": RegionProfile("au", "Australia", "apac", "australia", "ap_southeast", "AUD", "Australia/Sydney", "en"),
    "br": RegionProfile("br", "Brazil", "latam", "brazil_lgpd", "us_east", "BRL", "America/Sao_Paulo", "pt"),
    "ae": RegionProfile("ae", "UAE", "mena", "uae", "local_sovereign", "AED", "Asia/Dubai", "ar"),
}

# 150B — Localization
@dataclass(frozen=True)
class LocaleConfig:
    language: str
    date_format: str
    number_format: str  # "1,234.56" vs "1.234,56"
    currency_symbol: str
    currency_position: str  # "prefix" ($100) or "suffix" (100€)

LOCALES = {
    "en_US": LocaleConfig("en", "MM/DD/YYYY", "1,234.56", "$", "prefix"),
    "en_GB": LocaleConfig("en", "DD/MM/YYYY", "1,234.56", "£", "prefix"),
    "de_DE": LocaleConfig("de", "DD.MM.YYYY", "1.234,56", "€", "suffix"),
    "fr_FR": LocaleConfig("fr", "DD/MM/YYYY", "1 234,56", "€", "suffix"),
    "pt_BR": LocaleConfig("pt", "DD/MM/YYYY", "1.234,56", "R$", "prefix"),
    "ar_AE": LocaleConfig("ar", "DD/MM/YYYY", "1,234.56", "د.إ", "suffix"),
    "zh_CN": LocaleConfig("zh", "YYYY/MM/DD", "1,234.56", "¥", "prefix"),
}

# 150C — Regional Compliance
@dataclass(frozen=True)
class RegionalComplianceBundle:
    region_id: str
    data_residency_enforced: bool
    retention_default_days: int
    privacy_framework: str
    audit_format: str
    reporting_variant: str
    additional_rules: tuple[str, ...] = ()

COMPLIANCE_BUNDLES = {
    "us": RegionalComplianceBundle("us", False, 2555, "none", "us_gaap", "standard", ()),
    "eu_gdpr": RegionalComplianceBundle("eu_gdpr", True, 1825, "gdpr", "ifrs", "eu_variant", ("data_minimization", "right_to_erasure", "dpo_required")),
    "uk": RegionalComplianceBundle("uk", True, 1825, "uk_gdpr", "ifrs", "uk_variant", ("ico_notification",)),
    "brazil_lgpd": RegionalComplianceBundle("brazil_lgpd", True, 1825, "lgpd", "br_gaap", "br_variant", ("data_protection_officer",)),
    "singapore": RegionalComplianceBundle("singapore", True, 1825, "pdpa", "ifrs", "sg_variant", ()),
    "australia": RegionalComplianceBundle("australia", False, 2555, "privacy_act", "aasb", "au_variant", ()),
    "uae": RegionalComplianceBundle("uae", True, 1095, "pdpl", "ifrs", "ae_variant", ("sovereign_data",)),
}

# 150D — Multi-Region Deployment
@dataclass
class RegionalDeploymentConfig:
    region_id: str
    connector_bundle: tuple[str, ...]
    tenant_template: str
    support_routing: str  # "local", "follow_the_sun", "centralized"
    slo_variant: str
    pricing_currency: str
    tax_rate_pct: float

REGIONAL_DEPLOYMENTS = {
    "us": RegionalDeploymentConfig("us", ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"), "standard_us", "centralized", "standard", "USD", 0.0),
    "eu": RegionalDeploymentConfig("eu", ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"), "gdpr_eu", "follow_the_sun", "eu_sla", "EUR", 20.0),
    "uk": RegionalDeploymentConfig("uk", ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"), "uk_standard", "follow_the_sun", "uk_sla", "GBP", 20.0),
    "sg": RegionalDeploymentConfig("sg", ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"), "apac_standard", "follow_the_sun", "apac_sla", "SGD", 8.0),
    "ae": RegionalDeploymentConfig("ae", ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"), "sovereign_ae", "local", "ae_sla", "AED", 5.0),
}

# 150E — Regional GTM
@dataclass(frozen=True)
class RegionalGTMConfig:
    region_id: str
    partner_model: str  # "direct_first", "partner_first", "hybrid"
    certification_variant: str
    pricing_multiplier: float  # vs US base
    priority_packs: tuple[str, ...]

REGIONAL_GTM = {
    "us": RegionalGTMConfig("us", "hybrid", "standard", 1.0, ("regulated_ops", "enterprise_service", "financial_control")),
    "eu": RegionalGTMConfig("eu", "partner_first", "eu_certified", 1.1, ("regulated_ops", "financial_control", "public_sector")),
    "uk": RegionalGTMConfig("uk", "hybrid", "uk_certified", 1.05, ("regulated_ops", "financial_control", "enterprise_service")),
    "sg": RegionalGTMConfig("sg", "partner_first", "apac_certified", 0.9, ("enterprise_service", "financial_control")),
    "ae": RegionalGTMConfig("ae", "partner_first", "mena_certified", 1.15, ("public_sector", "regulated_ops")),
}

# 150F — Global Dashboard
class GlobalOperatingDashboard:
    def __init__(self):
        self._regional_tenants: dict[str, list[str]] = {}  # region -> tenant_ids

    def register_tenant(self, region: str, tenant_id: str) -> None:
        self._regional_tenants.setdefault(region, []).append(tenant_id)

    def tenants_by_region(self) -> dict[str, int]:
        return {r: len(ts) for r, ts in self._regional_tenants.items()}

    @property
    def total_regions(self) -> int:
        return len(self._regional_tenants)

    @property
    def total_tenants(self) -> int:
        return sum(len(ts) for ts in self._regional_tenants.values())

    def dashboard(self) -> dict[str, Any]:
        return {
            "total_regions": self.total_regions,
            "total_tenants": self.total_tenants,
            "tenants_by_region": self.tenants_by_region(),
            "regions_available": len(REGIONS),
            "compliance_bundles": len(COMPLIANCE_BUNDLES),
            "locales_supported": len(LOCALES),
            "deployment_configs": len(REGIONAL_DEPLOYMENTS),
        }
