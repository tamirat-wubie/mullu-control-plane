"""Purpose: comprehensive tests for the PolicyEnforcementEngine.
Governance scope: runtime-core policy enforcement tests only.
Dependencies: policy_enforcement engine, event_spine engine, policy_enforcement contracts.
Invariants:
  - Enforcement is fail-closed: default decision is DENY.
  - Only ACTIVE sessions may execute actions.
  - Step-up requires explicit approval.
  - Revocations are permanent.
  - Constraints narrow permissions per session.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.policy_enforcement import PolicyEnforcementEngine
from mcoi_runtime.contracts.policy_enforcement import (
    SessionStatus,
    SessionKind,
    PrivilegeLevel,
    EnforcementDecision,
    RevocationReason,
    StepUpStatus,
    SessionRecord,
    SessionConstraint,
    PrivilegeElevationRequest,
    PrivilegeElevationDecision,
    EnforcementEvent,
    RevocationRecord,
    SessionSnapshot,
    EnforcementAuditRecord,
    PolicySessionBinding,
    SessionClosureReport,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(spine: EventSpineEngine) -> PolicyEnforcementEngine:
    return PolicyEnforcementEngine(spine)


@pytest.fixture()
def active_session(engine: PolicyEnforcementEngine) -> SessionRecord:
    """Create and return a single active session for convenience."""
    return engine.open_session("s1", "id1")


# ===================================================================
# Constructor tests
# ===================================================================


class TestConstructor:
    def test_accepts_event_spine(self, spine: EventSpineEngine) -> None:
        eng = PolicyEnforcementEngine(spine)
        assert eng.session_count == 0

    def test_rejects_none(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicyEnforcementEngine(None)  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicyEnforcementEngine("not-an-engine")  # type: ignore[arg-type]

    def test_rejects_dict(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicyEnforcementEngine({})  # type: ignore[arg-type]


# ===================================================================
# Property tests (fresh engine)
# ===================================================================


class TestInitialProperties:
    def test_session_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.session_count == 0

    def test_active_session_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.active_session_count == 0

    def test_constraint_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.constraint_count == 0

    def test_step_up_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.step_up_count == 0

    def test_enforcement_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.enforcement_count == 0

    def test_revocation_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.revocation_count == 0

    def test_binding_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.binding_count == 0

    def test_audit_count_zero(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.audit_count == 0


# ===================================================================
# open_session
# ===================================================================


class TestOpenSession:
    def test_returns_session_record(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert isinstance(rec, SessionRecord)

    def test_status_is_active(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert rec.status == SessionStatus.ACTIVE

    def test_session_id_matches(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert rec.session_id == "s1"

    def test_identity_id_matches(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert rec.identity_id == "id1"

    def test_default_kind_interactive(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert rec.kind == SessionKind.INTERACTIVE

    def test_default_privilege_standard(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert rec.privilege_level == PrivilegeLevel.STANDARD

    def test_custom_kind(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", kind=SessionKind.SERVICE)
        assert rec.kind == SessionKind.SERVICE

    def test_custom_privilege(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.ADMIN)
        assert rec.privilege_level == PrivilegeLevel.ADMIN

    def test_custom_scope_ref_id(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", scope_ref_id="scope-1")
        assert rec.scope_ref_id == "scope-1"

    def test_custom_environment_id(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", environment_id="env-1")
        assert rec.environment_id == "env-1"

    def test_custom_connector_id(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", connector_id="conn-1")
        assert rec.connector_id == "conn-1"

    def test_custom_campaign_id(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", campaign_id="camp-1")
        assert rec.campaign_id == "camp-1"

    def test_opened_at_set(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1")
        assert rec.opened_at != ""

    def test_increments_session_count(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        assert engine.session_count == 1

    def test_increments_active_session_count(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        assert engine.active_session_count == 1

    def test_duplicate_raises(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.open_session("s1", "id2")

    def test_multiple_sessions(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.open_session("s3", "id2")
        assert engine.session_count == 3

    def test_session_kind_campaign(self, engine: PolicyEnforcementEngine) -> None:
        rec = engine.open_session("s1", "id1", kind=SessionKind.CAMPAIGN)
        assert rec.kind == SessionKind.CAMPAIGN


# ===================================================================
# get_session
# ===================================================================


class TestGetSession:
    def test_returns_existing(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        rec = engine.get_session("s1")
        assert rec.session_id == "s1"

    def test_unknown_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_session("no-such")


# ===================================================================
# sessions_for_identity
# ===================================================================


class TestSessionsForIdentity:
    def test_returns_empty_tuple(self, engine: PolicyEnforcementEngine) -> None:
        result = engine.sessions_for_identity("id-none")
        assert result == ()

    def test_returns_matching(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.open_session("s3", "id2")
        result = engine.sessions_for_identity("id1")
        assert len(result) == 2
        assert all(r.identity_id == "id1" for r in result)



# ===================================================================
# active_sessions
# ===================================================================


class TestActiveSessions:
    def test_empty_when_no_sessions(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.active_sessions() == ()

    def test_returns_only_active(self, engine: PolicyEnforcementEngine) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.suspend_session("s2")
        result = engine.active_sessions()
        assert len(result) == 1
        assert result[0].session_id == "s1"


# ===================================================================
# add_constraint
# ===================================================================


class TestAddConstraint:
    def test_returns_session_constraint(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        c = engine.add_constraint("c1", "s1")
        assert isinstance(c, SessionConstraint)

    def test_constraint_id_matches(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        c = engine.add_constraint("c1", "s1")
        assert c.constraint_id == "c1"

    def test_session_id_matches(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        c = engine.add_constraint("c1", "s1")
        assert c.session_id == "s1"

    def test_default_max_privilege(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        c = engine.add_constraint("c1", "s1")
        assert c.max_privilege == PrivilegeLevel.STANDARD

    def test_custom_fields(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        c = engine.add_constraint(
            "c1", "s1",
            resource_type="file",
            action="read",
            environment_id="staging",
            connector_id="conn-1",
            max_privilege=PrivilegeLevel.ELEVATED,
        )
        assert c.resource_type == "file"
        assert c.action == "read"
        assert c.environment_id == "staging"
        assert c.connector_id == "conn-1"
        assert c.max_privilege == PrivilegeLevel.ELEVATED

    def test_increments_constraint_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1")
        assert engine.constraint_count == 1

    def test_duplicate_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.add_constraint("c1", "s1")

    def test_unknown_session_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.add_constraint("c1", "no-such")

    def test_created_at_set(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        c = engine.add_constraint("c1", "s1")
        assert c.created_at != ""


# ===================================================================
# constraints_for_session
# ===================================================================


class TestConstraintsForSession:
    def test_empty(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.constraints_for_session("s1") == ()

    def test_returns_matching(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1")
        engine.add_constraint("c2", "s1")
        result = engine.constraints_for_session("s1")
        assert len(result) == 2



# ===================================================================
# bind_session
# ===================================================================


class TestBindSession:
    def test_returns_binding(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        b = engine.bind_session("b1", "s1", "file", "file-123")
        assert isinstance(b, PolicySessionBinding)

    def test_fields_match(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        b = engine.bind_session("b1", "s1", "file", "file-123")
        assert b.binding_id == "b1"
        assert b.session_id == "s1"
        assert b.resource_type == "file"
        assert b.resource_id == "file-123"

    def test_bound_at_set(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        b = engine.bind_session("b1", "s1", "file", "file-123")
        assert b.bound_at != ""

    def test_increments_binding_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.bind_session("b1", "s1", "file", "file-123")
        assert engine.binding_count == 1

    def test_duplicate_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.bind_session("b1", "s1", "file", "f1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.bind_session("b1", "s1", "file", "f2")

    def test_unknown_session_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.bind_session("b1", "no-such", "file", "f1")


# ===================================================================
# bindings_for_session
# ===================================================================


class TestBindingsForSession:
    def test_empty(self, engine: PolicyEnforcementEngine) -> None:
        assert engine.bindings_for_session("s1") == ()

    def test_returns_matching(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.bind_session("b1", "s1", "file", "f1")
        engine.bind_session("b2", "s1", "db", "db1")
        result = engine.bindings_for_session("s1")
        assert len(result) == 2


# ===================================================================
# evaluate_session_action — basic decisions
# ===================================================================


class TestEvaluateSessionAction:
    def test_unknown_session_denied(self, engine: PolicyEnforcementEngine) -> None:
        ev = engine.evaluate_session_action("no-such", "file", "read")
        assert ev.decision == EnforcementDecision.DENIED

    def test_active_session_allowed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_returns_enforcement_event(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert isinstance(ev, EnforcementEvent)

    def test_event_fields(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action(
            "s1", "file", "read", environment_id="prod", connector_id="c1"
        )
        assert ev.session_id == "s1"
        assert ev.resource_type == "file"
        assert ev.action == "read"
        assert ev.environment_id == "prod"
        assert ev.connector_id == "c1"

    def test_identity_id_on_event(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.identity_id == "id1"

    def test_unknown_session_identity_unknown(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        ev = engine.evaluate_session_action("no-such", "file", "read")
        assert ev.identity_id == "unknown"

    def test_increments_enforcement_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.evaluate_session_action("s1", "file", "read")
        assert engine.enforcement_count == 1

    def test_increments_audit_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.evaluate_session_action("s1", "file", "read")
        assert engine.audit_count == 1


# ===================================================================
# evaluate_session_action — non-active session status mapping
# ===================================================================


class TestEvaluateNonActiveSession:
    def test_suspended_returns_suspended(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.suspend_session("s1")
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.SUSPENDED

    def test_revoked_returns_revoked(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.REVOKED

    def test_expired_returns_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.expire_session("s1")
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.DENIED

    def test_closed_returns_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.close_session("s1")
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.DENIED


# ===================================================================
# evaluate_session_action — privilege checks
# ===================================================================


class TestEvaluatePrivilege:
    def test_standard_session_standard_action_allowed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action(
            "s1", "file", "read", required_privilege=PrivilegeLevel.STANDARD
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_standard_session_elevated_action_step_up(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action(
            "s1", "file", "write", required_privilege=PrivilegeLevel.ELEVATED
        )
        assert ev.decision == EnforcementDecision.STEP_UP_REQUIRED

    def test_standard_session_admin_action_step_up(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        ev = engine.evaluate_session_action(
            "s1", "file", "delete", required_privilege=PrivilegeLevel.ADMIN
        )
        assert ev.decision == EnforcementDecision.STEP_UP_REQUIRED

    def test_elevated_session_standard_allowed(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.ELEVATED)
        ev = engine.evaluate_session_action(
            "s1", "file", "read", required_privilege=PrivilegeLevel.STANDARD
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_elevated_session_elevated_allowed(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.ELEVATED)
        ev = engine.evaluate_session_action(
            "s1", "file", "write", required_privilege=PrivilegeLevel.ELEVATED
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_elevated_session_admin_step_up(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.ELEVATED)
        ev = engine.evaluate_session_action(
            "s1", "file", "admin-op", required_privilege=PrivilegeLevel.ADMIN
        )
        assert ev.decision == EnforcementDecision.STEP_UP_REQUIRED

    def test_admin_session_system_step_up(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.ADMIN)
        ev = engine.evaluate_session_action(
            "s1", "file", "sys-op", required_privilege=PrivilegeLevel.SYSTEM
        )
        assert ev.decision == EnforcementDecision.STEP_UP_REQUIRED

    def test_emergency_session_allows_all(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.EMERGENCY)
        for level in PrivilegeLevel:
            ev = engine.evaluate_session_action(
                "s1", "file", "op", required_privilege=level
            )
            assert ev.decision == EnforcementDecision.ALLOWED


# ===================================================================
# evaluate_session_action — constraint checks
# ===================================================================


class TestEvaluateConstraints:
    def test_environment_mismatch_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", environment_id="staging")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", environment_id="prod"
        )
        assert ev.decision == EnforcementDecision.DENIED

    def test_environment_match_allowed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", environment_id="staging")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", environment_id="staging"
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_connector_mismatch_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", connector_id="conn-a")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", connector_id="conn-b"
        )
        assert ev.decision == EnforcementDecision.DENIED

    def test_connector_match_allowed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", connector_id="conn-a")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", connector_id="conn-a"
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_resource_type_mismatch_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", resource_type="database")
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.DENIED

    def test_resource_type_match_allowed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", resource_type="file")
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_action_mismatch_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", action="read")
        ev = engine.evaluate_session_action("s1", "file", "write")
        assert ev.decision == EnforcementDecision.DENIED

    def test_action_match_allowed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", action="read")
        ev = engine.evaluate_session_action("s1", "file", "read")
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_max_privilege_cap_step_up(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1", privilege_level=PrivilegeLevel.ADMIN)
        engine.add_constraint("c1", "s1", max_privilege=PrivilegeLevel.STANDARD)
        ev = engine.evaluate_session_action(
            "s1", "file", "op", required_privilege=PrivilegeLevel.ELEVATED
        )
        assert ev.decision == EnforcementDecision.STEP_UP_REQUIRED

    def test_constraint_environment_empty_no_block(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        """Constraint with empty environment_id does not block any environment."""
        engine.add_constraint("c1", "s1", environment_id="")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", environment_id="prod"
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_action_empty_environment_no_block(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        """Action with empty environment_id does not trigger env constraint."""
        engine.add_constraint("c1", "s1", environment_id="staging")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", environment_id=""
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_multiple_constraints_first_blocks(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.add_constraint("c1", "s1", environment_id="staging")
        engine.add_constraint("c2", "s1", resource_type="file")
        ev = engine.evaluate_session_action(
            "s1", "file", "read", environment_id="prod"
        )
        assert ev.decision == EnforcementDecision.DENIED


# ===================================================================
# request_step_up
# ===================================================================


class TestRequestStepUp:
    def test_returns_request(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        req = engine.request_step_up("r1", "s1", "id1")
        assert isinstance(req, PrivilegeElevationRequest)

    def test_status_pending(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        req = engine.request_step_up("r1", "s1", "id1")
        assert req.status == StepUpStatus.PENDING

    def test_fields_match(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        req = engine.request_step_up(
            "r1", "s1", "id1",
            requested_level=PrivilegeLevel.ADMIN,
            reason="need admin",
            resource_type="db",
            action="drop",
        )
        assert req.request_id == "r1"
        assert req.session_id == "s1"
        assert req.identity_id == "id1"
        assert req.requested_level == PrivilegeLevel.ADMIN
        assert req.reason == "need admin"
        assert req.resource_type == "db"
        assert req.action == "drop"

    def test_default_level_elevated(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        req = engine.request_step_up("r1", "s1", "id1")
        assert req.requested_level == PrivilegeLevel.ELEVATED

    def test_increments_step_up_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        assert engine.step_up_count == 1

    def test_duplicate_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.request_step_up("r1", "s1", "id1")

    def test_unknown_session_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.request_step_up("r1", "no-such", "id1")


# ===================================================================
# approve_step_up
# ===================================================================


class TestApproveStepUp:
    def test_returns_decision(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        dec = engine.approve_step_up("d1", "r1", "approver-1")
        assert isinstance(dec, PrivilegeElevationDecision)

    def test_decision_status_approved(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        dec = engine.approve_step_up("d1", "r1", "approver-1")
        assert dec.status == StepUpStatus.APPROVED

    def test_decision_fields(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        dec = engine.approve_step_up("d1", "r1", "approver-1", reason="ok")
        assert dec.decision_id == "d1"
        assert dec.request_id == "r1"
        assert dec.approver_id == "approver-1"
        assert dec.reason == "ok"

    def test_updates_request_status(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        engine.approve_step_up("d1", "r1", "approver-1")
        # The internal request should now be APPROVED — verify via a second approve attempt
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot approve"):
            engine.approve_step_up("d2", "r1", "approver-2")

    def test_elevates_session_privilege(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1", requested_level=PrivilegeLevel.ELEVATED)
        engine.approve_step_up("d1", "r1", "approver-1")
        session = engine.get_session("s1")
        assert session.privilege_level == PrivilegeLevel.ELEVATED

    def test_elevates_to_admin(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1", requested_level=PrivilegeLevel.ADMIN)
        engine.approve_step_up("d1", "r1", "approver-1")
        session = engine.get_session("s1")
        assert session.privilege_level == PrivilegeLevel.ADMIN

    def test_non_pending_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        engine.deny_step_up("d1", "r1", "approver-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot approve"):
            engine.approve_step_up("d2", "r1", "approver-1")

    def test_unknown_request_raises(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.approve_step_up("d1", "no-such", "approver-1")


# ===================================================================
# deny_step_up
# ===================================================================


class TestDenyStepUp:
    def test_returns_decision(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        dec = engine.deny_step_up("d1", "r1", "approver-1")
        assert isinstance(dec, PrivilegeElevationDecision)

    def test_decision_status_denied(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        dec = engine.deny_step_up("d1", "r1", "approver-1")
        assert dec.status == StepUpStatus.DENIED

    def test_does_not_elevate_session(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1", requested_level=PrivilegeLevel.ELEVATED)
        engine.deny_step_up("d1", "r1", "approver-1")
        session = engine.get_session("s1")
        assert session.privilege_level == PrivilegeLevel.STANDARD

    def test_non_pending_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        engine.approve_step_up("d1", "r1", "approver-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot deny"):
            engine.deny_step_up("d2", "r1", "approver-1")

    def test_unknown_request_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.deny_step_up("d1", "no-such", "approver-1")

    def test_decision_fields(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.request_step_up("r1", "s1", "id1")
        dec = engine.deny_step_up("d1", "r1", "approver-1", reason="risky")
        assert dec.decision_id == "d1"
        assert dec.approver_id == "approver-1"
        assert dec.reason == "risky"


# ===================================================================
# revoke_session
# ===================================================================


class TestRevokeSession:
    def test_returns_revocation_record(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.revoke_session("s1", RevocationReason.POLICY_VIOLATION)
        assert isinstance(rec, RevocationRecord)

    def test_session_becomes_revoked(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.POLICY_VIOLATION)
        session = engine.get_session("s1")
        assert session.status == SessionStatus.REVOKED

    def test_record_fields(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.revoke_session(
            "s1", RevocationReason.RISK_ESCALATION, detail="high risk"
        )
        assert rec.session_id == "s1"
        assert rec.identity_id == "id1"
        assert rec.reason == RevocationReason.RISK_ESCALATION
        assert rec.detail == "high risk"
        assert rec.revoked_at != ""

    def test_increments_revocation_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        assert engine.revocation_count == 1

    def test_sets_closed_at(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        session = engine.get_session("s1")
        assert session.closed_at != ""

    def test_unknown_session_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.revoke_session("no-such", RevocationReason.MANUAL_REVOCATION)

    def test_expired_session_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.expire_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot revoke"):
            engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)

    def test_closed_session_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.close_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot revoke"):
            engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)

    def test_suspended_session_can_be_revoked(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.suspend_session("s1")
        rec = engine.revoke_session("s1", RevocationReason.COMPLIANCE_FAILURE)
        assert rec.reason == RevocationReason.COMPLIANCE_FAILURE
        assert engine.get_session("s1").status == SessionStatus.REVOKED



# ===================================================================
# expire_session
# ===================================================================


class TestExpireSession:
    def test_returns_session_record(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.expire_session("s1")
        assert isinstance(rec, SessionRecord)

    def test_status_expired(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.expire_session("s1")
        assert rec.status == SessionStatus.EXPIRED

    def test_sets_closed_at(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.expire_session("s1")
        assert rec.closed_at != ""

    def test_unknown_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.expire_session("no-such")

    def test_non_active_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.suspend_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot expire"):
            engine.expire_session("s1")

    def test_decrements_active_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        assert engine.active_session_count == 1
        engine.expire_session("s1")
        assert engine.active_session_count == 0


# ===================================================================
# suspend_session
# ===================================================================


class TestSuspendSession:
    def test_returns_session_record(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.suspend_session("s1")
        assert isinstance(rec, SessionRecord)

    def test_status_suspended(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.suspend_session("s1")
        assert rec.status == SessionStatus.SUSPENDED

    def test_no_closed_at(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.suspend_session("s1")
        assert rec.closed_at == ""

    def test_unknown_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.suspend_session("no-such")

    def test_non_active_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.suspend_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot suspend"):
            engine.suspend_session("s1")

    def test_decrements_active_count(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.suspend_session("s1")
        assert engine.active_session_count == 0


# ===================================================================
# close_session
# ===================================================================


class TestCloseSession:
    def test_returns_closure_report(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        report = engine.close_session("s1")
        assert isinstance(report, SessionClosureReport)

    def test_session_becomes_closed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.close_session("s1")
        session = engine.get_session("s1")
        assert session.status == SessionStatus.CLOSED

    def test_report_fields(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        report = engine.close_session("s1")
        assert report.session_id == "s1"
        assert report.identity_id == "id1"
        assert report.closed_at != ""

    def test_report_stats_zero(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        report = engine.close_session("s1")
        assert report.total_enforcements == 0
        assert report.total_denials == 0
        assert report.total_step_ups == 0
        assert report.total_revocations == 0
        assert report.bindings_count == 0
        assert report.constraints_count == 0

    def test_unknown_raises(self, engine: PolicyEnforcementEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.close_session("no-such")

    def test_expired_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.expire_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot close"):
            engine.close_session("s1")

    def test_revoked_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot close"):
            engine.close_session("s1")

    def test_suspended_can_be_closed(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.suspend_session("s1")
        report = engine.close_session("s1")
        assert isinstance(report, SessionClosureReport)
        assert engine.get_session("s1").status == SessionStatus.CLOSED

    def test_sets_closed_at_on_session(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.close_session("s1")
        session = engine.get_session("s1")
        assert session.closed_at != ""


# ===================================================================
# session_snapshot
# ===================================================================


class TestSessionSnapshot:
    def test_returns_snapshot(self, engine: PolicyEnforcementEngine) -> None:
        snap = engine.session_snapshot("snap-1")
        assert isinstance(snap, SessionSnapshot)

    def test_snapshot_fields(self, engine: PolicyEnforcementEngine) -> None:
        snap = engine.session_snapshot("snap-1", scope_ref_id="scope-x")
        assert snap.snapshot_id == "snap-1"
        assert snap.scope_ref_id == "scope-x"
        assert snap.captured_at != ""

    def test_snapshot_counts_empty(self, engine: PolicyEnforcementEngine) -> None:
        snap = engine.session_snapshot("snap-1")
        assert snap.total_sessions == 0
        assert snap.active_sessions == 0
        assert snap.suspended_sessions == 0
        assert snap.revoked_sessions == 0
        assert snap.total_constraints == 0
        assert snap.total_step_ups == 0
        assert snap.total_revocations == 0
        assert snap.total_enforcements == 0

    def test_snapshot_counts_populated(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.suspend_session("s2")
        engine.add_constraint("c1", "s1")
        engine.evaluate_session_action("s1", "file", "read")
        snap = engine.session_snapshot("snap-1")
        assert snap.total_sessions == 2
        assert snap.active_sessions == 1
        assert snap.suspended_sessions == 1
        assert snap.total_constraints == 1
        assert snap.total_enforcements == 1

    def test_duplicate_raises(self, engine: PolicyEnforcementEngine) -> None:
        engine.session_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.session_snapshot("snap-1")


# ===================================================================
# Audit / query methods
# ===================================================================


class TestAuditQueries:
    def test_audits_for_session_empty(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        assert engine.audits_for_session("s1") == ()

    def test_audits_for_session_populated(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.evaluate_session_action("s1", "file", "read")
        audits = engine.audits_for_session("s1")
        assert len(audits) == 1
        assert isinstance(audits[0], EnforcementAuditRecord)
        assert audits[0].session_id == "s1"

    def test_revocations_for_session_empty(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        assert engine.revocations_for_session("s1") == ()

    def test_revocations_for_session_populated(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        revs = engine.revocations_for_session("s1")
        assert len(revs) == 1
        assert isinstance(revs[0], RevocationRecord)

    def test_enforcements_for_session_empty(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        assert engine.enforcements_for_session("s1") == ()

    def test_enforcements_for_session_populated(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.evaluate_session_action("s1", "file", "read")
        engine.evaluate_session_action("s1", "db", "write")
        evts = engine.enforcements_for_session("s1")
        assert len(evts) == 2
        assert all(isinstance(e, EnforcementEvent) for e in evts)



# ===================================================================
# state_hash
# ===================================================================


class TestStateHash:
    def test_returns_16_char_hex(self, engine: PolicyEnforcementEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_deterministic_for_same_state(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_after_open_session(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        h1 = engine.state_hash()
        engine.open_session("s1", "id1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_constraint(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        h1 = engine.state_hash()
        engine.add_constraint("c1", "s1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_enforcement(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        h1 = engine.state_hash()
        engine.evaluate_session_action("s1", "file", "read")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_revocation(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        h1 = engine.state_hash()
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_binding(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        h1 = engine.state_hash()
        engine.bind_session("b1", "s1", "file", "f1")
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# Golden Scenario 1: User authorized globally but blocked by session
# constraint in prod (session has environment constraint to "staging",
# action in "prod" -> DENIED)
# ===================================================================


class TestGoldenScenario1EnvironmentConstraintBlocksProd:
    def test_user_allowed_in_staging_but_denied_in_prod(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """A user with a globally active session is restricted to staging by
        a constraint. Actions targeting prod must be DENIED."""
        # Open session with elevated privilege — authorized globally
        engine.open_session(
            "gs1-session", "user-1",
            privilege_level=PrivilegeLevel.ELEVATED,
            environment_id="staging",
        )
        # Add environment constraint: restrict to staging only
        engine.add_constraint(
            "gs1-env-constraint", "gs1-session",
            environment_id="staging",
        )

        # Allowed in staging
        ev_staging = engine.evaluate_session_action(
            "gs1-session", "deployment", "deploy",
            environment_id="staging",
        )
        assert ev_staging.decision == EnforcementDecision.ALLOWED

        # Denied in prod
        ev_prod = engine.evaluate_session_action(
            "gs1-session", "deployment", "deploy",
            environment_id="prod",
        )
        assert ev_prod.decision == EnforcementDecision.DENIED
        assert "environment constraint" in ev_prod.reason

        # Audit records exist for both
        audits = engine.audits_for_session("gs1-session")
        assert len(audits) == 2


# ===================================================================
# Golden Scenario 2: Connector use requires step-up approval
# (session at STANDARD, action requires ELEVATED -> STEP_UP_REQUIRED,
# then approve -> ALLOWED)
# ===================================================================


class TestGoldenScenario2ConnectorStepUpApproval:
    def test_step_up_flow_from_denied_to_allowed(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """A connector action requiring ELEVATED privilege on a STANDARD
        session triggers STEP_UP_REQUIRED. After approval the action is ALLOWED."""
        engine.open_session(
            "gs2-session", "user-2",
            kind=SessionKind.CONNECTOR,
            privilege_level=PrivilegeLevel.STANDARD,
        )

        # Attempt connector action requiring elevated privilege
        ev1 = engine.evaluate_session_action(
            "gs2-session", "connector", "execute",
            required_privilege=PrivilegeLevel.ELEVATED,
            connector_id="salesforce",
        )
        assert ev1.decision == EnforcementDecision.STEP_UP_REQUIRED

        # Request step-up
        req = engine.request_step_up(
            "gs2-step-up", "gs2-session", "user-2",
            requested_level=PrivilegeLevel.ELEVATED,
            reason="connector execution requires elevated",
            resource_type="connector",
            action="execute",
        )
        assert req.status == StepUpStatus.PENDING

        # Approve step-up
        dec = engine.approve_step_up(
            "gs2-decision", "gs2-step-up", "admin-1",
            reason="approved for connector use",
        )
        assert dec.status == StepUpStatus.APPROVED

        # Verify session is now elevated
        session = engine.get_session("gs2-session")
        assert session.privilege_level == PrivilegeLevel.ELEVATED

        # Retry action — now allowed
        ev2 = engine.evaluate_session_action(
            "gs2-session", "connector", "execute",
            required_privilege=PrivilegeLevel.ELEVATED,
            connector_id="salesforce",
        )
        assert ev2.decision == EnforcementDecision.ALLOWED


# ===================================================================
# Golden Scenario 3: Expired delegated session loses access immediately
# (expire session -> all actions DENIED)
# ===================================================================


class TestGoldenScenario3ExpiredDelegatedSession:
    def test_expired_session_all_actions_denied(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """A delegated session that expires must immediately deny all actions."""
        engine.open_session(
            "gs3-session", "delegate-1",
            kind=SessionKind.SERVICE,
            privilege_level=PrivilegeLevel.ADMIN,
        )

        # Verify actions are allowed before expiry
        ev_before = engine.evaluate_session_action(
            "gs3-session", "api", "call",
            required_privilege=PrivilegeLevel.STANDARD,
        )
        assert ev_before.decision == EnforcementDecision.ALLOWED

        # Expire the session
        expired = engine.expire_session("gs3-session")
        assert expired.status == SessionStatus.EXPIRED
        assert expired.closed_at != ""

        # All actions now denied
        ev_standard = engine.evaluate_session_action(
            "gs3-session", "api", "call",
            required_privilege=PrivilegeLevel.STANDARD,
        )
        assert ev_standard.decision == EnforcementDecision.DENIED

        ev_admin = engine.evaluate_session_action(
            "gs3-session", "api", "admin-call",
            required_privilege=PrivilegeLevel.ADMIN,
        )
        assert ev_admin.decision == EnforcementDecision.DENIED

        ev_read = engine.evaluate_session_action(
            "gs3-session", "file", "read",
        )
        assert ev_read.decision == EnforcementDecision.DENIED


# ===================================================================
# Golden Scenario 4: Risk/compliance failure revokes active session
# (revoke with RISK_ESCALATION -> REVOKED, action -> REVOKED decision)
# ===================================================================


class TestGoldenScenario4RiskRevocation:
    def test_risk_revocation_blocks_all_actions(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """A risk escalation revokes an active session. Subsequent actions
        return REVOKED decision (not just DENIED)."""
        engine.open_session("gs4-session", "user-4")

        # Verify normal access
        ev_before = engine.evaluate_session_action(
            "gs4-session", "data", "query",
        )
        assert ev_before.decision == EnforcementDecision.ALLOWED

        # Risk escalation triggers revocation
        rev = engine.revoke_session(
            "gs4-session", RevocationReason.RISK_ESCALATION,
            detail="anomalous access pattern detected",
        )
        assert rev.reason == RevocationReason.RISK_ESCALATION

        # Session is now revoked
        session = engine.get_session("gs4-session")
        assert session.status == SessionStatus.REVOKED

        # Actions return REVOKED (not just DENIED)
        ev_after = engine.evaluate_session_action(
            "gs4-session", "data", "query",
        )
        assert ev_after.decision == EnforcementDecision.REVOKED

        # Revocation record is retrievable
        revs = engine.revocations_for_session("gs4-session")
        assert len(revs) == 1
        assert revs[0].detail == "anomalous access pattern detected"


# ===================================================================
# Golden Scenario 5: Campaign action allowed in workspace but denied
# in environment (constraint blocks environment mismatch)
# ===================================================================


class TestGoldenScenario5CampaignEnvironmentBlock:
    def test_campaign_allowed_in_workspace_denied_in_wrong_env(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """A campaign session is constrained to a specific environment.
        Actions in the correct environment are allowed; actions in a
        different environment are denied."""
        engine.open_session(
            "gs5-session", "campaign-user",
            kind=SessionKind.CAMPAIGN,
            campaign_id="campaign-42",
            environment_id="workspace-dev",
        )
        # Constraint: only allowed in workspace-dev environment
        engine.add_constraint(
            "gs5-env-constraint", "gs5-session",
            environment_id="workspace-dev",
        )

        # Allowed in workspace-dev
        ev_ok = engine.evaluate_session_action(
            "gs5-session", "campaign", "execute",
            environment_id="workspace-dev",
        )
        assert ev_ok.decision == EnforcementDecision.ALLOWED

        # Denied in production
        ev_prod = engine.evaluate_session_action(
            "gs5-session", "campaign", "execute",
            environment_id="production",
        )
        assert ev_prod.decision == EnforcementDecision.DENIED

        # Denied in staging
        ev_staging = engine.evaluate_session_action(
            "gs5-session", "campaign", "execute",
            environment_id="staging",
        )
        assert ev_staging.decision == EnforcementDecision.DENIED


# ===================================================================
# Golden Scenario 6: Close session produces accurate closure report
# with all stats
# ===================================================================


class TestGoldenScenario6ClosureReportStats:
    def test_closure_report_has_accurate_stats(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """After various operations the closure report must accurately
        reflect total_enforcements, total_denials, total_step_ups,
        total_revocations, bindings_count, and constraints_count."""
        engine.open_session("gs6-session", "user-6")

        # Add constraints (2)
        engine.add_constraint("gs6-c1", "gs6-session", resource_type="file")
        engine.add_constraint("gs6-c2", "gs6-session", environment_id="dev")

        # Add bindings (3)
        engine.bind_session("gs6-b1", "gs6-session", "file", "f1")
        engine.bind_session("gs6-b2", "gs6-session", "file", "f2")
        engine.bind_session("gs6-b3", "gs6-session", "db", "db1")

        # Enforce some actions: 1 allowed, 1 denied (resource mismatch), 1 denied (env mismatch)
        ev1 = engine.evaluate_session_action(
            "gs6-session", "file", "read", environment_id="dev",
        )
        assert ev1.decision == EnforcementDecision.ALLOWED

        ev2 = engine.evaluate_session_action(
            "gs6-session", "database", "read",
        )
        assert ev2.decision == EnforcementDecision.DENIED

        ev3 = engine.evaluate_session_action(
            "gs6-session", "file", "read", environment_id="prod",
        )
        assert ev3.decision == EnforcementDecision.DENIED

        # Request step-up (1)
        engine.request_step_up(
            "gs6-step-up", "gs6-session", "user-6",
            requested_level=PrivilegeLevel.ELEVATED,
        )

        # Close session
        report = engine.close_session("gs6-session")

        assert report.session_id == "gs6-session"
        assert report.identity_id == "user-6"
        assert report.total_enforcements == 3
        assert report.total_denials == 2
        assert report.total_step_ups == 1
        assert report.total_revocations == 0
        assert report.bindings_count == 3
        assert report.constraints_count == 2
        assert report.closed_at != ""

        # Session is now CLOSED
        session = engine.get_session("gs6-session")
        assert session.status == SessionStatus.CLOSED


# ===================================================================
# Additional edge-case and integration tests
# ===================================================================


class TestEdgeCases:
    def test_double_revoke_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.revoke_session("s1", RevocationReason.POLICY_VIOLATION)

    def test_close_already_closed_raises(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        engine.close_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.close_session("s1")

    def test_multiple_evaluations_tracked(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        for i in range(5):
            engine.evaluate_session_action("s1", "file", f"action-{i}")
        assert engine.enforcement_count == 5
        assert engine.audit_count == 5

    def test_snapshot_reflects_revoked(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.revoke_session("s1", RevocationReason.MANUAL_REVOCATION)
        snap = engine.session_snapshot("snap-rev")
        assert snap.revoked_sessions == 1
        assert snap.active_sessions == 1
        assert snap.total_sessions == 2

    def test_constraint_for_different_sessions_isolated(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.add_constraint("c1", "s1", environment_id="staging")
        # s2 has no constraints — action in prod allowed
        ev = engine.evaluate_session_action(
            "s2", "file", "read", environment_id="prod"
        )
        assert ev.decision == EnforcementDecision.ALLOWED

    def test_binding_for_different_sessions_isolated(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        engine.open_session("s1", "id1")
        engine.open_session("s2", "id1")
        engine.bind_session("b1", "s1", "file", "f1")
        assert len(engine.bindings_for_session("s1")) == 1
        assert len(engine.bindings_for_session("s2")) == 0

    def test_session_record_is_frozen(
        self, engine: PolicyEnforcementEngine, active_session: SessionRecord
    ) -> None:
        rec = engine.get_session("s1")
        with pytest.raises(AttributeError):
            rec.status = SessionStatus.CLOSED  # type: ignore[misc]

    def test_privilege_order_comprehensive(
        self, engine: PolicyEnforcementEngine
    ) -> None:
        """Verify the full privilege ordering: STANDARD < ELEVATED < ADMIN < SYSTEM < EMERGENCY."""
        levels = [
            PrivilegeLevel.STANDARD,
            PrivilegeLevel.ELEVATED,
            PrivilegeLevel.ADMIN,
            PrivilegeLevel.SYSTEM,
            PrivilegeLevel.EMERGENCY,
        ]
        for i, level in enumerate(levels):
            sid = f"priv-{i}"
            engine.open_session(sid, "id1", privilege_level=level)
            # Should allow everything at or below its level
            for j in range(i + 1):
                ev = engine.evaluate_session_action(
                    sid, "res", "act", required_privilege=levels[j]
                )
                assert ev.decision == EnforcementDecision.ALLOWED, (
                    f"{level} should allow {levels[j]}"
                )
            # Should require step-up for everything above
            for j in range(i + 1, len(levels)):
                ev = engine.evaluate_session_action(
                    sid, "res", "act", required_privilege=levels[j]
                )
                assert ev.decision == EnforcementDecision.STEP_UP_REQUIRED, (
                    f"{level} should require step-up for {levels[j]}"
                )
