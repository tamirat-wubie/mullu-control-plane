"""Phase 204D — Plugin system tests."""

import pytest
from mcoi_runtime.core.plugin_system import (
    HookPoint, PluginDescriptor, PluginInstance, PluginRegistry, PluginStatus,
)


class TestPluginRegistry:
    def test_register(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(plugin_id="p1", name="Plugin 1", version="1.0")
        instance = reg.register(desc)
        assert instance.status == PluginStatus.REGISTERED

    def test_duplicate_register(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(plugin_id="p1", name="P1", version="1.0")
        reg.register(desc)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(desc)

    def test_load(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(
            plugin_id="p1", name="P1", version="1.0",
            hooks=(HookPoint.PRE_LLM_CALL,),
        )
        reg.register(desc)
        instance = reg.load("p1", hooks={HookPoint.PRE_LLM_CALL: lambda **kw: "ok"})
        assert instance.status == PluginStatus.LOADED

    def test_load_undeclared_hook(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(plugin_id="p1", name="P1", version="1.0", hooks=())
        reg.register(desc)
        with pytest.raises(ValueError, match="^plugin hook not declared$"):
            reg.load("p1", hooks={HookPoint.PRE_LLM_CALL: lambda **kw: None})

    def test_load_missing_dependency(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(
            plugin_id="p2", name="P2", version="1.0", dependencies=("p1",),
        )
        reg.register(desc)
        with pytest.raises(ValueError, match="dependency not loaded"):
            reg.load("p2")

    def test_load_with_dependency(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        reg.load("p1")
        reg.register(PluginDescriptor(
            plugin_id="p2", name="P2", version="1.0", dependencies=("p1",),
        ))
        instance = reg.load("p2")
        assert instance.status == PluginStatus.LOADED

    def test_activate(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        reg.load("p1")
        instance = reg.activate("p1")
        assert instance.status == PluginStatus.ACTIVE

    def test_activate_unloaded(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        with pytest.raises(ValueError, match="^plugin must be loaded before activation$"):
            reg.activate("p1")

    def test_disable(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        reg.load("p1")
        reg.activate("p1")
        assert reg.disable("p1") is True
        assert reg.get("p1").status == PluginStatus.DISABLED

    def test_dispatch_hook(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(
            plugin_id="p1", name="P1", version="1.0",
            hooks=(HookPoint.PRE_LLM_CALL,),
        )
        reg.register(desc)
        call_log = []
        reg.load("p1", hooks={HookPoint.PRE_LLM_CALL: lambda **kw: call_log.append("called")})
        reg.activate("p1")
        results = reg.dispatch_hook(HookPoint.PRE_LLM_CALL)
        assert len(call_log) == 1

    def test_dispatch_skips_disabled(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(
            plugin_id="p1", name="P1", version="1.0",
            hooks=(HookPoint.PRE_LLM_CALL,),
        )
        reg.register(desc)
        reg.load("p1", hooks={HookPoint.PRE_LLM_CALL: lambda **kw: "result"})
        reg.activate("p1")
        reg.disable("p1")
        results = reg.dispatch_hook(HookPoint.PRE_LLM_CALL)
        assert len(results) == 0

    def test_dispatch_error_marks_errored(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(
            plugin_id="p1", name="P1", version="1.0",
            hooks=(HookPoint.ON_ERROR,),
        )
        reg.register(desc)
        reg.load("p1", hooks={HookPoint.ON_ERROR: lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))})
        reg.activate("p1")
        results = reg.dispatch_hook(HookPoint.ON_ERROR)
        assert reg.get("p1").status == PluginStatus.ERRORED
        assert reg.get("p1").error == "plugin hook error (RuntimeError)"
        assert results[0]["error"] == "plugin hook error (RuntimeError)"
        assert "boom" not in reg.get("p1").error

    def test_list_plugins(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p2", name="P2", version="1.0"))
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        plugins = reg.list_plugins()
        assert plugins[0].descriptor.plugin_id == "p1"

    def test_active_plugins(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        reg.register(PluginDescriptor(plugin_id="p2", name="P2", version="1.0"))
        reg.load("p1")
        reg.activate("p1")
        assert len(reg.active_plugins()) == 1

    def test_summary(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="p1", name="P1", version="1.0"))
        reg.load("p1")
        reg.activate("p1")
        summary = reg.summary()
        assert summary["total"] == 1
        assert summary["active"] == 1


class TestBoundedPluginRegistryContracts:
    def test_registry_errors_are_bounded(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(plugin_id="plugin-secret", name="P1", version="1.0")
        reg.register(desc)

        with pytest.raises(ValueError, match="^plugin already registered$") as exc_info:
            reg.register(desc)
        assert "plugin-secret" not in str(exc_info.value)

        with pytest.raises(ValueError, match="^plugin not found$") as exc_info:
            reg.load("missing-plugin")
        assert "missing-plugin" not in str(exc_info.value)

    def test_dependency_and_activation_errors_are_bounded(self):
        reg = PluginRegistry()
        reg.register(PluginDescriptor(plugin_id="plugin-secret", name="P1", version="1.0"))
        reg.register(PluginDescriptor(plugin_id="plugin-dependent", name="P2", version="1.0", dependencies=("plugin-secret",)))

        with pytest.raises(ValueError, match="^plugin dependency not loaded$") as exc_info:
            reg.load("plugin-dependent")
        assert "plugin-secret" not in str(exc_info.value)

        with pytest.raises(ValueError, match="^plugin must be loaded before activation$") as exc_info:
            reg.activate("plugin-secret")
        assert "registered" not in str(exc_info.value)
        assert "plugin-secret" not in str(exc_info.value)

    def test_hook_declaration_errors_are_bounded(self):
        reg = PluginRegistry()
        desc = PluginDescriptor(plugin_id="plugin-secret", name="P1", version="1.0", hooks=())
        reg.register(desc)
        with pytest.raises(ValueError, match="^plugin hook not declared$") as exc_info:
            reg.load("plugin-secret", hooks={HookPoint.PRE_LLM_CALL: lambda **kw: None})
        assert "plugin-secret" not in str(exc_info.value)
        assert "PRE_LLM_CALL" not in str(exc_info.value)
