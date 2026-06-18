"""Submit a verified trust-ledger anchor export to an external anchor ledger.

Purpose: convert a previously verified trust-ledger anchor export into a
signed, append-only submission receipt.
Governance scope: operator-authorized anchor submission, receipt replay,
tamper-evident ledger chaining, and fail-closed verification.
Dependencies: scripts.verify_anchor_receipt and trust-ledger submission schema.
Invariants:
  - Submission is blocked unless the operator supplies an explicit authority ref
    and confirmation flag.
  - Bundle, anchor receipt, artifact, and package files are verified before any
    ledger append occurs.
  - The submission ledger replay, optional remote submit, and append run under
    one cross-process lock.
  - Submission receipts do not replace terminal closure certificates.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.proxy_policy import ProxyEnvironmentBlocked, assert_proxy_environment_allowed  # noqa: E402
from scripts.verify_anchor_receipt import verify_anchor_receipt_files  # noqa: E402


SUBMISSION_RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_anchor_submission_receipt.schema.json"
REMOTE_PREFLIGHT_SCHEMA_PATH = ROOT / "schemas" / "trust_ledger_remote_submission_preflight.schema.json"
ZERO_HASH = "0" * 64
SUBMISSION_STATUS = "submitted"
MAX_REMOTE_RESPONSE_BYTES = 65_536
MAX_REMOTE_TIMEOUT_SECONDS = 30.0
MAX_SUBMISSION_LEDGER_LOCK_TIMEOUT_SECONDS = 30.0
DEFAULT_SUBMISSION_LEDGER_LOCK_TIMEOUT_SECONDS = 10.0
DEFAULT_SUBMISSION_LEDGER_STALE_LOCK_SECONDS = 120.0
_SUBMISSION_LEDGER_LOCK_HELD = object()
UrlOpen = Callable[..., Any]


def submit_trust_ledger_anchor_export(
    *,
    bundle_path: Path,
    receipt_path: Path,
    artifacts_path: Path,
    package_path: Path,
    ledger_path: Path,
    operator_id: str,
    authority_ref: str,
    submitted_at: str,
    verification_secret: str,
    submission_secret: str,
    signature_key_id: str,
    confirm_submit: bool,
    receipt_out: Path | None = None,
    remote_submit_url: str = "",
    allow_remote_submit: bool = False,
    remote_preflight_receipt_path: Path | None = None,
    remote_api_token: str = "",
    remote_timeout_seconds: float = 10.0,
    ledger_lock_timeout_seconds: float = DEFAULT_SUBMISSION_LEDGER_LOCK_TIMEOUT_SECONDS,
    ledger_stale_lock_seconds: float = DEFAULT_SUBMISSION_LEDGER_STALE_LOCK_SECONDS,
    urlopen: UrlOpen | None = None,
    strict: bool = False,
    _ledger_lock_acquired: object | None = None,
) -> dict[str, Any]:
    """Verify one anchor export and append a signed submission receipt."""
    if not confirm_submit:
        return _report(valid=False, reason="operator_confirmation_required")
    if not _operator_id_allowed(operator_id):
        return _report(valid=False, reason="operator_id_invalid")
    if not _authority_ref_allowed(authority_ref):
        return _report(valid=False, reason="authority_ref_invalid")
    if not submitted_at:
        return _report(valid=False, reason="submitted_at_required")
    if not submission_secret:
        return _report(valid=False, reason="submission_secret_required")
    if not signature_key_id:
        return _report(valid=False, reason="signature_key_id_required")
    if remote_submit_url and not allow_remote_submit:
        return _report(valid=False, reason="remote_submission_confirmation_required")
    if allow_remote_submit and not remote_submit_url:
        return _report(valid=False, reason="remote_submit_url_required")
    if allow_remote_submit and not remote_api_token:
        return _report(valid=False, reason="remote_api_token_required")
    if allow_remote_submit and remote_preflight_receipt_path is None:
        return _report(valid=False, reason="remote_preflight_receipt_required")
    remote_url_error = _validate_remote_submit_url(remote_submit_url) if remote_submit_url else ""
    if remote_url_error:
        return _report(valid=False, reason=remote_url_error)
    remote_timeout_error = _validate_remote_timeout_seconds(remote_timeout_seconds)
    if (remote_submit_url or allow_remote_submit) and remote_timeout_error:
        return _report(valid=False, reason=remote_timeout_error)
    lock_config_error = _validate_submission_ledger_lock_config(
        timeout_seconds=ledger_lock_timeout_seconds,
        stale_lock_seconds=ledger_stale_lock_seconds,
    )
    if lock_config_error:
        return _report(valid=False, reason=lock_config_error)
    if _ledger_lock_acquired is not _SUBMISSION_LEDGER_LOCK_HELD:
        try:
            with _SubmissionLedgerFileLock(
                ledger_path,
                timeout_seconds=ledger_lock_timeout_seconds,
                stale_lock_seconds=ledger_stale_lock_seconds,
            ):
                return submit_trust_ledger_anchor_export(
                    bundle_path=bundle_path,
                    receipt_path=receipt_path,
                    artifacts_path=artifacts_path,
                    package_path=package_path,
                    ledger_path=ledger_path,
                    operator_id=operator_id,
                    authority_ref=authority_ref,
                    submitted_at=submitted_at,
                    verification_secret=verification_secret,
                    submission_secret=submission_secret,
                    signature_key_id=signature_key_id,
                    confirm_submit=confirm_submit,
                    receipt_out=receipt_out,
                    remote_submit_url=remote_submit_url,
                    allow_remote_submit=allow_remote_submit,
                    remote_preflight_receipt_path=remote_preflight_receipt_path,
                    remote_api_token=remote_api_token,
                    remote_timeout_seconds=remote_timeout_seconds,
                    ledger_lock_timeout_seconds=ledger_lock_timeout_seconds,
                    ledger_stale_lock_seconds=ledger_stale_lock_seconds,
                    urlopen=urlopen,
                    strict=strict,
                    _ledger_lock_acquired=_SUBMISSION_LEDGER_LOCK_HELD,
                )
        except TimeoutError as exc:
            return _report(valid=False, reason=str(exc))

    verification = verify_anchor_receipt_files(
        bundle_path=bundle_path,
        receipt_path=receipt_path,
        artifacts_path=artifacts_path,
        package_path=package_path,
        signing_secret=verification_secret,
        strict=strict,
    )
    if verification["valid"] is not True:
        return _report(
            valid=False,
            reason=f"anchor_verification_failed:{verification['reason']}",
            anchor_verification=verification,
        )
    if verification["package_present"] is not True or verification["package_valid"] is not True:
        return _report(
            valid=False,
            reason="package_verification_required",
            anchor_verification=verification,
        )

    receipt_payload = _read_json_object(receipt_path, "anchor_receipt")
    package_payload = _read_json_object(package_path, "package")
    read_error = _first_read_error(receipt_payload, package_payload)
    if read_error:
        return _report(valid=False, **read_error, anchor_verification=verification)

    ledger_state = verify_submission_ledger(ledger_path=ledger_path, signing_secret=submission_secret)
    if ledger_state["valid"] is not True:
        return _report(
            valid=False,
            reason=f"submission_ledger_invalid:{ledger_state['reason']}",
            anchor_verification=verification,
            ledger_state=ledger_state,
        )

    ledger_sequence = int(ledger_state["submission_count"]) + 1
    previous_submission_hash = str(ledger_state["latest_submission_hash"])
    remote_preflight = _remote_preflight_report(valid=True, reason="remote_preflight_not_requested")
    remote_submission = _remote_submission_report(valid=True, reason="remote_submission_not_requested")
    external_anchor_ref = f"ledger://trust-ledger-anchor-submissions/{ledger_sequence}/{verification['anchor_receipt_id']}"
    metadata_extra: dict[str, Any] = {}
    if allow_remote_submit:
        remote_payload = _build_remote_submission_payload(
            verification=verification,
            anchor_receipt=receipt_payload["payload"],
            package=package_payload["payload"],
            operator_id=operator_id,
            authority_ref=authority_ref,
            submitted_at=submitted_at,
            ledger_sequence=ledger_sequence,
            previous_submission_hash=previous_submission_hash,
        )
        remote_preflight = _verify_remote_preflight_receipt(
            preflight_path=remote_preflight_receipt_path,
            payload=remote_payload,
            remote_submit_url=remote_submit_url,
            remote_timeout_seconds=remote_timeout_seconds,
            operator_id=operator_id,
            authority_ref=authority_ref,
            ledger_path=ledger_path,
            ledger_sequence=ledger_sequence,
            previous_submission_hash=previous_submission_hash,
            strict=strict,
        )
        if remote_preflight["valid"] is not True:
            return _report(
                valid=False,
                reason=f"remote_preflight_receipt_failed:{remote_preflight['reason']}",
                anchor_verification=verification,
                ledger_state=ledger_state,
                remote_preflight=remote_preflight,
                remote_submission=_remote_submission_report(
                    valid=False,
                    reason="remote_submission_blocked_by_preflight",
                    submission_payload_hash=str(remote_payload["submission_payload_hash"]),
                ),
            )
        remote_submission = _submit_remote_transparency_log(
            submit_url=remote_submit_url,
            api_token=remote_api_token,
            timeout_seconds=remote_timeout_seconds,
            payload=remote_payload,
            urlopen=urlopen or urllib.request.urlopen,
        )
        if remote_submission["valid"] is not True:
            return _report(
                valid=False,
                reason=f"remote_submission_failed:{remote_submission['reason']}",
                anchor_verification=verification,
                ledger_state=ledger_state,
                remote_preflight=remote_preflight,
                remote_submission=remote_submission,
            )
        external_anchor_ref = str(remote_submission["external_anchor_ref"])
        metadata_extra = {
            "remote_submission_url": remote_submit_url,
            "remote_submission_payload_hash": remote_submission["submission_payload_hash"],
            "remote_response_hash": remote_submission["remote_response_hash"],
            "remote_receipt_hash": remote_submission["remote_receipt_hash"],
            "remote_status_code": remote_submission["status_code"],
            "remote_preflight_receipt_path": _path_label(remote_preflight_receipt_path),
            "remote_preflight_receipt_id": remote_preflight["receipt_id"],
            "remote_preflight_checked_at": remote_preflight["checked_at"],
            "remote_preflight_expected_payload_hash": remote_preflight[
                "expected_remote_submission_payload_hash"
            ],
        }

    submission_receipt = _build_submission_receipt(
        verification=verification,
        anchor_receipt=receipt_payload["payload"],
        package=package_payload["payload"],
        ledger_path=ledger_path,
        ledger_sequence=ledger_sequence,
        previous_submission_hash=previous_submission_hash,
        external_anchor_ref=external_anchor_ref,
        operator_id=operator_id,
        authority_ref=authority_ref,
        submitted_at=submitted_at,
        signing_secret=submission_secret,
        signature_key_id=signature_key_id,
        metadata_extra=metadata_extra,
    )
    schema_errors = _validate_schema_instance(_load_schema(SUBMISSION_RECEIPT_SCHEMA_PATH), submission_receipt)
    if schema_errors:
        return _report(
            valid=False,
            reason="submission_receipt_schema_validation_failed",
            schema_valid=False,
            schema_errors=schema_errors if strict else schema_errors[:10],
            anchor_verification=verification,
            ledger_state=ledger_state,
            remote_preflight=remote_preflight,
            remote_submission=remote_submission,
        )

    _append_jsonl(ledger_path, submission_receipt)
    output_files = {"ledger": str(ledger_path)}
    if receipt_out is not None:
        _write_json(receipt_out, submission_receipt)
        output_files["submission_receipt"] = str(receipt_out)

    return _report(
        valid=True,
        reason="anchor_submission_recorded",
        submitted=True,
        schema_valid=True,
        schema_errors=[],
        anchor_verification=verification,
        ledger_state=ledger_state,
        remote_preflight=remote_preflight,
        remote_submission=remote_submission,
        submission_receipt=submission_receipt,
        output_files=output_files,
    )


def verify_submission_ledger(*, ledger_path: Path, signing_secret: str = "") -> dict[str, Any]:
    """Replay the submission ledger hash chain and optional HMAC signatures."""
    if not ledger_path.exists():
        return _ledger_report(valid=True, reason="ledger_empty")

    latest_submission_hash = ZERO_HASH
    latest_submission_id = ""
    submission_count = 0
    schema = _load_schema(SUBMISSION_RECEIPT_SCHEMA_PATH)
    try:
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return _ledger_report(valid=False, reason="ledger_read_failed", schema_errors=[type(exc).__name__])

    for line_number, line in enumerate(lines, 1):
        if not line:
            return _ledger_report(
                valid=False,
                reason="ledger_blank_line",
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return _ledger_report(
                valid=False,
                reason="ledger_json_invalid",
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        if not isinstance(payload, dict):
            return _ledger_report(
                valid=False,
                reason="ledger_record_must_be_object",
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        schema_errors = _validate_schema_instance(schema, payload)
        if schema_errors:
            return _ledger_report(
                valid=False,
                reason="ledger_record_schema_validation_failed",
                schema_valid=False,
                schema_errors=schema_errors[:10],
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        if int(payload["ledger_sequence"]) != line_number:
            return _ledger_report(
                valid=False,
                reason="ledger_sequence_mismatch",
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        if str(payload["previous_submission_hash"]) != latest_submission_hash:
            return _ledger_report(
                valid=False,
                reason="ledger_previous_hash_mismatch",
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        expected_hash = _submission_hash(payload)
        if not hmac.compare_digest(expected_hash, str(payload["submission_hash"])):
            return _ledger_report(
                valid=False,
                reason="ledger_submission_hash_mismatch",
                latest_submission_hash=latest_submission_hash,
                latest_submission_id=latest_submission_id,
                submission_count=submission_count,
            )
        if signing_secret:
            expected_signature = _submission_signature(payload, signing_secret=signing_secret)
            if not hmac.compare_digest(expected_signature, str(payload["signature"])):
                return _ledger_report(
                    valid=False,
                    reason="ledger_submission_signature_mismatch",
                    latest_submission_hash=latest_submission_hash,
                    latest_submission_id=latest_submission_id,
                    submission_count=submission_count,
                )
        latest_submission_hash = str(payload["submission_hash"])
        latest_submission_id = str(payload["submission_id"])
        submission_count += 1

    return _ledger_report(
        valid=True,
        reason="ledger_verified",
        latest_submission_hash=latest_submission_hash,
        latest_submission_id=latest_submission_id,
        submission_count=submission_count,
    )


def _build_submission_receipt(
    *,
    verification: dict[str, Any],
    anchor_receipt: dict[str, Any],
    package: dict[str, Any],
    ledger_path: Path,
    ledger_sequence: int,
    previous_submission_hash: str,
    external_anchor_ref: str,
    operator_id: str,
    authority_ref: str,
    submitted_at: str,
    signing_secret: str,
    signature_key_id: str,
    metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    anchor_receipt_id = str(verification["anchor_receipt_id"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "submission_id": "trust-anchor-submission-pending",
        "bundle_id": str(verification["bundle_id"]),
        "anchor_receipt_id": anchor_receipt_id,
        "package_id": str(verification["package_id"]),
        "tenant_id": str(package["tenant_id"]),
        "command_id": str(verification["command_id"]),
        "terminal_certificate_id": str(verification["terminal_certificate_id"]),
        "anchor_target": str(anchor_receipt["anchor_target"]),
        "external_anchor_ref": external_anchor_ref,
        "external_anchor_status": SUBMISSION_STATUS,
        "operator_id": operator_id,
        "authority_ref": authority_ref,
        "submitted_at": submitted_at,
        "ledger_path": str(ledger_path),
        "ledger_sequence": ledger_sequence,
        "previous_submission_hash": previous_submission_hash,
        "package_hash": str(verification["package_hash"]),
        "anchor_receipt_hash": str(anchor_receipt["anchor_receipt_hash"]),
        "required_artifact_types": [str(value) for value in anchor_receipt["required_artifact_types"]],
        "anchor_verification_reason": str(verification["reason"]),
        "submission_hash": ZERO_HASH,
        "signature_key_id": signature_key_id,
        "signature": "hmac-sha256:unsigned",
        "metadata": {
            "submission_is_not_terminal_closure": True,
            "requires_operator_confirmation": True,
            "source_package_created_at": str(package["created_at"]),
            **(metadata_extra or {}),
        },
    }
    submission_hash = _submission_hash(payload)
    payload["submission_id"] = f"trust-anchor-submission-{submission_hash[:16]}"
    payload["submission_hash"] = submission_hash
    payload["signature"] = _submission_signature(payload, signing_secret=signing_secret)
    return payload


def _build_remote_submission_payload(
    *,
    verification: dict[str, Any],
    anchor_receipt: dict[str, Any],
    package: dict[str, Any],
    operator_id: str,
    authority_ref: str,
    submitted_at: str,
    ledger_sequence: int,
    previous_submission_hash: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "bundle_id": str(verification["bundle_id"]),
        "anchor_receipt_id": str(verification["anchor_receipt_id"]),
        "package_id": str(verification["package_id"]),
        "tenant_id": str(package["tenant_id"]),
        "command_id": str(verification["command_id"]),
        "terminal_certificate_id": str(verification["terminal_certificate_id"]),
        "anchor_target": str(anchor_receipt["anchor_target"]),
        "operator_id": operator_id,
        "authority_ref": authority_ref,
        "submitted_at": submitted_at,
        "ledger_sequence": ledger_sequence,
        "previous_submission_hash": previous_submission_hash,
        "package_hash": str(verification["package_hash"]),
        "anchor_receipt_hash": str(anchor_receipt["anchor_receipt_hash"]),
        "required_artifact_types": [str(value) for value in anchor_receipt["required_artifact_types"]],
        "anchor_verification_reason": str(verification["reason"]),
    }
    return {**payload, "submission_payload_hash": _stable_hash(payload)}


def _submit_remote_transparency_log(
    *,
    submit_url: str,
    api_token: str,
    timeout_seconds: float,
    payload: dict[str, Any],
    urlopen: UrlOpen,
) -> dict[str, Any]:
    submission_payload_hash = str(payload["submission_payload_hash"])
    request_body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        submit_url,
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Idempotency-Key": submission_payload_hash,
            "X-Mullu-Anchor-Submission-Hash": submission_payload_hash,
        },
    )
    try:
        assert_proxy_environment_allowed()
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", getattr(response, "code", 0)) or 0)
            body = response.read(MAX_REMOTE_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return _remote_submission_report(
            valid=False,
            reason="remote_http_error",
            status_code=int(exc.code),
            submission_payload_hash=submission_payload_hash,
        )
    except ProxyEnvironmentBlocked:
        return _remote_submission_report(
            valid=False,
            reason="remote_proxy_environment_blocked",
            submission_payload_hash=submission_payload_hash,
        )
    except (TimeoutError, OSError, ValueError, urllib.error.URLError) as exc:
        return _remote_submission_report(
            valid=False,
            reason=f"remote_transport_error:{type(exc).__name__}",
            submission_payload_hash=submission_payload_hash,
        )
    if len(body) > MAX_REMOTE_RESPONSE_BYTES:
        return _remote_submission_report(
            valid=False,
            reason="remote_response_too_large",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
        )
    if status_code < 200 or status_code >= 300:
        return _remote_submission_report(
            valid=False,
            reason="remote_status_not_accepted",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
        )
    try:
        remote_payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _remote_submission_report(
            valid=False,
            reason="remote_response_json_invalid",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
        )
    if not isinstance(remote_payload, dict):
        return _remote_submission_report(
            valid=False,
            reason="remote_response_must_be_object",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
        )
    observed_hash = str(remote_payload.get("observed_submission_payload_hash", ""))
    if observed_hash != submission_payload_hash:
        return _remote_submission_report(
            valid=False,
            reason="remote_submission_payload_hash_mismatch",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
            observed_submission_payload_hash=observed_hash,
            remote_response_hash=_stable_hash(remote_payload),
        )
    external_anchor_ref = str(remote_payload.get("external_anchor_ref", ""))
    if _external_anchor_ref_allowed(external_anchor_ref) is not True:
        return _remote_submission_report(
            valid=False,
            reason="remote_external_anchor_ref_invalid",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
            observed_submission_payload_hash=observed_hash,
            remote_response_hash=_stable_hash(remote_payload),
        )
    remote_receipt_hash = str(remote_payload.get("remote_receipt_hash", ""))
    if _remote_receipt_hash_allowed(remote_receipt_hash) is not True:
        return _remote_submission_report(
            valid=False,
            reason="remote_receipt_hash_invalid",
            status_code=status_code,
            submission_payload_hash=submission_payload_hash,
            observed_submission_payload_hash=observed_hash,
            remote_receipt_hash=remote_receipt_hash,
            remote_response_hash=_stable_hash(remote_payload),
        )
    return _remote_submission_report(
        valid=True,
        reason="remote_submission_accepted",
        status_code=status_code,
        external_anchor_ref=external_anchor_ref,
        submission_payload_hash=submission_payload_hash,
        observed_submission_payload_hash=observed_hash,
        remote_receipt_hash=remote_receipt_hash,
        remote_response_hash=_stable_hash(remote_payload),
    )


def _verify_remote_preflight_receipt(
    *,
    preflight_path: Path | None,
    payload: dict[str, Any],
    remote_submit_url: str,
    remote_timeout_seconds: float,
    operator_id: str,
    authority_ref: str,
    ledger_path: Path,
    ledger_sequence: int,
    previous_submission_hash: str,
    strict: bool,
) -> dict[str, Any]:
    if preflight_path is None:
        return _remote_preflight_report(valid=False, reason="remote_preflight_receipt_required")

    preflight_path_label = _path_label(preflight_path)
    loaded = _read_json_object(preflight_path, "remote_preflight_receipt")
    if loaded.get("reason"):
        return _remote_preflight_report(
            valid=False,
            reason=str(loaded["reason"]),
            receipt_path=preflight_path_label,
        )

    preflight = loaded["payload"]
    schema_errors = _validate_schema_instance(_load_schema(REMOTE_PREFLIGHT_SCHEMA_PATH), preflight)
    if schema_errors:
        return _remote_preflight_report(
            valid=False,
            reason="remote_preflight_receipt_schema_validation_failed",
            schema_valid=False,
            schema_errors=schema_errors if strict else schema_errors[:10],
            receipt_path=preflight_path_label,
        )

    preflight_timeout_seconds = float(preflight["remote_timeout_seconds"])
    timeout_error = _validate_remote_timeout_seconds(preflight_timeout_seconds)
    if timeout_error:
        return _remote_preflight_report(
            valid=False,
            reason=timeout_error,
            schema_valid=True,
            receipt_path=preflight_path_label,
            receipt_id=str(preflight["receipt_id"]),
            checked_at=str(preflight["checked_at"]),
        )

    expected_hash = str(preflight["expected_remote_submission_payload_hash"])
    actual_hash = str(payload["submission_payload_hash"])
    canonical_receipt_id = _remote_preflight_receipt_id(preflight)
    if str(preflight["receipt_id"]) != canonical_receipt_id:
        return _remote_preflight_report(
            valid=False,
            reason="receipt_id_mismatch",
            schema_valid=True,
            receipt_path=preflight_path_label,
            receipt_id=str(preflight["receipt_id"]),
            canonical_receipt_id=canonical_receipt_id,
            checked_at=str(preflight["checked_at"]),
            expected_remote_submission_payload_hash=expected_hash,
            actual_remote_submission_payload_hash=actual_hash,
            expected_remote_idempotency_key=str(preflight["expected_remote_idempotency_key"]),
            actual_remote_idempotency_key=actual_hash,
        )

    expected_host = _remote_submit_host(remote_submit_url)
    required_matches = (
        ("ready", preflight["ready"], True),
        ("outcome", preflight["outcome"], "SolvedVerified"),
        ("operator_id", preflight["operator_id"], operator_id),
        ("authority_ref", preflight["authority_ref"], authority_ref),
        ("remote_submit_url", preflight["remote_submit_url"], remote_submit_url),
        ("remote_submit_host", preflight["remote_submit_host"], expected_host),
        ("remote_timeout_seconds", preflight_timeout_seconds, float(remote_timeout_seconds)),
        ("remote_api_token_present", preflight["remote_api_token_present"], True),
        ("verification_secret_present", preflight["verification_secret_present"], True),
        ("submission_secret_present", preflight["submission_secret_present"], True),
        ("signature_key_id_present", preflight["signature_key_id_present"], True),
        ("ledger_path", preflight["ledger_path"], _path_label(ledger_path)),
        ("next_ledger_sequence", int(preflight["next_ledger_sequence"]), ledger_sequence),
        ("previous_submission_hash", preflight["previous_submission_hash"], previous_submission_hash),
        ("required_artifact_types", preflight["required_artifact_types"], payload["required_artifact_types"]),
        ("expected_remote_submission_payload_hash", expected_hash, actual_hash),
        ("expected_remote_idempotency_key", preflight["expected_remote_idempotency_key"], actual_hash),
    )
    for field_name, observed, expected in required_matches:
        if observed != expected:
            return _remote_preflight_report(
                valid=False,
                reason=f"{field_name}_mismatch",
                schema_valid=True,
                receipt_path=preflight_path_label,
                receipt_id=str(preflight["receipt_id"]),
                checked_at=str(preflight["checked_at"]),
                expected_remote_submission_payload_hash=expected_hash,
                actual_remote_submission_payload_hash=actual_hash,
                expected_remote_idempotency_key=str(preflight["expected_remote_idempotency_key"]),
                actual_remote_idempotency_key=actual_hash,
            )

    if preflight["blockers"] or preflight["hard_blockers"]:
        return _remote_preflight_report(
            valid=False,
            reason="remote_preflight_receipt_has_blockers",
            schema_valid=True,
            receipt_path=preflight_path_label,
            receipt_id=str(preflight["receipt_id"]),
            checked_at=str(preflight["checked_at"]),
            expected_remote_submission_payload_hash=expected_hash,
            actual_remote_submission_payload_hash=actual_hash,
            expected_remote_idempotency_key=str(preflight["expected_remote_idempotency_key"]),
            actual_remote_idempotency_key=actual_hash,
        )

    metadata = preflight["metadata"]
    metadata_matches = (
        ("preflight_only", metadata["preflight_only"], True),
        ("remote_submit_executed", metadata["remote_submit_executed"], False),
        ("ledger_append_executed", metadata["ledger_append_executed"], False),
        ("requires_operator_confirmation_for_submit", metadata["requires_operator_confirmation_for_submit"], True),
    )
    for field_name, observed, expected in metadata_matches:
        if observed != expected:
            return _remote_preflight_report(
                valid=False,
                reason=f"metadata_{field_name}_mismatch",
                schema_valid=True,
                receipt_path=preflight_path_label,
                receipt_id=str(preflight["receipt_id"]),
                checked_at=str(preflight["checked_at"]),
                expected_remote_submission_payload_hash=expected_hash,
                actual_remote_submission_payload_hash=actual_hash,
                expected_remote_idempotency_key=str(preflight["expected_remote_idempotency_key"]),
                actual_remote_idempotency_key=actual_hash,
            )

    return _remote_preflight_report(
        valid=True,
        reason="remote_preflight_receipt_verified",
        receipt_path=preflight_path_label,
        receipt_id=str(preflight["receipt_id"]),
        canonical_receipt_id=canonical_receipt_id,
        checked_at=str(preflight["checked_at"]),
        expected_remote_submission_payload_hash=expected_hash,
        actual_remote_submission_payload_hash=actual_hash,
        expected_remote_idempotency_key=str(preflight["expected_remote_idempotency_key"]),
        actual_remote_idempotency_key=actual_hash,
    )


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "reason": f"{label}_read_failed",
            "schema_valid": False,
            "schema_errors": [type(exc).__name__],
        }
    if not isinstance(payload, dict):
        return {
            "reason": f"{label}_json_must_be_object",
            "schema_valid": False,
            "schema_errors": [f"{label} JSON must be an object"],
        }
    return {"reason": "", "payload": payload}


def _first_read_error(*loaded_payloads: dict[str, Any]) -> dict[str, Any] | None:
    for loaded in loaded_payloads:
        if loaded.get("reason"):
            return {
                "reason": str(loaded["reason"]),
                "schema_valid": bool(loaded.get("schema_valid", False)),
                "schema_errors": list(loaded.get("schema_errors", [])),
            }
    return None


def _path_label(path: Path) -> str:
    """Return an evidence path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _authority_ref_allowed(value: str) -> bool:
    if not value or value.strip() != value or len(value) > 256:
        return False
    if any(character.isspace() or ord(character) < 32 for character in value):
        return False
    return value.startswith(("proof://", "authority://"))


