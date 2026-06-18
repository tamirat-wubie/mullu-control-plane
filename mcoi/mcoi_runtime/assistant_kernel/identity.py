"""Purpose: assistant profile and accountable identity bindings.
Governance scope: owner/tenant boundaries, skill/capability separation,
    approval policy, evidence requirements, and protected capability denial.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Every assistant profile has explicit owner and tenant scope.
  - Skills describe procedure; capabilities grant executable authority.
  - Profile skill identifiers stay inside the profile-kind namespace.
  - Allowed and forbidden capabilities are disjoint after protected denials.
  - Profile metadata cannot grant execution authority or production readiness.
  - Evidence requirements and escalation paths are never implicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from mcoi_runtime.governance.protected_variables import (
    ProtectedVariable,
    ProtectedVariableMonitor,
    ProtectionRule,
)


ASSISTANT_PROFILE_KINDS = (
    "personal",
    "founder",
    "team_ops",
    "finance_ops",
    "executive_ops",
    "corporate_admin",
)
OWNER_SCOPES = ("single_owner", "team_owned", "organization_owned")
TENANT_SCOPES = ("personal_tenant", "team_tenant", "organization_tenant", "enterprise_tenant")
EXTERNAL_EFFECT_POLICIES = ("deny", "approval_required", "dual_approval_required")
PROTECTED_FORBIDDEN_CAPABILITIES = frozenset(
    {
        "approval.self_grant",
        "connector.raw_secret.read",
        "payment.execute.unapproved",
        "policy.modify",
        "policy.promote",
    }
)
FORBIDDEN_PROFILE_METADATA_KEYS = frozenset(
    {
        "deployment_witness_closed",
        "execution_authority_granted",
        "live_execution_ready",
        "production_ready",
        "public_production_ready",
        "public_readiness_claim_allowed",
    }
)
_FORBIDDEN_CAPABILITIES_FIELD = "forbidden_capabilities"


def _assistant_capability_floor_monitor() -> ProtectedVariableMonitor:
    monitor = ProtectedVariableMonitor()
    monitor.register(
        ProtectedVariable(
            name=_FORBIDDEN_CAPABILITIES_FIELD,
            rule=ProtectionRule.REQUIRED_SUPERSET,
            required_members=tuple(sorted(PROTECTED_FORBIDDEN_CAPABILITIES)),
        )
    )
    return monitor


_ASSISTANT_CAPABILITY_FLOOR_MONITOR = _assistant_capability_floor_monitor()


@dataclass(frozen=True, slots=True)
class AssistantProfile:
    """Governed assistant profile used to bind skills to admitted capabilities."""

    assistant_id: str
    kind: str
    owner_scope: str
    tenant_scope: str
    role: str
    skill_ids: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    memory_policy: str
    approval_policy: str
    budget_policy: str
    external_send_policy: str
    data_retention_policy: str
    evidence_required: tuple[str, ...]
    escalation_path: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assistant_id", ensure_non_empty_text("assistant_id", self.assistant_id))
        if self.kind not in ASSISTANT_PROFILE_KINDS:
            raise RuntimeCoreInvariantError("assistant kind is not admitted")
        if self.owner_scope not in OWNER_SCOPES:
            raise RuntimeCoreInvariantError("owner_scope is not admitted")
        if self.tenant_scope not in TENANT_SCOPES:
            raise RuntimeCoreInvariantError("tenant_scope is not admitted")
        object.__setattr__(self, "role", ensure_non_empty_text("role", self.role))
        skill_ids = _normalize_text_tuple(self.skill_ids, "skill_ids")
        _validate_skill_namespace(self.kind, skill_ids)
        allowed = _normalize_text_tuple(self.allowed_capabilities, "allowed_capabilities")
        forbidden = _apply_protected_forbidden_capability_floor(self.forbidden_capabilities)
        if set(allowed).intersection(forbidden):
            raise RuntimeCoreInvariantError("capability scope conflict")
        if set(skill_ids).intersection(allowed, forbidden):
            raise RuntimeCoreInvariantError("skill identifiers must not grant capability authority")
        if self.external_send_policy not in EXTERNAL_EFFECT_POLICIES:
            raise RuntimeCoreInvariantError("external_send_policy is not admitted")
        object.__setattr__(self, "skill_ids", skill_ids)
        object.__setattr__(self, "allowed_capabilities", allowed)
        object.__setattr__(self, "forbidden_capabilities", forbidden)
        object.__setattr__(self, "memory_policy", ensure_non_empty_text("memory_policy", self.memory_policy))
        object.__setattr__(self, "approval_policy", ensure_non_empty_text("approval_policy", self.approval_policy))
        object.__setattr__(self, "budget_policy", ensure_non_empty_text("budget_policy", self.budget_policy))
        object.__setattr__(
            self,
            "data_retention_policy",
            ensure_non_empty_text("data_retention_policy", self.data_retention_policy),
        )
        object.__setattr__(self, "evidence_required", _normalize_text_tuple(self.evidence_required, "evidence_required"))
        object.__setattr__(self, "escalation_path", _normalize_text_tuple(self.escalation_path, "escalation_path"))
        metadata = dict(self.metadata)
        _validate_profile_metadata(metadata)
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-oriented immutable profile projection."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AssistantIdentityBinding:
    """Runtime identity binding for one assistant profile instance."""

    binding_id: str
    assistant_id: str
    owner_id: str
    tenant_id: str
    profile_kind: str
    role: str
    allowed_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    evidence_required: tuple[str, ...]
    created_at: str
    binding_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", ensure_non_empty_text("binding_id", self.binding_id))
        object.__setattr__(self, "assistant_id", ensure_non_empty_text("assistant_id", self.assistant_id))
        object.__setattr__(self, "owner_id", ensure_non_empty_text("owner_id", self.owner_id))
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        if self.profile_kind not in ASSISTANT_PROFILE_KINDS:
            raise RuntimeCoreInvariantError("profile_kind is not admitted")
        object.__setattr__(self, "role", ensure_non_empty_text("role", self.role))
        object.__setattr__(
            self,
            "allowed_capabilities",
            _normalize_text_tuple(self.allowed_capabilities, "allowed_capabilities"),
        )
        object.__setattr__(
            self,
            "forbidden_capabilities",
            _normalize_text_tuple(self.forbidden_capabilities, "forbidden_capabilities"),
        )
        object.__setattr__(self, "evidence_required", _normalize_text_tuple(self.evidence_required, "evidence_required"))
        object.__setattr__(self, "created_at", ensure_non_empty_text("created_at", self.created_at))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-oriented identity binding projection."""
        return _json_ready(asdict(self))


