"""Conformance tests for the general-agent capability closure manifest.

Purpose: Keep the human-readable closure record aligned with promotion readiness evidence.
Governance scope: Symbolic intelligence terminology, explicit blocker traceability, and PRS status.
Dependencies: docs/57_general_agent_capability_closure_manifest.md.
Invariants: No forbidden terminology, readiness stamp is present, production blockers remain visible.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "57_general_agent_capability_closure_manifest.md"
FORBIDDEN_PHRASE = " ".join(("artificial", "intelligence"))


def _manifest_text() -> str:
    return MANIFEST.read_text(encoding="utf-8")


def test_manifest_uses_symbolic_intelligence_terminology() -> None:
    manifest_text = _manifest_text()

    assert FORBIDDEN_PHRASE not in manifest_text.lower()
    assert "symbolic intelligence" in manifest_text
    assert "public-production claim" in manifest_text
    assert "\u00e2" not in manifest_text


def test_manifest_records_current_promotion_readiness_stamp() -> None:
    manifest_text = _manifest_text()

    assert "`pilot-governed-core`" in manifest_text
    assert "10 capsules" in manifest_text
    assert "52 capabilities" in manifest_text
    assert "deployment.witness.publish.with_approval" in manifest_text
    assert "scripts/plan_capability_adapter_closure.py" in manifest_text
    assert "scripts/plan_deployment_publication_closure.py" in manifest_text
    assert "scripts/plan_general_agent_promotion_closure.py" in manifest_text
    assert "schemas/general_agent_promotion_closure_plan.schema.json" in manifest_text
    assert "scripts/validate_general_agent_promotion_closure_plan_schema.py" in manifest_text
    assert "scripts/validate_general_agent_promotion_closure_plan.py" in manifest_text
    assert "scripts/emit_general_agent_promotion_environment_binding_receipt.py" in manifest_text
    assert "scripts/validate_general_agent_promotion_environment_binding_receipt.py" in manifest_text
    assert "scripts/preflight_general_agent_promotion_handoff.py" in manifest_text


def test_manifest_preserves_open_blocker_traceability() -> None:
    manifest_text = _manifest_text()
    expected_blockers = {
        "adapter_evidence_not_closed",
        "browser_adapter_not_closed",
        "voice_adapter_not_closed",
        "email_calendar_adapter_not_closed",
        "deployment_witness_not_published",
        "production_health_not_declared",
    }

    assert "Open Production Blockers" in manifest_text
    assert expected_blockers <= set(manifest_text.split())
    assert "document_adapter_not_closed" not in manifest_text
    assert ".change_assurance/capability_adapter_closure_plan.json" in manifest_text
    assert ".change_assurance/deployment_publication_closure_plan.json" in manifest_text
    assert ".change_assurance/general_agent_promotion_closure_plan.json" in manifest_text
    assert ".change_assurance/general_agent_promotion_closure_plan_schema_validation.json" in manifest_text
    assert ".change_assurance/general_agent_promotion_closure_plan_validation.json" in manifest_text
    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in manifest_text
    assert ".change_assurance/general_agent_promotion_handoff_preflight.json" in manifest_text
    assert "STATUS:" in manifest_text
