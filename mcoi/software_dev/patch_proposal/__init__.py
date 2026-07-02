"""Patch Proposal / Diff Proposal draft capability.

Purpose: expose a reusable local-lab patch proposal artifact before file
writing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: software_dev.patch_proposal.runner.
Invariants: patch proposals are preview-only and never execution authority.
"""

from .runner import (
    ARTIFACT_FILENAME,
    CAPABILITY_ID,
    PatchProposalDraftError,
    build_patch_proposal_draft,
    collect_patch_proposal_draft,
    validate_patch_proposal_draft,
    write_patch_proposal_draft,
)

__all__ = [
    "ARTIFACT_FILENAME",
    "CAPABILITY_ID",
    "PatchProposalDraftError",
    "build_patch_proposal_draft",
    "collect_patch_proposal_draft",
    "validate_patch_proposal_draft",
    "write_patch_proposal_draft",
]
