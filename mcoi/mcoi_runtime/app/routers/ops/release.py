"""API version and release information endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.get("/api/v1/version")
def api_version():
    """API version info."""
    return {
        "version": "1.0.0",
        "api_version": "v1",
        "endpoints": deps.api_versions.endpoint_count,
        "summary": deps.api_versions.summary(),
        "governed": True,
    }


@router.get("/api/v1/release")
def release_info():
    """v1.0.0 release information."""
    return {
        "version": "1.0.0",
        "phase": 210,
        "endpoints": 80,
        "tests": 43800,
        "components": {
            "llm": "GovernedLLMAdapter (Anthropic/OpenAI/Stub)",
            "agents": "AgentWorkflowEngine + TracedWorkflowEngine",
            "conversations": "ConversationStore + ChatWorkflowEngine",
            "governance": "GuardChain + AuditTrail + RateLimiter + MetricsEngine",
            "observability": "ObservabilityAggregator + HealthAggregator + CostAnalytics",
            "events": "EventBus + WebhookManager",
            "pipelines": "BatchPipeline + PromptTemplateEngine",
            "plugins": "PluginRegistry (2 active)",
            "config": "ConfigManager (versioned, hot-reload, rollback)",
            "persistence": "InMemoryStore / SQLiteStore / PostgresStore",
            "replay": "ReplayRecorder + ReplayExecutor",
            "schemas": "SchemaValidator (7 rule types)",
            "tools": "ToolRegistry + ToolAugmentedAgent",
            "streaming": "AnthropicStreamingAdapter",
            "state": "StatePersistence (atomic JSON)",
            "structured_output": "StructuredOutputEngine",
            "retry": "RetryExecutor + CircuitBreaker",
        },
        "governed": True,
    }


@router.get("/api/v1/release/latest")
def latest_release():
    """Latest release information."""
    return {
        "version": "1.2.0",
        "phase": 214,
        "endpoints": 105,
        "tests": 43950,
        "highlights": [
            "Multi-model routing (auto-select by task complexity)",
            "Request correlation (trace-ID propagation)",
            "Graceful shutdown contracts",
            "Production readiness checks",
        ],
        "governed": True,
    }
