#!/usr/bin/env python3
"""Emit a deterministic pilot proof-slice witness.

Purpose: exercise the gateway causal-closure path with one tenant-scoped web
message and write a machine-readable witness for pilot deployment reflection.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway router, command spine, causal closure kernel.
Invariants:
  - The pilot command enters through GatewayRouter, not a private shortcut.
  - A success witness requires terminal closure certification.
  - The emitted witness records command, response, proof, and event evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

import gateway.command_spine as command_spine_module  # noqa: E402
from gateway.approval import ApprovalRouter  # noqa: E402
from gateway.command_spine import CommandLedger, CommandState, InMemoryCommandLedgerStore  # noqa: E402
from gateway.router import GatewayMessage, GatewayRouter, TenantMapping  # noqa: E402

DEFAULT_OUTPUT_PATH = Path(".change_assurance") / "pilot_proof_slice_witness.json"
DEFAULT_CLOCK_VALUE = "2026-04-24T12:00:00+00:00"
DEFAULT_TENANT_ID = "pilot-tenant"
DEFAULT_IDENTITY_ID = "pilot-operator"
DEFAULT_CHANNEL = "web"
DEFAULT_SENDER_ID = "pilot-web-user"
DEFAULT_CONVERSATION_ID = "pilot-conversation"
DEFAULT_MESSAGE_ID = "pilot-message-1"
DEFAULT_PROMPT = "Produce a governed pilot readiness summary."
DEFAULT_RESPONSE = "Pilot proof slice completed with governed closure."
SCRIPT_VERSION = "pilot-proof-slice.v0.1"


@dataclass(frozen=True, slots=True)
class PilotProofSliceConfig:
    """Input contract for one deterministic pilot proof-slice run."""

    tenant_id: str = DEFAULT_TENANT_ID
    identity_id: str = DEFAULT_IDENTITY_ID
    channel: str = DEFAULT_CHANNEL
    sender_id: str = DEFAULT_SENDER_ID
    conversation_id: str = DEFAULT_CONVERSATION_ID
    message_id: str = DEFAULT_MESSAGE_ID
    prompt: str = DEFAULT_PROMPT
    response: str = DEFAULT_RESPONSE
    clock_value: str = DEFAULT_CLOCK_VALUE

    def __post_init__(self) -> None:
        for field_name, value in (
            ("tenant_id", self.tenant_id),
            ("identity_id", self.identity_id),
            ("channel", self.channel),
            ("sender_id", self.sender_id),
            ("conversation_id", self.conversation_id),
            ("message_id", self.message_id),
            ("prompt", self.prompt),
            ("response", self.response),
            ("clock_value", self.clock_value),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class _PilotSession:
    """Deterministic session fixture for local proof-slice execution."""

    response: str

    def llm(self, prompt: str, **_kwargs: Any) -> Mapping[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            return {"succeeded": False, "error": "empty prompt", "content": ""}
        return {"succeeded": True, "error": "", "content": self.response}

    def close(self) -> None:
        return None


@dataclass(slots=True)
class _PilotPlatform:
    """Deterministic platform fixture that preserves the GovernedSession contract."""

    response: str
    sessions_opened: int = 0

    def connect(self, *, identity_id: str, tenant_id: str) -> _PilotSession:
        if not identity_id.strip() or not tenant_id.strip():
            raise PermissionError("identity_id and tenant_id are required")
        self.sessions_opened += 1
        return _PilotSession(response=self.response)


@dataclass(frozen=True, slots=True)
class _StableUuid:
    """Small uuid4-compatible value object for deterministic pilot ids."""

    hex: str


def build_pilot_router(config: PilotProofSliceConfig) -> GatewayRouter:
    """Build the governed router used by the proof-slice run."""

    def clock() -> str:
        return config.clock_value

    router = GatewayRouter(
        platform=_PilotPlatform(response=config.response),
        clock=clock,
        approval_router=ApprovalRouter(clock=clock),
        command_ledger=CommandLedger(clock=clock, store=InMemoryCommandLedgerStore()),
    )
    router.register_tenant_mapping(
        TenantMapping(
            channel=config.channel,
            sender_id=config.sender_id,
            tenant_id=config.tenant_id,
            identity_id=config.identity_id,
        )
    )
    return router


def run_pilot_proof_slice(config: PilotProofSliceConfig) -> dict[str, Any]:
    """Execute one governed pilot command and return its witness."""
    original_uuid4 = command_spine_module.uuid4
    uuid_counter = 0

    def deterministic_uuid4() -> _StableUuid:
        nonlocal uuid_counter
        uuid_counter += 1
        return _StableUuid(
            _stable_hash(
                {
                    "script_version": SCRIPT_VERSION,
                    "tenant_id": config.tenant_id,
                    "identity_id": config.identity_id,
                    "message_id": config.message_id,
                    "counter": uuid_counter,
                }
            )[:32]
        )

    command_spine_module.uuid4 = deterministic_uuid4
    try:
        router = build_pilot_router(config)
        message = GatewayMessage(
            message_id=config.message_id,
            channel=config.channel,
            sender_id=config.sender_id,
            body=config.prompt,
            conversation_id=config.conversation_id,
            received_at=config.clock_value,
        )
        response = router.handle_message(message)
    finally:
        command_spine_module.uuid4 = original_uuid4

    metadata = dict(response.metadata)
    command_id = _required_string(metadata, "command_id")
    events = router._commands.events_for(command_id)
    terminal_certificate = _required_mapping(metadata, "terminal_certificate")
    event_states = [event.next_state.value for event in events]

    if CommandState.TERMINALLY_CERTIFIED.value not in event_states:
        raise RuntimeError("pilot proof slice did not reach terminal certification")
    if not bool(metadata.get("success_claim_allowed")):
        raise RuntimeError("pilot proof slice did not authorize a success claim")

    response_hash = _stable_hash(
        {
            "body": response.body,
            "command_id": command_id,
            "terminal_certificate_id": metadata.get("terminal_certificate_id", ""),
        }
    )
    witness = {
        "witness_id": _stable_hash(
            {
                "script_version": SCRIPT_VERSION,
                "command_id": command_id,
                "response_hash": response_hash,
            }
        ),
        "script_version": SCRIPT_VERSION,
        "generated_at": config.clock_value,
        "tenant_id": config.tenant_id,
        "identity_id": config.identity_id,
        "channel": config.channel,
        "message_id": config.message_id,
        "conversation_id": config.conversation_id,
        "command_id": command_id,
        "response_hash": response_hash,
        "response_body": response.body,
        "response_allowed": True,
        "success_claim_allowed": bool(metadata["success_claim_allowed"]),
        "terminal_certificate_id": metadata["terminal_certificate_id"],
        "terminal_disposition": terminal_certificate["disposition"],
        "terminal_evidence_refs": list(terminal_certificate["evidence_refs"]),
        "closure_memory_entry_id": _required_mapping(metadata, "closure_memory_entry")["entry_id"],
        "learning_admission_status": _required_mapping(metadata, "learning_admission")["status"],
        "claim_count": len(metadata.get("claims", ())),
        "evidence_count": len(metadata.get("evidence", ())),
        "event_count": len(events),
        "event_states": event_states,
        "latest_event_hash": events[-1].event_hash if events else "",
        "proof": {
            "terminal_certified": CommandState.TERMINALLY_CERTIFIED.value in event_states,
            "response_evidence_closed": CommandState.RESPONSE_EVIDENCE_CLOSED.value in event_states,
            "memory_promoted": CommandState.MEMORY_PROMOTED.value in event_states,
            "learning_decided": CommandState.LEARNING_DECIDED.value in event_states,
            "responded": event_states[-1] == CommandState.RESPONDED.value if event_states else False,
        },
    }
    _validate_witness(witness)
    return witness


def write_witness(witness: Mapping[str, Any], output_path: Path) -> Path:
    """Write the pilot witness as deterministic JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(witness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _required_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"witness source missing required string: {key}")
    return value


