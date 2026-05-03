#!/usr/bin/env python3
"""Plan capability adapter closure actions.

Purpose: convert adapter evidence blockers into deterministic operator actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: .change_assurance/capability_adapter_evidence.json and live receipt scripts.
Invariants:
  - Planning does not claim closure or mutate adapter receipts.
  - Every blocker maps to an explicit action, dependency, credential, or evidence request.
  - Unknown blockers remain visible as manual-review actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE = REPO_ROOT / ".change_assurance" / "capability_adapter_evidence.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_adapter_closure_plan.json"


@dataclass(frozen=True, slots=True)
class AdapterClosureAction:
    """One deterministic action needed to close adapter evidence."""

    action_id: str
    adapter_id: str
    blocker: str
    action_type: str
    command: str
    evidence_required: tuple[str, ...]
    risk_level: str
    approval_required: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready closure action."""
        payload = asdict(self)
        payload["evidence_required"] = list(self.evidence_required)
        return payload


@dataclass(frozen=True, slots=True)
class AdapterClosurePlan:
    """Deterministic plan for closing adapter evidence blockers."""

    plan_id: str
    source_evidence_path: str
    source_ready: bool
    action_count: int
    blockers: tuple[str, ...]
    actions: tuple[AdapterClosureAction, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready closure plan."""
        return {
            "plan_id": self.plan_id,
            "source_evidence_path": self.source_evidence_path,
            "source_ready": self.source_ready,
            "action_count": self.action_count,
            "blockers": list(self.blockers),
            "actions": [action.as_dict() for action in self.actions],
        }


def plan_capability_adapter_closure(evidence_path: Path = DEFAULT_EVIDENCE) -> AdapterClosurePlan:
    """Build a deterministic closure plan from the adapter evidence report."""
    payload = _load_evidence(evidence_path)
    adapters = payload.get("adapters", ())
    blockers: list[str] = []
    actions: list[AdapterClosureAction] = []
    for adapter in adapters if isinstance(adapters, list) else ():
        if not isinstance(adapter, dict):
            continue
        adapter_id = str(adapter.get("adapter_id", "unknown.adapter"))
        for blocker in adapter.get("blockers", ()):
            blocker_text = str(blocker)
            blockers.append(blocker_text)
            actions.append(_action_for(adapter_id, blocker_text))
    if not actions:
        for blocker in payload.get("blockers", ()):
            blocker_text = str(blocker)
            blockers.append(blocker_text)
            actions.append(_action_for("unknown.adapter", blocker_text))
    unique_blockers = tuple(dict.fromkeys(blockers))
    unique_actions = tuple(_dedupe_actions(actions))
    plan_material = {
        "source_report_id": str(payload.get("report_id", "")),
        "source_ready": payload.get("ready") is True,
        "blockers": unique_blockers,
        "actions": [action.as_dict() for action in unique_actions],
    }
    plan_digest = hashlib.sha256(
        json.dumps(plan_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AdapterClosurePlan(
        plan_id=f"capability-adapter-closure-plan-{plan_digest[:16]}",
        source_evidence_path=str(evidence_path),
        source_ready=payload.get("ready") is True,
        action_count=len(unique_actions),
        blockers=unique_blockers,
        actions=unique_actions,
    )


def write_adapter_closure_plan(plan: AdapterClosurePlan, output_path: Path) -> Path:
    """Write one deterministic adapter closure plan."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _action_for(adapter_id: str, blocker: str) -> AdapterClosureAction:
    if blocker.startswith("browser_dependency_missing:"):
        return _dependency_action(
            adapter_id,
            blocker,
            "Install Playwright Python package and browser runtime in the adapter-worker image.",
            ("playwright_import_check", "browser_runtime_install_receipt"),
        )
    if blocker == "browser_live_evidence_missing":
        return _receipt_action(
            adapter_id,
            blocker,
            "python scripts/produce_capability_adapter_live_receipts.py --target browser --browser-sandbox-evidence <sandbox_receipt_json_path> --strict",
            ("browser_live_receipt.json", "sandbox_receipt_json_path"),
        )
    if blocker.startswith("document_dependency_missing:"):
        module_name = blocker.split(":", 1)[1]
        return _dependency_action(
            adapter_id,
            blocker,
            f"Install document parser dependency `{module_name}` in the document-worker image.",
            (f"{module_name}_import_check", "document_worker_build_receipt"),
        )
    if blocker == "document_live_evidence_missing":
        return _receipt_action(
            adapter_id,
            blocker,
            "python scripts/produce_capability_adapter_live_receipts.py --target document --strict",
            ("document_live_receipt.json", "production_parser_registry_receipt"),
        )
    if blocker.startswith("voice_dependency_missing:OPENAI_API_KEY"):
        return AdapterClosureAction(
            action_id=_action_id(adapter_id, blocker),
            adapter_id=adapter_id,
            blocker=blocker,
            action_type="credential",
            command="Set OPENAI_API_KEY only in the governed voice-worker secret store.",
            evidence_required=("secret_presence_attestation", "voice_worker_secret_binding"),
            risk_level="high",
            approval_required=True,
        )
    if blocker.startswith("voice_dependency_missing:"):
        return _dependency_action(
            adapter_id,
            blocker,
            "Install OpenAI provider client in the voice-worker image.",
            ("openai_import_check", "voice_worker_build_receipt"),
        )
    if blocker == "voice_live_evidence_missing":
        return _receipt_action(
            adapter_id,
            blocker,
            "python scripts/produce_capability_adapter_live_receipts.py --target voice --voice-audio-path <approved_audio_sample> --strict",
            ("voice_live_receipt.json", "approved_audio_sample_hash"),
        )
    if blocker.startswith("email_calendar_dependency_missing:"):
        return AdapterClosureAction(
            action_id=_action_id(adapter_id, blocker),
            adapter_id=adapter_id,
            blocker=blocker,
            action_type="credential",
            command="Bind one scoped connector token: GMAIL_ACCESS_TOKEN, GOOGLE_CALENDAR_ACCESS_TOKEN, or MICROSOFT_GRAPH_ACCESS_TOKEN.",
            evidence_required=("connector_scope_attestation", "secret_presence_attestation"),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "email_calendar_live_evidence_missing":
        return _receipt_action(
            adapter_id,
            blocker,
            "python scripts/produce_capability_adapter_live_receipts.py --target email-calendar --strict",
            ("email_calendar_live_receipt.json", "read_only_probe_receipt"),
        )
    return AdapterClosureAction(
        action_id=_action_id(adapter_id, blocker),
        adapter_id=adapter_id,
        blocker=blocker,
        action_type="manual-review",
        command="Review blocker and add a governed closure action before claiming production readiness.",
        evidence_required=("manual_review_receipt",),
        risk_level="medium",
        approval_required=True,
    )


def _dependency_action(
    adapter_id: str,
    blocker: str,
    command: str,
    evidence_required: tuple[str, ...],
) -> AdapterClosureAction:
    return AdapterClosureAction(
        action_id=_action_id(adapter_id, blocker),
        adapter_id=adapter_id,
        blocker=blocker,
        action_type="dependency",
        command=command,
        evidence_required=evidence_required,
        risk_level="medium",
        approval_required=False,
    )


def _receipt_action(
    adapter_id: str,
    blocker: str,
    command: str,
    evidence_required: tuple[str, ...],
) -> AdapterClosureAction:
    return AdapterClosureAction(
        action_id=_action_id(adapter_id, blocker),
        adapter_id=adapter_id,
        blocker=blocker,
        action_type="live-receipt",
        command=command,
        evidence_required=evidence_required,
        risk_level="medium",
        approval_required=False,
    )


def _action_id(adapter_id: str, blocker: str) -> str:
    normalized_adapter = adapter_id.replace(".", "-").replace("_", "-")
    normalized_blocker = blocker.replace(":", "-").replace("_", "-")
    return f"{normalized_adapter}-{normalized_blocker}"


def _dedupe_actions(actions: list[AdapterClosureAction]) -> list[AdapterClosureAction]:
    deduped: dict[str, AdapterClosureAction] = {}
    for action in actions:
        deduped.setdefault(action.action_id, action)
    return list(deduped.values())


def _load_evidence(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"adapter evidence report missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("adapter evidence root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse adapter closure plan arguments."""
    parser = argparse.ArgumentParser(description="Plan capability adapter closure actions.")
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for adapter closure planning."""
    args = parse_args(argv)
    plan = plan_capability_adapter_closure(Path(args.evidence))
    write_adapter_closure_plan(plan, Path(args.output))
    if args.json:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    elif plan.source_ready:
        print(f"CAPABILITY ADAPTER CLOSURE PLAN EMPTY plan_id={plan.plan_id}")
    else:
        print(f"CAPABILITY ADAPTER CLOSURE PLAN WRITTEN actions={plan.action_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