def _operator_id_allowed(value: str) -> bool:
    if not value or value.strip() != value or len(value) > 128:
        return False
    return not any(character.isspace() or ord(character) < 32 for character in value)


def _validate_remote_submit_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return "remote_submit_url_invalid"
    if parsed.scheme != "https":
        return "remote_submit_url_must_be_https"
    if not parsed.netloc or not parsed.hostname:
        return "remote_submit_url_host_required"
    if parsed.username or parsed.password:
        return "remote_submit_url_credentials_forbidden"
    if parsed.query or parsed.fragment:
        return "remote_submit_url_query_fragment_forbidden"
    return ""


def _validate_remote_timeout_seconds(value: float) -> str:
    if not math.isfinite(value) or value <= 0 or value > MAX_REMOTE_TIMEOUT_SECONDS:
        return "remote_timeout_seconds_invalid"
    return ""


def _validate_submission_ledger_lock_config(*, timeout_seconds: float, stale_lock_seconds: float) -> str:
    if (
        not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or timeout_seconds > MAX_SUBMISSION_LEDGER_LOCK_TIMEOUT_SECONDS
    ):
        return "submission_ledger_lock_timeout_seconds_invalid"
    if not math.isfinite(stale_lock_seconds) or stale_lock_seconds <= 0:
        return "submission_ledger_stale_lock_seconds_invalid"
    return ""


def _remote_submit_host(value: str) -> str:
    try:
        return urllib.parse.urlparse(value).hostname or ""
    except ValueError:
        return ""


def _external_anchor_ref_allowed(value: str) -> bool:
    if not value or value.strip() != value or len(value) > 512:
        return False
    if any(character.isspace() or ord(character) < 32 for character in value):
        return False
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"https", "ledger"} and bool(parsed.netloc)


def _remote_receipt_hash_allowed(value: str) -> bool:
    prefix = "sha256:"
    digest = value.removeprefix(prefix)
    return value.startswith(prefix) and len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


class _SubmissionLedgerFileLock:
    """Cross-process lock for trust-ledger submission replay and append."""

    def __init__(self, path: Path, *, timeout_seconds: float, stale_lock_seconds: float) -> None:
        self._lock_path = Path(f"{path}.lock")
        self._timeout_seconds = timeout_seconds
        self._stale_lock_seconds = stale_lock_seconds
        self._acquired = False

    def __enter__(self) -> "_SubmissionLedgerFileLock":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._timeout_seconds
        while True:
            try:
                descriptor = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                if self._lock_is_stale():
                    self._lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError("submission_ledger_lock_timeout") from exc
                time.sleep(min(0.05, self._timeout_seconds))
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "pid": os.getpid(),
                    "lock_path": str(self._lock_path),
                    "created_unix": time.time(),
                }, sort_keys=True))
            self._acquired = True
            return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._acquired:
            self._lock_path.unlink(missing_ok=True)
            self._acquired = False

    def _lock_is_stale(self) -> bool:
        try:
            lock_age_seconds = time.time() - self._lock_path.stat().st_mtime
        except FileNotFoundError:
            return False
        return lock_age_seconds > self._stale_lock_seconds


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _submission_hash(payload: dict[str, Any]) -> str:
    hashed_payload = dict(payload)
    hashed_payload["submission_id"] = ""
    hashed_payload["submission_hash"] = ""
    hashed_payload["signature"] = ""
    return _stable_hash(hashed_payload)


