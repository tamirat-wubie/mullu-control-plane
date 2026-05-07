#!/usr/bin/env python3
"""Governed artifact validation for MCOI examples, pilot assets, and runtime fixtures.

Validates:
  1. Shipped config artifacts deserialize through AppConfig without silent key drift.
  2. Shipped request artifacts normalize through the governed CLI request contract.
  3. Request templates validate without executing adapters or mutating runtime state.
  4. Request action routes are admitted by their paired config artifact or by default config.
  5. Auxiliary pilot JSON artifacts remain inventory-bounded and contract-validated.
  6. MAF runtime fixtures remain inventory-bounded and structurally governed.
  7. MCOI runtime fixtures remain inventory-bounded and structurally governed.
  8. Operator and pilot markdown references stay aligned with governed artifact inventory.
  9. Release and pilot operational documents stay aligned with live profiles, packs, and witnesses.

Usage:
  python scripts/validate_artifacts.py
  python scripts/validate_artifacts.py --strict
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"
MCOI_EXAMPLES_DIR = MCOI_PATH / "examples"
PILOT_EXAMPLES_DIR = REPO_ROOT / "examples" / "pilots"
MAF_RUNTIME_FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "maf_runtime"
MCOI_RUNTIME_FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "mcoi_runtime"

if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.app.cli import _build_operator_request
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.policy_packs import PolicyPackRegistry
from mcoi_runtime.app.profiles import list_profiles
from mcoi_runtime.contracts.document import DocumentVerificationStatus
from mcoi_runtime.core.document import extract_json_fields, ingest_document, verify_extraction
from mcoi_runtime.core.template_validator import TemplateValidationError, TemplateValidator


@dataclass(frozen=True, slots=True)
class ExampleArtifactInventory:
    """Deterministic inventory of governed JSON artifacts."""

    config_paths: tuple[Path, ...]
    request_paths: tuple[Path, ...]
    auxiliary_paths: tuple[Path, ...]
    maf_runtime_fixture_paths: tuple[Path, ...]
    mcoi_runtime_fixture_paths: tuple[Path, ...]
    pilot_directories: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class OperationalDocumentExpectation:
    """Required dynamic and static content for governed non-JSON documents."""

    required_literals: tuple[str, ...] = ()
    forbidden_literals: tuple[str, ...] = ()
    require_all_profiles: bool = False
    require_all_policy_packs: bool = False


AuxiliaryArtifactValidator = Callable[[Path], list[str]]
MAFRuntimeFixtureValidator = Callable[[Path], list[str]]
MCOIRuntimeFixtureValidator = Callable[[Path], list[str]]

JOURNAL_ENTRY_KINDS = frozenset(
    {
        "tick",
        "transition",
        "checkpoint",
        "event_emitted",
        "obligation_changed",
        "reaction_decided",
        "heartbeat",
        "livelock",
        "halt",
        "resume",
    }
)
CHECKPOINT_SCOPES = frozenset(
    {
        "supervisor",
        "event_spine",
        "obligation_runtime",
        "reaction_engine",
        "composite",
    }
)
RESTORE_VERDICTS = frozenset(
    {
        "verified",
        "hash_mismatch",
        "subsystem_missing",
        "rollback_triggered",
    }
)
JOURNAL_VALIDATION_VERDICTS = frozenset(
    {
        "valid",
        "sequence_gap",
        "epoch_mismatch",
        "ordering_violation",
        "empty_journal",
    }
)
REPLAY_STEP_VERDICTS = frozenset(
    {
        "match",
        "outcome_diverged",
        "tick_number_diverged",
        "skipped",
        "error",
    }
)
REPLAY_SESSION_VERDICTS = frozenset(
    {
        "success",
        "divergence_detected",
        "empty_journal",
        "aborted",
    }
)
INCIDENT_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
INCIDENT_STATUSES = frozenset({"open", "recovering", "escalated", "resolved", "closed"})
RECOVERY_ACTIONS = frozenset(
    {"retry", "retry_variant", "reobserve", "replan", "rollback", "escalate", "skip", "no_action"}
)
RECOVERY_DECISION_STATUSES = frozenset(
    {"approved", "blocked_autonomy", "blocked_profile", "blocked_policy", "not_applicable"}
)
CONTINUITY_SCOPES = frozenset({"environment", "service", "connector", "asset", "workspace", "tenant"})
CONTINUITY_STATUSES = frozenset({"active", "draft", "activated", "suspended", "retired"})
RECOVERY_EXECUTION_STATUSES = frozenset({"pending", "in_progress", "completed", "failed", "cancelled"})
DISRUPTION_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
RECOVERY_VERIFICATION_STATUSES = frozenset({"pending", "passed", "failed", "skipped"})
FAILOVER_DISPOSITIONS = frozenset({"initiated", "completed", "failed", "rolled_back"})
DELEGATION_STATUSES = frozenset({"accepted", "rejected", "expired"})
MERGE_OUTCOMES = frozenset({"merged", "conflict_detected", "deferred"})
CONFLICT_STRATEGIES = frozenset({"prefer_latest", "prefer_highest_confidence", "escalate", "manual"})
CASE_STATUSES = frozenset({"open", "in_progress", "under_review", "pending_decision", "closed", "escalated"})
CASE_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
CASE_KINDS = frozenset({"incident", "compliance", "audit", "security", "operational", "legal", "fault_analysis"})
EVIDENCE_STATUSES = frozenset({"pending", "admitted", "reviewed", "challenged", "excluded"})
REVIEW_DISPOSITIONS = frozenset({"requires_review", "accepted", "rejected", "inconclusive", "escalated"})
CASE_CLOSURE_DISPOSITIONS = frozenset({"resolved", "unresolved", "remediated", "escalated", "dismissed"})
HUMAN_TASK_STATUSES = frozenset({"pending", "assigned", "in_progress", "completed", "cancelled", "escalated"})
HUMAN_REVIEW_MODES = frozenset({"single", "parallel", "sequential"})
APPROVAL_MODES = frozenset({"single", "quorum", "unanimous", "override"})
BOARD_DECISION_STATUSES = frozenset({"pending", "approved", "rejected", "escalated", "overridden"})
COLLABORATION_SCOPES = frozenset({"change", "case", "procurement", "service", "regulatory", "executive"})
ATTESTATION_STATUSES = frozenset({"pending", "granted", "denied", "revoked", "expired"})
CERTIFICATION_STATUSES = frozenset({"pending", "active", "suspended", "revoked", "expired", "recertification_required"})
ASSURANCE_LEVELS = frozenset({"none", "low", "moderate", "high", "full"})
ASSURANCE_SCOPES = frozenset({"control", "program", "workspace", "tenant", "connector", "campaign"})
EVIDENCE_SUFFICIENCY_LEVELS = frozenset({"insufficient", "partial", "sufficient", "comprehensive"})
RECERTIFICATION_STATUSES = frozenset({"scheduled", "in_progress", "completed", "overdue", "waived"})
CONTRACT_STATUSES = frozenset({"draft", "active", "suspended", "expired", "terminated", "renewed"})
COMMITMENT_KINDS = frozenset({"sla", "ola", "availability", "response_time", "throughput", "compliance"})
SLA_STATUSES = frozenset({"healthy", "at_risk", "breached", "waived", "closed"})
BREACH_SEVERITIES = frozenset({"minor", "moderate", "major", "critical"})
RENEWAL_STATUSES = frozenset({"scheduled", "in_progress", "completed", "overdue", "declined"})
REMEDY_DISPOSITIONS = frozenset({"pending", "credit_issued", "penalty_applied", "waived", "escalated", "closed"})
ASSET_STATUSES = frozenset({"active", "inactive", "maintenance", "retired", "disposed"})
ASSET_KINDS = frozenset({"hardware", "software", "license", "service", "infrastructure", "data"})
CONFIGURATION_ITEM_STATUSES = frozenset({"active", "pending", "deprecated", "archived"})
INVENTORY_DISPOSITIONS = frozenset({"available", "assigned", "reserved", "depleted", "expired"})
OWNERSHIP_TYPES = frozenset({"owned", "leased", "licensed", "shared", "vendor_managed"})
LIFECYCLE_DISPOSITIONS = frozenset({"provisioned", "deployed", "upgraded", "decommissioned", "transferred", "renewed"})
BILLING_STATUSES = frozenset({"active", "suspended", "closed", "delinquent"})
INVOICE_STATUSES = frozenset({"draft", "issued", "paid", "overdue", "disputed", "voided"})
CHARGE_KINDS = frozenset({"service", "usage", "subscription", "overage", "setup", "professional_services"})
CREDIT_DISPOSITIONS = frozenset({"pending", "applied", "expired", "voided"})
DISPUTE_STATUSES = frozenset({"open", "under_review", "resolved_accepted", "resolved_rejected", "withdrawn"})
PAYMENT_STATUSES = frozenset({"pending", "cleared", "failed", "reversed"})
SETTLEMENT_STATUSES = frozenset({"open", "partial", "settled", "disputed", "written_off"})
COLLECTION_STATUSES = frozenset({"open", "in_progress", "paused", "resolved", "escalated", "closed"})
WRITEOFF_DISPOSITIONS = frozenset({"pending", "approved", "rejected", "reversed"})
PAYMENT_METHOD_KINDS = frozenset({"bank_transfer", "credit_card", "check", "wire", "ach", "crypto"})
DUNNING_SEVERITIES = frozenset({"reminder", "warning", "final_notice", "escalation"})
CUSTOMER_STATUSES = frozenset({"active", "inactive", "suspended", "churned", "prospect"})
ACCOUNT_STATUSES = frozenset({"active", "suspended", "closed", "delinquent", "pending"})
PRODUCT_STATUSES = frozenset({"active", "draft", "deprecated", "retired"})
ENTITLEMENT_STATUSES = frozenset({"active", "expired", "revoked", "suspended"})
ACCOUNT_HEALTH_STATUSES = frozenset({"healthy", "at_risk", "degraded", "critical"})
CUSTOMER_DISPOSITIONS = frozenset({"approved", "denied", "escalated", "deferred"})
PARTNER_STATUSES = frozenset({"active", "inactive", "suspended", "terminated", "prospect"})
PARTNER_KINDS = frozenset(
    {
        "reseller",
        "distributor",
        "service_partner",
        "technology_partner",
        "referral",
        "managed_service",
    }
)
ECOSYSTEM_ROLES = frozenset({"provider", "consumer", "intermediary", "integrator"})
REVENUE_SHARE_STATUSES = frozenset({"pending", "active", "settled", "disputed", "cancelled"})
PARTNER_HEALTH_STATUSES = frozenset({"healthy", "at_risk", "degraded", "critical"})
PARTNER_DISPOSITIONS = frozenset({"approved", "denied", "escalated", "deferred"})
OFFERING_STATUSES = frozenset({"draft", "active", "suspended", "retired"})
OFFERING_KINDS = frozenset({"standalone", "bundle", "add_on", "trial", "custom"})
BUNDLE_DISPOSITIONS = frozenset({"valid", "invalid", "partial", "expired"})
ELIGIBILITY_STATUSES = frozenset({"eligible", "ineligible", "requires_approval", "expired"})
MARKETPLACE_CHANNELS = frozenset({"direct", "partner", "marketplace", "internal", "api"})
PRICING_DISPOSITIONS = frozenset({"standard", "discounted", "promotional", "negotiated"})
VENDOR_STATUSES = frozenset({"active", "suspended", "blocked", "terminated", "under_review"})
PROCUREMENT_REQUEST_STATUSES = frozenset(
    {"draft", "submitted", "approved", "denied", "cancelled", "fulfilled"}
)
PURCHASE_ORDER_STATUSES = frozenset(
    {"draft", "issued", "acknowledged", "fulfilled", "cancelled", "disputed"}
)
VENDOR_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
RENEWAL_DISPOSITIONS = frozenset({"pending", "approved", "denied", "deferred", "auto_renewed"})
PROCUREMENT_DECISION_STATUSES = frozenset({"pending", "approved", "denied", "escalated"})
BUDGET_SCOPES = frozenset({"global", "portfolio", "campaign", "connector", "channel", "team", "function"})
FINANCIAL_COST_CATEGORIES = frozenset(
    {
        "connector_call",
        "communication",
        "artifact_parsing",
        "provider_routing",
        "compute",
        "human_labor",
        "escalation",
        "overhead",
    }
)
SPEND_STATUSES = frozenset({"reserved", "consumed", "released", "cancelled", "refunded"})
APPROVAL_THRESHOLD_MODES = frozenset(
    {"per_transaction", "cumulative", "percentage_of_limit", "remaining_budget"}
)
CHARGE_DISPOSITIONS = frozenset(
    {
        "approved",
        "denied_hard_stop",
        "denied_insufficient",
        "pending_approval",
        "warning_issued",
        "fallback_suggested",
    }
)
BUDGET_CONFLICT_KINDS = frozenset(
    {
        "over_limit",
        "currency_mismatch",
        "double_reservation",
        "orphaned_reservation",
        "negative_balance",
        "threshold_breach",
    }
)
LEDGER_STATUSES = frozenset({"active", "suspended", "closed", "archived"})
LEDGER_NETWORK_KINDS = frozenset({"private", "consortium", "public", "hybrid"})
SETTLEMENT_PROOF_STATUSES = frozenset({"pending", "confirmed", "failed", "disputed"})
ANCHOR_DISPOSITIONS = frozenset({"anchored", "pending", "failed", "revoked"})
WALLET_STATUSES = frozenset({"active", "frozen", "closed", "compromised"})
LEDGER_VIOLATION_KINDS = frozenset(
    {"proof_failed", "anchor_expired", "wallet_compromised", "settlement_disputed"}
)


def _sort_paths(paths: list[Path]) -> tuple[Path, ...]:
    return tuple(sorted(paths, key=lambda path: path.relative_to(REPO_ROOT).as_posix()))


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_relative_path(path)}: invalid {kind} JSON: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"{_relative_path(path)}: cannot read {kind} artifact: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{_relative_path(path)}: {kind} JSON root must be an object")
    return payload


def _validate_iso8601_text(value: Any, *, field_name: str, path: Path) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{_relative_path(path)}: field '{field_name}' must be a non-empty ISO 8601 string"]
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return [f"{_relative_path(path)}: field '{field_name}' must be a valid ISO 8601 string"]
    return []


def _parse_iso8601_text(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _require_non_empty_text(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, str) and value.strip():
        return []
    return [f"{_relative_path(path)}: field '{field_name}' must be a non-empty string"]


def _require_positive_int(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be a positive integer"]
    return []


def _require_non_negative_int(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be a non-negative integer"]
    return []


def _require_number_in_range(
    value: Any,
    *,
    field_name: str,
    path: Path,
    minimum: float,
    maximum: float,
) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return [f"{_relative_path(path)}: field '{field_name}' must be a numeric value"]
    if value < minimum or value > maximum:
        return [
            f"{_relative_path(path)}: field '{field_name}' must be between {minimum} and {maximum}"
        ]
    return []


def _validate_currency_code(value: Any, *, field_name: str, path: Path) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{_relative_path(path)}: field '{field_name}' must be a non-empty 3-letter currency code"]
    if len(value) != 3 or not value.isalpha() or not value.isupper():
        return [f"{_relative_path(path)}: field '{field_name}' must be a 3-letter uppercase currency code"]
    return []


def _validate_sha256_hash_text(value: Any, *, field_name: str, path: Path) -> list[str]:
    errors = _require_non_empty_text(value, field_name=field_name, path=path)
    if errors:
        return errors
    if not value.startswith("sha256:"):
        return [f"{_relative_path(path)}: field '{field_name}' must be a sha256-prefixed hash"]
    return []


def _validate_exact_object_fields(
    payload: dict[str, Any],
    *,
    path: Path,
    expected_fields: tuple[str, ...],
    kind: str,
) -> list[str]:
    errors: list[str] = []
    unknown_fields = sorted(set(payload) - set(expected_fields))
    missing_fields = tuple(field for field in expected_fields if field not in payload)
    if unknown_fields:
        errors.append(
            f"{_relative_path(path)}: unexpected {kind} fields: {', '.join(unknown_fields)}"
        )
    if missing_fields:
        errors.append(f"{_relative_path(path)}: missing {kind} fields: {', '.join(missing_fields)}")
    return errors


def _validate_document_to_action_input(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="pilot auxiliary")
    errors: list[str] = []
    expected_keys = ("task", "target", "retention_days", "notify_email")

    unknown_keys = sorted(set(payload) - set(expected_keys))
    if unknown_keys:
        errors.append(
            f"{_relative_path(path)}: unexpected auxiliary fields: {', '.join(unknown_keys)}"
        )

    missing_keys = tuple(key for key in expected_keys if key not in payload)
    if missing_keys:
        errors.append(
            f"{_relative_path(path)}: missing auxiliary fields: {', '.join(missing_keys)}"
        )
        return errors

    errors.extend(_require_non_empty_text(payload["task"], field_name="task", path=path))
    errors.extend(_require_non_empty_text(payload["target"], field_name="target", path=path))
    errors.extend(_require_positive_int(payload["retention_days"], field_name="retention_days", path=path))
    errors.extend(_require_non_empty_text(payload["notify_email"], field_name="notify_email", path=path))
    if errors:
        return errors

    content = path.read_text(encoding="utf-8")
    document_one = ingest_document(
        "pilot-document-to-action-input",
        _relative_path(path),
        content,
    )
    document_two = ingest_document(
        "pilot-document-to-action-input",
        _relative_path(path),
        content,
    )
    extraction = extract_json_fields(document_one, expected_keys)
    verification = verify_extraction(extraction, expected_keys)

    if document_one.fingerprint.content_hash != document_two.fingerprint.content_hash:
        errors.append(f"{_relative_path(path)}: document fingerprint must be deterministic")
    if extraction.extracted_count != len(expected_keys):
        errors.append(f"{_relative_path(path)}: extracted_count must equal expected field count")
    if extraction.missing_count != 0:
        errors.append(f"{_relative_path(path)}: extraction must not miss required pilot fields")
    if extraction.malformed_count != 0:
        errors.append(f"{_relative_path(path)}: extraction must not mark pilot fields malformed")
    if verification.status is not DocumentVerificationStatus.PASS:
        errors.append(f"{_relative_path(path)}: verification must pass for the shipped pilot document")

    return errors


AUXILIARY_PILOT_VALIDATORS: dict[str, AuxiliaryArtifactValidator] = {
    "examples/pilots/document_to_action/input_document.json": _validate_document_to_action_input,
}


def _validate_event_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_event_record_fixture_dict(payload, path=path, field_name="runtime fixture")


def _validate_event_record_fixture_dict(
    payload: object,
    *,
    path: Path,
    field_name: str,
) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "event_id",
            "event_type",
            "source",
            "correlation_id",
            "payload",
            "emitted_at",
        ),
        kind=field_name,
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["event_id"], field_name="event_id", path=path))
    errors.extend(_require_non_empty_text(payload["event_type"], field_name="event_type", path=path))
    errors.extend(_require_non_empty_text(payload["source"], field_name="source", path=path))
    errors.extend(
        _require_non_empty_text(payload["correlation_id"], field_name="correlation_id", path=path)
    )
    errors.extend(_validate_iso8601_text(payload["emitted_at"], field_name="emitted_at", path=path))
    if not isinstance(payload["payload"], dict) or not payload["payload"]:
        errors.append(f"{_relative_path(path)}: field 'payload' must be a non-empty object")
    return errors


def _validate_event_envelope_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "envelope_id",
            "event",
            "target_subsystems",
            "priority",
            "delivered",
            "delivered_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["envelope_id"], field_name="envelope_id", path=path))
    errors.extend(
        _validate_event_record_fixture_dict(payload["event"], path=path, field_name="event")
    )
    target_subsystems = payload["target_subsystems"]
    if not isinstance(target_subsystems, list) or not target_subsystems:
        errors.append(f"{_relative_path(path)}: field 'target_subsystems' must be a non-empty array")
    else:
        for index, subsystem in enumerate(target_subsystems):
            errors.extend(
                _require_non_empty_text(
                    subsystem,
                    field_name=f"target_subsystems[{index}]",
                    path=path,
                )
            )
    errors.extend(_require_non_negative_int(payload["priority"], field_name="priority", path=path))
    if not isinstance(payload["delivered"], bool):
        errors.append(f"{_relative_path(path)}: field 'delivered' must be boolean")
    errors.extend(
        _validate_iso8601_text(payload["delivered_at"], field_name="delivered_at", path=path)
    )
    return errors


def _validate_event_subscription_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "subscription_id",
            "event_type",
            "subscriber_id",
            "reaction_id",
            "filter_source",
            "active",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("subscription_id", "event_type", "subscriber_id", "reaction_id", "filter_source"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["active"], bool):
        errors.append(f"{_relative_path(path)}: field 'active' must be boolean")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_event_reaction_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "reaction_id",
            "event_id",
            "subscription_id",
            "action_taken",
            "result",
            "reacted_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("reaction_id", "event_id", "subscription_id", "action_taken", "result"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["reacted_at"], field_name="reacted_at", path=path))
    return errors


def _validate_event_window_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "window_id",
            "correlation_id",
            "window_start",
            "window_end",
            "event_count",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["window_id"], field_name="window_id", path=path))
    errors.extend(
        _require_non_empty_text(payload["correlation_id"], field_name="correlation_id", path=path)
    )
    errors.extend(_validate_iso8601_text(payload["window_start"], field_name="window_start", path=path))
    errors.extend(_validate_iso8601_text(payload["window_end"], field_name="window_end", path=path))
    errors.extend(_require_non_negative_int(payload["event_count"], field_name="event_count", path=path))
    return errors


def _validate_event_correlation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "correlation_id",
            "event_ids",
            "root_event_id",
            "description",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(
        _require_non_empty_text(payload["correlation_id"], field_name="correlation_id", path=path)
    )
    errors.extend(_require_non_empty_text(payload["root_event_id"], field_name="root_event_id", path=path))
    errors.extend(_require_non_empty_text(payload["description"], field_name="description", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))

    event_ids = payload["event_ids"]
    if not isinstance(event_ids, list) or not event_ids:
        errors.append(f"{_relative_path(path)}: field 'event_ids' must be a non-empty array")
    else:
        for index, event_id in enumerate(event_ids):
            errors.extend(
                _require_non_empty_text(event_id, field_name=f"event_ids[{index}]", path=path)
            )
        if isinstance(payload["root_event_id"], str) and payload["root_event_id"] not in event_ids:
            errors.append(f"{_relative_path(path)}: root_event_id must be present in event_ids")
    return errors


def _validate_supervisor_tick_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "tick_id",
            "tick_number",
            "phase_sequence",
            "events_polled",
            "obligations_evaluated",
            "deadlines_checked",
            "reactions_fired",
            "decisions",
            "outcome",
            "errors",
            "started_at",
            "completed_at",
            "duration_ms",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["tick_id"], field_name="tick_id", path=path))
    errors.extend(_require_non_negative_int(payload["tick_number"], field_name="tick_number", path=path))
    for field_name in (
        "events_polled",
        "obligations_evaluated",
        "deadlines_checked",
        "reactions_fired",
        "duration_ms",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("started_at", "completed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_empty_text(payload["outcome"], field_name="outcome", path=path))

    phase_sequence = payload["phase_sequence"]
    if not isinstance(phase_sequence, list) or not phase_sequence:
        errors.append(f"{_relative_path(path)}: field 'phase_sequence' must be a non-empty array")
    else:
        for index, phase in enumerate(phase_sequence):
            if not isinstance(phase, str) or not phase.strip():
                errors.append(
                    f"{_relative_path(path)}: phase_sequence[{index}] must be a non-empty string"
                )

    decision_fields = (
        "decision_id",
        "action_type",
        "target_id",
        "reason",
        "governance_approved",
        "decided_at",
        "metadata",
    )
    decisions = payload["decisions"]
    if not isinstance(decisions, list):
        errors.append(f"{_relative_path(path)}: field 'decisions' must be an array")
    else:
        for index, decision in enumerate(decisions):
            if not isinstance(decision, dict):
                errors.append(f"{_relative_path(path)}: decisions[{index}] must be an object")
                continue
            nested_errors = _validate_exact_object_fields(
                decision,
                path=path,
                expected_fields=decision_fields,
                kind=f"decision[{index}]",
            )
            if nested_errors:
                errors.extend(nested_errors)
                continue
            for field_name in ("decision_id", "action_type", "target_id", "reason"):
                errors.extend(
                    _require_non_empty_text(
                        decision[field_name],
                        field_name=f"decisions[{index}].{field_name}",
                        path=path,
                    )
                )
            if not isinstance(decision["governance_approved"], bool):
                errors.append(
                    f"{_relative_path(path)}: field 'decisions[{index}].governance_approved' must be boolean"
                )
            errors.extend(
                _validate_iso8601_text(
                    decision["decided_at"],
                    field_name=f"decisions[{index}].decided_at",
                    path=path,
                )
            )
            if not isinstance(decision["metadata"], dict):
                errors.append(
                    f"{_relative_path(path)}: field 'decisions[{index}].metadata' must be an object"
                )

    error_values = payload["errors"]
    if not isinstance(error_values, list):
        errors.append(f"{_relative_path(path)}: field 'errors' must be an array")
    else:
        for index, error_value in enumerate(error_values):
            if not isinstance(error_value, str) or not error_value.strip():
                errors.append(f"{_relative_path(path)}: errors[{index}] must be a non-empty string")

    return errors


def _validate_simulation_comparison_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "comparison_id",
            "request_id",
            "ranked_option_ids",
            "scores",
            "top_risk_level",
            "review_burden",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(
        _require_non_empty_text(payload["comparison_id"], field_name="comparison_id", path=path)
    )
    errors.extend(_require_non_empty_text(payload["request_id"], field_name="request_id", path=path))
    errors.extend(
        _require_non_empty_text(payload["top_risk_level"], field_name="top_risk_level", path=path)
    )
    errors.extend(
        _require_number_in_range(
            payload["review_burden"],
            field_name="review_burden",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )

    ranked_option_ids = payload["ranked_option_ids"]
    if not isinstance(ranked_option_ids, list) or not ranked_option_ids:
        errors.append(f"{_relative_path(path)}: field 'ranked_option_ids' must be a non-empty array")
    else:
        for index, option_id in enumerate(ranked_option_ids):
            if not isinstance(option_id, str) or not option_id.strip():
                errors.append(
                    f"{_relative_path(path)}: ranked_option_ids[{index}] must be a non-empty string"
                )
        if len(set(ranked_option_ids)) != len(ranked_option_ids):
            errors.append(f"{_relative_path(path)}: ranked_option_ids must not contain duplicates")

    scores = payload["scores"]
    if not isinstance(scores, dict) or not scores:
        errors.append(f"{_relative_path(path)}: field 'scores' must be a non-empty object")
    else:
        for option_id, score in scores.items():
            if not isinstance(option_id, str) or not option_id.strip():
                errors.append(f"{_relative_path(path)}: scores keys must be non-empty strings")
                break
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                errors.append(
                    f"{_relative_path(path)}: score for option '{option_id}' must be numeric"
                )
        if isinstance(ranked_option_ids, list) and ranked_option_ids:
            if set(scores.keys()) != set(ranked_option_ids):
                errors.append(
                    f"{_relative_path(path)}: scores keys must match ranked_option_ids exactly"
                )

    return errors


def _validate_job_descriptor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "job_id",
            "name",
            "description",
            "priority",
            "created_at",
            "goal_id",
            "workflow_id",
            "deadline",
            "sla_target_minutes",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in (
        "job_id",
        "name",
        "description",
        "priority",
        "goal_id",
        "workflow_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("created_at", "deadline"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_positive_int(
            payload["sla_target_minutes"],
            field_name="sla_target_minutes",
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    return errors


def _validate_work_queue_entry_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "entry_id",
            "job_id",
            "priority",
            "enqueued_at",
            "assigned_to_person_id",
            "assigned_to_team_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "entry_id",
        "job_id",
        "priority",
        "assigned_to_person_id",
        "assigned_to_team_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["enqueued_at"], field_name="enqueued_at", path=path))
    return errors


def _validate_assignment_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assignment_id",
            "job_id",
            "assigned_to_id",
            "assigned_by_id",
            "assigned_at",
            "reason",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "assignment_id",
        "job_id",
        "assigned_to_id",
        "assigned_by_id",
        "reason",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["assigned_at"], field_name="assigned_at", path=path))
    return errors


def _validate_job_state_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "job_id",
            "status",
            "sla_status",
            "current_assignment_id",
            "pause_reason",
            "thread_id",
            "goal_id",
            "workflow_id",
            "started_at",
            "updated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "job_id",
        "status",
        "sla_status",
        "current_assignment_id",
        "pause_reason",
        "thread_id",
        "goal_id",
        "workflow_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("started_at", "updated_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_follow_up_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("follow_up_id", "job_id", "reason", "scheduled_at", "resolved", "executed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("follow_up_id", "job_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("scheduled_at", "executed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["resolved"], bool):
        errors.append(f"{_relative_path(path)}: field 'resolved' must be boolean")
    return errors


def _validate_deadline_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("job_id", "deadline", "sla_status", "evaluated_at", "sla_target_minutes"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("job_id", "sla_status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("deadline", "evaluated_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_positive_int(
            payload["sla_target_minutes"],
            field_name="sla_target_minutes",
            path=path,
        )
    )
    return errors


def _validate_job_execution_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "job_id",
            "execution_id",
            "status",
            "started_at",
            "outcome_summary",
            "errors",
            "completed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("job_id", "execution_id", "status", "outcome_summary"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("started_at", "completed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    errors_list = payload["errors"]
    if not isinstance(errors_list, list):
        errors.append(f"{_relative_path(path)}: field 'errors' must be an array")
    else:
        for index, error_value in enumerate(errors_list):
            errors.extend(_require_non_empty_text(error_value, field_name=f"errors[{index}]", path=path))
    return errors


def _validate_job_pause_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("job_id", "paused_at", "reason", "resumed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("job_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("paused_at", "resumed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_job_resume_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("job_id", "resumed_at", "resumed_by_id", "reason"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("job_id", "resumed_by_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["resumed_at"], field_name="resumed_at", path=path))
    return errors


def _validate_goal_descriptor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("goal_id", "description", "priority", "created_at", "deadline", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("goal_id", "description", "priority"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("created_at", "deadline"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_goal_dependency_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("goal_id", "depends_on_goal_id", "dependency_type"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("goal_id", "depends_on_goal_id", "dependency_type"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_sub_goal_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_sub_goal_dict(payload, path=path, field_name="runtime fixture")


def _validate_sub_goal_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "sub_goal_id",
            "goal_id",
            "description",
            "status",
            "skill_id",
            "workflow_id",
            "predecessors",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("sub_goal_id", "goal_id", "description", "status", "skill_id", "workflow_id"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    predecessors = payload["predecessors"]
    predecessors_field_name = f"{prefix}predecessors".strip(".")
    if not isinstance(predecessors, list):
        errors.append(f"{_relative_path(path)}: field '{predecessors_field_name}' must be an array")
    else:
        for index, predecessor in enumerate(predecessors):
            errors.extend(
                _require_non_empty_text(
                    predecessor,
                    field_name=f"{predecessors_field_name}[{index}]",
                    path=path,
                )
            )
    return errors


def _validate_goal_execution_state_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "goal_id",
            "status",
            "updated_at",
            "current_plan_id",
            "completed_sub_goals",
            "failed_sub_goals",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("goal_id", "status", "current_plan_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["updated_at"], field_name="updated_at", path=path))
    for list_name in ("completed_sub_goals", "failed_sub_goals"):
        values = payload[list_name]
        if not isinstance(values, list):
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be an array")
        else:
            for index, value in enumerate(values):
                errors.extend(_require_non_empty_text(value, field_name=f"{list_name}[{index}]", path=path))
            if len(set(values)) != len(values):
                errors.append(f"{_relative_path(path)}: {list_name} must not contain duplicates")
    if isinstance(payload["completed_sub_goals"], list) and isinstance(payload["failed_sub_goals"], list):
        overlap = set(payload["completed_sub_goals"]) & set(payload["failed_sub_goals"])
        if overlap:
            errors.append(
                f"{_relative_path(path)}: sub-goal IDs appear in both completed and failed: {sorted(overlap)}"
            )
    return errors


def _validate_goal_replan_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("goal_id", "previous_plan_id", "new_plan_id", "reason", "replanned_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("goal_id", "previous_plan_id", "new_plan_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["replanned_at"], field_name="replanned_at", path=path))
    return errors


def _validate_workflow_stage_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_workflow_stage_dict(payload, path=path, field_name="runtime fixture")


def _validate_workflow_stage_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("stage_id", "stage_type", "skill_id", "description", "predecessors", "timeout_seconds"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("stage_id", "stage_type", "skill_id", "description"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    predecessors = payload["predecessors"]
    predecessors_field_name = f"{prefix}predecessors".strip(".")
    if not isinstance(predecessors, list):
        errors.append(f"{_relative_path(path)}: field '{predecessors_field_name}' must be an array")
    else:
        for index, predecessor in enumerate(predecessors):
            errors.extend(
                _require_non_empty_text(
                    predecessor,
                    field_name=f"{predecessors_field_name}[{index}]",
                    path=path,
                )
            )
    errors.extend(
        _require_positive_int(
            payload["timeout_seconds"],
            field_name=f"{prefix}timeout_seconds".strip("."),
            path=path,
        )
    )
    return errors


def _validate_workflow_binding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_workflow_binding_dict(payload, path=path, field_name="runtime fixture")


def _validate_workflow_binding_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "binding_id",
            "source_stage_id",
            "source_output_key",
            "target_stage_id",
            "target_input_key",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in (
        "binding_id",
        "source_stage_id",
        "source_output_key",
        "target_stage_id",
        "target_input_key",
    ):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    return errors


def _validate_workflow_descriptor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("workflow_id", "name", "description", "stages", "bindings", "created_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("workflow_id", "name", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    stages = payload["stages"]
    if not isinstance(stages, list) or not stages:
        errors.append(f"{_relative_path(path)}: field 'stages' must be a non-empty array")
        return errors
    stage_ids: set[str] = set()
    for index, stage in enumerate(stages):
        errors.extend(
            _validate_workflow_stage_dict(
                stage,
                path=path,
                field_name=f"stages[{index}]",
            )
        )
        if isinstance(stage, dict) and isinstance(stage.get("stage_id"), str):
            stage_id = stage["stage_id"]
            if stage_id in stage_ids:
                errors.append(f"{_relative_path(path)}: stages must not repeat stage_id '{stage_id}'")
            stage_ids.add(stage_id)
    for index, stage in enumerate(stages):
        if isinstance(stage, dict):
            for predecessor in stage.get("predecessors", []):
                if predecessor not in stage_ids:
                    errors.append(
                        f"{_relative_path(path)}: stages[{index}].predecessors references unknown stage_id '{predecessor}'"
                    )
                elif predecessor == stage.get("stage_id"):
                    errors.append(
                        f"{_relative_path(path)}: stages[{index}] must not list itself as a predecessor"
                    )
    bindings = payload["bindings"]
    if not isinstance(bindings, list):
        errors.append(f"{_relative_path(path)}: field 'bindings' must be an array")
    else:
        for index, binding in enumerate(bindings):
            errors.extend(
                _validate_workflow_binding_dict(
                    binding,
                    path=path,
                    field_name=f"bindings[{index}]",
                )
            )
            if isinstance(binding, dict):
                source_stage_id = binding.get("source_stage_id")
                target_stage_id = binding.get("target_stage_id")
                if isinstance(source_stage_id, str) and source_stage_id not in stage_ids:
                    errors.append(
                        f"{_relative_path(path)}: bindings[{index}].source_stage_id references unknown stage_id '{source_stage_id}'"
                    )
                if isinstance(target_stage_id, str) and target_stage_id not in stage_ids:
                    errors.append(
                        f"{_relative_path(path)}: bindings[{index}].target_stage_id references unknown stage_id '{target_stage_id}'"
                    )
    return errors


def _validate_workflow_transition_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("from_stage_id", "to_stage_id", "transition_type", "condition"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("from_stage_id", "to_stage_id", "transition_type", "condition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_stage_execution_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_stage_execution_result_dict(payload, path=path, field_name="runtime fixture")


def _validate_stage_execution_result_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    required_fields = {"stage_id", "status", "output", "started_at", "completed_at"}
    optional_fields = {"error"}
    actual_fields = set(payload)
    missing_fields = sorted(required_fields - actual_fields)
    unexpected_fields = sorted(actual_fields - required_fields - optional_fields)
    errors: list[str] = []
    if missing_fields:
        errors.append(
            f"{_relative_path(path)}: {field_name} missing required fields {', '.join(repr(name) for name in missing_fields)}"
        )
    if unexpected_fields:
        errors.append(
            f"{_relative_path(path)}: {field_name} has unexpected fields {', '.join(repr(name) for name in unexpected_fields)}"
        )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("stage_id", "status"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
    )
    if not isinstance(payload["output"], dict):
        errors.append(f"{_relative_path(path)}: field '{f'{prefix}output'.strip('.')}' must be an object")
    if "error" in payload and payload["error"] is not None and isinstance(payload["error"], (str, int, float, bool)):
        # Allow null or structured JSON objects/arrays, but reject scalar drift.
        errors.append(f"{_relative_path(path)}: field '{f'{prefix}error'.strip('.')}' must be null or structured JSON")
    for nested_field_name in ("started_at", "completed_at"):
        errors.extend(
            _validate_iso8601_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    return errors


def _validate_workflow_execution_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("workflow_id", "execution_id", "status", "stage_results", "started_at", "completed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("workflow_id", "execution_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    stage_results = payload["stage_results"]
    if not isinstance(stage_results, list):
        errors.append(f"{_relative_path(path)}: field 'stage_results' must be an array")
    else:
        for index, stage_result in enumerate(stage_results):
            errors.extend(
                _validate_stage_execution_result_dict(
                    stage_result,
                    path=path,
                    field_name=f"stage_results[{index}]",
                )
            )
    for field_name in ("started_at", "completed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_workflow_verification_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("execution_id", "verified", "mismatch_reasons", "verified_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["execution_id"], field_name="execution_id", path=path))
    if not isinstance(payload["verified"], bool):
        errors.append(f"{_relative_path(path)}: field 'verified' must be boolean")
    mismatch_reasons = payload["mismatch_reasons"]
    if not isinstance(mismatch_reasons, list):
        errors.append(f"{_relative_path(path)}: field 'mismatch_reasons' must be an array")
    else:
        for index, reason in enumerate(mismatch_reasons):
            errors.extend(_require_non_empty_text(reason, field_name=f"mismatch_reasons[{index}]", path=path))
    errors.extend(_validate_iso8601_text(payload["verified_at"], field_name="verified_at", path=path))
    return errors


def _validate_goal_plan_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("plan_id", "goal_id", "sub_goals", "created_at", "version"),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["plan_id"], field_name="plan_id", path=path))
    errors.extend(_require_non_empty_text(payload["goal_id"], field_name="goal_id", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    errors.extend(_require_positive_int(payload["version"], field_name="version", path=path))

    sub_goals = payload["sub_goals"]
    if not isinstance(sub_goals, list) or not sub_goals:
        errors.append(f"{_relative_path(path)}: field 'sub_goals' must be a non-empty array")
        return errors

    sub_goal_fields = (
        "sub_goal_id",
        "goal_id",
        "description",
        "status",
        "skill_id",
        "workflow_id",
        "predecessors",
    )
    sub_goal_ids: list[str] = []
    predecessor_pairs: list[tuple[str, list[str]]] = []
    for index, sub_goal in enumerate(sub_goals):
        if not isinstance(sub_goal, dict):
            errors.append(f"{_relative_path(path)}: sub_goals[{index}] must be an object")
            continue
        nested_errors = _validate_exact_object_fields(
            sub_goal,
            path=path,
            expected_fields=sub_goal_fields,
            kind=f"sub_goal[{index}]",
        )
        if nested_errors:
            errors.extend(nested_errors)
            continue
        for field_name in ("sub_goal_id", "goal_id", "description", "status", "skill_id", "workflow_id"):
            errors.extend(
                _require_non_empty_text(
                    sub_goal[field_name],
                    field_name=f"sub_goals[{index}].{field_name}",
                    path=path,
                )
            )
        predecessors = sub_goal["predecessors"]
        if not isinstance(predecessors, list):
            errors.append(f"{_relative_path(path)}: sub_goals[{index}].predecessors must be an array")
        else:
            for predecessor_index, predecessor in enumerate(predecessors):
                if not isinstance(predecessor, str) or not predecessor.strip():
                    errors.append(
                        f"{_relative_path(path)}: sub_goals[{index}].predecessors[{predecessor_index}] must be a non-empty string"
                    )
        sub_goal_id = sub_goal["sub_goal_id"]
        sub_goal_ids.append(sub_goal_id)
        predecessor_pairs.append((sub_goal_id, list(predecessors) if isinstance(predecessors, list) else []))

    known_ids = set(sub_goal_ids)
    if len(known_ids) != len(sub_goal_ids):
        errors.append(f"{_relative_path(path)}: sub_goals must have unique sub_goal_id values")
    for sub_goal_id, predecessors in predecessor_pairs:
        for predecessor in predecessors:
            if predecessor not in known_ids:
                errors.append(
                    f"{_relative_path(path)}: sub_goal '{sub_goal_id}' references unknown predecessor '{predecessor}'"
                )
            elif predecessor == sub_goal_id:
                errors.append(
                    f"{_relative_path(path)}: sub_goal '{sub_goal_id}' must not list itself as a predecessor"
                )

    return errors


def _validate_obligation_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "obligation_id",
            "trigger",
            "trigger_ref_id",
            "state",
            "owner",
            "deadline",
            "description",
            "correlation_id",
            "metadata",
            "created_at",
            "updated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in (
        "obligation_id",
        "trigger",
        "trigger_ref_id",
        "state",
        "description",
        "correlation_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("created_at", "updated_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    errors.extend(
        _validate_obligation_owner_dict(payload["owner"], path=path, field_name="owner")
    )

    deadline = payload["deadline"]
    if not isinstance(deadline, dict):
        errors.append(f"{_relative_path(path)}: field 'deadline' must be an object")
    else:
        deadline_errors = _validate_exact_object_fields(
            deadline,
            path=path,
            expected_fields=("deadline_id", "due_at", "warn_at", "hard"),
            kind="deadline",
        )
        if deadline_errors:
            errors.extend(deadline_errors)
        else:
            errors.extend(
                _require_non_empty_text(
                    deadline["deadline_id"],
                    field_name="deadline.deadline_id",
                    path=path,
                )
            )
            errors.extend(
                _validate_iso8601_text(deadline["due_at"], field_name="deadline.due_at", path=path)
            )
            errors.extend(
                _validate_iso8601_text(
                    deadline["warn_at"],
                    field_name="deadline.warn_at",
                    path=path,
                )
            )
            if not isinstance(deadline["hard"], bool):
                errors.append(f"{_relative_path(path)}: field 'deadline.hard' must be boolean")

    return errors


def _validate_obligation_owner_dict(owner: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(owner, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        owner,
        path=path,
        expected_fields=("owner_id", "owner_type", "display_name"),
        kind=field_name,
    )
    if errors:
        return errors
    for nested_field_name in ("owner_id", "owner_type", "display_name"):
        errors.extend(
            _require_non_empty_text(
                owner[nested_field_name],
                field_name=f"{field_name}.{nested_field_name}",
                path=path,
            )
        )
    return errors


def _validate_obligation_closure_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "closure_id",
            "obligation_id",
            "final_state",
            "reason",
            "closed_by",
            "closed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("closure_id", "obligation_id", "final_state", "reason", "closed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if payload["final_state"] not in {"completed", "expired", "cancelled"}:
        errors.append(
            f"{_relative_path(path)}: final_state must be one of completed, expired, or cancelled"
        )
    return errors


def _validate_obligation_transfer_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "transfer_id",
            "obligation_id",
            "from_owner",
            "to_owner",
            "reason",
            "transferred_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("transfer_id", "obligation_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _validate_obligation_owner_dict(payload["from_owner"], path=path, field_name="from_owner")
    )
    errors.extend(
        _validate_obligation_owner_dict(payload["to_owner"], path=path, field_name="to_owner")
    )
    errors.extend(
        _validate_iso8601_text(payload["transferred_at"], field_name="transferred_at", path=path)
    )
    from_owner = payload["from_owner"]
    to_owner = payload["to_owner"]
    if (
        isinstance(from_owner, dict)
        and isinstance(to_owner, dict)
        and isinstance(from_owner.get("owner_id"), str)
        and isinstance(to_owner.get("owner_id"), str)
        and from_owner.get("owner_id") == to_owner.get("owner_id")
    ):
        errors.append(f"{_relative_path(path)}: from_owner.owner_id must differ from to_owner.owner_id")
    return errors


def _validate_obligation_escalation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "escalation_id",
            "obligation_id",
            "escalated_to",
            "reason",
            "severity",
            "escalated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("escalation_id", "obligation_id", "reason", "severity"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _validate_obligation_owner_dict(payload["escalated_to"], path=path, field_name="escalated_to")
    )
    errors.extend(
        _validate_iso8601_text(payload["escalated_at"], field_name="escalated_at", path=path)
    )
    return errors


def _validate_operational_node_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_operational_node_dict(payload, path=path, field_name="runtime fixture")


def _validate_operational_node_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("node_id", "node_type", "label", "created_at", "metadata"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("node_id", "node_type", "label"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    errors.extend(
        _validate_iso8601_text(
            payload["created_at"],
            field_name=f"{prefix}created_at".strip("."),
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        metadata_field_name = f"{prefix}metadata".strip(".")
        errors.append(f"{_relative_path(path)}: field '{metadata_field_name}' must be an object")
    return errors


def _validate_operational_edge_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_operational_edge_dict(payload, path=path, field_name="runtime fixture")


def _validate_operational_edge_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "edge_type",
            "source_node_id",
            "target_node_id",
            "label",
            "created_at",
            "metadata",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in (
        "edge_id",
        "edge_type",
        "source_node_id",
        "target_node_id",
        "label",
    ):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    errors.extend(
        _validate_iso8601_text(
            payload["created_at"],
            field_name=f"{prefix}created_at".strip("."),
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        metadata_field_name = f"{prefix}metadata".strip(".")
        errors.append(f"{_relative_path(path)}: field '{metadata_field_name}' must be an object")
    return errors


def _validate_evidence_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "source_node_id",
            "target_node_id",
            "evidence_type",
            "confidence",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("edge_id", "source_node_id", "target_node_id", "evidence_type"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_decision_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "source_node_id",
            "target_node_id",
            "decision",
            "decided_by_id",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("edge_id", "source_node_id", "target_node_id", "decision", "decided_by_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_obligation_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "source_node_id",
            "target_node_id",
            "obligation",
            "fulfilled",
            "created_at",
            "deadline",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("edge_id", "source_node_id", "target_node_id", "obligation"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["fulfilled"], bool):
        errors.append(f"{_relative_path(path)}: field 'fulfilled' must be boolean")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    errors.extend(_validate_iso8601_text(payload["deadline"], field_name="deadline", path=path))
    return errors


def _validate_state_delta_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("delta_id", "node_id", "field_name", "old_value", "new_value", "changed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("delta_id", "node_id", "field_name"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("old_value", "new_value"):
        if not isinstance(payload[field_name], str):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be a string")
    errors.extend(_validate_iso8601_text(payload["changed_at"], field_name="changed_at", path=path))
    return errors


def _validate_causal_path_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("path_id", "node_ids", "edge_ids", "description"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("path_id", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for list_name in ("node_ids", "edge_ids"):
        values = payload[list_name]
        if not isinstance(values, list) or not values:
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be a non-empty array")
        else:
            for index, value in enumerate(values):
                errors.extend(_require_non_empty_text(value, field_name=f"{list_name}[{index}]", path=path))
    return errors


def _validate_graph_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("snapshot_id", "node_count", "edge_count", "captured_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    errors.extend(_require_non_negative_int(payload["node_count"], field_name="node_count", path=path))
    errors.extend(_require_non_negative_int(payload["edge_count"], field_name="edge_count", path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    return errors


def _validate_graph_query_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("query_id", "matched_nodes", "matched_edges", "executed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["query_id"], field_name="query_id", path=path))
    errors.extend(_validate_iso8601_text(payload["executed_at"], field_name="executed_at", path=path))
    matched_nodes = payload["matched_nodes"]
    if not isinstance(matched_nodes, list):
        errors.append(f"{_relative_path(path)}: field 'matched_nodes' must be an array")
    else:
        for index, node in enumerate(matched_nodes):
            errors.extend(
                _validate_operational_node_dict(node, path=path, field_name=f"matched_nodes[{index}]")
            )
    matched_edges = payload["matched_edges"]
    if not isinstance(matched_edges, list):
        errors.append(f"{_relative_path(path)}: field 'matched_edges' must be an array")
    else:
        for index, edge in enumerate(matched_edges):
            errors.extend(
                _validate_operational_edge_dict(edge, path=path, field_name=f"matched_edges[{index}]")
            )
    return errors


def _validate_service_function_template_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "name",
            "function_type",
            "description",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("function_id", "name", "function_type", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    return errors


def _validate_role_descriptor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "role_id",
            "name",
            "description",
            "required_skills",
            "approval_required",
            "max_concurrent_per_worker",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("role_id", "name", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    required_skills = payload["required_skills"]
    if not isinstance(required_skills, list) or not required_skills:
        errors.append(f"{_relative_path(path)}: field 'required_skills' must be a non-empty array")
    else:
        for index, skill in enumerate(required_skills):
            if not isinstance(skill, str) or not skill.strip():
                errors.append(
                    f"{_relative_path(path)}: required_skills[{index}] must be a non-empty string"
                )
    if not isinstance(payload["approval_required"], bool):
        errors.append(f"{_relative_path(path)}: field 'approval_required' must be boolean")
    errors.extend(
        _require_positive_int(
            payload["max_concurrent_per_worker"],
            field_name="max_concurrent_per_worker",
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    return errors


def _validate_function_policy_binding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "binding_id",
            "function_id",
            "policy_pack_id",
            "autonomy_mode",
            "review_required",
            "deployment_profile_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "binding_id",
        "function_id",
        "policy_pack_id",
        "autonomy_mode",
        "deployment_profile_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["review_required"], bool):
        errors.append(f"{_relative_path(path)}: field 'review_required' must be boolean")
    return errors


def _validate_function_sla_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "target_completion_minutes",
            "approval_latency_minutes",
            "escalation_threshold_minutes",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["function_id"], field_name="function_id", path=path))
    for field_name in (
        "target_completion_minutes",
        "approval_latency_minutes",
        "escalation_threshold_minutes",
    ):
        errors.extend(_require_positive_int(payload[field_name], field_name=field_name, path=path))
    if (
        isinstance(payload["target_completion_minutes"], int)
        and isinstance(payload["escalation_threshold_minutes"], int)
        and not isinstance(payload["target_completion_minutes"], bool)
        and not isinstance(payload["escalation_threshold_minutes"], bool)
        and payload["escalation_threshold_minutes"] > payload["target_completion_minutes"]
    ):
        errors.append(
            f"{_relative_path(path)}: escalation_threshold_minutes must not exceed target_completion_minutes"
        )
    return errors


def _validate_function_queue_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "team_id",
            "default_role_id",
            "communication_style",
            "max_concurrent_jobs",
            "escalation_chain_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "function_id",
        "team_id",
        "default_role_id",
        "communication_style",
        "escalation_chain_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_positive_int(
            payload["max_concurrent_jobs"],
            field_name="max_concurrent_jobs",
            path=path,
        )
    )
    return errors


def _validate_assignment_policy_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "policy_id",
            "role_id",
            "strategy",
            "fallback_team_id",
            "escalation_chain_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "policy_id",
        "role_id",
        "strategy",
        "fallback_team_id",
        "escalation_chain_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_worker_capacity_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_worker_capacity_fixture_dict(payload, path)


def _validate_team_queue_state_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "team_id",
            "queued_jobs",
            "assigned_jobs",
            "waiting_jobs",
            "overloaded_workers",
            "captured_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["team_id"], field_name="team_id", path=path))
    for field_name in (
        "queued_jobs",
        "assigned_jobs",
        "waiting_jobs",
        "overloaded_workers",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    return errors


def _validate_worker_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "worker_id",
            "name",
            "roles",
            "max_concurrent_jobs",
            "status",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("worker_id", "name", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    roles = payload["roles"]
    if not isinstance(roles, list) or not roles:
        errors.append(f"{_relative_path(path)}: field 'roles' must be a non-empty array")
    else:
        for index, role in enumerate(roles):
            if not isinstance(role, str) or not role.strip():
                errors.append(f"{_relative_path(path)}: roles[{index}] must be a non-empty string")
    errors.extend(
        _require_positive_int(
            payload["max_concurrent_jobs"],
            field_name="max_concurrent_jobs",
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assignment_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "job_id",
            "worker_id",
            "role_id",
            "reason",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "job_id", "worker_id", "role_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    return errors


def _validate_handoff_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "handoff_id",
            "job_id",
            "from_worker_id",
            "to_worker_id",
            "reason",
            "thread_id",
            "handoff_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "handoff_id",
        "job_id",
        "from_worker_id",
        "to_worker_id",
        "reason",
        "thread_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["handoff_at"], field_name="handoff_at", path=path))
    if payload["from_worker_id"] == payload["to_worker_id"]:
        errors.append(f"{_relative_path(path)}: from_worker_id and to_worker_id must differ")
    return errors


def _validate_workload_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("snapshot_id", "team_id", "worker_capacities", "captured_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    errors.extend(_require_non_empty_text(payload["team_id"], field_name="team_id", path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    worker_capacities = payload["worker_capacities"]
    if not isinstance(worker_capacities, list) or not worker_capacities:
        errors.append(f"{_relative_path(path)}: field 'worker_capacities' must be a non-empty array")
        return errors
    seen_worker_ids: set[str] = set()
    for index, worker_capacity in enumerate(worker_capacities):
        if not isinstance(worker_capacity, dict):
            errors.append(f"{_relative_path(path)}: worker_capacities[{index}] must be an object")
            continue
        nested_path = Path(f"{path.as_posix()}#{index}")
        nested_errors = _validate_worker_capacity_fixture_dict(worker_capacity, nested_path)
        errors.extend(nested_errors)
        worker_id = worker_capacity.get("worker_id")
        if isinstance(worker_id, str) and worker_id in seen_worker_ids:
            errors.append(
                f"{_relative_path(path)}: worker_capacities must not repeat worker_id '{worker_id}'"
            )
        elif isinstance(worker_id, str):
            seen_worker_ids.add(worker_id)
    return errors


def _validate_function_outcome_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "outcome_id",
            "function_id",
            "job_id",
            "completed",
            "completion_minutes",
            "escalated",
            "drift_detected",
            "recorded_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("outcome_id", "function_id", "job_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("completed", "escalated", "drift_detected"):
        if not isinstance(payload[field_name], bool):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be boolean")
    errors.extend(
        _require_non_negative_int(
            payload["completion_minutes"],
            field_name="completion_minutes",
            path=path,
        )
    )
    errors.extend(_validate_iso8601_text(payload["recorded_at"], field_name="recorded_at", path=path))
    return errors


def _validate_function_metrics_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "period_start",
            "period_end",
            "total_jobs",
            "completed_jobs",
            "failed_jobs",
            "avg_completion_minutes",
            "escalation_count",
            "drift_count",
            "captured_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["function_id"], field_name="function_id", path=path))
    for field_name in ("period_start", "period_end", "captured_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_jobs",
        "completed_jobs",
        "failed_jobs",
        "escalation_count",
        "drift_count",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["avg_completion_minutes"],
            field_name="avg_completion_minutes",
            path=path,
            minimum=0.0,
            maximum=1000000.0,
        )
    )
    return errors


def _validate_worker_capacity_fixture_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "worker_id",
            "max_concurrent",
            "current_load",
            "available_slots",
            "updated_at",
        ),
        kind="worker_capacity",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["worker_id"], field_name="worker_id", path=path))
    errors.extend(_require_positive_int(payload["max_concurrent"], field_name="max_concurrent", path=path))
    errors.extend(_require_non_negative_int(payload["current_load"], field_name="current_load", path=path))
    errors.extend(_require_non_negative_int(payload["available_slots"], field_name="available_slots", path=path))
    errors.extend(_validate_iso8601_text(payload["updated_at"], field_name="updated_at", path=path))
    if (
        isinstance(payload["max_concurrent"], int)
        and isinstance(payload["current_load"], int)
        and isinstance(payload["available_slots"], int)
        and not isinstance(payload["max_concurrent"], bool)
        and not isinstance(payload["current_load"], bool)
        and not isinstance(payload["available_slots"], bool)
    ):
        if payload["current_load"] > payload["max_concurrent"]:
            errors.append(f"{_relative_path(path)}: current_load cannot exceed max_concurrent")
        if payload["available_slots"] != payload["max_concurrent"] - payload["current_load"]:
            errors.append(
                f"{_relative_path(path)}: available_slots must equal max_concurrent - current_load"
            )
    return errors


def _validate_simulation_option_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "option_id",
            "label",
            "risk_level",
            "estimated_cost",
            "estimated_duration_seconds",
            "success_probability",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("option_id", "label", "risk_level"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_non_negative_float(payload["estimated_cost"], field_name="estimated_cost", path=path)
    )
    errors.extend(
        _require_non_negative_float(
            payload["estimated_duration_seconds"],
            field_name="estimated_duration_seconds",
            path=path,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["success_probability"],
            field_name="success_probability",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    return errors


def _require_non_negative_float(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return [f"{_relative_path(path)}: field '{field_name}' must be a numeric value"]
    if value < 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be non-negative"]
    return []


def _validate_simulation_request_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("request_id", "context_type", "context_id", "description", "options"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("request_id", "context_type", "context_id", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    options = payload["options"]
    if not isinstance(options, list) or not options:
        errors.append(f"{_relative_path(path)}: field 'options' must be a non-empty array")
        return errors
    seen_option_ids: set[str] = set()
    for index, option in enumerate(options):
        if not isinstance(option, dict):
            errors.append(f"{_relative_path(path)}: options[{index}] must be an object")
            continue
        nested_path = Path(f"{path.as_posix()}#options[{index}]")
        errors.extend(_validate_simulation_option_fixture_dict(option, nested_path))
        option_id = option.get("option_id")
        if isinstance(option_id, str) and option_id in seen_option_ids:
            errors.append(f"{_relative_path(path)}: options must not repeat option_id '{option_id}'")
        elif isinstance(option_id, str):
            seen_option_ids.add(option_id)
    return errors


def _validate_consequence_estimate_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "estimate_id",
            "option_id",
            "affected_node_ids",
            "new_edges_count",
            "new_obligations_count",
            "blocked_nodes_count",
            "unblocked_nodes_count",
        ),
        kind="consequence",
    )
    if errors:
        return errors
    for field_name in ("estimate_id", "option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    affected_node_ids = payload["affected_node_ids"]
    if not isinstance(affected_node_ids, list):
        errors.append(f"{_relative_path(path)}: field 'affected_node_ids' must be an array")
    else:
        for index, node_id in enumerate(affected_node_ids):
            if not isinstance(node_id, str) or not node_id.strip():
                errors.append(
                    f"{_relative_path(path)}: affected_node_ids[{index}] must be a non-empty string"
                )
    for field_name in (
        "new_edges_count",
        "new_obligations_count",
        "blocked_nodes_count",
        "unblocked_nodes_count",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_risk_estimate_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "estimate_id",
            "option_id",
            "risk_level",
            "incident_probability",
            "review_burden",
            "provider_exposure_count",
            "verification_difficulty",
            "rationale",
        ),
        kind="risk",
    )
    if errors:
        return errors
    for field_name in ("estimate_id", "option_id", "risk_level", "verification_difficulty", "rationale"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["incident_probability"],
            field_name="incident_probability",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    for field_name in ("review_burden", "provider_exposure_count"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_obligation_projection_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "projection_id",
            "option_id",
            "new_obligations",
            "fulfilled_obligations",
            "deadline_pressure",
        ),
        kind="obligation_projection",
    )
    if errors:
        return errors
    for field_name in ("projection_id", "option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for list_name in ("new_obligations", "fulfilled_obligations"):
        values = payload[list_name]
        if not isinstance(values, list):
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be an array")
        else:
            for index, obligation_id in enumerate(values):
                if not isinstance(obligation_id, str) or not obligation_id.strip():
                    errors.append(
                        f"{_relative_path(path)}: {list_name}[{index}] must be a non-empty string"
                    )
    errors.extend(
        _require_non_negative_int(
            payload["deadline_pressure"],
            field_name="deadline_pressure",
            path=path,
        )
    )
    return errors


def _validate_simulation_option_fixture_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "option_id",
            "label",
            "risk_level",
            "estimated_cost",
            "estimated_duration_seconds",
            "success_probability",
        ),
        kind="simulation_option",
    )
    if errors:
        return errors
    for field_name in ("option_id", "label", "risk_level"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["estimated_cost"], field_name="estimated_cost", path=path))
    errors.extend(
        _require_non_negative_float(
            payload["estimated_duration_seconds"],
            field_name="estimated_duration_seconds",
            path=path,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["success_probability"],
            field_name="success_probability",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    return errors


def _validate_simulation_outcome_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "outcome_id",
            "option_id",
            "consequence",
            "risk",
            "obligation_projection",
            "simulated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["outcome_id"], field_name="outcome_id", path=path))
    errors.extend(_require_non_empty_text(payload["option_id"], field_name="option_id", path=path))
    errors.extend(_validate_iso8601_text(payload["simulated_at"], field_name="simulated_at", path=path))
    for nested_name, validator in (
        ("consequence", _validate_consequence_estimate_dict),
        ("risk", _validate_risk_estimate_dict),
        ("obligation_projection", _validate_obligation_projection_dict),
    ):
        nested_value = payload[nested_name]
        if not isinstance(nested_value, dict):
            errors.append(f"{_relative_path(path)}: field '{nested_name}' must be an object")
        else:
            nested_path = Path(f"{path.as_posix()}#{nested_name}")
            errors.extend(validator(nested_value, nested_path))
            option_id = nested_value.get("option_id")
            if isinstance(option_id, str) and option_id != payload["option_id"]:
                errors.append(
                    f"{_relative_path(path)}: {nested_name}.option_id must match outcome option_id"
                )
    return errors


def _validate_simulation_verdict_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "verdict_id",
            "comparison_id",
            "verdict_type",
            "recommended_option_id",
            "confidence",
            "reasons",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("verdict_id", "comparison_id", "verdict_type", "recommended_option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    reasons = payload["reasons"]
    if not isinstance(reasons, list) or not reasons:
        errors.append(f"{_relative_path(path)}: field 'reasons' must be a non-empty array")
    else:
        for index, reason in enumerate(reasons):
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{_relative_path(path)}: reasons[{index}] must be a non-empty string")
    return errors


def _validate_benchmark_scenario_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_benchmark_scenario_dict(payload, path=path, field_name="runtime fixture")


def _validate_benchmark_scenario_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "scenario_id",
            "name",
            "description",
            "category",
            "inputs",
            "expected_outcome",
            "expected_properties",
            "tags",
            "timeout_ms",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("scenario_id", "name", "description", "category", "expected_outcome"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("inputs", "expected_properties"):
        if not isinstance(payload[nested_field_name], dict):
            errors.append(
                f"{_relative_path(path)}: field '{f'{prefix}{nested_field_name}'.strip('.')}' must be an object"
            )
    tags = payload["tags"]
    tags_field_name = f"{prefix}tags".strip(".")
    if not isinstance(tags, list):
        errors.append(f"{_relative_path(path)}: field '{tags_field_name}' must be an array")
    else:
        for index, tag in enumerate(tags):
            errors.extend(_require_non_empty_text(tag, field_name=f"{tags_field_name}[{index}]", path=path))
    errors.extend(
        _require_positive_int(
            payload["timeout_ms"],
            field_name=f"{prefix}timeout_ms".strip("."),
            path=path,
        )
    )
    return errors


def _validate_benchmark_suite_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("suite_id", "name", "category", "scenarios", "version", "created_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("suite_id", "name", "category", "version"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    scenarios = payload["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        errors.append(f"{_relative_path(path)}: field 'scenarios' must be a non-empty array")
    else:
        seen_scenario_ids: set[str] = set()
        for index, scenario in enumerate(scenarios):
            errors.extend(
                _validate_benchmark_scenario_dict(
                    scenario,
                    path=path,
                    field_name=f"scenarios[{index}]",
                )
            )
            if isinstance(scenario, dict) and isinstance(scenario.get("scenario_id"), str):
                scenario_id = scenario["scenario_id"]
                if scenario_id in seen_scenario_ids:
                    errors.append(
                        f"{_relative_path(path)}: scenarios must not repeat scenario_id '{scenario_id}'"
                    )
                seen_scenario_ids.add(scenario_id)
    return errors


def _validate_benchmark_metric_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_benchmark_metric_dict(payload, path=path, field_name="runtime fixture")


def _validate_benchmark_metric_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("metric_id", "kind", "name", "value", "threshold", "passed"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("metric_id", "kind", "name"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("value", "threshold"):
        errors.extend(
            _require_number_in_range(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    passed_field_name = f"{prefix}passed".strip(".")
    if not isinstance(payload["passed"], bool):
        errors.append(f"{_relative_path(path)}: field '{passed_field_name}' must be boolean")
    elif (
        isinstance(payload["value"], (int, float))
        and not isinstance(payload["value"], bool)
        and isinstance(payload["threshold"], (int, float))
        and not isinstance(payload["threshold"], bool)
        and payload["passed"] != (payload["value"] >= payload["threshold"])
    ):
        errors.append(
            f"{_relative_path(path)}: {passed_field_name} must be true iff value >= threshold"
        )
    return errors


def _validate_benchmark_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_benchmark_result_dict(payload, path=path, field_name="runtime fixture")


def _validate_benchmark_result_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "result_id",
            "scenario_id",
            "outcome",
            "metrics",
            "actual_properties",
            "error_message",
            "duration_ms",
            "executed_at",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("result_id", "scenario_id", "outcome"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    metrics = payload["metrics"]
    metrics_field_name = f"{prefix}metrics".strip(".")
    if not isinstance(metrics, list):
        errors.append(f"{_relative_path(path)}: field '{metrics_field_name}' must be an array")
    else:
        for index, metric in enumerate(metrics):
            errors.extend(
                _validate_benchmark_metric_dict(
                    metric,
                    path=path,
                    field_name=f"{metrics_field_name}[{index}]",
                )
            )
    actual_properties_field_name = f"{prefix}actual_properties".strip(".")
    if not isinstance(payload["actual_properties"], dict):
        errors.append(
            f"{_relative_path(path)}: field '{actual_properties_field_name}' must be an object"
        )
    error_message_field_name = f"{prefix}error_message".strip(".")
    if payload["error_message"] is not None and not isinstance(payload["error_message"], str):
        errors.append(f"{_relative_path(path)}: field '{error_message_field_name}' must be a string or null")
    errors.extend(
        _require_non_negative_int(
            payload["duration_ms"],
            field_name=f"{prefix}duration_ms".strip("."),
            path=path,
        )
    )
    errors.extend(
        _validate_iso8601_text(
            payload["executed_at"],
            field_name=f"{prefix}executed_at".strip("."),
            path=path,
        )
    )
    return errors


def _validate_benchmark_run_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("run_id", "suite_id", "results", "started_at", "finished_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("run_id", "suite_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    results = payload["results"]
    if not isinstance(results, list):
        errors.append(f"{_relative_path(path)}: field 'results' must be an array")
    else:
        for index, result in enumerate(results):
            errors.extend(
                _validate_benchmark_result_dict(
                    result,
                    path=path,
                    field_name=f"results[{index}]",
                )
            )
    for field_name in ("started_at", "finished_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_adversarial_case_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "case_id",
            "name",
            "description",
            "category",
            "severity",
            "target_subsystem",
            "attack_vector",
            "inputs",
            "expected_behavior",
            "tags",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "case_id",
        "name",
        "description",
        "category",
        "severity",
        "target_subsystem",
        "attack_vector",
        "expected_behavior",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["inputs"], dict):
        errors.append(f"{_relative_path(path)}: field 'inputs' must be an object")
    tags = payload["tags"]
    if not isinstance(tags, list):
        errors.append(f"{_relative_path(path)}: field 'tags' must be an array")
    else:
        for index, tag in enumerate(tags):
            errors.extend(_require_non_empty_text(tag, field_name=f"tags[{index}]", path=path))
    return errors


def _validate_regression_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_regression_record_dict(payload, path=path, field_name="runtime fixture")


def _validate_regression_record_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "regression_id",
            "metric_name",
            "category",
            "baseline_value",
            "current_value",
            "direction",
            "delta",
            "baseline_run_id",
            "current_run_id",
            "detected_at",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in (
        "regression_id",
        "metric_name",
        "category",
        "direction",
        "baseline_run_id",
        "current_run_id",
    ):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("baseline_value", "current_value"):
        errors.extend(
            _require_number_in_range(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    delta_field_name = f"{prefix}delta".strip(".")
    if isinstance(payload["delta"], bool) or not isinstance(payload["delta"], (int, float)):
        errors.append(f"{_relative_path(path)}: field '{delta_field_name}' must be numeric")
    errors.extend(
        _validate_iso8601_text(
            payload["detected_at"],
            field_name=f"{prefix}detected_at".strip("."),
            path=path,
        )
    )
    return errors


def _validate_capability_scorecard_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "scorecard_id",
            "category",
            "status",
            "pass_rate",
            "metric_count",
            "metrics_passing",
            "adversarial_pass_rate",
            "regressions",
            "confidence_trend",
            "assessed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("scorecard_id", "category", "status", "confidence_trend"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("pass_rate", "adversarial_pass_rate"):
        errors.extend(
            _require_number_in_range(
                payload[field_name],
                field_name=field_name,
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    for field_name in ("metric_count", "metrics_passing"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if (
        isinstance(payload["metric_count"], int)
        and not isinstance(payload["metric_count"], bool)
        and isinstance(payload["metrics_passing"], int)
        and not isinstance(payload["metrics_passing"], bool)
        and payload["metrics_passing"] > payload["metric_count"]
    ):
        errors.append(f"{_relative_path(path)}: metrics_passing cannot exceed metric_count")
    regressions = payload["regressions"]
    if not isinstance(regressions, list):
        errors.append(f"{_relative_path(path)}: field 'regressions' must be an array")
    else:
        for index, regression in enumerate(regressions):
            errors.extend(
                _validate_regression_record_dict(
                    regression,
                    path=path,
                    field_name=f"regressions[{index}]",
                )
            )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    return errors


def _validate_resource_budget_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("resource_id", "resource_type", "total", "consumed", "reserved"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("resource_id", "resource_type"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total", "consumed", "reserved"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    if (
        isinstance(payload["total"], (int, float))
        and isinstance(payload["consumed"], (int, float))
        and isinstance(payload["reserved"], (int, float))
        and not isinstance(payload["total"], bool)
        and not isinstance(payload["consumed"], bool)
        and not isinstance(payload["reserved"], bool)
        and payload["consumed"] + payload["reserved"] > payload["total"]
    ):
        errors.append(f"{_relative_path(path)}: consumed + reserved must not exceed total")
    return errors


def _validate_decision_factor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_decision_factor_dict(payload, path=path, field_name="runtime fixture")


def _validate_decision_factor_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("factor_id", "kind", "weight", "value", "label"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("factor_id", "kind", "label"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("weight", "value"):
        errors.extend(
            _require_number_in_range(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    return errors


def _validate_utility_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "profile_id",
            "context_type",
            "context_id",
            "factors",
            "tradeoff_direction",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("profile_id", "context_type", "context_id", "tradeoff_direction"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    factors = payload["factors"]
    if not isinstance(factors, list) or not factors:
        errors.append(f"{_relative_path(path)}: field 'factors' must be a non-empty array")
    else:
        total_weight = 0.0
        for index, factor in enumerate(factors):
            errors.extend(
                _validate_decision_factor_dict(
                    factor,
                    path=path,
                    field_name=f"factors[{index}]",
                )
            )
            if (
                isinstance(factor, dict)
                and isinstance(factor.get("weight"), (int, float))
                and not isinstance(factor.get("weight"), bool)
            ):
                total_weight += float(factor["weight"])
        if total_weight <= 0.0:
            errors.append(f"{_relative_path(path)}: sum of factor weights must be greater than 0")
    return errors


def _validate_option_utility_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_option_utility_dict(payload, path=path, field_name="runtime fixture")


def _validate_option_utility_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("option_id", "raw_score", "weighted_score", "factor_contributions", "rank"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    errors.extend(
        _require_non_empty_text(
            payload["option_id"],
            field_name=f"{prefix}option_id".strip("."),
            path=path,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["raw_score"],
            field_name=f"{prefix}raw_score".strip("."),
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["weighted_score"],
            field_name=f"{prefix}weighted_score".strip("."),
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    factor_contributions = payload["factor_contributions"]
    if not isinstance(factor_contributions, dict):
        factor_field_name = f"{prefix}factor_contributions".strip(".")
        errors.append(
            f"{_relative_path(path)}: field '{factor_field_name}' must be an object"
        )
    else:
        for factor_id, contribution in factor_contributions.items():
            if not isinstance(factor_id, str) or not factor_id.strip():
                errors.append(f"{_relative_path(path)}: factor_contributions keys must be non-empty strings")
                break
            if isinstance(contribution, bool) or not isinstance(contribution, (int, float)):
                errors.append(
                    f"{_relative_path(path)}: factor_contributions['{factor_id}'] must be numeric"
                )
    errors.extend(
        _require_positive_int(payload["rank"], field_name=f"{prefix}rank".strip("."), path=path)
    )
    return errors


def _validate_decision_comparison_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "comparison_id",
            "profile_id",
            "option_utilities",
            "best_option_id",
            "spread",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("comparison_id", "profile_id", "best_option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["spread"], field_name="spread", path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    option_utilities = payload["option_utilities"]
    if not isinstance(option_utilities, list) or not option_utilities:
        errors.append(f"{_relative_path(path)}: field 'option_utilities' must be a non-empty array")
    else:
        option_ids: set[str] = set()
        for index, option_utility in enumerate(option_utilities):
            errors.extend(
                _validate_option_utility_dict(
                    option_utility,
                    path=path,
                    field_name=f"option_utilities[{index}]",
                )
            )
            if isinstance(option_utility, dict) and isinstance(option_utility.get("option_id"), str):
                option_ids.add(option_utility["option_id"])
        if isinstance(payload["best_option_id"], str) and payload["best_option_id"] not in option_ids:
            errors.append(f"{_relative_path(path)}: best_option_id must reference an option in option_utilities")
    return errors


def _validate_tradeoff_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "tradeoff_id",
            "comparison_id",
            "chosen_option_id",
            "rejected_option_ids",
            "tradeoff_direction",
            "rationale",
            "recorded_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("tradeoff_id", "comparison_id", "chosen_option_id", "tradeoff_direction", "rationale"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["recorded_at"], field_name="recorded_at", path=path))
    rejected_option_ids = payload["rejected_option_ids"]
    if not isinstance(rejected_option_ids, list):
        errors.append(f"{_relative_path(path)}: field 'rejected_option_ids' must be an array")
    else:
        for index, option_id in enumerate(rejected_option_ids):
            errors.extend(
                _require_non_empty_text(option_id, field_name=f"rejected_option_ids[{index}]", path=path)
            )
    return errors


def _validate_decision_policy_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "policy_id",
            "name",
            "min_confidence",
            "max_risk_tolerance",
            "max_cost",
            "deadline_weight",
            "require_human_above_risk",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("policy_id", "name"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("min_confidence", "max_risk_tolerance", "deadline_weight", "require_human_above_risk"):
        errors.extend(
            _require_number_in_range(
                payload[field_name],
                field_name=field_name,
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    errors.extend(_require_non_negative_float(payload["max_cost"], field_name="max_cost", path=path))
    return errors


def _validate_utility_verdict_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "verdict_id",
            "comparison_id",
            "policy_id",
            "approved",
            "recommended_option_id",
            "confidence",
            "reasons",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("verdict_id", "comparison_id", "policy_id", "recommended_option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["approved"], bool):
        errors.append(f"{_relative_path(path)}: field 'approved' must be boolean")
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    reasons = payload["reasons"]
    if not isinstance(reasons, list) or not reasons:
        errors.append(f"{_relative_path(path)}: field 'reasons' must be a non-empty array")
    else:
        for index, reason in enumerate(reasons):
            errors.extend(_require_non_empty_text(reason, field_name=f"reasons[{index}]", path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    return errors


def _validate_supervisor_policy_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "policy_id",
            "tick_interval_ms",
            "max_events_per_tick",
            "max_actions_per_tick",
            "backpressure_threshold",
            "livelock_repeat_threshold",
            "livelock_strategy",
            "heartbeat_every_n_ticks",
            "checkpoint_every_n_ticks",
            "max_consecutive_errors",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["policy_id"], field_name="policy_id", path=path))
    errors.extend(_require_non_empty_text(payload["livelock_strategy"], field_name="livelock_strategy", path=path))
    for field_name in (
        "tick_interval_ms",
        "max_events_per_tick",
        "max_actions_per_tick",
        "backpressure_threshold",
        "livelock_repeat_threshold",
        "heartbeat_every_n_ticks",
        "checkpoint_every_n_ticks",
        "max_consecutive_errors",
    ):
        errors.extend(_require_positive_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_supervisor_health_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "health_id",
            "tick_number",
            "phase",
            "consecutive_errors",
            "consecutive_idle_ticks",
            "backpressure_active",
            "livelock_detected",
            "open_obligations",
            "pending_events",
            "overall_confidence",
            "assessed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("health_id", "phase"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "tick_number",
        "consecutive_errors",
        "consecutive_idle_ticks",
        "open_obligations",
        "pending_events",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("backpressure_active", "livelock_detected"):
        if not isinstance(payload[field_name], bool):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be boolean")
    errors.extend(
        _require_number_in_range(
            payload["overall_confidence"],
            field_name="overall_confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    return errors


def _validate_runtime_heartbeat_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "heartbeat_id",
            "tick_number",
            "phase",
            "outcome_of_last_tick",
            "open_obligations",
            "pending_events",
            "uptime_ticks",
            "emitted_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("heartbeat_id", "phase", "outcome_of_last_tick"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("tick_number", "open_obligations", "pending_events", "uptime_ticks"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["emitted_at"], field_name="emitted_at", path=path))
    return errors


def _validate_supervisor_checkpoint_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "checkpoint_id",
            "tick_number",
            "phase",
            "status",
            "open_obligation_ids",
            "pending_event_count",
            "consecutive_errors",
            "consecutive_idle_ticks",
            "recent_tick_outcomes",
            "state_hash",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("checkpoint_id", "phase", "status", "state_hash"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "tick_number",
        "pending_event_count",
        "consecutive_errors",
        "consecutive_idle_ticks",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for list_name in ("open_obligation_ids", "recent_tick_outcomes"):
        values = payload[list_name]
        if not isinstance(values, list):
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be an array")
        else:
            for index, value in enumerate(values):
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{_relative_path(path)}: {list_name}[{index}] must be a non-empty string")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_livelock_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "livelock_id",
            "tick_number",
            "repeated_pattern",
            "repeat_count",
            "strategy_applied",
            "resolved",
            "detected_at",
            "resolution_detail",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("livelock_id", "repeated_pattern", "strategy_applied"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_int(payload["tick_number"], field_name="tick_number", path=path))
    errors.extend(_require_positive_int(payload["repeat_count"], field_name="repeat_count", path=path))
    if not isinstance(payload["resolved"], bool):
        errors.append(f"{_relative_path(path)}: field 'resolved' must be boolean")
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["resolution_detail"], str):
        errors.append(f"{_relative_path(path)}: field 'resolution_detail' must be a string")
    return errors


def _validate_journal_entry_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("entry_id", "epoch_id", "sequence", "kind", "subject_id", "payload", "recorded_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("entry_id", "epoch_id", "kind", "subject_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in JOURNAL_ENTRY_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(JOURNAL_ENTRY_KINDS))}"
        )
    errors.extend(_require_non_negative_int(payload["sequence"], field_name="sequence", path=path))
    if not isinstance(payload["payload"], (dict, list)):
        errors.append(f"{_relative_path(path)}: field 'payload' must be structured JSON")
    errors.extend(_validate_iso8601_text(payload["recorded_at"], field_name="recorded_at", path=path))
    return errors


def _validate_subsystem_snapshot_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("snapshot_id", "scope", "state_hash", "record_count", "captured_at", "payload"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("snapshot_id", "scope", "state_hash"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    if payload["scope"] not in CHECKPOINT_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field '{f'{prefix}scope'.strip('.')}' must be one of {', '.join(sorted(CHECKPOINT_SCOPES))}"
        )
    errors.extend(
        _require_non_negative_int(
            payload["record_count"],
            field_name=f"{prefix}record_count".strip("."),
            path=path,
        )
    )
    errors.extend(
        _validate_iso8601_text(
            payload["captured_at"],
            field_name=f"{prefix}captured_at".strip("."),
            path=path,
        )
    )
    nested_payload = payload["payload"]
    if not isinstance(nested_payload, dict):
        errors.append(f"{_relative_path(path)}: field '{f'{prefix}payload'.strip('.')}' must be an object")
    else:
        for key in nested_payload:
            if not isinstance(key, str) or not key.strip():
                errors.append(
                    f"{_relative_path(path)}: field '{f'{prefix}payload'.strip('.')}' must use non-empty string keys"
                )
                break
    return errors


def _validate_subsystem_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_subsystem_snapshot_dict(payload, path=path, field_name="runtime fixture")


def _validate_composite_checkpoint_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "checkpoint_id",
            "epoch_id",
            "tick_number",
            "snapshots",
            "journal_sequence",
            "composite_hash",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("checkpoint_id", "epoch_id", "composite_hash"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_int(payload["tick_number"], field_name="tick_number", path=path))
    errors.extend(
        _require_non_negative_int(payload["journal_sequence"], field_name="journal_sequence", path=path)
    )
    snapshots = payload["snapshots"]
    snapshot_scopes: list[str] = []
    if not isinstance(snapshots, list) or not snapshots:
        errors.append(f"{_relative_path(path)}: field 'snapshots' must be a non-empty array")
    else:
        for index, snapshot in enumerate(snapshots):
            errors.extend(
                _validate_subsystem_snapshot_dict(
                    snapshot,
                    path=path,
                    field_name=f"snapshots[{index}]",
                )
            )
            if isinstance(snapshot, dict) and isinstance(snapshot.get("scope"), str):
                snapshot_scopes.append(snapshot["scope"])
        if len(set(snapshot_scopes)) != len(snapshot_scopes):
            errors.append(f"{_relative_path(path)}: snapshots must not repeat scope values")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_restore_verification_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "verification_id",
            "checkpoint_id",
            "epoch_id",
            "tick_number",
            "verdict",
            "expected_composite_hash",
            "actual_composite_hash",
            "subsystem_results",
            "verified_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "verification_id",
        "checkpoint_id",
        "epoch_id",
        "verdict",
        "expected_composite_hash",
        "actual_composite_hash",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["verdict"] not in RESTORE_VERDICTS:
        errors.append(
            f"{_relative_path(path)}: field 'verdict' must be one of {', '.join(sorted(RESTORE_VERDICTS))}"
        )
    errors.extend(_require_non_negative_int(payload["tick_number"], field_name="tick_number", path=path))
    subsystem_results = payload["subsystem_results"]
    if not isinstance(subsystem_results, dict) or not subsystem_results:
        errors.append(f"{_relative_path(path)}: field 'subsystem_results' must be a non-empty object")
    else:
        for subsystem_name, subsystem_result in subsystem_results.items():
            if not isinstance(subsystem_name, str) or not subsystem_name.strip():
                errors.append(
                    f"{_relative_path(path)}: field 'subsystem_results' must use non-empty string keys"
                )
                continue
            if not isinstance(subsystem_result, dict) or not subsystem_result:
                errors.append(
                    f"{_relative_path(path)}: subsystem_results.{subsystem_name} must be a non-empty object"
                )
                continue
            for result_key, result_value in subsystem_result.items():
                if not isinstance(result_key, str) or not result_key.strip():
                    errors.append(
                        f"{_relative_path(path)}: subsystem_results.{subsystem_name} must use non-empty string keys"
                    )
                    break
                if not isinstance(result_value, str) or not result_value.strip():
                    errors.append(
                        f"{_relative_path(path)}: subsystem_results.{subsystem_name}.{result_key} must be a non-empty string"
                    )
    errors.extend(_validate_iso8601_text(payload["verified_at"], field_name="verified_at", path=path))
    if payload["verdict"] == "verified" and (
        payload["expected_composite_hash"] != payload["actual_composite_hash"]
    ):
        errors.append(
            f"{_relative_path(path)}: verified restore_verification must keep expected_composite_hash equal to actual_composite_hash"
        )
    if payload["verdict"] == "hash_mismatch" and (
        payload["expected_composite_hash"] == payload["actual_composite_hash"]
    ):
        errors.append(
            f"{_relative_path(path)}: hash_mismatch restore_verification must keep expected_composite_hash different from actual_composite_hash"
        )
    return errors


def _validate_journal_validation_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "validation_id",
            "epoch_id",
            "entry_count",
            "first_sequence",
            "last_sequence",
            "verdict",
            "gap_positions",
            "detail",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("validation_id", "epoch_id", "verdict", "detail"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["verdict"] not in JOURNAL_VALIDATION_VERDICTS:
        errors.append(
            f"{_relative_path(path)}: field 'verdict' must be one of {', '.join(sorted(JOURNAL_VALIDATION_VERDICTS))}"
        )
    for field_name in ("entry_count", "first_sequence", "last_sequence"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    gap_positions = payload["gap_positions"]
    if not isinstance(gap_positions, list):
        errors.append(f"{_relative_path(path)}: field 'gap_positions' must be an array")
    else:
        for index, gap_position in enumerate(gap_positions):
            errors.extend(
                _require_positive_int(gap_position, field_name=f"gap_positions[{index}]", path=path)
            )
    if payload["entry_count"] == 0:
        if payload["verdict"] != "empty_journal":
            errors.append(f"{_relative_path(path)}: empty journals must use verdict 'empty_journal'")
        if payload["first_sequence"] != 0 or payload["last_sequence"] != 0:
            errors.append(
                f"{_relative_path(path)}: empty journals must keep first_sequence and last_sequence at 0"
            )
    elif payload["first_sequence"] > payload["last_sequence"]:
        errors.append(f"{_relative_path(path)}: first_sequence must be less than or equal to last_sequence")
    if payload["verdict"] == "sequence_gap" and not gap_positions:
        errors.append(f"{_relative_path(path)}: sequence_gap verdict requires at least one gap_positions entry")
    if payload["verdict"] == "valid" and gap_positions:
        errors.append(f"{_relative_path(path)}: valid verdict must not carry gap_positions entries")
    return errors


def _validate_replay_step_result_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "step_id",
            "sequence",
            "kind",
            "verdict",
            "expected_payload",
            "actual_payload",
            "detail",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("step_id", "kind", "verdict", "detail"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    if payload["kind"] not in JOURNAL_ENTRY_KINDS:
        errors.append(
            f"{_relative_path(path)}: field '{f'{prefix}kind'.strip('.')}' must be one of {', '.join(sorted(JOURNAL_ENTRY_KINDS))}"
        )
    if payload["verdict"] not in REPLAY_STEP_VERDICTS:
        errors.append(
            f"{_relative_path(path)}: field '{f'{prefix}verdict'.strip('.')}' must be one of {', '.join(sorted(REPLAY_STEP_VERDICTS))}"
        )
    errors.extend(
        _require_non_negative_int(
            payload["sequence"],
            field_name=f"{prefix}sequence".strip("."),
            path=path,
        )
    )
    for nested_field_name in ("expected_payload", "actual_payload"):
        if not isinstance(payload[nested_field_name], (dict, list)):
            errors.append(
                f"{_relative_path(path)}: field '{f'{prefix}{nested_field_name}'.strip('.')}' must be structured JSON"
            )
    if payload["verdict"] == "match" and (
        payload["expected_payload"] != payload["actual_payload"]
    ):
        errors.append(
            f"{_relative_path(path)}: match replay_step_result must keep expected_payload equal to actual_payload"
        )
    return errors


def _validate_replay_step_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_replay_step_result_dict(payload, path=path, field_name="runtime fixture")


def _validate_replay_session_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "session_id",
            "epoch_id",
            "entries_replayed",
            "entries_matched",
            "entries_diverged",
            "entries_skipped",
            "verdict",
            "steps",
            "started_at",
            "completed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("session_id", "epoch_id", "verdict"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["verdict"] not in REPLAY_SESSION_VERDICTS:
        errors.append(
            f"{_relative_path(path)}: field 'verdict' must be one of {', '.join(sorted(REPLAY_SESSION_VERDICTS))}"
        )
    for field_name in ("entries_replayed", "entries_matched", "entries_diverged", "entries_skipped"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    steps = payload["steps"]
    if not isinstance(steps, list):
        errors.append(f"{_relative_path(path)}: field 'steps' must be an array")
    else:
        for index, step in enumerate(steps):
            errors.extend(
                _validate_replay_step_result_dict(
                    step,
                    path=path,
                    field_name=f"steps[{index}]",
                )
            )
    for field_name in ("started_at", "completed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    total_entries = payload["entries_matched"] + payload["entries_diverged"] + payload["entries_skipped"]
    if total_entries != payload["entries_replayed"]:
        errors.append(
            f"{_relative_path(path)}: entries_matched + entries_diverged + entries_skipped must equal entries_replayed"
        )
    if isinstance(steps, list) and len(steps) != payload["entries_replayed"]:
        errors.append(f"{_relative_path(path)}: steps length must equal entries_replayed")
    if payload["verdict"] == "success" and payload["entries_diverged"] != 0:
        errors.append(f"{_relative_path(path)}: success replay_session_result must keep entries_diverged at 0")
    if payload["verdict"] == "empty_journal" and (
        payload["entries_replayed"] != 0 or (isinstance(steps, list) and steps)
    ):
        errors.append(
            f"{_relative_path(path)}: empty_journal replay_session_result must keep entries_replayed at 0 and steps empty"
        )
    return errors


def _validate_incident_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "incident_id",
            "severity",
            "status",
            "source_type",
            "source_id",
            "failure_family",
            "message",
            "occurred_at",
            "run_id",
            "skill_id",
            "provider_id",
            "escalation_id",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "incident_id",
        "severity",
        "status",
        "source_type",
        "source_id",
        "failure_family",
        "message",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["severity"] not in INCIDENT_SEVERITIES:
        errors.append(
            f"{_relative_path(path)}: field 'severity' must be one of {', '.join(sorted(INCIDENT_SEVERITIES))}"
        )
    if payload["status"] not in INCIDENT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(INCIDENT_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["occurred_at"], field_name="occurred_at", path=path))
    for optional_field_name in ("run_id", "skill_id", "provider_id", "escalation_id"):
        optional_value = payload[optional_field_name]
        if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
            errors.append(
                f"{_relative_path(path)}: field '{optional_field_name}' must be null or a non-empty string"
            )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    elif payload["status"] in {"escalated", "closed"} and payload["escalation_id"] is None:
        errors.append(
            f"{_relative_path(path)}: escalated or closed incident records must carry escalation_id"
        )
    return errors


def _validate_recovery_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "incident_id",
            "action",
            "status",
            "reason",
            "autonomy_mode",
            "profile_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "incident_id", "action", "status", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["action"] not in RECOVERY_ACTIONS:
        errors.append(
            f"{_relative_path(path)}: field 'action' must be one of {', '.join(sorted(RECOVERY_ACTIONS))}"
        )
    if payload["status"] not in RECOVERY_DECISION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(RECOVERY_DECISION_STATUSES))}"
        )
    for optional_field_name in ("autonomy_mode", "profile_id"):
        optional_value = payload[optional_field_name]
        if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
            errors.append(
                f"{_relative_path(path)}: field '{optional_field_name}' must be null or a non-empty string"
            )
    if payload["status"] == "approved" and payload["action"] == "no_action":
        errors.append(
            f"{_relative_path(path)}: approved recovery decisions must not use action 'no_action'"
        )
    if payload["status"] == "not_applicable" and payload["action"] != "no_action":
        errors.append(
            f"{_relative_path(path)}: not_applicable recovery decisions must use action 'no_action'"
        )
    return errors


def _validate_recovery_attempt_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "attempt_id",
            "incident_id",
            "decision_id",
            "action",
            "succeeded",
            "started_at",
            "finished_at",
            "error_message",
            "result_run_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("attempt_id", "incident_id", "decision_id", "action"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["action"] not in RECOVERY_ACTIONS:
        errors.append(
            f"{_relative_path(path)}: field 'action' must be one of {', '.join(sorted(RECOVERY_ACTIONS))}"
        )
    if not isinstance(payload["succeeded"], bool):
        errors.append(f"{_relative_path(path)}: field 'succeeded' must be boolean")
    errors.extend(_validate_iso8601_text(payload["started_at"], field_name="started_at", path=path))
    errors.extend(_validate_iso8601_text(payload["finished_at"], field_name="finished_at", path=path))
    error_message = payload["error_message"]
    if error_message is not None and (not isinstance(error_message, str) or not error_message.strip()):
        errors.append(f"{_relative_path(path)}: field 'error_message' must be null or a non-empty string")
    result_run_id = payload["result_run_id"]
    if result_run_id is not None and (not isinstance(result_run_id, str) or not result_run_id.strip()):
        errors.append(f"{_relative_path(path)}: field 'result_run_id' must be null or a non-empty string")
    if not errors and _parse_iso8601_text(payload["finished_at"]) < _parse_iso8601_text(payload["started_at"]):
        errors.append(f"{_relative_path(path)}: finished_at must be greater than or equal to started_at")
    if payload["succeeded"] and error_message is not None:
        errors.append(f"{_relative_path(path)}: succeeded recovery attempts must keep error_message null")
    if not payload["succeeded"] and error_message is None:
        errors.append(f"{_relative_path(path)}: failed recovery attempts must carry error_message")
    return errors


def _validate_recovery_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "recovery_id",
            "execution_id",
            "trace_id",
            "recorded_at",
            "metadata",
            "extensions",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("recovery_id", "execution_id", "trace_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["recorded_at"], field_name="recorded_at", path=path))
    for mapping_field_name in ("metadata", "extensions"):
        mapping_value = payload[mapping_field_name]
        if not isinstance(mapping_value, dict):
            errors.append(f"{_relative_path(path)}: field '{mapping_field_name}' must be an object")
            continue
        for nested_key in mapping_value:
            if not isinstance(nested_key, str) or not nested_key.strip():
                errors.append(
                    f"{_relative_path(path)}: field '{mapping_field_name}' must use non-empty string keys"
                )
                break
    return errors


def _validate_continuity_plan_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "plan_id",
            "name",
            "tenant_id",
            "scope",
            "status",
            "scope_ref_id",
            "rto_minutes",
            "rpo_minutes",
            "failover_target_ref",
            "owner_ref",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "plan_id",
        "name",
        "tenant_id",
        "scope",
        "status",
        "scope_ref_id",
        "failover_target_ref",
        "owner_ref",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in CONTINUITY_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(CONTINUITY_SCOPES))}"
        )
    if payload["status"] not in CONTINUITY_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(CONTINUITY_STATUSES))}"
        )
    errors.extend(_require_non_negative_int(payload["rto_minutes"], field_name="rto_minutes", path=path))
    errors.extend(_require_non_negative_int(payload["rpo_minutes"], field_name="rpo_minutes", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if payload["rpo_minutes"] > payload["rto_minutes"]:
        errors.append(f"{_relative_path(path)}: rpo_minutes must be less than or equal to rto_minutes")
    return errors


def _validate_recovery_plan_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "recovery_plan_id",
            "plan_id",
            "name",
            "tenant_id",
            "status",
            "priority",
            "description",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("recovery_plan_id", "plan_id", "name", "tenant_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    if payload["status"] not in RECOVERY_EXECUTION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(RECOVERY_EXECUTION_STATUSES))}"
        )
    errors.extend(_require_non_negative_int(payload["priority"], field_name="priority", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_failover_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "failover_id",
            "plan_id",
            "disruption_id",
            "disposition",
            "source_ref",
            "target_ref",
            "initiated_at",
            "completed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "failover_id",
        "plan_id",
        "disruption_id",
        "disposition",
        "source_ref",
        "target_ref",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in FAILOVER_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(FAILOVER_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["initiated_at"], field_name="initiated_at", path=path))
    if not isinstance(payload["completed_at"], str):
        errors.append(f"{_relative_path(path)}: field 'completed_at' must be a string")
    elif payload["completed_at"]:
        errors.extend(_validate_iso8601_text(payload["completed_at"], field_name="completed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if not errors and payload["completed_at"] and _parse_iso8601_text(payload["completed_at"]) < _parse_iso8601_text(payload["initiated_at"]):
        errors.append(f"{_relative_path(path)}: completed_at must be greater than or equal to initiated_at")
    if payload["disposition"] in {"completed", "failed", "rolled_back"} and not payload["completed_at"]:
        errors.append(f"{_relative_path(path)}: terminal failovers must carry completed_at")
    if payload["disposition"] == "initiated" and payload["completed_at"]:
        errors.append(f"{_relative_path(path)}: initiated failovers must keep completed_at empty")
    return errors


def _validate_disruption_event_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "disruption_id",
            "tenant_id",
            "scope",
            "scope_ref_id",
            "severity",
            "description",
            "detected_at",
            "resolved_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("disruption_id", "tenant_id", "scope", "scope_ref_id", "severity", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in CONTINUITY_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(CONTINUITY_SCOPES))}"
        )
    if payload["severity"] not in DISRUPTION_SEVERITIES:
        errors.append(
            f"{_relative_path(path)}: field 'severity' must be one of {', '.join(sorted(DISRUPTION_SEVERITIES))}"
        )
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    errors.extend(_validate_iso8601_text(payload["resolved_at"], field_name="resolved_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if not errors and _parse_iso8601_text(payload["resolved_at"]) < _parse_iso8601_text(payload["detected_at"]):
        errors.append(f"{_relative_path(path)}: resolved_at must be greater than or equal to detected_at")
    return errors


def _validate_recovery_objective_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "objective_id",
            "plan_id",
            "name",
            "target_minutes",
            "actual_minutes",
            "met",
            "evaluated_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("objective_id", "plan_id", "name"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_int(payload["target_minutes"], field_name="target_minutes", path=path))
    errors.extend(_require_non_negative_int(payload["actual_minutes"], field_name="actual_minutes", path=path))
    if not isinstance(payload["met"], bool):
        errors.append(f"{_relative_path(path)}: field 'met' must be a boolean")
    errors.extend(_validate_iso8601_text(payload["evaluated_at"], field_name="evaluated_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if isinstance(payload["met"], bool):
        if payload["met"] and payload["actual_minutes"] > payload["target_minutes"]:
            errors.append(
                f"{_relative_path(path)}: met recovery objectives must keep actual_minutes less than or equal to target_minutes"
            )
        if not payload["met"] and payload["actual_minutes"] <= payload["target_minutes"]:
            errors.append(
                f"{_relative_path(path)}: unmet recovery objectives must keep actual_minutes greater than target_minutes"
            )
    return errors


def _validate_recovery_execution_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "execution_id",
            "recovery_plan_id",
            "disruption_id",
            "status",
            "executed_by",
            "started_at",
            "completed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("execution_id", "recovery_plan_id", "disruption_id", "status", "executed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in RECOVERY_EXECUTION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(RECOVERY_EXECUTION_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["started_at"], field_name="started_at", path=path))
    if not isinstance(payload["completed_at"], str):
        errors.append(f"{_relative_path(path)}: field 'completed_at' must be a string")
    elif payload["completed_at"]:
        errors.extend(_validate_iso8601_text(payload["completed_at"], field_name="completed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if not errors and payload["completed_at"] and _parse_iso8601_text(payload["completed_at"]) < _parse_iso8601_text(payload["started_at"]):
        errors.append(f"{_relative_path(path)}: completed_at must be greater than or equal to started_at")
    if payload["status"] in {"completed", "failed", "cancelled"} and not payload["completed_at"]:
        errors.append(
            f"{_relative_path(path)}: terminal recovery executions must carry completed_at"
        )
    if payload["status"] == "in_progress" and payload["completed_at"]:
        errors.append(
            f"{_relative_path(path)}: in_progress recovery executions must keep completed_at empty"
        )
    return errors


def _validate_verification_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "verification_id",
            "execution_id",
            "status",
            "verified_by",
            "confidence",
            "reason",
            "verified_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("verification_id", "execution_id", "status", "verified_by", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in RECOVERY_VERIFICATION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(RECOVERY_VERIFICATION_STATUSES))}"
        )
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_validate_iso8601_text(payload["verified_at"], field_name="verified_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if payload["status"] == "passed" and payload["confidence"] <= 0.0:
        errors.append(f"{_relative_path(path)}: passed verification records must keep confidence above 0.0")
    return errors


def _validate_continuity_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_plans",
            "total_active_plans",
            "total_recovery_plans",
            "total_disruptions",
            "total_failovers",
            "total_recoveries",
            "total_verifications",
            "total_violations",
            "total_objectives",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_plans",
        "total_active_plans",
        "total_recovery_plans",
        "total_disruptions",
        "total_failovers",
        "total_recoveries",
        "total_verifications",
        "total_violations",
        "total_objectives",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if payload["total_active_plans"] > payload["total_plans"]:
        errors.append(f"{_relative_path(path)}: total_active_plans must not exceed total_plans")
    return errors


def _validate_continuity_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "violation_id",
            "plan_id",
            "tenant_id",
            "operation",
            "reason",
            "detected_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "plan_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_continuity_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_plans",
            "total_disruptions",
            "total_failovers",
            "total_recoveries",
            "total_verifications_passed",
            "total_verifications_failed",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_plans",
        "total_disruptions",
        "total_failovers",
        "total_recoveries",
        "total_verifications_passed",
        "total_verifications_failed",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_delegation_request_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "delegation_id",
            "delegator_id",
            "delegate_id",
            "goal_id",
            "action_scope",
            "deadline",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("delegation_id", "delegator_id", "delegate_id", "goal_id", "action_scope"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["delegator_id"] == payload["delegate_id"]:
        errors.append(f"{_relative_path(path)}: delegator_id and delegate_id must be different")
    if payload["deadline"] is not None:
        errors.extend(_validate_iso8601_text(payload["deadline"], field_name="deadline", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_delegation_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("delegation_id", "status", "reason", "resolved_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("delegation_id", "status", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in DELEGATION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(DELEGATION_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["resolved_at"], field_name="resolved_at", path=path))
    return errors


def _validate_mcoi_handoff_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "handoff_id",
            "from_party",
            "to_party",
            "goal_id",
            "context_ids",
            "handed_off_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("handoff_id", "from_party", "to_party", "goal_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["from_party"] == payload["to_party"]:
        errors.append(f"{_relative_path(path)}: from_party and to_party must be different")
    context_ids = payload["context_ids"]
    if not isinstance(context_ids, list) or not context_ids:
        errors.append(f"{_relative_path(path)}: field 'context_ids' must be a non-empty array")
    elif not errors:
        for index, context_id in enumerate(context_ids):
            errors.extend(_require_non_empty_text(context_id, field_name=f"context_ids[{index}]", path=path))
    errors.extend(_validate_iso8601_text(payload["handed_off_at"], field_name="handed_off_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_merge_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("merge_id", "goal_id", "source_ids", "outcome", "reason", "resolved_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("merge_id", "goal_id", "outcome", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    source_ids = payload["source_ids"]
    if not isinstance(source_ids, list) or len(source_ids) < 2:
        errors.append(f"{_relative_path(path)}: field 'source_ids' must contain at least two items")
    else:
        for index, source_id in enumerate(source_ids):
            errors.extend(_require_non_empty_text(source_id, field_name=f"source_ids[{index}]", path=path))
    if payload["outcome"] not in MERGE_OUTCOMES:
        errors.append(
            f"{_relative_path(path)}: field 'outcome' must be one of {', '.join(sorted(MERGE_OUTCOMES))}"
        )
    errors.extend(_validate_iso8601_text(payload["resolved_at"], field_name="resolved_at", path=path))
    return errors


def _validate_conflict_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    required_fields = {"conflict_id", "goal_id", "conflicting_ids", "strategy", "resolved", "metadata"}
    optional_fields = {"resolution_id"}
    actual_fields = set(payload)
    missing_fields = sorted(required_fields - actual_fields)
    unexpected_fields = sorted(actual_fields - required_fields - optional_fields)
    errors: list[str] = []
    if missing_fields:
        errors.append(
            f"{_relative_path(path)}: runtime fixture missing required fields {', '.join(repr(name) for name in missing_fields)}"
        )
    if unexpected_fields:
        errors.append(
            f"{_relative_path(path)}: runtime fixture has unexpected fields {', '.join(repr(name) for name in unexpected_fields)}"
        )
    if errors:
        return errors
    for field_name in ("conflict_id", "goal_id", "strategy"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    conflicting_ids = payload["conflicting_ids"]
    if not isinstance(conflicting_ids, list) or len(conflicting_ids) < 2:
        errors.append(f"{_relative_path(path)}: field 'conflicting_ids' must contain at least two items")
    else:
        for index, conflicting_id in enumerate(conflicting_ids):
            errors.extend(_require_non_empty_text(conflicting_id, field_name=f"conflicting_ids[{index}]", path=path))
    if payload["strategy"] not in CONFLICT_STRATEGIES:
        errors.append(
            f"{_relative_path(path)}: field 'strategy' must be one of {', '.join(sorted(CONFLICT_STRATEGIES))}"
        )
    if not isinstance(payload["resolved"], bool):
        errors.append(f"{_relative_path(path)}: field 'resolved' must be a boolean")
    resolution_id = payload.get("resolution_id")
    if resolution_id is not None:
        errors.extend(_require_non_empty_text(resolution_id, field_name="resolution_id", path=path))
    if payload["resolved"] is True and resolution_id is None:
        errors.append(f"{_relative_path(path)}: resolved conflicts must carry resolution_id")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_case_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "case_id",
            "tenant_id",
            "kind",
            "severity",
            "status",
            "title",
            "description",
            "opened_by",
            "opened_at",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("case_id", "tenant_id", "kind", "severity", "status", "title", "opened_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    if payload["kind"] not in CASE_KINDS:
        errors.append(f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(CASE_KINDS))}")
    if payload["severity"] not in CASE_SEVERITIES:
        errors.append(f"{_relative_path(path)}: field 'severity' must be one of {', '.join(sorted(CASE_SEVERITIES))}")
    if payload["status"] not in CASE_STATUSES:
        errors.append(f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(CASE_STATUSES))}")
    errors.extend(_validate_iso8601_text(payload["opened_at"], field_name="opened_at", path=path))
    if not isinstance(payload["closed_at"], str):
        errors.append(f"{_relative_path(path)}: field 'closed_at' must be a string")
    elif payload["closed_at"]:
        errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    if payload["status"] == "closed" and not payload["closed_at"]:
        errors.append(f"{_relative_path(path)}: closed cases must carry closed_at")
    if payload["status"] != "closed" and payload["closed_at"]:
        errors.append(f"{_relative_path(path)}: non-closed cases must keep closed_at empty")
    if not errors and payload["closed_at"] and _parse_iso8601_text(payload["closed_at"]) < _parse_iso8601_text(payload["opened_at"]):
        errors.append(f"{_relative_path(path)}: closed_at must be greater than or equal to opened_at")
    return errors


def _validate_evidence_item_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "evidence_id",
            "case_id",
            "source_type",
            "source_id",
            "status",
            "title",
            "description",
            "submitted_by",
            "submitted_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("evidence_id", "case_id", "source_type", "source_id", "status", "title", "submitted_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    if payload["status"] not in EVIDENCE_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(EVIDENCE_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["submitted_at"], field_name="submitted_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_review_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "review_id",
            "case_id",
            "evidence_id",
            "reviewer_id",
            "disposition",
            "notes",
            "reviewed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("review_id", "case_id", "evidence_id", "reviewer_id", "disposition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["notes"], str):
        errors.append(f"{_relative_path(path)}: field 'notes' must be a string")
    if payload["disposition"] not in REVIEW_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(REVIEW_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["reviewed_at"], field_name="reviewed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_case_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("decision_id", "case_id", "disposition", "decided_by", "reason", "decided_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "case_id", "disposition", "decided_by", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in CASE_CLOSURE_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(CASE_CLOSURE_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_case_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "case_id",
            "tenant_id",
            "disposition",
            "total_evidence",
            "total_reviews",
            "total_findings",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "case_id", "tenant_id", "disposition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in CASE_CLOSURE_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(CASE_CLOSURE_DISPOSITIONS))}"
        )
    for field_name in ("total_evidence", "total_reviews", "total_findings", "total_violations"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_case_assignment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("assignment_id", "case_id", "assignee_id", "role", "assigned_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assignment_id", "case_id", "assignee_id", "role"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["assigned_at"], field_name="assigned_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_evidence_collection_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("collection_id", "case_id", "title", "evidence_ids", "created_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("collection_id", "case_id", "title"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    evidence_ids = payload["evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids:
        errors.append(f"{_relative_path(path)}: field 'evidence_ids' must be a non-empty array")
    else:
        for index, evidence_id in enumerate(evidence_ids):
            errors.extend(_require_non_empty_text(evidence_id, field_name=f"evidence_ids[{index}]", path=path))
        if len(set(evidence_ids)) != len(evidence_ids):
            errors.append(f"{_relative_path(path)}: field 'evidence_ids' must not contain duplicates")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_finding_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "finding_id",
            "case_id",
            "severity",
            "title",
            "description",
            "evidence_ids",
            "remediation",
            "found_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("finding_id", "case_id", "severity", "title"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["severity"] not in CASE_SEVERITIES | {"informational"}:
        errors.append(
            f"{_relative_path(path)}: field 'severity' must be one of informational, {', '.join(sorted(CASE_SEVERITIES))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    evidence_ids = payload["evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids:
        errors.append(f"{_relative_path(path)}: field 'evidence_ids' must be a non-empty array")
    else:
        for index, evidence_id in enumerate(evidence_ids):
            errors.extend(_require_non_empty_text(evidence_id, field_name=f"evidence_ids[{index}]", path=path))
        if len(set(evidence_ids)) != len(evidence_ids):
            errors.append(f"{_relative_path(path)}: field 'evidence_ids' must not contain duplicates")
    if not isinstance(payload["remediation"], str):
        errors.append(f"{_relative_path(path)}: field 'remediation' must be a string")
    errors.extend(_validate_iso8601_text(payload["found_at"], field_name="found_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_case_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "scope_ref_id",
            "total_cases",
            "open_cases",
            "total_evidence",
            "total_reviews",
            "total_findings",
            "total_decisions",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("snapshot_id", "scope_ref_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_cases",
        "open_cases",
        "total_evidence",
        "total_reviews",
        "total_findings",
        "total_decisions",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["open_cases"] > payload["total_cases"]:
        errors.append(f"{_relative_path(path)}: field 'open_cases' must not exceed total_cases")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_case_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "case_id", "tenant_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "case_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_human_task_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "task_id",
            "tenant_id",
            "assignee_ref",
            "status",
            "scope",
            "scope_ref_id",
            "title",
            "description",
            "due_at",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("task_id", "tenant_id", "assignee_ref", "status", "scope", "scope_ref_id", "title"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in HUMAN_TASK_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(HUMAN_TASK_STATUSES))}"
        )
    if payload["scope"] not in COLLABORATION_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(COLLABORATION_SCOPES))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    if not isinstance(payload["due_at"], str):
        errors.append(f"{_relative_path(path)}: field 'due_at' must be a string")
    elif payload["due_at"]:
        errors.extend(_validate_iso8601_text(payload["due_at"], field_name="due_at", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if (
        not errors
        and payload["due_at"]
        and _parse_iso8601_text(payload["due_at"]) < _parse_iso8601_text(payload["created_at"])
    ):
        errors.append(f"{_relative_path(path)}: due_at must be greater than or equal to created_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_review_packet_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "packet_id",
            "tenant_id",
            "scope",
            "scope_ref_id",
            "review_mode",
            "title",
            "reviewer_count",
            "reviews_completed",
            "reviews_approved",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("packet_id", "tenant_id", "scope", "scope_ref_id", "review_mode", "title"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in COLLABORATION_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(COLLABORATION_SCOPES))}"
        )
    if payload["review_mode"] not in HUMAN_REVIEW_MODES:
        errors.append(
            f"{_relative_path(path)}: field 'review_mode' must be one of {', '.join(sorted(HUMAN_REVIEW_MODES))}"
        )
    for field_name in ("reviewer_count", "reviews_completed", "reviews_approved"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["reviews_completed"] > payload["reviewer_count"]:
        errors.append(f"{_relative_path(path)}: reviews_completed must not exceed reviewer_count")
    if not errors and payload["reviews_approved"] > payload["reviews_completed"]:
        errors.append(f"{_relative_path(path)}: reviews_approved must not exceed reviews_completed")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_approval_board_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "board_id",
            "tenant_id",
            "name",
            "approval_mode",
            "quorum_required",
            "scope",
            "scope_ref_id",
            "member_count",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("board_id", "tenant_id", "name", "approval_mode", "scope", "scope_ref_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["approval_mode"] not in APPROVAL_MODES:
        errors.append(
            f"{_relative_path(path)}: field 'approval_mode' must be one of {', '.join(sorted(APPROVAL_MODES))}"
        )
    if payload["scope"] not in COLLABORATION_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(COLLABORATION_SCOPES))}"
        )
    errors.extend(_require_positive_int(payload["quorum_required"], field_name="quorum_required", path=path))
    errors.extend(_require_non_negative_int(payload["member_count"], field_name="member_count", path=path))
    if not errors and payload["member_count"] > 0 and payload["quorum_required"] > payload["member_count"]:
        errors.append(f"{_relative_path(path)}: quorum_required must not exceed member_count")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_board_member_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("member_id", "board_id", "identity_ref", "role", "added_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("member_id", "board_id", "identity_ref", "role"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["added_at"], field_name="added_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_board_vote_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("vote_id", "board_id", "member_id", "scope_ref_id", "approved", "reason", "voted_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("vote_id", "board_id", "member_id", "scope_ref_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["approved"], bool):
        errors.append(f"{_relative_path(path)}: field 'approved' must be a boolean")
    if not isinstance(payload["reason"], str):
        errors.append(f"{_relative_path(path)}: field 'reason' must be a string")
    errors.extend(_validate_iso8601_text(payload["voted_at"], field_name="voted_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_collaborative_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "board_id",
            "scope_ref_id",
            "status",
            "total_votes",
            "approvals",
            "rejections",
            "decided_by",
            "decided_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "board_id", "scope_ref_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in BOARD_DECISION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(BOARD_DECISION_STATUSES))}"
        )
    for field_name in ("total_votes", "approvals", "rejections"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["approvals"] + payload["rejections"] > payload["total_votes"]:
        errors.append(f"{_relative_path(path)}: approvals plus rejections must not exceed total_votes")
    if payload["status"] != "pending":
        errors.extend(_require_non_empty_text(payload["decided_by"], field_name="decided_by", path=path))
    elif not isinstance(payload["decided_by"], str):
        errors.append(f"{_relative_path(path)}: field 'decided_by' must be a string")
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_handoff_packet_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "handoff_id",
            "tenant_id",
            "scope",
            "scope_ref_id",
            "from_ref",
            "to_ref",
            "direction",
            "reason",
            "handed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("handoff_id", "tenant_id", "scope", "scope_ref_id", "from_ref", "to_ref", "direction"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in COLLABORATION_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(COLLABORATION_SCOPES))}"
        )
    if payload["from_ref"] == payload["to_ref"]:
        errors.append(f"{_relative_path(path)}: from_ref and to_ref must be different")
    if not isinstance(payload["reason"], str):
        errors.append(f"{_relative_path(path)}: field 'reason' must be a string")
    errors.extend(_validate_iso8601_text(payload["handed_at"], field_name="handed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_human_workflow_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_tasks",
            "total_review_packets",
            "total_boards",
            "total_members",
            "total_votes",
            "total_decisions",
            "total_handoffs",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_tasks",
        "total_review_packets",
        "total_boards",
        "total_members",
        "total_votes",
        "total_decisions",
        "total_handoffs",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_human_workflow_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "tenant_id", "scope_ref_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "tenant_id", "scope_ref_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_human_workflow_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_tasks",
            "total_review_packets",
            "total_boards",
            "total_decisions_approved",
            "total_decisions_rejected",
            "total_handoffs",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_tasks",
        "total_review_packets",
        "total_boards",
        "total_decisions_approved",
        "total_decisions_rejected",
        "total_handoffs",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_attestation_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "attestation_id",
            "tenant_id",
            "scope",
            "scope_ref_id",
            "level",
            "status",
            "attested_by",
            "attested_at",
            "expires_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("attestation_id", "tenant_id", "scope", "scope_ref_id", "level", "status", "attested_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in ASSURANCE_SCOPES:
        errors.append(f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(ASSURANCE_SCOPES))}")
    if payload["level"] not in ASSURANCE_LEVELS:
        errors.append(f"{_relative_path(path)}: field 'level' must be one of {', '.join(sorted(ASSURANCE_LEVELS))}")
    if payload["status"] not in ATTESTATION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(ATTESTATION_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["attested_at"], field_name="attested_at", path=path))
    if not isinstance(payload["expires_at"], str):
        errors.append(f"{_relative_path(path)}: field 'expires_at' must be a string")
    elif payload["expires_at"]:
        errors.extend(_validate_iso8601_text(payload["expires_at"], field_name="expires_at", path=path))
    if (
        not errors
        and payload["expires_at"]
        and _parse_iso8601_text(payload["expires_at"]) < _parse_iso8601_text(payload["attested_at"])
    ):
        errors.append(f"{_relative_path(path)}: expires_at must be greater than or equal to attested_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_certification_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "certification_id",
            "tenant_id",
            "scope",
            "scope_ref_id",
            "status",
            "level",
            "certified_by",
            "certified_at",
            "expires_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("certification_id", "tenant_id", "scope", "scope_ref_id", "status", "level", "certified_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in ASSURANCE_SCOPES:
        errors.append(f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(ASSURANCE_SCOPES))}")
    if payload["status"] not in CERTIFICATION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(CERTIFICATION_STATUSES))}"
        )
    if payload["level"] not in ASSURANCE_LEVELS:
        errors.append(f"{_relative_path(path)}: field 'level' must be one of {', '.join(sorted(ASSURANCE_LEVELS))}")
    errors.extend(_validate_iso8601_text(payload["certified_at"], field_name="certified_at", path=path))
    if not isinstance(payload["expires_at"], str):
        errors.append(f"{_relative_path(path)}: field 'expires_at' must be a string")
    elif payload["expires_at"]:
        errors.extend(_validate_iso8601_text(payload["expires_at"], field_name="expires_at", path=path))
    if (
        not errors
        and payload["expires_at"]
        and _parse_iso8601_text(payload["expires_at"]) < _parse_iso8601_text(payload["certified_at"])
    ):
        errors.append(f"{_relative_path(path)}: expires_at must be greater than or equal to certified_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_assessment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assessment_id",
            "tenant_id",
            "scope",
            "scope_ref_id",
            "level",
            "sufficiency",
            "confidence",
            "assessed_by",
            "assessed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assessment_id", "tenant_id", "scope", "scope_ref_id", "level", "sufficiency", "assessed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in ASSURANCE_SCOPES:
        errors.append(f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(ASSURANCE_SCOPES))}")
    if payload["level"] not in ASSURANCE_LEVELS:
        errors.append(f"{_relative_path(path)}: field 'level' must be one of {', '.join(sorted(ASSURANCE_LEVELS))}")
    if payload["sufficiency"] not in EVIDENCE_SUFFICIENCY_LEVELS:
        errors.append(
            f"{_relative_path(path)}: field 'sufficiency' must be one of {', '.join(sorted(EVIDENCE_SUFFICIENCY_LEVELS))}"
        )
    errors.extend(
        _require_number_in_range(payload["confidence"], field_name="confidence", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_evidence_binding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("binding_id", "target_id", "target_type", "source_type", "source_id", "bound_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("binding_id", "target_id", "target_type", "source_type", "source_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["bound_at"], field_name="bound_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_recertification_window_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("window_id", "certification_id", "status", "starts_at", "ends_at", "completed_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("window_id", "certification_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in RECERTIFICATION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(RECERTIFICATION_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["starts_at"], field_name="starts_at", path=path))
    errors.extend(_validate_iso8601_text(payload["ends_at"], field_name="ends_at", path=path))
    if not isinstance(payload["completed_at"], str):
        errors.append(f"{_relative_path(path)}: field 'completed_at' must be a string")
    elif payload["completed_at"]:
        errors.extend(_validate_iso8601_text(payload["completed_at"], field_name="completed_at", path=path))
    if not errors and _parse_iso8601_text(payload["ends_at"]) < _parse_iso8601_text(payload["starts_at"]):
        errors.append(f"{_relative_path(path)}: ends_at must be greater than or equal to starts_at")
    if payload["status"] == "completed" and not payload["completed_at"]:
        errors.append(f"{_relative_path(path)}: completed recertification windows must carry completed_at")
    if payload["status"] != "completed" and payload["completed_at"]:
        errors.append(f"{_relative_path(path)}: non-completed recertification windows must keep completed_at empty")
    if (
        not errors
        and payload["completed_at"]
        and _parse_iso8601_text(payload["completed_at"]) < _parse_iso8601_text(payload["starts_at"])
    ):
        errors.append(f"{_relative_path(path)}: completed_at must be greater than or equal to starts_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_finding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("finding_id", "target_id", "target_type", "description", "impact_level", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("finding_id", "target_id", "target_type", "impact_level"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["impact_level"] not in ASSURANCE_LEVELS:
        errors.append(
            f"{_relative_path(path)}: field 'impact_level' must be one of {', '.join(sorted(ASSURANCE_LEVELS))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("decision_id", "target_id", "target_type", "level", "decided_by", "reason", "decided_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "target_id", "target_type", "level", "decided_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["level"] not in ASSURANCE_LEVELS:
        errors.append(f"{_relative_path(path)}: field 'level' must be one of {', '.join(sorted(ASSURANCE_LEVELS))}")
    if not isinstance(payload["reason"], str):
        errors.append(f"{_relative_path(path)}: field 'reason' must be a string")
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "scope_ref_id",
            "total_attestations",
            "granted_attestations",
            "total_certifications",
            "active_certifications",
            "total_assessments",
            "total_evidence_bindings",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    errors.extend(_require_non_empty_text(payload["scope_ref_id"], field_name="scope_ref_id", path=path))
    for field_name in (
        "total_attestations",
        "granted_attestations",
        "total_certifications",
        "active_certifications",
        "total_assessments",
        "total_evidence_bindings",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["granted_attestations"] > payload["total_attestations"]:
        errors.append(f"{_relative_path(path)}: granted_attestations must not exceed total_attestations")
    if not errors and payload["active_certifications"] > payload["total_certifications"]:
        errors.append(f"{_relative_path(path)}: active_certifications must not exceed total_certifications")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "target_id", "target_type", "tenant_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "target_id", "target_type", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assurance_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "target_id",
            "target_type",
            "tenant_id",
            "final_level",
            "total_evidence_bindings",
            "total_assessments",
            "total_findings",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "target_id", "target_type", "tenant_id", "final_level"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["final_level"] not in ASSURANCE_LEVELS:
        errors.append(
            f"{_relative_path(path)}: field 'final_level' must be one of {', '.join(sorted(ASSURANCE_LEVELS))}"
        )
    for field_name in ("total_evidence_bindings", "total_assessments", "total_findings", "total_violations"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_governance_contract_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "contract_id",
            "tenant_id",
            "counterparty",
            "status",
            "title",
            "description",
            "effective_at",
            "expires_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("contract_id", "tenant_id", "counterparty", "status", "title"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in CONTRACT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(CONTRACT_STATUSES))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    errors.extend(_validate_iso8601_text(payload["effective_at"], field_name="effective_at", path=path))
    if not isinstance(payload["expires_at"], str):
        errors.append(f"{_relative_path(path)}: field 'expires_at' must be a string")
    elif payload["expires_at"]:
        errors.extend(_validate_iso8601_text(payload["expires_at"], field_name="expires_at", path=path))
    if (
        not errors
        and payload["expires_at"]
        and _parse_iso8601_text(payload["expires_at"]) < _parse_iso8601_text(payload["effective_at"])
    ):
        errors.append(f"{_relative_path(path)}: expires_at must be greater than or equal to effective_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_contract_clause_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("clause_id", "contract_id", "title", "description", "commitment_kind", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("clause_id", "contract_id", "title", "commitment_kind"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["commitment_kind"] not in COMMITMENT_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'commitment_kind' must be one of {', '.join(sorted(COMMITMENT_KINDS))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_commitment_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "commitment_id",
            "contract_id",
            "clause_id",
            "tenant_id",
            "kind",
            "target_value",
            "scope_ref_id",
            "scope_ref_type",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "commitment_id",
        "contract_id",
        "clause_id",
        "tenant_id",
        "kind",
        "target_value",
        "scope_ref_id",
        "scope_ref_type",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in COMMITMENT_KINDS:
        errors.append(f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(COMMITMENT_KINDS))}")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_sla_window_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("window_id", "commitment_id", "status", "opens_at", "closes_at", "actual_value", "compliance", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("window_id", "commitment_id", "status", "actual_value"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in SLA_STATUSES:
        errors.append(f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(SLA_STATUSES))}")
    errors.extend(_validate_iso8601_text(payload["opens_at"], field_name="opens_at", path=path))
    errors.extend(_validate_iso8601_text(payload["closes_at"], field_name="closes_at", path=path))
    errors.extend(
        _require_number_in_range(payload["compliance"], field_name="compliance", path=path, minimum=0.0, maximum=1.0)
    )
    if not errors and _parse_iso8601_text(payload["closes_at"]) < _parse_iso8601_text(payload["opens_at"]):
        errors.append(f"{_relative_path(path)}: closes_at must be greater than or equal to opens_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_breach_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("breach_id", "commitment_id", "contract_id", "tenant_id", "severity", "description", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("breach_id", "commitment_id", "contract_id", "tenant_id", "severity"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["severity"] not in BREACH_SEVERITIES:
        errors.append(
            f"{_relative_path(path)}: field 'severity' must be one of {', '.join(sorted(BREACH_SEVERITIES))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_remedy_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("remedy_id", "breach_id", "tenant_id", "disposition", "amount", "description", "applied_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("remedy_id", "breach_id", "tenant_id", "disposition", "amount"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in REMEDY_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(REMEDY_DISPOSITIONS))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    errors.extend(_validate_iso8601_text(payload["applied_at"], field_name="applied_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_renewal_window_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("window_id", "contract_id", "status", "opens_at", "closes_at", "completed_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("window_id", "contract_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in RENEWAL_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(RENEWAL_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["opens_at"], field_name="opens_at", path=path))
    errors.extend(_validate_iso8601_text(payload["closes_at"], field_name="closes_at", path=path))
    if not isinstance(payload["completed_at"], str):
        errors.append(f"{_relative_path(path)}: field 'completed_at' must be a string")
    elif payload["completed_at"]:
        errors.extend(_validate_iso8601_text(payload["completed_at"], field_name="completed_at", path=path))
    if not errors and _parse_iso8601_text(payload["closes_at"]) < _parse_iso8601_text(payload["opens_at"]):
        errors.append(f"{_relative_path(path)}: closes_at must be greater than or equal to opens_at")
    if payload["status"] == "completed" and not payload["completed_at"]:
        errors.append(f"{_relative_path(path)}: completed renewal windows must carry completed_at")
    if payload["status"] != "completed" and payload["completed_at"]:
        errors.append(f"{_relative_path(path)}: non-completed renewal windows must keep completed_at empty")
    if (
        not errors
        and payload["completed_at"]
        and _parse_iso8601_text(payload["completed_at"]) < _parse_iso8601_text(payload["opens_at"])
    ):
        errors.append(f"{_relative_path(path)}: completed_at must be greater than or equal to opens_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_contract_assessment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assessment_id",
            "contract_id",
            "tenant_id",
            "total_commitments",
            "healthy_commitments",
            "at_risk_commitments",
            "breached_commitments",
            "overall_compliance",
            "assessed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assessment_id", "contract_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_commitments", "healthy_commitments", "at_risk_commitments", "breached_commitments"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["overall_compliance"], field_name="overall_compliance", path=path, minimum=0.0, maximum=1.0
        )
    )
    if (
        not errors
        and payload["healthy_commitments"] + payload["at_risk_commitments"] + payload["breached_commitments"]
        > payload["total_commitments"]
    ):
        errors.append(
            f"{_relative_path(path)}: healthy_commitments plus at_risk_commitments plus breached_commitments must not exceed total_commitments"
        )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_contract_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_contracts",
            "active_contracts",
            "total_commitments",
            "total_sla_windows",
            "total_breaches",
            "total_remedies",
            "total_renewals",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_contracts",
        "active_contracts",
        "total_commitments",
        "total_sla_windows",
        "total_breaches",
        "total_remedies",
        "total_renewals",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["active_contracts"] > payload["total_contracts"]:
        errors.append(f"{_relative_path(path)}: active_contracts must not exceed total_contracts")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_contract_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "contract_id",
            "tenant_id",
            "final_status",
            "total_commitments",
            "total_breaches",
            "total_remedies",
            "total_renewals",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "contract_id", "tenant_id", "final_status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["final_status"] not in CONTRACT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'final_status' must be one of {', '.join(sorted(CONTRACT_STATUSES))}"
        )
    for field_name in ("total_commitments", "total_breaches", "total_remedies", "total_renewals"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "asset_id",
            "name",
            "tenant_id",
            "kind",
            "status",
            "ownership",
            "owner_ref",
            "vendor_ref",
            "value",
            "registered_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("asset_id", "name", "tenant_id", "kind", "status", "ownership", "owner_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in ASSET_KINDS:
        errors.append(f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(ASSET_KINDS))}")
    if payload["status"] not in ASSET_STATUSES:
        errors.append(f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(ASSET_STATUSES))}")
    if payload["ownership"] not in OWNERSHIP_TYPES:
        errors.append(f"{_relative_path(path)}: field 'ownership' must be one of {', '.join(sorted(OWNERSHIP_TYPES))}")
    if not isinstance(payload["vendor_ref"], str):
        errors.append(f"{_relative_path(path)}: field 'vendor_ref' must be a string")
    errors.extend(_require_non_negative_float(payload["value"], field_name="value", path=path))
    errors.extend(_validate_iso8601_text(payload["registered_at"], field_name="registered_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_configuration_item_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "ci_id",
            "asset_id",
            "name",
            "status",
            "environment_ref",
            "workspace_ref",
            "version",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("ci_id", "asset_id", "name", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in CONFIGURATION_ITEM_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(CONFIGURATION_ITEM_STATUSES))}"
        )
    for field_name in ("environment_ref", "workspace_ref", "version"):
        if not isinstance(payload[field_name], str):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be a string")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_inventory_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "inventory_id",
            "asset_id",
            "tenant_id",
            "disposition",
            "total_quantity",
            "assigned_quantity",
            "available_quantity",
            "updated_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("inventory_id", "asset_id", "tenant_id", "disposition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in INVENTORY_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(INVENTORY_DISPOSITIONS))}"
        )
    for field_name in ("total_quantity", "assigned_quantity", "available_quantity"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["assigned_quantity"] + payload["available_quantity"] > payload["total_quantity"]:
        errors.append(
            f"{_relative_path(path)}: assigned_quantity plus available_quantity must not exceed total_quantity"
        )
    errors.extend(_validate_iso8601_text(payload["updated_at"], field_name="updated_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_assignment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assignment_id",
            "asset_id",
            "scope_ref_id",
            "scope_ref_type",
            "assigned_by",
            "assigned_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assignment_id", "asset_id", "scope_ref_id", "scope_ref_type", "assigned_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["assigned_at"], field_name="assigned_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_dependency_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("dependency_id", "asset_id", "depends_on_asset_id", "description", "created_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("dependency_id", "asset_id", "depends_on_asset_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["asset_id"] == payload["depends_on_asset_id"]:
        errors.append(f"{_relative_path(path)}: asset_id and depends_on_asset_id must be different")
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_lifecycle_event_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("event_id", "asset_id", "disposition", "description", "performed_by", "performed_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("event_id", "asset_id", "disposition", "performed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in LIFECYCLE_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(LIFECYCLE_DISPOSITIONS))}"
        )
    if not isinstance(payload["description"], str):
        errors.append(f"{_relative_path(path)}: field 'description' must be a string")
    errors.extend(_validate_iso8601_text(payload["performed_at"], field_name="performed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_assessment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("assessment_id", "asset_id", "health_score", "risk_score", "assessed_by", "assessed_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assessment_id", "asset_id", "assessed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(payload["health_score"], field_name="health_score", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(
        _require_number_in_range(payload["risk_score"], field_name="risk_score", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_assets",
            "total_active",
            "total_retired",
            "total_config_items",
            "total_inventory",
            "total_assignments",
            "total_dependencies",
            "total_violations",
            "total_asset_value",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_assets",
        "total_active",
        "total_retired",
        "total_config_items",
        "total_inventory",
        "total_assignments",
        "total_dependencies",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["total_asset_value"], field_name="total_asset_value", path=path))
    if not errors and payload["total_active"] + payload["total_retired"] > payload["total_assets"]:
        errors.append(f"{_relative_path(path)}: total_active plus total_retired must not exceed total_assets")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "asset_id", "tenant_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "asset_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_asset_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_assets",
            "total_active",
            "total_retired",
            "total_assignments",
            "total_dependencies",
            "total_asset_value",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_assets", "total_active", "total_retired", "total_assignments", "total_dependencies"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["total_asset_value"], field_name="total_asset_value", path=path))
    if not errors and payload["total_active"] + payload["total_retired"] > payload["total_assets"]:
        errors.append(f"{_relative_path(path)}: total_active plus total_retired must not exceed total_assets")
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_billing_account_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("account_id", "tenant_id", "counterparty", "status", "currency", "created_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("account_id", "tenant_id", "counterparty", "status", "currency"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in BILLING_STATUSES:
        errors.append(f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(BILLING_STATUSES))}")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_invoice_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "invoice_id",
            "account_id",
            "tenant_id",
            "status",
            "total_amount",
            "currency",
            "issued_at",
            "due_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("invoice_id", "account_id", "tenant_id", "status", "currency"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in INVOICE_STATUSES:
        errors.append(f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(INVOICE_STATUSES))}")
    errors.extend(_require_non_negative_float(payload["total_amount"], field_name="total_amount", path=path))
    errors.extend(_validate_iso8601_text(payload["issued_at"], field_name="issued_at", path=path))
    errors.extend(_validate_iso8601_text(payload["due_at"], field_name="due_at", path=path))
    if not errors and _parse_iso8601_text(payload["due_at"]) < _parse_iso8601_text(payload["issued_at"]):
        errors.append(f"{_relative_path(path)}: due_at must not precede issued_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_charge_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "charge_id",
            "invoice_id",
            "kind",
            "description",
            "amount",
            "scope_ref_id",
            "scope_ref_type",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("charge_id", "invoice_id", "kind", "description", "scope_ref_id", "scope_ref_type"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in CHARGE_KINDS:
        errors.append(f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(CHARGE_KINDS))}")
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_credit_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "credit_id",
            "account_id",
            "breach_id",
            "disposition",
            "amount",
            "reason",
            "applied_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("credit_id", "account_id", "breach_id", "disposition", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in CREDIT_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(CREDIT_DISPOSITIONS))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["applied_at"], field_name="applied_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_penalty_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("penalty_id", "account_id", "breach_id", "amount", "reason", "assessed_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("penalty_id", "account_id", "breach_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_dispute_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "dispute_id",
            "invoice_id",
            "account_id",
            "status",
            "reason",
            "amount",
            "opened_at",
            "resolved_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("dispute_id", "invoice_id", "account_id", "status", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in DISPUTE_STATUSES:
        errors.append(f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(DISPUTE_STATUSES))}")
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["opened_at"], field_name="opened_at", path=path))
    terminal_statuses = {"resolved_accepted", "resolved_rejected", "withdrawn"}
    if payload["status"] in terminal_statuses:
        errors.extend(_validate_iso8601_text(payload["resolved_at"], field_name="resolved_at", path=path))
        if not errors and _parse_iso8601_text(payload["resolved_at"]) < _parse_iso8601_text(payload["opened_at"]):
            errors.append(f"{_relative_path(path)}: resolved_at must not precede opened_at")
    elif payload["resolved_at"] != "":
        errors.append(f"{_relative_path(path)}: non-terminal disputes must use an empty resolved_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_revenue_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_accounts",
            "total_invoices",
            "total_charges",
            "total_credits",
            "total_penalties",
            "total_disputes",
            "total_recognized_revenue",
            "total_pending_revenue",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_accounts",
        "total_invoices",
        "total_charges",
        "total_credits",
        "total_penalties",
        "total_disputes",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_recognized_revenue", "total_pending_revenue"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["total_disputes"] > payload["total_invoices"]:
        errors.append(f"{_relative_path(path)}: total_disputes must not exceed total_invoices")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_billing_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("decision_id", "account_id", "description", "decided_by", "decided_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "account_id", "description", "decided_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_billing_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "account_id", "tenant_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "account_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_billing_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "account_id",
            "tenant_id",
            "total_invoices",
            "total_charges",
            "total_credits",
            "total_penalties",
            "total_disputes",
            "total_revenue",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "account_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_invoices", "total_charges", "total_credits", "total_penalties", "total_disputes"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["total_revenue"], field_name="total_revenue", path=path))
    if not errors and payload["total_disputes"] > payload["total_invoices"]:
        errors.append(f"{_relative_path(path)}: total_disputes must not exceed total_invoices")
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_payment_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "payment_id",
            "invoice_id",
            "account_id",
            "amount",
            "currency",
            "method",
            "status",
            "reference",
            "received_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("payment_id", "invoice_id", "account_id", "currency", "method", "status", "reference"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["method"] not in PAYMENT_METHOD_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'method' must be one of {', '.join(sorted(PAYMENT_METHOD_KINDS))}"
        )
    if payload["status"] not in PAYMENT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(PAYMENT_STATUSES))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["received_at"], field_name="received_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_settlement_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "settlement_id",
            "invoice_id",
            "account_id",
            "total_amount",
            "paid_amount",
            "credit_applied",
            "outstanding",
            "status",
            "currency",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("settlement_id", "invoice_id", "account_id", "status", "currency"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in SETTLEMENT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(SETTLEMENT_STATUSES))}"
        )
    for field_name in ("total_amount", "paid_amount", "credit_applied", "outstanding"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    if not errors:
        reconciled = payload["paid_amount"] + payload["credit_applied"] + payload["outstanding"]
        if abs(reconciled - payload["total_amount"]) > 1e-9:
            errors.append(
                f"{_relative_path(path)}: paid_amount plus credit_applied plus outstanding must equal total_amount"
            )
        if payload["status"] == "settled" and payload["outstanding"] != 0.0:
            errors.append(f"{_relative_path(path)}: settled settlements must have zero outstanding")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_collection_case_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "case_id",
            "invoice_id",
            "account_id",
            "status",
            "outstanding_amount",
            "dunning_count",
            "opened_at",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("case_id", "invoice_id", "account_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in COLLECTION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(COLLECTION_STATUSES))}"
        )
    errors.extend(_require_non_negative_float(payload["outstanding_amount"], field_name="outstanding_amount", path=path))
    errors.extend(_require_non_negative_int(payload["dunning_count"], field_name="dunning_count", path=path))
    errors.extend(_validate_iso8601_text(payload["opened_at"], field_name="opened_at", path=path))
    terminal_statuses = {"resolved", "closed"}
    if payload["status"] in terminal_statuses:
        errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
        if not errors and _parse_iso8601_text(payload["closed_at"]) < _parse_iso8601_text(payload["opened_at"]):
            errors.append(f"{_relative_path(path)}: closed_at must not precede opened_at")
    elif payload["closed_at"] != "":
        errors.append(f"{_relative_path(path)}: non-terminal collection cases must use an empty closed_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_dunning_notice_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("notice_id", "case_id", "account_id", "severity", "message", "sent_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("notice_id", "case_id", "account_id", "severity", "message"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["severity"] not in DUNNING_SEVERITIES:
        errors.append(
            f"{_relative_path(path)}: field 'severity' must be one of {', '.join(sorted(DUNNING_SEVERITIES))}"
        )
    errors.extend(_validate_iso8601_text(payload["sent_at"], field_name="sent_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_cash_application_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("application_id", "settlement_id", "payment_id", "amount", "applied_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("application_id", "settlement_id", "payment_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["applied_at"], field_name="applied_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_refund_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("refund_id", "payment_id", "account_id", "amount", "reason", "refunded_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("refund_id", "payment_id", "account_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["refunded_at"], field_name="refunded_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_writeoff_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "writeoff_id",
            "settlement_id",
            "account_id",
            "amount",
            "disposition",
            "reason",
            "written_off_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("writeoff_id", "settlement_id", "account_id", "disposition", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in WRITEOFF_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(WRITEOFF_DISPOSITIONS))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_iso8601_text(payload["written_off_at"], field_name="written_off_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_aging_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_settlements",
            "total_open",
            "total_partial",
            "total_settled",
            "total_disputed",
            "total_written_off",
            "total_outstanding",
            "total_collected",
            "total_refunded",
            "total_collection_cases",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_settlements",
        "total_open",
        "total_partial",
        "total_settled",
        "total_disputed",
        "total_written_off",
        "total_collection_cases",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_outstanding", "total_collected", "total_refunded"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    if not errors:
        classified_total = (
            payload["total_open"]
            + payload["total_partial"]
            + payload["total_settled"]
            + payload["total_disputed"]
            + payload["total_written_off"]
        )
        if classified_total > payload["total_settlements"]:
            errors.append(
                f"{_relative_path(path)}: classified settlement counts must not exceed total_settlements"
            )
        if payload["total_collection_cases"] > (
            payload["total_open"] + payload["total_partial"] + payload["total_disputed"]
        ):
            errors.append(
                f"{_relative_path(path)}: total_collection_cases must not exceed open plus partial plus disputed settlements"
            )
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_settlement_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("decision_id", "settlement_id", "description", "decided_by", "decided_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "settlement_id", "description", "decided_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_settlement_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "account_id",
            "total_settlements",
            "total_payments",
            "total_refunds",
            "total_writeoffs",
            "total_collection_cases",
            "total_collected",
            "total_outstanding",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "account_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_settlements",
        "total_payments",
        "total_refunds",
        "total_writeoffs",
        "total_collection_cases",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_collected", "total_outstanding"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    if not errors:
        if payload["total_refunds"] > payload["total_payments"]:
            errors.append(f"{_relative_path(path)}: total_refunds must not exceed total_payments")
        if payload["total_collection_cases"] > payload["total_settlements"]:
            errors.append(f"{_relative_path(path)}: total_collection_cases must not exceed total_settlements")
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_customer_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("customer_id", "tenant_id", "display_name", "status", "tier", "account_count", "created_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("customer_id", "tenant_id", "display_name", "status", "tier"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in CUSTOMER_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(CUSTOMER_STATUSES))}"
        )
    errors.extend(_require_non_negative_int(payload["account_count"], field_name="account_count", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_account_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "account_id",
            "customer_id",
            "tenant_id",
            "display_name",
            "status",
            "contract_ref",
            "entitlement_count",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("account_id", "customer_id", "tenant_id", "display_name", "status", "contract_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in ACCOUNT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(ACCOUNT_STATUSES))}"
        )
    errors.extend(_require_non_negative_int(payload["entitlement_count"], field_name="entitlement_count", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_product_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("product_id", "tenant_id", "display_name", "status", "category", "base_price", "created_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("product_id", "tenant_id", "display_name", "status", "category"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in PRODUCT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(PRODUCT_STATUSES))}"
        )
    errors.extend(_require_non_negative_float(payload["base_price"], field_name="base_price", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_subscription_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "subscription_id",
            "account_id",
            "product_id",
            "tenant_id",
            "status",
            "quantity",
            "start_at",
            "end_at",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("subscription_id", "account_id", "product_id", "tenant_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in ACCOUNT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(ACCOUNT_STATUSES))}"
        )
    errors.extend(_require_positive_int(payload["quantity"], field_name="quantity", path=path))
    errors.extend(_validate_iso8601_text(payload["start_at"], field_name="start_at", path=path))
    errors.extend(_validate_iso8601_text(payload["end_at"], field_name="end_at", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not errors and _parse_iso8601_text(payload["end_at"]) < _parse_iso8601_text(payload["start_at"]):
        errors.append(f"{_relative_path(path)}: end_at must not precede start_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_entitlement_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "entitlement_id",
            "account_id",
            "tenant_id",
            "service_ref",
            "status",
            "granted_at",
            "expires_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("entitlement_id", "account_id", "tenant_id", "service_ref", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in ENTITLEMENT_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(ENTITLEMENT_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["granted_at"], field_name="granted_at", path=path))
    errors.extend(_validate_iso8601_text(payload["expires_at"], field_name="expires_at", path=path))
    if not errors and _parse_iso8601_text(payload["expires_at"]) < _parse_iso8601_text(payload["granted_at"]):
        errors.append(f"{_relative_path(path)}: expires_at must not precede granted_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_account_health_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "account_id",
            "tenant_id",
            "health_status",
            "health_score",
            "sla_breaches",
            "open_cases",
            "billing_issues",
            "entitlement_count",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("snapshot_id", "account_id", "tenant_id", "health_status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["health_status"] not in ACCOUNT_HEALTH_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'health_status' must be one of {', '.join(sorted(ACCOUNT_HEALTH_STATUSES))}"
        )
    errors.extend(
        _require_number_in_range(payload["health_score"], field_name="health_score", path=path, minimum=0.0, maximum=1.0)
    )
    for field_name in ("sla_breaches", "open_cases", "billing_issues", "entitlement_count"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_customer_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "tenant_id",
            "customer_id",
            "account_id",
            "disposition",
            "reason",
            "decided_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "tenant_id", "customer_id", "account_id", "disposition", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in CUSTOMER_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(CUSTOMER_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_customer_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "tenant_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_customer_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_customers",
            "total_accounts",
            "total_products",
            "total_subscriptions",
            "total_entitlements",
            "total_health_snapshots",
            "total_decisions",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_customers",
        "total_accounts",
        "total_products",
        "total_subscriptions",
        "total_entitlements",
        "total_health_snapshots",
        "total_decisions",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors:
        if payload["total_accounts"] < payload["total_customers"]:
            errors.append(f"{_relative_path(path)}: total_accounts must be at least total_customers")
        if payload["total_health_snapshots"] > payload["total_accounts"]:
            errors.append(f"{_relative_path(path)}: total_health_snapshots must not exceed total_accounts")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_customer_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_customers",
            "total_accounts",
            "total_products",
            "total_subscriptions",
            "total_entitlements",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_customers",
        "total_accounts",
        "total_products",
        "total_subscriptions",
        "total_entitlements",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["total_accounts"] < payload["total_customers"]:
        errors.append(f"{_relative_path(path)}: total_accounts must be at least total_customers")
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "partner_id",
            "tenant_id",
            "display_name",
            "kind",
            "status",
            "tier",
            "account_link_count",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("partner_id", "tenant_id", "display_name", "kind", "status", "tier"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in PARTNER_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(PARTNER_KINDS))}"
        )
    if payload["status"] not in PARTNER_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(PARTNER_STATUSES))}"
        )
    errors.extend(
        _require_non_negative_int(payload["account_link_count"], field_name="account_link_count", path=path)
    )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_account_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "link_id",
            "partner_id",
            "account_id",
            "tenant_id",
            "role",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("link_id", "partner_id", "account_id", "tenant_id", "role"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["role"] not in ECOSYSTEM_ROLES:
        errors.append(
            f"{_relative_path(path)}: field 'role' must be one of {', '.join(sorted(ECOSYSTEM_ROLES))}"
        )
    if not errors and payload["partner_id"] == payload["account_id"]:
        errors.append(f"{_relative_path(path)}: partner_id must not equal account_id")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ecosystem_agreement_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "agreement_id",
            "partner_id",
            "tenant_id",
            "title",
            "contract_ref",
            "revenue_share_pct",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("agreement_id", "partner_id", "tenant_id", "title", "contract_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["revenue_share_pct"],
            field_name="revenue_share_pct",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_revenue_share_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "share_id",
            "partner_id",
            "agreement_id",
            "tenant_id",
            "gross_amount",
            "share_amount",
            "share_pct",
            "status",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("share_id", "partner_id", "agreement_id", "tenant_id", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["gross_amount"], field_name="gross_amount", path=path))
    errors.extend(_require_non_negative_float(payload["share_amount"], field_name="share_amount", path=path))
    errors.extend(
        _require_number_in_range(payload["share_pct"], field_name="share_pct", path=path, minimum=0.0, maximum=1.0)
    )
    if payload["status"] not in REVENUE_SHARE_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(REVENUE_SHARE_STATUSES))}"
        )
    if not errors:
        if payload["share_amount"] > payload["gross_amount"]:
            errors.append(f"{_relative_path(path)}: share_amount must not exceed gross_amount")
        max_share_amount = payload["gross_amount"] * payload["share_pct"]
        if payload["share_amount"] - max_share_amount > 1e-9:
            errors.append(
                f"{_relative_path(path)}: share_amount must not exceed gross_amount multiplied by share_pct"
            )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_commitment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "commitment_id",
            "partner_id",
            "tenant_id",
            "description",
            "target_value",
            "actual_value",
            "met",
            "assessed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("commitment_id", "partner_id", "tenant_id", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["target_value"], field_name="target_value", path=path))
    errors.extend(_require_non_negative_float(payload["actual_value"], field_name="actual_value", path=path))
    if not isinstance(payload["met"], bool):
        errors.append(f"{_relative_path(path)}: field 'met' must be boolean")
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_health_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "partner_id",
            "tenant_id",
            "health_status",
            "health_score",
            "sla_breaches",
            "open_cases",
            "billing_issues",
            "commitment_failures",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("snapshot_id", "partner_id", "tenant_id", "health_status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["health_status"] not in PARTNER_HEALTH_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'health_status' must be one of {', '.join(sorted(PARTNER_HEALTH_STATUSES))}"
        )
    errors.extend(
        _require_number_in_range(payload["health_score"], field_name="health_score", path=path, minimum=0.0, maximum=1.0)
    )
    for field_name in ("sla_breaches", "open_cases", "billing_issues", "commitment_failures"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "tenant_id",
            "partner_id",
            "disposition",
            "reason",
            "decided_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "tenant_id", "partner_id", "disposition", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in PARTNER_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(PARTNER_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "violation_id",
            "tenant_id",
            "partner_id",
            "operation",
            "reason",
            "detected_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "tenant_id", "partner_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_partners",
            "total_links",
            "total_agreements",
            "total_revenue_shares",
            "total_commitments",
            "total_health_snapshots",
            "total_decisions",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_partners",
        "total_links",
        "total_agreements",
        "total_revenue_shares",
        "total_commitments",
        "total_health_snapshots",
        "total_decisions",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["total_health_snapshots"] > payload["total_partners"]:
        errors.append(f"{_relative_path(path)}: total_health_snapshots must not exceed total_partners")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_partner_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_partners",
            "total_links",
            "total_agreements",
            "total_revenue_shares",
            "total_commitments",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_partners",
        "total_links",
        "total_agreements",
        "total_revenue_shares",
        "total_commitments",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_offering_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "offering_id",
            "product_id",
            "tenant_id",
            "display_name",
            "kind",
            "status",
            "version_ref",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("offering_id", "product_id", "tenant_id", "display_name", "kind", "status", "version_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in OFFERING_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(OFFERING_KINDS))}"
        )
    if payload["status"] not in OFFERING_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(OFFERING_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_package_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "package_id",
            "tenant_id",
            "display_name",
            "offering_count",
            "status",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("package_id", "tenant_id", "display_name", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_int(payload["offering_count"], field_name="offering_count", path=path))
    if payload["status"] not in OFFERING_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(OFFERING_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_bundle_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "bundle_id",
            "package_id",
            "offering_id",
            "tenant_id",
            "disposition",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("bundle_id", "package_id", "offering_id", "tenant_id", "disposition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in BUNDLE_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(BUNDLE_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_listing_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "listing_id",
            "offering_id",
            "tenant_id",
            "channel",
            "active",
            "listed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("listing_id", "offering_id", "tenant_id", "channel"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["channel"] not in MARKETPLACE_CHANNELS:
        errors.append(
            f"{_relative_path(path)}: field 'channel' must be one of {', '.join(sorted(MARKETPLACE_CHANNELS))}"
        )
    if not isinstance(payload["active"], bool):
        errors.append(f"{_relative_path(path)}: field 'active' must be boolean")
    errors.extend(_validate_iso8601_text(payload["listed_at"], field_name="listed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_eligibility_rule_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "rule_id",
            "offering_id",
            "tenant_id",
            "account_segment",
            "status",
            "reason",
            "evaluated_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("rule_id", "offering_id", "tenant_id", "account_segment", "status", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in ELIGIBILITY_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(ELIGIBILITY_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["evaluated_at"], field_name="evaluated_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_pricing_binding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "binding_id",
            "offering_id",
            "tenant_id",
            "base_price",
            "effective_price",
            "disposition",
            "contract_ref",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("binding_id", "offering_id", "tenant_id", "disposition", "contract_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["base_price"], field_name="base_price", path=path))
    errors.extend(_require_non_negative_float(payload["effective_price"], field_name="effective_price", path=path))
    if payload["disposition"] not in PRICING_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(PRICING_DISPOSITIONS))}"
        )
    if not errors:
        if payload["disposition"] == "standard" and payload["effective_price"] != payload["base_price"]:
            errors.append(f"{_relative_path(path)}: standard pricing must keep effective_price equal to base_price")
        if payload["disposition"] in {"discounted", "promotional"} and payload["effective_price"] > payload["base_price"]:
            errors.append(
                f"{_relative_path(path)}: discounted or promotional pricing must not exceed base_price"
            )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_marketplace_assessment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assessment_id",
            "tenant_id",
            "total_offerings",
            "active_offerings",
            "total_listings",
            "active_listings",
            "total_packages",
            "coverage_score",
            "assessed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assessment_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_offerings",
        "active_offerings",
        "total_listings",
        "active_listings",
        "total_packages",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(payload["coverage_score"], field_name="coverage_score", path=path, minimum=0.0, maximum=1.0)
    )
    if not errors:
        if payload["active_offerings"] > payload["total_offerings"]:
            errors.append(f"{_relative_path(path)}: active_offerings must not exceed total_offerings")
        if payload["active_listings"] > payload["total_listings"]:
            errors.append(f"{_relative_path(path)}: active_listings must not exceed total_listings")
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_marketplace_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_offerings",
            "total_packages",
            "total_bundles",
            "total_listings",
            "total_eligibility_rules",
            "total_pricing_bindings",
            "total_assessments",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_offerings",
        "total_packages",
        "total_bundles",
        "total_listings",
        "total_eligibility_rules",
        "total_pricing_bindings",
        "total_assessments",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_marketplace_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("violation_id", "tenant_id", "operation", "reason", "detected_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_marketplace_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_offerings",
            "total_packages",
            "total_bundles",
            "total_listings",
            "total_eligibility_rules",
            "total_pricing_bindings",
            "total_violations",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_offerings",
        "total_packages",
        "total_bundles",
        "total_listings",
        "total_eligibility_rules",
        "total_pricing_bindings",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_vendor_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "vendor_id",
            "name",
            "tenant_id",
            "status",
            "risk_level",
            "category",
            "registered_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("vendor_id", "name", "tenant_id", "status", "risk_level", "category"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in VENDOR_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(VENDOR_STATUSES))}"
        )
    if payload["risk_level"] not in VENDOR_RISK_LEVELS:
        errors.append(
            f"{_relative_path(path)}: field 'risk_level' must be one of {', '.join(sorted(VENDOR_RISK_LEVELS))}"
        )
    errors.extend(_validate_iso8601_text(payload["registered_at"], field_name="registered_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_procurement_request_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "request_id",
            "vendor_id",
            "tenant_id",
            "status",
            "description",
            "estimated_amount",
            "currency",
            "requested_by",
            "requested_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "request_id",
        "vendor_id",
        "tenant_id",
        "status",
        "description",
        "currency",
        "requested_by",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in PROCUREMENT_REQUEST_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(PROCUREMENT_REQUEST_STATUSES))}"
        )
    errors.extend(
        _require_non_negative_float(payload["estimated_amount"], field_name="estimated_amount", path=path)
    )
    errors.extend(_validate_iso8601_text(payload["requested_at"], field_name="requested_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_purchase_order_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "po_id",
            "request_id",
            "vendor_id",
            "tenant_id",
            "status",
            "amount",
            "currency",
            "issued_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("po_id", "request_id", "vendor_id", "tenant_id", "status", "currency"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in PURCHASE_ORDER_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(PURCHASE_ORDER_STATUSES))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    if not errors and payload["amount"] <= 0.0:
        errors.append(f"{_relative_path(path)}: amount must be positive for a purchase order")
    errors.extend(_validate_iso8601_text(payload["issued_at"], field_name="issued_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_vendor_assessment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assessment_id",
            "vendor_id",
            "risk_level",
            "performance_score",
            "fault_count",
            "assessed_by",
            "assessed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assessment_id", "vendor_id", "risk_level", "assessed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["risk_level"] not in VENDOR_RISK_LEVELS:
        errors.append(
            f"{_relative_path(path)}: field 'risk_level' must be one of {', '.join(sorted(VENDOR_RISK_LEVELS))}"
        )
    errors.extend(
        _require_number_in_range(
            payload["performance_score"],
            field_name="performance_score",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_require_non_negative_int(payload["fault_count"], field_name="fault_count", path=path))
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_vendor_commitment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "commitment_id",
            "vendor_id",
            "contract_ref",
            "description",
            "target_value",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("commitment_id", "vendor_id", "contract_ref", "description", "target_value"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_procurement_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "request_id",
            "status",
            "decided_by",
            "reason",
            "decided_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "request_id", "status", "decided_by", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in PROCUREMENT_DECISION_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(PROCUREMENT_DECISION_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_procurement_renewal_window_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "renewal_id",
            "vendor_id",
            "contract_ref",
            "disposition",
            "opens_at",
            "closes_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("renewal_id", "vendor_id", "contract_ref", "disposition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in RENEWAL_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(RENEWAL_DISPOSITIONS))}"
        )
    errors.extend(_validate_iso8601_text(payload["opens_at"], field_name="opens_at", path=path))
    errors.extend(_validate_iso8601_text(payload["closes_at"], field_name="closes_at", path=path))
    if not errors and _parse_iso8601_text(payload["closes_at"]) < _parse_iso8601_text(payload["opens_at"]):
        errors.append(f"{_relative_path(path)}: closes_at must not precede opens_at")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_vendor_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "violation_id",
            "vendor_id",
            "tenant_id",
            "operation",
            "reason",
            "detected_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "vendor_id", "tenant_id", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_procurement_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "total_vendors",
            "total_requests",
            "total_purchase_orders",
            "total_assessments",
            "total_commitments",
            "total_renewals",
            "total_violations",
            "total_procurement_value",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    for field_name in (
        "total_vendors",
        "total_requests",
        "total_purchase_orders",
        "total_assessments",
        "total_commitments",
        "total_renewals",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_non_negative_float(
            payload["total_procurement_value"],
            field_name="total_procurement_value",
            path=path,
        )
    )
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_procurement_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_vendors",
            "total_requests",
            "total_purchase_orders",
            "total_fulfilled",
            "total_cancelled",
            "total_procurement_value",
            "closed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_vendors", "total_requests", "total_purchase_orders", "total_fulfilled", "total_cancelled"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_non_negative_float(
            payload["total_procurement_value"],
            field_name="total_procurement_value",
            path=path,
        )
    )
    if not errors and payload["total_fulfilled"] + payload["total_cancelled"] > payload["total_purchase_orders"]:
        errors.append(
            f"{_relative_path(path)}: total_fulfilled plus total_cancelled must not exceed total_purchase_orders"
        )
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_budget_envelope_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "budget_id",
            "name",
            "scope",
            "scope_ref_id",
            "currency",
            "limit_amount",
            "reserved_amount",
            "consumed_amount",
            "warning_threshold",
            "hard_stop_threshold",
            "active",
            "tags",
            "created_at",
            "updated_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("budget_id", "name", "scope", "scope_ref_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["scope"] not in BUDGET_SCOPES:
        errors.append(
            f"{_relative_path(path)}: field 'scope' must be one of {', '.join(sorted(BUDGET_SCOPES))}"
        )
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    for field_name in ("limit_amount", "reserved_amount", "consumed_amount"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(payload["warning_threshold"], field_name="warning_threshold", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(
        _require_number_in_range(payload["hard_stop_threshold"], field_name="hard_stop_threshold", path=path, minimum=0.0, maximum=1.0)
    )
    if not isinstance(payload["active"], bool):
        errors.append(f"{_relative_path(path)}: field 'active' must be boolean")
    tags = payload["tags"]
    if not isinstance(tags, list):
        errors.append(f"{_relative_path(path)}: field 'tags' must be an array")
    else:
        for index, tag in enumerate(tags):
            errors.extend(_require_non_empty_text(tag, field_name=f"tags[{index}]", path=path))
    if not errors:
        if payload["consumed_amount"] + payload["reserved_amount"] > payload["limit_amount"]:
            errors.append(f"{_relative_path(path)}: consumed_amount plus reserved_amount must not exceed limit_amount")
        if payload["warning_threshold"] > payload["hard_stop_threshold"]:
            errors.append(f"{_relative_path(path)}: warning_threshold must not exceed hard_stop_threshold")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    errors.extend(_validate_iso8601_text(payload["updated_at"], field_name="updated_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_spend_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "spend_id",
            "budget_id",
            "category",
            "status",
            "amount",
            "currency",
            "campaign_ref",
            "step_ref",
            "connector_ref",
            "reason",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("spend_id", "budget_id", "category", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["category"] not in FINANCIAL_COST_CATEGORIES:
        errors.append(
            f"{_relative_path(path)}: field 'category' must be one of {', '.join(sorted(FINANCIAL_COST_CATEGORIES))}"
        )
    if payload["status"] not in SPEND_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(SPEND_STATUSES))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_cost_estimate_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "estimate_id",
            "category",
            "estimated_amount",
            "currency",
            "confidence",
            "connector_ref",
            "campaign_ref",
            "step_ref",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("estimate_id", "category"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["category"] not in FINANCIAL_COST_CATEGORIES:
        errors.append(
            f"{_relative_path(path)}: field 'category' must be one of {', '.join(sorted(FINANCIAL_COST_CATEGORIES))}"
        )
    errors.extend(_require_non_negative_float(payload["estimated_amount"], field_name="estimated_amount", path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    errors.extend(
        _require_number_in_range(payload["confidence"], field_name="confidence", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_connector_cost_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "profile_id",
            "connector_ref",
            "cost_per_call",
            "cost_per_unit",
            "currency",
            "unit_name",
            "monthly_minimum",
            "monthly_cap",
            "tier",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("profile_id", "connector_ref", "unit_name", "tier"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("cost_per_call", "cost_per_unit", "monthly_minimum", "monthly_cap"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    if not errors and payload["monthly_minimum"] > payload["monthly_cap"]:
        errors.append(f"{_relative_path(path)}: monthly_minimum must not exceed monthly_cap")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_campaign_budget_binding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "binding_id",
            "campaign_id",
            "budget_id",
            "allocated_amount",
            "consumed_amount",
            "currency",
            "active",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("binding_id", "campaign_id", "budget_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["allocated_amount"], field_name="allocated_amount", path=path))
    errors.extend(_require_non_negative_float(payload["consumed_amount"], field_name="consumed_amount", path=path))
    if not errors and payload["consumed_amount"] > payload["allocated_amount"]:
        errors.append(f"{_relative_path(path)}: consumed_amount must not exceed allocated_amount")
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    if not isinstance(payload["active"], bool):
        errors.append(f"{_relative_path(path)}: field 'active' must be boolean")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_approval_threshold_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "threshold_id",
            "budget_id",
            "mode",
            "amount",
            "currency",
            "approver_ref",
            "auto_approve_below",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("threshold_id", "budget_id", "mode", "approver_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["mode"] not in APPROVAL_THRESHOLD_MODES:
        errors.append(
            f"{_relative_path(path)}: field 'mode' must be one of {', '.join(sorted(APPROVAL_THRESHOLD_MODES))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_require_non_negative_float(payload["auto_approve_below"], field_name="auto_approve_below", path=path))
    if not errors and payload["auto_approve_below"] > payload["amount"]:
        errors.append(f"{_relative_path(path)}: auto_approve_below must not exceed amount")
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_budget_reservation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "reservation_id",
            "budget_id",
            "amount",
            "currency",
            "category",
            "campaign_ref",
            "step_ref",
            "connector_ref",
            "active",
            "reason",
            "created_at",
            "expires_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("reservation_id", "budget_id", "category"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["category"] not in FINANCIAL_COST_CATEGORIES:
        errors.append(
            f"{_relative_path(path)}: field 'category' must be one of {', '.join(sorted(FINANCIAL_COST_CATEGORIES))}"
        )
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    if not isinstance(payload["active"], bool):
        errors.append(f"{_relative_path(path)}: field 'active' must be boolean")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    errors.extend(_validate_iso8601_text(payload["expires_at"], field_name="expires_at", path=path))
    if not errors and _parse_iso8601_text(payload["expires_at"]) < _parse_iso8601_text(payload["created_at"]):
        errors.append(f"{_relative_path(path)}: expires_at must not precede created_at")
    return errors


def _validate_spend_forecast_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "forecast_id",
            "budget_id",
            "projected_amount",
            "currency",
            "period_start",
            "period_end",
            "confidence",
            "breakdown",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("forecast_id", "budget_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["projected_amount"], field_name="projected_amount", path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    errors.extend(_validate_iso8601_text(payload["period_start"], field_name="period_start", path=path))
    errors.extend(_validate_iso8601_text(payload["period_end"], field_name="period_end", path=path))
    errors.extend(
        _require_number_in_range(payload["confidence"], field_name="confidence", path=path, minimum=0.0, maximum=1.0)
    )
    breakdown = payload["breakdown"]
    if not isinstance(breakdown, dict):
        errors.append(f"{_relative_path(path)}: field 'breakdown' must be an object")
    else:
        for key, value in breakdown.items():
            if not isinstance(key, str) or not key.strip():
                errors.append(f"{_relative_path(path)}: breakdown keys must be non-empty strings")
                break
            errors.extend(_require_non_negative_float(value, field_name=f"breakdown[{key}]", path=path))
    if not errors and _parse_iso8601_text(payload["period_start"]) >= _parse_iso8601_text(payload["period_end"]):
        errors.append(f"{_relative_path(path)}: period_start must be before period_end")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_budget_conflict_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("conflict_id", "budget_id", "kind", "description", "severity", "detected_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("conflict_id", "budget_id", "kind", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in BUDGET_CONFLICT_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(BUDGET_CONFLICT_KINDS))}"
        )
    errors.extend(_require_non_negative_int(payload["severity"], field_name="severity", path=path))
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    return errors


def _validate_budget_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "budget_id",
            "disposition",
            "requested_amount",
            "available_amount",
            "currency",
            "reason",
            "reservation_id",
            "approval_required",
            "approver_ref",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "budget_id", "disposition"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in CHARGE_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(CHARGE_DISPOSITIONS))}"
        )
    errors.extend(_require_non_negative_float(payload["requested_amount"], field_name="requested_amount", path=path))
    errors.extend(_require_non_negative_float(payload["available_amount"], field_name="available_amount", path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    if not isinstance(payload["approval_required"], bool):
        errors.append(f"{_relative_path(path)}: field 'approval_required' must be boolean")
    elif payload["approval_required"] and (not isinstance(payload["approver_ref"], str) or not payload["approver_ref"].strip()):
        errors.append(f"{_relative_path(path)}: approver_ref must be non-empty when approval_required is true")
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    return errors


def _validate_financial_health_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "budget_id",
            "limit_amount",
            "consumed_amount",
            "reserved_amount",
            "available_amount",
            "utilization",
            "currency",
            "warning_triggered",
            "hard_stop_triggered",
            "active_reservations",
            "total_spend_records",
            "captured_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("snapshot_id", "budget_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("limit_amount", "consumed_amount", "reserved_amount", "available_amount"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(payload["utilization"], field_name="utilization", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    if not isinstance(payload["warning_triggered"], bool):
        errors.append(f"{_relative_path(path)}: field 'warning_triggered' must be boolean")
    if not isinstance(payload["hard_stop_triggered"], bool):
        errors.append(f"{_relative_path(path)}: field 'hard_stop_triggered' must be boolean")
    errors.extend(_require_non_negative_int(payload["active_reservations"], field_name="active_reservations", path=path))
    errors.extend(_require_non_negative_int(payload["total_spend_records"], field_name="total_spend_records", path=path))
    if not errors:
        if payload["consumed_amount"] + payload["reserved_amount"] > payload["limit_amount"]:
            errors.append(f"{_relative_path(path)}: consumed_amount plus reserved_amount must not exceed limit_amount")
        expected_available = payload["limit_amount"] - payload["consumed_amount"] - payload["reserved_amount"]
        if abs(payload["available_amount"] - expected_available) > 1e-9:
            errors.append(f"{_relative_path(path)}: available_amount must equal limit_amount minus consumed_amount minus reserved_amount")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    return errors


def _validate_budget_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "budget_id",
            "limit_amount",
            "total_consumed",
            "total_released",
            "total_reservations",
            "total_spend_records",
            "currency",
            "under_budget",
            "overspend_amount",
            "warnings_issued",
            "hard_stops_triggered",
            "closed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "budget_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("limit_amount", "total_consumed", "total_released", "overspend_amount"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_reservations", "total_spend_records", "warnings_issued", "hard_stops_triggered"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_currency_code(payload["currency"], field_name="currency", path=path))
    if not isinstance(payload["under_budget"], bool):
        errors.append(f"{_relative_path(path)}: field 'under_budget' must be boolean")
    if not errors:
        expected_overspend = max(payload["total_consumed"] - payload["limit_amount"], 0.0)
        if abs(payload["overspend_amount"] - expected_overspend) > 1e-9:
            errors.append(f"{_relative_path(path)}: overspend_amount must equal max(total_consumed minus limit_amount, 0)")
        if payload["under_budget"] and payload["overspend_amount"] != 0.0:
            errors.append(f"{_relative_path(path)}: under_budget reports must keep overspend_amount at 0")
        if not payload["under_budget"] and payload["overspend_amount"] <= 0.0:
            errors.append(f"{_relative_path(path)}: over-budget reports must carry a positive overspend_amount")
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    return errors


def _validate_ledger_account_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "account_id",
            "tenant_id",
            "display_name",
            "status",
            "network",
            "balance",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("account_id", "tenant_id", "display_name", "status", "network"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in LEDGER_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(LEDGER_STATUSES))}"
        )
    if payload["network"] not in LEDGER_NETWORK_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'network' must be one of {', '.join(sorted(LEDGER_NETWORK_KINDS))}"
        )
    errors.extend(_require_non_negative_float(payload["balance"], field_name="balance", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ledger_transaction_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "transaction_id",
            "tenant_id",
            "from_account",
            "to_account",
            "amount",
            "reference_ref",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("transaction_id", "tenant_id", "from_account", "to_account", "reference_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["amount"], field_name="amount", path=path))
    if not errors:
        if payload["amount"] <= 0.0:
            errors.append(f"{_relative_path(path)}: amount must be positive for a ledger transaction")
        if payload["from_account"] == payload["to_account"]:
            errors.append(f"{_relative_path(path)}: from_account must not equal to_account")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_settlement_proof_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "proof_id",
            "tenant_id",
            "transaction_ref",
            "status",
            "proof_hash",
            "verified_at",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("proof_id", "tenant_id", "transaction_ref", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in SETTLEMENT_PROOF_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(SETTLEMENT_PROOF_STATUSES))}"
        )
    errors.extend(_validate_sha256_hash_text(payload["proof_hash"], field_name="proof_hash", path=path))
    if payload["verified_at"]:
        errors.extend(_validate_iso8601_text(payload["verified_at"], field_name="verified_at", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not errors:
        if payload["status"] == "confirmed" and not payload["verified_at"]:
            errors.append(f"{_relative_path(path)}: confirmed settlement proofs must carry verified_at")
        if payload["status"] == "pending" and payload["verified_at"]:
            errors.append(f"{_relative_path(path)}: pending settlement proofs must keep verified_at empty")
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_anchor_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "anchor_id",
            "tenant_id",
            "source_ref",
            "content_hash",
            "disposition",
            "anchor_ref",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("anchor_id", "tenant_id", "source_ref", "disposition", "anchor_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["disposition"] not in ANCHOR_DISPOSITIONS:
        errors.append(
            f"{_relative_path(path)}: field 'disposition' must be one of {', '.join(sorted(ANCHOR_DISPOSITIONS))}"
        )
    errors.extend(_validate_sha256_hash_text(payload["content_hash"], field_name="content_hash", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_wallet_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "wallet_id",
            "tenant_id",
            "identity_ref",
            "status",
            "public_key_ref",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("wallet_id", "tenant_id", "identity_ref", "status", "public_key_ref"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["status"] not in WALLET_STATUSES:
        errors.append(
            f"{_relative_path(path)}: field 'status' must be one of {', '.join(sorted(WALLET_STATUSES))}"
        )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ledger_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "tenant_id",
            "operation",
            "disposition",
            "reason",
            "decided_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "tenant_id", "operation", "disposition", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ledger_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "snapshot_id",
            "tenant_id",
            "total_accounts",
            "total_transactions",
            "total_proofs",
            "total_anchors",
            "total_wallets",
            "total_violations",
            "captured_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("snapshot_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_accounts",
        "total_transactions",
        "total_proofs",
        "total_anchors",
        "total_wallets",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["total_proofs"] > payload["total_transactions"]:
        errors.append(f"{_relative_path(path)}: total_proofs must not exceed total_transactions")
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ledger_violation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "violation_id",
            "tenant_id",
            "kind",
            "operation",
            "reason",
            "detected_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("violation_id", "tenant_id", "kind", "operation", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if payload["kind"] not in LEDGER_VIOLATION_KINDS:
        errors.append(
            f"{_relative_path(path)}: field 'kind' must be one of {', '.join(sorted(LEDGER_VIOLATION_KINDS))}"
        )
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ledger_assessment_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "assessment_id",
            "tenant_id",
            "total_confirmed",
            "total_failed",
            "total_disputed",
            "integrity_score",
            "assessed_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("assessment_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total_confirmed", "total_failed", "total_disputed"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(payload["integrity_score"], field_name="integrity_score", path=path, minimum=0.0, maximum=1.0)
    )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_ledger_closure_report_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MCOI runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "report_id",
            "tenant_id",
            "total_accounts",
            "total_transactions",
            "total_proofs",
            "total_anchors",
            "total_violations",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("report_id", "tenant_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_accounts",
        "total_transactions",
        "total_proofs",
        "total_anchors",
        "total_violations",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if not errors and payload["total_proofs"] > payload["total_transactions"]:
        errors.append(f"{_relative_path(path)}: total_proofs must not exceed total_transactions")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


MAF_RUNTIME_FIXTURE_VALIDATORS: dict[str, MAFRuntimeFixtureValidator] = {
    "adversarial_case.json": _validate_adversarial_case_fixture,
    "assignment_record.json": _validate_assignment_record_fixture,
    "assignment_policy.json": _validate_assignment_policy_fixture,
    "assignment_decision.json": _validate_assignment_decision_fixture,
    "benchmark_metric.json": _validate_benchmark_metric_fixture,
    "benchmark_result.json": _validate_benchmark_result_fixture,
    "benchmark_run.json": _validate_benchmark_run_fixture,
    "benchmark_scenario.json": _validate_benchmark_scenario_fixture,
    "benchmark_suite.json": _validate_benchmark_suite_fixture,
    "causal_path.json": _validate_causal_path_fixture,
    "capability_scorecard.json": _validate_capability_scorecard_fixture,
    "decision_comparison.json": _validate_decision_comparison_fixture,
    "decision_factor.json": _validate_decision_factor_fixture,
    "decision_link.json": _validate_decision_link_fixture,
    "decision_policy.json": _validate_decision_policy_fixture,
    "evidence_link.json": _validate_evidence_link_fixture,
    "event_correlation.json": _validate_event_correlation_fixture,
    "event_envelope.json": _validate_event_envelope_fixture,
    "event_record.json": _validate_event_record_fixture,
    "event_reaction.json": _validate_event_reaction_fixture,
    "event_subscription.json": _validate_event_subscription_fixture,
    "event_window.json": _validate_event_window_fixture,
    "function_metrics_snapshot.json": _validate_function_metrics_snapshot_fixture,
    "function_outcome_record.json": _validate_function_outcome_record_fixture,
    "function_policy_binding.json": _validate_function_policy_binding_fixture,
    "function_queue_profile.json": _validate_function_queue_profile_fixture,
    "function_sla_profile.json": _validate_function_sla_profile_fixture,
    "follow_up_record.json": _validate_follow_up_record_fixture,
    "handoff_record.json": _validate_handoff_record_fixture,
    "deadline_record.json": _validate_deadline_record_fixture,
    "goal_dependency.json": _validate_goal_dependency_fixture,
    "goal_descriptor.json": _validate_goal_descriptor_fixture,
    "goal_execution_state.json": _validate_goal_execution_state_fixture,
    "job_descriptor.json": _validate_job_descriptor_fixture,
    "job_execution_record.json": _validate_job_execution_record_fixture,
    "job_pause_record.json": _validate_job_pause_record_fixture,
    "job_resume_record.json": _validate_job_resume_record_fixture,
    "job_state.json": _validate_job_state_fixture,
    "journal_entry.json": _validate_journal_entry_fixture,
    "journal_validation_result.json": _validate_journal_validation_result_fixture,
    "livelock_record.json": _validate_livelock_record_fixture,
    "goal_plan.json": _validate_goal_plan_fixture,
    "graph_query_result.json": _validate_graph_query_result_fixture,
    "graph_snapshot.json": _validate_graph_snapshot_fixture,
    "obligation_closure.json": _validate_obligation_closure_fixture,
    "obligation_escalation.json": _validate_obligation_escalation_fixture,
    "obligation_link.json": _validate_obligation_link_fixture,
    "obligation_record.json": _validate_obligation_record_fixture,
    "obligation_transfer.json": _validate_obligation_transfer_fixture,
    "operational_edge.json": _validate_operational_edge_fixture,
    "operational_node.json": _validate_operational_node_fixture,
    "role_descriptor.json": _validate_role_descriptor_fixture,
    "runtime_heartbeat.json": _validate_runtime_heartbeat_fixture,
    "option_utility.json": _validate_option_utility_fixture,
    "replay_session_result.json": _validate_replay_session_result_fixture,
    "replay_step_result.json": _validate_replay_step_result_fixture,
    "resource_budget.json": _validate_resource_budget_fixture,
    "regression_record.json": _validate_regression_record_fixture,
    "restore_verification.json": _validate_restore_verification_fixture,
    "service_function_template.json": _validate_service_function_template_fixture,
    "simulation_option.json": _validate_simulation_option_fixture,
    "simulation_outcome.json": _validate_simulation_outcome_fixture,
    "simulation_request.json": _validate_simulation_request_fixture,
    "simulation_comparison.json": _validate_simulation_comparison_fixture,
    "simulation_verdict.json": _validate_simulation_verdict_fixture,
    "sub_goal.json": _validate_sub_goal_fixture,
    "supervisor_checkpoint.json": _validate_supervisor_checkpoint_fixture,
    "supervisor_health.json": _validate_supervisor_health_fixture,
    "supervisor_policy.json": _validate_supervisor_policy_fixture,
    "supervisor_tick.json": _validate_supervisor_tick_fixture,
    "subsystem_snapshot.json": _validate_subsystem_snapshot_fixture,
    "state_delta.json": _validate_state_delta_fixture,
    "stage_execution_result.json": _validate_stage_execution_result_fixture,
    "team_queue_state.json": _validate_team_queue_state_fixture,
    "tradeoff_record.json": _validate_tradeoff_record_fixture,
    "utility_profile.json": _validate_utility_profile_fixture,
    "utility_verdict.json": _validate_utility_verdict_fixture,
    "work_queue_entry.json": _validate_work_queue_entry_fixture,
    "worker_profile.json": _validate_worker_profile_fixture,
    "worker_capacity.json": _validate_worker_capacity_fixture,
    "composite_checkpoint.json": _validate_composite_checkpoint_fixture,
    "workflow_binding.json": _validate_workflow_binding_fixture,
    "workflow_descriptor.json": _validate_workflow_descriptor_fixture,
    "workflow_execution_record.json": _validate_workflow_execution_record_fixture,
    "goal_replan_record.json": _validate_goal_replan_record_fixture,
    "workflow_stage.json": _validate_workflow_stage_fixture,
    "workflow_transition.json": _validate_workflow_transition_fixture,
    "workflow_verification_record.json": _validate_workflow_verification_record_fixture,
    "workload_snapshot.json": _validate_workload_snapshot_fixture,
}

MCOI_RUNTIME_FIXTURE_VALIDATORS: dict[str, MCOIRuntimeFixtureValidator] = {
    "account_health_snapshot.json": _validate_account_health_snapshot_fixture,
    "account_record.json": _validate_account_record_fixture,
    "anchor_record.json": _validate_anchor_record_fixture,
    "asset_assessment.json": _validate_asset_assessment_fixture,
    "asset_assignment.json": _validate_asset_assignment_fixture,
    "asset_closure_report.json": _validate_asset_closure_report_fixture,
    "asset_dependency.json": _validate_asset_dependency_fixture,
    "asset_record.json": _validate_asset_record_fixture,
    "asset_snapshot.json": _validate_asset_snapshot_fixture,
    "asset_violation.json": _validate_asset_violation_fixture,
    "billing_account.json": _validate_billing_account_fixture,
    "billing_closure_report.json": _validate_billing_closure_report_fixture,
    "billing_decision.json": _validate_billing_decision_fixture,
    "billing_violation.json": _validate_billing_violation_fixture,
    "breach_record.json": _validate_breach_record_fixture,
    "charge_record.json": _validate_charge_record_fixture,
    "commitment_record.json": _validate_commitment_record_fixture,
    "contract_assessment.json": _validate_contract_assessment_fixture,
    "contract_clause.json": _validate_contract_clause_fixture,
    "contract_closure_report.json": _validate_contract_closure_report_fixture,
    "contract_snapshot.json": _validate_contract_snapshot_fixture,
    "credit_record.json": _validate_credit_record_fixture,
    "assurance_assessment.json": _validate_assurance_assessment_fixture,
    "assurance_closure_report.json": _validate_assurance_closure_report_fixture,
    "assurance_decision.json": _validate_assurance_decision_fixture,
    "assurance_evidence_binding.json": _validate_assurance_evidence_binding_fixture,
    "assurance_finding.json": _validate_assurance_finding_fixture,
    "assurance_snapshot.json": _validate_assurance_snapshot_fixture,
    "assurance_violation.json": _validate_assurance_violation_fixture,
    "attestation_record.json": _validate_attestation_record_fixture,
    "approval_board.json": _validate_approval_board_fixture,
    "approval_threshold.json": _validate_approval_threshold_fixture,
    "certification_record.json": _validate_certification_record_fixture,
    "board_member.json": _validate_board_member_fixture,
    "board_vote.json": _validate_board_vote_fixture,
    "budget_closure_report.json": _validate_budget_closure_report_fixture,
    "budget_conflict.json": _validate_budget_conflict_fixture,
    "budget_decision.json": _validate_budget_decision_fixture,
    "budget_envelope.json": _validate_budget_envelope_fixture,
    "budget_reservation.json": _validate_budget_reservation_fixture,
    "campaign_budget_binding.json": _validate_campaign_budget_binding_fixture,
    "case_assignment.json": _validate_case_assignment_fixture,
    "case_closure_report.json": _validate_case_closure_report_fixture,
    "case_decision.json": _validate_case_decision_fixture,
    "case_record.json": _validate_case_record_fixture,
    "case_snapshot.json": _validate_case_snapshot_fixture,
    "case_violation.json": _validate_case_violation_fixture,
    "cash_application.json": _validate_cash_application_fixture,
    "collaborative_decision.json": _validate_collaborative_decision_fixture,
    "collection_case.json": _validate_collection_case_fixture,
    "configuration_item.json": _validate_configuration_item_fixture,
    "conflict_record.json": _validate_conflict_record_fixture,
    "continuity_closure_report.json": _validate_continuity_closure_report_fixture,
    "continuity_plan.json": _validate_continuity_plan_fixture,
    "continuity_snapshot.json": _validate_continuity_snapshot_fixture,
    "continuity_violation.json": _validate_continuity_violation_fixture,
    "customer_closure_report.json": _validate_customer_closure_report_fixture,
    "customer_decision.json": _validate_customer_decision_fixture,
    "customer_record.json": _validate_customer_record_fixture,
    "customer_snapshot.json": _validate_customer_snapshot_fixture,
    "customer_violation.json": _validate_customer_violation_fixture,
    "ecosystem_agreement.json": _validate_ecosystem_agreement_fixture,
    "delegation_request.json": _validate_delegation_request_fixture,
    "delegation_result.json": _validate_delegation_result_fixture,
    "disruption_event.json": _validate_disruption_event_fixture,
    "dispute_record.json": _validate_dispute_record_fixture,
    "dunning_notice.json": _validate_dunning_notice_fixture,
    "entitlement_record.json": _validate_entitlement_record_fixture,
    "financial_health_snapshot.json": _validate_financial_health_snapshot_fixture,
    "evidence_collection.json": _validate_evidence_collection_fixture,
    "evidence_item.json": _validate_evidence_item_fixture,
    "failover_record.json": _validate_failover_record_fixture,
    "finding_record.json": _validate_finding_record_fixture,
    "governance_contract_record.json": _validate_governance_contract_record_fixture,
    "handoff_packet.json": _validate_handoff_packet_fixture,
    "human_task_record.json": _validate_human_task_record_fixture,
    "human_workflow_closure_report.json": _validate_human_workflow_closure_report_fixture,
    "human_workflow_snapshot.json": _validate_human_workflow_snapshot_fixture,
    "human_workflow_violation.json": _validate_human_workflow_violation_fixture,
    "handoff_record.json": _validate_mcoi_handoff_record_fixture,
    "incident_record.json": _validate_incident_record_fixture,
    "inventory_record.json": _validate_inventory_record_fixture,
    "invoice_record.json": _validate_invoice_record_fixture,
    "lifecycle_event.json": _validate_lifecycle_event_fixture,
    "ledger_account.json": _validate_ledger_account_fixture,
    "ledger_assessment.json": _validate_ledger_assessment_fixture,
    "ledger_closure_report.json": _validate_ledger_closure_report_fixture,
    "ledger_decision.json": _validate_ledger_decision_fixture,
    "ledger_snapshot.json": _validate_ledger_snapshot_fixture,
    "ledger_transaction.json": _validate_ledger_transaction_fixture,
    "ledger_violation.json": _validate_ledger_violation_fixture,
    "listing_record.json": _validate_listing_record_fixture,
    "merge_decision.json": _validate_merge_decision_fixture,
    "marketplace_assessment.json": _validate_marketplace_assessment_fixture,
    "marketplace_closure_report.json": _validate_marketplace_closure_report_fixture,
    "marketplace_snapshot.json": _validate_marketplace_snapshot_fixture,
    "marketplace_violation.json": _validate_marketplace_violation_fixture,
    "payment_record.json": _validate_payment_record_fixture,
    "package_record.json": _validate_package_record_fixture,
    "penalty_record.json": _validate_penalty_record_fixture,
    "partner_account_link.json": _validate_partner_account_link_fixture,
    "partner_closure_report.json": _validate_partner_closure_report_fixture,
    "partner_commitment.json": _validate_partner_commitment_fixture,
    "partner_decision.json": _validate_partner_decision_fixture,
    "partner_health_snapshot.json": _validate_partner_health_snapshot_fixture,
    "partner_record.json": _validate_partner_record_fixture,
    "partner_snapshot.json": _validate_partner_snapshot_fixture,
    "partner_violation.json": _validate_partner_violation_fixture,
    "pricing_binding.json": _validate_pricing_binding_fixture,
    "procurement_closure_report.json": _validate_procurement_closure_report_fixture,
    "procurement_decision.json": _validate_procurement_decision_fixture,
    "procurement_renewal_window.json": _validate_procurement_renewal_window_fixture,
    "procurement_request.json": _validate_procurement_request_fixture,
    "procurement_snapshot.json": _validate_procurement_snapshot_fixture,
    "product_record.json": _validate_product_record_fixture,
    "purchase_order.json": _validate_purchase_order_fixture,
    "offering_record.json": _validate_offering_record_fixture,
    "bundle_record.json": _validate_bundle_record_fixture,
    "eligibility_rule.json": _validate_eligibility_rule_fixture,
    "recovery_objective.json": _validate_recovery_objective_fixture,
    "recovery_attempt.json": _validate_recovery_attempt_fixture,
    "recovery_decision.json": _validate_recovery_decision_fixture,
    "recovery_execution.json": _validate_recovery_execution_fixture,
    "recovery_plan.json": _validate_recovery_plan_fixture,
    "recovery_record.json": _validate_recovery_record_fixture,
    "revenue_share_record.json": _validate_revenue_share_record_fixture,
    "revenue_snapshot.json": _validate_revenue_snapshot_fixture,
    "remedy_record.json": _validate_remedy_record_fixture,
    "refund_record.json": _validate_refund_record_fixture,
    "review_packet.json": _validate_review_packet_fixture,
    "review_record.json": _validate_review_record_fixture,
    "recertification_window.json": _validate_recertification_window_fixture,
    "renewal_window.json": _validate_renewal_window_fixture,
    "settlement_closure_report.json": _validate_settlement_closure_report_fixture,
    "settlement_decision.json": _validate_settlement_decision_fixture,
    "settlement_proof.json": _validate_settlement_proof_fixture,
    "settlement_record.json": _validate_settlement_record_fixture,
    "sla_window.json": _validate_sla_window_fixture,
    "spend_forecast.json": _validate_spend_forecast_fixture,
    "spend_record.json": _validate_spend_record_fixture,
    "subscription_record.json": _validate_subscription_record_fixture,
    "verification_record.json": _validate_verification_record_fixture,
    "vendor_assessment.json": _validate_vendor_assessment_fixture,
    "vendor_commitment.json": _validate_vendor_commitment_fixture,
    "vendor_record.json": _validate_vendor_record_fixture,
    "vendor_violation.json": _validate_vendor_violation_fixture,
    "wallet_record.json": _validate_wallet_record_fixture,
    "writeoff_record.json": _validate_writeoff_record_fixture,
    "aging_snapshot.json": _validate_aging_snapshot_fixture,
    "connector_cost_profile.json": _validate_connector_cost_profile_fixture,
    "cost_estimate.json": _validate_cost_estimate_fixture,
}

DOCUMENT_ARTIFACT_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "OPERATOR_GUIDE_v0.1.md": (
        "mcoi/examples/config-local-dev.json",
        "mcoi/examples/config-safe-readonly.json",
        "mcoi/examples/request-echo.json",
        "mcoi/examples/request-with-bindings.json",
    ),
    "PILOT_WORKFLOWS_v0.1.md": (
        "examples/pilots/approval_gated_command/config.json",
        "examples/pilots/approval_gated_command/request.json",
        "examples/pilots/document_to_action/config.json",
        "examples/pilots/document_to_action/input_document.json",
        "examples/pilots/failure_escalation/config.json",
    ),
}

OPERATIONAL_DOCUMENT_EXPECTATIONS: dict[str, OperationalDocumentExpectation] = {
    "RELEASE_CHECKLIST_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "RELEASE_NOTES_v0.1.md",
            "KNOWN_LIMITATIONS_v0.1.md",
            "SECURITY_MODEL_v0.1.md",
            "OPERATOR_GUIDE_v0.1.md",
            "PILOT_WORKFLOWS_v0.1.md",
            "PILOT_CHECKLIST_v0.1.md",
            "PILOT_OPERATIONS_GUIDE_v0.1.md",
            "pytest -q",
            "cargo test",
            "scripts/validate_schemas.py --strict",
            "scripts/validate_artifacts.py --strict",
            "scripts/validate_release_status.py --strict",
        ),
        forbidden_literals=(
            "352+ tests",
            "All 4 profiles load correctly",
            "18 architecture docs complete",
            "22 JSON schemas validated",
        ),
        require_all_profiles=True,
        require_all_policy_packs=True,
    ),
    "RELEASE_NOTES_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "OPERATOR_GUIDE_v0.1.md",
            "PILOT_WORKFLOWS_v0.1.md",
            "PILOT_CHECKLIST_v0.1.md",
            "PILOT_OPERATIONS_GUIDE_v0.1.md",
            "scripts/validate_schemas.py --strict",
            "scripts/validate_release_status.py --strict",
            "pytest -q",
            "cargo test",
        ),
        forbidden_literals=(
            "Configuration profiles: local-dev, safe-readonly, operator-approved, sandboxed",
            "**Python:** 352 tests",
            "**JSON schemas:** 16 schemas",
            "18 documents covering all planes and subsystems",
        ),
        require_all_profiles=True,
    ),
    "PILOT_CHECKLIST_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "pytest -q",
            "cargo test",
            "scripts/validate_artifacts.py --strict",
            "examples/pilots/approval_gated_command/config.json",
            "examples/pilots/approval_gated_command/request.json",
            "examples/pilots/document_to_action/config.json",
            "examples/pilots/document_to_action/input_document.json",
            "examples/pilots/failure_escalation/config.json",
            "PILOT_WORKFLOWS_v0.1.md",
        ),
        forbidden_literals=(
            "556+ Python tests",
            "21 Rust tests",
        ),
    ),
    "PILOT_OPERATIONS_GUIDE_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "OPERATOR_GUIDE_v0.1.md",
            "PILOT_WORKFLOWS_v0.1.md",
            "PILOT_CHECKLIST_v0.1.md",
        ),
    ),
}

_DOC_ARTIFACT_PATTERN = re.compile(
    r"(mcoi/examples/[A-Za-z0-9._/-]+\.json|examples/pilots/[A-Za-z0-9._/-]+\.json)"
)


def discover_example_inventory() -> ExampleArtifactInventory:
    """Discover the governed artifact inventory."""
    pilot_directories = (
        _sort_paths([path for path in PILOT_EXAMPLES_DIR.iterdir() if path.is_dir()])
        if PILOT_EXAMPLES_DIR.exists()
        else ()
    )
    config_paths = _sort_paths(
        list(MCOI_EXAMPLES_DIR.glob("config-*.json"))
        + [path / "config.json" for path in pilot_directories if (path / "config.json").exists()]
    )
    request_paths = _sort_paths(
        list(MCOI_EXAMPLES_DIR.glob("request-*.json"))
        + [path / "request.json" for path in pilot_directories if (path / "request.json").exists()]
    )
    auxiliary_paths = _sort_paths(
        [
            path
            for pilot_directory in pilot_directories
            for path in pilot_directory.glob("*.json")
            if path.name not in {"config.json", "request.json"}
        ]
    )
    maf_runtime_fixture_paths = (
        _sort_paths(list(MAF_RUNTIME_FIXTURE_DIR.glob("*.json")))
        if MAF_RUNTIME_FIXTURE_DIR.exists()
        else ()
    )
    mcoi_runtime_fixture_paths = (
        _sort_paths(list(MCOI_RUNTIME_FIXTURE_DIR.glob("*.json")))
        if MCOI_RUNTIME_FIXTURE_DIR.exists()
        else ()
    )
    return ExampleArtifactInventory(
        config_paths=config_paths,
        request_paths=request_paths,
        auxiliary_paths=auxiliary_paths,
        maf_runtime_fixture_paths=maf_runtime_fixture_paths,
        mcoi_runtime_fixture_paths=mcoi_runtime_fixture_paths,
        pilot_directories=pilot_directories,
    )


def validate_config_artifact(path: Path) -> list[str]:
    """Validate a shipped config artifact against the app config contract."""
    try:
        payload = _load_json_object(path, kind="config")
        AppConfig.from_mapping(payload)
    except ValueError as exc:
        return [f"{_relative_path(path)}: {exc}"]
    return []


def _load_request_config(request_path: Path) -> tuple[AppConfig | None, list[str]]:
    paired_config_path = request_path.parent / "config.json"
    if not paired_config_path.exists():
        return AppConfig(), []
    errors = validate_config_artifact(paired_config_path)
    if errors:
        return None, errors
    return AppConfig.from_mapping(_load_json_object(paired_config_path, kind="config")), []


def validate_request_artifact(path: Path) -> list[str]:
    """Validate a shipped request artifact against the CLI request and template contracts."""
    errors: list[str] = []

    try:
        payload = _load_json_object(path, kind="request")
        request = _build_operator_request(payload, source_name=_relative_path(path))
    except ValueError as exc:
        return [str(exc)]

    validator = TemplateValidator()
    try:
        validated_template = validator.validate(request.template, request.bindings)
    except TemplateValidationError as exc:
        errors.append(f"{_relative_path(path)}: invalid request template {exc.code}: {exc}")
        return errors

    config, config_errors = _load_request_config(path)
    errors.extend(config_errors)
    if config is None:
        return errors

    if validated_template.action_type.value not in config.enabled_executor_routes:
        errors.append(
            f"{_relative_path(path)}: action route '{validated_template.action_type.value}' "
            "is not enabled by the paired config"
        )

    return errors


def validate_auxiliary_artifact(path: Path, *, artifact_key: str | None = None) -> list[str]:
    """Validate one governed auxiliary pilot artifact."""
    validator_key = artifact_key or _relative_path(path)
    validator = AUXILIARY_PILOT_VALIDATORS.get(validator_key)
    if validator is None:
        return [f"{_relative_path(path)}: no auxiliary validator registered"]
    return validator(path)


def validate_maf_runtime_fixture(path: Path, *, fixture_name: str | None = None) -> list[str]:
    """Validate one governed MAF runtime fixture witness."""
    validator_key = fixture_name or path.name
    validator = MAF_RUNTIME_FIXTURE_VALIDATORS.get(validator_key)
    if validator is None:
        return [f"{_relative_path(path)}: no MAF runtime fixture validator registered"]
    return validator(path)


def validate_maf_runtime_fixtures(*, strict: bool = False) -> list[str]:
    """Validate governed MAF runtime fixture inventory and witness shape."""
    errors: list[str] = []
    inventory = discover_example_inventory()
    actual_paths = inventory.maf_runtime_fixture_paths
    actual_names = {path.name for path in actual_paths}
    expected_names = set(MAF_RUNTIME_FIXTURE_VALIDATORS)

    if not MAF_RUNTIME_FIXTURE_DIR.exists():
        return [f"MAF runtime fixture directory not found: {_relative_path(MAF_RUNTIME_FIXTURE_DIR)}"]

    missing_fixtures = sorted(expected_names - actual_names)
    if missing_fixtures:
        errors.append(f"missing governed MAF runtime fixtures: {missing_fixtures}")
    if strict:
        unexpected_fixtures = sorted(actual_names - expected_names)
        if unexpected_fixtures:
            errors.append(f"unexpected MAF runtime fixtures: {unexpected_fixtures}")
    if strict and not actual_paths:
        errors.append("no governed MAF runtime fixtures discovered")

    for fixture_path in actual_paths:
        errors.extend(validate_maf_runtime_fixture(fixture_path))

    return errors


def validate_mcoi_runtime_fixture(path: Path, *, fixture_name: str | None = None) -> list[str]:
    """Validate one governed MCOI runtime fixture witness."""
    validator_key = fixture_name or path.name
    validator = MCOI_RUNTIME_FIXTURE_VALIDATORS.get(validator_key)
    if validator is None:
        return [f"{_relative_path(path)}: no MCOI runtime fixture validator registered"]
    return validator(path)


def validate_mcoi_runtime_fixtures(*, strict: bool = False) -> list[str]:
    """Validate governed MCOI runtime fixture inventory and witness shape."""
    errors: list[str] = []
    inventory = discover_example_inventory()
    actual_paths = inventory.mcoi_runtime_fixture_paths
    actual_names = {path.name for path in actual_paths}
    expected_names = set(MCOI_RUNTIME_FIXTURE_VALIDATORS)

    if not MCOI_RUNTIME_FIXTURE_DIR.exists():
        return [f"MCOI runtime fixture directory not found: {_relative_path(MCOI_RUNTIME_FIXTURE_DIR)}"]

    missing_fixtures = sorted(expected_names - actual_names)
    if missing_fixtures:
        errors.append(f"missing governed MCOI runtime fixtures: {missing_fixtures}")
    if strict:
        unexpected_fixtures = sorted(actual_names - expected_names)
        if unexpected_fixtures:
            errors.append(f"unexpected MCOI runtime fixtures: {unexpected_fixtures}")
    if strict and not actual_paths:
        errors.append("no governed MCOI runtime fixtures discovered")

    for fixture_path in actual_paths:
        errors.extend(validate_mcoi_runtime_fixture(fixture_path))

    return errors


def validate_document_artifact_reference_text(
    *,
    document_name: str,
    content: str,
    expected_paths: tuple[str, ...],
    governed_paths: set[str],
    strict: bool = False,
) -> list[str]:
    """Validate governed artifact references within one markdown document."""
    errors: list[str] = []
    referenced_paths = tuple(sorted(set(_DOC_ARTIFACT_PATTERN.findall(content))))

    missing_expected = sorted(set(expected_paths) - set(referenced_paths))
    if missing_expected:
        errors.append(
            f"{document_name}: missing governed artifact references {missing_expected}"
        )

    for referenced_path in referenced_paths:
        artifact_path = REPO_ROOT / referenced_path
        if referenced_path not in governed_paths:
            errors.append(
                f"{document_name}: references ungoverned artifact path {referenced_path}"
            )
        elif not artifact_path.exists():
            errors.append(
                f"{document_name}: references missing artifact path {referenced_path}"
            )

    if strict:
        unexpected_references = sorted(set(referenced_paths) - set(expected_paths))
        if unexpected_references:
            errors.append(
                f"{document_name}: unexpected governed artifact references {unexpected_references}"
            )

    return errors


def validate_documented_artifact_references(*, strict: bool = False) -> list[str]:
    """Validate markdown references to governed artifacts."""
    errors: list[str] = []
    inventory = discover_example_inventory()
    governed_paths = {
        _relative_path(path)
        for path in (
            list(inventory.config_paths)
            + list(inventory.request_paths)
            + list(inventory.auxiliary_paths)
        )
    }

    for document_name, expected_paths in DOCUMENT_ARTIFACT_EXPECTATIONS.items():
        document_path = REPO_ROOT / document_name
        if not document_path.exists():
            errors.append(f"{document_name}: documentation file not found")
            continue

        content = document_path.read_text(encoding="utf-8")
        errors.extend(
            validate_document_artifact_reference_text(
                document_name=document_name,
                content=content,
                expected_paths=expected_paths,
                governed_paths=governed_paths,
                strict=strict,
            )
        )

    return errors


def validate_operational_document_text(
    *,
    document_name: str,
    content: str,
    strict: bool = False,
) -> list[str]:
    """Validate non-JSON governed documents against live inventories."""
    expectation = OPERATIONAL_DOCUMENT_EXPECTATIONS.get(document_name)
    if expectation is None:
        return [f"{document_name}: no operational document expectation registered"] if strict else []

    errors: list[str] = []

    missing_literals = tuple(
        literal for literal in expectation.required_literals if literal not in content
    )
    if missing_literals:
        errors.append(f"{document_name}: missing required literals {list(missing_literals)}")

    stale_literals = tuple(
        literal for literal in expectation.forbidden_literals if literal in content
    )
    if stale_literals:
        errors.append(f"{document_name}: contains stale literals {list(stale_literals)}")

    if expectation.require_all_profiles:
        missing_profiles = tuple(
            profile_name for profile_name in list_profiles() if profile_name not in content
        )
        if missing_profiles:
            errors.append(f"{document_name}: missing built-in profiles {list(missing_profiles)}")

    if expectation.require_all_policy_packs:
        pack_ids = tuple(pack.pack_id for pack in PolicyPackRegistry().list_packs())
        missing_pack_ids = tuple(pack_id for pack_id in pack_ids if pack_id not in content)
        if missing_pack_ids:
            errors.append(f"{document_name}: missing policy pack IDs {list(missing_pack_ids)}")

    return errors


def validate_operational_documents(*, strict: bool = False) -> list[str]:
    """Validate release and pilot operational docs against governed inventories."""
    errors: list[str] = []

    for document_name in OPERATIONAL_DOCUMENT_EXPECTATIONS:
        document_path = REPO_ROOT / document_name
        if not document_path.exists():
            errors.append(f"{document_name}: operational document not found")
            continue

        content = document_path.read_text(encoding="utf-8")
        errors.extend(
            validate_operational_document_text(
                document_name=document_name,
                content=content,
                strict=strict,
            )
        )

    return errors


def validate_example_artifacts(*, strict: bool = False) -> list[str]:
    """Validate the shipped example inventory."""
    inventory = discover_example_inventory()
    errors: list[str] = []

    if strict and not inventory.config_paths:
        errors.append("no shipped config artifacts discovered")
    if strict and not inventory.request_paths:
        errors.append("no shipped request artifacts discovered")
    if strict and not inventory.maf_runtime_fixture_paths:
        errors.append("no governed MAF runtime fixtures discovered")
    if strict and not inventory.mcoi_runtime_fixture_paths:
        errors.append("no governed MCOI runtime fixtures discovered")
    if strict:
        expected_auxiliary = set(AUXILIARY_PILOT_VALIDATORS)
        actual_auxiliary = {_relative_path(path) for path in inventory.auxiliary_paths}
        missing_auxiliary = sorted(expected_auxiliary - actual_auxiliary)
        unexpected_auxiliary = sorted(actual_auxiliary - expected_auxiliary)
        if missing_auxiliary:
            errors.append(f"missing governed auxiliary pilot artifacts: {missing_auxiliary}")
        if unexpected_auxiliary:
            errors.append(f"unexpected auxiliary pilot artifacts: {unexpected_auxiliary}")

    for pilot_directory in inventory.pilot_directories:
        if not (pilot_directory / "config.json").exists():
            errors.append(
                f"{_relative_path(pilot_directory)}: pilot directory missing required config.json"
            )

    for config_path in inventory.config_paths:
        errors.extend(validate_config_artifact(config_path))

    for request_path in inventory.request_paths:
        errors.extend(validate_request_artifact(request_path))

    for auxiliary_path in inventory.auxiliary_paths:
        errors.extend(validate_auxiliary_artifact(auxiliary_path))

    errors.extend(validate_maf_runtime_fixtures(strict=strict))
    errors.extend(validate_mcoi_runtime_fixtures(strict=strict))
    errors.extend(validate_documented_artifact_references(strict=strict))
    errors.extend(validate_operational_documents(strict=strict))

    return errors


def main() -> None:
    strict = "--strict" in sys.argv
    inventory = discover_example_inventory()

    print("=== Artifact Inventory ===")
    print(f"  config artifacts:  {len(inventory.config_paths)}")
    print(f"  request artifacts: {len(inventory.request_paths)}")
    print(f"  auxiliary files:   {len(inventory.auxiliary_paths)}")
    print(f"  MAF fixtures:      {len(inventory.maf_runtime_fixture_paths)}")
    print(f"  MCOI fixtures:     {len(inventory.mcoi_runtime_fixture_paths)}")
    print(f"  pilot directories: {len(inventory.pilot_directories)}")

    print("\n=== Artifact Validation ===")
    errors = validate_example_artifacts(strict=strict)
    if errors:
        print(f"\n{'=' * 40}")
        print(f"FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    print("ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
