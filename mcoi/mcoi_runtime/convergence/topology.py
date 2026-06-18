"""Dual-topology graph and cycle diagnosis for CDG-RCCM.

Containment and dependency are deliberately separate. Containment is acyclic.
Dependency edges may be cyclic, but every cycle is classified before resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .contracts import (
    ComponentProjectionRequest,
    CycleClass,
    DependencyRelation,
    stable_hash,
)


@dataclass(frozen=True, slots=True)
class ConvergenceRegion:
    """One strongly connected dependency region and its diagnosed cycle class."""

    region_id: str
    component_ids: tuple[str, ...]
    request_ids: tuple[str, ...]
    cycle_class: CycleClass


class ContainmentGraph:
    """Acyclic ownership/containment graph."""

    def __init__(self) -> None:
        self._children: dict[str, set[str]] = {}
        self._parents: dict[str, str] = {}

    def add(self, parent_component_id: str, child_component_id: str) -> None:
        if not parent_component_id or not child_component_id:
            raise ValueError("containment component ids must be non-empty")
        if parent_component_id == child_component_id:
            raise ValueError("containment_self_cycle")
        existing_parent = self._parents.get(child_component_id)
        if existing_parent is not None and existing_parent != parent_component_id:
            raise ValueError("containment_child_has_multiple_owners")
        if self._reachable(child_component_id, parent_component_id):
            raise ValueError("containment_cycle")
        self._children.setdefault(parent_component_id, set()).add(child_component_id)
        self._children.setdefault(child_component_id, set())
        self._parents[child_component_id] = parent_component_id

    def children_of(self, component_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._children.get(component_id, set())))

    def parent_of(self, component_id: str) -> str | None:
        return self._parents.get(component_id)

    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted(set(self._children) | set(self._parents)))

    def edges(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (parent, child)
            for parent in sorted(self._children)
            for child in sorted(self._children[parent])
        )

    def _reachable(self, source: str, target: str) -> bool:
        queue = [source]
        visited: set[str] = set()
        while queue:
            current = queue.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._children.get(current, ()))
        return False


class DependencyMesh:
    """Typed dynamic dependency graph indexed by exact projection requests."""

    def __init__(self) -> None:
        self._requests: dict[str, ComponentProjectionRequest] = {}
        self._outgoing: dict[str, set[str]] = {}
        self._incoming: dict[str, set[str]] = {}

    def add_request(self, request: ComponentProjectionRequest) -> None:
        if request.request_id in self._requests:
            if self._requests[request.request_id] != request:
                raise ValueError("dependency_request_identity_collision")
            return
        self._requests[request.request_id] = request
        self._outgoing.setdefault(request.consumer_component_id, set()).add(request.request_id)
        self._incoming.setdefault(request.provider_component_id, set()).add(request.request_id)
        self._outgoing.setdefault(request.provider_component_id, set())
        self._incoming.setdefault(request.consumer_component_id, set())

    def remove_request(self, request_id: str) -> None:
        request = self._requests.pop(request_id, None)
        if request is None:
            return
        self._outgoing.get(request.consumer_component_id, set()).discard(request_id)
        self._incoming.get(request.provider_component_id, set()).discard(request_id)

    def request(self, request_id: str) -> ComponentProjectionRequest:
        try:
            return self._requests[request_id]
        except KeyError as exc:
            raise KeyError(f"unknown dependency request: {request_id}") from exc

    def requests(self) -> tuple[ComponentProjectionRequest, ...]:
        return tuple(self._requests[request_id] for request_id in sorted(self._requests))

    def outgoing_requests(self, consumer_component_id: str) -> tuple[ComponentProjectionRequest, ...]:
        return tuple(
            self._requests[request_id]
            for request_id in sorted(self._outgoing.get(consumer_component_id, set()))
        )

    def incoming_requests(self, provider_component_id: str) -> tuple[ComponentProjectionRequest, ...]:
        return tuple(
            self._requests[request_id]
            for request_id in sorted(self._incoming.get(provider_component_id, set()))
        )

    def adjacency(self) -> Mapping[str, tuple[str, ...]]:
        nodes = set(self._outgoing) | set(self._incoming)
        result: dict[str, tuple[str, ...]] = {}
        for node in sorted(nodes):
            providers = {
                self._requests[request_id].provider_component_id
                for request_id in self._outgoing.get(node, set())
            }
            result[node] = tuple(sorted(providers))
        return result

    def active_required_closure(self, root_component_id: str) -> tuple[str, ...]:
        """Return the root-relative transitive closure over blocking dependencies."""

        queue = [root_component_id]
        active: set[str] = set()
        while queue:
            component_id = queue.pop(0)
            if component_id in active:
                continue
            active.add(component_id)
            for request in self.outgoing_requests(component_id):
                if request.gate.value in {"hard", "provisional", "quorum", "temporal"}:
                    queue.append(request.provider_component_id)
                    queue.extend(request.fallback_provider_ids)
        return tuple(sorted(active))

    def strongly_connected_components(self, nodes: Iterable[str] | None = None) -> tuple[tuple[str, ...], ...]:
        """Tarjan SCC over the selected dependency nodes."""

        adjacency = self.adjacency()
        selected = set(nodes) if nodes is not None else set(adjacency)
        index = 0
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        components: list[tuple[str, ...]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = index
            lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for neighbor in adjacency.get(node, ()):
                if neighbor not in selected:
                    continue
                if neighbor not in indices:
                    visit(neighbor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[neighbor])

            if lowlinks[node] == indices[node]:
                region: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    region.append(member)
                    if member == node:
                        break
                components.append(tuple(sorted(region)))

        for node in sorted(selected):
            if node not in indices:
                visit(node)

        return tuple(sorted(components, key=lambda component: component))

    def cyclic_regions(self, nodes: Iterable[str] | None = None) -> tuple[ConvergenceRegion, ...]:
        selected = set(nodes) if nodes is not None else None
        regions: list[ConvergenceRegion] = []
        for component_ids in self.strongly_connected_components(selected):
            request_ids = self._request_ids_inside(component_ids)
            self_loop = any(
                self._requests[request_id].consumer_component_id
                == self._requests[request_id].provider_component_id
                for request_id in request_ids
            )
            if len(component_ids) < 2 and not self_loop:
                continue
            cycle_class = self._classify_cycle(request_ids)
            region_id = stable_hash(
                "cdg-region",
                {
                    "component_ids": component_ids,
                    "request_ids": request_ids,
                    "cycle_class": cycle_class.value,
                },
            )
            regions.append(
                ConvergenceRegion(
                    region_id=region_id,
                    component_ids=component_ids,
                    request_ids=request_ids,
                    cycle_class=cycle_class,
                )
            )
        return tuple(regions)

    def _request_ids_inside(self, component_ids: tuple[str, ...]) -> tuple[str, ...]:
        members = set(component_ids)
        return tuple(
            request_id
            for request_id, request in sorted(self._requests.items())
            if request.consumer_component_id in members and request.provider_component_id in members
        )

    def _classify_cycle(self, request_ids: tuple[str, ...]) -> CycleClass:
        requests = tuple(self._requests[request_id] for request_id in request_ids)
        relations = {request.relation for request in requests}
        if any(request.consumer_component_id == request.provider_component_id for request in requests):
            return CycleClass.HIDDEN_SELF_DEPENDENCY
        if DependencyRelation.RESOURCE_WAIT in relations:
            return CycleClass.RESOURCE_DEADLOCK
        if DependencyRelation.AUTHORITY_WAIT in relations:
            return CycleClass.AUTHORITY_DEADLOCK
        if DependencyRelation.TEMPORAL_PREVIOUS in relations:
            return CycleClass.TEMPORAL_FEEDBACK
        if relations and relations <= {DependencyRelation.ALTERNATIVE_TO}:
            return CycleClass.ALTERNATIVE_SELECTION
        return CycleClass.SEMANTIC_FEEDBACK
