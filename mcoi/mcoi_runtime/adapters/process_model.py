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

from typing import Callable

import hashlib
import subprocess
from dataclasses import dataclass

from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelResponse,
    ModelStatus,
    ValidationStatus,
)
from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


@dataclass(frozen=True, slots=True)
class ProcessModelConfig:
    """Configuration for a local process model adapter."""

    command: tuple[str, ...]
    timeout_seconds: float = 60.0
    cost_per_invocation: float = 0.0

    def __post_init__(self) -> None:
        if not self.command:
            raise ValueError("command must contain at least one element")
        for i, part in enumerate(self.command):
            ensure_non_empty_text(f"command[{i}]", part)
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.cost_per_invocation < 0:
            raise ValueError("cost_per_invocation must be non-negative")


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
                text=True,
                timeout=self._config.timeout_seconds,
            )

            if result.returncode != 0:
                return ModelResponse(
                    response_id=response_id,
                    invocation_id=invocation.invocation_id,
                    status=ModelStatus.FAILED,
                    output_digest=hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
                    completed_at=self._clock(),
                    validation_status=ValidationStatus.FAILED,
                    metadata={"returncode": result.returncode, "stderr": result.stderr[:500]},
                )

            output = result.stdout
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
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )
