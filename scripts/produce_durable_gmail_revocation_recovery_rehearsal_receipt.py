#!/usr/bin/env python3
"""Produce a durable Gmail revocation recovery rehearsal receipt.

Purpose: rehearse the Gmail OAuth invalid-grant recovery path without
performing a provider revocation call or serializing credential values.
Governance scope: Gmail OAuth revocation recovery, failed-refresh handling,
secret redaction, no external provider mutation, and no production claim.
Dependencies: gateway.gmail_oauth_lifecycle and
scripts.validate_durable_gmail_revocation_recovery_rehearsal_receipt.
Invariants:
  - No access token, refresh token, client secret, or private key is serialized.
  - No external provider revocation or mailbox write is performed.
  - The rehearsed invalid-grant path must require reauthorization.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gateway.gmail_oauth_lifecycle import (  # noqa: E402
    GMAIL_READONLY_SCOPE,
    GmailOAuthLifecycleConfig,
    GmailOAuthSecretRefs,
    GmailOAuthWitnessRefs,
    assert_no_secret_values,
    classify_refresh_response,
)
from scripts.validate_durable_gmail_revocation_recovery_rehearsal_receipt import (  # noqa: E402
    validate_revocation_recovery_rehearsal_receipt,
)


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_revocation_recovery_rehearsal_receipt.json"
DEFAULT_REFRESH_TOKEN_STORAGE_REF = "receipt:gmail-refresh-token-storage"
DEFAULT_REVOCATION_RECOVERY_REF = "witness:gmail-revocation-recovery-rehearsal"


def produce_revocation_recovery_rehearsal_receipt(
    *,
    environment: Mapping[str, str] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Produce a redacted non-destructive Gmail revocation recovery receipt."""

    env = dict(os.environ if environment is None else environment)
    checked_at = env.get("MULLU_VALIDATION_TIMESTAMP", "1970-01-01T00:00:00Z")
    config = _lifecycle_config(env)
    outcome = classify_refresh_response(
        status_code=400,
        response_payload={"error": "invalid_grant", "error_description": "redacted"},
        config=config,
    )
    blockers: list[str] = []
    if outcome.status != "refresh_token_revoked_or_expired":
        blockers.append("invalid_grant_not_classified_as_revoked_or_expired")
    if outcome.recovery_action != "halt_for_reauthorization":
        blockers.append("invalid_grant_recovery_action_not_reauthorization")
    if not outcome.requires_reauthorization:
        blockers.append("invalid_grant_did_not_require_reauthorization")

    status = "passed" if not blockers else "failed"
    payload = {
        "receipt_id": "durable_gmail_revocation_recovery_rehearsal_receipt",
        "adapter_id": "communication.gmail_oauth",
        "connector_id": "gmail",
        "mode": "foundation-local",
        "checked_at": checked_at,
        "status": status,
        "solver_outcome": "SolvedVerified" if status == "passed" else "AwaitingEvidence",
        "refresh_failure_case": "invalid_grant",
        "classified_refresh_status": outcome.status,
        "requires_reauthorization": outcome.requires_reauthorization,
        "retryable": outcome.retryable,
        "recovery_action": outcome.recovery_action,
        "refresh_token_storage_ref": config.witness_refs.refresh_token_storage_ref,
        "revocation_recovery_ref": config.witness_refs.revocation_recovery_ref,
        "external_provider_call_performed": False,
        "destructive_revocation_performed": False,
        "external_mailbox_write_performed": False,
        "credential_values_disclosed": False,
        "production_ready_claimed": False,
        "blockers": blockers,
    }
    _write_redacted_json(output_path, payload)
    return payload


def _lifecycle_config(environment: Mapping[str, str]) -> GmailOAuthLifecycleConfig:
    return GmailOAuthLifecycleConfig(
        connector_id="gmail",
        operation_family="read_only_search",
        scope_ids=(GMAIL_READONLY_SCOPE,),
        secret_refs=GmailOAuthSecretRefs(
            client_id_ref="secret:GMAIL_OAUTH_CLIENT_ID",
            client_secret_ref="secret:GMAIL_OAUTH_CLIENT_SECRET",
            refresh_token_ref="secret:GMAIL_REFRESH_TOKEN",
        ),
        witness_refs=GmailOAuthWitnessRefs(
            consent_screen_ref=environment.get("MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF", "witness:gmail-consent"),
            oauth_client_ref=environment.get("MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF", "witness:gmail-client"),
            least_privilege_scope_ref=environment.get(
                "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
                "receipt:gmail-readonly-scope",
            ),
            refresh_token_storage_ref=environment.get(
                "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
                DEFAULT_REFRESH_TOKEN_STORAGE_REF,
            ),
            revocation_recovery_ref=environment.get(
                "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
                DEFAULT_REVOCATION_RECOVERY_REF,
            ),
        ),
    )


def _write_redacted_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    assert_no_secret_values(serialized)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for durable Gmail revocation recovery rehearsal."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = produce_revocation_recovery_rehearsal_receipt(output_path=args.output)
    validation = validate_revocation_recovery_rehearsal_receipt(args.output, now=str(payload.get("checked_at", "")))
    response = {"receipt": payload, "validation": validation}
    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    if args.strict and not validation["ready_for_recovery_rehearsal"]:
        return 1
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
