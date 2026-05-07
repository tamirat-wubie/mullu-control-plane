"""Gateway marketplace and SDK catalog foundation.

Purpose: publish certified Mullu packages, connectors, capabilities, domain
    packs, and builder outputs through SDK-safe catalog contracts.
Governance scope: marketplace listing eligibility, SDK surface bounds,
    certification evidence, publication decisions, and raw execution blocking.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - Marketplace listings require certification evidence before publication.
  - SDK exports expose declarative contracts, not raw execution handles.
  - Side-effecting offerings require approval, receipt, and rollback contracts.
  - Publication decisions are hash-bound and fail closed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class MarketplaceOfferingKind(StrEnum):
    """Catalog offering classes."""

    CAPABILITY = "capability"
    CONNECTOR = "connector"
    DOMAIN_PACK = "domain_pack"
    BUILDER_APP = "builder_app"
    WORKFLOW_TEMPLATE = "workflow_template"


class MarketplaceChannel(StrEnum):
    """Publication channel."""

    INTERNAL = "internal"
    DIRECT = "direct"
    PARTNER = "partner"
    PUBLIC = "public"
    SDK = "sdk"


class MarketplacePublicationVerdict(StrEnum):
    """Publication decision verdict."""

    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


class SDKLanguage(StrEnum):
    """SDK export language surface."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    OPENAPI = "openapi"
    MCP = "mcp"


_WRITE_SIDE_EFFECTS = frozenset({
    "payment_dispatch",
    "external_message_send",
    "financial_record_create",
    "external_write",
    "ticket_update",
})
_RAW_SURFACE_KEYS = frozenset({"raw_tool_descriptor", "execution_handle", "secret", "credential", "shell_template"})


