"""Purpose: env-driven persistence wiring for job conversation-thread indexes.
Governance scope: served-runtime WHQR clarification thread replay persistence only.
Dependencies: hosted path validation, conversation thread store, conversation contracts.
Invariants:
  - Persistence is opt-in through an explicit absolute JSON store path.
  - Startup restore is read-only and fails closed on malformed existing stores.
  - Shutdown snapshot writes the current dependency index without changing thread semantics.
  - Missing configured files restore as an empty index for first boot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from mcoi_runtime.contracts.conversation import ConversationThread
from mcoi_runtime.persistence.conversation_thread_store import ConversationThreadStore

from ._integration_paths import validate_hosted_store_path

JOB_CONVERSATION_THREAD_STORE_PATH_ENV = "MULLU_JOB_CONVERSATION_THREAD_STORE_PATH"


@dataclass(frozen=True, slots=True)
class JobConversationThreadBootstrap:
    """Served-runtime job conversation thread persistence wiring."""

    store: ConversationThreadStore | None
    thread_index: dict[str, ConversationThread]
    save_on_shutdown: Callable[[], Mapping[str, object]] | None


def bootstrap_job_conversation_threads(
    runtime_env: Mapping[str, object],
) -> JobConversationThreadBootstrap:
    """Select optional persistence and restore the job conversation-thread index."""

    raw_value = runtime_env.get(JOB_CONVERSATION_THREAD_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return JobConversationThreadBootstrap(
            store=None,
            thread_index={},
            save_on_shutdown=None,
        )

    path = validate_job_conversation_thread_store_path(str(raw_value).strip())
    store = ConversationThreadStore(path)
    thread_index = store.load_index(allow_missing=True)

    def _save_on_shutdown() -> Mapping[str, object]:
        store.save_index(thread_index)
        return {
            "store_configured": True,
            "thread_count": len(thread_index),
        }

    return JobConversationThreadBootstrap(
        store=store,
        thread_index=thread_index,
        save_on_shutdown=_save_on_shutdown,
    )


def validate_job_conversation_thread_store_path(store_path: str | Path) -> Path:
    """Validate hosted job conversation-thread store path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=JOB_CONVERSATION_THREAD_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
