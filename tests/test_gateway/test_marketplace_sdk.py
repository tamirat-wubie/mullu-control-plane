"""Gateway marketplace SDK catalog tests.

Purpose: verify certified marketplace publication, SDK export bounds, raw
surface redaction, side-effect controls, and public schema behavior.
Governance scope: marketplace listings, SDK contracts, certification evidence,
publication decisions, and fail-closed publication.
Dependencies: gateway.marketplace_sdk and marketplace_sdk_catalog schema.
Invariants:
  - Publication requires certification evidence.
  - SDK exports expose declarative schemas, not raw execution handles.
  - Write offerings require approval, receipts, and rollback.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.marketplace_sdk import (
    MarketplaceChannel,
    MarketplaceOffering,
    MarketplaceOfferingKind,
    MarketplacePublicationVerdict,
    MarketplaceSDKCatalog,
    SDKExportContract,
    SDKLanguage,
    marketplace_sdk_catalog_snapshot_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "marketplace_sdk_catalog.schema.json"
NOW = "2026-05-06T12:00:00Z"


def test_certified_connector_publishes_to_sdk_channel() -> None:
    catalog = MarketplaceSDKCatalog()
    offering = catalog.register_offering(_write_connector())
    listing, decision = catalog.publish(
        offering_id=offering.offering_id,
        channel=MarketplaceChannel.SDK,
        listed_at=NOW,
    )
    snapshot = catalog.snapshot()

    assert listing is not None
    assert decision.verdict is MarketplacePublicationVerdict.ALLOW
    assert decision.reason == "publication_controls_satisfied"
    assert decision.evidence_refs == ("cert:quickbooks", "eval:quickbooks")
    assert snapshot.published_count == 1
    assert snapshot.blocked_count == 0
    assert snapshot.sdk_contract_count == 1
    assert snapshot.raw_execution_surface_exposed is False


def test_uncertified_offering_fails_closed() -> None:
    catalog = MarketplaceSDKCatalog()
    offering = catalog.register_offering(_read_only_builder(certified=False))
    listing, decision = catalog.publish(
        offering_id=offering.offering_id,
        channel=MarketplaceChannel.INTERNAL,
        listed_at=NOW,
    )

    assert listing is None
    assert decision.verdict is MarketplacePublicationVerdict.DENY
    assert "certification_evidence_missing" in decision.missing_controls
    assert catalog.snapshot().blocked_count == 1


def test_undeclared_channel_requires_review() -> None:
    catalog = MarketplaceSDKCatalog()
    offering = catalog.register_offering(_read_only_builder(certified=True))
    listing, decision = catalog.publish(
        offering_id=offering.offering_id,
        channel=MarketplaceChannel.PUBLIC,
        listed_at=NOW,
    )

    assert listing is None
    assert decision.verdict is MarketplacePublicationVerdict.REVIEW
    assert decision.reason == "publication_controls_missing"
    assert "channel_not_declared" in decision.missing_controls
    assert catalog.snapshot().review_count == 1


def test_write_offering_requires_controls_at_source() -> None:
    with pytest.raises(ValueError, match="write_offering_requires_approval"):
        MarketplaceOffering(
            offering_id="stripe-payment",
            display_name="Stripe Payment Dispatch",
            kind=MarketplaceOfferingKind.CONNECTOR,
            version="1.0.0",
            owner_team="finance_ops",
            risk="critical",
            channels=(MarketplaceChannel.SDK,),
            side_effects=("payment_dispatch",),
            certification_evidence_refs=("cert:stripe",),
            approval_required=False,
            receipt_required=True,
            rollback_required=True,
            sdk_contract=_sdk_contract(),
        )


def test_raw_sdk_metadata_is_redacted_before_publication() -> None:
    catalog = MarketplaceSDKCatalog()
    offering = catalog.register_offering(_read_only_builder(certified=True, metadata={"raw_tool_descriptor": "hidden", "visible": "yes"}))
    listing, decision = catalog.publish(
        offering_id=offering.offering_id,
        channel=MarketplaceChannel.INTERNAL,
        listed_at=NOW,
    )
    published = catalog.snapshot().offerings[0]

    assert listing is not None
    assert decision.verdict is MarketplacePublicationVerdict.ALLOW
    assert published.metadata == {"visible": "yes"}
    assert published.sdk_contract.metadata == {"visible": "yes"}


def test_marketplace_sdk_catalog_schema_exposes_public_contract() -> None:
    catalog = MarketplaceSDKCatalog()
    offering = catalog.register_offering(_write_connector())
    catalog.publish(offering_id=offering.offering_id, channel=MarketplaceChannel.SDK, listed_at=NOW)
    snapshot = catalog.snapshot()
    payload = marketplace_sdk_catalog_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:marketplace-sdk-catalog:1"
    assert "sdk" in schema["$defs"]["channel"]["enum"]
    assert "typescript" in schema["$defs"]["language"]["enum"]
    assert payload["raw_execution_surface_exposed"] is False
    assert snapshot.snapshot_hash


def _write_connector() -> MarketplaceOffering:
    return MarketplaceOffering(
        offering_id="quickbooks-create-bill",
        display_name="QuickBooks Create Bill",
        kind=MarketplaceOfferingKind.CONNECTOR,
        version="1.0.0",
        owner_team="finance_ops",
        risk="high",
        channels=(MarketplaceChannel.SDK, MarketplaceChannel.DIRECT),
        side_effects=("financial_record_create",),
        certification_evidence_refs=("cert:quickbooks", "eval:quickbooks"),
        approval_required=True,
        receipt_required=True,
        rollback_required=True,
        sdk_contract=_sdk_contract(),
    )


def _read_only_builder(*, certified: bool, metadata: dict[str, object] | None = None) -> MarketplaceOffering:
    return MarketplaceOffering(
        offering_id="support-triage-builder",
        display_name="Support Triage Builder",
        kind=MarketplaceOfferingKind.BUILDER_APP,
        version="1.0.0",
        owner_team="support_ops",
        risk="medium",
        channels=(MarketplaceChannel.INTERNAL, MarketplaceChannel.SDK),
        side_effects=(),
        certification_evidence_refs=("cert:support-builder",) if certified else (),
        approval_required=False,
        receipt_required=True,
        rollback_required=False,
        sdk_contract=_sdk_contract(metadata=metadata),
        metadata=metadata or {},
    )


def _sdk_contract(metadata: dict[str, object] | None = None) -> SDKExportContract:
    return SDKExportContract(
        contract_id="sdk-contract-001",
        languages=(SDKLanguage.PYTHON, SDKLanguage.TYPESCRIPT, SDKLanguage.OPENAPI),
        schema_refs=("schemas/connector_result.schema.json", "schemas/capability_descriptor.schema.json"),
        auth_scopes=("tenant.read", "capability.invoke"),
        rate_limit_ref="rate-limit:standard",
        sandbox_base_url="https://sandbox.mullusi.com",
        docs_ref="docs.mullusi.com/sdk/quickbooks-create-bill",
        metadata=metadata or {},
    )