def bind_assistant_identity(
    profile: AssistantProfile,
    *,
    owner_id: str,
    tenant_id: str,
    created_at: str,
) -> AssistantIdentityBinding:
    """Bind one assistant profile to a concrete owner and tenant."""
    owner = ensure_non_empty_text("owner_id", owner_id)
    tenant = ensure_non_empty_text("tenant_id", tenant_id)
    binding = AssistantIdentityBinding(
        binding_id=stable_identifier(
            "assistant-binding",
            {
                "assistant_id": profile.assistant_id,
                "owner_id": owner,
                "tenant_id": tenant,
                "created_at": created_at,
            },
        ),
        assistant_id=profile.assistant_id,
        owner_id=owner,
        tenant_id=tenant,
        profile_kind=profile.kind,
        role=profile.role,
        allowed_capabilities=profile.allowed_capabilities,
        forbidden_capabilities=profile.forbidden_capabilities,
        evidence_required=profile.evidence_required,
        created_at=created_at,
        metadata={
            "owner_scope": profile.owner_scope,
            "tenant_scope": profile.tenant_scope,
            "skill_capability_boundary_enforced": True,
        },
    )
    return _stamp_binding(binding)


def builtin_assistant_profiles() -> tuple[AssistantProfile, ...]:
    """Return the built-in assistant profile catalog."""
    return (
        personal_default_profile(),
        founder_default_profile(),
        team_ops_default_profile(),
        finance_ops_default_profile(),
        executive_ops_default_profile(),
        corporate_admin_default_profile(),
    )


