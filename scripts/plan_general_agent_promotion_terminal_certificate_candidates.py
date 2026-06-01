#!/usr/bin/env python3
"""Plan terminal certificate candidates from the promotion terminal gate.

Purpose: produce a non-executing candidate set from admitted terminal gate
items without minting terminal closure certificates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: general-agent promotion terminal certificate gate and candidate
schema.
Invariants:
  - Only admitted gate items become candidates.
  - Blocked gate items are summarized, not promoted.
  - This planner never executes actions or mints terminal closure certificates.
  - Secret values are never read or serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.plan_general_agent_promotion_terminal_certificate_gate import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_TERMINAL_GATE,
    validate_general_agent_promotion_terminal_certificate_gate,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_terminal_certificate_candidates.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_certificate_candidates.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"
TERMINAL_CERTIFICATE_SCHEMA_ID = "urn:mullusi:schema:terminal-closure-certificate:1"
TERMINAL_GATE_SCHEMA_ID = "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
ADMITTED_GATE_STATUSES = frozenset({"admitted_runnable", "admitted_approved"})


@dataclass(frozen=True, slots=True)
class TerminalCertificateCandidate:
    """One non-executing terminal certificate candidate."""

    candidate_id: str
    source_gate_item_id: str
    source_queue_item_id: str
    source_action_id: str
    source_plan_type: str
    terminal_gate_status: str
    approval_ref_present: bool
    approval_ref: str | None
    evidence_required: tuple[str, ...]
    receipt_validator: str

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready candidate data."""
        return {
            "candidate_id": self.candidate_id,
            "source_gate_item_id": self.source_gate_item_id,
            "source_queue_item_id": self.source_queue_item_id,
            "source_action_id": self.source_action_id,
            "source_plan_type": self.source_plan_type,
            "terminal_gate_status": self.terminal_gate_status,
            "approval_ref_present": self.approval_ref_present,
            "approval_ref": self.approval_ref,
            "evidence_required": list(self.evidence_required),
            "receipt_validator": self.receipt_validator,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
            "minting_status": "candidate_only",
            "certificate_minted": False,
            "execution_performed": False,
        }


