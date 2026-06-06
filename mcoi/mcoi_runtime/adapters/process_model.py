"""Purpose: local-process model provider — wraps a local CLI/process as a model adapter.
Governance scope: model orchestration adapter only.
Dependencies: model contracts, subprocess.
Invariants:
  - Bounded timeout on subprocess execution.
  - Response is digested, not stored raw.
  - Validation status starts as pending.
  - No direct trust of model output.
"""

from __future__ import annotations

from typing import Callable, Mapping

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from types import MappingProxyType

from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)
from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


_DEFAULT_MAX_OUTPUT_BYTES: int = 1_048_576  # 1 MB
_TRUNCATION_MARKER: str = "\n[TRUNCATED at {limit} bytes]"
_LOCALE_BASELINE: dict[str, str] = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}
_PLATFORM_PASSTHROUGH_KEYS: tuple[str, ...] = (
    ("PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP", "WINDIR")
    if os.name == "nt"
    else ("PATH", "HOME", "TMPDIR")
)


def _truncate_output(text: str | None, max_bytes: int) -> str:
    """Truncate output to max_bytes, appending a marker if truncated."""
    if text is None:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
    return truncated + _TRUNCATION_MARKER.format(limit=max_bytes)


def _bounded_process_error(exc: Exception) -> str:
    """Return a stable process-model failure without raw backend detail."""
    return f"process model error ({type(exc).__name__})"


def _minimal_process_environment(extra_environment: Mapping[str, str]) -> dict[str, str]:
    """Build a credential-scrubbed environment for local process model execution."""
    process_environment: dict[str, str] = dict(_LOCALE_BASELINE)
    for key in _PLATFORM_PASSTHROUGH_KEYS:
        value = os.environ.get(key)
        if value is not None:
            process_environment[key] = value
    process_environment.update(dict(extra_environment))
    return process_environment


def _build_process_environment(config: "ProcessModelConfig") -> dict[str, str] | None:
    explicit_environment = dict(config.environment)
    if config.allow_inherited_environment:
        if not explicit_environment:
            return None
        inherited_environment = dict(os.environ)
        inherited_environment.update(explicit_environment)
        return inherited_environment
    return _minimal_process_environment(explicit_environment)


@dataclass(frozen=True, slots=True)
class ProcessModelConfig:
    """Configuration for a local process model adapter."""

    command: tuple[str, ...]
    timeout_seconds: float = 60.0
    cost_per_invocation: float = 0.0
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES
    environment: Mapping[str, str] = field(default_factory=dict)
    allow_inherited_environment: bool = False

    def __post_init__(self) -> None:
        if not self.command:
            raise ValueError("command must contain at least one element")
        for i, part in enumerate(self.command):
            ensure_non_empty_text(f"command[{i}]", part)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.cost_per_invocation < 0:
            raise ValueError("cost_per_invocation must be non-negative")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if not isinstance(self.allow_inherited_environment, bool):
            raise ValueError("allow_inherited_environment must be a boolean")
        if not isinstance(self.environment, Mapping):
            raise ValueError("environment must be a mapping")
        normalized_environment: dict[str, str] = {}
        for key, value in self.environment.items():
            ensure_non_empty_text("environment key", key)
            if not isinstance(value, str):
                raise ValueError("environment values must be strings")
            normalized_environment[key] = value
        object.__setattr__(self, "environment", MappingProxyType(normalized_environment))


class ProcessModelAdapter:
    """Wraps a local CLI process as a governed model adapter.

    The prompt_hash from the invocation is passed as stdin to the process.
    The process stdout is captured, digested, and returned as the model response.
    """

    def __init__(self, *, config: ProcessModelConfig, clock: Callable[[], str]) -> None:
        self._config = config
        self._clock = clock

    def invoke(self, invocation: ModelInvocation) -> ModelResponse:
        response_id = stable_identifier("proc-model-resp", {
            "invocation_id": invocation.invocation_id,
            "command": self._config.command[0],
        })

        try:
            result = subprocess.run(
                list(self._config.command),
                input=invocation.prompt_hash,
                capture_output=True,
                check=False,
                env=_build_process_environment(self._config),
                shell=False,
                text=True,
                timeout=self._config.timeout_seconds,
            )

            if result.returncode != 0:
                stderr_truncated = _truncate_output(result.stderr, self._config.max_output_bytes)
                return ModelResponse(
                    response_id=response_id,
                    invocation_id=invocation.invocation_id,
                    status=ModelStatus.FAILED,
                    output_digest=hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
                    completed_at=self._clock(),
                    validation_status=ValidationStatus.FAILED,
                    metadata={"returncode": result.returncode, "stderr": stderr_truncated[:500]},
                )

            output = _truncate_output(result.stdout, self._config.max_output_bytes)
            output_digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
            output_tokens = len(output.split())

            return ModelResponse(
                response_id=response_id,
                invocation_id=invocation.invocation_id,
                status=ModelStatus.SUCCEEDED,
                output_digest=output_digest,
                completed_at=self._clock(),
                validation_status=ValidationStatus.PENDING,
                output_tokens=output_tokens,
                actual_cost=self._config.cost_per_invocation,
            )

        except subprocess.TimeoutExpired:
            return ModelResponse(
                response_id=response_id,
                invocation_id=invocation.invocation_id,
                status=ModelStatus.TIMEOUT,
                output_digest="none",
                completed_at=self._clock(),
                validation_status=ValidationStatus.FAILED,
            )
        except Exception as exc:
            return ModelResponse(
                response_id=response_id,
                invocation_id=invocation.invocation_id,
                status=ModelStatus.FAILED,
                output_digest="none",
                completed_at=self._clock(),
                validation_status=ValidationStatus.FAILED,
                metadata={"error": _bounded_process_error(exc)},
            )
