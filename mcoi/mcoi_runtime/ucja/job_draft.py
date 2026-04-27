"""
UCJA Job Draft — accumulator that flows through L0–L9.

Each layer reads what prior layers added and writes its own output. The
draft is immutable per-layer (a new draft is produced each step) so the
pipeline can rewind cleanly on reject.

This is the data side of UCJA. The pipeline runner lives in pipeline.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class LayerVerdict(Enum):
    """Each layer returns one of these via its LayerResult."""

    PASS = "pass"
    RECLASSIFY = "reclassify"
    REJECT = "reject"


@dataclass(frozen=True)
class LayerResult:
    """Per-layer outcome. Pipeline halts on RECLASSIFY or REJECT."""

    verdict: LayerVerdict
    reason: str = ""
    suggestion: str = ""

    def __post_init__(self) -> None:
        if self.verdict in (LayerVerdict.RECLASSIFY, LayerVerdict.REJECT) and not self.reason:
            raise ValueError(
                f"{self.verdict.value} verdict requires a reason "
                "(silent rejection is the same fabrication pattern as MUSIA_MODE)"
            )


@dataclass
class JobDraft:
    """
    Accumulator passed through L0→L9. Each layer adds its outputs.

    Fields are populated cumulatively; a layer reads what came before and
    writes its own slot. None means "not yet produced by any layer."
    """

    job_id: UUID = field(default_factory=uuid4)

    # Input that triggered the pipeline
    request_payload: dict[str, Any] = field(default_factory=dict)

    # L0: Reality qualification
    qualified: Optional[bool] = None
    qualification_reason: str = ""

    # L1: Purpose + boundary + authority
    purpose_statement: str = ""
    boundary_specification: dict[str, Any] = field(default_factory=dict)
    authority_required: tuple[str, ...] = ()

    # L2: Transformation model
    initial_state_descriptor: dict[str, Any] = field(default_factory=dict)
    target_state_descriptor: dict[str, Any] = field(default_factory=dict)
    causation_mechanism: str = ""

    # L3: Dependencies & assumptions
    dependencies: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    # L4: Task decomposition
    task_descriptions: tuple[str, ...] = ()

    # L5: Functional structuring
    functional_groups: tuple[tuple[str, ...], ...] = ()

    # L6: Flow connector contracts
    flow_contracts: tuple[dict[str, Any], ...] = ()

    # L7: Failure / risk / degradation model
    risks: tuple[str, ...] = ()
    degradation_thresholds: tuple[dict[str, Any], ...] = ()

    # L8: Temporal & decision governance
    deadlines: tuple[dict[str, Any], ...] = ()
    decision_authorities: tuple[str, ...] = ()

    # L9: Closure / validation / drift control
    closure_criteria: tuple[str, ...] = ()
    drift_detectors: tuple[str, ...] = ()

    # Pipeline trace
    layer_results: tuple[tuple[str, LayerResult], ...] = ()

    def with_layer(self, layer_name: str, result: LayerResult) -> "JobDraft":
        """Append a layer trace entry without mutating in place."""
        return replace(
            self,
            layer_results=self.layer_results + ((layer_name, result),),
        )

    def is_complete(self) -> bool:
        """True iff L0–L9 all produced PASS results."""
        if len(self.layer_results) < 10:
            return False
        return all(r.verdict == LayerVerdict.PASS for _, r in self.layer_results)