@dataclass(frozen=True, slots=True)
class TerminalCertificateCandidatePlan:
    """Non-executing terminal certificate candidate set."""

    schema_version: int
    candidate_set_id: str
    generated_at: str
    source_gate_path: str
    source_gate_id: str
    ready_for_candidate_review: bool
    ready_for_terminal_certificate_minting: bool
    gate_action_count: int
    candidate_count: int
    skipped_gate_action_count: int
    blocked_gate_action_count: int
    blocked_reasons: tuple[str, ...]
    candidates: tuple[TerminalCertificateCandidate, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready candidate set data."""
        return {
            "schema_version": self.schema_version,
            "candidate_set_id": self.candidate_set_id,
            "generated_at": self.generated_at,
            "source_gate_path": self.source_gate_path,
            "source_gate_id": self.source_gate_id,
            "ready_for_candidate_review": self.ready_for_candidate_review,
            "ready_for_terminal_certificate_minting": self.ready_for_terminal_certificate_minting,
            "gate_action_count": self.gate_action_count,
            "candidate_count": self.candidate_count,
            "skipped_gate_action_count": self.skipped_gate_action_count,
            "blocked_gate_action_count": self.blocked_gate_action_count,
            "blocked_reasons": list(self.blocked_reasons),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "metadata": dict(self.metadata),
        }


def plan_general_agent_promotion_terminal_certificate_candidates(
    *,
    gate_path: Path = DEFAULT_TERMINAL_GATE,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> TerminalCertificateCandidatePlan:
    """Plan terminal certificate candidates from admitted terminal gate items."""
    gate = _load_json_object(gate_path, "terminal certificate gate")
    gate_errors = validate_general_agent_promotion_terminal_certificate_gate(gate)
    gate_hash = _stable_hash(gate)
    if gate_errors:
        return _candidate_plan(
            gate_path=gate_path,
            generated_at=generated_at,
            gate=gate,
            gate_hash=gate_hash,
            candidates=(),
            blocked_reasons=tuple(f"terminal_certificate_gate_invalid:{error}" for error in gate_errors),
        )
    candidates = tuple(
        _candidate_from_gate_action(action)
        for action in _gate_actions(gate)
        if _is_admitted_gate_action(action)
    )
    blocked_reasons = tuple(
        sorted(
            {
                reason
                for action in _gate_actions(gate)
                if not _is_admitted_gate_action(action)
                for reason in _string_tuple(action.get("blocked_reasons", ()))
            }
            | {"terminal_certificate_minting_not_performed"}
        )
    )
    return _candidate_plan(
        gate_path=gate_path,
        generated_at=generated_at,
        gate=gate,
        gate_hash=gate_hash,
        candidates=candidates,
        blocked_reasons=blocked_reasons,
    )


def write_general_agent_promotion_terminal_certificate_candidates(
    plan: TerminalCertificateCandidatePlan,
    output_path: Path,
) -> Path:
    """Write one terminal certificate candidate set artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_general_agent_promotion_terminal_certificate_candidates(
    plan: TerminalCertificateCandidatePlan | dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate one terminal certificate candidate set against its schema."""
    schema = _load_schema(schema_path)
    payload = plan.as_dict() if isinstance(plan, TerminalCertificateCandidatePlan) else plan
    return tuple(_validate_schema_instance(schema, payload))


def _path_label(path: Path) -> str:
    """Return a terminal-candidate path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _candidate_from_gate_action(action: dict[str, Any]) -> TerminalCertificateCandidate:
    candidate_id = _field_text(action, "certificate_candidate_id", "")
    if not candidate_id:
        candidate_id = _candidate_id(_field_text(action, "source_action_id", "unknown"))
    return TerminalCertificateCandidate(
        candidate_id=candidate_id,
        source_gate_item_id=_field_text(action, "gate_item_id", "unknown-gate-item"),
        source_queue_item_id=_field_text(action, "source_queue_item_id", "unknown-queue-item"),
        source_action_id=_field_text(action, "source_action_id", "unknown-action"),
        source_plan_type=_field_text(action, "source_plan_type", "adapter"),
        terminal_gate_status=_field_text(action, "terminal_gate_status", "admitted_runnable"),
        approval_ref_present=action.get("approval_ref_present") is True,
        approval_ref=_optional_text(action.get("approval_ref")),
        evidence_required=_string_tuple(action.get("evidence_required", ())),
        receipt_validator=_field_text(action, "receipt_validator", "not_declared"),
    )


def _candidate_plan(
    *,
    gate_path: Path,
    generated_at: str,
    gate: dict[str, Any],
    gate_hash: str,
    candidates: tuple[TerminalCertificateCandidate, ...],
    blocked_reasons: tuple[str, ...],
) -> TerminalCertificateCandidatePlan:
    gate_action_count = _gate_action_count(gate)
    candidate_material = {
        "generated_at": generated_at,
        "gate_hash": gate_hash,
        "candidates": [candidate.as_dict() for candidate in candidates],
        "blocked_reasons": list(blocked_reasons),
    }
    candidate_digest = _stable_hash(candidate_material)
    return TerminalCertificateCandidatePlan(
        schema_version=1,
        candidate_set_id=f"general-agent-promotion-terminal-certificate-candidates-{candidate_digest[:16]}",
        generated_at=generated_at,
        source_gate_path=_path_label(gate_path),
        source_gate_id=_field_text(gate, "gate_id", "invalid-terminal-certificate-gate"),
        ready_for_candidate_review=bool(candidates),
        ready_for_terminal_certificate_minting=False,
        gate_action_count=gate_action_count,
        candidate_count=len(candidates),
        skipped_gate_action_count=max(gate_action_count - len(candidates), 0),
        blocked_gate_action_count=_int_field(gate, "blocked_action_count"),
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        candidates=candidates,
        metadata={
            "candidate_plan_is_not_execution": True,
            "terminal_certificates_minted": False,
            "secret_values_serialized": False,
            "source_gate_ready": gate.get("ready_for_terminal_certificate") is True,
            "source_gate_hash": gate_hash,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
            "terminal_certificate_gate_schema_id": TERMINAL_GATE_SCHEMA_ID,
        },
    )


def _is_admitted_gate_action(action: dict[str, Any]) -> bool:
    return (
        action.get("terminal_gate_status") in ADMITTED_GATE_STATUSES
        and isinstance(action.get("certificate_candidate_id"), str)
        and bool(str(action.get("certificate_candidate_id", "")).strip())
    )


def _gate_actions(gate: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    actions = gate.get("actions", ())
    if not isinstance(actions, list):
        return ()
    return tuple(action for action in actions if isinstance(action, dict))


def _gate_action_count(gate: dict[str, Any]) -> int:
    action_count = gate.get("action_count")
    if isinstance(action_count, int) and action_count >= 0:
        return action_count
    return len(_gate_actions(gate))


def _int_field(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    return value if isinstance(value, int) and value >= 0 else 0


def _field_text(payload: dict[str, Any], field_name: str, fallback: str) -> str:
    value = str(payload.get(field_name, "")).strip()
    return value or fallback


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _candidate_id(source_action_id: str) -> str:
    digest = _stable_hash({"source_action_id": source_action_id})
    return f"terminal-certificate-candidate-{digest[:16]}"


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse terminal certificate candidate planner arguments."""
    parser = argparse.ArgumentParser(description="Plan terminal certificate candidates from a terminal gate.")
    parser.add_argument("--gate", default=str(DEFAULT_TERMINAL_GATE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-candidates", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal certificate candidate planning."""
    args = parse_args(argv)
    plan = plan_general_agent_promotion_terminal_certificate_candidates(
        gate_path=Path(args.gate),
        generated_at=args.generated_at,
    )
    schema_errors = validate_general_agent_promotion_terminal_certificate_candidates(plan, Path(args.schema))
    write_general_agent_promotion_terminal_certificate_candidates(plan, Path(args.output))
    payload = plan.as_dict() | {"schema_valid": not schema_errors, "schema_errors": list(schema_errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif schema_errors:
        for error in schema_errors:
            print(f"error: {error}")
    else:
        print(
            "GENERAL AGENT PROMOTION TERMINAL CERTIFICATE CANDIDATES WRITTEN "
            f"candidates={plan.candidate_count} minting={plan.ready_for_terminal_certificate_minting}"
        )
    if schema_errors and args.strict:
        return 2
    if args.require_candidates and not plan.ready_for_candidate_review:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
