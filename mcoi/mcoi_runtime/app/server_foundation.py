"""Foundation bootstrap helpers for the governed HTTP server.

Purpose: isolate early LLM, certification, safety, proof, and tenant-ledger
bootstrap from the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: llm bootstrap, certification services, safety services, and
tenant ledger helpers.
Invariants:
  - LLM ledger writes remain deterministic and hashed.
  - Certification daemon config stays env-driven and bounded.
  - Safety, proof, and tenant-ledger services preserve the same clock source.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Mapping

from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm
from mcoi_runtime.app.streaming import StreamingAdapter
from mcoi_runtime.core.certification_daemon import (
    CertificationConfig,
    CertificationDaemon,
)
from mcoi_runtime.governance.guards.content_safety import build_default_safety_chain
from mcoi_runtime.core.live_path_certification import LivePathCertifier
from mcoi_runtime.core.pii_scanner import PIIScanner
from mcoi_runtime.core.proof_bridge import ProofBridge
from mcoi_runtime.persistence.tenant_ledger import TenantLedger


@dataclass(frozen=True)
class FoundationServicesBootstrap:
    """Foundation bootstrap result."""

    llm_bootstrap_result: Any
    certifier: Any
    streaming_adapter: Any
    cert_daemon: Any
    pii_scanner: Any
    content_safety_chain: Any
    proof_bridge: Any
    tenant_ledger: Any


def bootstrap_foundation_services(
    *,
    clock: Callable[[], str],
    runtime_env: Mapping[str, str],
    store: Any,
    llm_config_cls: type[Any] = LLMConfig,
    bootstrap_llm_fn: Callable[..., Any] = bootstrap_llm,
    live_path_certifier_cls: type[Any] = LivePathCertifier,
    streaming_adapter_cls: type[Any] = StreamingAdapter,
    certification_config_cls: type[Any] = CertificationConfig,
    certification_daemon_cls: type[Any] = CertificationDaemon,
    pii_scanner_cls: type[Any] = PIIScanner,
    build_default_safety_chain_fn: Callable[[], Any] = build_default_safety_chain,
    proof_bridge_cls: type[Any] = ProofBridge,
    tenant_ledger_cls: type[Any] = TenantLedger,
    hashlib_module: Any = hashlib,
    json_module: Any = json,
) -> FoundationServicesBootstrap:
    """Bootstrap early foundation services for the governed server."""

    def append_hashed_ledger(
        entry_type: str,
        actor_id: str,
        tenant_id: str,
        payload: Mapping[str, Any],
    ) -> Any:
        digest = hashlib_module.sha256(
            json_module.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        return store.append_ledger(entry_type, actor_id, tenant_id, payload, digest)

    llm_bootstrap_result = bootstrap_llm_fn(
        clock=clock,
        config=llm_config_cls.from_env(),
        ledger_sink=lambda entry: append_hashed_ledger(
            entry.get("type", "llm"),
            entry.get("tenant_id", "system"),
            entry.get("tenant_id", "system"),
            entry,
        ),
    )
    llm_bridge = llm_bootstrap_result.bridge

    certifier = live_path_certifier_cls(clock=clock)
    streaming_adapter = streaming_adapter_cls(clock=clock)
    cert_daemon = certification_daemon_cls(
        certifier=certifier,
        clock=clock,
        config=certification_config_cls(
            interval_seconds=float(runtime_env.get("MULLU_CERT_INTERVAL", "300")),
            enabled=runtime_env.get("MULLU_CERT_ENABLED", "true").lower() == "true",
        ),
        api_handle_fn=lambda _req: {"governed": True, "status": "ok"},
        db_write_fn=lambda tenant_id, content: append_hashed_ledger(
            "certification",
            "certifier",
            tenant_id,
            content,
        ),
        db_read_fn=lambda tenant_id: store.query_ledger(tenant_id),
        llm_invoke_fn=lambda prompt: llm_bridge.complete(prompt, budget_id="default"),
        ledger_fn=lambda tenant_id: store.query_ledger(tenant_id),
        state_fn=lambda: (
            hashlib_module.sha256(str(store.ledger_count()).encode()).hexdigest(),
            store.ledger_count(),
        ),
    )

    pii_scanner = pii_scanner_cls(
        enabled=runtime_env.get("MULLU_PII_SCAN", "true").lower() == "true",
    )
    content_safety_chain = build_default_safety_chain_fn()
    proof_bridge = proof_bridge_cls(clock=clock)
    tenant_ledger = tenant_ledger_cls(clock=clock)

    return FoundationServicesBootstrap(
        llm_bootstrap_result=llm_bootstrap_result,
        certifier=certifier,
        streaming_adapter=streaming_adapter,
        cert_daemon=cert_daemon,
        pii_scanner=pii_scanner,
        content_safety_chain=content_safety_chain,
        proof_bridge=proof_bridge,
        tenant_ledger=tenant_ledger,
    )
