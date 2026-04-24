"""Tests for AssuranceRuntimeEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.assurance_runtime import (
    AssuranceDecision,
    AssuranceEvidenceBinding,
    AssuranceFinding,
    AssuranceLevel,
    AssuranceScope,
    AssuranceSnapshot,
    AttestationRecord,
    AttestationStatus,
    CertificationRecord,
    CertificationStatus,
    EvidenceSufficiency,
    RecertificationStatus,
    RecertificationWindow,
)
from mcoi_runtime.core.assurance_runtime import AssuranceRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ── Helpers ──────────────────────────────────────────────────────────

def _make_engine() -> tuple[AssuranceRuntimeEngine, EventSpineEngine]:
    es = EventSpineEngine()
    eng = AssuranceRuntimeEngine(es)
    return eng, es


def _register_and_bind(eng: AssuranceRuntimeEngine, att_id: str = "att-1",
                       tenant: str = "t1", ref: str = "ref-1",
                       binding_id: str = "b-1") -> AttestationRecord:
    att = eng.register_attestation(att_id, tenant, ref, attested_by="assurance-attester-1")
    eng.bind_evidence(binding_id, att_id, "attestation", "record", "rec-1")
    return att


def _register_cert_and_bind(eng: AssuranceRuntimeEngine, cert_id: str = "cert-1",
                            tenant: str = "t1", ref: str = "ref-1",
                            binding_id: str = "bc-1") -> CertificationRecord:
    cert = eng.register_certification(cert_id, tenant, ref, certified_by="assurance-certifier-1")
    eng.bind_evidence(binding_id, cert_id, "certification", "record", "rec-1")
    return cert


# =====================================================================
# Constructor
# =====================================================================

class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AssuranceRuntimeEngine("not-an-engine")

    def test_valid_construction(self):
        eng, _ = _make_engine()
        assert eng.attestation_count == 0
        assert eng.certification_count == 0
        assert eng.assessment_count == 0
        assert eng.binding_count == 0
        assert eng.finding_count == 0
        assert eng.decision_count == 0
        assert eng.violation_count == 0
        assert eng.window_count == 0


# =====================================================================
# Attestation registration
# =====================================================================

class TestRegisterAttestation:
    def test_basic_registration(self):
        eng, es = _make_engine()
        att = eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        assert isinstance(att, AttestationRecord)
        assert att.attestation_id == "att-1"
        assert att.tenant_id == "t1"
        assert att.scope_ref_id == "ref-1"
        assert att.status == AttestationStatus.PENDING
        assert att.scope == AssuranceScope.CONTROL
        assert att.level == AssuranceLevel.NONE
        assert eng.attestation_count == 1
        assert es.event_count >= 1

    def test_custom_scope_and_level(self):
        eng, _ = _make_engine()
        att = eng.register_attestation(
            "att-1", "t1", "ref-1",
            scope=AssuranceScope.PROGRAM,
            level=AssuranceLevel.HIGH,
            attested_by="assurance-attester-1",
        )
        assert att.scope == AssuranceScope.PROGRAM
        assert att.level == AssuranceLevel.HIGH

    def test_custom_attested_by(self):
        eng, _ = _make_engine()
        att = eng.register_attestation("att-1", "t1", "ref-1", attested_by="admin")
        assert att.attested_by == "admin"

    def test_missing_attested_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="attested_by required for attestation"):
            eng.register_attestation("att-1", "t1", "ref-1")

    def test_system_attested_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="attested_by must exclude system"):
            eng.register_attestation("att-1", "t1", "ref-1", attested_by="system")

    def test_duplicate_raises(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_attestation("att-1", "t2", "ref-2", attested_by="assurance-attester-1")

    def test_get_attestation(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        att = eng.get_attestation("att-1")
        assert att.attestation_id == "att-1"

    def test_get_attestation_unknown(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_attestation("nope")

    def test_attestations_for_tenant(self):
        eng, _ = _make_engine()
        eng.register_attestation("a1", "t1", "r1", attested_by="assurance-attester-1")
        eng.register_attestation("a2", "t1", "r2", attested_by="assurance-attester-1")
        eng.register_attestation("a3", "t2", "r3", attested_by="assurance-attester-1")
        result = eng.attestations_for_tenant("t1")
        assert len(result) == 2
        assert isinstance(result, tuple)

    def test_attestations_for_tenant_empty(self):
        eng, _ = _make_engine()
        assert eng.attestations_for_tenant("t99") == ()

    def test_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        assert es.event_count > initial

    def test_all_scopes(self):
        eng, _ = _make_engine()
        for i, scope in enumerate(AssuranceScope):
            att = eng.register_attestation(f"att-{i}", "t1", f"ref-{i}", scope=scope, attested_by="assurance-attester-1")
            assert att.scope == scope

    def test_all_levels(self):
        eng, _ = _make_engine()
        for i, level in enumerate(AssuranceLevel):
            att = eng.register_attestation(f"att-{i}", "t1", f"ref-{i}", level=level, attested_by="assurance-attester-1")
            assert att.level == level


# =====================================================================
# Grant attestation
# =====================================================================

class TestGrantAttestation:
    def test_grant_with_evidence(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        granted = eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        assert granted.status == AttestationStatus.GRANTED
        assert granted.level == AssuranceLevel.HIGH
        assert eng.granted_attestation_count == 1

    def test_grant_without_evidence_raises(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        with pytest.raises(RuntimeCoreInvariantError, match="without evidence"):
            eng.grant_attestation("att-1", AssuranceLevel.HIGH)

    def test_grant_revoked_raises(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.revoke_attestation("att-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot grant"):
            eng.grant_attestation("att-1", AssuranceLevel.LOW)

    def test_grant_preserves_fields(self):
        eng, _ = _make_engine()
        orig = _register_and_bind(eng)
        granted = eng.grant_attestation("att-1", AssuranceLevel.MODERATE)
        assert granted.tenant_id == orig.tenant_id
        assert granted.scope == orig.scope
        assert granted.scope_ref_id == orig.scope_ref_id
        assert granted.attested_by == orig.attested_by

    def test_grant_emits_event(self):
        eng, es = _make_engine()
        _register_and_bind(eng)
        initial = es.event_count
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        assert es.event_count > initial

    def test_grant_different_levels(self):
        eng, _ = _make_engine()
        for i, level in enumerate([AssuranceLevel.LOW, AssuranceLevel.MODERATE, AssuranceLevel.HIGH, AssuranceLevel.FULL]):
            _register_and_bind(eng, att_id=f"att-{i}", binding_id=f"b-{i}")
            granted = eng.grant_attestation(f"att-{i}", level)
            assert granted.level == level


# =====================================================================
# Deny attestation
# =====================================================================

class TestDenyAttestation:
    def test_deny_pending(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        denied = eng.deny_attestation("att-1", reason="insufficient")
        assert denied.status == AttestationStatus.DENIED
        assert denied.level == AssuranceLevel.NONE

    def test_deny_granted(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        denied = eng.deny_attestation("att-1")
        assert denied.status == AttestationStatus.DENIED

    def test_deny_revoked_raises(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.revoke_attestation("att-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            eng.deny_attestation("att-1")

    def test_deny_expired_raises(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        # Force expired status
        old = eng.get_attestation("att-1")
        expired = AttestationRecord(
            attestation_id=old.attestation_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            level=old.level,
            status=AttestationStatus.EXPIRED,
            attested_by=old.attested_by,
            attested_at=old.attested_at,
        )
        eng._attestations["att-1"] = expired
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            eng.deny_attestation("att-1")

    def test_deny_emits_event(self):
        eng, es = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        initial = es.event_count
        eng.deny_attestation("att-1")
        assert es.event_count > initial


# =====================================================================
# Revoke attestation
# =====================================================================

class TestRevokeAttestation:
    def test_revoke_granted(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        revoked = eng.revoke_attestation("att-1", reason="violation")
        assert revoked.status == AttestationStatus.REVOKED
        assert revoked.level == AssuranceLevel.NONE
        assert eng.granted_attestation_count == 0

    def test_revoke_pending_raises(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        with pytest.raises(RuntimeCoreInvariantError, match="only revoke GRANTED"):
            eng.revoke_attestation("att-1")

    def test_revoke_denied_raises(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        eng.deny_attestation("att-1")
        with pytest.raises(RuntimeCoreInvariantError, match="only revoke GRANTED"):
            eng.revoke_attestation("att-1")

    def test_revoke_emits_event(self):
        eng, es = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        initial = es.event_count
        eng.revoke_attestation("att-1")
        assert es.event_count > initial


# =====================================================================
# Certification registration
# =====================================================================

class TestRegisterCertification:
    def test_basic_registration(self):
        eng, es = _make_engine()
        cert = eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        assert isinstance(cert, CertificationRecord)
        assert cert.certification_id == "cert-1"
        assert cert.status == CertificationStatus.PENDING
        assert cert.scope == AssuranceScope.CONTROL
        assert cert.level == AssuranceLevel.NONE
        assert eng.certification_count == 1
        assert es.event_count >= 1

    def test_custom_scope(self):
        eng, _ = _make_engine()
        cert = eng.register_certification(
            "cert-1", "t1", "ref-1",
            scope=AssuranceScope.CONNECTOR,
            level=AssuranceLevel.FULL,
            certified_by="assurance-certifier-1",
        )
        assert cert.scope == AssuranceScope.CONNECTOR
        assert cert.level == AssuranceLevel.FULL

    def test_missing_certified_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="certified_by required for certification"):
            eng.register_certification("cert-1", "t1", "ref-1")

    def test_system_certified_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="certified_by must exclude system"):
            eng.register_certification("cert-1", "t1", "ref-1", certified_by="system")

    def test_duplicate_raises(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_certification("cert-1", "t2", "ref-2", certified_by="assurance-certifier-1")

    def test_get_certification(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        cert = eng.get_certification("cert-1")
        assert cert.certification_id == "cert-1"

    def test_get_certification_unknown(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown") as exc_info:
            eng.get_certification("nope")
        assert "nope" not in str(exc_info.value)

    def test_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        assert es.event_count > initial


# =====================================================================
# Activate certification
# =====================================================================

class TestActivateCertification:
    def test_activate_with_evidence(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        active = eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        assert active.status == CertificationStatus.ACTIVE
        assert active.level == AssuranceLevel.HIGH
        assert eng.active_certification_count == 1

    def test_activate_without_evidence_raises(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        with pytest.raises(RuntimeCoreInvariantError, match="without evidence"):
            eng.activate_certification("cert-1", AssuranceLevel.HIGH)

    def test_activate_revoked_raises(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        eng.revoke_certification("cert-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot activate"):
            eng.activate_certification("cert-1", AssuranceLevel.LOW)

    def test_activate_expired_raises(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.expire_certification("cert-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot activate"):
            eng.activate_certification("cert-1", AssuranceLevel.LOW)

    def test_activate_emits_event(self):
        eng, es = _make_engine()
        _register_cert_and_bind(eng)
        initial = es.event_count
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        assert es.event_count > initial


# =====================================================================
# Suspend certification
# =====================================================================

class TestSuspendCertification:
    def test_suspend_active(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        suspended = eng.suspend_certification("cert-1", reason="audit")
        assert suspended.status == CertificationStatus.SUSPENDED
        assert eng.active_certification_count == 0

    def test_suspend_pending_raises(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        with pytest.raises(RuntimeCoreInvariantError, match="only suspend ACTIVE"):
            eng.suspend_certification("cert-1")

    def test_suspend_preserves_level(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        suspended = eng.suspend_certification("cert-1")
        assert suspended.level == AssuranceLevel.HIGH

    def test_suspend_emits_event(self):
        eng, es = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        initial = es.event_count
        eng.suspend_certification("cert-1")
        assert es.event_count > initial


# =====================================================================
# Revoke certification
# =====================================================================

class TestRevokeCertification:
    def test_revoke_active(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        revoked = eng.revoke_certification("cert-1", reason="breach")
        assert revoked.status == CertificationStatus.REVOKED
        assert revoked.level == AssuranceLevel.NONE

    def test_revoke_pending(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        revoked = eng.revoke_certification("cert-1")
        assert revoked.status == CertificationStatus.REVOKED

    def test_revoke_already_revoked_raises(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        eng.revoke_certification("cert-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot revoke"):
            eng.revoke_certification("cert-1")

    def test_revoke_suspended(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        eng.suspend_certification("cert-1")
        revoked = eng.revoke_certification("cert-1")
        assert revoked.status == CertificationStatus.REVOKED

    def test_revoke_emits_event(self):
        eng, es = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        initial = es.event_count
        eng.revoke_certification("cert-1")
        assert es.event_count > initial


# =====================================================================
# Expire certification
# =====================================================================

class TestExpireCertification:
    def test_expire_active(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        expired = eng.expire_certification("cert-1")
        assert expired.status == CertificationStatus.EXPIRED
        assert expired.level == AssuranceLevel.NONE

    def test_expire_pending(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        expired = eng.expire_certification("cert-1")
        assert expired.status == CertificationStatus.EXPIRED

    def test_expire_already_expired_raises(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.expire_certification("cert-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot expire"):
            eng.expire_certification("cert-1")

    def test_expire_emits_event(self):
        eng, es = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        initial = es.event_count
        eng.expire_certification("cert-1")
        assert es.event_count > initial


# =====================================================================
# Mark recertification required
# =====================================================================

class TestMarkRecertificationRequired:
    def test_mark_active(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        marked = eng.mark_recertification_required("cert-1")
        assert marked.status == CertificationStatus.RECERTIFICATION_REQUIRED
        assert marked.level == AssuranceLevel.HIGH

    def test_mark_pending(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        marked = eng.mark_recertification_required("cert-1")
        assert marked.status == CertificationStatus.RECERTIFICATION_REQUIRED

    def test_mark_revoked_raises(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.revoke_certification("cert-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot mark"):
            eng.mark_recertification_required("cert-1")

    def test_mark_emits_event(self):
        eng, es = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        initial = es.event_count
        eng.mark_recertification_required("cert-1")
        assert es.event_count > initial


# =====================================================================
# Evidence binding
# =====================================================================

class TestBindEvidence:
    def test_basic_binding(self):
        eng, es = _make_engine()
        b = eng.bind_evidence("b1", "att-1", "attestation", "record", "rec-1")
        assert isinstance(b, AssuranceEvidenceBinding)
        assert b.binding_id == "b1"
        assert b.target_id == "att-1"
        assert b.target_type == "attestation"
        assert b.source_type == "record"
        assert b.source_id == "rec-1"
        assert eng.binding_count == 1

    def test_duplicate_raises(self):
        eng, _ = _make_engine()
        eng.bind_evidence("b1", "att-1", "attestation", "record", "rec-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.bind_evidence("b1", "att-2", "attestation", "record", "rec-2")

    def test_bindings_for_target(self):
        eng, _ = _make_engine()
        eng.bind_evidence("b1", "att-1", "attestation", "record", "rec-1")
        eng.bind_evidence("b2", "att-1", "attestation", "memory", "mem-1")
        eng.bind_evidence("b3", "cert-1", "certification", "event", "evt-1")
        result = eng.bindings_for_target("att-1", "attestation")
        assert len(result) == 2
        assert isinstance(result, tuple)

    def test_bindings_for_target_empty(self):
        eng, _ = _make_engine()
        assert eng.bindings_for_target("nope", "attestation") == ()

    def test_multiple_source_types(self):
        eng, _ = _make_engine()
        eng.bind_evidence("b1", "x", "attestation", "record", "r1")
        eng.bind_evidence("b2", "x", "attestation", "memory", "m1")
        eng.bind_evidence("b3", "x", "attestation", "event", "e1")
        assert eng.binding_count == 3
        assert len(eng.bindings_for_target("x", "attestation")) == 3

    def test_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.bind_evidence("b1", "att-1", "attestation", "record", "rec-1")
        assert es.event_count > initial


# =====================================================================
# Assess assurance
# =====================================================================

class TestAssessAssurance:
    def test_no_evidence_insufficient(self):
        eng, _ = _make_engine()
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a.sufficiency == EvidenceSufficiency.INSUFFICIENT
        assert a.level == AssuranceLevel.NONE
        assert a.confidence == 0.0

    def test_one_binding_partial(self):
        eng, _ = _make_engine()
        eng.bind_evidence("b1", "ref-1", "any", "record", "r1")
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a.sufficiency == EvidenceSufficiency.PARTIAL
        assert a.level == AssuranceLevel.LOW
        assert a.confidence == pytest.approx(0.3)

    def test_two_bindings_sufficient(self):
        eng, _ = _make_engine()
        eng.bind_evidence("b1", "ref-1", "any", "record", "r1")
        eng.bind_evidence("b2", "ref-1", "any", "memory", "m1")
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a.sufficiency == EvidenceSufficiency.SUFFICIENT
        assert a.level == AssuranceLevel.MODERATE
        assert a.confidence == pytest.approx(0.7)

    def test_three_bindings_sufficient(self):
        eng, _ = _make_engine()
        for i in range(3):
            eng.bind_evidence(f"b{i}", "ref-1", "any", "record", f"r{i}")
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a.sufficiency == EvidenceSufficiency.SUFFICIENT
        assert a.level == AssuranceLevel.MODERATE

    def test_four_bindings_comprehensive(self):
        eng, _ = _make_engine()
        for i in range(4):
            eng.bind_evidence(f"b{i}", "ref-1", "any", "record", f"r{i}")
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a.sufficiency == EvidenceSufficiency.COMPREHENSIVE
        assert a.level == AssuranceLevel.HIGH
        assert a.confidence == pytest.approx(0.9)

    def test_five_bindings_comprehensive(self):
        eng, _ = _make_engine()
        for i in range(5):
            eng.bind_evidence(f"b{i}", "ref-1", "any", "record", f"r{i}")
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a.sufficiency == EvidenceSufficiency.COMPREHENSIVE
        assert a.level == AssuranceLevel.HIGH

    def test_missing_assessed_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="assessed_by required for assurance assessment"):
            eng.assess_assurance("a1", "t1", "ref-1")

    def test_system_assessed_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="assessed_by must exclude system"):
            eng.assess_assurance("a1", "t1", "ref-1", assessed_by="system")

    def test_duplicate_assessment_raises(self):
        eng, _ = _make_engine()
        eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")

    def test_assessment_count(self):
        eng, _ = _make_engine()
        eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        eng.assess_assurance("a2", "t1", "ref-2", assessed_by="assurance-assessor-1")
        assert eng.assessment_count == 2

    def test_assessment_is_frozen(self):
        eng, _ = _make_engine()
        a = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        with pytest.raises(AttributeError):
            a.level = AssuranceLevel.HIGH

    def test_assessment_scope(self):
        eng, _ = _make_engine()
        a = eng.assess_assurance("a1", "t1", "ref-1", scope=AssuranceScope.PROGRAM, assessed_by="assurance-assessor-1")
        assert a.scope == AssuranceScope.PROGRAM

    def test_assessment_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert es.event_count > initial


# =====================================================================
# Record assurance finding
# =====================================================================

class TestRecordAssuranceFinding:
    def test_basic_finding(self):
        eng, _ = _make_engine()
        f = eng.record_assurance_finding(
            "f1", "target-1", "attestation",
            description="test finding",
            impact_level=AssuranceLevel.LOW,
        )
        assert isinstance(f, AssuranceFinding)
        assert f.finding_id == "f1"
        assert f.impact_level == AssuranceLevel.LOW
        assert f.description == "test finding"
        assert eng.finding_count == 1

    def test_duplicate_raises(self):
        eng, _ = _make_engine()
        eng.record_assurance_finding("f1", "t1", "attestation")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_assurance_finding("f1", "t2", "cert")

    def test_high_impact_revokes_granted_attestation(self):
        eng, _ = _make_engine()
        _register_and_bind(eng, ref="target-1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        assert eng.granted_attestation_count == 1
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.HIGH)
        assert eng.get_attestation("att-1").status == AttestationStatus.REVOKED
        assert eng.granted_attestation_count == 0

    def test_full_impact_revokes_granted_attestation(self):
        eng, _ = _make_engine()
        _register_and_bind(eng, ref="target-1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.FULL)
        assert eng.get_attestation("att-1").status == AttestationStatus.REVOKED

    def test_high_impact_suspends_active_certification(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng, ref="target-1")
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        assert eng.active_certification_count == 1
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.HIGH)
        assert eng.get_certification("cert-1").status == CertificationStatus.SUSPENDED
        assert eng.active_certification_count == 0

    def test_low_impact_does_not_revoke(self):
        eng, _ = _make_engine()
        _register_and_bind(eng, ref="target-1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.LOW)
        assert eng.get_attestation("att-1").status == AttestationStatus.GRANTED

    def test_moderate_impact_does_not_revoke(self):
        eng, _ = _make_engine()
        _register_and_bind(eng, ref="target-1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.MODERATE)
        assert eng.get_attestation("att-1").status == AttestationStatus.GRANTED

    def test_none_impact_does_not_revoke(self):
        eng, _ = _make_engine()
        _register_and_bind(eng, ref="target-1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.NONE)
        assert eng.get_attestation("att-1").status == AttestationStatus.GRANTED

    def test_finding_only_affects_matching_scope_ref(self):
        eng, _ = _make_engine()
        _register_and_bind(eng, att_id="att-1", ref="target-1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        _register_and_bind(eng, att_id="att-2", ref="target-2", binding_id="b-2")
        eng.grant_attestation("att-2", AssuranceLevel.HIGH)
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.HIGH)
        assert eng.get_attestation("att-1").status == AttestationStatus.REVOKED
        assert eng.get_attestation("att-2").status == AttestationStatus.GRANTED

    def test_finding_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.record_assurance_finding("f1", "t1", "attestation")
        assert es.event_count > initial

    def test_finding_does_not_affect_pending_attestation(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "target-1", attested_by="assurance-attester-1")
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.HIGH)
        assert eng.get_attestation("att-1").status == AttestationStatus.PENDING

    def test_finding_does_not_affect_pending_certification(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "target-1", certified_by="assurance-certifier-1")
        eng.record_assurance_finding("f1", "target-1", "scope", impact_level=AssuranceLevel.HIGH)
        assert eng.get_certification("cert-1").status == CertificationStatus.PENDING


# =====================================================================
# Make assurance decision
# =====================================================================

class TestMakeAssuranceDecision:
    def test_basic_decision(self):
        eng, _ = _make_engine()
        d = eng.make_assurance_decision(
            "d1", "att-1", "attestation",
            level=AssuranceLevel.HIGH,
            decided_by="admin",
            reason="all checks passed",
        )
        assert isinstance(d, AssuranceDecision)
        assert d.decision_id == "d1"
        assert d.level == AssuranceLevel.HIGH
        assert d.decided_by == "admin"
        assert d.reason == "all checks passed"
        assert eng.decision_count == 1

    def test_duplicate_raises(self):
        eng, _ = _make_engine()
        eng.make_assurance_decision("d1", "t1", "att", decided_by="assurance-decider-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.make_assurance_decision("d1", "t2", "cert", decided_by="assurance-decider-1")

    def test_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.make_assurance_decision("d1", "t1", "att", decided_by="assurance-decider-1")
        assert es.event_count > initial

    def test_default_values(self):
        eng, _ = _make_engine()
        d = eng.make_assurance_decision("d1", "t1", "att", decided_by="assurance-decider-1")
        assert d.level == AssuranceLevel.NONE
        assert d.decided_by == "assurance-decider-1"
        assert d.reason == ""

    def test_missing_decided_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="decided_by required for assurance decision"):
            eng.make_assurance_decision("d1", "t1", "att")

    def test_system_decided_by_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="decided_by must exclude system"):
            eng.make_assurance_decision("d1", "t1", "att", decided_by="system")


# =====================================================================
# Schedule recertification
# =====================================================================

class TestScheduleRecertification:
    def test_basic_schedule(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        w = eng.schedule_recertification(
            "w1", "cert-1",
            "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00",
        )
        assert isinstance(w, RecertificationWindow)
        assert w.window_id == "w1"
        assert w.certification_id == "cert-1"
        assert w.status == RecertificationStatus.SCHEDULED
        assert eng.window_count == 1

    def test_duplicate_raises(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification("w1", "cert-1", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.schedule_recertification("w1", "cert-1", "2026-02-01T00:00:00+00:00", "2026-07-01T00:00:00+00:00")

    def test_unknown_certification_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown") as exc_info:
            eng.schedule_recertification("w1", "nope", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        assert "nope" not in str(exc_info.value)

    def test_windows_for_certification(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.register_certification("cert-2", "t1", "ref-2", certified_by="assurance-certifier-1")
        eng.schedule_recertification("w1", "cert-1", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        eng.schedule_recertification("w2", "cert-1", "2026-07-01T00:00:00+00:00", "2026-12-01T00:00:00+00:00")
        eng.schedule_recertification("w3", "cert-2", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        result = eng.windows_for_certification("cert-1")
        assert len(result) == 2
        assert isinstance(result, tuple)

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        initial = es.event_count
        eng.schedule_recertification("w1", "cert-1", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        assert es.event_count > initial


# =====================================================================
# Complete recertification
# =====================================================================

class TestCompleteRecertification:
    def test_complete_window(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification("w1", "cert-1", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        completed = eng.complete_recertification("w1")
        assert completed.status == RecertificationStatus.COMPLETED
        assert completed.completed_at != ""

    def test_unknown_window_raises(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown") as exc_info:
            eng.complete_recertification("nope")
        assert "nope" not in str(exc_info.value)

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification("w1", "cert-1", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        initial = es.event_count
        eng.complete_recertification("w1")
        assert es.event_count > initial


# =====================================================================
# Violation detection
# =====================================================================

class TestDetectAssuranceViolations:
    def test_no_violations(self):
        eng, _ = _make_engine()
        violations = eng.detect_assurance_violations()
        assert violations == ()
        assert eng.violation_count == 0

    def test_expired_active_certification(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        old = eng.get_certification("cert-1")
        expired_cert = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.ACTIVE,
            level=old.level,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at="2020-01-01T00:00:00+00:00",
        )
        eng._certifications["cert-1"] = expired_cert
        violations = eng.detect_assurance_violations()
        assert len(violations) >= 1
        ops = [v.operation for v in violations]
        assert "expired_certification_active" in ops

    def test_overdue_recertification_window(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification(
            "w1", "cert-1",
            "2020-01-01T00:00:00+00:00", "2020-06-01T00:00:00+00:00",
        )
        violations = eng.detect_assurance_violations()
        assert len(violations) >= 1
        ops = [v.operation for v in violations]
        assert "overdue_recertification" in ops

    def test_idempotent_violation_detection(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification(
            "w1", "cert-1",
            "2020-01-01T00:00:00+00:00", "2020-06-01T00:00:00+00:00",
        )
        v1 = eng.detect_assurance_violations()
        v2 = eng.detect_assurance_violations()
        assert len(v1) >= 1
        assert len(v2) == 0

    def test_violations_for_tenant(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification(
            "w1", "cert-1",
            "2020-01-01T00:00:00+00:00", "2020-06-01T00:00:00+00:00",
        )
        eng.detect_assurance_violations()
        result = eng.violations_for_tenant("t1")
        assert len(result) >= 1
        assert isinstance(result, tuple)

    def test_violations_for_tenant_empty(self):
        eng, _ = _make_engine()
        assert eng.violations_for_tenant("t99") == ()

    def test_completed_window_no_violation(self):
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification(
            "w1", "cert-1",
            "2020-01-01T00:00:00+00:00", "2020-06-01T00:00:00+00:00",
        )
        eng.complete_recertification("w1")
        violations = eng.detect_assurance_violations()
        assert len([v for v in violations if v.operation == "overdue_recertification"]) == 0


# =====================================================================
# Snapshot
# =====================================================================

class TestAssuranceSnapshot:
    def test_basic_snapshot(self):
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        snap = eng.assurance_snapshot("snap-1", "ref-1")
        assert isinstance(snap, AssuranceSnapshot)
        assert snap.snapshot_id == "snap-1"
        assert snap.total_attestations == 1
        assert snap.total_certifications == 1
        assert snap.captured_at != ""

    def test_snapshot_reflects_state(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.MODERATE)
        eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        snap = eng.assurance_snapshot("snap-1")
        assert snap.total_attestations == 1
        assert snap.granted_attestations == 1
        assert snap.total_certifications == 1
        assert snap.active_certifications == 1
        assert snap.total_assessments == 1
        assert snap.total_evidence_bindings == 2

    def test_duplicate_snapshot_raises(self):
        eng, _ = _make_engine()
        eng.assurance_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.assurance_snapshot("snap-1")

    def test_snapshot_emits_event(self):
        eng, es = _make_engine()
        initial = es.event_count
        eng.assurance_snapshot("snap-1")
        assert es.event_count > initial

    def test_empty_snapshot(self):
        eng, _ = _make_engine()
        snap = eng.assurance_snapshot("snap-1")
        assert snap.total_attestations == 0
        assert snap.granted_attestations == 0
        assert snap.total_certifications == 0
        assert snap.active_certifications == 0


# =====================================================================
# State hash
# =====================================================================

class TestStateHash:
    def test_deterministic(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_changes_with_state(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_returns_string(self):
        eng, _ = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# =====================================================================
# Properties
# =====================================================================

class TestProperties:
    def test_granted_attestation_count(self):
        eng, _ = _make_engine()
        assert eng.granted_attestation_count == 0
        _register_and_bind(eng, att_id="a1", binding_id="b1")
        _register_and_bind(eng, att_id="a2", binding_id="b2")
        eng.grant_attestation("a1", AssuranceLevel.HIGH)
        assert eng.granted_attestation_count == 1
        eng.grant_attestation("a2", AssuranceLevel.LOW)
        assert eng.granted_attestation_count == 2

    def test_active_certification_count(self):
        eng, _ = _make_engine()
        assert eng.active_certification_count == 0
        _register_cert_and_bind(eng, cert_id="c1", binding_id="bc1")
        _register_cert_and_bind(eng, cert_id="c2", binding_id="bc2")
        eng.activate_certification("c1", AssuranceLevel.HIGH)
        assert eng.active_certification_count == 1
        eng.activate_certification("c2", AssuranceLevel.MODERATE)
        assert eng.active_certification_count == 2
        eng.suspend_certification("c1")
        assert eng.active_certification_count == 1

    def test_window_count(self):
        eng, _ = _make_engine()
        assert eng.window_count == 0
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.schedule_recertification("w1", "cert-1", "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00")
        assert eng.window_count == 1

    def test_finding_count(self):
        eng, _ = _make_engine()
        assert eng.finding_count == 0
        eng.record_assurance_finding("f1", "t1", "att")
        assert eng.finding_count == 1

    def test_decision_count(self):
        eng, _ = _make_engine()
        assert eng.decision_count == 0
        eng.make_assurance_decision("d1", "t1", "att", decided_by="assurance-decider-1")
        assert eng.decision_count == 1


# =====================================================================
# Golden scenarios
# =====================================================================

class TestGoldenScenarios:
    def test_scenario_1_full_attestation_lifecycle(self):
        """Register -> bind evidence -> grant -> revoke."""
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ctrl-1", attested_by="assurance-attester-1")
        eng.bind_evidence("b1", "att-1", "attestation", "record", "rec-1")
        granted = eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        assert granted.status == AttestationStatus.GRANTED
        revoked = eng.revoke_attestation("att-1", reason="policy change")
        assert revoked.status == AttestationStatus.REVOKED
        assert eng.granted_attestation_count == 0

    def test_scenario_2_full_certification_lifecycle(self):
        """Register -> bind -> activate -> suspend -> mark recertification."""
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "prog-1", scope=AssuranceScope.PROGRAM, certified_by="assurance-certifier-1")
        eng.bind_evidence("b1", "cert-1", "certification", "record", "rec-1")
        active = eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        assert active.status == CertificationStatus.ACTIVE
        suspended = eng.suspend_certification("cert-1", reason="audit")
        assert suspended.status == CertificationStatus.SUSPENDED

    def test_scenario_3_evidence_sufficiency_assessment(self):
        """Incrementally add evidence and re-assess."""
        eng, _ = _make_engine()
        a1 = eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a1.sufficiency == EvidenceSufficiency.INSUFFICIENT

        eng.bind_evidence("b1", "ref-1", "attestation", "record", "r1")
        a2 = eng.assess_assurance("a2", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a2.sufficiency == EvidenceSufficiency.PARTIAL

        eng.bind_evidence("b2", "ref-1", "attestation", "memory", "m1")
        eng.bind_evidence("b3", "ref-1", "attestation", "event", "e1")
        a3 = eng.assess_assurance("a3", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a3.sufficiency == EvidenceSufficiency.SUFFICIENT

        eng.bind_evidence("b4", "ref-1", "attestation", "record", "r2")
        a4 = eng.assess_assurance("a4", "t1", "ref-1", assessed_by="assurance-assessor-1")
        assert a4.sufficiency == EvidenceSufficiency.COMPREHENSIVE

    def test_scenario_4_high_finding_auto_degrades(self):
        """Grant attestation + activate cert, then HIGH finding revokes/suspends both."""
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "scope-1", attested_by="assurance-attester-1")
        eng.bind_evidence("b1", "att-1", "attestation", "record", "r1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.register_certification("cert-1", "t1", "scope-1", certified_by="assurance-certifier-1")
        eng.bind_evidence("b2", "cert-1", "certification", "record", "r2")
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)

        assert eng.granted_attestation_count == 1
        assert eng.active_certification_count == 1

        eng.record_assurance_finding("f1", "scope-1", "scope", impact_level=AssuranceLevel.HIGH)

        assert eng.get_attestation("att-1").status == AttestationStatus.REVOKED
        assert eng.get_certification("cert-1").status == CertificationStatus.SUSPENDED
        assert eng.granted_attestation_count == 0
        assert eng.active_certification_count == 0

    def test_scenario_5_recertification_flow(self):
        """Register cert -> schedule window -> complete window."""
        eng, _ = _make_engine()
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.bind_evidence("b1", "cert-1", "certification", "record", "r1")
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        eng.schedule_recertification(
            "w1", "cert-1",
            "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00",
        )
        completed = eng.complete_recertification("w1")
        assert completed.status == RecertificationStatus.COMPLETED
        windows = eng.windows_for_certification("cert-1")
        assert len(windows) == 1

    def test_scenario_6_snapshot_and_hash(self):
        """Full setup then snapshot and state hash."""
        eng, _ = _make_engine()
        eng.register_attestation("att-1", "t1", "ref-1", attested_by="assurance-attester-1")
        eng.bind_evidence("b1", "att-1", "attestation", "record", "r1")
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.register_certification("cert-1", "t1", "ref-1", certified_by="assurance-certifier-1")
        eng.bind_evidence("b2", "cert-1", "certification", "record", "r2")
        eng.activate_certification("cert-1", AssuranceLevel.MODERATE)
        eng.assess_assurance("a1", "t1", "ref-1", assessed_by="assurance-assessor-1")
        eng.make_assurance_decision("d1", "att-1", "attestation", level=AssuranceLevel.HIGH, decided_by="assurance-decider-1")

        snap = eng.assurance_snapshot("snap-1", "ref-1")
        assert snap.total_attestations == 1
        assert snap.granted_attestations == 1
        assert snap.total_certifications == 1
        assert snap.active_certifications == 1
        assert snap.total_evidence_bindings == 2
        assert snap.total_assessments == 1

        h = eng.state_hash()
        assert isinstance(h, str) and len(h) == 64


class TestBoundedAssuranceContracts:
    def test_terminal_attestation_message_is_bounded(self):
        eng, _ = _make_engine()
        _register_and_bind(eng)
        eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        eng.revoke_attestation("att-1", reason="policy change")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot grant attestation in current status") as exc:
            eng.grant_attestation("att-1", AssuranceLevel.HIGH)
        assert "revoked" not in str(exc.value).lower()
        assert "att-1" not in str(exc.value)

    def test_terminal_certification_message_is_bounded(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        eng.expire_certification("cert-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot activate certification in current status") as exc:
            eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        assert "expired" not in str(exc.value).lower()
        assert "cert-1" not in str(exc.value)

    def test_violation_reasons_are_bounded(self):
        eng, _ = _make_engine()
        _register_cert_and_bind(eng)
        eng.activate_certification("cert-1", AssuranceLevel.HIGH)
        old = eng.get_certification("cert-1")
        eng._certifications["cert-1"] = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.ACTIVE,
            level=old.level,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at="2020-01-01T00:00:00+00:00",
        )
        eng.schedule_recertification("w1", "cert-1", "2020-01-01T00:00:00+00:00", "2020-06-01T00:00:00+00:00")
        reasons = {v.reason for v in eng.detect_assurance_violations()}
        assert "active certification is expired" in reasons
        assert "recertification window is overdue" in reasons
        assert all("2020" not in reason for reason in reasons)
