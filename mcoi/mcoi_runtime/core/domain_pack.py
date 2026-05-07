"""Purpose: domain pack engine.
Governance scope: registering, activating, deprecating, resolving, and
    managing domain-specific behavior packs.
Dependencies: domain_pack contracts, core invariants.
Invariants:
  - No duplicate pack IDs.
  - Only ACTIVE packs participate in resolution.
  - Deterministic resolution order.
  - Higher-specificity scope beats lower-specificity scope.
  - Version conflicts surfaced explicitly.
  - Immutable returns only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Mapping

from ..contracts.domain_pack import (
    DomainBenchmarkProfile,
    DomainEscalationProfile,
    DomainExtractionRule,
    DomainMemoryRule,
    DomainPackActivation,
    DomainPackConflict,
    DomainPackDescriptor,
    DomainPackResolution,
    DomainPackStatus,
    DomainRoutingRule,
    DomainRuleKind,
    DomainSimulationProfile,
    DomainUtilityProfile,
    DomainVocabularyEntry,
    PackScope,
    scope_specificity,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DomainPackEngine:
    """Manages domain pack lifecycle and resolution."""

    def __init__(self) -> None:
        self._packs: dict[str, DomainPackDescriptor] = {}
        self._activations: list[DomainPackActivation] = []
        self._extraction_rules: dict[str, DomainExtractionRule] = {}
        self._routing_rules: dict[str, DomainRoutingRule] = {}
        self._memory_rules: dict[str, DomainMemoryRule] = {}
        self._simulation_profiles: dict[str, DomainSimulationProfile] = {}
        self._utility_profiles: dict[str, DomainUtilityProfile] = {}
        self._benchmark_profiles: dict[str, DomainBenchmarkProfile] = {}
        self._escalation_profiles: dict[str, DomainEscalationProfile] = {}
        self._vocabulary: dict[str, DomainVocabularyEntry] = {}
        self._conflicts: dict[str, DomainPackConflict] = {}
        self._resolutions: list[DomainPackResolution] = []

    # -----------------------------------------------------------------------
    # Pack lifecycle
    # -----------------------------------------------------------------------

    def register_pack(self, descriptor: DomainPackDescriptor) -> DomainPackDescriptor:
        """Register a new domain pack. Rejects duplicates."""
        if not isinstance(descriptor, DomainPackDescriptor):
            raise RuntimeCoreInvariantError("descriptor must be a DomainPackDescriptor")
        if descriptor.pack_id in self._packs:
            raise RuntimeCoreInvariantError(
                "pack already registered"
            )
        self._packs[descriptor.pack_id] = descriptor
        return descriptor

    def activate_pack(self, pack_id: str) -> DomainPackActivation:
        """Activate a pack. Only DRAFT or DISABLED packs can be activated."""
        pack = self._get_pack_or_raise(pack_id)
        if pack.status == DomainPackStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                "pack already active"
            )
        if pack.status == DomainPackStatus.DEPRECATED:
            raise RuntimeCoreInvariantError(
                "deprecated pack cannot be activated"
            )
        now = _now_iso()
        activation = DomainPackActivation(
            activation_id=stable_identifier("pack-activation", {"pack_id": pack_id, "ts": now}),
            pack_id=pack_id,
            previous_status=pack.status,
            new_status=DomainPackStatus.ACTIVE,
            activated_at=now,
            reason="activated",
        )
        # Update pack status
        updated = DomainPackDescriptor(
            pack_id=pack.pack_id,
            domain_name=pack.domain_name,
            version=pack.version,
            status=DomainPackStatus.ACTIVE,
            scope=pack.scope,
            scope_ref_id=pack.scope_ref_id,
            description=pack.description,
            tags=pack.tags,
            created_at=pack.created_at,
            updated_at=now,
            metadata=dict(pack.metadata),
        )
        self._packs[pack_id] = updated
        self._activations.append(activation)
        return activation

    def deprecate_pack(self, pack_id: str) -> DomainPackActivation:
        """Deprecate a pack. Only ACTIVE packs can be deprecated."""
        pack = self._get_pack_or_raise(pack_id)
        if pack.status != DomainPackStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                "pack must be active before deprecation"
            )
        now = _now_iso()
        activation = DomainPackActivation(
            activation_id=stable_identifier("pack-deprecate", {"pack_id": pack_id, "ts": now}),
            pack_id=pack_id,
            previous_status=pack.status,
            new_status=DomainPackStatus.DEPRECATED,
            activated_at=now,
            reason="deprecated",
        )
        updated = DomainPackDescriptor(
            pack_id=pack.pack_id,
            domain_name=pack.domain_name,
            version=pack.version,
            status=DomainPackStatus.DEPRECATED,
            scope=pack.scope,
            scope_ref_id=pack.scope_ref_id,
            description=pack.description,
            tags=pack.tags,
            created_at=pack.created_at,
            updated_at=now,
            metadata=dict(pack.metadata),
        )
        self._packs[pack_id] = updated
        self._activations.append(activation)
        return activation

    def disable_pack(self, pack_id: str) -> DomainPackActivation:
        """Disable a pack. Only ACTIVE packs can be disabled."""
        pack = self._get_pack_or_raise(pack_id)
        if pack.status != DomainPackStatus.ACTIVE:
            raise RuntimeCoreInvariantError(
                "pack must be active before disable"
            )
        now = _now_iso()
        activation = DomainPackActivation(
            activation_id=stable_identifier("pack-disable", {"pack_id": pack_id, "ts": now}),
            pack_id=pack_id,
            previous_status=pack.status,
            new_status=DomainPackStatus.DISABLED,
            activated_at=now,
            reason="disabled",
        )
        updated = DomainPackDescriptor(
            pack_id=pack.pack_id,
            domain_name=pack.domain_name,
            version=pack.version,
            status=DomainPackStatus.DISABLED,
            scope=pack.scope,
            scope_ref_id=pack.scope_ref_id,
            description=pack.description,
            tags=pack.tags,
            created_at=pack.created_at,
            updated_at=now,
            metadata=dict(pack.metadata),
        )
        self._packs[pack_id] = updated
        self._activations.append(activation)
        return activation

    def get_pack(self, pack_id: str) -> DomainPackDescriptor:
        """Get a pack by ID."""
        return self._get_pack_or_raise(pack_id)

    def list_packs(
        self,
        *,
        domain_name: str = "",
        status: DomainPackStatus | None = None,
        scope: PackScope | None = None,
    ) -> tuple[DomainPackDescriptor, ...]:
        """List packs with optional filters."""
        result = list(self._packs.values())
        if domain_name:
            result = [p for p in result if p.domain_name == domain_name]
        if status is not None:
            result = [p for p in result if p.status == status]
        if scope is not None:
            result = [p for p in result if p.scope == scope]
        return tuple(sorted(result, key=lambda p: p.pack_id))

    def list_active_packs(
        self,
        *,
        domain_name: str = "",
        scope: PackScope | None = None,
    ) -> tuple[DomainPackDescriptor, ...]:
        """List only ACTIVE packs."""
        return self.list_packs(
            domain_name=domain_name,
            status=DomainPackStatus.ACTIVE,
            scope=scope,
        )

    # -----------------------------------------------------------------------
    # Rule / profile registration
    # -----------------------------------------------------------------------

    def add_extraction_rule(self, rule: DomainExtractionRule) -> None:
        """Add an extraction rule. Pack must exist."""
        if not isinstance(rule, DomainExtractionRule):
            raise RuntimeCoreInvariantError("must be a DomainExtractionRule")
        self._get_pack_or_raise(rule.pack_id)
        if rule.rule_id in self._extraction_rules:
            raise RuntimeCoreInvariantError(
                "duplicate extraction rule"
            )
        self._extraction_rules[rule.rule_id] = rule

    def add_routing_rule(self, rule: DomainRoutingRule) -> None:
        """Add a routing rule. Pack must exist."""
        if not isinstance(rule, DomainRoutingRule):
            raise RuntimeCoreInvariantError("must be a DomainRoutingRule")
        self._get_pack_or_raise(rule.pack_id)
        if rule.rule_id in self._routing_rules:
            raise RuntimeCoreInvariantError(
                "duplicate routing rule"
            )
        self._routing_rules[rule.rule_id] = rule

    def add_memory_rule(self, rule: DomainMemoryRule) -> None:
        """Add a memory rule. Pack must exist."""
        if not isinstance(rule, DomainMemoryRule):
            raise RuntimeCoreInvariantError("must be a DomainMemoryRule")
        self._get_pack_or_raise(rule.pack_id)
        if rule.rule_id in self._memory_rules:
            raise RuntimeCoreInvariantError(
                "duplicate memory rule"
            )
        self._memory_rules[rule.rule_id] = rule

    def add_simulation_profile(self, profile: DomainSimulationProfile) -> None:
        """Add a simulation profile. Pack must exist."""
        if not isinstance(profile, DomainSimulationProfile):
            raise RuntimeCoreInvariantError("must be a DomainSimulationProfile")
        self._get_pack_or_raise(profile.pack_id)
        if profile.profile_id in self._simulation_profiles:
            raise RuntimeCoreInvariantError(
                "duplicate simulation profile"
            )
        self._simulation_profiles[profile.profile_id] = profile

    def add_utility_profile(self, profile: DomainUtilityProfile) -> None:
        """Add a utility profile. Pack must exist."""
        if not isinstance(profile, DomainUtilityProfile):
            raise RuntimeCoreInvariantError("must be a DomainUtilityProfile")
        self._get_pack_or_raise(profile.pack_id)
        if profile.profile_id in self._utility_profiles:
            raise RuntimeCoreInvariantError(
                "duplicate utility profile"
            )
        self._utility_profiles[profile.profile_id] = profile

    def add_benchmark_profile(self, profile: DomainBenchmarkProfile) -> None:
        """Add a benchmark profile. Pack must exist."""
        if not isinstance(profile, DomainBenchmarkProfile):
            raise RuntimeCoreInvariantError("must be a DomainBenchmarkProfile")
        self._get_pack_or_raise(profile.pack_id)
        if profile.profile_id in self._benchmark_profiles:
            raise RuntimeCoreInvariantError(
                "duplicate benchmark profile"
            )
        self._benchmark_profiles[profile.profile_id] = profile

    def add_escalation_profile(self, profile: DomainEscalationProfile) -> None:
        """Add an escalation profile. Pack must exist."""
        if not isinstance(profile, DomainEscalationProfile):
            raise RuntimeCoreInvariantError("must be a DomainEscalationProfile")
        self._get_pack_or_raise(profile.pack_id)
        if profile.profile_id in self._escalation_profiles:
            raise RuntimeCoreInvariantError(
                "duplicate escalation profile"
            )
        self._escalation_profiles[profile.profile_id] = profile

    def add_vocabulary_entry(self, entry: DomainVocabularyEntry) -> None:
        """Add a vocabulary entry. Pack must exist."""
        if not isinstance(entry, DomainVocabularyEntry):
            raise RuntimeCoreInvariantError("must be a DomainVocabularyEntry")
        self._get_pack_or_raise(entry.pack_id)
        if entry.entry_id in self._vocabulary:
            raise RuntimeCoreInvariantError(
                "duplicate vocabulary entry"
            )
        self._vocabulary[entry.entry_id] = entry

    # -----------------------------------------------------------------------
    # Resolution — deterministic scope-based pack selection
    # -----------------------------------------------------------------------

    def resolve_for_scope(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
        *,
        rule_kind: DomainRuleKind | None = None,
    ) -> DomainPackResolution:
        """Resolve which active packs apply at this scope.

        Resolution rules:
        1. Only ACTIVE packs participate.
        2. Exact scope_ref match first.
        3. Narrower scope beats broader scope.
        4. Higher version wins when scope and status are equal.
        5. Conflicts are surfaced explicitly.
        """
        active = [p for p in self._packs.values()
                  if p.status == DomainPackStatus.ACTIVE]

        # Filter by scope applicability: pack scope must be <= requested scope
        applicable = []
        requested_spec = scope_specificity(scope)
        for p in active:
            pack_spec = scope_specificity(p.scope)
            if pack_spec <= requested_spec:
                applicable.append(p)

        # Sort by specificity (most specific first), then version descending, then pack_id
        applicable.sort(
            key=lambda p: (-scope_specificity(p.scope), p.version, p.pack_id),
            reverse=False,
        )
        # Re-sort: highest specificity first, then highest version, then pack_id
        applicable.sort(
            key=lambda p: (scope_specificity(p.scope), p.version),
            reverse=True,
        )

        # If scope_ref_id provided, prefer exact match
        if scope_ref_id:
            exact_match = [p for p in applicable if p.scope_ref_id == scope_ref_id]
            non_exact = [p for p in applicable if p.scope_ref_id != scope_ref_id]
            # Exact matches first, then non-exact
            applicable = exact_match + [p for p in non_exact if not p.scope_ref_id]

        # Detect conflicts: same domain_name, same scope, different pack_id
        conflict_ids = []
        seen_domains: dict[str, str] = {}
        for p in applicable:
            key = (p.domain_name, p.scope)
            if p.domain_name in seen_domains and seen_domains[p.domain_name] != p.pack_id:
                # Create conflict
                conflict = self._record_conflict(
                    seen_domains[p.domain_name], p.pack_id,
                    rule_kind or DomainRuleKind.EXTRACTION, p.scope,
                )
                conflict_ids.append(conflict.conflict_id)
            else:
                seen_domains[p.domain_name] = p.pack_id

        now = _now_iso()
        resolution = DomainPackResolution(
            resolution_id=stable_identifier("pack-resolve", {"scope": str(scope), "ref": scope_ref_id, "seq": str(len(self._resolutions))}),
            scope=scope,
            scope_ref_id=scope_ref_id,
            resolved_pack_ids=tuple(p.pack_id for p in applicable),
            rule_kind=rule_kind or DomainRuleKind.EXTRACTION,
            conflict_ids=tuple(conflict_ids),
            resolved_at=now,
        )
        self._resolutions.append(resolution)
        return resolution

    def resolve_extraction_rules(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> tuple[DomainExtractionRule, ...]:
        """Resolve extraction rules for a scope, ordered by priority."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.EXTRACTION,
        )
        rules = [
            r for r in self._extraction_rules.values()
            if r.pack_id in resolution.resolved_pack_ids
            and self._packs[r.pack_id].status == DomainPackStatus.ACTIVE
        ]
        return tuple(sorted(rules, key=lambda r: (-r.priority, r.rule_id)))

    def resolve_routing_rules(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> tuple[DomainRoutingRule, ...]:
        """Resolve routing rules for a scope."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.ROUTING,
        )
        rules = [
            r for r in self._routing_rules.values()
            if r.pack_id in resolution.resolved_pack_ids
            and self._packs[r.pack_id].status == DomainPackStatus.ACTIVE
        ]
        return tuple(sorted(rules, key=lambda r: (-r.priority, r.rule_id)))

    def resolve_memory_rules(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> tuple[DomainMemoryRule, ...]:
        """Resolve memory rules for a scope."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.MEMORY,
        )
        rules = [
            r for r in self._memory_rules.values()
            if r.pack_id in resolution.resolved_pack_ids
            and self._packs[r.pack_id].status == DomainPackStatus.ACTIVE
        ]
        return tuple(sorted(rules, key=lambda r: r.rule_id))

    def resolve_simulation_profile(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> DomainSimulationProfile | None:
        """Resolve simulation profile for a scope (most specific wins)."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.SIMULATION,
        )
        profiles = [
            p for p in self._simulation_profiles.values()
            if p.pack_id in resolution.resolved_pack_ids
            and self._packs[p.pack_id].status == DomainPackStatus.ACTIVE
        ]
        if not profiles:
            return None
        # Most specific pack's profile wins
        profiles.sort(
            key=lambda p: (
                scope_specificity(self._packs[p.pack_id].scope),
                self._packs[p.pack_id].version,
            ),
            reverse=True,
        )
        return profiles[0]

    def resolve_utility_profile(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> DomainUtilityProfile | None:
        """Resolve utility profile for a scope (most specific wins)."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.UTILITY,
        )
        profiles = [
            p for p in self._utility_profiles.values()
            if p.pack_id in resolution.resolved_pack_ids
            and self._packs[p.pack_id].status == DomainPackStatus.ACTIVE
        ]
        if not profiles:
            return None
        profiles.sort(
            key=lambda p: (
                scope_specificity(self._packs[p.pack_id].scope),
                self._packs[p.pack_id].version,
            ),
            reverse=True,
        )
        return profiles[0]

    def resolve_benchmark_profile(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> DomainBenchmarkProfile | None:
        """Resolve benchmark profile for a scope (most specific wins)."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.BENCHMARK,
        )
        profiles = [
            p for p in self._benchmark_profiles.values()
            if p.pack_id in resolution.resolved_pack_ids
            and self._packs[p.pack_id].status == DomainPackStatus.ACTIVE
        ]
        if not profiles:
            return None
        profiles.sort(
            key=lambda p: (
                scope_specificity(self._packs[p.pack_id].scope),
                self._packs[p.pack_id].version,
            ),
            reverse=True,
        )
        return profiles[0]

    def resolve_escalation_profile(
        self,
        scope: PackScope,
        scope_ref_id: str = "",
    ) -> DomainEscalationProfile | None:
        """Resolve escalation profile for a scope (most specific wins)."""
        resolution = self.resolve_for_scope(
            scope, scope_ref_id, rule_kind=DomainRuleKind.ESCALATION,
        )
        profiles = [
            p for p in self._escalation_profiles.values()
            if p.pack_id in resolution.resolved_pack_ids
            and self._packs[p.pack_id].status == DomainPackStatus.ACTIVE
        ]
        if not profiles:
            return None
        profiles.sort(
            key=lambda p: (
                scope_specificity(self._packs[p.pack_id].scope),
                self._packs[p.pack_id].version,
            ),
            reverse=True,
        )
        return profiles[0]

    def find_conflicts(
        self,
        scope: PackScope | None = None,
    ) -> tuple[DomainPackConflict, ...]:
        """Return all recorded conflicts, optionally filtered by scope."""
        conflicts = list(self._conflicts.values())
        if scope is not None:
            conflicts = [c for c in conflicts if c.scope == scope]
        return tuple(sorted(conflicts, key=lambda c: c.conflict_id))

    # -----------------------------------------------------------------------
    # Retrieval helpers
    # -----------------------------------------------------------------------

    def get_extraction_rules_for_pack(
        self, pack_id: str,
    ) -> tuple[DomainExtractionRule, ...]:
        """Get all extraction rules for a specific pack."""
        self._get_pack_or_raise(pack_id)
        rules = [r for r in self._extraction_rules.values() if r.pack_id == pack_id]
        return tuple(sorted(rules, key=lambda r: (-r.priority, r.rule_id)))

    def get_routing_rules_for_pack(
        self, pack_id: str,
    ) -> tuple[DomainRoutingRule, ...]:
        """Get all routing rules for a specific pack."""
        self._get_pack_or_raise(pack_id)
        rules = [r for r in self._routing_rules.values() if r.pack_id == pack_id]
        return tuple(sorted(rules, key=lambda r: (-r.priority, r.rule_id)))

    def get_vocabulary_for_pack(
        self, pack_id: str,
    ) -> tuple[DomainVocabularyEntry, ...]:
        """Get all vocabulary entries for a specific pack."""
        self._get_pack_or_raise(pack_id)
        entries = [e for e in self._vocabulary.values() if e.pack_id == pack_id]
        return tuple(sorted(entries, key=lambda e: e.entry_id))

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def pack_count(self) -> int:
        return len(self._packs)

    @property
    def active_pack_count(self) -> int:
        return sum(1 for p in self._packs.values()
                   if p.status == DomainPackStatus.ACTIVE)

    @property
    def extraction_rule_count(self) -> int:
        return len(self._extraction_rules)

    @property
    def routing_rule_count(self) -> int:
        return len(self._routing_rules)

    @property
    def conflict_count(self) -> int:
        return len(self._conflicts)

    @property
    def resolution_count(self) -> int:
        return len(self._resolutions)

    def state_hash(self) -> str:
        """Deterministic hash over all engine state."""
        h = sha256()
        for pid in sorted(self._packs):
            p = self._packs[pid]
            h.update(f"pack:{pid}:{p.status}:{p.version}:{p.scope}".encode())
        for rid in sorted(self._extraction_rules):
            r = self._extraction_rules[rid]
            h.update(f"extr:{rid}:{r.pack_id}:{r.priority}".encode())
        for rid in sorted(self._routing_rules):
            r = self._routing_rules[rid]
            h.update(f"route:{rid}:{r.pack_id}:{r.priority}".encode())
        for rid in sorted(self._memory_rules):
            h.update(f"mem:{rid}".encode())
        for pid in sorted(self._simulation_profiles):
            h.update(f"sim:{pid}".encode())
        for pid in sorted(self._utility_profiles):
            h.update(f"util:{pid}".encode())
        for pid in sorted(self._benchmark_profiles):
            h.update(f"bench:{pid}".encode())
        for pid in sorted(self._escalation_profiles):
            h.update(f"esc:{pid}".encode())
        for cid in sorted(self._conflicts):
            h.update(f"conflict:{cid}".encode())
        for vid in sorted(self._vocabulary):
            h.update(f"vocab:{vid}".encode())
        for i, act in enumerate(self._activations):
            h.update(f"activation:{i}:{act.pack_id}:{act.new_status}".encode())
        for i, res in enumerate(self._resolutions):
            h.update(f"resolution:{i}:{res.resolution_id}".encode())
        return h.hexdigest()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _get_pack_or_raise(self, pack_id: str) -> DomainPackDescriptor:
        if pack_id not in self._packs:
            raise RuntimeCoreInvariantError(
                "pack not found"
            )
        return self._packs[pack_id]

    def _record_conflict(
        self,
        pack_id_a: str,
        pack_id_b: str,
        rule_kind: DomainRuleKind,
        scope: PackScope,
    ) -> DomainPackConflict:
        """Record a conflict between two packs. Idempotent by pair."""
        # Normalize order for determinism
        a, b = sorted([pack_id_a, pack_id_b])
        cid = stable_identifier("pack-conflict", {"a": a, "b": b, "kind": str(rule_kind), "scope": str(scope)})
        if cid not in self._conflicts:
            conflict = DomainPackConflict(
                conflict_id=cid,
                pack_id_a=a,
                pack_id_b=b,
                rule_kind=rule_kind,
                scope=scope,
                description="Conflicting domain pack rules",
                detected_at=_now_iso(),
            )
            self._conflicts[cid] = conflict
        return self._conflicts[cid]
