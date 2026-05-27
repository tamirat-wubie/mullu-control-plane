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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report Mullu Govern clearance capture readiness.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable readiness report.")
    parser.add_argument("--receipt-path", type=Path, help="Write the machine-readable report to this path.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when capture evidence is still blocked.")
    args = parser.parse_args([] if argv is None else argv)

    report = build_capture_readiness()
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
