"""Build the canonical gate template registry.

Purpose: define reusable gate templates shared by capability passports,
promotion paths, evidence packets, and future debt reports.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: static registry definitions and capability passport gate IDs.
Invariants:
  - Gate templates are read-only policy metadata and never execution authority.
  - Every template has explicit inputs, receipts, block conditions, and failure mode.
  - Gate IDs are stable and reusable across capability families.
"""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION = 1
REGISTRY_ID = "gate_template_registry.foundation.v1"


class GateTemplateRegistryError(ValueError):
    """Raised when gate template registry projection is unsafe."""


GATE_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "gate_id": "gate.uao.admission",
        "display_name": "UAO admission",
        "category": "admission",
        "purpose": "Require Universal Action Orchestration admission before effect-bearing or governed work proceeds.",
        "applies_to": ["all_capabilities"],
        "required_inputs": ["action", "state", "memory", "policy", "capabilities", "exposure_boundary"],
        "required_receipts": ["universal_action_orchestration_validation_receipt"],
        "blocks_when_missing": ["unorchestrated_effect"],
        "failure_mode": "GovernanceBlocked",
        "operator_status_when_missing": "Blocked",
        "validator_refs": ["universal_action_orchestration_contract"],
    },
    {
        "gate_id": "gate.capability.registry",
        "display_name": "Capability registry binding",
        "category": "admission",
        "purpose": "Require the action to bind to a governed capability registry entry before execution.",
        "applies_to": ["all_capabilities"],
        "required_inputs": ["capability_id", "capability_registry_entry", "certification_status"],
        "required_receipts": ["capability_registry_entry"],
        "blocks_when_missing": ["raw_tool_path", "unregistered_capability"],
        "failure_mode": "GovernanceBlocked",
        "operator_status_when_missing": "Blocked",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.evidence.intake",
        "display_name": "Evidence intake",
        "category": "evidence",
        "purpose": "Require claimed evidence refs to be present, bounded, and associated with the capability.",
        "applies_to": ["all_capabilities"],
        "required_inputs": ["evidence_refs", "source_ref", "capability_id"],
        "required_receipts": ["evidence_intake_receipt"],
        "blocks_when_missing": ["missing_evidence", "unbound_evidence_ref"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Evidence missing",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.evidence.verification",
        "display_name": "Evidence verification",
        "category": "evidence",
        "purpose": "Require evidence to be checked before it can support readiness, execution, or closure claims.",
        "applies_to": ["all_capabilities"],
        "required_inputs": ["evidence_refs", "verification_policy", "capability_id"],
        "required_receipts": ["evidence_verification_receipt"],
        "blocks_when_missing": ["unverified_claim", "stale_evidence"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Evidence missing",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.receipt.append",
        "display_name": "Receipt append",
        "category": "receipt",
        "purpose": "Require action evidence to be appended as a receipt before terminal closure or success response.",
        "applies_to": ["all_capabilities"],
        "required_inputs": ["required_receipts", "receipt_store", "capability_id"],
        "required_receipts": ["effect_reconciliation_receipt", "terminal_closure_certificate"],
        "blocks_when_missing": ["success_without_receipt", "terminal_closure_overclaim"],
        "failure_mode": "GovernanceBlocked",
        "operator_status_when_missing": "Blocked",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.approval.required",
        "display_name": "Approval required",
        "category": "approval",
        "purpose": "Require explicit operator or policy approval before high-risk or effect-bearing action execution.",
        "applies_to": ["high_risk", "critical_risk", "external_send", "world_mutating"],
        "required_inputs": ["approval_chain", "approval_refs", "actor_id", "separation_of_duty"],
        "required_receipts": ["approval_decision_receipt"],
        "blocks_when_missing": ["execute_without_approval", "self_approval"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Needs approval",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.sandbox.required",
        "display_name": "Sandbox required",
        "category": "isolation",
        "purpose": "Require sandbox or dry-run evidence before live promotion or worker execution.",
        "applies_to": ["worker_bound", "connector", "browser", "computer", "physical"],
        "required_inputs": ["sandbox_receipt", "isolation_profile", "capability_id"],
        "required_receipts": ["sandbox_receipt"],
        "blocks_when_missing": ["live_without_sandbox", "worker_without_rehearsal"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Live action disabled",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.connector.lease",
        "display_name": "Connector lease",
        "category": "isolation",
        "purpose": "Require scoped connector or worker lease evidence before provider, mailbox, calendar, browser, or payment access.",
        "applies_to": ["connector", "browser", "communication", "financial", "phone", "physical"],
        "required_inputs": ["connector_id", "lease_ref", "secret_scope", "network_allowlist"],
        "required_receipts": ["connector_lease_receipt"],
        "blocks_when_missing": ["connector_call_without_lease", "credential_scope_exceeded"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Evidence missing",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.rollback.required",
        "display_name": "Rollback required",
        "category": "recovery",
        "purpose": "Require rollback, compensation, or explicit review-only recovery status before effect-bearing action.",
        "applies_to": ["world_mutating", "external_write", "file_write", "payment", "physical"],
        "required_inputs": ["rollback_status", "rollback_capability", "compensation_capability"],
        "required_receipts": ["rollback_or_recovery_receipt"],
        "blocks_when_missing": ["execute_without_recovery", "unrecoverable_effect_overclaim"],
        "failure_mode": "GovernanceBlocked",
        "operator_status_when_missing": "Prepare-only",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.external.send",
        "display_name": "External send",
        "category": "external_effect",
        "purpose": "Require approval, evidence, and receipts before email, invite, notification, payment, or other external send.",
        "applies_to": ["external_send", "communication", "messaging", "financial"],
        "required_inputs": ["recipient_hashes", "approval_ref", "provider_scope"],
        "required_receipts": ["external_send_receipt", "provider_receipt"],
        "blocks_when_missing": ["external_send_without_approval", "recipient_unapproved"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Needs approval",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.workspace.write",
        "display_name": "Workspace write",
        "category": "local_effect",
        "purpose": "Require diff, path confinement, and rollback evidence before workspace file mutation.",
        "applies_to": ["computer", "software_dev", "document", "file_write"],
        "required_inputs": ["workspace_root", "path_policy", "diff_ref", "rollback_ref"],
        "required_receipts": ["workspace_write_receipt", "diff_receipt"],
        "blocks_when_missing": ["unapproved_file_write", "workspace_escape", "missing_diff"],
        "failure_mode": "GovernanceBlocked",
        "operator_status_when_missing": "Prepare-only",
        "validator_refs": ["capability_passports_validator"],
    },
    {
        "gate_id": "gate.production.evidence",
        "display_name": "Production evidence",
        "category": "promotion",
        "purpose": "Require live read, live write when effect-bearing, worker, and recovery evidence before production readiness.",
        "applies_to": ["production_claim", "live_action", "capability_promotion"],
        "required_inputs": ["maturity_assessment", "production_blockers", "evidence_refs"],
        "required_receipts": ["production_evidence_receipt"],
        "blocks_when_missing": ["claim_production_ready", "live_action_enablement"],
        "failure_mode": "AwaitingEvidence",
        "operator_status_when_missing": "Live action disabled",
        "validator_refs": ["capability_passports_validator"],
    },
)


def build_gate_template_registry() -> dict[str, Any]:
    """Return the deterministic canonical gate template registry.

    Input contract: none.
    Output contract: JSON-serializable registry with stable gate templates.
    Error contract: raises GateTemplateRegistryError if the static definitions
    contain duplicate IDs or authority overclaims.
    """

    _validate_static_templates(GATE_TEMPLATES)
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": REGISTRY_ID,
        "mode": "foundation",
        "registry_is_not_execution_authority": True,
        "template_count": len(GATE_TEMPLATES),
        "categories": _categories(GATE_TEMPLATES),
        "templates": [dict(template) for template in GATE_TEMPLATES],
        "validators": [
            {
                "validator_id": "gate_template_registry_validator",
                "command": "python scripts/validate_gate_template_registry.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "gate_template_registry_tests",
                "command": "python -m pytest tests/test_validate_gate_template_registry.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": (
            "Bind capability passport required_gates to this registry before "
            "building dashboard, evidence passport, promotion path, or debt report projections."
        ),
    }


def gate_template_ids() -> tuple[str, ...]:
    """Return all canonical gate template IDs."""

    return tuple(template["gate_id"] for template in GATE_TEMPLATES)


def _validate_static_templates(templates: tuple[dict[str, Any], ...]) -> None:
    gate_ids = [str(template.get("gate_id", "")) for template in templates]
    if len(gate_ids) != len(set(gate_ids)):
        raise GateTemplateRegistryError("duplicate gate template id")
    for template in templates:
        gate_id = str(template.get("gate_id", ""))
        if not gate_id.startswith("gate."):
            raise GateTemplateRegistryError(f"{gate_id}: gate_id must start with gate.")
        for field_name in (
            "display_name",
            "category",
            "purpose",
            "failure_mode",
            "operator_status_when_missing",
        ):
            value = template.get(field_name)
            if not isinstance(value, str) or not value:
                raise GateTemplateRegistryError(f"{gate_id}: {field_name} must be non-empty text")
        for field_name in (
            "applies_to",
            "required_inputs",
            "required_receipts",
            "blocks_when_missing",
            "validator_refs",
        ):
            value = template.get(field_name)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
                raise GateTemplateRegistryError(f"{gate_id}: {field_name} must be a non-empty string list")


def _categories(templates: tuple[dict[str, Any], ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for template in templates:
        category = str(template["category"])
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))
