"""Gateway Worker - command-spine dispatch loop.

Purpose: Claims ready commands from the command ledger and executes them via
    the governed gateway router outside the webhook request path.
Governance scope: command dispatch continuation only.
Dependencies: gateway router, command ledger, standard-library timing.
Invariants:
  - Commands are claimed through leases before execution.
  - Each loop iteration is bounded by batch size.
  - Worker shutdown is explicit and does not interrupt command execution.
  - CLI defaults are conservative for local and production deployment.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from typing import Protocol

from gateway.command_spine import CommandAnchor
from gateway.router import GatewayResponse

_log = logging.getLogger(__name__)


class CommandWorkerRouter(Protocol):
    """Router surface required by the gateway worker."""

    def process_ready_commands(
        self,
        *,
        worker_id: str = "gateway-worker",
        limit: int = 10,
        lease_seconds: int = 300,
    ) -> list[GatewayResponse]:
        """Claim and execute ready commands."""
        ...

    def anchor_command_events(
        self,
        *,
        signing_secret: str,
        signature_key_id: str = "local",
    ) -> CommandAnchor | None:
        """Sign unanchored command events."""
        ...


@dataclass(frozen=True, slots=True)
class GatewayWorkerConfig:
    """Bounded worker-loop configuration."""

    worker_id: str = "gateway-worker"
    batch_size: int = 10
    lease_seconds: int = 300
    poll_seconds: float = 2.0
    run_once: bool = False
    anchor_signing_secret: str = ""
    anchor_signature_key_id: str = "local"


class GatewayWorker:
    """Runs bounded command dispatch passes against a gateway router."""

    def __init__(self, router: CommandWorkerRouter, config: GatewayWorkerConfig) -> None:
        if not config.worker_id:
            raise ValueError("worker_id is required")
        if config.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if config.lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if config.poll_seconds < 0:
            raise ValueError("poll_seconds must be >= 0")
        self._router = router
        self._config = config
        self._running = False

    def run_once(self) -> int:
        """Run one bounded claim/execute pass and return response count."""
        responses = self._router.process_ready_commands(
            worker_id=self._config.worker_id,
            limit=self._config.batch_size,
            lease_seconds=self._config.lease_seconds,
        )
        if self._config.anchor_signing_secret:
            self._router.anchor_command_events(
                signing_secret=self._config.anchor_signing_secret,
                signature_key_id=self._config.anchor_signature_key_id,
            )
        return len(responses)

    def run_forever(self) -> None:
        """Run until stop() is called or the process receives interruption."""
        self._running = True
        while self._running:
            processed = self.run_once()
            _log.info("gateway worker processed %d command(s)", processed)
            if self._config.run_once:
                self._running = False
                break
            time.sleep(self._config.poll_seconds)

    def stop(self) -> None:
        """Request a graceful stop after the current pass."""
        self._running = False


def build_router_from_env() -> CommandWorkerRouter:
    """Build the production router using gateway server configuration."""
    from gateway.server import create_gateway_app

    app = create_gateway_app()
    return app.state.router


def config_from_env() -> GatewayWorkerConfig:
    """Build worker configuration from environment variables."""
    return GatewayWorkerConfig(
        worker_id=os.environ.get("MULLU_GATEWAY_WORKER_ID", "gateway-worker"),
        batch_size=int(os.environ.get("MULLU_GATEWAY_WORKER_BATCH_SIZE", "10")),
        lease_seconds=int(os.environ.get("MULLU_GATEWAY_WORKER_LEASE_SECONDS", "300")),
        poll_seconds=float(os.environ.get("MULLU_GATEWAY_WORKER_POLL_SECONDS", "2.0")),
        run_once=os.environ.get("MULLU_GATEWAY_WORKER_RUN_ONCE", "0").strip().lower()
        in {"1", "true", "yes", "on"},
        anchor_signing_secret=os.environ.get("MULLU_COMMAND_ANCHOR_SECRET", ""),
        anchor_signature_key_id=os.environ.get("MULLU_COMMAND_ANCHOR_KEY_ID", "local"),
    )


def parse_args(argv: list[str] | None = None) -> GatewayWorkerConfig:
    """Parse CLI flags for the worker entry point."""
    defaults = config_from_env()
    parser = argparse.ArgumentParser(description="Run the Mullu gateway command worker.")
    parser.add_argument("--worker-id", default=defaults.worker_id)
    parser.add_argument("--batch-size", type=int, default=defaults.batch_size)
    parser.add_argument("--lease-seconds", type=int, default=defaults.lease_seconds)
    parser.add_argument("--poll-seconds", type=float, default=defaults.poll_seconds)
    parser.add_argument("--once", action="store_true", default=defaults.run_once)
    args = parser.parse_args(argv)
    return GatewayWorkerConfig(
        worker_id=args.worker_id,
        batch_size=args.batch_size,
        lease_seconds=args.lease_seconds,
        poll_seconds=args.poll_seconds,
        run_once=args.once,
        anchor_signing_secret=defaults.anchor_signing_secret,
        anchor_signature_key_id=defaults.anchor_signature_key_id,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for `python -m gateway.worker`."""
    logging.basicConfig(level=os.environ.get("MULLU_LOG_LEVEL", "INFO"))
    config = parse_args(argv)
    worker = GatewayWorker(build_router_from_env(), config)
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        worker.stop()
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