def finance_ops_default_profile() -> AssistantProfile:
    """Return the flagship FinanceOps assistant profile."""
    return AssistantProfile(
        assistant_id="finance_ops.default",
        kind="finance_ops",
        owner_scope="organization_owned",
        tenant_scope="enterprise_tenant",
        role="finance_ops_assistant",
        skill_ids=(
            "skill.finance_ops.invoice_intake",
            "skill.finance_ops.approval_packet",
            "skill.finance_ops.reconciliation",
        ),
        allowed_capabilities=(
            "invoice.read",
            "invoice.extract",
            "vendor.verify",
            "po.match",
            "budget.check",
            "approval.request",
            "payment.prepare",
            "payment.execute.with_approval",
            "payment.reconcile",
            "ledger.update",
            "evidence.export",
            "email.draft",
            "email.send.with_approval",
            "calendar.read",
        ),
        forbidden_capabilities=(
            "payment.execute",
            "bank_account.modify",
            "vendor.create.without_review",
        ),
        memory_policy="admitted_finance_facts_only",
        approval_policy="fresh_dual_control_for_payment",
        budget_policy="budget_check_required_before_payment_prepare",
        external_send_policy="dual_approval_required",
        data_retention_policy="finance_audit_retention",
        evidence_required=(
            "invoice_source_evidence",
            "vendor_verification_receipt",
            "duplicate_payment_check",
            "budget_check_receipt",
            "approval_receipt",
            "payment_receipt",
            "ledger_reconciliation",
            "signed_evidence_bundle",
        ),
        escalation_path=("finance_admin", "controller", "audit_owner"),
        metadata={"flagship_pack": "finance_ops", "activation_requires_live_receipts": True},
    )


def personal_default_profile() -> AssistantProfile:
    """Return a personal assistant profile for owner-scoped daily workflows."""
    return AssistantProfile(
        assistant_id="personal.default",
        kind="personal",
        owner_scope="single_owner",
        tenant_scope="personal_tenant",
        role="personal_assistant",
        skill_ids=("skill.personal.inbox_triage", "skill.personal.meeting_scheduling"),
        allowed_capabilities=(
            "email.read",
            "email.search",
            "email.draft",
            "email.send.with_approval",
            "calendar.read",
            "calendar.conflict_check",
            "calendar.schedule",
            "calendar.invite",
            "memory.preference.admit",
            "task.reminder.schedule",
        ),
        forbidden_capabilities=("payment.execute", "device.host_control"),
        memory_policy="verified_preferences_only",
        approval_policy="owner_approval_for_external_write",
        budget_policy="personal_budget_awareness_only",
        external_send_policy="approval_required",
        data_retention_policy="owner_controlled_retention",
        evidence_required=("approval_receipt", "effect_receipt", "closure_receipt"),
        escalation_path=("owner",),
    )


def founder_default_profile() -> AssistantProfile:
    """Return a founder assistant profile for constrained executive delegation."""
    return _organization_profile(
        assistant_id="founder.default",
        kind="founder",
        role="founder_assistant",
        skill_ids=("skill.founder.briefing", "skill.founder.follow_up"),
        allowed_capabilities=("email.draft", "calendar.read", "calendar.invite", "task.reminder.schedule"),
        escalation_path=("founder", "operator"),
    )


def team_ops_default_profile() -> AssistantProfile:
    """Return a TeamOps assistant profile for shared inbox routing."""
    return _organization_profile(
        assistant_id="team_ops.default",
        kind="team_ops",
        role="team_ops_assistant",
        skill_ids=("skill.team_ops.shared_inbox_triage", "skill.team_ops.owner_assignment"),
        allowed_capabilities=(
            "messaging.thread.read",
            "email.read",
            "email.draft",
            "email.send.with_approval",
            "task.assign",
            "evidence.export",
        ),
        escalation_path=("team_lead", "ops_owner"),
    )


