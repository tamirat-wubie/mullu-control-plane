"""Regenerate or check the governed-planning-profile fixture chain.

Purpose: keep the deterministic governed-planning-profile examples aligned
with their upstream builder functions from shadow observation through runtime
authorization rejection.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: governed-planning-profile validator builders and checked-in JSON
fixtures under examples/.
Invariants: fixture writes are explicit via --write, checks are deterministic,
and the first stale fixture is reported without mutating files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.report_governed_planning_profile_shadow_dossier import build_shadow_dossier
from scripts.validate_governed_planning_profile_operator_shadow_pilot_evidence import (
    DEFAULT_FIXTURE as OPERATOR_SHADOW_PILOT_EVIDENCE_FIXTURE,
    build_operator_shadow_pilot_evidence_request,
)
from scripts.validate_governed_planning_profile_operator_shadow_pilot_observation_receipt import (
    DEFAULT_RECEIPT as OPERATOR_SHADOW_PILOT_OBSERVATION_RECEIPT,
    build_operator_shadow_pilot_observation_receipt,
)
from scripts.validate_governed_planning_profile_replay_recovery_witness import (
    DEFAULT_WITNESS as REPLAY_RECOVERY_WITNESS,
    build_replay_recovery_witness,
)
from scripts.validate_governed_planning_profile_runtime_authorization_approval_witness_template import (
    DEFAULT_TEMPLATE as RUNTIME_AUTHORIZATION_APPROVAL_WITNESS_TEMPLATE,
    build_approval_witness_template,
)
from scripts.validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection import (
    DEFAULT_WITNESS as RUNTIME_AUTHORIZATION_GENERIC_CONTINUATION_REJECTION,
    build_generic_continuation_rejection_witness,
)
from scripts.validate_governed_planning_profile_runtime_authorization_request import (
    DEFAULT_REQUEST as RUNTIME_AUTHORIZATION_REQUEST,
    build_runtime_authorization_request,
)
from scripts.validate_governed_planning_profile_runtime_authorization_signed_approval_generic_continuation_rejection import (
    DEFAULT_WITNESS as RUNTIME_AUTHORIZATION_SIGNED_APPROVAL_GENERIC_CONTINUATION_REJECTION,
    build_signed_approval_generic_continuation_rejection,
)
from scripts.validate_governed_planning_profile_runtime_authorization_signed_approval_intake import (
    DEFAULT_INTAKE as RUNTIME_AUTHORIZATION_SIGNED_APPROVAL_INTAKE,
    build_signed_approval_intake,
)
from scripts.validate_governed_planning_profile_runtime_promotion_approval_packet import (
    DEFAULT_PACKET as RUNTIME_PROMOTION_APPROVAL_PACKET,
    build_runtime_promotion_approval_packet,
)
from scripts.validate_governed_planning_profile_terminal_closure_certificate import (
    DEFAULT_CERTIFICATE as TERMINAL_CLOSURE_CERTIFICATE,
    build_terminal_closure_certificate,
)

@dataclass(frozen=True)
class FixtureCandidate:
    """A generated payload and the checked-in fixture it should match."""

    fixture_id: str
    path: Path
    payload: Mapping[str, Any]
    sort_keys: bool = True


@dataclass(frozen=True)
class FixtureEvaluation:
    """Comparison result for one fixture candidate."""

    fixture_id: str
    path: Path
    matched: bool
    action: str
    expected_sha256: str
    current_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "path": _repo_relative(self.path),
            "matched": self.matched,
            "action": self.action,
            "expected_sha256": self.expected_sha256,
            "current_sha256": self.current_sha256,
        }


def build_governed_planning_profile_fixture_chain() -> tuple[FixtureCandidate, ...]:
    """Build the deterministic fixture chain in causal dependency order."""

    shadow_dossier = build_shadow_dossier()
    operator_evidence = build_operator_shadow_pilot_evidence_request(shadow_dossier)
    operator_observation = build_operator_shadow_pilot_observation_receipt(
        dossier=shadow_dossier,
        evidence_request=operator_evidence,
    )
    runtime_promotion_packet = build_runtime_promotion_approval_packet(operator_observation)
    replay_recovery_witness = build_replay_recovery_witness(runtime_promotion_packet)
    terminal_closure_certificate = build_terminal_closure_certificate(replay_recovery_witness)
    runtime_authorization_request = build_runtime_authorization_request(
        terminal_closure_certificate
    )
    generic_continuation_rejection = build_generic_continuation_rejection_witness(
        runtime_authorization_request
    )
    approval_witness_template = build_approval_witness_template(
        runtime_authorization_request=runtime_authorization_request,
        generic_continuation_rejection=generic_continuation_rejection,
    )
    signed_approval_intake = build_signed_approval_intake(approval_witness_template)
    signed_approval_generic_rejection = build_signed_approval_generic_continuation_rejection(
        signed_approval_intake
    )

    return (
        FixtureCandidate(
            "operator_shadow_pilot_evidence",
            OPERATOR_SHADOW_PILOT_EVIDENCE_FIXTURE,
            operator_evidence,
        ),
        FixtureCandidate(
            "operator_shadow_pilot_observation_receipt",
            OPERATOR_SHADOW_PILOT_OBSERVATION_RECEIPT,
            operator_observation,
        ),
        FixtureCandidate(
            "runtime_promotion_approval_packet",
            RUNTIME_PROMOTION_APPROVAL_PACKET,
            runtime_promotion_packet,
        ),
        FixtureCandidate(
            "replay_recovery_witness",
            REPLAY_RECOVERY_WITNESS,
            replay_recovery_witness,
        ),
        FixtureCandidate(
            "terminal_closure_certificate",
            TERMINAL_CLOSURE_CERTIFICATE,
            terminal_closure_certificate,
        ),
        FixtureCandidate(
            "runtime_authorization_request",
            RUNTIME_AUTHORIZATION_REQUEST,
            runtime_authorization_request,
        ),
        FixtureCandidate(
            "runtime_authorization_generic_continuation_rejection",
            RUNTIME_AUTHORIZATION_GENERIC_CONTINUATION_REJECTION,
            generic_continuation_rejection,
        ),
        FixtureCandidate(
            "runtime_authorization_approval_witness_template",
            RUNTIME_AUTHORIZATION_APPROVAL_WITNESS_TEMPLATE,
            approval_witness_template,
        ),
        FixtureCandidate(
            "runtime_authorization_signed_approval_intake",
            RUNTIME_AUTHORIZATION_SIGNED_APPROVAL_INTAKE,
            signed_approval_intake,
        ),
        FixtureCandidate(
            "runtime_authorization_signed_approval_generic_continuation_rejection",
            RUNTIME_AUTHORIZATION_SIGNED_APPROVAL_GENERIC_CONTINUATION_REJECTION,
            signed_approval_generic_rejection,
        ),
    )


def evaluate_fixture_chain(
    candidates: Sequence[FixtureCandidate],
    *,
    write: bool = False,
) -> tuple[FixtureEvaluation, ...]:
    """Compare generated fixture payloads with checked-in files."""

    evaluations: list[FixtureEvaluation] = []
    for candidate in candidates:
        expected_text = _stable_json(candidate.payload, sort_keys=candidate.sort_keys)
        expected_hash = _sha256(expected_text)
        current_text = _read_text(candidate.path)
        current_hash = _sha256(current_text) if current_text is not None else None
        matched = current_text == expected_text
        action = "unchanged" if matched else "stale"

        if write and not matched:
            candidate.path.parent.mkdir(parents=True, exist_ok=True)
            candidate.path.write_text(expected_text, encoding="utf-8")
            current_hash = expected_hash
            matched = True
            action = "written"

        evaluations.append(
            FixtureEvaluation(
                fixture_id=candidate.fixture_id,
                path=candidate.path,
                matched=matched,
                action=action,
                expected_sha256=expected_hash,
                current_sha256=current_hash,
            )
        )
    return tuple(evaluations)


def first_stale_fixture(
    evaluations: Iterable[FixtureEvaluation],
) -> FixtureEvaluation | None:
    """Return the first non-matching fixture in causal order."""

    return next((evaluation for evaluation in evaluations if not evaluation.matched), None)


def build_summary(evaluations: Sequence[FixtureEvaluation]) -> dict[str, Any]:
    stale = [evaluation for evaluation in evaluations if not evaluation.matched]
    first_stale = stale[0] if stale else None
    return {
        "status": "passed" if not stale else "stale",
        "fixture_count": len(evaluations),
        "stale_count": len(stale),
        "first_stale_fixture": first_stale.as_dict() if first_stale else None,
        "fixtures": [evaluation.as_dict() for evaluation in evaluations],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Check fixtures without writing. This is the default.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite stale fixtures from the deterministic builder chain.",
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON result envelope.")
    args = parser.parse_args(argv)

    evaluations = evaluate_fixture_chain(
        build_governed_planning_profile_fixture_chain(),
        write=args.write,
    )
    summary = build_summary(evaluations)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        _print_text_summary(summary)

    return 0 if summary["status"] == "passed" else 1


def _print_text_summary(summary: Mapping[str, Any]) -> None:
    print(f"STATUS: {summary['status']}")
    print(f"fixtures: {summary['fixture_count']}")
    print(f"stale: {summary['stale_count']}")
    first_stale = summary.get("first_stale_fixture")
    if first_stale:
        print(f"first_stale_fixture: {first_stale['path']}")
        print(
            "next_action: python "
            "scripts/regenerate_governed_planning_profile_fixture_chain.py --write"
        )


def _stable_json(payload: Mapping[str, Any], *, sort_keys: bool) -> str:
    return json.dumps(payload, indent=2, sort_keys=sort_keys) + "\n"


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
