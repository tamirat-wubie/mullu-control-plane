#!/usr/bin/env python3
"""Plan full general-agent promotion closure.

Purpose: combine adapter and deployment closure plans into one deterministic
operator-facing promotion plan, with optional activation-blocked improvement
portfolio actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: adapter closure plan, deployment publication closure plan,
optional capability improvement portfolio, and general-agent promotion
readiness artifact.
Invariants:
  - Aggregation never claims production readiness.
  - Approval-required actions remain approval-required.
  - Source plan blockers and action counts remain traceable.
  - Improvement portfolio actions remain operator review steps, not execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_READINESS = REPO_ROOT / ".change_assurance" / "general_agent_promotion_readiness.json"
DEFAULT_ADAPTER_PLAN = REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan.json"
DEFAULT_DEPLOYMENT_PLAN = REPO_ROOT / ".change_assurance" / "deployment_publication_closure_plan.json"
DEFAULT_PORTFOLIO_PLAN = REPO_ROOT / ".change_assurance" / "capability_improvement_portfolio.json"
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
    portfolio_plan_path: Path | None = None,
    platform_system: Callable[[], str] | None = None,
) -> PromotionClosurePlan:
    """Combine current closure plans into one production-promotion plan."""
    readiness = _load_json_object(readiness_path, "promotion readiness")
    adapter_plan = _load_json_object(adapter_plan_path, "adapter closure plan")
    deployment_plan = _load_json_object(deployment_plan_path, "deployment publication closure plan")
    portfolio_plan = (
        _load_json_object(portfolio_plan_path, "capability improvement portfolio")
        if portfolio_plan_path is not None
        else None
    )
    host_platform = platform_system or platform.system
    actions = tuple(
        _tag_action(action, source="adapter", platform_system=host_platform)
        for action in _action_items(adapter_plan)
    ) + tuple(
        _tag_action(action, source="deployment", platform_system=host_platform)
        for action in _action_items(deployment_plan)
    ) + tuple(
        portfolio_closure_action
        for portfolio_closure_action in _portfolio_actions(portfolio_plan)
    )
    blockers = tuple(
        dict.fromkeys(
            [
                *[str(blocker) for blocker in readiness.get("blockers", ())],
                *[str(blocker) for blocker in adapter_plan.get("blockers", ())],
                *[str(blocker) for blocker in deployment_plan.get("blockers", ())],
                *[str(blocker) for blocker in (portfolio_plan or {}).get("blocked_reasons", ())],
            ]
        )
    )
    source_plan_ids = [
        str(adapter_plan.get("plan_id", "")),
        str(deployment_plan.get("plan_id", "")),
    ]
    source_plan_paths = [_path_label(adapter_plan_path), _path_label(deployment_plan_path)]
    if portfolio_plan_path is not None:
        source_plan_ids.append(str((portfolio_plan or {}).get("portfolio_id", "")))
        source_plan_paths.append(_path_label(portfolio_plan_path))
    approval_required_count = sum(1 for action in actions if action.get("approval_required") is True)
    plan_material = {
        "readiness_level": str(readiness.get("readiness_level", "unknown")),
        "source_ready": readiness.get("ready") is True,
        "source_plan_ids": tuple(source_plan_ids),
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
        source_plans=tuple(source_plan_paths),
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


def _tag_action(
    action: dict[str, Any],
    *,
    source: str,
    platform_system: Callable[[], str],
) -> dict[str, Any]:
    tagged = dict(action)
    tagged["source_plan_type"] = source
    if source == "adapter" and tagged.get("blocker") == "browser_live_evidence_missing":
        tagged["execution_environment"] = _browser_live_evidence_execution_environment(
            platform_system=platform_system
        )
    return tagged


def _browser_live_evidence_execution_environment(
    *,
    platform_system: Callable[[], str],
) -> dict[str, Any]:
    current_host_os = str(platform_system()).strip() or "unknown"
    return {
        "required_host_os": "Linux",
        "current_host_os": current_host_os,
        "current_environment_ready": current_host_os.lower() == "linux",
        "blocker_if_unmet": "browser_sandbox_runner_linux_only",
        "requirements": [
            "linux_host",
            "rootless_docker",
            "no_workspace_changes",
            "browser_sandbox_evidence_validation",
        ],
    }


def _portfolio_actions(portfolio_plan: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not portfolio_plan:
        return ()
    plans = portfolio_plan.get("plans", ())
    if not isinstance(plans, list):
        raise ValueError("capability improvement portfolio plans must be a list")
    portfolio_hash = str(portfolio_plan.get("portfolio_hash", "")).strip()
    portfolio_id = str(portfolio_plan.get("portfolio_id", "")).strip()
    actions: list[dict[str, Any]] = []
    for index, plan in enumerate(plans):
        if not isinstance(plan, dict):
            raise ValueError(f"capability improvement portfolio plan {index} must be an object")
        capability_id = str(plan.get("capability_id", "")).strip()
        if not capability_id:
            raise ValueError(f"capability improvement portfolio plan {index} missing capability_id")
        diagnosis = plan.get("diagnosis", {})
        candidate = plan.get("candidate", {})
        health_signal = plan.get("health_signal", {})
        if not isinstance(diagnosis, dict) or not isinstance(candidate, dict) or not isinstance(health_signal, dict):
            raise ValueError(f"capability improvement portfolio plan {index} shape invalid")
        plan_id = str(plan.get("plan_id", "")).strip()
        action_id = f"capability-improvement-{_safe_id(capability_id)}-{_safe_id(plan_id)[-16:]}"
        evidence_required = tuple(
            dict.fromkeys(
                [
                    *[str(ref) for ref in health_signal.get("evidence_refs", ()) if str(ref).strip()],
                    *[str(ref) for ref in diagnosis.get("evidence_refs", ()) if str(ref).strip()],
                    *[str(ref) for ref in plan.get("blocked_reasons", ()) if str(ref).strip()],
                ]
            )
        )
        actions.append(
            {
                "action_id": action_id,
                "action_type": "capability-improvement",
                "blocker": f"capability_improvement_required:{capability_id}",
                "command": f"Review activation-blocked improvement plan {plan_id} for {capability_id}.",
                "verification_command": (
                    "python -m pytest tests/test_gateway/test_autonomous_capability_upgrade.py "
                    "tests/test_gateway/test_operator_capability_console.py -q"
                ),
                "receipt_validator": f"capability_improvement_portfolio:{portfolio_hash}:{plan_id}",
                "evidence_required": list(evidence_required),
                "risk_level": str(diagnosis.get("severity", "medium")),
                "approval_required": True,
                "source_plan_type": "portfolio",
            }
        )
    if portfolio_id and not actions:
        raise ValueError("capability improvement portfolio has no plans")
    return tuple(actions)


def _safe_id(value: str) -> str:
    normalized = "".join(char if char.isalnum() else "-" for char in value).strip("-").lower()
    return normalized or "unknown"


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    try:
        payload = _loads_strict_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _path_label(path: Path) -> str:
    """Return a promotion-plan path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion closure plan arguments."""
    parser = argparse.ArgumentParser(description="Plan full general-agent promotion closure.")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--adapter-plan", default=str(DEFAULT_ADAPTER_PLAN))
    parser.add_argument("--deployment-plan", default=str(DEFAULT_DEPLOYMENT_PLAN))
    parser.add_argument("--portfolio-plan", default="")
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
        portfolio_plan_path=Path(args.portfolio_plan) if str(args.portfolio_plan).strip() else None,
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
