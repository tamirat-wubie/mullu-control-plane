"""Purpose: typed assistant goals and flagship FinanceOps goal templates.
Governance scope: intent declaration, required capability lists, closure
    predicates, and risk tier selection before planning.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - A goal is not executable authority.
  - Every goal declares required capabilities and closure predicates.
  - High-risk financial goals carry invoice, vendor, approval, payment,
    reconciliation, and signed evidence closure requirements.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


RISK_TIERS = ("low", "medium", "high", "critical")
FINANCE_OPS_INVOICE_PAYMENT_CAPABILITIES = (
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
)
FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES = (
    "invoice_identity_verified",
    "vendor_identity_verified",
    "duplicate_payment_check_passed",
    "budget_available",
    "approval_valid",
    "payment_receipt_exists",
    "ledger_reconciliation_exists",
    "signed_evidence_bundle_exists",
)


@dataclass(frozen=True, slots=True)
class AssistantGoal:
    """One admitted assistant goal proposal."""

    goal_id: str
    tenant_id: str
    owner_id: str
    profile_id: str
    intent: str
    required_capabilities: tuple[str, ...]
    required_closure_predicates: tuple[str, ...]
    risk_tier: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", ensure_non_empty_text("goal_id", self.goal_id))
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "owner_id", ensure_non_empty_text("owner_id", self.owner_id))
        object.__setattr__(self, "profile_id", ensure_non_empty_text("profile_id", self.profile_id))
        object.__setattr__(self, "intent", ensure_non_empty_text("intent", self.intent))
        object.__setattr__(
            self,
            "required_capabilities",
            _normalize_text_tuple(self.required_capabilities, "required_capabilities"),
        )
        object.__setattr__(
            self,
            "required_closure_predicates",
            _normalize_text_tuple(self.required_closure_predicates, "required_closure_predicates"),
        )
        if self.risk_tier not in RISK_TIERS:
            raise RuntimeCoreInvariantError("risk_tier is not admitted")
        object.__setattr__(self, "created_at", ensure_non_empty_text("created_at", self.created_at))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-oriented goal projection."""
        return {
            **asdict(self),
            "required_capabilities": list(self.required_capabilities),
            "required_closure_predicates": list(self.required_closure_predicates),
        }


def finance_ops_invoice_payment_goal(
    *,
    tenant_id: str,
    owner_id: str,
    profile_id: str,
    invoice_ref: str,
    vendor_ref: str,
    created_at: str,
) -> AssistantGoal:
    """Build the flagship FinanceOps invoice-payment goal template."""
    invoice = ensure_non_empty_text("invoice_ref", invoice_ref)
    vendor = ensure_non_empty_text("vendor_ref", vendor_ref)
    payload = {
        "tenant_id": tenant_id,
        "owner_id": owner_id,
        "profile_id": profile_id,
        "invoice_ref": invoice,
        "vendor_ref": vendor,
        "created_at": created_at,
    }
    return AssistantGoal(
        goal_id=stable_identifier("assistant-goal-finance-payment", payload),
        tenant_id=tenant_id,
        owner_id=owner_id,
        profile_id=profile_id,
        intent="prepare_invoice_payment_with_approval_and_reconciliation",
        required_capabilities=FINANCE_OPS_INVOICE_PAYMENT_CAPABILITIES,
        required_closure_predicates=FINANCE_OPS_PAYMENT_CLOSURE_PREDICATES,
        risk_tier="critical",
        created_at=created_at,
        metadata={
            "invoice_ref": invoice,
            "vendor_ref": vendor,
            "closure_requires_two_confirmations": True,
        },
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized
