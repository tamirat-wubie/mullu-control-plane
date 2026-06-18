#!/usr/bin/env python3
"""Mint a TeamOps shared inbox terminal closure certificate.

Purpose: convert a ready TeamOps terminal closure review packet into the
canonical terminal closure certificate schema.
Governance scope: TeamOps workflow closure, evidence binding, replay binding,
duplicate-action protection, certificate minting, and no-production-claim
constraints.
Dependencies: schemas/terminal_closure_certificate.schema.json and
scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet.
Invariants:
  - Only ready TeamOps terminal closure review packets can mint certificates.
  - Provider-observation receipt identity is preserved from the review packet.
  - The minting producer performs no provider call, mailbox write, draft, or send.
  - The emitted certificate is schema-valid and redacted before it is written.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_REVIEW_PACKET,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_terminal_closure_review_packet import (  # noqa: E402
    validate_team_ops_shared_inbox_terminal_closure_review_packet,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "terminal_closure_certificate.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_certificate.json"
TERMINAL_CERTIFICATE_SCHEMA_ID = "urn:mullusi:schema:terminal-closure-certificate:1"
WORKFLOW_ID = "team_ops.shared_inbox_triage"


def mint_team_ops_shared_inbox_terminal_closure_certificate(
    *,
    review_packet_path: Path = DEFAULT_REVIEW_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
    closed_at: str | None = None,
) -> dict[str, Any]:
    """Mint a canonical terminal closure certificate from a ready review packet."""

    review_validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=review_packet_path,
        require_ready=True,
    )
    if not review_validation.valid or not review_validation.ready:
        raise RuntimeError("TeamOps terminal closure review packet not ready for certificate minting")
    review_packet = _load_json_object(review_packet_path, "TeamOps terminal closure review packet")
    _assert_redacted(review_packet)
    certificate = _certificate_from_review_packet(
        review_packet=review_packet,
        review_packet_path=review_packet_path,
        closed_at=closed_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    _assert_redacted(certificate)
    schema_errors = _validate_schema_instance(_load_schema(schema_path), certificate)
    if schema_errors:
        raise RuntimeError(f"TeamOps terminal closure certificate schema validation failed: {schema_errors}")
    return certificate


def write_team_ops_shared_inbox_terminal_closure_certificate(
    certificate: Mapping[str, Any],
    output_path: Path,
) -> Path:
    """Write one TeamOps terminal closure certificate artifact."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _certificate_from_review_packet(
    *,
    review_packet: Mapping[str, Any],
    review_packet_path: Path,
    closed_at: str,
) -> dict[str, Any]:
    review_packet_hash = str(review_packet.get("review_packet_hash", ""))
    review_packet_ref = str(review_packet.get("review_packet_ref", ""))
    review_packet_id = str(review_packet.get("receipt_id", ""))
    evidence_refs = _certificate_evidence_refs(review_packet, review_packet_path)
    certificate_id = _certificate_id(
        review_packet_id=review_packet_id,
        review_packet_hash=review_packet_hash,
        provider_observation_receipt_id=str(review_packet.get("provider_observation_receipt_id", "")),
        evidence_refs=evidence_refs,
    )
    return {
        "certificate_id": certificate_id,
        "command_id": WORKFLOW_ID,
        "execution_id": review_packet_id,
        "disposition": "committed",
        "verification_result_id": review_packet_ref,
        "effect_reconciliation_id": f"teamops-effect-reconciliation:{review_packet_hash[:16]}",
        "evidence_refs": evidence_refs,
        "closed_at": closed_at,
        "response_closure_ref": review_packet_ref,
        "memory_entry_id": None,
        "compensation_outcome_id": None,
        "accepted_risk_id": None,
        "case_id": None,
        "graph_refs": [
            f"workflow:{WORKFLOW_ID}",
            f"review_packet:{review_packet_id}",
            f"send_execution:{review_packet.get('send_execution_ref', '')}",
            f"dispatch_receipt:{review_packet.get('dispatch_receipt_ref', '')}",
            f"provider_observation:{review_packet.get('provider_observation_receipt_id', '')}",
            f"provider_message:{review_packet.get('provider_message_ref', '')}",
            f"first_observation:{review_packet.get('first_observation_ref', '')}",
            f"second_observation:{review_packet.get('second_observation_ref', '')}",
            f"replay:{review_packet.get('replay_ref', '')}",
        ],
        "metadata": {
            "source": "team_ops_shared_inbox_terminal_closure_certificate",
            "terminal_proof": True,
            "team_ops_terminal_closure": True,
            "source_review_packet_id": review_packet_id,
            "source_review_packet_ref": review_packet_ref,
            "source_review_packet_hash": review_packet_hash,
            "source_review_packet_path": _artifact_ref(review_packet_path),
            "source_sent_message_observation_receipt_id": str(
                review_packet.get("source_sent_message_observation_receipt_id", "")
            ),
            "source_sent_message_observation_receipt_ref": str(
                review_packet.get("source_sent_message_observation_receipt_ref", "")
            ),
            "provider_observation_receipt_ref": str(review_packet.get("provider_observation_receipt_ref", "")),
            "provider_observation_receipt_id": str(review_packet.get("provider_observation_receipt_id", "")),
            "provider_observation_receipt_valid": review_packet.get("provider_observation_receipt_valid") is True,
            "approval_chain_reviewed": review_packet.get("approval_chain_reviewed") is True,
            "send_execution_reviewed": review_packet.get("send_execution_reviewed") is True,
            "sent_message_observation_reviewed": review_packet.get("sent_message_observation_reviewed") is True,
            "duplicate_absence_reviewed": review_packet.get("duplicate_absence_reviewed") is True,
            "deterministic_replay_reviewed": review_packet.get("deterministic_replay_reviewed") is True,
            "duplicate_absence_observed": review_packet.get("duplicate_absence_observed") is True,
            "deterministic_replay_observed": review_packet.get("deterministic_replay_observed") is True,
            "external_message_sent_by_minting_producer": False,
            "external_mailbox_write_performed_by_minting_producer": False,
            "provider_mutation_performed_by_minting_producer": False,
            "provider_call_performed_by_minting_producer": False,
            "draft_created_by_minting_producer": False,
            "raw_message_content_serialized": False,
            "raw_provider_payload_serialized": False,
            "no_secret_values_serialized": True,
            "production_ready_claimed": False,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
        },
    }


def _certificate_evidence_refs(review_packet: Mapping[str, Any], review_packet_path: Path) -> list[str]:
    refs = [
        _artifact_ref(review_packet_path),
        str(review_packet.get("review_packet_ref", "")),
        str(review_packet.get("source_sent_message_observation_receipt_ref", "")),
        *tuple(str(ref) for ref in review_packet.get("required_terminal_evidence_refs", ()) if isinstance(ref, str)),
        *tuple(str(ref) for ref in review_packet.get("evidence_refs", ()) if isinstance(ref, str)),
    ]
    return [ref for ref in dict.fromkeys(refs) if ref.strip()]


def _certificate_id(
    *,
    review_packet_id: str,
    review_packet_hash: str,
    provider_observation_receipt_id: str,
    evidence_refs: Sequence[str],
) -> str:
    material = {
        "review_packet_id": review_packet_id,
        "review_packet_hash": review_packet_hash,
        "provider_observation_receipt_id": provider_observation_receipt_id,
        "evidence_refs": list(evidence_refs),
    }
    digest = _stable_hash(material)
    return f"teamops-shared-inbox-terminal-closure-certificate-{digest[:16]}"


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing")
    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _artifact_ref(path: Path) -> str:
    label = path.as_posix().replace("\\", "/")
    if not path.is_absolute():
        return label
    resolved_path = path.resolve(strict=False)
    try:
        relative_label = os.path.relpath(str(resolved_path), str(REPO_ROOT)).replace(os.sep, "/")
    except ValueError:
        return path.name
    if relative_label == "." or relative_label.startswith("../") or relative_label.startswith("..\\"):
        return path.name
    return relative_label


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError(f"TeamOps terminal closure certificate contains secret marker: {marker}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps terminal closure certificate minting arguments."""

    parser = argparse.ArgumentParser(description="Mint TeamOps terminal closure certificate.")
    parser.add_argument("--review-packet", default=str(DEFAULT_REVIEW_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--closed-at")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure certificate minting."""

    args = parse_args(argv)
    try:
        certificate = mint_team_ops_shared_inbox_terminal_closure_certificate(
            review_packet_path=Path(args.review_packet),
            schema_path=Path(args.schema),
            closed_at=args.closed_at,
        )
        write_team_ops_shared_inbox_terminal_closure_certificate(certificate, Path(args.output))
    except (OSError, RuntimeError, ValueError) as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "certificate_minted": False,
                        "error": str(exc),
                        "solver_outcome": "GovernanceBlocked",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"TeamOps terminal closure certificate minting failed: {exc}")
        return 2
    if args.json:
        print(json.dumps(certificate, indent=2, sort_keys=True))
    else:
        print(f"TeamOps terminal closure certificate minted: {certificate['certificate_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
