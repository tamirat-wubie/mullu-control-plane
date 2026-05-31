"""Purpose: build nested-mind record_observation plan/evidence JSON files.
Governance scope: offline operator preparation for live observation submission.
Dependencies: nested-mind observation submission contracts.
Invariants:
  - Performs no network calls and no nested-mind writes.
  - Produces only record_observation proposal payloads.
  - Plan/evidence hashes are deterministic and token-free.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = REPO_ROOT / "mcoi"
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.contracts import (  # noqa: E402
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindProposalEvidence,
    build_observation_proposal_payload,
    stable_json_hash,
)
from mcoi_runtime.core.invariants import stable_identifier  # noqa: E402
from mcoi_runtime.persistence._serialization import loads_strict_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build nested-mind record_observation plan/evidence JSON.")
    parser.add_argument("--mind-id", required=True)
    parser.add_argument("--observation-id", required=True)
    parser.add_argument("--observation", required=True, help="Path to bounded observation JSON object")
    parser.add_argument("--mullu-receipt-hash", required=True)
    parser.add_argument("--authority-receipt-hash", required=True)
    parser.add_argument("--plan-out", required=True)
    parser.add_argument("--evidence-out", required=True)
    parser.add_argument("--planned-at", default="", help="ISO timestamp override")
    args = parser.parse_args(argv)

    observation_value = _load_observation(Path(args.observation))
    planned_at = args.planned_at or _utc_now()
    observation_hash = stable_json_hash(observation_value)
    evidence_hash = stable_json_hash(
        {
            "mind_id": args.mind_id,
            "observation_hash": observation_hash,
            "mullu_receipt_hash": args.mullu_receipt_hash,
            "authority_receipt_hash": args.authority_receipt_hash,
        }
    )
    evidence = NestedMindProposalEvidence(
        evidence_id=stable_identifier(
            "nested-mind-proposal-evidence",
            {
                "mind_id": args.mind_id,
                "evidence_hash": evidence_hash,
                "mullu_receipt_hash": args.mullu_receipt_hash,
                "authority_receipt_hash": args.authority_receipt_hash,
            },
        ),
        mind_id=args.mind_id,
        evidence_hash=evidence_hash,
        mullu_receipt_hash=args.mullu_receipt_hash,
        authority_receipt_hash=args.authority_receipt_hash,
        metadata={"observation_hash": observation_hash},
    )
    proposal_payload = build_observation_proposal_payload(
        evidence,
        observation_id=args.observation_id,
        observation_hash=observation_hash,
        observation_value=observation_value,
    )
    payload_hash = stable_json_hash(proposal_payload)
    plan = NestedMindObservationProposalPlan(
        plan_id=stable_identifier(
            "nested-mind-observation-plan",
            {
                "evidence_id": evidence.evidence_id,
                "payload_hash": payload_hash,
                "planned_at": planned_at,
            },
        ),
        proposal_evidence_id=evidence.evidence_id,
        mind_id=evidence.mind_id,
        method="POST",
        target_route=f"/minds/{evidence.mind_id}/proposals",
        proposal_payload=proposal_payload,
        payload_hash=payload_hash,
        mullu_receipt_hash=evidence.mullu_receipt_hash,
        authority_receipt_hash=evidence.authority_receipt_hash,
        status=NestedMindObservationProposalPlanStatus.PLANNED,
        planned_at=planned_at,
    )
    _write_json(Path(args.evidence_out), evidence.to_json())
    _write_json(Path(args.plan_out), plan.to_json())
    print(
        json.dumps(
            {
                "status": "planned",
                "plan_id": plan.plan_id,
                "evidence_id": evidence.evidence_id,
                "payload_hash": plan.payload_hash,
                "observation_hash": observation_hash,
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
    return 0


def _load_observation(path: Path) -> Mapping[str, Any]:
    try:
        raw = loads_strict_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"failed to read {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse JSON from {path}") from exc
    except ValueError as exc:
        raise RuntimeError(f"failed to parse strict JSON from {path}") from exc
    if not isinstance(raw, Mapping):
        raise RuntimeError("observation must be a JSON object")
    _reject_forbidden_observation(raw)
    return raw


def _reject_forbidden_observation(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if "token" in key_text or "authorization" in key_text or "raw_response_body" in key_text:
                raise RuntimeError("observation contains forbidden sensitive field")
            _reject_forbidden_observation(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_observation(item)


def _write_json(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
