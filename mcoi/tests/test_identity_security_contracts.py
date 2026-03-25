"""Purpose: verify identity/security contract dataclasses enforce invariants.
Governance scope: identity_security contract tests only.
Dependencies: identity_security contracts module.
Invariants:
  - Every dataclass validates required fields.
  - Enum fields reject non-enum values.
  - Frozen dataclasses reject attribute mutation.
  - metadata is frozen to MappingProxyType; to_dict() returns plain dict.
  - to_dict() preserves enum objects.
  - require_non_negative_int rejects negative, bool, float.
  - Date-only ISO strings ("2025-06-01") are accepted.
  - CredentialRecord.rotated_at is optional (empty string accepted).
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.identity_security import (
    BreakGlassRecord,
    CredentialRecord,
    CredentialStatus,
    DelegationChain,
    IdentityDescriptor,
    IdentityType,
    PrivilegeElevation,
    PrivilegeLevel,
    RecertificationRecord,
    RecertificationStatus,
    SecurityClosureReport,
    SecuritySession,
    SecuritySnapshot,
    SessionSecurityStatus,
    VaultAccessRecord,
    VaultOperation,
)

_NOW = "2026-03-19T00:00:00+00:00"
_DATE_ONLY = "2025-06-01"


# =====================================================================
# Enum coverage
# =====================================================================


class TestIdentityTypeEnum:
    def test_values(self) -> None:
        assert IdentityType.HUMAN.value == "human"
        assert IdentityType.MACHINE.value == "machine"
        assert IdentityType.SERVICE.value == "service"
        assert IdentityType.DELEGATED.value == "delegated"

    def test_member_count(self) -> None:
        assert len(IdentityType) == 4

    def test_identity(self) -> None:
        for member in IdentityType:
            assert IdentityType(member.value) is member


class TestCredentialStatusEnum:
    def test_values(self) -> None:
        assert CredentialStatus.ACTIVE.value == "active"
        assert CredentialStatus.ROTATED.value == "rotated"
        assert CredentialStatus.REVOKED.value == "revoked"
        assert CredentialStatus.EXPIRED.value == "expired"

    def test_member_count(self) -> None:
        assert len(CredentialStatus) == 4


class TestPrivilegeLevelEnum:
    def test_values(self) -> None:
        assert PrivilegeLevel.STANDARD.value == "standard"
        assert PrivilegeLevel.ELEVATED.value == "elevated"
        assert PrivilegeLevel.ADMIN.value == "admin"
        assert PrivilegeLevel.BREAK_GLASS.value == "break_glass"

    def test_member_count(self) -> None:
        assert len(PrivilegeLevel) == 4


class TestSessionSecurityStatusEnum:
    def test_values(self) -> None:
        assert SessionSecurityStatus.ACTIVE.value == "active"
        assert SessionSecurityStatus.LOCKED.value == "locked"
        assert SessionSecurityStatus.EXPIRED.value == "expired"
        assert SessionSecurityStatus.TERMINATED.value == "terminated"

    def test_member_count(self) -> None:
        assert len(SessionSecurityStatus) == 4


class TestRecertificationStatusEnum:
    def test_values(self) -> None:
        assert RecertificationStatus.PENDING.value == "pending"
        assert RecertificationStatus.APPROVED.value == "approved"
        assert RecertificationStatus.DENIED.value == "denied"
        assert RecertificationStatus.EXPIRED.value == "expired"

    def test_member_count(self) -> None:
        assert len(RecertificationStatus) == 4


class TestVaultOperationEnum:
    def test_values(self) -> None:
        assert VaultOperation.READ.value == "read"
        assert VaultOperation.WRITE.value == "write"
        assert VaultOperation.ROTATE.value == "rotate"
        assert VaultOperation.DELETE.value == "delete"
        assert VaultOperation.SEAL.value == "seal"

    def test_member_count(self) -> None:
        assert len(VaultOperation) == 5


# =====================================================================
# IdentityDescriptor
# =====================================================================


def _identity(**kw):
    defaults = dict(
        identity_id="id-1", tenant_id="t-1", display_name="Alice",
        identity_type=IdentityType.HUMAN,
        credential_status=CredentialStatus.ACTIVE,
        privilege_level=PrivilegeLevel.STANDARD, created_at=_NOW,
    )
    defaults.update(kw)
    return IdentityDescriptor(**defaults)


class TestIdentityDescriptorConstruction:
    def test_minimal(self) -> None:
        d = _identity()
        assert d.identity_id == "id-1"
        assert d.tenant_id == "t-1"
        assert d.display_name == "Alice"
        assert d.identity_type is IdentityType.HUMAN
        assert d.credential_status is CredentialStatus.ACTIVE
        assert d.privilege_level is PrivilegeLevel.STANDARD
        assert d.created_at == _NOW

    def test_with_metadata(self) -> None:
        d = _identity(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)
        assert d.metadata["k"] == "v"

    def test_date_only_accepted(self) -> None:
        d = _identity(created_at=_DATE_ONLY)
        assert d.created_at == _DATE_ONLY

    def test_all_identity_types(self) -> None:
        for it in IdentityType:
            d = _identity(identity_type=it)
            assert d.identity_type is it

    def test_all_privilege_levels(self) -> None:
        for pl in PrivilegeLevel:
            d = _identity(privilege_level=pl)
            assert d.privilege_level is pl

    def test_all_credential_statuses(self) -> None:
        for cs in CredentialStatus:
            d = _identity(credential_status=cs)
            assert d.credential_status is cs

    def test_nested_metadata_frozen(self) -> None:
        d = _identity(metadata={"nested": {"a": 1}})
        assert isinstance(d.metadata["nested"], MappingProxyType)

    def test_empty_metadata_default(self) -> None:
        d = _identity()
        assert isinstance(d.metadata, MappingProxyType)
        assert len(d.metadata) == 0


class TestIdentityDescriptorRejections:
    @pytest.mark.parametrize("field,val", [
        ("identity_id", ""), ("identity_id", "   "),
        ("tenant_id", ""), ("tenant_id", "  "),
        ("display_name", ""), ("display_name", "  "),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _identity(**{field: val})

    def test_rejects_bad_identity_type(self) -> None:
        with pytest.raises(ValueError, match="identity_type"):
            _identity(identity_type="human")

    def test_rejects_bad_credential_status(self) -> None:
        with pytest.raises(ValueError, match="credential_status"):
            _identity(credential_status="active")

    def test_rejects_bad_privilege_level(self) -> None:
        with pytest.raises(ValueError, match="privilege_level"):
            _identity(privilege_level="standard")

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _identity(created_at="not-a-date")

    def test_rejects_empty_created_at(self) -> None:
        with pytest.raises(ValueError):
            _identity(created_at="")

    @pytest.mark.parametrize("field", ["identity_id", "tenant_id", "display_name"])
    def test_rejects_non_string(self, field) -> None:
        with pytest.raises((ValueError, TypeError)):
            _identity(**{field: 123})


class TestIdentityDescriptorFrozen:
    def test_frozen(self) -> None:
        d = _identity()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "identity_id", "changed")

    def test_metadata_frozen(self) -> None:
        d = _identity(metadata={"k": "v"})
        with pytest.raises(TypeError):
            d.metadata["new"] = "val"


class TestIdentityDescriptorSerialization:
    def test_to_dict_preserves_enums(self) -> None:
        d = _identity()
        out = d.to_dict()
        assert isinstance(out["identity_type"], IdentityType)
        assert isinstance(out["credential_status"], CredentialStatus)
        assert isinstance(out["privilege_level"], PrivilegeLevel)

    def test_to_dict_metadata_plain_dict(self) -> None:
        d = _identity(metadata={"k": "v"})
        out = d.to_dict()
        assert isinstance(out["metadata"], dict)
        assert not isinstance(out["metadata"], MappingProxyType)

    def test_to_json_dict_enums_serialized(self) -> None:
        d = _identity()
        out = d.to_json_dict()
        assert out["identity_type"] == "human"
        assert out["credential_status"] == "active"
        assert out["privilege_level"] == "standard"

    def test_to_json_roundtrip(self) -> None:
        d = _identity()
        s = d.to_json()
        parsed = json.loads(s)
        assert parsed["identity_id"] == "id-1"


# =====================================================================
# CredentialRecord
# =====================================================================


def _credential(**kw):
    defaults = dict(
        credential_id="cred-1", tenant_id="t-1", identity_ref="id-1",
        status=CredentialStatus.ACTIVE, algorithm="RSA-256",
        expires_at=_NOW, created_at=_NOW,
    )
    defaults.update(kw)
    return CredentialRecord(**defaults)


class TestCredentialRecordConstruction:
    def test_minimal(self) -> None:
        c = _credential()
        assert c.credential_id == "cred-1"
        assert c.status is CredentialStatus.ACTIVE
        assert c.algorithm == "RSA-256"
        assert c.rotated_at == ""

    def test_with_rotated_at(self) -> None:
        c = _credential(rotated_at=_NOW)
        assert c.rotated_at == _NOW

    def test_rotated_at_empty_accepted(self) -> None:
        c = _credential(rotated_at="")
        assert c.rotated_at == ""

    def test_date_only_expires_at(self) -> None:
        c = _credential(expires_at=_DATE_ONLY)
        assert c.expires_at == _DATE_ONLY

    def test_date_only_created_at(self) -> None:
        c = _credential(created_at=_DATE_ONLY)
        assert c.created_at == _DATE_ONLY

    def test_all_credential_statuses(self) -> None:
        for cs in CredentialStatus:
            c = _credential(status=cs)
            assert c.status is cs

    def test_metadata_frozen(self) -> None:
        c = _credential(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)


class TestCredentialRecordRejections:
    @pytest.mark.parametrize("field,val", [
        ("credential_id", ""), ("credential_id", "   "),
        ("tenant_id", ""), ("identity_ref", ""),
        ("algorithm", ""), ("algorithm", "   "),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _credential(**{field: val})

    def test_rejects_bad_status(self) -> None:
        with pytest.raises(ValueError, match="status"):
            _credential(status="active")

    def test_rejects_bad_expires_at(self) -> None:
        with pytest.raises(ValueError):
            _credential(expires_at="not-a-date")

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _credential(created_at="not-a-date")

    def test_rejects_bad_rotated_at(self) -> None:
        with pytest.raises(ValueError):
            _credential(rotated_at="not-a-date")

    def test_rejects_empty_expires_at(self) -> None:
        with pytest.raises(ValueError):
            _credential(expires_at="")


class TestCredentialRecordFrozen:
    def test_frozen(self) -> None:
        c = _credential()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "credential_id", "changed")

    def test_frozen_status(self) -> None:
        c = _credential()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "status", CredentialStatus.REVOKED)


class TestCredentialRecordSerialization:
    def test_to_dict_preserves_enums(self) -> None:
        c = _credential()
        out = c.to_dict()
        assert isinstance(out["status"], CredentialStatus)

    def test_to_dict_metadata_plain_dict(self) -> None:
        c = _credential(metadata={"a": 1})
        out = c.to_dict()
        assert isinstance(out["metadata"], dict)
        assert not isinstance(out["metadata"], MappingProxyType)

    def test_to_json_dict(self) -> None:
        c = _credential()
        out = c.to_json_dict()
        assert out["status"] == "active"

    def test_to_json_roundtrip(self) -> None:
        c = _credential()
        s = c.to_json()
        parsed = json.loads(s)
        assert parsed["credential_id"] == "cred-1"


# =====================================================================
# DelegationChain
# =====================================================================


def _chain(**kw):
    defaults = dict(
        chain_id="ch-1", tenant_id="t-1", delegator_ref="id-1",
        delegate_ref="id-2", scope_ref="scope-1", depth=0, created_at=_NOW,
    )
    defaults.update(kw)
    return DelegationChain(**defaults)


class TestDelegationChainConstruction:
    def test_minimal(self) -> None:
        c = _chain()
        assert c.chain_id == "ch-1"
        assert c.depth == 0

    def test_with_depth(self) -> None:
        c = _chain(depth=3)
        assert c.depth == 3

    def test_date_only(self) -> None:
        c = _chain(created_at=_DATE_ONLY)
        assert c.created_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        c = _chain(metadata={"x": [1, 2]})
        assert isinstance(c.metadata, MappingProxyType)

    def test_zero_depth(self) -> None:
        c = _chain(depth=0)
        assert c.depth == 0

    def test_large_depth(self) -> None:
        c = _chain(depth=999)
        assert c.depth == 999


class TestDelegationChainRejections:
    @pytest.mark.parametrize("field,val", [
        ("chain_id", ""), ("tenant_id", ""),
        ("delegator_ref", ""), ("delegate_ref", ""),
        ("scope_ref", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _chain(**{field: val})

    def test_rejects_negative_depth(self) -> None:
        with pytest.raises(ValueError, match="depth"):
            _chain(depth=-1)

    def test_rejects_bool_depth(self) -> None:
        with pytest.raises(ValueError, match="depth"):
            _chain(depth=True)

    def test_rejects_float_depth(self) -> None:
        with pytest.raises(ValueError, match="depth"):
            _chain(depth=1.5)

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _chain(created_at="nope")


class TestDelegationChainFrozen:
    def test_frozen(self) -> None:
        c = _chain()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "chain_id", "changed")

    def test_frozen_depth(self) -> None:
        c = _chain()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "depth", 999)


class TestDelegationChainSerialization:
    def test_to_dict(self) -> None:
        c = _chain()
        out = c.to_dict()
        assert out["chain_id"] == "ch-1"
        assert out["depth"] == 0

    def test_to_dict_metadata_plain(self) -> None:
        c = _chain(metadata={"k": "v"})
        out = c.to_dict()
        assert isinstance(out["metadata"], dict)

    def test_to_json_roundtrip(self) -> None:
        c = _chain()
        parsed = json.loads(c.to_json())
        assert parsed["depth"] == 0


# =====================================================================
# PrivilegeElevation
# =====================================================================


def _elevation(**kw):
    defaults = dict(
        elevation_id="elev-1", tenant_id="t-1", identity_ref="id-1",
        from_level=PrivilegeLevel.STANDARD, to_level=PrivilegeLevel.ELEVATED,
        reason="testing", approved_by="admin-1", created_at=_NOW,
    )
    defaults.update(kw)
    return PrivilegeElevation(**defaults)


class TestPrivilegeElevationConstruction:
    def test_minimal(self) -> None:
        e = _elevation()
        assert e.elevation_id == "elev-1"
        assert e.from_level is PrivilegeLevel.STANDARD
        assert e.to_level is PrivilegeLevel.ELEVATED

    def test_all_from_levels(self) -> None:
        for pl in PrivilegeLevel:
            e = _elevation(from_level=pl)
            assert e.from_level is pl

    def test_all_to_levels(self) -> None:
        for pl in PrivilegeLevel:
            e = _elevation(to_level=pl)
            assert e.to_level is pl

    def test_date_only(self) -> None:
        e = _elevation(created_at=_DATE_ONLY)
        assert e.created_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        e = _elevation(metadata={"flag": True})
        assert isinstance(e.metadata, MappingProxyType)


class TestPrivilegeElevationRejections:
    @pytest.mark.parametrize("field,val", [
        ("elevation_id", ""), ("tenant_id", ""),
        ("identity_ref", ""), ("reason", ""),
        ("approved_by", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _elevation(**{field: val})

    def test_rejects_bad_from_level(self) -> None:
        with pytest.raises(ValueError, match="from_level"):
            _elevation(from_level="standard")

    def test_rejects_bad_to_level(self) -> None:
        with pytest.raises(ValueError, match="to_level"):
            _elevation(to_level="elevated")

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _elevation(created_at="nope")


class TestPrivilegeElevationFrozen:
    def test_frozen(self) -> None:
        e = _elevation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "elevation_id", "changed")

    def test_frozen_reason(self) -> None:
        e = _elevation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(e, "reason", "new reason")


class TestPrivilegeElevationSerialization:
    def test_to_dict_preserves_enums(self) -> None:
        e = _elevation()
        out = e.to_dict()
        assert isinstance(out["from_level"], PrivilegeLevel)
        assert isinstance(out["to_level"], PrivilegeLevel)

    def test_to_json_dict_serializes_enums(self) -> None:
        e = _elevation()
        out = e.to_json_dict()
        assert out["from_level"] == "standard"
        assert out["to_level"] == "elevated"

    def test_to_json_roundtrip(self) -> None:
        e = _elevation()
        parsed = json.loads(e.to_json())
        assert parsed["reason"] == "testing"


# =====================================================================
# SecuritySession
# =====================================================================


def _session(**kw):
    defaults = dict(
        session_id="ses-1", tenant_id="t-1", identity_ref="id-1",
        status=SessionSecurityStatus.ACTIVE, ip_ref="127.0.0.1", created_at=_NOW,
    )
    defaults.update(kw)
    return SecuritySession(**defaults)


class TestSecuritySessionConstruction:
    def test_minimal(self) -> None:
        s = _session()
        assert s.session_id == "ses-1"
        assert s.status is SessionSecurityStatus.ACTIVE
        assert s.ip_ref == "127.0.0.1"

    def test_all_statuses(self) -> None:
        for st in SessionSecurityStatus:
            s = _session(status=st)
            assert s.status is st

    def test_date_only(self) -> None:
        s = _session(created_at=_DATE_ONLY)
        assert s.created_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        s = _session(metadata={"ua": "chrome"})
        assert isinstance(s.metadata, MappingProxyType)


class TestSecuritySessionRejections:
    @pytest.mark.parametrize("field,val", [
        ("session_id", ""), ("tenant_id", ""),
        ("identity_ref", ""), ("ip_ref", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _session(**{field: val})

    def test_rejects_bad_status(self) -> None:
        with pytest.raises(ValueError, match="status"):
            _session(status="active")

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _session(created_at="nope")


class TestSecuritySessionFrozen:
    def test_frozen(self) -> None:
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "session_id", "changed")

    def test_frozen_status(self) -> None:
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "status", SessionSecurityStatus.LOCKED)


class TestSecuritySessionSerialization:
    def test_to_dict_preserves_enums(self) -> None:
        s = _session()
        out = s.to_dict()
        assert isinstance(out["status"], SessionSecurityStatus)

    def test_to_json_dict(self) -> None:
        s = _session()
        out = s.to_json_dict()
        assert out["status"] == "active"

    def test_to_json_roundtrip(self) -> None:
        s = _session()
        parsed = json.loads(s.to_json())
        assert parsed["session_id"] == "ses-1"


# =====================================================================
# VaultAccessRecord
# =====================================================================


def _vault(**kw):
    defaults = dict(
        access_id="va-1", tenant_id="t-1", identity_ref="id-1",
        secret_ref="sec-1", operation=VaultOperation.READ, created_at=_NOW,
    )
    defaults.update(kw)
    return VaultAccessRecord(**defaults)


class TestVaultAccessRecordConstruction:
    def test_minimal(self) -> None:
        v = _vault()
        assert v.access_id == "va-1"
        assert v.operation is VaultOperation.READ

    def test_all_operations(self) -> None:
        for op in VaultOperation:
            v = _vault(operation=op)
            assert v.operation is op

    def test_date_only(self) -> None:
        v = _vault(created_at=_DATE_ONLY)
        assert v.created_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        v = _vault(metadata={"policy": "strict"})
        assert isinstance(v.metadata, MappingProxyType)


class TestVaultAccessRecordRejections:
    @pytest.mark.parametrize("field,val", [
        ("access_id", ""), ("tenant_id", ""),
        ("identity_ref", ""), ("secret_ref", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _vault(**{field: val})

    def test_rejects_bad_operation(self) -> None:
        with pytest.raises(ValueError, match="operation"):
            _vault(operation="read")

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _vault(created_at="nope")


class TestVaultAccessRecordFrozen:
    def test_frozen(self) -> None:
        v = _vault()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "access_id", "changed")


class TestVaultAccessRecordSerialization:
    def test_to_dict_preserves_enums(self) -> None:
        v = _vault()
        out = v.to_dict()
        assert isinstance(out["operation"], VaultOperation)

    def test_to_json_dict(self) -> None:
        v = _vault()
        out = v.to_json_dict()
        assert out["operation"] == "read"

    def test_to_json_roundtrip(self) -> None:
        v = _vault()
        parsed = json.loads(v.to_json())
        assert parsed["secret_ref"] == "sec-1"


# =====================================================================
# RecertificationRecord
# =====================================================================


def _recert(**kw):
    defaults = dict(
        recert_id="rc-1", tenant_id="t-1", identity_ref="id-1",
        status=RecertificationStatus.PENDING, reviewer_ref="rev-1",
        decided_at=_NOW,
    )
    defaults.update(kw)
    return RecertificationRecord(**defaults)


class TestRecertificationRecordConstruction:
    def test_minimal(self) -> None:
        r = _recert()
        assert r.recert_id == "rc-1"
        assert r.status is RecertificationStatus.PENDING

    def test_all_statuses(self) -> None:
        for st in RecertificationStatus:
            r = _recert(status=st)
            assert r.status is st

    def test_date_only(self) -> None:
        r = _recert(decided_at=_DATE_ONLY)
        assert r.decided_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        r = _recert(metadata={"note": "ok"})
        assert isinstance(r.metadata, MappingProxyType)


class TestRecertificationRecordRejections:
    @pytest.mark.parametrize("field,val", [
        ("recert_id", ""), ("tenant_id", ""),
        ("identity_ref", ""), ("reviewer_ref", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _recert(**{field: val})

    def test_rejects_bad_status(self) -> None:
        with pytest.raises(ValueError, match="status"):
            _recert(status="pending")

    def test_rejects_bad_decided_at(self) -> None:
        with pytest.raises(ValueError):
            _recert(decided_at="nope")


class TestRecertificationRecordFrozen:
    def test_frozen(self) -> None:
        r = _recert()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "recert_id", "changed")


class TestRecertificationRecordSerialization:
    def test_to_dict_preserves_enums(self) -> None:
        r = _recert()
        out = r.to_dict()
        assert isinstance(out["status"], RecertificationStatus)

    def test_to_json_dict(self) -> None:
        r = _recert()
        out = r.to_json_dict()
        assert out["status"] == "pending"

    def test_to_json_roundtrip(self) -> None:
        r = _recert()
        parsed = json.loads(r.to_json())
        assert parsed["reviewer_ref"] == "rev-1"


# =====================================================================
# BreakGlassRecord
# =====================================================================


def _breakglass(**kw):
    defaults = dict(
        break_id="bg-1", tenant_id="t-1", identity_ref="id-1",
        reason="emergency", authorized_by="admin-1", created_at=_NOW,
    )
    defaults.update(kw)
    return BreakGlassRecord(**defaults)


class TestBreakGlassRecordConstruction:
    def test_minimal(self) -> None:
        b = _breakglass()
        assert b.break_id == "bg-1"
        assert b.reason == "emergency"
        assert b.authorized_by == "admin-1"

    def test_date_only(self) -> None:
        b = _breakglass(created_at=_DATE_ONLY)
        assert b.created_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        b = _breakglass(metadata={"severity": "critical"})
        assert isinstance(b.metadata, MappingProxyType)


class TestBreakGlassRecordRejections:
    @pytest.mark.parametrize("field,val", [
        ("break_id", ""), ("tenant_id", ""),
        ("identity_ref", ""), ("reason", ""),
        ("authorized_by", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _breakglass(**{field: val})

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _breakglass(created_at="nope")


class TestBreakGlassRecordFrozen:
    def test_frozen(self) -> None:
        b = _breakglass()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(b, "break_id", "changed")

    def test_frozen_reason(self) -> None:
        b = _breakglass()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(b, "reason", "new")


class TestBreakGlassRecordSerialization:
    def test_to_dict(self) -> None:
        b = _breakglass()
        out = b.to_dict()
        assert out["break_id"] == "bg-1"

    def test_to_dict_metadata_plain(self) -> None:
        b = _breakglass(metadata={"k": "v"})
        out = b.to_dict()
        assert isinstance(out["metadata"], dict)

    def test_to_json_roundtrip(self) -> None:
        b = _breakglass()
        parsed = json.loads(b.to_json())
        assert parsed["authorized_by"] == "admin-1"


# =====================================================================
# SecuritySnapshot
# =====================================================================


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_identities=5, total_credentials=3, total_sessions=2,
        total_elevations=1, total_vault_accesses=4, total_violations=0,
        captured_at=_NOW,
    )
    defaults.update(kw)
    return SecuritySnapshot(**defaults)


class TestSecuritySnapshotConstruction:
    def test_minimal(self) -> None:
        s = _snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.total_identities == 5
        assert s.total_credentials == 3
        assert s.total_sessions == 2
        assert s.total_elevations == 1
        assert s.total_vault_accesses == 4
        assert s.total_violations == 0

    def test_zero_counts(self) -> None:
        s = _snapshot(
            total_identities=0, total_credentials=0, total_sessions=0,
            total_elevations=0, total_vault_accesses=0, total_violations=0,
        )
        assert s.total_identities == 0

    def test_date_only(self) -> None:
        s = _snapshot(captured_at=_DATE_ONLY)
        assert s.captured_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        s = _snapshot(metadata={"region": "us-east"})
        assert isinstance(s.metadata, MappingProxyType)


class TestSecuritySnapshotRejections:
    @pytest.mark.parametrize("field,val", [
        ("snapshot_id", ""), ("tenant_id", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: val})

    @pytest.mark.parametrize("field", [
        "total_identities", "total_credentials", "total_sessions",
        "total_elevations", "total_vault_accesses", "total_violations",
    ])
    def test_rejects_negative_int(self, field) -> None:
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_identities", "total_credentials", "total_sessions",
        "total_elevations", "total_vault_accesses", "total_violations",
    ])
    def test_rejects_bool(self, field) -> None:
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_identities", "total_credentials", "total_sessions",
        "total_elevations", "total_vault_accesses", "total_violations",
    ])
    def test_rejects_float(self, field) -> None:
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: 1.5})

    def test_rejects_bad_captured_at(self) -> None:
        with pytest.raises(ValueError):
            _snapshot(captured_at="nope")


class TestSecuritySnapshotFrozen:
    def test_frozen(self) -> None:
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "changed")

    def test_frozen_count(self) -> None:
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "total_identities", 99)


class TestSecuritySnapshotSerialization:
    def test_to_dict(self) -> None:
        s = _snapshot()
        out = s.to_dict()
        assert out["total_identities"] == 5
        assert isinstance(out["metadata"], dict)

    def test_to_json_roundtrip(self) -> None:
        s = _snapshot()
        parsed = json.loads(s.to_json())
        assert parsed["total_violations"] == 0


# =====================================================================
# SecurityClosureReport
# =====================================================================


def _closure(**kw):
    defaults = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_identities=10, total_credentials=5,
        total_sessions=3, total_violations=1, created_at=_NOW,
    )
    defaults.update(kw)
    return SecurityClosureReport(**defaults)


class TestSecurityClosureReportConstruction:
    def test_minimal(self) -> None:
        r = _closure()
        assert r.report_id == "rpt-1"
        assert r.total_identities == 10
        assert r.total_violations == 1

    def test_zero_counts(self) -> None:
        r = _closure(
            total_identities=0, total_credentials=0,
            total_sessions=0, total_violations=0,
        )
        assert r.total_identities == 0

    def test_date_only(self) -> None:
        r = _closure(created_at=_DATE_ONLY)
        assert r.created_at == _DATE_ONLY

    def test_metadata_frozen(self) -> None:
        r = _closure(metadata={"final": True})
        assert isinstance(r.metadata, MappingProxyType)


class TestSecurityClosureReportRejections:
    @pytest.mark.parametrize("field,val", [
        ("report_id", ""), ("tenant_id", ""),
    ])
    def test_rejects_empty_text(self, field, val) -> None:
        with pytest.raises(ValueError, match=field):
            _closure(**{field: val})

    @pytest.mark.parametrize("field", [
        "total_identities", "total_credentials",
        "total_sessions", "total_violations",
    ])
    def test_rejects_negative_int(self, field) -> None:
        with pytest.raises(ValueError, match=field):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_identities", "total_credentials",
        "total_sessions", "total_violations",
    ])
    def test_rejects_bool(self, field) -> None:
        with pytest.raises(ValueError, match=field):
            _closure(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_identities", "total_credentials",
        "total_sessions", "total_violations",
    ])
    def test_rejects_float(self, field) -> None:
        with pytest.raises(ValueError, match=field):
            _closure(**{field: 1.5})

    def test_rejects_bad_created_at(self) -> None:
        with pytest.raises(ValueError):
            _closure(created_at="nope")


class TestSecurityClosureReportFrozen:
    def test_frozen(self) -> None:
        r = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "changed")

    def test_frozen_count(self) -> None:
        r = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "total_violations", 99)


class TestSecurityClosureReportSerialization:
    def test_to_dict(self) -> None:
        r = _closure()
        out = r.to_dict()
        assert out["total_identities"] == 10
        assert isinstance(out["metadata"], dict)

    def test_to_json_roundtrip(self) -> None:
        r = _closure()
        parsed = json.loads(r.to_json())
        assert parsed["total_violations"] == 1


# =====================================================================
# Cross-cutting: parametric field-name x dataclass negative tests
# =====================================================================


class TestCrossCuttingWhitespace:
    """Whitespace-only strings rejected for all text fields."""

    def test_identity_whitespace_identity_id(self) -> None:
        with pytest.raises(ValueError):
            _identity(identity_id="   ")

    def test_credential_whitespace_credential_id(self) -> None:
        with pytest.raises(ValueError):
            _credential(credential_id="   ")

    def test_chain_whitespace_chain_id(self) -> None:
        with pytest.raises(ValueError):
            _chain(chain_id="   ")

    def test_elevation_whitespace_elevation_id(self) -> None:
        with pytest.raises(ValueError):
            _elevation(elevation_id="   ")

    def test_session_whitespace_session_id(self) -> None:
        with pytest.raises(ValueError):
            _session(session_id="   ")

    def test_vault_whitespace_access_id(self) -> None:
        with pytest.raises(ValueError):
            _vault(access_id="   ")

    def test_recert_whitespace_recert_id(self) -> None:
        with pytest.raises(ValueError):
            _recert(recert_id="   ")

    def test_breakglass_whitespace_break_id(self) -> None:
        with pytest.raises(ValueError):
            _breakglass(break_id="   ")

    def test_snapshot_whitespace_snapshot_id(self) -> None:
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="   ")

    def test_closure_whitespace_report_id(self) -> None:
        with pytest.raises(ValueError):
            _closure(report_id="   ")


class TestCrossCuttingMetadata:
    """Metadata is always MappingProxyType; to_dict returns plain dict."""

    @pytest.mark.parametrize("factory", [
        _identity, _credential, _chain, _elevation, _session,
        _vault, _recert, _breakglass, _snapshot, _closure,
    ])
    def test_metadata_is_mapping_proxy(self, factory) -> None:
        obj = factory(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    @pytest.mark.parametrize("factory", [
        _identity, _credential, _chain, _elevation, _session,
        _vault, _recert, _breakglass, _snapshot, _closure,
    ])
    def test_to_dict_metadata_plain(self, factory) -> None:
        obj = factory(metadata={"k": "v"})
        out = obj.to_dict()
        assert isinstance(out["metadata"], dict)
        assert not isinstance(out["metadata"], MappingProxyType)

    @pytest.mark.parametrize("factory", [
        _identity, _credential, _chain, _elevation, _session,
        _vault, _recert, _breakglass, _snapshot, _closure,
    ])
    def test_metadata_mutation_rejected(self, factory) -> None:
        obj = factory(metadata={"k": "v"})
        with pytest.raises(TypeError):
            obj.metadata["new"] = "val"


class TestCrossCuttingFrozenness:
    """All dataclasses reject attribute mutation via setattr."""

    @pytest.mark.parametrize("factory,field", [
        (_identity, "identity_id"), (_credential, "credential_id"),
        (_chain, "chain_id"), (_elevation, "elevation_id"),
        (_session, "session_id"), (_vault, "access_id"),
        (_recert, "recert_id"), (_breakglass, "break_id"),
        (_snapshot, "snapshot_id"), (_closure, "report_id"),
    ])
    def test_frozen_primary_key(self, factory, field) -> None:
        obj = factory()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(obj, field, "x")


class TestCrossCuttingDateOnly:
    """Date-only strings accepted for datetime fields."""

    def test_identity_date_only(self) -> None:
        _identity(created_at=_DATE_ONLY)

    def test_credential_expires_date_only(self) -> None:
        _credential(expires_at=_DATE_ONLY)

    def test_credential_created_date_only(self) -> None:
        _credential(created_at=_DATE_ONLY)

    def test_chain_date_only(self) -> None:
        _chain(created_at=_DATE_ONLY)

    def test_elevation_date_only(self) -> None:
        _elevation(created_at=_DATE_ONLY)

    def test_session_date_only(self) -> None:
        _session(created_at=_DATE_ONLY)

    def test_vault_date_only(self) -> None:
        _vault(created_at=_DATE_ONLY)

    def test_recert_date_only(self) -> None:
        _recert(decided_at=_DATE_ONLY)

    def test_breakglass_date_only(self) -> None:
        _breakglass(created_at=_DATE_ONLY)

    def test_snapshot_date_only(self) -> None:
        _snapshot(captured_at=_DATE_ONLY)

    def test_closure_date_only(self) -> None:
        _closure(created_at=_DATE_ONLY)


class TestCrossCuttingISOVariants:
    """Various ISO-8601 formats accepted."""

    @pytest.mark.parametrize("ts", [
        "2025-06-01",
        "2025-06-01T10:00:00",
        "2025-06-01T10:00:00+00:00",
        "2025-06-01T10:00:00Z",
        "2025-06-01T10:00:00.123456+00:00",
    ])
    def test_identity_iso_variants(self, ts) -> None:
        d = _identity(created_at=ts)
        assert d.created_at == ts


class TestCrossCuttingToJson:
    """to_json() is valid JSON for all dataclasses."""

    @pytest.mark.parametrize("factory", [
        _identity, _credential, _chain, _elevation, _session,
        _vault, _recert, _breakglass, _snapshot, _closure,
    ])
    def test_to_json_valid(self, factory) -> None:
        obj = factory()
        s = obj.to_json()
        parsed = json.loads(s)
        assert isinstance(parsed, dict)


class TestCrossCuttingEquality:
    """Frozen dataclass equality by value."""

    @pytest.mark.parametrize("factory", [
        _identity, _credential, _chain, _elevation, _session,
        _vault, _recert, _breakglass, _snapshot, _closure,
    ])
    def test_equality(self, factory) -> None:
        a = factory()
        b = factory()
        assert a == b

    @pytest.mark.parametrize("factory", [
        _identity, _credential, _chain, _elevation, _session,
        _vault, _recert, _breakglass, _snapshot, _closure,
    ])
    def test_equality_consistent(self, factory) -> None:
        a = factory()
        b = factory()
        assert a == b
