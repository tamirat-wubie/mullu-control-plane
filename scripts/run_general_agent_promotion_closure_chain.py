"""Run the governed general-agent promotion closure artifact chain.

Purpose: Produce the readiness, source closure plans, optional capability
    improvement portfolio, aggregate closure plan, and validation receipts in a
    deterministic order.
Governance scope: promotion-readiness evidence, adapter closure planning,
    deployment closure planning, portfolio witness inclusion, aggregate closure
    planning, schema validation, and drift validation.
Dependencies: general-agent promotion validators, closure planners, portfolio
    producer, and schema validation scripts.
Invariants:
  - This chain writes artifacts only; it does not execute closure actions.
  - Production readiness blockers remain explicit and do not fail artifact
    validation by themselves.
  - Schema and drift validation failures fail the chain.
  - Portfolio actions remain activation-blocked and approval-required.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.plan_capability_adapter_closure import (  # noqa: E402
    DEFAULT_EVIDENCE as DEFAULT_ADAPTER_EVIDENCE,
    plan_capability_adapter_closure,
    write_adapter_closure_plan,
)
from scripts.plan_deployment_publication_closure import (  # noqa: E402
    DEFAULT_DEPLOYMENT_STATUS,
    plan_deployment_publication_closure,
    write_deployment_publication_closure_plan,
)
from scripts.plan_general_agent_promotion_closure import (  # noqa: E402
    plan_general_agent_promotion_closure,
    write_general_agent_promotion_closure_plan,
)
from scripts.plan_general_agent_promotion_live_evidence_queue import (  # noqa: E402
    DEFAULT_ENVIRONMENT_BINDINGS,
    plan_general_agent_promotion_live_evidence_queue,
    validate_general_agent_promotion_live_evidence_queue,
    write_general_agent_promotion_live_evidence_queue,
)
from scripts.plan_general_agent_promotion_terminal_certificate_gate import (  # noqa: E402
    plan_general_agent_promotion_terminal_certificate_gate,
    validate_general_agent_promotion_terminal_certificate_gate,
    write_general_agent_promotion_terminal_certificate_gate,
)
from scripts.plan_general_agent_promotion_terminal_certificate_candidates import (  # noqa: E402
    plan_general_agent_promotion_terminal_certificate_candidates,
    validate_general_agent_promotion_terminal_certificate_candidates,
    write_general_agent_promotion_terminal_certificate_candidates,
)
from scripts.produce_capability_improvement_portfolio import (  # noqa: E402
    produce_capability_improvement_portfolio,
)
from scripts.reconcile_general_agent_promotion_terminal_evidence import (  # noqa: E402
    reconcile_general_agent_promotion_terminal_evidence,
    validate_general_agent_promotion_terminal_evidence_reconciliation,
    write_general_agent_promotion_terminal_evidence_reconciliation,
)
from scripts.gate_general_agent_promotion_terminal_minting import (  # noqa: E402
    gate_general_agent_promotion_terminal_minting,
    validate_general_agent_promotion_terminal_minting_gate,
    write_general_agent_promotion_terminal_minting_gate,
)
from scripts.validate_capability_adapter_closure_plan_schema import (  # noqa: E402
    validate_capability_adapter_closure_plan_schema,
    write_capability_adapter_closure_plan_schema_validation,
)
from scripts.validate_deployment_publication_closure_plan_schema import (  # noqa: E402
    validate_deployment_publication_closure_plan_schema,
    write_deployment_publication_closure_plan_schema_validation,
)
from scripts.validate_general_agent_promotion import (  # noqa: E402
    validate_general_agent_promotion,
    write_general_agent_promotion_readiness,
)
from scripts.validate_general_agent_promotion_closure_plan import (  # noqa: E402
    validate_general_agent_promotion_closure_plan,
    write_general_agent_promotion_closure_plan_validation,
)
from scripts.validate_general_agent_promotion_closure_plan_schema import (  # noqa: E402
    validate_general_agent_promotion_closure_plan_schema,
    write_general_agent_promotion_closure_plan_schema_validation,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / ".change_assurance"


@dataclass(frozen=True, slots=True)
class GeneralAgentPromotionClosureChainRun:
    """Summary of one promotion closure chain run."""

    status: str
    output_dir: str
    artifact_valid: bool
    promotion_ready: bool
    readiness_level: str
    include_portfolio: bool
    total_action_count: int
    approval_required_action_count: int
    portfolio_plan_count: int
    live_evidence_queue_ready: bool
    live_evidence_runnable_action_count: int
    live_evidence_blocked_action_count: int
    terminal_certificate_gate_ready: bool
    terminal_certificate_admitted_action_count: int
    terminal_certificate_blocked_action_count: int
    terminal_certificate_candidate_count: int
    terminal_certificate_minting_ready: bool
    terminal_evidence_reconciled_candidate_count: int
    terminal_evidence_blocked_candidate_count: int
    terminal_minting_gate_admitted_candidate_count: int
    terminal_minting_gate_blocked_candidate_count: int
    artifacts: dict[str, str]
    promotion_blockers: tuple[str, ...]
    validation_errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether all artifact validation gates passed."""
        return self.artifact_valid and not self.validation_errors

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready run metadata."""
        payload = asdict(self)
        payload["promotion_blockers"] = list(self.promotion_blockers)
        payload["validation_errors"] = list(self.validation_errors)
        return payload


def run_general_agent_promotion_closure_chain(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
    deployment_status_path: Path = DEFAULT_DEPLOYMENT_STATUS,
    include_portfolio: bool = True,
    portfolio_domain: str = "",
    portfolio_risk_level: str = "",
    portfolio_candidate_limit: int = 5,
    environment_bindings_path: Path = DEFAULT_ENVIRONMENT_BINDINGS,
    environment_binding_receipt_path: Path | None = None,
    terminal_approval_receipt_path: Path | None = None,
    terminal_minting_authority_ref: str | None = None,
) -> GeneralAgentPromotionClosureChainRun:
    """Produce and validate the default promotion closure artifact chain.

    Input contract: source paths must be readable and output_dir must be
    writable.
    Output contract: all chain artifacts are written under output_dir.
    Error contract: schema, drift, producer, or missing-source failures are
    returned as validation_errors without hiding promotion blockers.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _artifact_paths(output_dir)
    validation_errors: list[str] = []

    readiness = validate_general_agent_promotion(
        repo_root=REPO_ROOT,
        deployment_status_path=deployment_status_path,
        adapter_evidence_path=adapter_evidence_path,
    )
    write_general_agent_promotion_readiness(readiness, paths["readiness"])

    adapter_plan = plan_capability_adapter_closure(adapter_evidence_path)
    write_adapter_closure_plan(adapter_plan, paths["adapter_plan"])
    adapter_schema_validation = validate_capability_adapter_closure_plan_schema(
        plan_path=paths["adapter_plan"],
    )
    write_capability_adapter_closure_plan_schema_validation(
        adapter_schema_validation,
        paths["adapter_schema_validation"],
    )
    validation_errors.extend(_prefixed_errors("adapter_schema", adapter_schema_validation.errors))

    deployment_plan = plan_deployment_publication_closure(
        readiness_path=paths["readiness"],
        deployment_status_path=deployment_status_path,
    )
    write_deployment_publication_closure_plan(deployment_plan, paths["deployment_plan"])
    deployment_schema_validation = validate_deployment_publication_closure_plan_schema(
        plan_path=paths["deployment_plan"],
    )
    write_deployment_publication_closure_plan_schema_validation(
        deployment_schema_validation,
        paths["deployment_schema_validation"],
    )
    validation_errors.extend(_prefixed_errors("deployment_schema", deployment_schema_validation.errors))

    portfolio_plan_path: Path | None = None
    portfolio_plan_count = 0
    if include_portfolio:
        portfolio_result = produce_capability_improvement_portfolio(
            output_path=paths["portfolio"],
            domain=portfolio_domain,
            risk_level=portfolio_risk_level,
            candidate_limit=portfolio_candidate_limit,
        )
        portfolio_plan_path = paths["portfolio"]
        portfolio_plan_count = portfolio_result.plan_count
        validation_errors.extend(_prefixed_errors("portfolio", portfolio_result.validation_errors))
        validation_errors.extend(_prefixed_errors("portfolio", portfolio_result.blockers))

    promotion_plan = plan_general_agent_promotion_closure(
        readiness_path=paths["readiness"],
        adapter_plan_path=paths["adapter_plan"],
        deployment_plan_path=paths["deployment_plan"],
        portfolio_plan_path=portfolio_plan_path,
    )
    write_general_agent_promotion_closure_plan(promotion_plan, paths["promotion_plan"])
    promotion_schema_validation = validate_general_agent_promotion_closure_plan_schema(
        plan_path=paths["promotion_plan"],
    )
    write_general_agent_promotion_closure_plan_schema_validation(
        promotion_schema_validation,
        paths["promotion_schema_validation"],
    )
    validation_errors.extend(_prefixed_errors("promotion_schema", promotion_schema_validation.errors))

    promotion_drift_validation = validate_general_agent_promotion_closure_plan(
        promotion_plan_path=paths["promotion_plan"],
        readiness_path=paths["readiness"],
        adapter_plan_path=paths["adapter_plan"],
        deployment_plan_path=paths["deployment_plan"],
        portfolio_plan_path=portfolio_plan_path,
    )
    write_general_agent_promotion_closure_plan_validation(
        promotion_drift_validation,
        paths["promotion_drift_validation"],
    )
    validation_errors.extend(_prefixed_errors("promotion_drift", promotion_drift_validation.errors))

    live_evidence_queue = plan_general_agent_promotion_live_evidence_queue(
        promotion_plan_path=paths["promotion_plan"],
        environment_bindings_path=environment_bindings_path,
        environment_binding_receipt_path=(
            environment_binding_receipt_path
            if environment_binding_receipt_path is not None
            else paths["environment_binding_receipt"]
        ),
    )
    write_general_agent_promotion_live_evidence_queue(
        live_evidence_queue,
        paths["live_evidence_queue"],
    )
    live_evidence_schema_errors = validate_general_agent_promotion_live_evidence_queue(live_evidence_queue)
    validation_errors.extend(_prefixed_errors("live_evidence_queue_schema", live_evidence_schema_errors))

    terminal_certificate_gate = plan_general_agent_promotion_terminal_certificate_gate(
        queue_path=paths["live_evidence_queue"],
        approval_receipt_path=(
            terminal_approval_receipt_path
            if terminal_approval_receipt_path is not None
            else paths["terminal_approval_receipt"]
        ),
    )
    write_general_agent_promotion_terminal_certificate_gate(
        terminal_certificate_gate,
        paths["terminal_certificate_gate"],
    )
    terminal_gate_schema_errors = validate_general_agent_promotion_terminal_certificate_gate(terminal_certificate_gate)
    validation_errors.extend(_prefixed_errors("terminal_certificate_gate_schema", terminal_gate_schema_errors))

    terminal_certificate_candidates = plan_general_agent_promotion_terminal_certificate_candidates(
        gate_path=paths["terminal_certificate_gate"],
    )
    write_general_agent_promotion_terminal_certificate_candidates(
        terminal_certificate_candidates,
        paths["terminal_certificate_candidates"],
    )
    terminal_candidate_schema_errors = validate_general_agent_promotion_terminal_certificate_candidates(
        terminal_certificate_candidates,
    )
    validation_errors.extend(_prefixed_errors("terminal_certificate_candidates_schema", terminal_candidate_schema_errors))

    terminal_evidence_reconciliation = reconcile_general_agent_promotion_terminal_evidence(
        candidate_path=paths["terminal_certificate_candidates"],
    )
    write_general_agent_promotion_terminal_evidence_reconciliation(
        terminal_evidence_reconciliation,
        paths["terminal_evidence_reconciliation"],
    )
    terminal_evidence_schema_errors = validate_general_agent_promotion_terminal_evidence_reconciliation(
        terminal_evidence_reconciliation,
    )
    validation_errors.extend(_prefixed_errors("terminal_evidence_reconciliation_schema", terminal_evidence_schema_errors))

    terminal_minting_gate = gate_general_agent_promotion_terminal_minting(
        reconciliation_path=paths["terminal_evidence_reconciliation"],
        authority_ref=terminal_minting_authority_ref,
    )
    write_general_agent_promotion_terminal_minting_gate(
        terminal_minting_gate,
        paths["terminal_minting_gate"],
    )
    terminal_minting_gate_schema_errors = validate_general_agent_promotion_terminal_minting_gate(
        terminal_minting_gate,
    )
    validation_errors.extend(_prefixed_errors("terminal_minting_gate_schema", terminal_minting_gate_schema_errors))

    artifact_valid = not validation_errors
    status = "failed"
    if artifact_valid and readiness.ready:
        status = "passed"
    elif artifact_valid:
        status = "passed_blocked"
    return GeneralAgentPromotionClosureChainRun(
        status=status,
        output_dir=str(output_dir),
        artifact_valid=artifact_valid,
        promotion_ready=readiness.ready,
        readiness_level=readiness.readiness_level,
        include_portfolio=include_portfolio,
        total_action_count=promotion_plan.total_action_count,
        approval_required_action_count=promotion_plan.approval_required_action_count,
        portfolio_plan_count=portfolio_plan_count,
        live_evidence_queue_ready=live_evidence_queue.ready_to_execute,
        live_evidence_runnable_action_count=live_evidence_queue.runnable_action_count,
        live_evidence_blocked_action_count=live_evidence_queue.blocked_action_count,
        terminal_certificate_gate_ready=terminal_certificate_gate.ready_for_terminal_certificate,
        terminal_certificate_admitted_action_count=terminal_certificate_gate.admitted_action_count,
        terminal_certificate_blocked_action_count=terminal_certificate_gate.blocked_action_count,
        terminal_certificate_candidate_count=terminal_certificate_candidates.candidate_count,
        terminal_certificate_minting_ready=terminal_minting_gate.ready_for_terminal_certificate_minting,
        terminal_evidence_reconciled_candidate_count=terminal_evidence_reconciliation.reconciled_candidate_count,
        terminal_evidence_blocked_candidate_count=terminal_evidence_reconciliation.blocked_candidate_count,
        terminal_minting_gate_admitted_candidate_count=terminal_minting_gate.admitted_candidate_count,
        terminal_minting_gate_blocked_candidate_count=terminal_minting_gate.blocked_candidate_count,
        artifacts={
            name: str(path)
            for name, path in paths.items()
            if name not in {"environment_binding_receipt", "terminal_approval_receipt"}
            and (include_portfolio or name != "portfolio")
        },
        promotion_blockers=readiness.blockers,
        validation_errors=tuple(dict.fromkeys(validation_errors)),
    )


