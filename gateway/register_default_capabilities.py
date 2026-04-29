"""Gateway default capability registration.

Purpose: Provide a stable import point for installing built-in Mullu
    capability handlers into the domain-neutral dispatcher.
Governance scope: built-in financial, creative, and enterprise capability
    handler registration.
Dependencies: gateway capability dispatcher.
Invariants:
  - Registration is explicit by domain.
  - Handler installation does not grant authority by itself.
  - Registry admission remains the source of capability availability.
"""

from __future__ import annotations

from typing import Any

from gateway.capability_dispatch import (
    CapabilityDispatcher,
    register_creative_capabilities,
    register_enterprise_capabilities,
    register_financial_capabilities,
)


def register_default_capabilities(
    dispatcher: CapabilityDispatcher,
    *,
    financial_provider: Any | None = None,
    payment_executor: Any | None = None,
    knowledge_base: Any | None = None,
    notification_engine: Any | None = None,
    task_scheduler: Any | None = None,
) -> CapabilityDispatcher:
    """Register the default capability set and return the dispatcher."""
    register_financial_capabilities(
        dispatcher,
        financial_provider=financial_provider,
        payment_executor=payment_executor,
    )
    register_creative_capabilities(dispatcher)
    register_enterprise_capabilities(
        dispatcher,
        knowledge_base=knowledge_base,
        notification_engine=notification_engine,
        task_scheduler=task_scheduler,
    )
    return dispatcher
