"""Gateway solver-forge CLI.

Purpose: A read-and-experiment entrypoint for the Solver Forge laboratory.
    Lists the method registry, lists benchmarks, runs a benchmark through the
    governed composer, and previews the Capability Forge input a winner would
    produce. It is the "run the lab" surface.
Governance scope: NON-promoting by construction. There is no install, promote,
    certify, deploy, or register subcommand. `run` produces a comparison report
    and (optionally) a ledger file; `forge-input` PREVIEWS the bridge output but
    never calls CapabilityForge.create_candidate. Acting on a winner stays a
    deliberate, downstream, human-driven step through the C0-C7 maturity ladder.
Dependencies: gateway.method_registry, gateway.solver_forge_benchmarks,
    gateway.candidate_ledger, gateway.solver_forge_bridge.

Run it with:  python -m gateway.solver_forge_cli <command> ...
"""

from __future__ import annotations

import argparse
import json

from gateway.candidate_ledger import (
    CandidateLedger,
    CandidateRun,
    JsonFileCandidateLedgerStore,
)
from gateway.method_registry import default_registry
from gateway.solver_forge_benchmarks import (
    get_benchmark,
    list_benchmarks,
    run_benchmark,
)
from gateway.solver_forge_bridge import forge_input_for_winner


def _scores_dict(run: CandidateRun) -> dict[str, float]:
    return {s.metric_id: s.value for s in run.scores}


def _report_to_dict(report, ledger: CandidateLedger) -> dict:
    runs = {r.record_hash: r for r in ledger.for_signature(report.signature_hash)}

    def _entry(record_hash: str) -> dict:
        run = runs[record_hash]
        return {
            "pipeline_id": run.candidate_pipeline_id,
            "method_families": list(run.method_families),
            "outcome": run.outcome,
            "scores": _scores_dict(run),
            "baseline_delta": run.baseline_delta,
            "cost_units": run.cost_units,
        }

    winner_hashes = set(report.winner_record_hashes)
    passed_non_winners = [
        h
        for h in report.candidate_record_hashes
        if h not in winner_hashes and runs[h].outcome == "passed"
    ]
    return {
        "benchmark_id": report.problem_id,
        "signature_hash": report.signature_hash,
        "primary_metric_id": report.primary_metric_id,
        "baseline_record_hash": report.baseline_record_hash,
        "winners": [_entry(h) for h in report.winner_record_hashes],
        "passed_non_winners": [_entry(h) for h in passed_non_winners],
        "negatives": [_entry(h) for h in report.negative_record_hashes],
        "skipped_capsules": report.skipped_reasons,
        "baseline_compromised": report.baseline_compromised,
        "baseline_findings": list(report.baseline_findings),
    }


def cmd_list_capsules(args: argparse.Namespace) -> int:
    registry = default_registry()
    capsules = registry.all_capsules()
    if args.domain:
        capsules = registry.for_domain(args.domain)
    if args.family:
        capsules = tuple(c for c in capsules if c.method_family == args.family)
    if not capsules:
        print("(no capsules match)")
        return 0
    print(f"{len(capsules)} capsule(s):")
    for c in capsules:
        print(
            f"  {c.capsule_id}\n"
            f"      family={c.method_family} risk_ceiling={c.risk_ceiling} "
            f"cost={c.cost_class} explainability={c.explainability}\n"
            f"      {c.metadata.get('summary', '')}"
        )
    return 0


def cmd_list_benchmarks(args: argparse.Namespace) -> int:
    benchmarks = list_benchmarks()
    print(f"{len(benchmarks)} benchmark(s):")
    for b in benchmarks:
        sig = b.signature
        print(
            f"  {b.benchmark_id}  (domain={sig.domain} risk={sig.risk} "
            f"primary={sig.success_metrics()[0].metric_id})\n"
            f"      {b.description}"
        )
    return 0


def _run(benchmark_id: str, ledger_out: str | None):
    ledger = None
    if ledger_out:
        ledger = CandidateLedger(JsonFileCandidateLedgerStore(ledger_out))
    return run_benchmark(benchmark_id, ledger=ledger)


