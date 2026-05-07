"""Purpose: typed context bundles for governed software planning and patching.
Governance scope: task context requests, selected repository evidence, token
    estimates, cost estimates, and prompt-boundary receipts.
Dependencies: shared contract utilities and code_intelligence contracts.
Invariants:
  - A context request has explicit task summary and affected-file boundary.
  - A context bundle contains only repository-relative paths and typed symbols.
  - Token and cost estimates are non-negative deterministic approximations.
  - Selection reasons are explicit so prompt scope can be audited.
  - Context receipts summarize selection evidence without execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
    require_non_negative_int,
)
from .code_intelligence import CodeSymbol, FileRiskAssessment


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    frozen_values = freeze_value(list(values))
    if not isinstance(frozen_values, tuple):
        raise ValueError(f"{field_name} must be a tuple of strings")
    for index, item in enumerate(frozen_values):
        require_non_empty_text(item, f"{field_name}[{index}]")
    return frozen_values


def _freeze_metadata(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return freeze_value(dict(values))


@dataclass(frozen=True, slots=True)
class CodeContextRequest(ContractRecord):
    """Input boundary for building a minimal code context bundle."""

    task_summary: str
    affected_files: tuple[str, ...]
    acceptance_criteria: tuple[str, ...] = ()
    max_symbol_count: int = 40
    max_test_count: int = 20
    max_dependency_edges: int = 60
    target_model: str = "unspecified"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_summary", require_non_empty_text(self.task_summary, "task_summary"))
        affected_files = _freeze_text_tuple(tuple(self.affected_files), "affected_files")
        if not affected_files:
            raise ValueError("affected_files must contain at least one item")
        object.__setattr__(self, "affected_files", affected_files)
        object.__setattr__(
            self,
            "acceptance_criteria",
            _freeze_text_tuple(tuple(self.acceptance_criteria), "acceptance_criteria"),
        )
        object.__setattr__(
            self,
            "max_symbol_count",
            require_non_negative_int(self.max_symbol_count, "max_symbol_count"),
        )
        object.__setattr__(
            self,
            "max_test_count",
            require_non_negative_int(self.max_test_count, "max_test_count"),
        )
        object.__setattr__(
            self,
            "max_dependency_edges",
            require_non_negative_int(self.max_dependency_edges, "max_dependency_edges"),
        )
        object.__setattr__(self, "target_model", require_non_empty_text(self.target_model, "target_model"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class ContextFileSelection(ContractRecord):
    """One selected repository file and the causal reason for inclusion."""

    file_path: str
    reason: str
    distance: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", require_non_empty_text(self.file_path, "file_path"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "distance", require_non_negative_int(self.distance, "distance"))


@dataclass(frozen=True, slots=True)
class ContextEstimate(ContractRecord):
    """Deterministic estimate for a context bundle."""

    token_estimate: int
    cost_microusd_estimate: int
    estimation_method: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "token_estimate",
            require_non_negative_int(self.token_estimate, "token_estimate"),
        )
        object.__setattr__(
            self,
            "cost_microusd_estimate",
            require_non_negative_int(self.cost_microusd_estimate, "cost_microusd_estimate"),
        )
        object.__setattr__(
            self,
            "estimation_method",
            require_non_empty_text(self.estimation_method, "estimation_method"),
        )


@dataclass(frozen=True, slots=True)
class CodeContextBundle(ContractRecord):
    """Minimal prompt-ready context derived from RepoMap plus a bounded request."""

    bundle_id: str
    repository: str
    commit_sha: str
    task_summary: str
    selected_files: tuple[ContextFileSelection, ...]
    selected_symbols: tuple[CodeSymbol, ...]
    selected_tests: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    acceptance_criteria: tuple[str, ...]
    risk_assessments: tuple[FileRiskAssessment, ...]
    estimate: ContextEstimate
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "commit_sha", require_non_empty_text(self.commit_sha, "commit_sha"))
        object.__setattr__(self, "task_summary", require_non_empty_text(self.task_summary, "task_summary"))
        if not self.selected_files:
            raise ValueError("selected_files must contain at least one item")
        for selection in self.selected_files:
            if not isinstance(selection, ContextFileSelection):
                raise ValueError("selected_files must contain ContextFileSelection records")
        object.__setattr__(self, "selected_files", freeze_value(list(self.selected_files)))
        for symbol in self.selected_symbols:
            if not isinstance(symbol, CodeSymbol):
                raise ValueError("selected_symbols must contain CodeSymbol records")
        object.__setattr__(self, "selected_symbols", freeze_value(list(self.selected_symbols)))
        object.__setattr__(self, "selected_tests", _freeze_text_tuple(tuple(self.selected_tests), "selected_tests"))
        normalized_edges: list[tuple[str, str]] = []
        for index, edge in enumerate(self.dependency_edges):
            if not isinstance(edge, tuple) or len(edge) != 2:
                raise ValueError(f"dependency_edges[{index}] must be a source-target tuple")
            normalized_edges.append(
                (
                    require_non_empty_text(edge[0], f"dependency_edges[{index}].source"),
                    require_non_empty_text(edge[1], f"dependency_edges[{index}].target"),
                )
            )
        object.__setattr__(self, "dependency_edges", freeze_value(normalized_edges))
        object.__setattr__(
            self,
            "acceptance_criteria",
            _freeze_text_tuple(tuple(self.acceptance_criteria), "acceptance_criteria"),
        )
        for assessment in self.risk_assessments:
            if not isinstance(assessment, FileRiskAssessment):
                raise ValueError("risk_assessments must contain FileRiskAssessment records")
        object.__setattr__(self, "risk_assessments", freeze_value(list(self.risk_assessments)))
        if not isinstance(self.estimate, ContextEstimate):
            raise ValueError("estimate must be a ContextEstimate")
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class CodeContextReceipt(ContractRecord):
    """Read-only receipt proving a prompt context bundle was selected."""

    receipt_id: str
    bundle_id: str
    repository: str
    commit_sha: str
    selected_file_count: int
    selected_symbol_count: int
    selected_test_count: int
    dependency_edge_count: int
    token_estimate: int
    cost_microusd_estimate: int
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", require_non_empty_text(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "commit_sha", require_non_empty_text(self.commit_sha, "commit_sha"))
        object.__setattr__(
            self,
            "selected_file_count",
            require_non_negative_int(self.selected_file_count, "selected_file_count"),
        )
        object.__setattr__(
            self,
            "selected_symbol_count",
            require_non_negative_int(self.selected_symbol_count, "selected_symbol_count"),
        )
        object.__setattr__(
            self,
            "selected_test_count",
            require_non_negative_int(self.selected_test_count, "selected_test_count"),
        )
        object.__setattr__(
            self,
            "dependency_edge_count",
            require_non_negative_int(self.dependency_edge_count, "dependency_edge_count"),
        )
        object.__setattr__(
            self,
            "token_estimate",
            require_non_negative_int(self.token_estimate, "token_estimate"),
        )
        object.__setattr__(
            self,
            "cost_microusd_estimate",
            require_non_negative_int(self.cost_microusd_estimate, "cost_microusd_estimate"),
        )
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
