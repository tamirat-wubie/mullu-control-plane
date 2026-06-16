#!/usr/bin/env python3
"""Collect a personal-assistant foundation evidence receipt.

Purpose: bind local console read-model, public console probe, and component
witness artifacts into one replayable no-effect evidence receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: checked-in personal-assistant evidence examples and JSON output.
Invariants:
  - Collection never calls connectors, providers, deployment routes, or workers.
  - The aggregate receipt is not execution authority and is not terminal closure.
  - Secret values and raw private payloads are never serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONSOLE_READ_MODEL = REPO_ROOT / "examples" / "personal_assistant_console_read_model.json"
DEFAULT_PUBLIC_CONSOLE_PROBE = REPO_ROOT / "examples" / "personal_assistant_public_console_probe_receipt.json"
DEFAULT_COMPONENT_WITNESS = REPO_ROOT / "examples" / "personal_assistant_component_witness_receipt.json"
DEFAULT_OUTPUT = REPO_ROOT / "examples" / "personal_assistant_foundation_evidence_receipt.json"

EVIDENCE_KINDS = ("console_read_model", "public_console_probe", "component_witness")
NO_EFFECT_FLAGS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "connector_mutation_allowed",
    "external_effect_allowed",
    "customer_readiness_claim_allowed",
    "nested_mind_live_activation_allowed",
)


def collect_personal_assistant_foundation_evidence(
    *,
    console_read_model_path: Path = DEFAULT_CONSOLE_READ_MODEL,
    public_console_probe_path: Path = DEFAULT_PUBLIC_CONSOLE_PROBE,
    component_witness_path: Path = DEFAULT_COMPONENT_WITNESS,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Collect one aggregate no-effect personal-assistant foundation receipt."""
    console = _read_json_object(console_read_model_path, "personal-assistant console read model")
    public_probe = _read_json_object(public_console_probe_path, "personal-assistant public console probe")
    component_witness = _read_json_object(component_witness_path, "personal-assistant component witness")
    generated_at = _format_utc(now_utc or datetime.now(UTC))

    console_verified = _console_read_model_verified(console)
    public_probe_verified = _public_console_probe_verified(public_probe)
    component_verified = _component_witness_verified(component_witness)
    effect_boundary = _aggregate_effect_boundary(console, public_probe, component_witness)
    no_effect_boundary_verified = not any(effect_boundary.values())
    foundation_evidence_closed = (
        console_verified and public_probe_verified and component_verified and no_effect_boundary_verified
    )
    proof_state = "Pass" if foundation_evidence_closed else "Fail"
    solver_outcome = "SolvedVerified" if foundation_evidence_closed else "AwaitingEvidence"

    receipt_without_id = {
        "schema_version": "personal_assistant.foundation_evidence_receipt.v1",
        "generated_at": generated_at,
        "proof_state": proof_state,
        "solver_outcome": solver_outcome,
        "governed": True,
        "receipt_is_not_execution_authority": True,
        "receipt_is_not_terminal_closure": True,
        "evidence_items": [
            {
                "item_id": "personal_assistant_console_read_model",
                "source_ref": _path_label(console_read_model_path),
                "evidence_kind": "console_read_model",
                "proof_state": "Pass" if console_verified else "Fail",
                "solver_outcome": "SolvedVerified" if console_verified else "AwaitingEvidence",
                "closed": console_verified,
                "no_effect_boundary_verified": _console_no_effect_boundary_verified(console),
            },
            {
                "item_id": "personal_assistant_public_console_probe",
                "source_ref": _path_label(public_console_probe_path),
                "evidence_kind": "public_console_probe",
                "proof_state": _bounded_outcome(public_probe.get("proof_state"), allowed={"Pass", "Fail"}),
                "solver_outcome": _bounded_outcome(
                    public_probe.get("solver_outcome"),
                    allowed={"SolvedVerified", "AwaitingEvidence"},
                ),
                "closed": _object(public_probe.get("summary")).get("probe_closed") is True,
                "no_effect_boundary_verified": _object(public_probe.get("summary")).get(
                    "no_effect_boundary_verified"
                )
                is True,
            },
            {
                "item_id": "personal_assistant_component_witness",
                "source_ref": _path_label(component_witness_path),
                "evidence_kind": "component_witness",
                "proof_state": _bounded_outcome(component_witness.get("proof_state"), allowed={"Pass", "Fail"}),
                "solver_outcome": _bounded_outcome(
                    component_witness.get("solver_outcome"),
                    allowed={"SolvedVerified", "AwaitingEvidence"},
                ),
                "closed": _object(component_witness.get("summary")).get("witness_closed") is True,
                "no_effect_boundary_verified": _object(component_witness.get("summary")).get(
                    "no_effect_boundary_verified"
                )
                is True,
            },
        ],
        "effect_boundary": effect_boundary,
        "summary": {
            "evidence_item_count": 3,
            "console_read_model_verified": console_verified,
            "public_console_probe_verified": public_probe_verified,
            "component_witness_verified": component_verified,
            "no_effect_boundary_verified": no_effect_boundary_verified,
            "foundation_evidence_closed": foundation_evidence_closed,
        },
        "lineage": {
            "accepted_deltas": [
                {
                    "delta_id": f"delta-personal-assistant-foundation-evidence-{generated_at[:10]}",
                    "reason": _lineage_reason(foundation_evidence_closed),
                    "logged_in_lineage": True,
                }
            ],
            "rejected_deltas": [],
        },
    }
    return {
        "receipt_id": _receipt_id(receipt_without_id),
        **receipt_without_id,
    }


