#!/usr/bin/env python3
"""Plan deployment publication closure actions.

Purpose: convert deployment promotion blockers into deterministic operator
actions without changing public deployment status.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: .change_assurance/general_agent_promotion_readiness.json,
DEPLOYMENT_STATUS.md, and deployment witness publication scripts.
Invariants:
  - Planning never flips DEPLOYMENT_STATUS.md to published.
  - Public health declaration requires a matching published witness gateway URL.
  - Unknown deployment blockers remain visible as manual-review actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_READINESS = REPO_ROOT / ".change_assurance" / "general_agent_promotion_readiness.json"
DEFAULT_DEPLOYMENT_STATUS = REPO_ROOT / "DEPLOYMENT_STATUS.md"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "deployment_publication_closure_plan.json"


@dataclass(frozen=True, slots=True)
class DeploymentClosureAction:
    """One deterministic deployment closure action."""

    action_id: str
    blocker: str
    action_type: str
    command: str
    evidence_required: tuple[str, ...]
    risk_level: str
    approval_required: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready closure action."""
        payload = asdict(self)
        payload["evidence_required"] = list(self.evidence_required)
        return payload


@dataclass(frozen=True, slots=True)
class DeploymentPublicationClosurePlan:
    """Deterministic deployment publication closure plan."""

    plan_id: str
    source_readiness_path: str
    deployment_status_path: str
    source_ready: bool
    action_count: int
    blockers: tuple[str, ...]
    actions: tuple[DeploymentClosureAction, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready closure plan."""
        return {
            "plan_id": self.plan_id,
            "source_readiness_path": self.source_readiness_path,
            "deployment_status_path": self.deployment_status_path,
            "source_ready": self.source_ready,
            "action_count": self.action_count,
            "blockers": list(self.blockers),
            "actions": [action.as_dict() for action in self.actions],
        }


def plan_deployment_publication_closure(
    readiness_path: Path = DEFAULT_READINESS,
    deployment_status_path: Path = DEFAULT_DEPLOYMENT_STATUS,
) -> DeploymentPublicationClosurePlan:
    """Build a deterministic plan for deployment publication blockers."""
    readiness = _load_json_object(readiness_path, "promotion readiness")
    blockers = _deployment_readiness_blockers(readiness)
    actions = tuple(_dedupe_actions([_action_for(blocker) for blocker in blockers]))
    plan_material = {
        "source_report_id": str(readiness.get("readiness_id", readiness.get("report_id", ""))),
        "source_ready": readiness.get("ready") is True,
        "blockers": blockers,
        "actions": [action.as_dict() for action in actions],
    }
    plan_digest = hashlib.sha256(
        json.dumps(plan_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DeploymentPublicationClosurePlan(
        plan_id=f"deployment-publication-closure-plan-{plan_digest[:16]}",
        source_readiness_path=str(readiness_path),
        deployment_status_path=str(deployment_status_path),
        source_ready=readiness.get("ready") is True,
        action_count=len(actions),
        blockers=blockers,
        actions=actions,
    )


def write_deployment_publication_closure_plan(
    plan: DeploymentPublicationClosurePlan,
    output_path: Path,
) -> Path:
    """Write one deterministic deployment publication closure plan."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _action_for(blocker: str) -> DeploymentClosureAction:
    if blocker == "deployment_witness_secret_missing":
        return DeploymentClosureAction(
            action_id="provision-deployment-witness-secret",
            blocker=blocker,
            action_type="secret-binding",
            command=(
                "Provision GitHub Actions secret MULLU_DEPLOYMENT_WITNESS_SECRET; "
                "do not print or serialize the secret value."
            ),
            evidence_required=(
                "gh_secret_list_presence:MULLU_DEPLOYMENT_WITNESS_SECRET",
                "deployment_witness_preflight",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_runtime_witness_secret_missing":
        return DeploymentClosureAction(
            action_id="provision-runtime-witness-secret",
            blocker=blocker,
            action_type="secret-binding",
            command=(
                "Provision GitHub Actions secret MULLU_RUNTIME_WITNESS_SECRET; "
                "do not print or serialize the secret value."
            ),
            evidence_required=(
                "gh_secret_list_presence:MULLU_RUNTIME_WITNESS_SECRET",
                "deployment_witness_preflight",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_runtime_conformance_secret_missing":
        return DeploymentClosureAction(
            action_id="provision-runtime-conformance-secret",
            blocker=blocker,
            action_type="secret-binding",
            command=(
                "Provision GitHub Actions secret MULLU_RUNTIME_CONFORMANCE_SECRET; "
                "do not print or serialize the secret value."
            ),
            evidence_required=(
                "gh_secret_list_presence:MULLU_RUNTIME_CONFORMANCE_SECRET",
                "deployment_witness_preflight",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_repository_variables_mismatch":
        return DeploymentClosureAction(
            action_id="provision-deployment-target-variables",
            blocker=blocker,
            action_type="repository-variable-binding",
            command=(
                "python scripts/provision_deployment_target.py "
                "--gateway-url \"$MULLU_GATEWAY_URL\" "
                "--expected-environment \"$MULLU_EXPECTED_RUNTIME_ENV\""
            ),
            evidence_required=(
                "gh_variable_list_presence:MULLU_GATEWAY_URL",
                "gh_variable_list_presence:MULLU_EXPECTED_RUNTIME_ENV",
                "deployment_witness_preflight",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_dns_not_verified":
        return DeploymentClosureAction(
            action_id="verify-gateway-dns",
            blocker=blocker,
            action_type="dns-verification",
            command=(
                "python scripts/collect_gateway_dns_resolution_receipt.py "
                "--host \"$MULLU_GATEWAY_HOST\" "
                "--output .change_assurance/gateway_dns_resolution_receipt.json "
                "--json && "
                "python scripts/preflight_deployment_witness.py "
                "--gateway-host \"$MULLU_GATEWAY_HOST\" "
                "--gateway-url \"$MULLU_GATEWAY_URL\""
            ),
            evidence_required=(
                "dns_resolution_receipt",
                "deployment_witness_preflight",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_endpoint_contract_missing":
        return DeploymentClosureAction(
            action_id="verify-gateway-endpoint-contracts",
            blocker=blocker,
            action_type="endpoint-verification",
            command=(
                "Rerun deployment preflight with endpoint probes enabled and "
                "collect /health, /gateway/witness, and /runtime/conformance evidence."
            ),
            evidence_required=(
                "health_endpoint_receipt",
                "runtime_witness_receipt",
                "runtime_conformance_receipt",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_publication_workflow_unavailable":
        return DeploymentClosureAction(
            action_id="repair-deployment-publication-workflow",
            blocker=blocker,
            action_type="workflow-repair",
            command=(
                "Inspect .github/workflows/gateway-publication.yml and "
                "deployment-witness.yml, restore active workflow state, then rerun readiness."
            ),
            evidence_required=(
                "workflow_state_active",
                "gateway_publication_readiness",
            ),
            risk_level="medium",
            approval_required=True,
        )
    if blocker == "deployment_witness_not_published":
        return DeploymentClosureAction(
            action_id="deployment-witness-publish-with-approval",
            blocker=blocker,
            action_type="publish-witness",
            command=(
                "python scripts/publish_gateway_publication.py "
                "--gateway-url \"$MULLU_GATEWAY_URL\" "
                "--dispatch-witness --dispatch "
                "--receipt-output .change_assurance/gateway_publication_receipt.json"
            ),
            evidence_required=(
                "gateway_publication_readiness.json",
                "gateway_publication_receipt.json",
                "deployment_witness.json",
                "operator_approval_ref",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "production_health_not_declared":
        return DeploymentClosureAction(
            action_id="declare-public-production-health",
            blocker=blocker,
            action_type="status-update",
            command=(
                "Update DEPLOYMENT_STATUS.md only after deployment_witness.json "
                "has deployment_claim=published and public health equals <gateway_url>/health."
            ),
            evidence_required=(
                "deployment_witness.json",
                "https_health_probe_receipt",
                "deployment_publication_closure_validation",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_runtime_responsibility_debt_present":
        return DeploymentClosureAction(
            action_id="clear-runtime-responsibility-debt",
            blocker=blocker,
            action_type="responsibility-debt-closure",
            command=(
                "Inspect /gateway/witness and /runtime/conformance; clear runtime "
                "responsibility debt before re-running deployment witness collection."
            ),
            evidence_required=(
                "gateway_witness_responsibility_debt_clear",
                "runtime_responsibility_debt_clear",
                "deployment_witness.json",
            ),
            risk_level="high",
            approval_required=True,
        )
    if blocker == "deployment_authority_responsibility_debt_present":
        return DeploymentClosureAction(
            action_id="clear-authority-responsibility-debt",
            blocker=blocker,
            action_type="responsibility-debt-closure",
            command=(
                "Inspect /authority/responsibility, close or escalate overdue "
                "obligations, then re-collect runtime conformance and deployment witness."
            ),
            evidence_required=(
                "authority_responsibility_debt_clear",
                "authority_obligation_closure_receipts",
                "deployment_witness.json",
            ),
            risk_level="high",
            approval_required=True,
        )
    return DeploymentClosureAction(
        action_id=f"manual-review-{blocker.replace('_', '-')}",
        blocker=blocker,
        action_type="manual-review",
        command="Review deployment blocker and add a governed publication action before status mutation.",
        evidence_required=("manual_review_receipt",),
        risk_level="medium",
        approval_required=True,
    )


def _deployment_blockers() -> frozenset[str]:
    return frozenset(
        {
            "deployment_witness_not_published",
            "deployment_witness_secret_missing",
            "deployment_runtime_witness_secret_missing",
            "deployment_runtime_conformance_secret_missing",
            "deployment_repository_variables_mismatch",
            "deployment_dns_not_verified",
            "deployment_endpoint_contract_missing",
            "deployment_publication_workflow_unavailable",
            "deployment_runtime_responsibility_debt_present",
            "deployment_authority_responsibility_debt_present",
            "production_health_not_declared",
        }
    )


def _deployment_readiness_blockers(readiness: dict[str, Any]) -> tuple[str, ...]:
    declared_blockers = [
        blocker
        for blocker in (str(item) for item in readiness.get("blockers", ()))
        if blocker in _deployment_blockers() or blocker.startswith("deployment_")
    ]
    step_blockers = [
        blocker
        for step in readiness.get("steps", ())
        if isinstance(step, dict) and step.get("passed") is not True
        for blocker in _blockers_for_failed_step(step)
    ]
    return tuple(dict.fromkeys([*declared_blockers, *step_blockers]))


def _blockers_for_failed_step(step: dict[str, Any]) -> tuple[str, ...]:
    name = str(step.get("name", "")).casefold()
    detail = str(step.get("detail", "")).casefold()
    if name == "deployment witness secret" or "mullu_deployment_witness_secret" in detail:
        return ("deployment_witness_secret_missing",)
    if name == "runtime witness secret" or "mullu_runtime_witness_secret" in detail:
        return ("deployment_runtime_witness_secret_missing",)
    if name == "runtime conformance secret" or "mullu_runtime_conformance_secret" in detail:
        return ("deployment_runtime_conformance_secret_missing",)
    if name == "repository variables":
        return ("deployment_repository_variables_mismatch",)
    if name == "dns resolution":
        return ("deployment_dns_not_verified",)
    if name in {"gateway health endpoint", "gateway runtime witness endpoint", "runtime conformance endpoint"}:
        return ("deployment_endpoint_contract_missing",)
    if name in {"gateway publication workflow", "deployment witness workflow"}:
        return ("deployment_publication_workflow_unavailable",)
    if name == "kubeconfig secret":
        return ("deployment_kubeconfig_secret_missing",)
    return (f"deployment_{name.replace(' ', '_')}_failed",) if name else ("deployment_unknown_step_failed",)


def _dedupe_actions(actions: list[DeploymentClosureAction]) -> list[DeploymentClosureAction]:
    deduped: dict[str, DeploymentClosureAction] = {}
    for action in actions:
        deduped.setdefault(action.action_id, action)
    return list(deduped.values())


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    try:
        payload = _loads_strict_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment publication closure plan arguments."""
    parser = argparse.ArgumentParser(description="Plan deployment publication closure actions.")
    parser.add_argument("--readiness", default=str(DEFAULT_READINESS))
    parser.add_argument("--deployment-status", default=str(DEFAULT_DEPLOYMENT_STATUS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment publication closure planning."""
    args = parse_args(argv)
    plan = plan_deployment_publication_closure(
        readiness_path=Path(args.readiness),
        deployment_status_path=Path(args.deployment_status),
    )
    write_deployment_publication_closure_plan(plan, Path(args.output))
    if args.json:
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
    elif plan.action_count:
        print(f"DEPLOYMENT PUBLICATION CLOSURE PLAN WRITTEN actions={plan.action_count}")
    else:
        print(f"DEPLOYMENT PUBLICATION CLOSURE PLAN EMPTY plan_id={plan.plan_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
