"""Purpose: verify nested-mind observation flow symbols are package-exported.
Governance scope: import contract for runtime operators and evidence store.
Dependencies: mcoi_runtime contracts and persistence packages.
Invariants: downstream code can use public package paths without private imports.
"""

from mcoi_runtime.adapters import (
    NestedMindConnector,
    NestedMindObservationReconciler,
    NestedMindObservationSubmissionOutcome,
    NestedMindObservationSubmitter,
)
from mcoi_runtime.contracts import (
    NestedMindCommitWitness,
    NestedMindObservationProposalPlan,
    NestedMindObservationReconciliationReport,
    NestedMindObservationSubmissionReport,
    build_observation_proposal_payload,
    stable_json_hash,
)
from mcoi_runtime.persistence import NestedMindEvidenceEntry, NestedMindEvidenceStore


def test_nested_mind_contracts_are_public_exports() -> None:
    assert NestedMindObservationProposalPlan.__name__ == "NestedMindObservationProposalPlan"
    assert NestedMindObservationSubmissionReport.__name__ == "NestedMindObservationSubmissionReport"
    assert NestedMindCommitWitness.__name__ == "NestedMindCommitWitness"
    assert (
        NestedMindObservationReconciliationReport.__name__
        == "NestedMindObservationReconciliationReport"
    )
    assert callable(build_observation_proposal_payload)
    assert stable_json_hash({"symbol": "observation"}) == stable_json_hash(
        {"symbol": "observation"}
    )


def test_nested_mind_persistence_symbols_are_public_exports() -> None:
    assert NestedMindEvidenceEntry.__name__ == "NestedMindEvidenceEntry"
    assert NestedMindEvidenceStore.__name__ == "NestedMindEvidenceStore"
    assert hasattr(NestedMindEvidenceStore, "record_plan")
    assert hasattr(NestedMindEvidenceStore, "record_reconciliation_report")


def test_nested_mind_adapters_are_public_exports() -> None:
    assert NestedMindConnector.__name__ == "NestedMindConnector"
    assert NestedMindObservationSubmitter.__name__ == "NestedMindObservationSubmitter"
    assert NestedMindObservationSubmissionOutcome.__name__ == "NestedMindObservationSubmissionOutcome"
    assert NestedMindObservationReconciler.__name__ == "NestedMindObservationReconciler"
