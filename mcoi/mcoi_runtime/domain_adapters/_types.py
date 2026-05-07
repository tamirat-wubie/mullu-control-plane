"""
Universal types shared by the cycle helper and every domain adapter.

Extracted from software_dev.py at v4.14.1 to break the
``_cycle_helpers ↔ software_dev`` circular import that the static
import analyzer detects.

``UniversalRequest`` and ``UniversalResult`` are domain-neutral envelopes
used by the SCCCE cycle. Domain adapters translate their own request
shapes to/from these. Hosting them in a third neutral module removes the
cycle without changing runtime behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


@dataclass
class UniversalRequest:
    """Domain-agnostic shape consumed by UCJA L0 and the cycle."""

    request_id: UUID = field(default_factory=uuid4)
    purpose_statement: str = ""
    initial_state_descriptor: dict[str, Any] = field(default_factory=dict)
    target_state_descriptor: dict[str, Any] = field(default_factory=dict)
    boundary_specification: dict[str, Any] = field(default_factory=dict)
    constraint_set: tuple[dict[str, Any], ...] = ()
    authority_required: tuple[str, ...] = ()
    observer_required: tuple[str, ...] = ()


@dataclass
class UniversalResult:
    """Domain-agnostic UCJA pipeline output."""

    job_definition_id: UUID
    construct_graph_summary: dict[str, int]  # construct_type -> count
    cognitive_cycles_run: int
    converged: bool
    cascade_chain: tuple[UUID, ...] = ()
    proof_state: str = "Unknown"  # Pass | Fail(reason) | Unknown | BudgetUnknown
    rejected_deltas: tuple[dict[str, Any], ...] = ()