def _submission_signature(payload: dict[str, Any], *, signing_secret: str) -> str:
    signed_payload = dict(payload)
    signed_payload["signature"] = ""
    encoded = json.dumps(signed_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hmac.new(signing_secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _remote_preflight_receipt_id(preflight: dict[str, Any]) -> str:
    anchor_verification = preflight.get("anchor_verification", {})
    ledger_state = preflight.get("ledger_state", {})
    metadata = preflight.get("metadata", {})
    receipt_seed = {
        "schema_version": int(preflight["schema_version"]),
        "checked_at": str(preflight["checked_at"]),
        "ready": bool(preflight["ready"]),
        "outcome": str(preflight["outcome"]),
        "operator_id": str(preflight["operator_id"]),
        "authority_ref": str(preflight["authority_ref"]),
        "remote_submit_url": str(preflight["remote_submit_url"]),
        "remote_submit_host": str(preflight["remote_submit_host"]),
        "remote_timeout_seconds": float(preflight["remote_timeout_seconds"]),
        "remote_api_token_present": bool(preflight["remote_api_token_present"]),
        "verification_secret_present": bool(preflight["verification_secret_present"]),
        "submission_secret_present": bool(preflight["submission_secret_present"]),
        "signature_key_id_present": bool(preflight["signature_key_id_present"]),
        "ledger_path": str(preflight["ledger_path"]),
        "next_ledger_sequence": int(preflight["next_ledger_sequence"]),
        "previous_submission_hash": str(preflight["previous_submission_hash"]),
        "required_artifact_types": [str(value) for value in preflight["required_artifact_types"]],
        "expected_remote_submission_payload_hash": str(preflight["expected_remote_submission_payload_hash"]),
        "expected_remote_idempotency_key": str(preflight["expected_remote_idempotency_key"]),
        "steps": [
            {
                "name": str(step["name"]),
                "passed": bool(step["passed"]),
                "detail": str(step["detail"]),
            }
            for step in preflight["steps"]
        ],
        "blockers": [str(blocker) for blocker in preflight["blockers"]],
        "hard_blockers": [str(blocker) for blocker in preflight["hard_blockers"]],
        "anchor_verification_hash": _stable_hash(anchor_verification),
        "anchor_verification_reason": str(anchor_verification.get("reason", "")),
        "ledger_state_hash": _stable_hash(ledger_state),
        "ledger_state_reason": str(ledger_state.get("reason", "")),
        "metadata": {
            "preflight_only": bool(metadata["preflight_only"]),
            "remote_submit_executed": bool(metadata["remote_submit_executed"]),
            "ledger_append_executed": bool(metadata["ledger_append_executed"]),
            "requires_operator_confirmation_for_submit": bool(metadata["requires_operator_confirmation_for_submit"]),
        },
    }
    return f"trust-ledger-remote-submission-preflight-{_stable_hash(receipt_seed)[:16]}"


def _report(
    *,
    valid: bool,
    reason: str,
    submitted: bool = False,
    schema_valid: bool = True,
    schema_errors: list[str] | None = None,
    anchor_verification: dict[str, Any] | None = None,
    ledger_state: dict[str, Any] | None = None,
    remote_submission: dict[str, Any] | None = None,
    remote_preflight: dict[str, Any] | None = None,
    submission_receipt: dict[str, Any] | None = None,
    output_files: dict[str, str] | None = None,
) -> dict[str, Any]:
    receipt = submission_receipt or {}
    verification = anchor_verification or {}
    return {
        "valid": valid,
        "reason": reason,
        "submitted": submitted,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors or [],
        "bundle_id": str(receipt.get("bundle_id", verification.get("bundle_id", ""))),
        "anchor_receipt_id": str(receipt.get("anchor_receipt_id", verification.get("anchor_receipt_id", ""))),
        "package_id": str(receipt.get("package_id", verification.get("package_id", ""))),
        "submission_id": str(receipt.get("submission_id", "")),
        "ledger_path": str(receipt.get("ledger_path", "")),
        "ledger_sequence": int(receipt.get("ledger_sequence", 0) or 0),
        "previous_submission_hash": str(receipt.get("previous_submission_hash", "")),
        "submission_hash": str(receipt.get("submission_hash", "")),
        "signature_key_id": str(receipt.get("signature_key_id", "")),
        "anchor_verification": verification,
        "ledger_state": ledger_state or {},
        "remote_preflight": remote_preflight or {},
        "remote_submission": remote_submission or {},
        "submission_receipt": receipt,
        "output_files": output_files or {},
    }


def _ledger_report(
    *,
    valid: bool,
    reason: str,
    schema_valid: bool = True,
    schema_errors: list[str] | None = None,
    latest_submission_hash: str = ZERO_HASH,
    latest_submission_id: str = "",
    submission_count: int = 0,
) -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors or [],
        "latest_submission_hash": latest_submission_hash,
        "latest_submission_id": latest_submission_id,
        "submission_count": submission_count,
    }


def _remote_submission_report(
    *,
    valid: bool,
    reason: str,
    status_code: int = 0,
    external_anchor_ref: str = "",
    submission_payload_hash: str = "",
    observed_submission_payload_hash: str = "",
    remote_receipt_hash: str = "",
    remote_response_hash: str = "",
) -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
        "status_code": status_code,
        "external_anchor_ref": external_anchor_ref,
        "submission_payload_hash": submission_payload_hash,
        "observed_submission_payload_hash": observed_submission_payload_hash,
        "remote_receipt_hash": remote_receipt_hash,
        "remote_response_hash": remote_response_hash,
    }


