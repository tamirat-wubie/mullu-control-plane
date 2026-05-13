"""Purpose: witness agent adapter lifecycle proof surface coverage.
Governance scope: keeps the proof coverage matrix bound to adapter lifecycle
tests without duplicating the full protocol suite.
Dependencies: mcoi.tests.test_agent_adapter_protocol.
Invariants: lifecycle evidence remains reachable from a documented test entry.
"""

from __future__ import annotations

from test_agent_adapter_protocol import (
    client,
    test_action_request_allowed,
    test_action_request_propagates_goal_hierarchy,
    test_action_result_submitted,
    test_adapter_summary,
    test_agent_checkpoint_restore_roundtrip,
    test_full_governed_flow,
    test_heartbeat_registered_agent,
    test_register_agent,
)

__all__ = [
    "client",
    "test_action_request_allowed",
    "test_action_request_propagates_goal_hierarchy",
    "test_action_result_submitted",
    "test_adapter_summary",
    "test_agent_checkpoint_restore_roundtrip",
    "test_full_governed_flow",
    "test_heartbeat_registered_agent",
    "test_register_agent",
]