def write_personal_assistant_foundation_evidence_receipt(
    receipt: Mapping[str, object],
    output_path: Path,
) -> Path:
    """Write one personal-assistant foundation evidence receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def _console_read_model_verified(console: Mapping[str, Any]) -> bool:
    lane_status = _object(console.get("lane_status"))
    assurance = _object(console.get("assurance"))
    return (
        console.get("console_id") == "personal_assistant_console_foundation"
        and console.get("status") == "foundation_read_only"
        and console.get("solver_outcome") == "SolvedVerified"
        and console.get("governed") is True
        and lane_status.get("lane_count") == 12
        and assurance.get("outcome") == "SolvedVerified"
        and assurance.get("ready_for_live_execution") is False
        and assurance.get("ready_for_customer_readiness_claim") is False
        and _console_no_effect_boundary_verified(console)
    )


def _console_no_effect_boundary_verified(console: Mapping[str, Any]) -> bool:
    lane_status = _object(console.get("lane_status"))
    effect_boundary = _object(console.get("effect_boundary"))
    private_payload_policy = _object(console.get("private_payload_policy"))
    return (
        all(lane_status.get(flag) is False for flag in NO_EFFECT_FLAGS)
        and effect_boundary.get("execution_allowed") is False
        and effect_boundary.get("live_connector_execution_allowed") is False
        and effect_boundary.get("public_readiness_claim_allowed") is False
        and effect_boundary.get("nested_mind_live_activation_allowed") is False
        and private_payload_policy.get("raw_private_payload_serialized") is False
        and private_payload_policy.get("secret_values_serialized") is False
    )


def _public_console_probe_verified(public_probe: Mapping[str, Any]) -> bool:
    summary = _object(public_probe.get("summary"))
    return (
        public_probe.get("proof_state") == "Pass"
        and public_probe.get("solver_outcome") == "SolvedVerified"
        and summary.get("probe_closed") is True
        and summary.get("console_read_model_verified") is True
        and summary.get("html_view_verified") is True
        and summary.get("no_effect_boundary_verified") is True
    )


def _component_witness_verified(component_witness: Mapping[str, Any]) -> bool:
    summary = _object(component_witness.get("summary"))
    return (
        component_witness.get("proof_state") == "Pass"
        and component_witness.get("solver_outcome") == "SolvedVerified"
        and summary.get("witness_closed") is True
        and summary.get("component_witness_verified") is True
        and summary.get("request_path_witness_verified") is True
        and summary.get("lifecycle_witness_verified") is True
        and summary.get("no_effect_boundary_verified") is True
    )


def _aggregate_effect_boundary(
    console: Mapping[str, Any],
    public_probe: Mapping[str, Any],
    component_witness: Mapping[str, Any],
) -> dict[str, bool]:
    console_effect = _object(console.get("effect_boundary"))
    console_lane = _object(console.get("lane_status"))
    public_effect = _object(public_probe.get("effect_boundary"))
    component_effect = _object(component_witness.get("effect_boundary"))
    private_payload_policy = _object(console.get("private_payload_policy"))
    return {
        "execution_allowed": _any_true(
            console_effect.get("execution_allowed"),
            console_lane.get("execution_allowed"),
            public_effect.get("execution_allowed"),
            component_effect.get("can_execute"),
        ),
        "live_connector_execution_allowed": _any_true(
            console_effect.get("live_connector_execution_allowed"),
            console_lane.get("live_connector_execution_allowed"),
            public_effect.get("live_connector_execution_allowed"),
            component_effect.get("live_connector_send_enabled"),
        ),
        "connector_mutation_allowed": _any_true(
            console_lane.get("connector_mutation_allowed"),
            public_effect.get("connector_mutation_allowed"),
            component_effect.get("can_mutate"),
            component_effect.get("can_call_connector"),
        ),
        "external_effect_allowed": _any_true(
            console_lane.get("external_effect_allowed"),
            public_effect.get("external_effect_allowed"),
            component_effect.get("can_send_external_message"),
        ),
        "customer_readiness_claim_allowed": _any_true(
            console_effect.get("public_readiness_claim_allowed"),
            console_lane.get("customer_readiness_claim_allowed"),
            public_effect.get("customer_readiness_claim_allowed"),
        ),
        "nested_mind_live_activation_allowed": _any_true(
            console_effect.get("nested_mind_live_activation_allowed"),
            console_lane.get("nested_mind_live_activation_allowed"),
            public_effect.get("nested_mind_live_activation_allowed"),
        ),
        "secret_values_serialized": _any_true(
            private_payload_policy.get("secret_values_serialized"),
            public_effect.get("secret_values_serialized"),
            component_effect.get("secret_values_serialized"),
        ),
        "raw_private_payloads_serialized": _any_true(
            private_payload_policy.get("raw_private_payload_serialized"),
            public_effect.get("raw_response_bodies_serialized"),
            component_effect.get("raw_private_connector_payloads_serialized"),
        ),
    }


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to read {label}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return parsed


def _object(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _any_true(*values: object) -> bool:
    return any(value is True for value in values)


def _bounded_outcome(value: object, *, allowed: set[str]) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    if "Fail" in allowed:
        return "Fail"
    return "AwaitingEvidence"


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _receipt_id(receipt_without_id: Mapping[str, object]) -> str:
    material = json.dumps(receipt_without_id, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"personal-assistant-foundation-evidence-{hashlib.sha256(material).hexdigest()[:16]}"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _lineage_reason(foundation_evidence_closed: bool) -> str:
    if foundation_evidence_closed:
        return "Recorded aggregate Personal Assistant foundation evidence while preserving no-effect authority."
    return "Recorded aggregate Personal Assistant foundation evidence and preserved AwaitingEvidence."


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant foundation evidence collection arguments."""
    parser = argparse.ArgumentParser(description="Collect personal-assistant foundation evidence.")
    parser.add_argument("--console-read-model", default=str(DEFAULT_CONSOLE_READ_MODEL))
    parser.add_argument("--public-console-probe", default=str(DEFAULT_PUBLIC_CONSOLE_PROBE))
    parser.add_argument("--component-witness", default=str(DEFAULT_COMPONENT_WITNESS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, now_utc: datetime | None = None) -> int:
    """CLI entry point for personal-assistant foundation evidence collection."""
    args = parse_args(argv)
    receipt = collect_personal_assistant_foundation_evidence(
        console_read_model_path=Path(args.console_read_model),
        public_console_probe_path=Path(args.public_console_probe),
        component_witness_path=Path(args.component_witness),
        now_utc=now_utc,
    )
    write_personal_assistant_foundation_evidence_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=False))
    else:
        print(f"personal-assistant foundation evidence outcome: {receipt['solver_outcome']}")
    return 0 if receipt["solver_outcome"] == "SolvedVerified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