def cmd_run(args: argparse.Namespace) -> int:
    try:
        report, ledger = _run(args.benchmark_id, args.ledger_out)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1

    payload = _report_to_dict(report, ledger)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0

    print(f"Benchmark: {payload['benchmark_id']}")
    print(
        f"Signature: {payload['signature_hash'][:12]}  "
        f"primary={payload['primary_metric_id']}  "
        f"baseline={payload['baseline_record_hash'][:12] or '(none)'}"
    )
    print(f"Baseline compromised: {payload['baseline_compromised']}")

    def _line(entry: dict) -> str:
        fam = ",".join(entry["method_families"])
        primary = payload["primary_metric_id"]
        score = entry["scores"].get(primary)
        delta = entry["baseline_delta"].get(primary)
        delta_str = f" delta={delta:+.4f}" if delta is not None else ""
        return f"    - {fam}  {primary}={score}{delta_str}  [{entry['outcome']}]"

    print(f"Winners ({len(payload['winners'])}):")
    for entry in payload["winners"] or []:
        print(_line(entry))
    print(f"Passed non-winners ({len(payload['passed_non_winners'])}):")
    for entry in payload["passed_non_winners"] or []:
        print(_line(entry) + "  (did not beat baseline on primary metric)")
    print(f"Negatives ({len(payload['negatives'])}):")
    for entry in payload["negatives"] or []:
        print(_line(entry))
    if payload["skipped_capsules"]:
        print("Skipped capsules:")
        for cid, reason in payload["skipped_capsules"].items():
            print(f"    - {cid}: {reason}")
    if args.ledger_out:
        print(f"Ledger written to: {args.ledger_out}")
    return 0


def cmd_forge_input(args: argparse.Namespace) -> int:
    """PREVIEW the Capability Forge input a winner would produce. Read-only:
    this never creates a package and never promotes anything."""
    try:
        report, ledger = run_benchmark(args.benchmark_id)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1
    if not report.winner_record_hashes:
        print("no winner to forge -- nothing beat the baseline on the primary metric")
        return 1

    runs = {r.record_hash: r for r in ledger.for_signature(report.signature_hash)}
    winner = runs[report.winner_record_hashes[0]]
    signature = get_benchmark(args.benchmark_id).signature

    forge_input = forge_input_for_winner(
        winner=winner,
        signature=signature,
        capability_id=args.capability_id,
        version=args.version,
        api_docs_ref=args.api_docs_ref,
        input_schema_ref=args.input_schema_ref,
        output_schema_ref=args.output_schema_ref,
        owner_team=args.owner_team,
        requires_approval=(signature.risk == "high"),
    )
    print("PREVIEW ONLY -- no capability package created, no promotion performed.")
    print(
        json.dumps(
            {
                "capability_id": forge_input.capability_id,
                "version": forge_input.version,
                "domain": forge_input.domain,
                "risk": forge_input.risk,
                "requires_approval": forge_input.requires_approval,
                "solver_forge_provenance": forge_input.metadata.get("solver_forge"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solver_forge_cli",
        description=(
            "Run the governed Solver Forge laboratory. Read + experiment only: "
            "this tool never promotes, installs, or deploys a capability."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_caps = sub.add_parser("list-capsules", help="list method registry capsules")
    p_caps.add_argument("--domain", default=None)
    p_caps.add_argument("--family", default=None)
    p_caps.set_defaults(func=cmd_list_capsules)

    p_bench = sub.add_parser("list-benchmarks", help="list runnable benchmarks")
    p_bench.set_defaults(func=cmd_list_benchmarks)

    p_run = sub.add_parser("run", help="run a benchmark through the composer")
    p_run.add_argument("benchmark_id")
    p_run.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_run.add_argument("--ledger-out", default=None, help="write the ledger to a JSON file")
    p_run.set_defaults(func=cmd_run)

    p_forge = sub.add_parser(
        "forge-input", help="PREVIEW the forge input a winner would produce (read-only)"
    )
    p_forge.add_argument("benchmark_id")
    p_forge.add_argument("--capability-id", dest="capability_id", required=True)
    p_forge.add_argument("--version", default="0.1.0")
    p_forge.add_argument("--owner-team", dest="owner_team", required=True)
    p_forge.add_argument("--api-docs-ref", dest="api_docs_ref", default="docs/api/TBD.md")
    p_forge.add_argument(
        "--input-schema-ref", dest="input_schema_ref", default="schemas/TBD.input.schema.json"
    )
    p_forge.add_argument(
        "--output-schema-ref", dest="output_schema_ref", default="schemas/TBD.output.schema.json"
    )
    p_forge.set_defaults(func=cmd_forge_input)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