def executive_ops_default_profile() -> AssistantProfile:
    """Return an ExecutiveOps assistant profile for briefings and delegated follow-up."""
    return _organization_profile(
        assistant_id="executive_ops.default",
        kind="executive_ops",
        role="executive_ops_assistant",
        skill_ids=("skill.executive_ops.briefing", "skill.executive_ops.decision_log"),
        allowed_capabilities=("email.draft", "calendar.read", "calendar.invite", "task.assign", "evidence.export"),
        escalation_path=("executive_owner", "chief_of_staff"),
    )


def corporate_admin_default_profile() -> AssistantProfile:
    """Return a corporate admin assistant profile for governed administration."""
    return _organization_profile(
        assistant_id="corporate_admin.default",
        kind="corporate_admin",
        role="corporate_admin_assistant",
        skill_ids=("skill.corporate_admin.access_review", "skill.corporate_admin.audit_export"),
        allowed_capabilities=(
            "directory.read",
            "approval.request",
            "access.request.route",
            "audit.export",
            "evidence.export",
        ),
        escalation_path=("it_admin", "security_owner", "compliance_officer"),
        external_send_policy="dual_approval_required",
    )


def _organization_profile(
    *,
    assistant_id: str,
    kind: str,
    role: str,
    skill_ids: tuple[str, ...],
    allowed_capabilities: tuple[str, ...],
    escalation_path: tuple[str, ...],
    external_send_policy: str = "approval_required",
) -> AssistantProfile:
    return AssistantProfile(
        assistant_id=assistant_id,
        kind=kind,
        owner_scope="organization_owned",
        tenant_scope="organization_tenant",
        role=role,
        skill_ids=skill_ids,
        allowed_capabilities=allowed_capabilities,
        forbidden_capabilities=("payment.execute", "policy.modify"),
        memory_policy="tenant_scoped_admitted_facts_only",
        approval_policy="role_bound_external_write_approval",
        budget_policy="tenant_budget_gate",
        external_send_policy=external_send_policy,
        data_retention_policy="tenant_retention_policy",
        evidence_required=("approval_receipt", "effect_receipt", "closure_receipt"),
        escalation_path=escalation_path,
    )


def _stamp_binding(binding: AssistantIdentityBinding) -> AssistantIdentityBinding:
    unstamped = replace(binding, binding_hash="")
    return replace(binding, binding_hash=stable_identifier("assistant-binding-hash", asdict(unstamped)))


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized


def _validate_skill_namespace(kind: str, skill_ids: tuple[str, ...]) -> None:
    namespace = f"skill.{kind}."
    if any(not skill_id.startswith(namespace) for skill_id in skill_ids):
        raise RuntimeCoreInvariantError("skill_ids must stay within assistant kind namespace")


def _validate_profile_metadata(metadata: dict[str, Any]) -> None:
    forbidden_keys = sorted(str(key) for key in metadata if str(key) in FORBIDDEN_PROFILE_METADATA_KEYS)
    if forbidden_keys:
        raise RuntimeCoreInvariantError("assistant profile metadata cannot carry authority or readiness claim keys")


def _apply_protected_forbidden_capability_floor(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    """Return forbidden capabilities with the protected denial floor present."""
    normalized = _normalize_optional_text_tuple(capabilities)
    report = _ASSISTANT_CAPABILITY_FLOOR_MONITOR.check(
        {},
        {_FORBIDDEN_CAPABILITIES_FIELD: normalized},
    )
    if not report.ok:
        normalized = _normalize_text_tuple(
            (*normalized, *tuple(sorted(PROTECTED_FORBIDDEN_CAPABILITIES))),
            _FORBIDDEN_CAPABILITIES_FIELD,
        )
    final_report = _ASSISTANT_CAPABILITY_FLOOR_MONITOR.check(
        {},
        {_FORBIDDEN_CAPABILITIES_FIELD: normalized},
    )
    if not final_report.ok:
        raise RuntimeCoreInvariantError("protected forbidden capability floor missing")
    return normalized


def _normalize_optional_text_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