def _remote_preflight_report(
    *,
    valid: bool,
    reason: str,
    schema_valid: bool = True,
    schema_errors: list[str] | None = None,
    receipt_path: str = "",
    receipt_id: str = "",
    canonical_receipt_id: str = "",
    checked_at: str = "",
    expected_remote_submission_payload_hash: str = "",
    actual_remote_submission_payload_hash: str = "",
    expected_remote_idempotency_key: str = "",
    actual_remote_idempotency_key: str = "",
) -> dict[str, Any]:
    return {
        "valid": valid,
        "reason": reason,
        "schema_valid": schema_valid,
        "schema_errors": schema_errors or [],
        "receipt_path": receipt_path,
        "receipt_id": receipt_id,
        "canonical_receipt_id": canonical_receipt_id,
        "checked_at": checked_at,
        "expected_remote_submission_payload_hash": expected_remote_submission_payload_hash,
        "actual_remote_submission_payload_hash": actual_remote_submission_payload_hash,
        "expected_remote_idempotency_key": expected_remote_idempotency_key,
        "actual_remote_idempotency_key": actual_remote_idempotency_key,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a verified trust-ledger anchor export")
    parser.add_argument("--bundle", required=True, type=Path, help="Path to trust-ledger bundle JSON")
    parser.add_argument("--receipt", required=True, type=Path, help="Path to external anchor receipt JSON")
    parser.add_argument("--artifacts", required=True, type=Path, help="Path to evidence artifact array JSON")
    parser.add_argument("--package", required=True, type=Path, help="Path to trust-ledger export package JSON")
    parser.add_argument("--ledger-path", required=True, type=Path, help="Append-only external anchor ledger JSONL path")
    parser.add_argument("--receipt-out", type=Path, help="Optional path for the signed submission receipt JSON")
    parser.add_argument("--operator-id", required=True, help="Operator identity authorizing the submission")
    parser.add_argument("--authority-ref", required=True, help="proof:// or authority:// reference for operator authority")
    parser.add_argument("--submitted-at", required=True, help="Submission timestamp as an RFC3339 date-time")
    parser.add_argument(
        "--verification-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_SECRET", ""),
        help="Anchor HMAC secret; defaults to MULLU_TRUST_LEDGER_ANCHOR_SECRET",
    )
    parser.add_argument(
        "--submission-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_SUBMISSION_SECRET", ""),
        help="Submission HMAC secret; defaults to MULLU_TRUST_LEDGER_SUBMISSION_SECRET",
    )
    parser.add_argument(
        "--signature-key-id",
        default=os.environ.get("MULLU_TRUST_LEDGER_SUBMISSION_KEY_ID", "anchor-submission-key"),
    )
    parser.add_argument("--remote-submit-url", default="", help="Optional HTTPS transparency-log submission endpoint")
    parser.add_argument("--allow-remote-submit", action="store_true", help="Explicitly authorize remote HTTPS submit")
    parser.add_argument(
        "--remote-preflight-receipt",
        type=Path,
        help="Required read-only preflight receipt for effect-bearing remote submission",
    )
    parser.add_argument(
        "--remote-api-token",
        default=os.environ.get("MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_TOKEN", ""),
        help="Remote submission bearer token; defaults to MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_TOKEN",
    )
    parser.add_argument("--remote-timeout-seconds", type=float, default=10.0)
    parser.add_argument(
        "--ledger-lock-timeout-seconds",
        type=float,
        default=DEFAULT_SUBMISSION_LEDGER_LOCK_TIMEOUT_SECONDS,
        help="Maximum seconds to wait for the submission-ledger replay/append lock",
    )
    parser.add_argument(
        "--ledger-stale-lock-seconds",
        type=float,
        default=DEFAULT_SUBMISSION_LEDGER_STALE_LOCK_SECONDS,
        help="Age after which a submission-ledger lock witness may be treated as stale",
    )
    parser.add_argument("--confirm-submit", action="store_true", help="Explicitly authorize ledger append")
    parser.add_argument("--strict", action="store_true", help="Return all schema errors")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args(argv)

    report = submit_trust_ledger_anchor_export(
        bundle_path=args.bundle,
        receipt_path=args.receipt,
        artifacts_path=args.artifacts,
        package_path=args.package,
        ledger_path=args.ledger_path,
        operator_id=args.operator_id,
        authority_ref=args.authority_ref,
        submitted_at=args.submitted_at,
        verification_secret=args.verification_secret,
        submission_secret=args.submission_secret,
        signature_key_id=args.signature_key_id,
        confirm_submit=args.confirm_submit,
        receipt_out=args.receipt_out,
        remote_submit_url=args.remote_submit_url,
        allow_remote_submit=args.allow_remote_submit,
        remote_preflight_receipt_path=args.remote_preflight_receipt,
        remote_api_token=args.remote_api_token,
        remote_timeout_seconds=args.remote_timeout_seconds,
        ledger_lock_timeout_seconds=args.ledger_lock_timeout_seconds,
        ledger_stale_lock_seconds=args.ledger_stale_lock_seconds,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "submitted" if report["valid"] else "blocked"
        print(f"anchor export submission {status}: {report['reason']}")
        if report.get("submission_id"):
            print(f"submission_id: {report['submission_id']}")
        if report.get("ledger_path"):
            print(f"ledger_path: {report['ledger_path']}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
