"""Local Developer Workflow v1 projection package.

Purpose: expose a local-lab, preview-only developer workflow bundle.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.local_developer_workflow_v1.runner.
Invariants: workflow artifacts never grant file-write, branch-push, PR-create,
merge, deployment, connector, or live execution authority.
"""

from .composition import (
    BLOCKED_EXTERNAL_EFFECTS,
    COMPOSITION_WORKFLOW_ID,
    TERMINAL_WAIT_STAGE_ID,
    build_foundation_workflow_composition_descriptor,
    build_foundation_workflow_composition_read_model,
    validate_foundation_workflow_composition,
)
from .runner import (
    ARTIFACT_FILENAMES,
    DEFAULT_OBJECTIVE,
    LocalDeveloperWorkflowV1Error,
    build_local_developer_workflow_v1_artifacts,
    collect_git_repository_status,
    validate_local_developer_workflow_v1_artifacts,
    write_local_developer_workflow_v1_artifacts,
)
from .closure_packet import (
    CLOSURE_PACKET_FILENAME,
    CLOSURE_PACKET_ID,
    LocalDeveloperWorkflowClosurePacketError,
    build_local_developer_workflow_closure_packet,
    validate_local_developer_workflow_closure_packet,
    write_local_developer_workflow_closure_packet,
)

__all__ = [
    "ARTIFACT_FILENAMES",
    "DEFAULT_OBJECTIVE",
    "LocalDeveloperWorkflowV1Error",
    "build_local_developer_workflow_v1_artifacts",
    "collect_git_repository_status",
    "validate_local_developer_workflow_v1_artifacts",
    "write_local_developer_workflow_v1_artifacts",
    "CLOSURE_PACKET_FILENAME",
    "CLOSURE_PACKET_ID",
    "LocalDeveloperWorkflowClosurePacketError",
    "build_local_developer_workflow_closure_packet",
    "validate_local_developer_workflow_closure_packet",
    "write_local_developer_workflow_closure_packet",
]
__all__ += [
    "BLOCKED_EXTERNAL_EFFECTS",
    "COMPOSITION_WORKFLOW_ID",
    "TERMINAL_WAIT_STAGE_ID",
    "build_foundation_workflow_composition_descriptor",
    "build_foundation_workflow_composition_read_model",
    "validate_foundation_workflow_composition",
]
