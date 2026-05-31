"""Static regression tests for nested-mind server wiring.

Purpose: verify that server.py mounts the optional nested-mind connector through
its integration helper instead of bypassing the env-driven bootstrap boundary.
Governance scope: default-off runtime registration and dependency-container
surface for the read-only nested-mind Γ bridge.
Dependencies: source inspection only; this test intentionally does not import
server.py because module import performs full control-plane startup wiring.
Invariants: server.py calls mount_nested_mind_connector_from_env, always
registers bootstrap posture, and registers the connector only when enabled.
"""

from __future__ import annotations

from pathlib import Path

_SERVER_PATH = (
    Path(__file__).resolve().parent.parent
    / "mcoi"
    / "mcoi_runtime"
    / "app"
    / "server.py"
)


def _server_source() -> str:
    return _SERVER_PATH.read_text(encoding="utf-8")


def test_server_imports_nested_mind_integration_helper() -> None:
    source = _server_source()

    assert "from mcoi_runtime.app.nested_mind_integration import (" in source
    assert "mount_nested_mind_connector_from_env" in source
    assert "mount_nested_mind_observation_bridge_from_env" in source
    assert "mount_nested_mind_observation_submitter_from_env" in source


def test_server_registers_nested_mind_bootstrap_and_enabled_connector() -> None:
    source = _server_source()

    assert "nested_mind_bootstrap = mount_nested_mind_connector_from_env(" in source
    assert "runtime_env=os.environ" in source
    assert "clock=_clock" in source
    assert 'deps.set("nested_mind_bootstrap", nested_mind_bootstrap)' in source
    assert "if nested_mind_bootstrap.connector is not None:" in source
    assert (
        'deps.set("nested_mind_connector", nested_mind_bootstrap.connector)'
        in source
    )


def test_server_registers_nested_mind_observation_bridge_and_submitter() -> None:
    source = _server_source()

    assert (
        "nested_mind_observation_bridge_bootstrap = "
        "mount_nested_mind_observation_bridge_from_env("
    ) in source
    assert (
        'deps.set(\n    "nested_mind_observation_bridge_bootstrap",'
    ) in source
    assert (
        'deps.set(\n    "nested_mind_observation_bridge_planner",'
    ) in source
    assert (
        "nested_mind_observation_submitter_bootstrap = "
        "mount_nested_mind_observation_submitter_from_env("
    ) in source
    assert (
        'deps.set(\n    "nested_mind_observation_submitter_bootstrap",'
    ) in source
    assert "if nested_mind_observation_submitter_bootstrap.submitter is not None:" in source
    assert (
        'deps.set(\n        "nested_mind_observation_submitter",'
    ) in source


def test_nested_mind_wiring_runs_after_note_memory_and_before_god_mode() -> None:
    source = _server_source()

    note_memory_index = source.index("note_memory_bootstrap = mount_note_memory_router_from_env")
    nested_mind_index = source.index("nested_mind_bootstrap = mount_nested_mind_connector_from_env")
    bridge_index = source.index("nested_mind_observation_bridge_bootstrap = mount_nested_mind_observation_bridge_from_env")
    submitter_index = source.index("nested_mind_observation_submitter_bootstrap = mount_nested_mind_observation_submitter_from_env")
    god_mode_index = source.index("from mcoi_runtime.core.god_mode_integration import install_god_mode")

    assert note_memory_index < nested_mind_index < bridge_index < submitter_index < god_mode_index
