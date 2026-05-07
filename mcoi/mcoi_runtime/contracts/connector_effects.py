"""Purpose: typed connector invocation receipts for observed effect assurance.
Governance scope: external connector request/response evidence only.
Dependencies: connector contracts, contract base helpers, and Python dataclasses.
Invariants: receipts bind request/response hashes, method, status, and evidence references without raw payload capture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text
from .integration import ConnectorStatus


@dataclass(frozen=True, slots=True)
class ConnectorInvocationReceipt(ContractRecord):
    """Observed external connector invocation evidence."""

    receipt_id: str
    result_id: str
    connector_id: str
    provider: str
    method: str
    url_hash: str
    request_hash: str
    response_digest: str
    status: ConnectorStatus
    evidence_ref: str
    started_at: str
    finished_at: str
    status_code: int | None = None
    error_code: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "result_id",
            "connector_id",
            "provider",
            "method",
            "url_hash",
            "request_hash",
            "response_digest",
            "evidence_ref",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            object.__setattr__(self, field_name, require_non_empty_text(value, field_name))
        if not isinstance(self.status, ConnectorStatus):
            raise ValueError("status must be a ConnectorStatus value")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        if self.status_code is not None and (
            not isinstance(self.status_code, int) or isinstance(self.status_code, bool)
        ):
            raise ValueError("status_code must be an integer when provided")
        if self.error_code is not None:
            object.__setattr__(self, "error_code", require_non_empty_text(self.error_code, "error_code"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
