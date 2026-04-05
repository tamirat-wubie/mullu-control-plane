"""Purpose: verify evidence-to-state merge behavior for runtime-core.
Governance scope: runtime-core tests only.
Dependencies: pytest and the runtime-core evidence merger module.
Invariants: state categories stay distinct, provenance is preserved, and committed state is never silently overwritten.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.evidence_merger import (
    EvidenceInput,
    EvidenceMerger,
    EvidenceState,
    EvidenceStateCategory,
    StateAtom,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def test_evidence_merger_preserves_provenance_and_state_categories() -> None:
    merger = EvidenceMerger()
    state = EvidenceState(
        committed={
            "workspace.root": StateAtom(
                state_key="workspace.root",
                value="C:/workspace",
                provenance_ids=("seed-1",),
            )
        }
    )

    merged = merger.merge(
        state,
        (
            EvidenceInput(
                evidence_id="evidence-1",
                state_key="workspace.files",
                value=12,
                category=EvidenceStateCategory.OBSERVED,
            ),
            EvidenceInput(
                evidence_id="evidence-2",
                state_key="forecast.files",
                value=18,
                category=EvidenceStateCategory.PREDICTED,
            ),
        ),
    )

    assert merged.observed["workspace.files"].provenance_ids == ("evidence-1",)
    assert merged.predicted["forecast.files"].value == 18
    assert merged.committed["workspace.root"].value == "C:/workspace"
    assert "workspace.root" not in merged.observed


def test_evidence_merger_rejects_conflicting_committed_state_writes() -> None:
    merger = EvidenceMerger()
    state = EvidenceState(
        committed={
            "workspace.root": StateAtom(
                state_key="workspace.root",
                value="C:/workspace",
                provenance_ids=("seed-1",),
            )
        }
    )

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        merger.merge(
            state,
            (
                EvidenceInput(
                    evidence_id="evidence-2",
                    state_key="workspace.root",
                    value="D:/other",
                    category=EvidenceStateCategory.COMMITTED,
                ),
            ),
        )

    assert str(exc_info.value) == "state conflict requires explicit reconciliation"
    assert "committed" not in str(exc_info.value)
    assert "workspace.root" not in str(exc_info.value)
    assert state.committed["workspace.root"].value == "C:/workspace"
    assert state.committed["workspace.root"].provenance_ids == ("seed-1",)


def test_evidence_merger_rejects_conflicting_observed_state_writes() -> None:
    merger = EvidenceMerger()
    state = EvidenceState(
        observed={
            "workspace.files": StateAtom(
                state_key="workspace.files",
                value=12,
                provenance_ids=("seed-1",),
            )
        }
    )

    with pytest.raises(RuntimeCoreInvariantError) as exc_info:
        merger.merge(
            state,
            (
                EvidenceInput(
                    evidence_id="evidence-2",
                    state_key="workspace.files",
                    value=14,
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
        )

    assert str(exc_info.value) == "state conflict requires explicit reconciliation"
    assert "observed" not in str(exc_info.value)
    assert "workspace.files" not in str(exc_info.value)
    assert state.observed["workspace.files"].value == 12
    assert state.observed["workspace.files"].provenance_ids == ("seed-1",)