def _artifact_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "readiness": output_dir / "general_agent_promotion_readiness.json",
        "adapter_plan": output_dir / "capability_adapter_closure_plan.json",
        "adapter_schema_validation": output_dir / "capability_adapter_closure_plan_schema_validation.json",
        "deployment_plan": output_dir / "deployment_publication_closure_plan.json",
        "deployment_schema_validation": output_dir / "deployment_publication_closure_plan_schema_validation.json",
        "portfolio": output_dir / "capability_improvement_portfolio.json",
        "promotion_plan": output_dir / "general_agent_promotion_closure_plan.json",
        "promotion_schema_validation": output_dir / "general_agent_promotion_closure_plan_schema_validation.json",
        "promotion_drift_validation": output_dir / "general_agent_promotion_closure_plan_validation.json",
        "environment_binding_receipt": output_dir / "general_agent_promotion_environment_binding_receipt.json",
        "live_evidence_queue": output_dir / "general_agent_promotion_live_evidence_queue.json",
        "terminal_approval_receipt": output_dir / "general_agent_promotion_terminal_approvals.json",
        "terminal_certificate_gate": output_dir / "general_agent_promotion_terminal_certificate_gate.json",
        "terminal_certificate_candidates": output_dir / "general_agent_promotion_terminal_certificate_candidates.json",
        "terminal_evidence_reconciliation": output_dir / "general_agent_promotion_terminal_evidence_reconciliation.json",
        "terminal_minting_gate": output_dir / "general_agent_promotion_terminal_minting_gate.json",
    }


