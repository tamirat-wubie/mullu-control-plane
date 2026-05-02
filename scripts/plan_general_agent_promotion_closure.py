#!/usr/bin/env python3
"""Plan full general-agent promotion closure.

Purpose: combine adapter and deployment closure plans into one deterministic
operator-facing promotion plan.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: adapter closure plan, deployment publication closure plan, and
general-agent promotion readiness artifact.
Invariants:
  - Aggregation never claims production readiness.
  - Approval-required actions remain approval-required.
  - Source plan blockers and action counts remain traceable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_READINESS = REPO_ROOT / ".change_assurance" / "general_agent_promotion_readiness.json"
DEFAULT_ADAPTER_PLAN = REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan.json"
DEFAULT_DEPLOYMENT_PLAN = REPO_ROOT / ".change_assurance" / "deployment_publication_closure_plan.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_closure_plan.json"


@dataclass(frozen=True, slots=True)
class PromotionClosurePlan:
    """Combined closure plan for production general-agent promotion."""

    plan_id: str
    readiness_level: str
    source_ready: bool
    total_action_count: int
    approval_required_action_count: int
    source_plans: tuple[str, ...]
    blockers: tuple[str, ...]
    actions: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready closure plan."""
        return {
            "plan_id": self.plan_id,
            "readiness_level": self.readiness_level,
            "source_ready": self.source_ready,
            "total_action_count": self.total_action_count,
            "approval_required_action_count": self.approval_required_action_count,
            "source_plans": list(self.source_plans),
            "blockers": list(self.blockers),
            "actions": list(self.actions),
        }


def plan_general_agent_promotion_closure(
    *,
    readiness_path: Path = DEFAULT_READINESS,
    adapter_plan_path: Path = DEFAULT_ADAPTER_PLAN,
    deployment_plan_path: Path = DEFAULT_DEPLOYMENT_PLAN,
) -> PromotionClosurePlan:
    """Combine current closure plans into one production-promotion plan."""
    readiness = _load_json_object(readiness_path, "promotion readiness")
    adapter_plan = _load_json_object(adapter_plan_path, "adapter closure plan")
    deployment_plan = _load_json_object(deployment_plan_path, "deployment publication closure plan")
    actions = tuple(
        _tag_action(action, source="adapter")
        for action in _action_items(adapter_plan)
    ) + tuple(
        _tag_action(action, source="deployment")
        for action in _action_items(deployment_plan)
    )
    blockers = tuple(
        dict.fromkeys(
            [
                *[str(blocker) for blocker in readiness.get("blockers", ())],
                *[str(blocker) for blocker in adapter_plan.get("blockers", ())],
                *[str(blocker) for blocker in deployment_plan.get("blockers", ())],
            ]
        )
    )
    approval_required_count = sum(1 for action in actions if action.get("approval_required") is True)
    plan_material = {
        "readiness_level": str(readiness.get("readiness_level", "unknown")),
        "source_ready": readiness.get("ready") is True,
        "source_plan_ids": (
            str(adapter_plan.get("plan_id", "")),
            str(deployment_plan.get("plan_id", "")),
        ),
        "blockers": blockers,
        "actions": actions,
    }
    plan_digest = hashlib.sha256(
        json.dumps(plan_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PromotionClosurePlan(
        plan_id=f"general-agent-promotion-closure-plan-{plan_digest[:16]}",
        readiness_level=str(readiness.get("readiness_level", "unknown")),
        source_ready=readiness.get("ready") is True,
        total_action_count=len(actions),
        approval_required_action_count=approval_required_count,
        source_plans=(str(adapter_plan_path), str(deployment_plan_path)),
        blockers=blockers,
        actions=actions,
    )


def write_general_agent_promotion_closure_plan(
    plan: PromotionClosurePlan,
    output_path: Path,
) -> Path:
    """Write one deterministic general-agent promotion closure plan."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _action_items(plan: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    actions = plan.get("actions", ())
    if not isinstance(actions, list):
        raise ValueError("source plan actions must be a list")
    return tuple(action for action in actions if isinstance(action, dict))


def _tag_action(action: dict[str, Any], *, source: str) -> dict[str, Any]:
    tagged = dict(action)
    tagged["source_plan_type"] = source
    return tagged


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion closure plan arguments."""
    parser = argparse.ArgumentParser(description="Plan full general-agent promotion closure.")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--adapter-plan", default=str(DEFAULT_ADAPTER_PLAN))
    parser.add_argument("--deployment-plan", default=str(DEFAULT_DEPLOYMENT_PLAN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for full promotion closure planning."""
    args = parse_args(argv)
    plan = plan_general_agent_promotion_closure(
        readiness_path=Path(args.readiness),
        adapter_plan_path=Path(args.adapter_plan),
        deployment_plan_path=Path(args.deployment_plan),
    )
    write_general_agent_promotion_closure_plan(plan, Path(args.output))
    if args.json:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    elif plan.total_action_count:
        print(
            "GENERAL AGENT PROMOTION CLOSURE PLAN WRITTEN "
            f"actions={plan.total_action_count} approvals={plan.approval_required_action_count}"
        )
    else:
        print(f"GENERAL AGENT PROMOTION CLOSURE PLAN EMPTY plan_id={plan.plan_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
