"""Purpose: verify repair template registry admission and read models.
Governance scope: causal repair templates, evidence gates, and operator receipts.
Dependencies: pytest and mcoi_runtime.core.repair_template_registry.
Invariants:
  - Missing templates block admission.
  - External templates require idempotency and confirmation evidence.
  - Rollback and restore templates require sufficient snapshot evidence.
  - Financial/legal templates require approval before admission.
  - Duplicate template keys and ids are rejected.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.causal_repair import (
    EffectClass,
    RepairStrategy,
    ReversibilityClass,
    SnapshotQuality,
)
from mcoi_runtime.core.repair_template_registry import (
    RepairTemplate,
    RepairTemplateAdmissionStatus,
    RepairTemplateKind,
    RepairTemplateRegistry,
    RepairTemplateRegistryError,
    RepairTemplateRisk,
    TemplateSelectionRequest,
)


def test_default_file_edit_template_admits_version_restore_with_required_evidence() -> None:
    registry = RepairTemplateRegistry.default_registry()

    selection = registry.evaluate(
        TemplateSelectionRequest(
            domain="file",
            action_type="edit",
            effect_class=EffectClass.INTERNAL_VERSIONED,
            reversibility_class=ReversibilityClass.VERSION_RESTORE,
            available_evidence=("before_hash", "version_id", "restore_pointer"),
            snapshot_quality=SnapshotQuality.S3_VERSIONED,
        )
    )

    assert selection.status is RepairTemplateAdmissionStatus.ADMITTED
    assert selection.admitted is True
    assert selection.template_id == "repair-template.file.edit.v1"
    assert selection.required_strategy is RepairStrategy.VERSION_RESTORE
    assert selection.missing_evidence == ()
    assert selection.request_id.startswith("repair-template-request-")


def test_email_send_template_blocks_visible_effect_without_idempotency() -> None:
    registry = RepairTemplateRegistry.default_registry()

    selection = registry.evaluate(
        TemplateSelectionRequest(
            domain="email",
            action_type="send",
            effect_class=EffectClass.USER_VISIBLE,
            reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
            available_evidence=("message_id", "recipient_set"),
            snapshot_quality=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
            external_confirmation_present=True,
        )
    )

    assert selection.status is RepairTemplateAdmissionStatus.BLOCKED
    assert selection.admitted is False
    assert selection.reason == "idempotency_key_missing"
    assert selection.missing_evidence == ("idempotency_key",)
    assert selection.required_strategy is RepairStrategy.SEMANTIC_COMPENSATION
    assert selection.template_id == "repair-template.email.send.v1"


def test_payment_charge_template_requires_approval_after_provider_evidence() -> None:
    registry = RepairTemplateRegistry.default_registry()

    selection = registry.evaluate(
        TemplateSelectionRequest(
            domain="payment",
            action_type="charge",
            effect_class=EffectClass.FINANCIAL_OR_LEGAL,
            reversibility_class=ReversibilityClass.RECONCILE_REQUIRED,
            available_evidence=(
                "provider_charge_lookup",
                "customer_authorization",
                "idempotency_key",
            ),
            has_idempotency_key=True,
            snapshot_quality=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
            external_confirmation_present=True,
        )
    )

    assert selection.status is RepairTemplateAdmissionStatus.APPROVAL_REQUIRED
    assert selection.admitted is False
    assert selection.reason == "approval_required"
    assert selection.missing_evidence == ("approval_ref",)
    assert selection.required_strategy is RepairStrategy.RECONCILE_THEN_DECIDE
    assert selection.template_id == "repair-template.payment.charge.v1"


def test_file_edit_template_blocks_weak_snapshot_before_restore_claim() -> None:
    registry = RepairTemplateRegistry.default_registry()

    selection = registry.evaluate(
        TemplateSelectionRequest(
            domain="file",
            action_type="edit",
            effect_class=EffectClass.INTERNAL_VERSIONED,
            reversibility_class=ReversibilityClass.VERSION_RESTORE,
            available_evidence=("before_hash", "version_id", "restore_pointer"),
            snapshot_quality=SnapshotQuality.S2_LOCAL,
        )
    )

    assert selection.status is RepairTemplateAdmissionStatus.BLOCKED
    assert selection.admitted is False
    assert selection.reason == "snapshot_quality_insufficient"
    assert selection.missing_evidence == ("S3_snapshot",)
    assert selection.required_strategy is RepairStrategy.VERSION_RESTORE
    assert selection.evidence_refs == ("before_hash", "version_id", "restore_pointer")


def test_duplicate_template_registration_rejects_key_and_id_collisions() -> None:
    template = _local_rollback_template("repair-template.local.config.v1")
    duplicate_key = _local_rollback_template("repair-template.local.config.v2")
    duplicate_id = RepairTemplate(
        template_id="repair-template.local.config.v1",
        domain="config",
        action_type="patch",
        effect_class=EffectClass.INTERNAL_REVERSIBLE,
        reversibility_class=ReversibilityClass.EXACT_ROLLBACK,
        template_kind=RepairTemplateKind.ROLLBACK,
        risk=RepairTemplateRisk.LOW,
        required_strategy=RepairStrategy.EXACT_ROLLBACK,
        snapshot_quality_minimum=SnapshotQuality.S2_LOCAL,
        rollback_capability_ref="capability://config.rollback_patch",
        required_evidence=("before_hash",),
    )

    with pytest.raises(RepairTemplateRegistryError, match="duplicate repair template key"):
        RepairTemplateRegistry((template, duplicate_key))
    with pytest.raises(RepairTemplateRegistryError, match="duplicate repair template id"):
        RepairTemplateRegistry((template, duplicate_id))
    assert template.template_key == ("config", "update")
    assert duplicate_id.template_key == ("config", "patch")


def test_missing_template_blocks_with_forbid_strategy() -> None:
    registry = RepairTemplateRegistry.default_registry()

    selection = registry.evaluate(
        TemplateSelectionRequest(
            domain="calendar",
            action_type="delete_event",
            effect_class=EffectClass.USER_VISIBLE,
            reversibility_class=ReversibilityClass.SEMANTIC_COMPENSATION,
            available_evidence=("event_id", "idempotency_key"),
            has_idempotency_key=True,
            snapshot_quality=SnapshotQuality.S4_CAUSAL_WITH_EXTERNAL_IDS,
        )
    )

    assert selection.status is RepairTemplateAdmissionStatus.TEMPLATE_MISSING
    assert selection.admitted is False
    assert selection.template_id is None
    assert selection.reason == "repair_template_missing"
    assert selection.required_strategy is RepairStrategy.FORBID
    assert selection.missing_evidence == ()


def test_default_registry_read_model_is_deterministic_and_risk_aware() -> None:
    registry = RepairTemplateRegistry.default_registry()

    read_model = registry.read_model()

    assert read_model["template_count"] == 7
    assert "repair-template.payment.charge.v1" in read_model["template_ids"]
    assert read_model["risk_counts"]["critical"] == 3
    assert read_model["effect_counts"]["user_visible"] == 1
    assert read_model["template_keys"][0] == "deployment.release"
    assert read_model["templates"][0]["template_id"] == "repair-template.deployment.release.v1"


def _local_rollback_template(template_id: str) -> RepairTemplate:
    return RepairTemplate(
        template_id=template_id,
        domain="config",
        action_type="update",
        effect_class=EffectClass.INTERNAL_REVERSIBLE,
        reversibility_class=ReversibilityClass.EXACT_ROLLBACK,
        template_kind=RepairTemplateKind.ROLLBACK,
        risk=RepairTemplateRisk.LOW,
        required_strategy=RepairStrategy.EXACT_ROLLBACK,
        snapshot_quality_minimum=SnapshotQuality.S2_LOCAL,
        rollback_capability_ref="capability://config.rollback_update",
        required_evidence=("before_hash",),
    )
