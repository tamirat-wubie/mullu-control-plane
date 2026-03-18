"""Purpose: typed evidence records used by observer and verification surfaces.
Governance scope: runtime contract typing only.
Dependencies: shared verification semantics and contract base helpers.
Invariants: evidence stays explicit and serialization remains stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._base import ContractRecord, freeze_value, require_non_empty_text


@dataclass(frozen=True, slots=True)
class EvidenceRecord(ContractRecord):
    description: str
    uri: str | None = None
    details: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if self.uri is not None:
            object.__setattr__(self, "uri", require_non_empty_text(self.uri, "uri"))
        object.__setattr__(self, "details", freeze_value(self.details))
