"""Purpose: concrete campaign templates for real work execution.
Governance scope: approval-driven deployment, support escalation,
    and document/request processing campaign templates.
Dependencies: work_campaign contracts, work_campaign engine.
Invariants:
  - Templates produce valid campaign step sequences.
  - All templates include close steps.
  - Templates are deterministic.
"""

from __future__ import annotations

from ..contracts.work_campaign import (
    CampaignDependency,
    CampaignDescriptor,
    CampaignPriority,
    CampaignStep,
    CampaignStepStatus,
    CampaignStepType,
    CampaignTrigger,
)
from .work_campaign import WorkCampaignEngine


def create_approval_deployment_campaign(
    engine: WorkCampaignEngine,
    campaign_id: str,
    *,
    request_ref: str = "",
    approver_id: str = "",
    workflow_id: str = "",
    owner_id: str = "",
    priority: CampaignPriority = CampaignPriority.HIGH,
) -> CampaignDescriptor:
    """Create an approval-driven deployment campaign.

    Flow:
    1. Ingest request
    2. Extract approval/deadline
    3. Contact approver
    4. Wait for response
    5. Create obligation if missing
    6. Trigger workflow/job
    7. Report outcome
    8. Close
    """
    steps = [
        CampaignStep(
            step_id=f"{campaign_id}-ingest",
            campaign_id=campaign_id,
            step_type=CampaignStepType.INGEST_ARTIFACT,
            order=0,
            name="Ingest deployment request",
            target_ref=request_ref,
            input_payload={"request_ref": request_ref},
        ),
        CampaignStep(
            step_id=f"{campaign_id}-extract",
            campaign_id=campaign_id,
            step_type=CampaignStepType.EXTRACT_COMMITMENTS,
            order=1,
            name="Extract approval and deadline",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-contact",
            campaign_id=campaign_id,
            step_type=CampaignStepType.SEND_COMMUNICATION,
            order=2,
            name="Contact approver",
            target_ref=approver_id,
            input_payload={"approver_id": approver_id},
        ),
        CampaignStep(
            step_id=f"{campaign_id}-wait",
            campaign_id=campaign_id,
            step_type=CampaignStepType.WAIT_FOR_REPLY,
            order=3,
            name="Wait for approval response",
            timeout_seconds=86400,
        ),
        CampaignStep(
            step_id=f"{campaign_id}-obligation",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CREATE_OBLIGATION,
            order=4,
            name="Create deployment obligation",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-workflow",
            campaign_id=campaign_id,
            step_type=CampaignStepType.RUN_WORKFLOW,
            order=5,
            name="Trigger deployment workflow",
            target_ref=workflow_id,
            input_payload={"workflow_id": workflow_id},
        ),
        CampaignStep(
            step_id=f"{campaign_id}-report",
            campaign_id=campaign_id,
            step_type=CampaignStepType.SEND_COMMUNICATION,
            order=6,
            name="Report deployment outcome",
            target_ref=approver_id,
        ),
        CampaignStep(
            step_id=f"{campaign_id}-close",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CLOSE,
            order=7,
            name="Close deployment campaign",
        ),
    ]

    dependencies = [
        CampaignDependency(
            dependency_id=f"{campaign_id}-dep-extract",
            campaign_id=campaign_id,
            source_step_id=f"{campaign_id}-ingest",
            target_step_id=f"{campaign_id}-extract",
        ),
        CampaignDependency(
            dependency_id=f"{campaign_id}-dep-contact",
            campaign_id=campaign_id,
            source_step_id=f"{campaign_id}-extract",
            target_step_id=f"{campaign_id}-contact",
        ),
        CampaignDependency(
            dependency_id=f"{campaign_id}-dep-wait",
            campaign_id=campaign_id,
            source_step_id=f"{campaign_id}-contact",
            target_step_id=f"{campaign_id}-wait",
        ),
        CampaignDependency(
            dependency_id=f"{campaign_id}-dep-obligation",
            campaign_id=campaign_id,
            source_step_id=f"{campaign_id}-wait",
            target_step_id=f"{campaign_id}-obligation",
        ),
        CampaignDependency(
            dependency_id=f"{campaign_id}-dep-workflow",
            campaign_id=campaign_id,
            source_step_id=f"{campaign_id}-obligation",
            target_step_id=f"{campaign_id}-workflow",
        ),
    ]

    return engine.register_campaign(
        campaign_id,
        "Approval-Driven Deployment",
        steps,
        priority=priority,
        trigger=CampaignTrigger.MANUAL,
        owner_id=owner_id,
        dependencies=dependencies,
        tags=("deployment", "approval"),
    )


def create_support_escalation_campaign(
    engine: WorkCampaignEngine,
    campaign_id: str,
    *,
    issue_ref: str = "",
    escalation_chain: list[str] | None = None,
    owner_id: str = "",
    priority: CampaignPriority = CampaignPriority.HIGH,
) -> CampaignDescriptor:
    """Create a support escalation campaign.

    Flow:
    1. Ingest issue/ticket
    2. Classify severity
    3. Route through support identity chain
    4. Escalate on timeout/failure
    5. Collect artifacts/transcript
    6. Close with outcome record
    """
    chain = escalation_chain or ["tier-1", "tier-2", "manager"]

    steps = [
        CampaignStep(
            step_id=f"{campaign_id}-ingest",
            campaign_id=campaign_id,
            step_type=CampaignStepType.INGEST_ARTIFACT,
            order=0,
            name="Ingest support ticket",
            target_ref=issue_ref,
        ),
        CampaignStep(
            step_id=f"{campaign_id}-classify",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CHECK_CONDITION,
            order=1,
            name="Classify severity",
        ),
    ]

    order = 2
    for i, identity in enumerate(chain):
        steps.append(CampaignStep(
            step_id=f"{campaign_id}-route-{i}",
            campaign_id=campaign_id,
            step_type=CampaignStepType.ROUTE_TO_IDENTITY,
            order=order,
            name=f"Route to {identity}",
            target_ref=identity,
        ))
        order += 1

    steps.extend([
        CampaignStep(
            step_id=f"{campaign_id}-escalate",
            campaign_id=campaign_id,
            step_type=CampaignStepType.ESCALATE,
            order=order,
            name="Escalate if unresolved",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-collect",
            campaign_id=campaign_id,
            step_type=CampaignStepType.INGEST_ARTIFACT,
            order=order + 1,
            name="Collect artifacts and transcript",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-close",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CLOSE,
            order=order + 2,
            name="Close support case",
        ),
    ])

    return engine.register_campaign(
        campaign_id,
        "Support Escalation",
        steps,
        priority=priority,
        trigger=CampaignTrigger.INCIDENT_DETECTED,
        trigger_ref_id=issue_ref,
        owner_id=owner_id,
        tags=("support", "escalation"),
    )


def create_document_processing_campaign(
    engine: WorkCampaignEngine,
    campaign_id: str,
    *,
    artifact_ref: str = "",
    notify_ids: list[str] | None = None,
    owner_id: str = "",
    priority: CampaignPriority = CampaignPriority.NORMAL,
) -> CampaignDescriptor:
    """Create a document/request processing campaign.

    Flow:
    1. Ingest document/artifact
    2. Extract commitments/owners/deadlines
    3. Create obligations
    4. Notify owners
    5. Follow up
    6. Escalate overdue
    7. Archive outcome into memory
    8. Close
    """
    notifiers = notify_ids or []

    steps = [
        CampaignStep(
            step_id=f"{campaign_id}-ingest",
            campaign_id=campaign_id,
            step_type=CampaignStepType.INGEST_ARTIFACT,
            order=0,
            name="Ingest document",
            target_ref=artifact_ref,
        ),
        CampaignStep(
            step_id=f"{campaign_id}-extract",
            campaign_id=campaign_id,
            step_type=CampaignStepType.EXTRACT_COMMITMENTS,
            order=1,
            name="Extract commitments, owners, deadlines",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-obligations",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CREATE_OBLIGATION,
            order=2,
            name="Create obligations from extracted commitments",
        ),
    ]

    order = 3
    for i, nid in enumerate(notifiers):
        steps.append(CampaignStep(
            step_id=f"{campaign_id}-notify-{i}",
            campaign_id=campaign_id,
            step_type=CampaignStepType.SEND_COMMUNICATION,
            order=order,
            name=f"Notify owner: {nid}",
            target_ref=nid,
        ))
        order += 1

    steps.extend([
        CampaignStep(
            step_id=f"{campaign_id}-followup",
            campaign_id=campaign_id,
            step_type=CampaignStepType.WAIT_FOR_REPLY,
            order=order,
            name="Wait for follow-up",
            timeout_seconds=172800,
        ),
        CampaignStep(
            step_id=f"{campaign_id}-escalate",
            campaign_id=campaign_id,
            step_type=CampaignStepType.ESCALATE,
            order=order + 1,
            name="Escalate overdue items",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-close",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CLOSE,
            order=order + 2,
            name="Archive and close",
        ),
    ])

    return engine.register_campaign(
        campaign_id,
        "Document Processing",
        steps,
        priority=priority,
        trigger=CampaignTrigger.ARTIFACT_INGESTED,
        trigger_ref_id=artifact_ref,
        owner_id=owner_id,
        tags=("document", "processing"),
    )
