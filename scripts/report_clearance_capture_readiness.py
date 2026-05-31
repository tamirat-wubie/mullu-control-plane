"""Report missing Mullu Govern clearance capture files.

Purpose: derive the current file-level intake state from capture requirements.
Governance scope: remaining naming clearance gates and evidence file presence.
Dependencies: docs/clearance-evidence/mullu/2026-05-15/capture-requirements.json.
Invariants: this report is read-only and never changes launch state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_PATH = (
    REPO_ROOT
    / "docs"
    / "clearance-evidence"
    / "mullu"
    / "2026-05-15"
    / "capture-requirements.json"
)
SOURCE_REFS_BY_GATE = {
    "uspto_search": (
        "USPTO Trademark Search: https://tmsearch.uspto.gov/",
        "USPTO search guidance: https://www.uspto.gov/trademarks/search",
    ),
    "wipo_search": (
        "WIPO Global Brand Database: https://www.wipo.int/reference/en/branddb/",
    ),
    "euipo_tmview_search": (
        "EUIPO eSearch plus: https://www.euipo.europa.eu/en/search-ip",
        "TMview: https://www.tmdn.org/tmview/",
    ),
    "close_variant_review": (
        "USPTO TSDR: https://tsdr.uspto.gov/",
        "USPTO TSDR status guidance: https://www.uspto.gov/trademarks/apply/check-status-view-documents",
    ),
    "domain_ownership": (
        "ICANN Lookup: https://lookup.icann.org/en/lookup",
        "selected registrar account",
        "authoritative DNS provider account",
        "HTTPS certificate issuer or certificate transparency record",
    ),
    "legal_review": (
        "qualified legal or trademark reviewer decision packet",
    ),
}

SEARCH_QUERY_BY_REQUIRED_FILE = {
    "uspto-search-mullu-govern.pdf": "Mullu Govern",
    "uspto-search-mullu.pdf": "MULLU",
    "uspto-search-mullusi.pdf": "MULLUSI",
    "uspto-search-mullu-govern-by-mullusi.pdf": "Mullu Govern by Mullusi",
    "uspto-search-mullu-by-mullusi.pdf": "Mullu by Mullusi",
    "uspto-search-mullu-surfaces.pdf": "Mullu Inspect; Mullu CLI; Mullu Code; Mullu Control Plane",
    "uspto-search-mulu.pdf": "MULU",
    "wipo-search-mullu-govern.pdf": "Mullu Govern",
    "wipo-search-mullu.pdf": "MULLU",
    "wipo-search-mullusi.pdf": "MULLUSI",
    "wipo-search-mullu-govern-by-mullusi.pdf": "Mullu Govern by Mullusi",
    "wipo-search-mullu-by-mullusi.pdf": "Mullu by Mullusi",
    "euipo-search-mullu-govern.pdf": "Mullu Govern",
    "euipo-search-mullu.pdf": "MULLU",
    "euipo-search-mullusi.pdf": "MULLUSI",
    "euipo-search-mullu-govern-by-mullusi.pdf": "Mullu Govern by Mullusi",
    "euipo-search-mullu-by-mullusi.pdf": "Mullu by Mullusi",
    "tmview-search-mullu-govern.pdf": "Mullu Govern",
    "tmview-search-mullu.pdf": "MULLU",
    "tmview-search-mullusi.pdf": "MULLUSI",
    "tmview-search-mullu-govern-by-mullusi.pdf": "Mullu Govern by Mullusi",
    "tmview-search-mullu-by-mullusi.pdf": "Mullu by Mullusi",
    "tsdr-99518598.pdf": "99518598",
    "tsdr-99264214.pdf": "99264214",
    "tsdr-85772539.pdf": "85772539",
    "tsdr-85494313.pdf": "85494313",
    "tsdr-85222451.pdf": "85222451",
    "mulu-confusion-analysis.md": "Mullu Govern and MULLU compared against MULU-like marks",
    "registrar-ownership.pdf": "selected launch route registrar ownership",
    "dns-zone-control.pdf": "selected launch route DNS zone authority",
    "https-certificate.pdf": "selected launch route HTTPS certificate",
    "renewal-and-lock-controls.pdf": "selected launch route renewal, MFA, and lock controls",
    "legal-review-decision.pdf": "signed qualified legal or trademark decision",
    "reviewed-evidence-list.md": "complete reviewed evidence file list",
}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _gate_missing_files(evidence_root: Path, gate: dict[str, object]) -> list[str]:
    directory = evidence_root / str(gate["directory"])
    required_files = [str(required_file) for required_file in gate["required_files"]]
    return [required_file for required_file in required_files if not (directory / required_file).exists()]


def build_capture_readiness(requirements_path: Path = REQUIREMENTS_PATH) -> dict[str, Any]:
    requirements = _read_json(requirements_path)
    evidence_root = _resolve_evidence_root(requirements["evidence_root"])
    gates = [gate for gate in requirements["gates"] if isinstance(gate, dict)]

    gate_reports: list[dict[str, Any]] = []
    total_required = 0
    total_missing = 0

    for gate in gates:
        required_files = [str(required_file) for required_file in gate["required_files"]]
        missing_files = _gate_missing_files(evidence_root, gate)
        present_files = [required_file for required_file in required_files if required_file not in missing_files]
        total_required += len(required_files)
        total_missing += len(missing_files)
        gate_reports.append(
            {
                "gate": gate["gate"],
                "directory": gate["directory"],
                "authority": gate["authority"],
                "required_count": len(required_files),
                "present_count": len(present_files),
                "missing_count": len(missing_files),
                "present_files": present_files,
                "missing_files": missing_files,
                "status": "capture_ready_for_review" if not missing_files else "blocked",
            }
        )

    total_present = total_required - total_missing
    status = "capture_ready_for_review" if total_missing == 0 else "blocked"
    return {
        "product_name": requirements["product_name"],
        "suite_family": requirements["suite_family"],
        "company_brand": requirements["company_brand"],
        "evidence_root": requirements["evidence_root"],
        "public_paid_launch_allowed": requirements["public_paid_launch_allowed"],
        "required_files_present": total_present,
        "required_files_total": total_required,
        "required_files_missing": total_missing,
        "gates": gate_reports,
        "status": status,
    }


def build_capture_manifest(requirements_path: Path = REQUIREMENTS_PATH) -> dict[str, Any]:
    requirements = _read_json(requirements_path)
    evidence_root = _resolve_evidence_root(requirements["evidence_root"])
    evidence_root_display = str(requirements["evidence_root"])
    gates = [gate for gate in requirements["gates"] if isinstance(gate, dict)]

    tasks: list[dict[str, Any]] = []
    for gate in gates:
        gate_name = str(gate["gate"])
        directory = str(gate["directory"])
        required_files = [str(required_file) for required_file in gate["required_files"]]
        source_refs = SOURCE_REFS_BY_GATE[gate_name]
        gate_dir = evidence_root / directory
        for required_file in required_files:
            if required_file == "decision.md":
                continue
            output_path = f"{evidence_root_display}{directory}{required_file}"
            tasks.append(
                {
                    "gate": gate_name,
                    "directory": directory,
                    "required_file": required_file,
                    "output_path": output_path,
                    "authority": gate["authority"],
                    "source_refs": list(source_refs),
                    "query_or_record": SEARCH_QUERY_BY_REQUIRED_FILE[required_file],
                    "present": (gate_dir / required_file).exists(),
                    "gate_impact": "non_closing_capture_only",
                }
            )

    return {
        "product_name": requirements["product_name"],
        "suite_family": requirements["suite_family"],
        "company_brand": requirements["company_brand"],
        "evidence_root": evidence_root_display,
        "public_paid_launch_allowed": requirements["public_paid_launch_allowed"],
        "task_count": len(tasks),
        "tasks": tasks,
        "mutation_rule": requirements["mutation_rule"],
        "status": "capture_manifest_ready",
    }


def _resolve_evidence_root(raw_evidence_root: object) -> Path:
    evidence_root = Path(str(raw_evidence_root))
    if evidence_root.is_absolute():
        return evidence_root
    return REPO_ROOT / evidence_root


def print_capture_readiness(report: dict[str, Any]) -> None:
    print("Mullu Govern Clearance Capture Readiness")
    print("========================================")
    print(f"Product: {report['product_name']}")
    print(f"Suite/family: {report['suite_family']}")
    print(f"Company: {report['company_brand']}")
    print(f"Evidence root: {report['evidence_root']}")
    print(f"Paid public launch allowed: {report['public_paid_launch_allowed']}")
    print()

    for gate in report["gates"]:
        print(f"{gate['gate']}: {gate['present_count']}/{gate['required_count']} required files present")
        print(f"  directory: {gate['directory']}")
        print(f"  authority: {gate['authority']}")
        if gate["missing_files"]:
            print("  missing:")
            for missing_file in gate["missing_files"]:
                print(f"    - {missing_file}")
        else:
            print("  missing: none")
        print()

    print(f"Required files present: {report['required_files_present']}/{report['required_files_total']}")
    print(f"Required files missing: {report['required_files_missing']}")
    print(f"STATUS: {report['status']}")


def render_capture_manifest(manifest: dict[str, Any]) -> str:
    lines = [
        "Mullu Govern Clearance Capture Manifest",
        "=======================================",
        f"Product: {manifest['product_name']}",
        f"Suite/family: {manifest['suite_family']}",
        f"Company: {manifest['company_brand']}",
        f"Evidence root: {manifest['evidence_root']}",
        f"Paid public launch allowed: {manifest['public_paid_launch_allowed']}",
        "",
        "Gate impact: every task is non-closing capture only.",
        f"Mutation rule: {manifest['mutation_rule']}",
        "",
    ]
    current_gate = ""
    for task in manifest["tasks"]:
        if task["gate"] != current_gate:
            current_gate = task["gate"]
            lines.extend([f"## {current_gate}", ""])
        lines.extend(
            [
                f"- Output file: `{task['output_path']}`",
                f"  Query or record: `{task['query_or_record']}`",
                f"  Required authority: {task['authority']}",
                f"  Present: {task['present']}",
                f"  Gate impact: {task['gate_impact']}",
                "  Source refs:",
            ]
        )
        for source_ref in task["source_refs"]:
            lines.append(f"    - {source_ref}")
        lines.append("")
    lines.extend(
        [
            f"Task count: {manifest['task_count']}",
            f"STATUS: {manifest['status']}",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report Mullu Govern clearance capture readiness.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable readiness report.")
    parser.add_argument("--receipt-path", type=Path, help="Write the machine-readable report to this path.")
    parser.add_argument("--capture-manifest", action="store_true", help="Emit a file-level capture manifest.")
    parser.add_argument("--manifest-path", type=Path, help="Write the file-level capture manifest to this path.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when capture evidence is still blocked.")
    args = parser.parse_args([] if argv is None else argv)

    report = build_capture_readiness()
    if args.capture_manifest or args.manifest_path is not None:
        manifest_text = render_capture_manifest(build_capture_manifest())
        if args.manifest_path is not None:
            args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            args.manifest_path.write_text(manifest_text, encoding="utf-8")
        if args.capture_manifest:
            print(manifest_text, end="")
        if args.strict and report["status"] != "capture_ready_for_review":
            return 1
        return 0

    report_json = json.dumps(report, indent=2, sort_keys=True)
    if args.receipt_path is not None:
        args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_path.write_text(f"{report_json}\n", encoding="utf-8")
    if args.json:
        print(report_json)
    else:
        print_capture_readiness(report)
    if args.strict and report["status"] != "capture_ready_for_review":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
