"""Tests for note-memory projection intelligence modules.

Purpose: verify Concept Boxes, axis traversal, Sigma/Mesh scoring, projection,
repair, action compilation, decision-use receipts, and bridges.
Governance scope: lineage separation, denominator guarding, projection-only
state, repair creation, no direct execution, and deterministic receipts.
Dependencies: pytest and mcoi_runtime.core note-memory intelligence modules.
Invariants: memory informs action, InceptaDive-M interrogates memory, Mesh
scores deltas, and only governance can approve execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from mcoi_runtime.core.concept_box_ledger import ConceptBoxLedger, build_note_concept_box, build_project_concept_box
from mcoi_runtime.core.decision_use_receipts import build_decision_use_receipt
from mcoi_runtime.core.incepta_scoring_adapter import ResonanceLinks, ScoringInput, score_axis_finding
from mcoi_runtime.core.inceptadive_axis_traversal import DeltaType, TraversalAxis, traverse_concept_box
from mcoi_runtime.core.inceptadive_interrogation_queue import (
    InterrogationPriority,
    InterrogationReason,
    build_interrogation_queue,
)
from mcoi_runtime.core.memory_action_compiler import compile_memory_actions
from mcoi_runtime.core.memory_repair_queue import build_memory_repair_queue
from mcoi_runtime.core.note_memory_mesh import (
    NoteKind,
    NoteMemoryDraft,
    NoteMemoryMesh,
    NoteScope,
    ProofState,
    TrustZone,
)
from mcoi_runtime.core.note_memory_projection import CandidateActionStatus, project_note_memory
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.note_memory_temporal_bridge import build_temporal_candidates
from mcoi_runtime.core.note_memory_world_state_bridge import bridge_projection_to_world_state
from mcoi_runtime.core.operational_dashboard_intelligence import (
    DashboardSimpleActionSummary,
    DashboardSimpleHomeSummary,
    DashboardSimpleStartGuideSummary,
    DashboardSimpleWorkflowSummary,
    WorkflowHealth,
    build_operational_dashboard_state,
)
from mcoi_runtime.core.outcome_learning_bridge import build_outcome_learning_record
from mcoi_runtime.core.simple_platform import SimpleActionRequest, SimplePlatform, SimpleWorkflowRequest


class MutableClock:
    """Frozen test clock with explicit advancement."""

    def __init__(self, value: str) -> None:
        self._value = datetime.fromisoformat(value).astimezone(timezone.utc)

    def __call__(self) -> str:
        return self._value.isoformat()


def _mesh(tmp_path, clock: MutableClock) -> NoteMemoryMesh:
    return NoteMemoryMesh(tmp_path / "notes", clock=clock)


def _capture_projection_notes(tmp_path):
    clock = MutableClock("2026-05-31T12:00:00+00:00")
    mesh = _mesh(tmp_path, clock)
    deploy_note = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.REPOSITORY,
            content_summary="After DNS verification, deploy dashboard",
            source_ref="test:deploy",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-06-03T00:00:00+00:00",
            evidence_refs=("dns-verification",),
        )
    )
    blocker_note = mesh.capture_note(
        NoteMemoryDraft(
            kind=NoteKind.WORKING_NOTE,
            scope=NoteScope.REPOSITORY,
            content_summary="Security review pending blocks dashboard deployment",
            source_ref="test:security",
            proof_state=ProofState.PASS,
            trust_zone=TrustZone.WORKSPACE,
            expires_at="2026-06-03T00:00:00+00:00",
            evidence_refs=("security-review-ticket",),
        )
    )
    return mesh, deploy_note, blocker_note


def test_concept_box_ledger_preserves_projection_lineage_and_hash(tmp_path) -> None:
    _, deploy_note, _ = _capture_projection_notes(tmp_path)
    box = build_note_concept_box(deploy_note)
    ledger = ConceptBoxLedger(tmp_path / "ledger")
    stored = ledger.append_box(box)
    listed = ledger.list_boxes()

    assert stored.snapshot_hash == stored.expected_snapshot_hash()
    assert listed == (stored,)
    assert stored.source_note_ids == (deploy_note.note_id,)
    assert stored.to_dict()["projection_only"] is True
    assert "InceptaDive-M" in stored.lineage


def test_concept_box_ledger_rejects_non_string_identity_on_readback(tmp_path) -> None:
    _, deploy_note, _ = _capture_projection_notes(tmp_path)
    ledger = ConceptBoxLedger(tmp_path / "ledger")
    stored = ledger.append_box(build_note_concept_box(deploy_note))
    ledger_path = tmp_path / "ledger" / "concept-boxes.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["identity_facets"] = [f"note:{deploy_note.note_id}", 42]
    ledger_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeCoreInvariantError, match="invalid Concept Box ledger entry") as raised:
        ledger.list_boxes()

    assert f"{ledger_path}:1" in str(raised.value)
    assert isinstance(raised.value.__cause__, RuntimeCoreInvariantError)
    assert stored.snapshot_hash == stored.expected_snapshot_hash()


def test_concept_box_ledger_rejects_non_list_lineage_on_readback(tmp_path) -> None:
    _, deploy_note, _ = _capture_projection_notes(tmp_path)
    ledger = ConceptBoxLedger(tmp_path / "ledger")
    stored = ledger.append_box(build_note_concept_box(deploy_note))
    ledger_path = tmp_path / "ledger" / "concept-boxes.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["lineage"] = "note-memory"
    ledger_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeCoreInvariantError, match="invalid Concept Box ledger entry") as raised:
        ledger.list_boxes()

    assert f"{ledger_path}:1" in str(raised.value)
    assert isinstance(raised.value.__cause__, RuntimeCoreInvariantError)
    assert stored.lineage == ("note-memory", "InceptaDive-M")


def test_concept_box_ledger_rejects_non_string_box_id_on_readback(tmp_path) -> None:
    _, deploy_note, _ = _capture_projection_notes(tmp_path)
    ledger = ConceptBoxLedger(tmp_path / "ledger")
    stored = ledger.append_box(build_note_concept_box(deploy_note))
    ledger_path = tmp_path / "ledger" / "concept-boxes.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["box_id"] = 1001
    ledger_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeCoreInvariantError, match="invalid Concept Box ledger entry") as raised:
        ledger.list_boxes()

    assert f"{ledger_path}:1" in str(raised.value)
    assert isinstance(raised.value.__cause__, RuntimeCoreInvariantError)
    assert stored.source_note_ids == (deploy_note.note_id,)


def test_axis_traversal_emits_findings_without_truth_promotion(tmp_path) -> None:
    _, _, blocker_note = _capture_projection_notes(tmp_path)
    box = build_note_concept_box(blocker_note)
    result = traverse_concept_box(box)
    fracture_findings = [finding for finding in result.findings if finding.delta_type == DeltaType.FRACTURE]

    assert result.to_dict()["execution_approval"] is False
    assert any(finding.axis == TraversalAxis.INTENSITY for finding in fracture_findings)
    assert all(finding.source_box_id == box.box_id for finding in result.findings)
    assert all(finding.lineage_tag == "InceptaDive-M:axis-traversal" for finding in result.findings)
    assert fracture_findings[0].repair_requirement


def test_scoring_adapter_uses_mesh_denominator_guard_for_sigma_memory_kernel(tmp_path) -> None:
    _, _, blocker_note = _capture_projection_notes(tmp_path)
    box = build_note_concept_box(blocker_note)
    finding = next(finding for finding in traverse_concept_box(box).findings if finding.delta_type == DeltaType.FRACTURE)

    score = score_axis_finding(
        ScoringInput(
            finding=finding,
            layer_index=1,
            semantic_delta_magnitude=1.0,
            resonance_links=ResonanceLinks(
                structural_match=0.9,
                causal_coherence=0.9,
                mfidel_judgment=1.0,
                min_alignment=0.85,
            ),
            prior_deltas=(0.5,),
        )
    )

    assert score.denominator_guard_applied is True
    assert score.to_dict()["execution_approval"] is False
    assert score.true_delta_score > score.suppression_adjusted_score
    assert score.promotion_recommendation.value == "repair_required"
    assert score.repair_recommendation == finding.repair_requirement


def test_projection_blocks_deploy_candidates_and_records_receipt(tmp_path) -> None:
    mesh, deploy_note, blocker_note = _capture_projection_notes(tmp_path)
    boxes = tuple(build_note_concept_box(event) for event in (deploy_note, blocker_note))
    findings = tuple(finding for box in boxes for finding in traverse_concept_box(box).findings)
    scores = tuple(
        score_axis_finding(
            ScoringInput(
                finding=finding,
                layer_index=index,
                semantic_delta_magnitude=1.0,
                resonance_links=ResonanceLinks(0.8, 0.8, 1.0, 0.8),
            )
        )
        for index, finding in enumerate(findings, start=1)
    )

    projection = project_note_memory(
        mesh.list_events(),
        concept_boxes=boxes,
        axis_findings=findings,
        scores=scores,
        assessed_at="2026-05-31T12:05:00+00:00",
    )
    deploy_actions = [action for action in projection.candidate_actions if action.action_type == "deploy"]

    assert len(projection.active_claims) == 2
    assert projection.receipt.snapshot_hash == projection.receipt.expected_snapshot_hash()
    assert projection.fracture_delta_ids
    assert projection.blockers
    assert deploy_actions[0].status == CandidateActionStatus.BLOCKED
    assert deploy_actions[0].execution_allowed is False


def test_repair_queue_and_action_compiler_never_execute(tmp_path) -> None:
    mesh, deploy_note, blocker_note = _capture_projection_notes(tmp_path)
    boxes = tuple(build_note_concept_box(event) for event in (deploy_note, blocker_note))
    findings = tuple(finding for box in boxes for finding in traverse_concept_box(box).findings)
    projection = project_note_memory(
        mesh.list_events(),
        concept_boxes=boxes,
        axis_findings=findings,
        assessed_at="2026-05-31T12:05:00+00:00",
    )

    repairs = build_memory_repair_queue(projection, axis_findings=findings)
    actions = compile_memory_actions(projection, repair_items=repairs)

    assert repairs
    assert actions
    assert all(item.execution_allowed is False for item in repairs)
    assert all(action.execution_allowed is False for action in actions)
    assert all(action.governance_status == "requires_mullu_control_plane_verdict" for action in actions)


def test_decision_receipt_and_bridges_are_deterministic_and_projection_only(tmp_path) -> None:
    mesh, deploy_note, blocker_note = _capture_projection_notes(tmp_path)
    boxes = tuple(build_note_concept_box(event) for event in (deploy_note, blocker_note))
    findings = tuple(finding for box in boxes for finding in traverse_concept_box(box).findings)
    projection = project_note_memory(
        mesh.list_events(),
        concept_boxes=boxes,
        axis_findings=findings,
        assessed_at="2026-05-31T12:05:00+00:00",
    )
    repairs = build_memory_repair_queue(projection, axis_findings=findings)
    actions = compile_memory_actions(projection, repair_items=repairs)
    receipt = build_decision_use_receipt(
        decision_id="decision-dashboard-deploy",
        retrieval_receipt_id="retrieval-dashboard-deploy",
        projection=projection,
        compiled_action=actions[0],
        repair_items=repairs,
        governance_verdict="block",
        proof_state=ProofState.PASS,
        confidence_score=0.82,
        assessed_at="2026-05-31T12:10:00+00:00",
    )
    world_facts = bridge_projection_to_world_state(projection)
    temporal_candidates = build_temporal_candidates(projection)
    learning = build_outcome_learning_record(
        compiled_action=actions[0],
        expected_outcome="dashboard reachable",
        actual_outcome="security review pending",
    )

    assert receipt.snapshot_hash == receipt.expected_snapshot_hash()
    assert blocker_note.note_id in receipt.blocking_note_ids
    assert deploy_note.note_id in receipt.supporting_note_ids
    assert all(note_id.startswith("note-") for note_id in receipt.blocking_note_ids)
    assert not any(finding.finding_id in receipt.blocking_note_ids for finding in findings)
    assert any(fact.expected_state_violation for fact in world_facts)
    assert all(candidate.schedule_direct_execution is False for candidate in temporal_candidates)
    assert learning.write_back_required is True


def test_interrogation_queue_targets_blockers_and_dashboard_separates_state(tmp_path) -> None:
    mesh, deploy_note, blocker_note = _capture_projection_notes(tmp_path)
    note_boxes = tuple(build_note_concept_box(event) for event in (deploy_note, blocker_note))
    project_box = build_project_concept_box(
        project_id="project-dashboard",
        project_label="Dashboard deployment",
        source_events=mesh.list_events(),
        created_at="2026-05-31T12:00:00+00:00",
        updated_at="2026-05-31T12:05:00+00:00",
    )
    boxes = (*note_boxes, project_box)
    findings = tuple(finding for box in boxes for finding in traverse_concept_box(box).findings)
    projection = project_note_memory(
        mesh.list_events(),
        concept_boxes=boxes,
        axis_findings=findings,
        assessed_at="2026-05-31T12:05:00+00:00",
    )
    repairs = build_memory_repair_queue(projection, axis_findings=findings)
    actions = compile_memory_actions(projection, repair_items=repairs)

    tasks = build_interrogation_queue(boxes, projection, repair_items=repairs)
    dashboard = build_operational_dashboard_state(
        projection=projection,
        boxes=boxes,
        repair_items=repairs,
        compiled_actions=actions,
        interrogation_tasks=tasks,
    )

    assert tasks
    assert any(task.reason == InterrogationReason.PROJECT_BLOCKER for task in tasks)
    assert any(task.priority == InterrogationPriority.HIGH for task in tasks)
    assert all(task.execution_allowed is False for task in tasks)
    assert dashboard.workflow_health == WorkflowHealth.REPAIR_REQUIRED
    assert dashboard.active_project_count == 1
    assert dashboard.blocked_action_ids
    assert dashboard.repair_ids
    assert dashboard.fracture_delta_ids
    assert dashboard.high_intensity_box_ids
    assert dashboard.execution_allowed is False


def test_dashboard_projects_simple_actions_without_execution_authority(tmp_path) -> None:
    mesh, deploy_note, blocker_note = _capture_projection_notes(tmp_path)
    boxes = tuple(build_note_concept_box(event) for event in (deploy_note, blocker_note))
    findings = tuple(finding for box in boxes for finding in traverse_concept_box(box).findings)
    projection = project_note_memory(
        mesh.list_events(),
        concept_boxes=boxes,
        axis_findings=findings,
        assessed_at="2026-05-31T12:05:00+00:00",
    )
    simple_platform = SimplePlatform()
    ready_check = simple_platform.check_action(
        SimpleActionRequest(
            goal="Review docs",
            action="view",
            target="docs/README.md",
            allowed_area="docs/**",
            actor_id="dashboard-test",
        )
    )
    review_check = simple_platform.check_action(
        SimpleActionRequest(
            goal="Notify support",
            action="send",
            target="support@mullusi.com",
            allowed_area="support@mullusi.com",
            actor_id="dashboard-test",
        )
    )
    blocked_check = simple_platform.check_action(
        SimpleActionRequest(
            goal="Update deployment config",
            action="change",
            target="deploy/config.json",
            allowed_area="docs/**",
            actor_id="dashboard-test",
        )
    )

    dashboard = build_operational_dashboard_state(
        projection=projection,
        boxes=boxes,
        simple_action_checks=(ready_check, review_check, blocked_check),
    )
    payload = dashboard.to_dict()

    assert len(dashboard.simple_action_summaries) == 3
    assert dashboard.simple_ready_action_refs == (ready_check.decision_ref,)
    assert dashboard.simple_review_action_refs == (review_check.decision_ref,)
    assert dashboard.simple_blocked_action_refs == (blocked_check.decision_ref,)
    assert payload["simple_action_summaries"][0]["title"] == "Ready"
    assert payload["simple_action_summaries"][1]["review_reasons"] == ["External changes require approval."]
    assert payload["simple_action_summaries"][2]["blocked_reasons"] == ["The target is outside the allowed area."]
    assert all(summary["execution_allowed"] is False for summary in payload["simple_action_summaries"])
    assert payload["execution_allowed"] is False


def test_dashboard_projects_simple_workflows_and_start_guide_without_execution_authority(tmp_path) -> None:
    mesh, deploy_note, blocker_note = _capture_projection_notes(tmp_path)
    boxes = tuple(build_note_concept_box(event) for event in (deploy_note, blocker_note))
    findings = tuple(finding for box in boxes for finding in traverse_concept_box(box).findings)
    projection = project_note_memory(
        mesh.list_events(),
        concept_boxes=boxes,
        axis_findings=findings,
        assessed_at="2026-05-31T12:05:00+00:00",
    )
    simple_platform = SimplePlatform()
    ready_plan = simple_platform.check_workflow(
        SimpleWorkflowRequest(
            workflow="docs_update",
            target="docs/README.md",
            actor_id="dashboard-test",
        )
    )
    review_plan = simple_platform.check_workflow({"workflow": "support-notice", "actor_id": "dashboard-test"})
    blocked_plan = simple_platform.check_workflow(
        {
            "workflow": "docs-update",
            "target": "deploy/config.json",
            "actor_id": "dashboard-test",
        }
    )

    dashboard = build_operational_dashboard_state(
        projection=projection,
        boxes=boxes,
        simple_workflow_plans=(ready_plan, review_plan, blocked_plan),
        simple_start_guide=SimplePlatform.onboarding_guide(),
    )
    payload = dashboard.to_dict()

    assert len(dashboard.simple_workflow_summaries) == 3
    assert dashboard.simple_ready_workflow_refs == (dashboard.simple_workflow_summaries[0].workflow_ref,)
    assert dashboard.simple_review_workflow_refs == (dashboard.simple_workflow_summaries[1].workflow_ref,)
    assert dashboard.simple_blocked_workflow_refs == (dashboard.simple_workflow_summaries[2].workflow_ref,)
    assert payload["simple_workflow_summaries"][0]["ready_count"] == 3
    assert payload["simple_workflow_summaries"][1]["review_count"] == 1
    assert payload["simple_workflow_summaries"][2]["blocked_count"] == 2
    assert payload["simple_start_guide"]["recommended_commands"][0] == "mullu workflows"
    assert payload["simple_home_summary"]["title"] == "Blocked"
    assert payload["simple_home_summary"]["primary_command"] == "mullu workflows"
    assert payload["simple_home_summary"]["ready_workflow_count"] == 1
    assert payload["simple_home_summary"]["review_workflow_count"] == 1
    assert payload["simple_home_summary"]["blocked_workflow_count"] == 1
    assert all(summary["execution_allowed"] is False for summary in payload["simple_workflow_summaries"])
    assert payload["simple_start_guide"]["execution_allowed"] is False
    assert payload["simple_home_summary"]["execution_allowed"] is False
    assert payload["execution_allowed"] is False


def test_dashboard_simple_action_summary_rejects_execution_authority() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="dashboard simple action cannot allow execution"):
        DashboardSimpleActionSummary(
            action_ref="gate-decision-test",
            outcome="ready",
            title="Ready",
            message="Ready for display.",
            next_step="Continue.",
            proof_stamp_ref="proof-test",
            boundary_witness_ref="witness-test",
            blocked_reasons=(),
            review_reasons=(),
            execution_allowed=True,
        )


def test_dashboard_simple_workflow_summary_rejects_execution_authority() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="dashboard simple workflow cannot allow execution"):
        DashboardSimpleWorkflowSummary(
            workflow_ref="dashboard-simple-workflow-test",
            workflow="docs_update",
            label="Update docs",
            outcome="ready",
            title="Ready",
            message="Ready for display.",
            next_step="Continue.",
            ready_count=1,
            review_count=0,
            blocked_count=0,
            action_refs=("gate-decision-test",),
            execution_allowed=True,
        )


def test_dashboard_simple_start_guide_rejects_execution_authority() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="dashboard simple start guide cannot allow execution"):
        DashboardSimpleStartGuideSummary(
            title="Mullu simple mode",
            message="Unsafe guide.",
            recommended_commands=("mullu workflows",),
            outcomes=("Ready",),
            execution_allowed=True,
        )


def test_dashboard_simple_home_summary_rejects_execution_authority() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="dashboard simple home cannot allow execution"):
        DashboardSimpleHomeSummary(
            title="Ready",
            message="Unsafe home.",
            primary_command="mullu workflows",
            ready_workflow_count=1,
            review_workflow_count=0,
            blocked_workflow_count=0,
            execution_allowed=True,
        )


def test_projection_rejects_fracture_finding_without_box_source_lineage(tmp_path) -> None:
    _, _, blocker_note = _capture_projection_notes(tmp_path)
    box = build_note_concept_box(blocker_note)
    finding = next(finding for finding in traverse_concept_box(box).findings if finding.delta_type == DeltaType.FRACTURE)

    with pytest.raises(RuntimeCoreInvariantError, match="source note lineage"):
        project_note_memory(
            (blocker_note,),
            axis_findings=(finding,),
            assessed_at="2026-05-31T12:05:00+00:00",
        )
