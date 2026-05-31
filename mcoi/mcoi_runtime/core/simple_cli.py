"""CLI front door for simple governed platform actions.

Purpose: provide a small, readable command surface for users who only need to
check whether a task is ready, needs review, or is blocked.
Governance scope: command-line usability projection only; checks execute
through SimplePlatform and the MVK governance gate.
Dependencies: argparse, json, and simple platform facade.
Invariants: every command returns a governed outcome and failures are reported
with explicit causal context.
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .invariants import RuntimeCoreInvariantError
from .simple_platform import SimpleActionRequest, SimplePlatform, SimpleTaskRequest, SimpleWorkflowRequest
from .simple_platform_api import SimplePlatformRuntime

SIMPLE_ACTION_VOCABULARY = frozenset(("view", "change", "send", "verify"))


def build_parser() -> argparse.ArgumentParser:
    """Build the simple platform parser."""

    parser = argparse.ArgumentParser(
        prog="mullu",
        description="Simple governed platform actions",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Check a task before continuing")
    check_parser.add_argument("--goal", required=True, help="What the user wants to accomplish")
    check_parser.add_argument(
        "--action",
        required=True,
        choices=("view", "change", "send", "verify"),
        help="Plain action type",
    )
    check_parser.add_argument("--target", required=True, help="File, message, or artifact target")
    check_parser.add_argument("--allowed-area", required=True, help="Area the task is allowed to touch")
    check_parser.add_argument("--actor-id", default="local-user", help="User or surface checking the task")
    check_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    task_parser = subparsers.add_parser("task", help="Check a common task without choosing action or scope")
    task_parser.add_argument(
        "task",
        choices=("review-docs", "update-docs", "notify-support", "verify-artifact"),
        help="Common task template",
    )
    task_parser.add_argument("--target", help="File, message, or artifact target")
    task_parser.add_argument("--goal", default="", help="Optional custom goal text")
    task_parser.add_argument("--actor-id", default="local-user", help="User or surface checking the task")
    task_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    tasks_parser = subparsers.add_parser("tasks", help="List common task templates")
    tasks_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    actions_parser = subparsers.add_parser("actions", help="List plain action types")
    actions_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    workflow_parser = subparsers.add_parser("workflow", help="Check a common workflow")
    workflow_parser.add_argument(
        "workflow",
        choices=("docs-update", "support-notice", "artifact-review"),
        help="Common workflow template",
    )
    workflow_parser.add_argument("--target", help="File, message, or artifact target")
    workflow_parser.add_argument("--goal", default="", help="Optional custom goal text")
    workflow_parser.add_argument("--actor-id", default="local-user", help="User or surface checking the workflow")
    workflow_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    workflows_parser = subparsers.add_parser("workflows", help="List common workflow templates")
    workflows_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")

    start_parser = subparsers.add_parser("start", help="Show the simple platform home screen")
    start_parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one simple platform command."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "start":
        home = SimplePlatform.simple_home().to_dict()
        if args.json:
            print(json.dumps(_envelope(True, "ready", {"home": home}), sort_keys=True, separators=(",", ":")))
        else:
            print(_start_text(home))
        return 0
    if args.command == "check":
        check = SimplePlatform().check_action(
            SimpleActionRequest(
                goal=args.goal,
                action=args.action,
                target=args.target,
                allowed_area=args.allowed_area,
                actor_id=args.actor_id,
            )
        )
        if args.json:
            print(
                json.dumps(
                    _envelope(check.ok_to_continue, check.outcome, check.to_dict()),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(_readable_check(check.to_dict()))
        return 0 if check.outcome == "ready" else 2
    if args.command == "task":
        check = SimplePlatform().check_task(
            SimpleTaskRequest(
                task=args.task.replace("-", "_"),
                target=args.target or "",
                goal=args.goal,
                actor_id=args.actor_id,
            )
        )
        if args.json:
            print(
                json.dumps(
                    _envelope(check.ok_to_continue, check.outcome, check.to_dict()),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(_readable_check(check.to_dict()))
        return 0 if check.outcome == "ready" else 2
    if args.command == "tasks":
        templates = _validated_task_templates([template.to_dict() for template in SimplePlatform.task_templates()])
        if args.json:
            print(json.dumps(_envelope(True, "listed", {"tasks": templates}), sort_keys=True, separators=(",", ":")))
        else:
            print(_readable_tasks(templates))
        return 0
    if args.command == "actions":
        actions = _validated_actions(SimplePlatformRuntime().action_menu().to_dict()["payload"]["actions"])
        if args.json:
            print(json.dumps(_envelope(True, "listed", {"actions": actions}), sort_keys=True, separators=(",", ":")))
        else:
            print(_readable_actions(actions))
        return 0
    if args.command == "workflow":
        plan = SimplePlatform().check_workflow(
            SimpleWorkflowRequest(
                workflow=args.workflow.replace("-", "_"),
                target=args.target or "",
                goal=args.goal,
                actor_id=args.actor_id,
            )
        )
        if args.json:
            print(
                json.dumps(
                    _envelope(plan.ok_to_continue, plan.outcome, plan.to_dict()),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        else:
            print(_readable_workflow(plan.to_dict()))
        return 0 if plan.outcome == "ready" else 2
    if args.command == "workflows":
        templates = _validated_workflow_templates([template.to_dict() for template in SimplePlatform.workflow_templates()])
        if args.json:
            print(json.dumps(_envelope(True, "listed", {"workflows": templates}), sort_keys=True, separators=(",", ":")))
        else:
            print(_readable_workflows(templates))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 1


def guarded_main(argv: Sequence[str] | None = None) -> int:
    """Run main while converting failures into governed output."""

    try:
        return main(argv)
    except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps(_envelope(False, "rejected", {}, error=str(exc)), sort_keys=True, separators=(",", ":")))
        return 1


def _readable_check(value: dict[str, object]) -> str:
    lines = [
        f"Outcome: {value['title']}",
        f"Message: {value['message']}",
        f"Next: {value['next_step']}",
        f"Proof: {value['proof_stamp_ref']}",
    ]
    blocked = value.get("blocked_reasons")
    review = value.get("review_reasons")
    if isinstance(blocked, list) and blocked:
        lines.append("Blocked reasons:")
        lines.extend(f"- {item}" for item in blocked)
    if isinstance(review, list) and review:
        lines.append("Review reasons:")
        lines.extend(f"- {item}" for item in review)
    return "\n".join(lines)


def _readable_tasks(templates: object) -> str:
    lines = ["Common tasks:"]
    for template in _validated_task_templates(templates):
        task_name = template["task"].replace("_", "-")
        target_hint = " --target <target>" if not template["default_target"] else ""
        lines.append(f"- {task_name}: {template['label']}")
        lines.append(f"  command: mullu task {task_name}{target_hint}")
    return "\n".join(lines)


def _validated_task_templates(templates: object) -> list[dict[str, str]]:
    if not isinstance(templates, list):
        raise RuntimeCoreInvariantError("simple task catalog must be a list")
    validated: list[dict[str, str]] = []
    for template in templates:
        if not isinstance(template, dict):
            raise RuntimeCoreInvariantError("simple task catalog item must be an object")
        validated.append(
            {
                "task": _catalog_text(template, "task catalog item", "task"),
                "label": _catalog_text(template, "task catalog item", "label"),
                "default_goal": _catalog_text(template, "task catalog item", "default_goal"),
                "action": _catalog_text(template, "task catalog item", "action"),
                "allowed_area": _catalog_text(template, "task catalog item", "allowed_area"),
                "default_target": _catalog_text(template, "task catalog item", "default_target", allow_empty=True),
            }
        )
    return validated


def _readable_actions(actions: object) -> str:
    lines = ["Plain actions:"]
    for action in _validated_actions(actions):
        lines.append(f"- {action['action']}: {action['label']}")
        lines.append(f"  purpose: {action['purpose']}")
    return "\n".join(lines)


def _validated_actions(actions: object) -> list[dict[str, str]]:
    if not isinstance(actions, list):
        raise RuntimeCoreInvariantError("simple action menu must be a list")
    validated: list[dict[str, str]] = []
    seen_actions: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            raise RuntimeCoreInvariantError("simple action menu item must be an object")
        action_id = _action_menu_text(action, "action")
        if action_id not in SIMPLE_ACTION_VOCABULARY:
            raise RuntimeCoreInvariantError("simple action menu item action is outside the governed vocabulary")
        if action_id in seen_actions:
            raise RuntimeCoreInvariantError("simple action menu item action must be unique")
        seen_actions.add(action_id)
        validated.append(
            {
                "action": action_id,
                "label": _action_menu_text(action, "label"),
                "purpose": _action_menu_text(action, "purpose"),
            }
        )
    return validated


def _action_menu_text(action: dict[object, object], field_name: str) -> str:
    return _catalog_text(action, "action menu item", field_name)


def _readable_workflow(value: dict[str, object]) -> str:
    lines = [
        f"Outcome: {value['title']}",
        f"Message: {value['message']}",
        f"Next: {value['next_step']}",
        f"Steps: {value['ready_count']} ready, {value['review_count']} review, {value['blocked_count']} blocked",
    ]
    checks = value.get("checks")
    if isinstance(checks, list):
        for index, check in enumerate(checks, start=1):
            if isinstance(check, dict):
                lines.append(f"- Step {index}: {check.get('title', 'Unknown')} - {check.get('next_step', '')}")
    return "\n".join(lines)


def _readable_workflows(templates: object) -> str:
    lines = ["Common workflows:"]
    for template in _validated_workflow_templates(templates):
        workflow_name = template["workflow"].replace("_", "-")
        target_hint = " --target <target>" if template["target_required"] else ""
        lines.append(f"- {workflow_name}: {template['label']}")
        lines.append(f"  command: mullu workflow {workflow_name}{target_hint}")
    return "\n".join(lines)


def _validated_workflow_templates(templates: object) -> list[dict[str, object]]:
    if not isinstance(templates, list):
        raise RuntimeCoreInvariantError("simple workflow catalog must be a list")
    validated: list[dict[str, object]] = []
    for template in templates:
        if not isinstance(template, dict):
            raise RuntimeCoreInvariantError("simple workflow catalog item must be an object")
        validated.append(
            {
                "workflow": _catalog_text(template, "workflow catalog item", "workflow"),
                "label": _catalog_text(template, "workflow catalog item", "label"),
                "default_goal": _catalog_text(template, "workflow catalog item", "default_goal"),
                "tasks": _catalog_text_list(template, "workflow catalog item", "tasks"),
                "target_required": _catalog_bool(template, "workflow catalog item", "target_required"),
                "default_target": _catalog_text(template, "workflow catalog item", "default_target", allow_empty=True),
            }
        )
    return validated


def _catalog_text(
    item: dict[object, object],
    item_name: str,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = item.get(field_name)
    if not isinstance(value, str):
        raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} must be text")
    if not allow_empty and not value.strip():
        raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} must be non-empty text")
    if value != value.strip():
        raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} must be trimmed text")
    return value


def _catalog_bool(item: dict[object, object], item_name: str, field_name: str) -> bool:
    value = item.get(field_name)
    if not isinstance(value, bool):
        raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} must be boolean")
    return value


def _catalog_text_list(item: dict[object, object], item_name: str, field_name: str) -> list[str]:
    value = item.get(field_name)
    if not isinstance(value, list):
        raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} must be a list")
    values: list[str] = []
    for member in value:
        if not isinstance(member, str):
            raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} item must be text")
        if not member.strip():
            raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} item must be non-empty text")
        if member != member.strip():
            raise RuntimeCoreInvariantError(f"simple {item_name} {field_name} item must be trimmed text")
        values.append(member)
    return values


def _start_text(home: dict[str, object]) -> str:
    lines = [
        str(home["title"]),
        str(home["message"]),
        f"Next: {home['next_action']}",
        "Recommended path:",
    ]
    for choice in home["choices"]:
        if isinstance(choice, dict):
            lines.append(f"- {choice['label']}: {choice['command']}")
    lines.extend(
        (
            "Common tasks: review-docs, update-docs, notify-support, verify-artifact",
            "Common workflows: docs-update, support-notice, artifact-review",
            "Actions: view, change, send, verify",
            "Outcomes: Ready, Needs review, Blocked",
        )
    )
    return "\n".join(lines)


def _envelope(ok: bool, status: str, payload: dict[str, object], *, error: str = "") -> dict[str, object]:
    return {
        "governed": True,
        "ok": ok,
        "status": status,
        "payload": payload,
        "error": error,
    }


if __name__ == "__main__":
    raise SystemExit(guarded_main())
