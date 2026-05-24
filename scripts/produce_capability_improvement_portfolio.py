"""Produce a governed capability improvement portfolio witness.

Purpose: Convert the default governed capability registry read model into a
    schema-validated capability improvement portfolio artifact.
Governance scope: read-only capability health projection, activation-blocked
    upgrade planning, schema validation, and closure-plan witness production.
Dependencies: gateway capability fabric, autonomous capability upgrade loop,
    and repository schema validation helpers.
Invariants:
  - The producer never mutates the capability registry.
  - Every emitted plan remains activation-blocked and operator-review required.
  - Every written artifact passes the public portfolio schema first.
  - Missing source records or schema violations are explicit blockers.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    root_text = str(import_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

from gateway.autonomous_capability_upgrade import (  # noqa: E402
    MATURITY_LEVELS,
    AutonomousCapabilityUpgradeLoop,
    CapabilityHealthSignal,
)
from gateway.capability_fabric import build_default_capability_admission_gate  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_improvement_portfolio.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_improvement_portfolio.schema.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"


@dataclass(frozen=True, slots=True)
class CapabilityImprovementPortfolioRun:
    """Summary of one portfolio witness production run."""

    status: str
    output_path: str
    portfolio_id: str
    plan_count: int
    prioritized_capability_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    validation_errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Return whether the portfolio artifact is schema-valid."""
        return self.status == "passed" and not self.blockers and not self.validation_errors

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready run metadata."""
        return _json_ready(asdict(self))


def produce_capability_improvement_portfolio(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    generated_at: str = DEFAULT_GENERATED_AT,
    domain: str = "",
    risk_level: str = "",
    candidate_limit: int = 5,
    clock: Callable[[], str] | None = None,
) -> CapabilityImprovementPortfolioRun:
    """Produce a schema-valid portfolio from governed capability records.

    Input contract: paths are filesystem targets, filters are exact domain or
    risk-level strings, and candidate_limit is a positive integer.
    Output contract: on pass, output_path contains the schema-valid portfolio.
    Error contract: source, filter, and schema failures are returned as blockers.
    """
    if candidate_limit <= 0:
        return _failed_run(
            output_path=output_path,
            blockers=("candidate_limit_positive_required",),
        )

    observed_at = generated_at.strip()
    if not observed_at:
        return _failed_run(output_path=output_path, blockers=("generated_at_required",))

    records = _governed_capability_records(clock=clock or (lambda: observed_at))
    filtered_records = tuple(
        record
        for record in records
        if _matches_filter(record, domain=domain, risk_level=risk_level)
    )
    if not filtered_records:
        return _failed_run(output_path=output_path, blockers=("governed_capability_records_required",))

    try:
        signals = tuple(
            _health_signal_from_record(record, observed_at=observed_at)
            for record in filtered_records
        )
        portfolio = AutonomousCapabilityUpgradeLoop().propose_portfolio(
            signals,
            generated_at=observed_at,
            max_candidates=candidate_limit,
        )
        payload = portfolio.to_json_dict()
        schema = _load_schema(schema_path)
        validation_errors = tuple(_validate_schema_instance(schema, payload))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _failed_run(output_path=output_path, blockers=(f"portfolio_production_failed:{exc}",))

    if validation_errors:
        return CapabilityImprovementPortfolioRun(
            status="failed",
            output_path=str(output_path),
            portfolio_id=str(payload.get("portfolio_id", "")),
            plan_count=len(payload.get("plans", ())) if isinstance(payload.get("plans"), list) else 0,
            prioritized_capability_ids=tuple(
                str(capability_id)
                for capability_id in payload.get("prioritized_capability_ids", ())
                if str(capability_id).strip()
            ),
            blockers=validation_errors,
            validation_errors=validation_errors,
        )

    _write_json(output_path, payload)
    return CapabilityImprovementPortfolioRun(
        status="passed",
        output_path=str(output_path),
        portfolio_id=str(payload["portfolio_id"]),
        plan_count=len(payload["plans"]),
        prioritized_capability_ids=tuple(str(capability_id) for capability_id in payload["prioritized_capability_ids"]),
        blockers=(),
        validation_errors=(),
    )


def _governed_capability_records(*, clock: Callable[[], str]) -> tuple[Mapping[str, Any], ...]:
    gate = build_default_capability_admission_gate(clock=clock)
    read_model = gate.read_model()
    records = read_model.get("governed_capability_records", ())
    return tuple(record for record in records if isinstance(record, Mapping))


def _matches_filter(record: Mapping[str, Any], *, domain: str, risk_level: str) -> bool:
    domain_filter = domain.strip()
    risk_filter = risk_level.strip()
    if domain_filter and _domain_for(record) != domain_filter:
        return False
    if risk_filter and str(record.get("risk_level", "")).strip() != risk_filter:
        return False
    return True


def _health_signal_from_record(record: Mapping[str, Any], *, observed_at: str) -> CapabilityHealthSignal:
    capability_id = str(record.get("capability_id", "")).strip()
    maturity_level = str(record.get("maturity_level", "C0")).strip()
    if maturity_level not in MATURITY_LEVELS:
        maturity_level = "C0"
    evidence_refs = _evidence_refs(record, capability_id=capability_id)
    return CapabilityHealthSignal(
        capability_id=capability_id,
        observed_at=observed_at,
        maturity_level=maturity_level,
        success_rate=1.0,
        failure_count=0,
        mean_latency_ms=0,
        cost_per_success=float(record.get("max_cost", 0.0) or 0.0),
        open_incidents=0,
        blocker_codes=_blocker_codes(record),
        evidence_refs=evidence_refs,
        metadata={
            "source": "governed_capability_registry",
            "producer": "produce_capability_improvement_portfolio",
            "domain": _domain_for(record),
            "risk_level": str(record.get("risk_level", "")),
            "production_ready": record.get("production_ready") is True,
        },
    )


def _domain_for(record: Mapping[str, Any]) -> str:
    capability_id = str(record.get("capability_id", "")).strip()
    if "." not in capability_id:
        return capability_id
    return capability_id.split(".", 1)[0]


def _blocker_codes(record: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    if record.get("production_ready") is not True:
        blockers.append("production_certification_missing")
    if record.get("requires_sandbox") is True:
        blockers.append("sandbox_receipt_required")
    if record.get("receipt_required") is True:
        blockers.append("receipt_closure_required")
    if record.get("requires_approval") is True:
        blockers.append("operator_approval_required")
    return tuple(dict.fromkeys(blockers))


def _evidence_refs(record: Mapping[str, Any], *, capability_id: str) -> tuple[str, ...]:
    refs = [f"capability_registry:{capability_id}"]
    maturity_assessment_id = str(record.get("maturity_assessment_id", "")).strip()
    if maturity_assessment_id:
        refs.append(f"capability_maturity:{maturity_assessment_id}")
    return tuple(refs)


def _failed_run(*, output_path: Path, blockers: tuple[str, ...]) -> CapabilityImprovementPortfolioRun:
    return CapabilityImprovementPortfolioRun(
        status="failed",
        output_path=str(output_path),
        portfolio_id="",
        plan_count=0,
        prioritized_capability_ids=(),
        blockers=blockers,
        validation_errors=(),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _json_ready(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse capability improvement portfolio producer arguments."""
    parser = argparse.ArgumentParser(description="Produce a governed capability improvement portfolio witness.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--domain", default="")
    parser.add_argument("--risk-level", default="")
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = parse_args(argv)
    run = produce_capability_improvement_portfolio(
        output_path=Path(args.output),
        schema_path=Path(args.schema),
        generated_at=args.generated_at,
        domain=args.domain,
        risk_level=args.risk_level,
        candidate_limit=args.candidate_limit,
    )
    if args.json:
        print(json.dumps(run.as_dict(), indent=2, sort_keys=True))
    elif run.passed:
        print(f"CAPABILITY IMPROVEMENT PORTFOLIO PASSED portfolio_id={run.portfolio_id}")
    else:
        print(f"CAPABILITY IMPROVEMENT PORTFOLIO FAILED blockers={list(run.blockers)}")
    return 0 if run.passed or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
