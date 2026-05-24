"""Purpose: typed knowledge records governed by learning admission.
Governance scope: runtime knowledge typing only.
Dependencies: evidence records and learning admission boundary docs.
Invariants: knowledge identity stays explicit before admission decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TypeVar, cast

from ._base import ContractRecord, freeze_value, require_non_empty_text
from .evidence import EvidenceRecord


ContractT = TypeVar("ContractT", bound=ContractRecord)


def _freeze_contract_array(
    values: object,
    field_name: str,
    record_type: type[ContractT],
    *,
    allow_empty: bool = True,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[Any, ...], freeze_value(list(values)))
    if not allow_empty and not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    for idx, value in enumerate(frozen):
        if not isinstance(value, record_type):
            raise ValueError(f"{field_name}[{idx}] must be a {record_type.__name__}")
    return cast(tuple[ContractT, ...], frozen)


@dataclass(frozen=True, slots=True)
class KnowledgeRecord(ContractRecord):
    knowledge_id: str
    subject_id: str
    content_hash: str
    evidence: tuple[EvidenceRecord, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("knowledge_id", "subject_id", "content_hash"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "evidence", _freeze_contract_array(self.evidence, "evidence", EvidenceRecord))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))
