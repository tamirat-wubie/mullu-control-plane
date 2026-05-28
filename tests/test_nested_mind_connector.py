"""Tests for the nested-mind read-only connector.

Purpose: verify route construction and governance classification for the
optional nested-mind Γ bridge.
Governance scope: read-only connector descriptor, route path safety, and
credential header forwarding boundary.
Dependencies: nested_mind adapter and canonical connector result contract.
Invariants: all operations use GET through the delegated HTTP connector, mind
identifiers cannot alter route shape, and no mutation method is exposed.
"""

from __future__ import annotations

from mcoi_runtime.adapters.nested_mind import (
    NESTED_MIND_CONNECTOR_ID,
    NestedMindConnector,
)
from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.integration import ConnectorResult, ConnectorStatus


def _clock() -> str:
    return "2026-05-28T00:00:00+00:00"


class FakeHttpConnector:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    def invoke(self, connector: object, request: dict[str, object]) -> ConnectorResult:
        self.calls.append((connector, request))
        return ConnectorResult(
            result_id="nested-result-1",
            connector_id=NESTED_MIND_CONNECTOR_ID,
            status=ConnectorStatus.SUCCEEDED,
            response_digest="0" * 64,
            started_at=_clock(),
            finished_at=_clock(),
        )


def test_read_projection_builds_root_projection_request() -> None:
    fake = FakeHttpConnector()
    connector = NestedMindConnector(
        clock=_clock,
        base_url="https://nested.example/",
        http_connector=fake,
    )

    result = connector.read_projection()

    assert result.status is ConnectorStatus.SUCCEEDED
    assert len(fake.calls) == 1
    descriptor, request = fake.calls[0]
    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.trust_class is TrustClass.BOUNDED_EXTERNAL
    assert request == {
        "url": "https://nested.example/minds/root",
        "method": "GET",
        "headers": {},
    }


def test_audit_and_replay_routes_are_read_only_get_requests() -> None:
    fake = FakeHttpConnector()
    connector = NestedMindConnector(
        clock=_clock,
        base_url="https://nested.example/api",
        http_connector=fake,
    )

    connector.verify_history("tenant-1")
    connector.replay_history("tenant-1")

    assert [call[1]["url"] for call in fake.calls] == [
        "https://nested.example/api/minds/tenant-1/audit",
        "https://nested.example/api/minds/tenant-1/replay",
    ]
    assert [call[1]["method"] for call in fake.calls] == ["GET", "GET"]


def test_bearer_token_is_forwarded_as_authorization_header_only() -> None:
    fake = FakeHttpConnector()
    connector = NestedMindConnector(
        clock=_clock,
        base_url="https://nested.example",
        bearer_token=" nested-token ",
        http_connector=fake,
    )

    connector.read_projection("root")

    assert fake.calls[0][1]["headers"] == {"Authorization": "Bearer nested-token"}


def test_rejects_mind_identifier_that_changes_route_shape() -> None:
    fake = FakeHttpConnector()
    connector = NestedMindConnector(
        clock=_clock,
        base_url="https://nested.example",
        http_connector=fake,
    )

    try:
        connector.read_projection("../root")
    except ValueError as exc:
        assert "path-segment-safe" in str(exc)
    else:
        raise AssertionError("unsafe mind identifier was accepted")

    assert fake.calls == []


def test_connector_exposes_no_mutation_methods() -> None:
    connector = NestedMindConnector(clock=_clock, base_url="https://nested.example")

    assert not hasattr(connector, "propose_edit")
    assert not hasattr(connector, "create_child_mind")
    assert connector.descriptor.metadata["mutation_routes_enabled"] is False
