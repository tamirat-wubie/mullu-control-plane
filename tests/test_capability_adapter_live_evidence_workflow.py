"""Capability adapter live evidence workflow tests.

Purpose: prove the manual adapter evidence workflow covers every adapter
family required by the general-agent promotion gate.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: .github/workflows/capability-adapter-live-evidence.yml.
Invariants: the workflow must not upload raw audio, browser screenshots, or
secret values; failed probes remain explicit JSON evidence.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "capability-adapter-live-evidence.yml"


def test_capability_adapter_live_evidence_workflow_targets_all_adapter_families() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert 'default: "all"' in workflow
    assert "          - browser" in workflow
    assert "          - document" in workflow
    assert "          - voice" in workflow
    assert "          - email-calendar" in workflow
    assert 'browser_url:' in workflow
    assert 'default: "https://api.mullusi.com/health"' in workflow
    assert "Produce browser sandbox evidence" in workflow
    assert "Produce browser live receipt" in workflow
    assert "Produce document live receipt" in workflow
    assert "Produce voice live receipt" in workflow
    assert "Produce email/calendar live receipt" in workflow


def test_capability_adapter_live_evidence_workflow_validates_sandbox_chain() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "docker build -f /tmp/mullu-agent-runner.Dockerfile -t mullu-agent-runner:latest /tmp" in workflow
    assert "python scripts/produce_browser_sandbox_evidence.py" in workflow
    assert "python scripts/validate_sandbox_execution_receipt.py" in workflow
    assert "--capability-prefix browser." in workflow
    assert "--require-no-workspace-changes" in workflow
    assert "python scripts/validate_browser_sandbox_evidence.py" in workflow
    assert '--browser-url "${{ inputs.browser_url }}"' in workflow
    assert '--browser-sandbox-evidence "$MULLU_BROWSER_SANDBOX_EVIDENCE"' in workflow


def test_capability_adapter_live_evidence_workflow_collects_remaining_receipts_after_failure() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "if: ${{ always() && (inputs.target == 'all' || inputs.target == 'document') }}" in workflow
    assert "if: ${{ always() && (inputs.target == 'all' || inputs.target == 'voice') }}" in workflow
    assert "if: ${{ always() && (inputs.target == 'all' || inputs.target == 'email-calendar') }}" in workflow
    assert "if: always()" in workflow


def test_capability_adapter_live_evidence_workflow_uploads_json_receipts_only() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in workflow
    assert ".change_assurance/browser_sandbox_evidence.json" in workflow
    assert ".change_assurance/browser_live_receipt.json" in workflow
    assert ".change_assurance/document_live_receipt.json" in workflow
    assert ".change_assurance/voice_live_receipt.json" in workflow
    assert ".change_assurance/email_calendar_live_receipt.json" in workflow
    assert ".change_assurance/capability_adapter_evidence.json" in workflow
    assert ".change_assurance/private/voice_probe_audio.wav" not in workflow.split("path: |", 1)[1]
    assert "/tmp/mullu-browser-evidence" not in workflow.split("path: |", 1)[1]