def _required_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise RuntimeError(f"witness source missing required mapping: {key}")
    return value


def _stable_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_witness(witness: Mapping[str, Any]) -> None:
    required_keys = (
        "witness_id",
        "command_id",
        "response_hash",
        "terminal_certificate_id",
        "terminal_disposition",
        "latest_event_hash",
    )
    missing = [key for key in required_keys if not witness.get(key)]
    if missing:
        raise RuntimeError(f"pilot witness missing required keys: {missing}")
    proof = _required_mapping(witness, "proof")
    failed = [key for key, value in proof.items() if value is not True]
    if failed:
        raise RuntimeError(f"pilot witness proof flags failed: {failed}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the pilot proof-slice CLI contract."""
    parser = argparse.ArgumentParser(description="Emit a governed pilot proof-slice witness.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--identity-id", default=DEFAULT_IDENTITY_ID)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--sender-id", default=DEFAULT_SENDER_ID)
    parser.add_argument("--conversation-id", default=DEFAULT_CONVERSATION_ID)
    parser.add_argument("--message-id", default=DEFAULT_MESSAGE_ID)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--response", default=DEFAULT_RESPONSE)
    parser.add_argument("--clock", default=DEFAULT_CLOCK_VALUE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for pilot proof-slice witness emission."""
    args = parse_args(argv)
    config = PilotProofSliceConfig(
        tenant_id=args.tenant_id,
        identity_id=args.identity_id,
        channel=args.channel,
        sender_id=args.sender_id,
        conversation_id=args.conversation_id,
        message_id=args.message_id,
        prompt=args.prompt,
        response=args.response,
        clock_value=args.clock,
    )
    witness = run_pilot_proof_slice(config)
    output_path = write_witness(witness, Path(args.output))
    print(f"pilot proof slice witness written: {output_path}")
    print(f"witness_id: {witness['witness_id']}")
    print(f"terminal_certificate_id: {witness['terminal_certificate_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
