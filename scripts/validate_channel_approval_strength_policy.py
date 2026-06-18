"""Validate the channel approval-strength policy contract.

Purpose: keep cross-channel approval handling bounded by request, actor,
tenant, channel, and risk-strength proof obligations.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: schemas/channel_approval_strength_policy.schema.json and
examples/channel_approval_strength_policy.foundation.json.
Invariants: casual text cannot approve request-bound actions; high-risk
approvals require operator-bound authority; critical approvals require dual
control.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


SCHEMA_PATH = REPO_ROOT / "schemas" / "channel_approval_strength_policy.schema.json"
EXAMPLE_PATH = REPO_ROOT / "examples" / "channel_approval_strength_policy.foundation.json"
REQUIRED_BLOCKED_PATTERNS = frozenset(
    {
        "casual_yes_without_request_id",
        "expired_approval_response",
        "identity_mismatch",
        "tenant_mismatch",
        "untrusted_response_channel",
        "cross_channel_without_binding_witness",
        "high_risk_without_operator_bound_approval",
        "critical_without_dual_control",
    }
)
REQUIRED_RECEIPTS = frozenset(
    {
        "approval_request_receipt",
        "approval_strength_policy_receipt",
        "identity_binding_receipt",
        "tenant_binding_receipt",
        "request_id_binding_receipt",
        "channel_binding_witness",
        "approval_resolution_receipt",
        "denial_receipt",
    }
)
REQUIRED_PROOF_OBLIGATIONS = frozenset(
    {
        "tenant_identity_bound",
        "actor_identity_bound",
        "request_id_bound",
        "approval_not_expired",
        "risk_strength_satisfied",
        "cross_channel_binding_when_channels_differ",
        "high_risk_operator_bound",
        "critical_dual_control",
        "no_casual_text_approval",
    }
)
REQUIRED_RISK_STRENGTH = {
    "low": "contextual",
    "medium": "request_bound",
    "high": "operator_bound",
    "critical": "dual_control",
}


def load_json_payload(path: Path) -> dict[str, Any]:
    """Load a JSON object from path or raise a causal validation error."""

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def validate_channel_approval_strength_policy(
    payload: dict[str, Any],
    schema_path: Path = SCHEMA_PATH,
) -> list[str]:
    """Return deterministic validation errors for the policy payload."""

    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, payload)

    if payload.get("default_decision") != "block":
        errors.append("default_decision must remain block")
    if payload.get("foundation_mode_only") is not True:
        errors.append("foundation_mode_only must be true")

    cross_channel_rules = payload.get("cross_channel_rules", {})
    if not isinstance(cross_channel_rules, dict):
        errors.append("cross_channel_rules must be an object")
    else:
        for flag_name in (
            "same_identity_required",
            "same_tenant_required",
            "same_request_id_required",
            "binding_witness_required",
        ):
            if cross_channel_rules.get(flag_name) is not True:
                errors.append(f"cross_channel_rules.{flag_name} must be true")
        if cross_channel_rules.get("unbound_cross_channel_approval_decision") != "block":
            errors.append("unbound cross-channel approval must block")

    observed_risk_strength = {
        entry.get("risk_tier"): entry.get("required_strength")
        for entry in payload.get("risk_strength_matrix", [])
        if isinstance(entry, dict)
    }
    for risk_tier, required_strength in REQUIRED_RISK_STRENGTH.items():
        if observed_risk_strength.get(risk_tier) != required_strength:
            errors.append(f"{risk_tier} risk must require {required_strength}")

    blocked_patterns = set(payload.get("blocked_patterns", ()))
    missing_patterns = sorted(REQUIRED_BLOCKED_PATTERNS - blocked_patterns)
    if missing_patterns:
        errors.append(f"blocked_patterns missing {missing_patterns}")

    receipts = set(payload.get("required_receipts", ()))
    missing_receipts = sorted(REQUIRED_RECEIPTS - receipts)
    if missing_receipts:
        errors.append(f"required_receipts missing {missing_receipts}")

    proof_obligations = set(payload.get("proof_obligations", ()))
    missing_obligations = sorted(REQUIRED_PROOF_OBLIGATIONS - proof_obligations)
    if missing_obligations:
        errors.append(f"proof_obligations missing {missing_obligations}")

    return errors


def main() -> int:
    """Validate the Foundation Mode channel approval-strength policy."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=EXAMPLE_PATH,
        help="Path to the channel approval-strength policy JSON.",
    )
    args = parser.parse_args()

    try:
        payload = load_json_payload(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"channel approval-strength policy validation failed: {exc}")
        return 1

    errors = validate_channel_approval_strength_policy(payload)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(f"channel approval-strength policy ok: {payload['policy_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
