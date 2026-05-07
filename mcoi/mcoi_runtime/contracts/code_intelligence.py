"""Purpose: typed repository intelligence contracts for software work.
Governance scope: code symbols, repository maps, test maps, risk profiles, and
    read-only repository intelligence receipts.
Dependencies: shared contract utilities, dataclasses, enum, and typing.
Invariants:
  - Repository paths are repository-relative POSIX strings.
  - Symbol line ranges are positive and ordered.
  - Test relationships are explicit in both source-to-test and test-to-source form.
  - Risk assessments carry both a bounded score and causal reasons.
  - Receipts expose counts and evidence references without effect-bearing authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
    require_non_negative_int,
)


class CodeSymbolKind(StrEnum):
    """Kinds of symbols emitted by the first repository intelligence pass."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    ASYNC_METHOD = "async_method"
    FASTAPI_ROUTE = "fastapi_route"
    PYDANTIC_SCHEMA = "pydantic_schema"
    DATACLASS_SCHEMA = "dataclass_schema"


class CodeFileRisk(StrEnum):
    """Risk tier for a repository file touched by software work."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _require_positive_line(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return value


def _require_percent_score(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return value


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    frozen_values = freeze_value(list(values))
    if not isinstance(frozen_values, tuple):
        raise ValueError(f"{field_name} must be a tuple of strings")
    for index, item in enumerate(frozen_values):
        require_non_empty_text(item, f"{field_name}[{index}]")
    return frozen_values


def _freeze_text_tuple_map(
    values: Mapping[str, tuple[str, ...]],
    field_name: str,
) -> Mapping[str, tuple[str, ...]]:
    normalized_values: dict[str, tuple[str, ...]] = {}
    for key, item_values in values.items():
        normalized_key = require_non_empty_text(key, f"{field_name}.key")
        normalized_values[normalized_key] = _freeze_text_tuple(tuple(item_values), field_name)
    return freeze_value(normalized_values)


@dataclass(frozen=True, slots=True)
class CodeSymbol(ContractRecord):
    """A repository-relative code symbol with local imports and references."""

    name: str
    kind: CodeSymbolKind
    file_path: str
    line_start: int
    line_end: int
    imports: tuple[str, ...] = ()
    referenced_by: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.kind, CodeSymbolKind):
            raise ValueError("kind must be a CodeSymbolKind")
        object.__setattr__(self, "file_path", require_non_empty_text(self.file_path, "file_path"))
        object.__setattr__(self, "line_start", _require_positive_line(self.line_start, "line_start"))
        object.__setattr__(self, "line_end", _require_positive_line(self.line_end, "line_end"))
        if self.line_end < self.line_start:
            raise ValueError("line_end must be >= line_start")
        object.__setattr__(self, "imports", _freeze_text_tuple(tuple(self.imports), "imports"))
        object.__setattr__(self, "referenced_by", _freeze_text_tuple(tuple(self.referenced_by), "referenced_by"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TestMap(ContractRecord):
    """Bidirectional map between source files and their relevant tests."""

    source_to_tests: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    test_to_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_to_tests",
            _freeze_text_tuple_map(self.source_to_tests, "source_to_tests"),
        )
        object.__setattr__(
            self,
            "test_to_sources",
            _freeze_text_tuple_map(self.test_to_sources, "test_to_sources"),
        )


@dataclass(frozen=True, slots=True)
class FileRiskAssessment(ContractRecord):
    """Risk score and causal reasons for a repository-relative file path."""

    file_path: str
    risk: CodeFileRisk
    score: int
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", require_non_empty_text(self.file_path, "file_path"))
        if not isinstance(self.risk, CodeFileRisk):
            raise ValueError("risk must be a CodeFileRisk")
        object.__setattr__(self, "score", _require_percent_score(self.score, "score"))
        object.__setattr__(self, "reasons", _freeze_text_tuple(tuple(self.reasons), "reasons"))


@dataclass(frozen=True, slots=True)
class RepoMap(ContractRecord):
    """Read-only structural map of a repository at one commit boundary."""

    repository: str
    commit_sha: str
    files: tuple[str, ...] = ()
    symbols: tuple[CodeSymbol, ...] = ()
    test_map: TestMap = field(default_factory=TestMap)
    dependency_edges: tuple[tuple[str, str], ...] = ()
    risk_assessments: tuple[FileRiskAssessment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "commit_sha", require_non_empty_text(self.commit_sha, "commit_sha"))
        object.__setattr__(self, "files", _freeze_text_tuple(tuple(self.files), "files"))
        for symbol in self.symbols:
            if not isinstance(symbol, CodeSymbol):
                raise ValueError("symbols must contain CodeSymbol records")
        object.__setattr__(self, "symbols", freeze_value(list(self.symbols)))
        if not isinstance(self.test_map, TestMap):
            raise ValueError("test_map must be a TestMap")
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
        for assessment in self.risk_assessments:
            if not isinstance(assessment, FileRiskAssessment):
                raise ValueError("risk_assessments must contain FileRiskAssessment records")
        object.__setattr__(self, "risk_assessments", freeze_value(list(self.risk_assessments)))


@dataclass(frozen=True, slots=True)
class RepoIntelligenceReceipt(ContractRecord):
    """Read-only receipt proving a repository map was produced."""

    receipt_id: str
    repository: str
    commit_sha: str
    file_count: int
    symbol_count: int
    test_mapping_count: int
    dependency_edge_count: int
    route_count: int
    schema_count: int
    risk_counts: Mapping[str, int] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", require_non_empty_text(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "commit_sha", require_non_empty_text(self.commit_sha, "commit_sha"))
        object.__setattr__(self, "file_count", require_non_negative_int(self.file_count, "file_count"))
        object.__setattr__(self, "symbol_count", require_non_negative_int(self.symbol_count, "symbol_count"))
        object.__setattr__(
            self,
            "test_mapping_count",
            require_non_negative_int(self.test_mapping_count, "test_mapping_count"),
        )
        object.__setattr__(
            self,
            "dependency_edge_count",
            require_non_negative_int(self.dependency_edge_count, "dependency_edge_count"),
        )
        object.__setattr__(self, "route_count", require_non_negative_int(self.route_count, "route_count"))
        object.__setattr__(self, "schema_count", require_non_negative_int(self.schema_count, "schema_count"))
        normalized_counts: dict[str, int] = {}
        for key, value in self.risk_counts.items():
            normalized_counts[require_non_empty_text(key, "risk_counts.key")] = require_non_negative_int(
                value,
                "risk_counts.value",
            )
        object.__setattr__(self, "risk_counts", freeze_value(normalized_counts))
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
