"""Purpose: assistant inbox item normalization.
Governance scope: source identity, channel boundaries, tenant/owner scope, and
    evidence references for downstream planning.
Dependencies: dataclasses and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Inbox items are observations, not action authority.
  - Every item declares channel, source, tenant, owner, and evidence.
  - External message bodies are kept behind source references when possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


INBOX_CHANNELS = ("email", "calendar", "sms", "chat", "voice", "document", "task")


@dataclass(frozen=True, slots=True)
class AssistantInboxItem:
    """Governed observation item available to assistant planning."""

    item_id: str
    tenant_id: str
    owner_id: str
    channel: str
    source_ref: str
    received_at: str
    summary: str
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", ensure_non_empty_text("item_id", self.item_id))
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "owner_id", ensure_non_empty_text("owner_id", self.owner_id))
        if self.channel not in INBOX_CHANNELS:
            raise RuntimeCoreInvariantError("inbox channel is not admitted")
        object.__setattr__(self, "source_ref", ensure_non_empty_text("source_ref", self.source_ref))
        object.__setattr__(self, "received_at", ensure_non_empty_text("received_at", self.received_at))
        object.__setattr__(self, "summary", ensure_non_empty_text("summary", self.summary))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


def make_inbox_item(
    *,
    tenant_id: str,
    owner_id: str,
    channel: str,
    source_ref: str,
    received_at: str,
    summary: str,
    evidence_refs: tuple[str, ...],
    metadata: dict[str, Any] | None = None,
) -> AssistantInboxItem:
    """Create a stable inbox observation item."""
    item_id = stable_identifier(
        "assistant-inbox",
        {
            "tenant_id": tenant_id,
            "owner_id": owner_id,
            "channel": channel,
            "source_ref": source_ref,
            "received_at": received_at,
        },
    )
    return AssistantInboxItem(
        item_id=item_id,
        tenant_id=tenant_id,
        owner_id=owner_id,
        channel=channel,
        source_ref=source_ref,
        received_at=received_at,
        summary=summary,
        evidence_refs=evidence_refs,
        metadata=metadata or {},
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized
