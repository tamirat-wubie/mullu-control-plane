"""Purpose: report GCI capability-contract coverage for governed tool registries.
Governance scope: read-only coverage audit; no execution authority is granted.
Dependencies: GCI capability contract evaluator and ToolDefinition-like records.
Invariants: reports are deterministic, side-effect free, and fail closed on blocked contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from mcoi_runtime.contracts.capability_contract import (
    CapabilityAdmissionStatus,
    CapabilityContract,
    evaluate_capability_contract,
)


class CapabilityContractTool(Protocol):
    """Structural tool shape needed for coverage auditing."""

    name: str
    enabled: bool
    capability_contract: CapabilityContract | None
    capability_contract_explicit: bool


@dataclass(frozen=True, slots=True)
class CapabilityContractCoverageIssue:
    """One missing or blocked capability-contract finding."""

    tool_name: str
    status: CapabilityAdmissionStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CapabilityContractCoverageRecord:
    """Read model for one registered tool's GCI contract coverage."""

    tool_name: str
    enabled: bool
    explicit_contract: bool
    contract_present: bool
    admission_status: CapabilityAdmissionStatus
    reasons: tuple[str, ...]

    @property
    def covered(self) -> bool:
        """True when the tool has a contract that satisfies Phi_gov admission."""
        return self.contract_present and self.admission_status is CapabilityAdmissionStatus.ENABLED


@dataclass(frozen=True, slots=True)
class CapabilityContractCoverageReport:
    """Aggregate GCI coverage read model for a governed tool registry."""

    tool_count: int
    enabled_tool_count: int
    covered_tool_count: int
    explicit_contract_count: int
    synthesized_contract_count: int
    blocked_tool_count: int
    records: tuple[CapabilityContractCoverageRecord, ...]
    issues: tuple[CapabilityContractCoverageIssue, ...]

    @property
    def complete(self) -> bool:
        """True when every registered tool has a Phi_gov-admitted contract."""
        return self.tool_count == self.covered_tool_count and not self.issues

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready report."""
        return {
            "tool_count": self.tool_count,
            "enabled_tool_count": self.enabled_tool_count,
            "covered_tool_count": self.covered_tool_count,
            "explicit_contract_count": self.explicit_contract_count,
            "synthesized_contract_count": self.synthesized_contract_count,
            "blocked_tool_count": self.blocked_tool_count,
            "complete": self.complete,
            "records": [
                {
                    "tool_name": record.tool_name,
                    "enabled": record.enabled,
                    "explicit_contract": record.explicit_contract,
                    "contract_present": record.contract_present,
                    "admission_status": record.admission_status.value,
                    "reasons": list(record.reasons),
                    "covered": record.covered,
                }
                for record in self.records
            ],
            "issues": [
                {
                    "tool_name": issue.tool_name,
                    "status": issue.status.value,
                    "reasons": list(issue.reasons),
                }
                for issue in self.issues
            ],
        }


def audit_capability_contract_coverage(
    tools: Iterable[CapabilityContractTool],
) -> CapabilityContractCoverageReport:
    """Evaluate registered tools for GCI capability-contract coverage."""
    records: list[CapabilityContractCoverageRecord] = []
    issues: list[CapabilityContractCoverageIssue] = []

    for tool in sorted(tools, key=lambda item: item.name):
        decision = evaluate_capability_contract(tool.capability_contract)
        record = CapabilityContractCoverageRecord(
            tool_name=tool.name,
            enabled=tool.enabled,
            explicit_contract=tool.capability_contract_explicit,
            contract_present=tool.capability_contract is not None,
            admission_status=decision.status,
            reasons=decision.reasons,
        )
        records.append(record)
        if not record.covered:
            issues.append(
                CapabilityContractCoverageIssue(
                    tool_name=tool.name,
                    status=decision.status,
                    reasons=decision.reasons,
                )
            )

    return CapabilityContractCoverageReport(
        tool_count=len(records),
        enabled_tool_count=sum(1 for record in records if record.enabled),
        covered_tool_count=sum(1 for record in records if record.covered),
        explicit_contract_count=sum(1 for record in records if record.explicit_contract),
        synthesized_contract_count=sum(1 for record in records if not record.explicit_contract),
        blocked_tool_count=len(issues),
        records=tuple(records),
        issues=tuple(issues),
    )