def _prefixed_errors(prefix: str, errors: tuple[str, ...] | list[str]) -> list[str]:
    return [f"{prefix}:{error}" for error in errors]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion closure chain arguments."""
    parser = argparse.ArgumentParser(description="Run the general-agent promotion closure artifact chain.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--deployment-status", default=str(DEFAULT_DEPLOYMENT_STATUS))
    parser.add_argument("--skip-portfolio", action="store_true")
    parser.add_argument("--portfolio-domain", default="")
    parser.add_argument("--portfolio-risk-level", default="")
    parser.add_argument("--portfolio-candidate-limit", type=int, default=5)
    parser.add_argument("--environment-bindings", default=str(DEFAULT_ENVIRONMENT_BINDINGS))
    parser.add_argument("--environment-binding-receipt", default="")
    parser.add_argument("--terminal-approval-receipt", default="")
    parser.add_argument("--terminal-minting-authority-ref", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = parse_args(argv)
    run = run_general_agent_promotion_closure_chain(
        output_dir=Path(args.output_dir),
        adapter_evidence_path=Path(args.adapter_evidence),
        deployment_status_path=Path(args.deployment_status),
        include_portfolio=not args.skip_portfolio,
        portfolio_domain=args.portfolio_domain,
        portfolio_risk_level=args.portfolio_risk_level,
        portfolio_candidate_limit=args.portfolio_candidate_limit,
        environment_bindings_path=Path(args.environment_bindings),
        environment_binding_receipt_path=(
            Path(args.environment_binding_receipt)
            if str(args.environment_binding_receipt).strip()
            else None
        ),
        terminal_approval_receipt_path=(
            Path(args.terminal_approval_receipt)
            if str(args.terminal_approval_receipt).strip()
            else None
        ),
        terminal_minting_authority_ref=(
            str(args.terminal_minting_authority_ref).strip()
            if str(args.terminal_minting_authority_ref).strip()
            else None
        ),
    )
    if args.json:
        print(json.dumps(run.as_dict(), indent=2, sort_keys=True))
    elif run.passed:
        print(
            "GENERAL AGENT PROMOTION CLOSURE CHAIN WRITTEN "
            f"status={run.status} actions={run.total_action_count} approvals={run.approval_required_action_count}"
        )
    else:
        print(f"GENERAL AGENT PROMOTION CLOSURE CHAIN FAILED errors={list(run.validation_errors)}")
    if args.require_ready and not run.promotion_ready:
        return 2
    return 0 if run.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