@dataclass(frozen=True, slots=True)
class SDKExportContract:
    """SDK-facing contract for one offering."""

    contract_id: str
    languages: tuple[SDKLanguage, ...]
    schema_refs: tuple[str, ...]
    auth_scopes: tuple[str, ...]
    rate_limit_ref: str
    sandbox_base_url: str
    docs_ref: str
    contract_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("contract_id", "rate_limit_ref", "sandbox_base_url", "docs_ref"):
            _require_text(getattr(self, field_name), field_name)
        languages = tuple(self.languages)
        if not languages or any(not isinstance(language, SDKLanguage) for language in languages):
            raise ValueError("sdk_languages_required")
        object.__setattr__(self, "languages", tuple(dict.fromkeys(languages)))
        object.__setattr__(self, "schema_refs", _normalize_text_tuple(self.schema_refs, "schema_refs"))
        object.__setattr__(self, "auth_scopes", _normalize_text_tuple(self.auth_scopes, "auth_scopes"))
        object.__setattr__(self, "metadata", _bounded_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class MarketplaceOffering:
    """Certified candidate for marketplace publication."""

    offering_id: str
    display_name: str
    kind: MarketplaceOfferingKind
    version: str
    owner_team: str
    risk: str
    channels: tuple[MarketplaceChannel, ...]
    side_effects: tuple[str, ...]
    certification_evidence_refs: tuple[str, ...]
    approval_required: bool
    receipt_required: bool
    rollback_required: bool
    sdk_contract: SDKExportContract
    offering_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("offering_id", "display_name", "version", "owner_team", "risk"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.kind, MarketplaceOfferingKind):
            raise ValueError("marketplace_offering_kind_invalid")
        channels = tuple(self.channels)
        if not channels or any(not isinstance(channel, MarketplaceChannel) for channel in channels):
            raise ValueError("marketplace_channels_required")
        object.__setattr__(self, "channels", tuple(dict.fromkeys(channels)))
        object.__setattr__(self, "side_effects", _normalize_text_tuple(self.side_effects, "side_effects", allow_empty=True))
        object.__setattr__(self, "certification_evidence_refs", _normalize_text_tuple(self.certification_evidence_refs, "certification_evidence_refs", allow_empty=True))
        if not isinstance(self.sdk_contract, SDKExportContract):
            raise ValueError("sdk_contract_required")
        if _has_write_side_effect(self):
            if self.approval_required is not True:
                raise ValueError("write_offering_requires_approval")
            if self.receipt_required is not True:
                raise ValueError("write_offering_requires_receipt")
            if self.rollback_required is not True:
                raise ValueError("write_offering_requires_rollback")
        object.__setattr__(self, "metadata", _bounded_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class MarketplaceListing:
    """Channel listing for one offering."""

    listing_id: str
    offering_id: str
    channel: MarketplaceChannel
    listed_at: str
    active: bool
    listing_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("listing_id", "offering_id", "listed_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.channel, MarketplaceChannel):
            raise ValueError("marketplace_channel_invalid")
        if not isinstance(self.active, bool):
            raise ValueError("listing_active_boolean_required")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class MarketplacePublicationDecision:
    """Publication decision for one offering/channel pair."""

    decision_id: str
    offering_id: str
    channel: MarketplaceChannel
    verdict: MarketplacePublicationVerdict
    reason: str
    missing_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "offering_id", "reason"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.channel, MarketplaceChannel):
            raise ValueError("marketplace_channel_invalid")
        if not isinstance(self.verdict, MarketplacePublicationVerdict):
            raise ValueError("marketplace_publication_verdict_invalid")
        object.__setattr__(self, "missing_controls", _normalize_text_tuple(self.missing_controls, "missing_controls", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class MarketplaceSDKCatalogSnapshot:
    """Operator read model for marketplace and SDK publication state."""

    catalog_id: str
    offerings: tuple[MarketplaceOffering, ...]
    listings: tuple[MarketplaceListing, ...]
    decisions: tuple[MarketplacePublicationDecision, ...]
    published_count: int
    blocked_count: int
    review_count: int
    sdk_contract_count: int
    raw_execution_surface_exposed: bool
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.catalog_id, "catalog_id")
        object.__setattr__(self, "offerings", tuple(self.offerings))
        object.__setattr__(self, "listings", tuple(self.listings))
        object.__setattr__(self, "decisions", tuple(self.decisions))
        for field_name in ("published_count", "blocked_count", "review_count", "sdk_contract_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name}_non_negative")
        if self.raw_execution_surface_exposed is not False:
            raise ValueError("raw_execution_surface_must_not_be_exposed")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class MarketplaceSDKCatalog:
    """In-memory marketplace and SDK catalog publisher."""

    def __init__(self, *, catalog_id: str = "marketplace-sdk-catalog") -> None:
        self._catalog_id = catalog_id
        self._offerings: dict[str, MarketplaceOffering] = {}
        self._listings: dict[str, MarketplaceListing] = {}
        self._decisions: list[MarketplacePublicationDecision] = []

    def register_offering(self, offering: MarketplaceOffering) -> MarketplaceOffering:
        """Register a stamped offering candidate."""
        stamped_contract = _stamp_contract(offering.sdk_contract)
        stamped = _stamp_offering(replace(offering, sdk_contract=stamped_contract))
        self._offerings[stamped.offering_id] = stamped
        return stamped

    def publish(
        self,
        *,
        offering_id: str,
        channel: MarketplaceChannel,
        listed_at: str,
    ) -> tuple[MarketplaceListing | None, MarketplacePublicationDecision]:
        """Publish one offering to one channel if controls are satisfied."""
        _require_text(offering_id, "offering_id")
        _require_text(listed_at, "listed_at")
        if not isinstance(channel, MarketplaceChannel):
            raise ValueError("marketplace_channel_invalid")
        offering = self._offerings.get(offering_id)
        if offering is None:
            return None, self._decision(offering_id, channel, MarketplacePublicationVerdict.DENY, "offering_missing", ("registered_offering",), ())
        missing = _missing_publication_controls(offering, channel)
        if missing:
            verdict = MarketplacePublicationVerdict.REVIEW if "channel_not_declared" in missing else MarketplacePublicationVerdict.DENY
            return None, self._decision(offering_id, channel, verdict, "publication_controls_missing", missing, offering.certification_evidence_refs)
        listing = _stamp_listing(MarketplaceListing(
            listing_id=f"listing-{canonical_hash({'offering_id': offering_id, 'channel': channel.value, 'listed_at': listed_at})[:16]}",
            offering_id=offering_id,
            channel=channel,
            listed_at=listed_at,
            active=True,
        ))
        self._listings[listing.listing_id] = listing
        decision = self._decision(offering_id, channel, MarketplacePublicationVerdict.ALLOW, "publication_controls_satisfied", (), offering.certification_evidence_refs)
        return listing, decision

    def snapshot(self) -> MarketplaceSDKCatalogSnapshot:
        """Return a stamped marketplace SDK snapshot."""
        snapshot = MarketplaceSDKCatalogSnapshot(
            catalog_id=self._catalog_id,
            offerings=tuple(sorted(self._offerings.values(), key=lambda item: item.offering_id)),
            listings=tuple(sorted(self._listings.values(), key=lambda item: item.listing_id)),
            decisions=tuple(self._decisions),
            published_count=len(self._listings),
            blocked_count=sum(1 for decision in self._decisions if decision.verdict == MarketplacePublicationVerdict.DENY),
            review_count=sum(1 for decision in self._decisions if decision.verdict == MarketplacePublicationVerdict.REVIEW),
            sdk_contract_count=len(self._offerings),
            raw_execution_surface_exposed=False,
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _decision(
        self,
        offering_id: str,
        channel: MarketplaceChannel,
        verdict: MarketplacePublicationVerdict,
        reason: str,
        missing_controls: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> MarketplacePublicationDecision:
        decision = MarketplacePublicationDecision(
            decision_id="pending",
            offering_id=offering_id or "unknown",
            channel=channel,
            verdict=verdict,
            reason=reason,
            missing_controls=missing_controls,
            evidence_refs=evidence_refs,
        )
        payload = decision.to_json_dict()
        payload["decision_hash"] = ""
        decision_hash = canonical_hash(payload)
        stamped = replace(decision, decision_id=f"marketplace-decision-{decision_hash[:16]}", decision_hash=decision_hash)
        self._decisions.append(stamped)
        return stamped


def marketplace_sdk_catalog_snapshot_to_json_dict(snapshot: MarketplaceSDKCatalogSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of marketplace SDK state."""
    return snapshot.to_json_dict()


def _missing_publication_controls(offering: MarketplaceOffering, channel: MarketplaceChannel) -> tuple[str, ...]:
    missing: list[str] = []
    if channel not in offering.channels:
        missing.append("channel_not_declared")
    if not offering.certification_evidence_refs:
        missing.append("certification_evidence_missing")
    if not offering.sdk_contract.contract_hash:
        missing.append("sdk_contract_hash_missing")
    if _has_write_side_effect(offering):
        if not offering.approval_required:
            missing.append("approval_required")
        if not offering.receipt_required:
            missing.append("receipt_required")
        if not offering.rollback_required:
            missing.append("rollback_required")
    return tuple(dict.fromkeys(missing))


def _has_write_side_effect(offering: MarketplaceOffering) -> bool:
    return bool(set(offering.side_effects).intersection(_WRITE_SIDE_EFFECTS))


def _stamp_contract(contract: SDKExportContract) -> SDKExportContract:
    payload = contract.to_json_dict()
    payload["contract_hash"] = ""
    return replace(contract, contract_hash=canonical_hash(payload))


def _stamp_offering(offering: MarketplaceOffering) -> MarketplaceOffering:
    payload = offering.to_json_dict()
    payload["offering_hash"] = ""
    return replace(offering, offering_hash=canonical_hash(payload))


def _stamp_listing(listing: MarketplaceListing) -> MarketplaceListing:
    payload = listing.to_json_dict()
    payload["listing_hash"] = ""
    return replace(listing, listing_hash=canonical_hash(payload))


def _bounded_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in dict(metadata).items() if str(key) not in _RAW_SURFACE_KEYS}


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
