"""Purpose: verify capability helper contracts for the governed server.
Governance scope: capability helper validation tests only.
Dependencies: server capability helpers.
Invariants: capability service wiring remains deterministic and auditable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app import server_capabilities


def test_bootstrap_capability_services_registers_tools_models_and_flags() -> None:
    class FakeObservability:
        def __init__(self) -> None:
            self.sources: dict[str, object] = {}

        def register_source(self, name, source) -> None:
            self.sources[name] = source

    class FakeBudgetManager:
        def get_budget(self, tenant_id: str):
            return {"tenant-a": object(), "tenant-b": object()}.get(tenant_id)

    bridge = type(
        "Bridge",
        (),
        {
            "invocation_count": 7,
            "total_cost": 1.25,
            "complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs},
        },
    )()
    observability = FakeObservability()

    bootstrap = server_capabilities.bootstrap_capability_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={},
        llm_bridge=bridge,
        observability=observability,
        tenant_budget_mgr=FakeBudgetManager(),
        evaluate_expression_fn=lambda expression: 9 if expression == "4+5" else 0,
    )

    assert bootstrap.tool_registry.invoke("calculator", {"expression": "4+5"}).output == {
        "result": "9"
    }
    assert bootstrap.tool_registry.invoke("get_time", {}).output == {
        "time": "2026-01-01T00:00:00Z"
    }
    assert bootstrap.structured_output.summary()["schemas"] == 1
    model_ids = set(bootstrap.model_router._profiles)
    assert bootstrap.model_router.summary()["models"] >= 61
    assert {
        "gpt-4.1-nano",
        "gemini-2.0-flash-lite",
        "deepseek-v4-flash",
        "LiquidAI/LFM2-24B-A2B",
        "accounts/fireworks/models/gpt-oss-20b",
        "meta-llama/Llama-3.1-8B-Instruct",
        "llama3.1-8b",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "Meta-Llama-3.3-70B-Instruct",
        "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
        "kimi-k2.5",
        "qwen-turbo",
        "glm-4.5-air",
        "Qwen/Qwen2.5-7B-Instruct",
        "gpt-oss-120b",
        "Qwen/Qwen3-32B-TEE",
        "qwen/qwen3-coder-30b-a3b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
        "llama3-70b",
        "parasail-qwen3-32b",
        "Qwen/Qwen2.5-7B-Instruct-1M",
        "meta-llama/Llama-3.1-70B-Instruct",
        "qwen/qwen3-30b-a3b",
        "qwen/qwen3-30b-a3b:free",
        "deepseek-chat-v3",
        "Qwen/Qwen3-32B-FP8",
        "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "qwen3-coder-30b-a3b",
        "qwen3-5-9b",
        "qwen/qwen3-32b",
        "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "qwen3.6-35b",
        "qwen/qwen3.5-9b",
        "deepseek/deepseek-v4-pro",
        "glm-4.7-flash",
        "qwen35-9b",
        "google/gemma-3-27b-instruct/bf-16",
        "qwen/qwen3-coder-next",
        "gemma-4",
        "deepseek/deepseek-chat",
        "Qwen/Qwen3-Coder-30B-A3B-Instruct:cheapest",
        "nvidia/Nemotron-120B-A12B",
        "deepseek/deepseek-chat-v3-0324",
        "nscale/openai/gpt-oss-20b",
        "scaleway/gpt-oss-120b",
        "ovhcloud/Qwen3-Coder-30B-A3B-Instruct",
        "aimlapi/nvidia/nemotron-3-nano-30b-a3b",
        "infomaniak/google/gemma-4-31B-it",
        "kataleptic/gemma3-27b",
    }.issubset(model_ids)
    assert "meta-llama-3.1-8b-instruct" not in model_ids
    assert bootstrap.model_router.summary()["models"] == len(model_ids)
    assert bootstrap.feature_flags.summary() == {"total": 4, "enabled": 4, "disabled": 0}
    assert bootstrap.feature_flags.is_enabled("tool_augmentation") is True
    assert bootstrap.llm_circuit.status()["state"] == "closed"
    assert bootstrap.state_persistence.summary()["base_dir"]
    assert {"tools", "model_router", "agent_memory", "capability_manifest_registry"}.issubset(
        observability.sources
    )
    manifest_registry = bootstrap.capability_manifest_registry.read_model()
    assert manifest_registry["configured"] is False
    assert manifest_registry["manifest_count"] == 0
    assert manifest_registry["capability_abi_coverage_status"] == "empty"
    assert manifest_registry["capability_abi_coverage"] == ()
    assert observability.sources["capability_manifest_registry"]() == manifest_registry


def test_bootstrap_capability_services_wires_usage_templates_and_isolation() -> None:
    class FakeObservability:
        def register_source(self, name, source) -> None:
            return None

    class FakeBudgetManager:
        def get_budget(self, tenant_id: str):
            if tenant_id == "tenant-a":
                return {"budget": 1}
            if tenant_id == "tenant-b":
                return {"budget": 2}
            return None

    bridge = type(
        "Bridge",
        (),
        {
            "invocation_count": 11,
            "total_cost": 4.5,
            "complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs},
        },
    )()

    bootstrap = server_capabilities.bootstrap_capability_services(
        clock=lambda: "2026-01-01T00:00:00Z",
        runtime_env={"MULLU_STATE_DIR": "C:\\state"},
        llm_bridge=bridge,
        observability=FakeObservability(),
        tenant_budget_mgr=FakeBudgetManager(),
        evaluate_expression_fn=lambda expression: 0,
    )

    isolation = bootstrap.isolation_verifier.verify("tenant-a", "tenant-b")
    usage = bootstrap.usage_reporter.generate("tenant-a")
    analytics = bootstrap.tenant_analytics.compute("tenant-a")
    templates = [template.template_id for template in bootstrap.wf_templates.list_templates()]

    assert isolation.all_isolated is True
    assert bootstrap.isolation_verifier.summary()["probes_registered"] == 3
    assert usage.llm_calls == 11
    assert usage.total_cost == 4.5
    assert analytics.llm_calls == 11
    assert analytics.total_cost == 4.5
    assert bootstrap.tenant_analytics.summary()["collectors"] == ["llm_calls", "total_cost"]
    assert templates == ["research-draft", "summarize-refine"]
    assert bootstrap.dep_graph.topological_sort()[-1] == "api"
    assert bootstrap.event_store.summary()["total_events"] == 0


def test_bootstrap_capability_services_exposes_enabled_manifest_registry() -> None:
    class FakeObservability:
        def __init__(self) -> None:
            self.sources: dict[str, object] = {}

        def register_source(self, name, source) -> None:
            self.sources[name] = source

    class FakeBudgetManager:
        def get_budget(self, tenant_id: str):
            return None

    bridge = type(
        "Bridge",
        (),
        {
            "invocation_count": 0,
            "total_cost": 0.0,
            "complete": lambda self, prompt, **kwargs: {"prompt": prompt, **kwargs},
        },
    )()
    observability = FakeObservability()

    bootstrap = server_capabilities.bootstrap_capability_services(
        clock=lambda: "2026-05-13T00:00:00+00:00",
        runtime_env={
            "MULLU_CAPABILITY_MANIFEST_REGISTRY_ENABLED": "true",
            "MULLU_CAPABILITY_MANIFEST_ENVIRONMENT": "local",
        },
        llm_bridge=bridge,
        observability=observability,
        tenant_budget_mgr=FakeBudgetManager(),
        evaluate_expression_fn=lambda expression: 0,
    )

    read_model = bootstrap.capability_manifest_registry.read_model()
    assert read_model["configured"] is True
    assert read_model["manifest_count"] == 12
    assert read_model["admission_count"] == 12
    assert read_model["capability_abi_coverage_status"] == "complete"
    assert read_model["capability_abi_covered_count"] == 12
    assert read_model["capability_abi_blocked_count"] == 0
    assert "software_dev.change.run" in read_model["capability_ids"]
    assert observability.sources["capability_manifest_registry"]() == read_model


def test_capability_manifest_registry_missing_directory_error_is_bounded() -> None:
    with pytest.raises(
        ValueError,
        match="^capability manifest registry startup failed \\(directory_not_found\\)$",
    ) as exc_info:
        server_capabilities._build_capability_manifest_registry_view(
            runtime_env={
                "MULLU_CAPABILITY_MANIFEST_REGISTRY_ENABLED": "true",
                "MULLU_CAPABILITY_MANIFEST_DIR": "capabilities/software_dev/missing_manifests",
            },
            clock=lambda: "2026-05-13T00:00:00+00:00",
        )

    message = str(exc_info.value)
    assert "missing_manifests" not in message
    assert "capabilities/software_dev" not in message
