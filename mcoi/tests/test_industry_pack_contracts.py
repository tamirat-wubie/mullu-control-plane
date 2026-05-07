"""Tests for industry pack contracts.

Governance scope: comprehensive coverage for all enums, dataclasses,
validation rules, immutability invariants, metadata freezing, and
serialization in the industry_pack contract module.
"""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.industry_pack import (
    DeploymentDisposition,
    IndustryPack,
    IndustryPackStatus,
    PackAssessment,
    PackBinding,
    PackCapability,
    PackCapabilityKind,
    PackClosureReport,
    PackConfiguration,
    PackDecision,
    PackDeploymentRecord,
    PackDomain,
    PackReadiness,
    PackRiskLevel,
    PackSnapshot,
    PackViolation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = "2026-03-24T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_industry_pack_status_members(self):
        assert len(IndustryPackStatus) == 5
        assert IndustryPackStatus.DRAFT.value == "draft"
        assert IndustryPackStatus.VALIDATED.value == "validated"
        assert IndustryPackStatus.DEPLOYED.value == "deployed"
        assert IndustryPackStatus.SUSPENDED.value == "suspended"
        assert IndustryPackStatus.RETIRED.value == "retired"

    def test_pack_domain_members(self):
        assert len(PackDomain) == 6
        assert PackDomain.REGULATED_OPS.value == "regulated_ops"
        assert PackDomain.RESEARCH_LAB.value == "research_lab"
        assert PackDomain.FACTORY_QUALITY.value == "factory_quality"
        assert PackDomain.ENTERPRISE_SERVICE.value == "enterprise_service"
        assert PackDomain.FINANCIAL_CONTROL.value == "financial_control"
        assert PackDomain.CUSTOM.value == "custom"

    def test_pack_capability_kind_members(self):
        assert len(PackCapabilityKind) == 10
        expected = {
            "intake", "case_management", "approval", "evidence",
            "reporting", "dashboard", "copilot", "governance",
            "observability", "continuity",
        }
        assert {k.value for k in PackCapabilityKind} == expected

    def test_pack_readiness_members(self):
        assert len(PackReadiness) == 4

    def test_deployment_disposition_members(self):
        assert len(DeploymentDisposition) == 4

    def test_pack_risk_level_members(self):
        assert len(PackRiskLevel) == 4


# ---------------------------------------------------------------------------
# IndustryPack
# ---------------------------------------------------------------------------


class TestIndustryPack:
    def test_valid(self):
        p = IndustryPack(
            pack_id="p1", tenant_id="t1", display_name="Test Pack",
            domain=PackDomain.REGULATED_OPS, created_at=_NOW,
        )
        assert p.pack_id == "p1"
        assert p.status == IndustryPackStatus.DRAFT
        assert p.capability_count == 0

    def test_empty_pack_id_rejected(self):
        with pytest.raises(ValueError):
            IndustryPack(pack_id="", tenant_id="t1", display_name="X", created_at=_NOW)

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            IndustryPack(pack_id="p1", tenant_id="", display_name="X", created_at=_NOW)

    def test_bad_domain_rejected(self):
        with pytest.raises(ValueError, match="^domain must be a PackDomain value$") as exc_info:
            IndustryPack(pack_id="p1", tenant_id="t1", display_name="X", domain="bad", created_at=_NOW)
        assert "str" not in str(exc_info.value)
        assert "bad" not in str(exc_info.value)

    def test_bad_status_rejected(self):
        with pytest.raises(ValueError, match="^status must be an IndustryPackStatus value$") as exc_info:
            IndustryPack(pack_id="p1", tenant_id="t1", display_name="X", status="bad", created_at=_NOW)
        assert "<class 'str'>" not in str(exc_info.value)
        assert "bad" not in str(exc_info.value)

    def test_negative_capability_count_rejected(self):
        with pytest.raises(ValueError):
            IndustryPack(pack_id="p1", tenant_id="t1", display_name="X", capability_count=-1, created_at=_NOW)

    def test_metadata_frozen(self):
        p = IndustryPack(pack_id="p1", tenant_id="t1", display_name="X", created_at=_NOW, metadata={"k": "v"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_serialization(self):
        p = IndustryPack(pack_id="p1", tenant_id="t1", display_name="X", created_at=_NOW)
        d = p.to_dict()
        assert d["pack_id"] == "p1"
        jd = p.to_json_dict()
        assert jd["domain"] == "custom"
        j = p.to_json()
        assert "p1" in j

    def test_immutable(self):
        p = IndustryPack(pack_id="p1", tenant_id="t1", display_name="X", created_at=_NOW)
        with pytest.raises(AttributeError):
            p.pack_id = "p2"


# ---------------------------------------------------------------------------
# PackCapability
# ---------------------------------------------------------------------------


class TestPackCapability:
    def test_valid(self):
        c = PackCapability(
            capability_id="c1", tenant_id="t1", pack_ref="p1",
            kind=PackCapabilityKind.INTAKE, target_runtime="rt1", created_at=_NOW,
        )
        assert c.enabled is True

    def test_enabled_must_be_bool(self):
        with pytest.raises(ValueError, match="^enabled must be a boolean value$") as exc_info:
            PackCapability(
                capability_id="c1", tenant_id="t1", pack_ref="p1",
                kind=PackCapabilityKind.INTAKE, target_runtime="rt1",
                enabled=1, created_at=_NOW,
            )
        assert "int" not in str(exc_info.value)

    def test_enabled_false(self):
        c = PackCapability(
            capability_id="c1", tenant_id="t1", pack_ref="p1",
            kind=PackCapabilityKind.INTAKE, target_runtime="rt1",
            enabled=False, created_at=_NOW,
        )
        assert c.enabled is False

    def test_bad_kind_rejected(self):
        with pytest.raises(ValueError, match="^kind must be a PackCapabilityKind value$") as exc_info:
            PackCapability(
                capability_id="c1", tenant_id="t1", pack_ref="p1",
                kind="bad", target_runtime="rt1", created_at=_NOW,
            )
        assert "bad" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# PackConfiguration
# ---------------------------------------------------------------------------


class TestPackConfiguration:
    def test_valid(self):
        cfg = PackConfiguration(config_id="cfg1", tenant_id="t1", pack_ref="p1", key="k", value="v", created_at=_NOW)
        assert cfg.key == "k"

    def test_empty_key_rejected(self):
        with pytest.raises(ValueError):
            PackConfiguration(config_id="cfg1", tenant_id="t1", pack_ref="p1", key="", value="v", created_at=_NOW)


# ---------------------------------------------------------------------------
# PackBinding
# ---------------------------------------------------------------------------


class TestPackBinding:
    def test_valid(self):
        b = PackBinding(binding_id="b1", tenant_id="t1", pack_ref="p1", runtime_ref="rt1", binding_type="primary", created_at=_NOW)
        assert b.binding_type == "primary"

    def test_empty_runtime_ref_rejected(self):
        with pytest.raises(ValueError):
            PackBinding(binding_id="b1", tenant_id="t1", pack_ref="p1", runtime_ref="", binding_type="primary", created_at=_NOW)


# ---------------------------------------------------------------------------
# PackAssessment
# ---------------------------------------------------------------------------


class TestPackAssessment:
    def test_valid(self):
        a = PackAssessment(
            assessment_id="a1", tenant_id="t1", pack_ref="p1",
            readiness=PackReadiness.READY, total_capabilities=10,
            enabled_capabilities=10, readiness_score=1.0, assessed_at=_NOW,
        )
        assert a.readiness_score == 1.0

    def test_score_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            PackAssessment(
                assessment_id="a1", tenant_id="t1", pack_ref="p1",
                readiness=PackReadiness.READY, total_capabilities=10,
                enabled_capabilities=10, readiness_score=1.5, assessed_at=_NOW,
            )

    def test_negative_score_rejected(self):
        with pytest.raises(ValueError):
            PackAssessment(
                assessment_id="a1", tenant_id="t1", pack_ref="p1",
                readiness=PackReadiness.NOT_READY, total_capabilities=10,
                enabled_capabilities=0, readiness_score=-0.1, assessed_at=_NOW,
            )


# ---------------------------------------------------------------------------
# PackDecision
# ---------------------------------------------------------------------------


class TestPackDecision:
    def test_valid(self):
        d = PackDecision(
            decision_id="d1", tenant_id="t1", pack_ref="p1",
            disposition=DeploymentDisposition.APPROVED, reason="ok", decided_at=_NOW,
        )
        assert d.disposition == DeploymentDisposition.APPROVED

    def test_bad_disposition_rejected(self):
        with pytest.raises(ValueError, match="^disposition must be a DeploymentDisposition value$") as exc_info:
            PackDecision(
                decision_id="d1", tenant_id="t1", pack_ref="p1",
                disposition="bad", reason="ok", decided_at=_NOW,
            )
        assert "bad" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# PackViolation
# ---------------------------------------------------------------------------


class TestPackViolation:
    def test_valid(self):
        v = PackViolation(violation_id="v1", tenant_id="t1", operation="deploy", reason="bad", detected_at=_NOW)
        assert v.operation == "deploy"


# ---------------------------------------------------------------------------
# PackSnapshot
# ---------------------------------------------------------------------------


class TestPackSnapshot:
    def test_valid(self):
        s = PackSnapshot(
            snapshot_id="s1", tenant_id="t1", total_packs=1,
            total_capabilities=10, total_bindings=2, total_configs=3,
            total_violations=0, captured_at=_NOW,
        )
        assert s.total_packs == 1

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            PackSnapshot(
                snapshot_id="s1", tenant_id="t1", total_packs=-1,
                total_capabilities=10, total_bindings=2, total_configs=3,
                total_violations=0, captured_at=_NOW,
            )


# ---------------------------------------------------------------------------
# PackDeploymentRecord
# ---------------------------------------------------------------------------


class TestPackDeploymentRecord:
    def test_valid(self):
        dr = PackDeploymentRecord(
            deployment_id="dr1", tenant_id="t1", pack_ref="p1",
            disposition=DeploymentDisposition.APPROVED, deployed_at=_NOW,
        )
        assert dr.deployment_id == "dr1"

    def test_bad_disposition_rejected(self):
        with pytest.raises(ValueError, match="^disposition must be a DeploymentDisposition value$") as exc_info:
            PackDeploymentRecord(
                deployment_id="dr1", tenant_id="t1", pack_ref="p1",
                disposition="bad", deployed_at=_NOW,
            )
        assert "bad" not in str(exc_info.value)


class TestBoundedIndustryPackContractMessages:
    def test_readiness_type_error_is_bounded(self):
        with pytest.raises(ValueError, match="^readiness must be a PackReadiness value$") as exc_info:
            PackAssessment(
                assessment_id="a1", tenant_id="t1", pack_ref="p1",
                readiness="secret-readiness", total_capabilities=1,
                enabled_capabilities=1, readiness_score=1.0, assessed_at=_NOW,
            )
        assert "secret-readiness" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# PackClosureReport
# ---------------------------------------------------------------------------


class TestPackClosureReport:
    def test_valid(self):
        cr = PackClosureReport(
            report_id="cr1", tenant_id="t1", total_packs=1,
            total_deployments=1, total_violations=0, created_at=_NOW,
        )
        assert cr.total_deployments == 1

    def test_negative_deployments_rejected(self):
        with pytest.raises(ValueError):
            PackClosureReport(
                report_id="cr1", tenant_id="t1", total_packs=1,
                total_deployments=-1, total_violations=0, created_at=_NOW,
            )
