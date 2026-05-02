"""Tests for adapter closure planning.

Purpose: prove adapter evidence blockers become explicit operator actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.plan_capability_adapter_closure.
Invariants:
  - Planning preserves blockers instead of claiming closure.
  - Credential actions require approval.
  - Live receipt actions name the receipt command and evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plan_capability_adapter_closure import (  # noqa: E402
    main,
    plan_capability_adapter_closure,
    write_adapter_closure_plan,
)


def test_adapter_closure_plan_maps_blockers_to_actions(tmp_path: Path) -> None:
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    evidence_path.write_text(json.dumps(_blocked_evidence()), encoding="utf-8")

    plan = plan_capability_adapter_closure(evidence_path)
    actions_by_blocker = {action.blocker: action for action in plan.actions}

    assert plan.source_ready is False
    assert plan.plan_id.startswith("capability-adapter-closure-plan-")
    assert plan.plan_id != "capability-adapter-closure-plan-04"
    assert plan.action_count == 4
    assert "browser_dependency_missing:playwright" in plan.blockers
    assert actions_by_blocker["browser_live_evidence_missing"].action_type == "live-receipt"
    assert "produce_capability_adapter_live_receipts.py --target browser" in actions_by_blocker[
        "browser_live_evidence_missing"
    ].command
    assert "sandbox_receipt_ref" in actions_by_blocker["browser_live_evidence_missing"].evidence_required
    assert actions_by_blocker["voice_dependency_missing:OPENAI_API_KEY"].approval_required is True
    assert actions_by_blocker["voice_dependency_missing:OPENAI_API_KEY"].risk_level == "high"


def test_adapter_closure_plan_preserves_unknown_blocker_for_manual_review(tmp_path: Path) -> None:
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    evidence_path.write_text(
        json.dumps({"ready": False, "blockers": ["unknown_new_blocker"], "adapters": []}),
        encoding="utf-8",
    )

    plan = plan_capability_adapter_closure(evidence_path)
    action = plan.actions[0]

    assert plan.action_count == 1
    assert action.blocker == "unknown_new_blocker"
    assert action.action_type == "manual-review"
    assert action.approval_required is True


def test_adapter_closure_plan_writer_and_cli_emit_json(tmp_path: Path, capsys) -> None:
    evidence_path = tmp_path / "capability_adapter_evidence.json"
    output_path = tmp_path / "capability_adapter_closure_plan.json"
    evidence_path.write_text(json.dumps(_blocked_evidence()), encoding="utf-8")
    plan = plan_capability_adapter_closure(evidence_path)

    written = write_adapter_closure_plan(plan, output_path)
    exit_code = main(["--evidence", str(evidence_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["action_count"] == 4
    assert stdout_payload["plan_id"] == payload["plan_id"]
    assert "voice_dependency_missing:OPENAI_API_KEY" in payload["blockers"]


def _blocked_evidence() -> dict[str, object]:
    return {
        "ready": False,
        "adapters": [
            {
                "adapter_id": "browser.playwright",
                "blockers": [
                    "browser_dependency_missing:playwright",
                    "browser_live_evidence_missing",
                ],
            },
            {
                "adapter_id": "voice.openai",
                "blockers": [
                    "voice_dependency_missing:OPENAI_API_KEY",
                    "voice_live_evidence_missing",
                ],
            },
        ],
        "blockers": [
            "browser_dependency_missing:playwright",
            "browser_live_evidence_missing",
            "voice_dependency_missing:OPENAI_API_KEY",
            "voice_live_evidence_missing",
        ],
    }
