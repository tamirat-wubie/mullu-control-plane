"""Purpose: verify InceptaDive metadata embedded in live assistant responses.
Governance scope: non-streaming chat and chat-workflow response envelopes,
    redaction, receipt recording, and no execution authority.
Dependencies: FastAPI TestClient, LLM chat router, and InceptaDive shadow runtime.
Invariants:
  - Assistant content remains under the normal route contract.
  - InceptaDive advisory metadata never grants execution or connector authority.
  - Raw user input and assistant content are not exposed through the advisory.
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.llm import router


def _client_with_shadow_runtime() -> tuple[TestClient, object]:
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1"})
    deps.set("inceptadive_shadow_runtime", runtime)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), runtime


def _sse_events(body: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in body.strip().split("\n\n"):
        event_type = ""
        event_data: dict[str, object] = {}
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                event_data = json.loads(line.removeprefix("data: "))
        if event_type:
            events.append((event_type, event_data))
    return events


def test_live_chat_response_embeds_redacted_inceptadive_advisory() -> None:
    client, runtime = _client_with_shadow_runtime()
    raw_marker = "live-secret-token"

    response = client.post(
        "/api/v1/chat",
        json={
            "conversation_id": "inceptadive-live-chat-1",
            "message": f"Review this production token rotation plan without exposing {raw_marker}.",
            "tenant_id": "tenant-shadow-chat",
        },
    )
    body = response.json()
    advisory = body["inceptadive_shadow_advisory"]
    results, receipts = runtime.recent_activity(limit=5)

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["content"]
    assert advisory["embedding_surface"] == "assistant_response"
    assert advisory["route"] == "/api/v1/chat"
    assert advisory["execution_authority"] is False
    assert advisory["connector_dispatch_authority"] is False
    assert advisory["shadow_memory_write_authority"] is False
    assert advisory["governance_verdict_replaced"] is False
    assert advisory["raw_request_text_exposed"] is False
    assert advisory["assistant_content_exposed"] is False
    assert advisory["private_memory_exposed"] is False
    assert raw_marker not in str(advisory)
    assert body["content"] not in str(advisory)
    assert len(results) == 1
    assert len(receipts) == 1
    assert results[0].to_dict()["execution_authority"] is False
    assert receipts[0].to_dict()["execution_authority"] is False


def test_streaming_chat_response_emits_redacted_inceptadive_advisory_event() -> None:
    client, runtime = _client_with_shadow_runtime()
    raw_marker = "stream-private-token"

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": "inceptadive-stream-chat-1",
            "message": f"Stream this release note without exposing {raw_marker}.",
            "tenant_id": "tenant-shadow-stream",
        },
    )
    events = _sse_events(response.text)
    event_names = [event_type for event_type, _data in events]
    advisory_events = [
        data for event_type, data in events if event_type == "inceptadive_shadow_advisory"
    ]
    advisory = advisory_events[0]
    results, receipts = runtime.recent_activity(limit=5)

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert event_names.count("inceptadive_shadow_advisory") == 1
    assert event_names.index("meta") < event_names.index("inceptadive_shadow_advisory")
    assert event_names.index("inceptadive_shadow_advisory") < event_names.index("done")
    assert advisory["embedding_surface"] == "assistant_response"
    assert advisory["route"] == "/api/v1/chat/stream"
    assert advisory["tenant_id"] == "tenant-shadow-stream"
    assert advisory["execution_authority"] is False
    assert advisory["connector_dispatch_authority"] is False
    assert advisory["shadow_memory_write_authority"] is False
    assert advisory["governance_verdict_replaced"] is False
    assert advisory["raw_request_text_exposed"] is False
    assert advisory["assistant_content_exposed"] is False
    assert advisory["private_memory_exposed"] is False
    assert raw_marker not in str(advisory)
    assert len(results) == 1
    assert len(receipts) == 1
    assert results[0].to_dict()["execution_authority"] is False
    assert receipts[0].to_dict()["execution_authority"] is False


def test_chat_workflow_response_embeds_redacted_inceptadive_advisory() -> None:
    client, runtime = _client_with_shadow_runtime()
    raw_marker = "workflow-private-token"

    response = client.post(
        "/api/v1/chat/workflow",
        json={
            "conversation_id": "inceptadive-workflow-chat-1",
            "message": f"Analyze this launch plan but keep {raw_marker} private.",
            "tenant_id": "tenant-shadow-workflow",
            "capability": "llm.completion",
        },
    )
    body = response.json()
    advisory = body["inceptadive_shadow_advisory"]
    results, receipts = runtime.recent_activity(limit=5)

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["response"]
    assert advisory["embedding_surface"] == "assistant_response"
    assert advisory["route"] == "/api/v1/chat/workflow"
    assert advisory["execution_authority"] is False
    assert advisory["connector_dispatch_authority"] is False
    assert advisory["shadow_memory_write_authority"] is False
    assert advisory["governance_verdict_replaced"] is False
    assert advisory["raw_request_text_exposed"] is False
    assert advisory["assistant_content_exposed"] is False
    assert advisory["private_memory_exposed"] is False
    assert raw_marker not in str(advisory)
    assert body["response"] not in str(advisory)
    assert len(results) == 1
    assert len(receipts) == 1
    assert results[0].to_dict()["execution_authority"] is False
    assert receipts[0].to_dict()["execution_authority"] is False
