"""Purpose: marketplace runtime integration bridge.
Governance scope: composing marketplace runtime with product releases,
    customer accounts, partner channels, contract terms, billing, entitlements;
    memory mesh and graph attachment.
Dependencies: marketplace_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every marketplace action emits events.
  - Marketplace state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.marketplace_runtime import (
    MarketplaceChannel,
    OfferingKind,
    PricingDisposition,
)
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .marketplace_runtime import MarketplaceRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-mktint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MarketplaceRuntimeIntegration:
    """Integration bridge for marketplace runtime with platform layers."""

    def __init__(
        self,
        marketplace_engine: MarketplaceRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(marketplace_engine, MarketplaceRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "marketplace_engine must be a MarketplaceRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._marketplace = marketplace_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Offering from platform layers
    # ------------------------------------------------------------------

    def offering_from_product_release(
        self,
        offering_id: str,
        product_id: str,
        tenant_id: str,
        display_name: str,
        version_ref: str,
        kind: OfferingKind = OfferingKind.STANDALONE,
    ) -> dict[str, Any]:
        offering = self._marketplace.register_offering(
            offering_id=offering_id, product_id=product_id, tenant_id=tenant_id,
            display_name=display_name, kind=kind, version_ref=version_ref,
        )
        self._marketplace.activate_offering(offering_id)
        _emit(self._events, "offering_from_product_release", {
            "offering_id": offering_id, "version_ref": version_ref,
        }, offering_id)
        return {
            "offering_id": offering.offering_id,
            "product_id": product_id,
            "tenant_id": tenant_id,
            "version_ref": version_ref,
            "kind": kind.value,
            "source_type": "product_release",
        }

    def offering_from_customer_account(
        self,
        offering_id: str,
        product_id: str,
        tenant_id: str,
        display_name: str,
        account_ref: str,
        kind: OfferingKind = OfferingKind.CUSTOM,
    ) -> dict[str, Any]:
        offering = self._marketplace.register_offering(
            offering_id=offering_id, product_id=product_id, tenant_id=tenant_id,
            display_name=display_name, kind=kind,
        )
        _emit(self._events, "offering_from_customer_account", {
            "offering_id": offering_id, "account_ref": account_ref,
        }, offering_id)
        return {
            "offering_id": offering.offering_id,
            "product_id": product_id,
            "tenant_id": tenant_id,
            "account_ref": account_ref,
            "kind": kind.value,
            "source_type": "customer_account",
        }

    def offering_from_partner_channel(
        self,
        offering_id: str,
        listing_id: str,
        product_id: str,
        tenant_id: str,
        display_name: str,
        partner_ref: str,
        channel: MarketplaceChannel = MarketplaceChannel.PARTNER,
    ) -> dict[str, Any]:
        offering = self._marketplace.register_offering(
            offering_id=offering_id, product_id=product_id, tenant_id=tenant_id,
            display_name=display_name, kind=OfferingKind.STANDALONE,
        )
        self._marketplace.activate_offering(offering_id)
        listing = self._marketplace.create_listing(
            listing_id=listing_id, offering_id=offering_id, tenant_id=tenant_id,
            channel=channel,
        )
        _emit(self._events, "offering_from_partner_channel", {
            "offering_id": offering_id, "listing_id": listing_id, "partner_ref": partner_ref,
        }, offering_id)
        return {
            "offering_id": offering.offering_id,
            "listing_id": listing.listing_id,
            "product_id": product_id,
            "tenant_id": tenant_id,
            "partner_ref": partner_ref,
            "channel": channel.value,
            "source_type": "partner_channel",
        }

    def offering_from_contract_terms(
        self,
        offering_id: str,
        product_id: str,
        tenant_id: str,
        display_name: str,
        contract_ref: str,
        base_price: float,
        effective_price: float = 0.0,
        disposition: PricingDisposition = PricingDisposition.NEGOTIATED,
    ) -> dict[str, Any]:
        offering = self._marketplace.register_offering(
            offering_id=offering_id, product_id=product_id, tenant_id=tenant_id,
            display_name=display_name, kind=OfferingKind.CUSTOM,
        )
        binding_id = stable_identifier("pb", {"offering_id": offering_id, "contract_ref": contract_ref})
        binding = self._marketplace.bind_pricing(
            binding_id=binding_id, offering_id=offering_id, tenant_id=tenant_id,
            base_price=base_price, effective_price=effective_price,
            disposition=disposition, contract_ref=contract_ref,
        )
        _emit(self._events, "offering_from_contract_terms", {
            "offering_id": offering_id, "contract_ref": contract_ref,
        }, offering_id)
        return {
            "offering_id": offering.offering_id,
            "binding_id": binding.binding_id,
            "product_id": product_id,
            "tenant_id": tenant_id,
            "contract_ref": contract_ref,
            "base_price": base_price,
            "effective_price": binding.effective_price,
            "source_type": "contract_terms",
        }

    def bind_pricing_from_billing(
        self,
        binding_id: str,
        offering_id: str,
        tenant_id: str,
        base_price: float,
        billing_ref: str,
        disposition: PricingDisposition = PricingDisposition.STANDARD,
    ) -> dict[str, Any]:
        binding = self._marketplace.bind_pricing(
            binding_id=binding_id, offering_id=offering_id, tenant_id=tenant_id,
            base_price=base_price, disposition=disposition, contract_ref=billing_ref,
        )
        _emit(self._events, "bind_pricing_from_billing", {
            "binding_id": binding_id, "billing_ref": billing_ref,
        }, binding_id)
        return {
            "binding_id": binding.binding_id,
            "offering_id": offering_id,
            "tenant_id": tenant_id,
            "base_price": base_price,
            "effective_price": binding.effective_price,
            "billing_ref": billing_ref,
            "source_type": "billing",
        }

    def bind_eligibility_from_entitlements(
        self,
        rule_id: str,
        offering_id: str,
        tenant_id: str,
        account_segment: str,
        has_entitlement: bool,
    ) -> dict[str, Any]:
        rule = self._marketplace.evaluate_eligibility(
            rule_id=rule_id, offering_id=offering_id, tenant_id=tenant_id,
            account_segment=account_segment, has_entitlement=has_entitlement,
        )
        _emit(self._events, "bind_eligibility_from_entitlements", {
            "rule_id": rule_id, "eligible": has_entitlement,
        }, rule_id)
        return {
            "rule_id": rule.rule_id,
            "offering_id": offering_id,
            "tenant_id": tenant_id,
            "account_segment": account_segment,
            "status": rule.status.value,
            "has_entitlement": has_entitlement,
            "source_type": "entitlements",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_marketplace_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-mkt", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)})
        content = {
            "offerings": self._marketplace.offering_count,
            "packages": self._marketplace.package_count,
            "bundles": self._marketplace.bundle_count,
            "listings": self._marketplace.listing_count,
            "eligibility_rules": self._marketplace.eligibility_rule_count,
            "pricing_bindings": self._marketplace.pricing_binding_count,
            "assessments": self._marketplace.assessment_count,
            "violations": self._marketplace.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            memory_type=MemoryType.OBSERVATION,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Marketplace runtime state",
            content=content,
            tags=("marketplace", "offering", "packaging"),
            source_ids=(scope_ref_id,),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_marketplace_to_memory", {"memory_id": mid}, mid)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_marketplace_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "offerings": self._marketplace.offering_count,
            "packages": self._marketplace.package_count,
            "bundles": self._marketplace.bundle_count,
            "listings": self._marketplace.listing_count,
            "eligibility_rules": self._marketplace.eligibility_rule_count,
            "pricing_bindings": self._marketplace.pricing_binding_count,
            "assessments": self._marketplace.assessment_count,
            "violations": self._marketplace.violation_count,
        }
