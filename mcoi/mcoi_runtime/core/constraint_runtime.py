"""Purpose: constraint / algorithm / solver runtime engine.
Governance scope: managing constraint definitions, solver problems, solutions,
    graph nodes, graph edges, schedule slots, assignment records, dependency chains,
    violation detection, snapshots, and closure reports.
Dependencies: constraint_runtime contracts, event_spine, core invariants.
Invariants:
  - SolveStatus transitions are explicit (PENDING->RUNNING->SOLVED/FAILED/TIMEOUT).
  - Graph edges require both nodes to exist.
  - Cycle detection in dependency chains is explicit.
  - Schedule conflicts are detectable.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from collections import defaultdict, deque
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.constraint_runtime import (
    AlgorithmKind,
    AssignmentRecord,
    AssignmentStrategy,
    ConstraintClosureReport,
    ConstraintDefinition,
    ConstraintKind,
    ConstraintSnapshot,
    DependencyChain,
    GraphEdge,
    GraphNode,
    GraphTraversal,
    PriorityMode,
    ScheduleSlot,
    SolveStatus,
    SolverProblem,
    SolverSolution,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-csrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ConstraintRuntimeEngine:
    """Engine for governed constraint / algorithm / solver runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._constraints: dict[str, ConstraintDefinition] = {}
        self._problems: dict[str, SolverProblem] = {}
        self._solutions: dict[str, SolverSolution] = {}
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._slots: dict[str, ScheduleSlot] = {}
        self._assignments: dict[str, AssignmentRecord] = {}
        self._dependencies: dict[str, DependencyChain] = {}
        self._violations: list[dict[str, str]] = []
        self._violation_keys: set[str] = set()

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def constraint_count(self) -> int:
        return len(self._constraints)

    @property
    def problem_count(self) -> int:
        return len(self._problems)

    @property
    def solution_count(self) -> int:
        return len(self._solutions)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def slot_count(self) -> int:
        return len(self._slots)

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)

    @property
    def dependency_count(self) -> int:
        return len(self._dependencies)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def add_constraint(
        self,
        constraint_id: str,
        tenant_id: str,
        kind: ConstraintKind,
        expression: str,
        variable_refs: str = "",
        priority: int = 0,
    ) -> ConstraintDefinition:
        """Add a constraint definition. Duplicate constraint_id raises."""
        if constraint_id in self._constraints:
            raise RuntimeCoreInvariantError(f"Duplicate constraint_id: {constraint_id}")
        now = self._now()
        constraint = ConstraintDefinition(
            constraint_id=constraint_id,
            tenant_id=tenant_id,
            kind=kind,
            expression=expression,
            variable_refs=variable_refs,
            priority=priority,
            created_at=now,
        )
        self._constraints[constraint_id] = constraint
        _emit(self._events, "constraint_added", {
            "constraint_id": constraint_id, "kind": kind.value,
        }, constraint_id, self._now())
        return constraint

    def get_constraint(self, constraint_id: str) -> ConstraintDefinition:
        c = self._constraints.get(constraint_id)
        if c is None:
            raise RuntimeCoreInvariantError(f"Unknown constraint_id: {constraint_id}")
        return c

    def constraints_for_tenant(self, tenant_id: str) -> tuple[ConstraintDefinition, ...]:
        return tuple(c for c in self._constraints.values() if c.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Problems
    # ------------------------------------------------------------------

    def create_problem(
        self,
        problem_id: str,
        tenant_id: str,
        algorithm: AlgorithmKind,
        constraint_count: int = 0,
        variable_count: int = 0,
    ) -> SolverProblem:
        """Create a new solver problem in PENDING status."""
        if problem_id in self._problems:
            raise RuntimeCoreInvariantError(f"Duplicate problem_id: {problem_id}")
        now = self._now()
        problem = SolverProblem(
            problem_id=problem_id,
            tenant_id=tenant_id,
            algorithm=algorithm,
            constraint_count=constraint_count,
            variable_count=variable_count,
            status=SolveStatus.PENDING,
            created_at=now,
        )
        self._problems[problem_id] = problem
        _emit(self._events, "problem_created", {
            "problem_id": problem_id, "algorithm": algorithm.value,
        }, problem_id, self._now())
        return problem

    def _replace_problem(self, problem_id: str, **kwargs: Any) -> SolverProblem:
        old = self._problems.get(problem_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown problem_id: {problem_id}")
        fields = {
            "problem_id": old.problem_id,
            "tenant_id": old.tenant_id,
            "algorithm": old.algorithm,
            "constraint_count": old.constraint_count,
            "variable_count": old.variable_count,
            "status": old.status,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = SolverProblem(**fields)
        self._problems[problem_id] = updated
        return updated

    def start_problem(self, problem_id: str) -> SolverProblem:
        """Transition problem from PENDING to RUNNING."""
        old = self._problems.get(problem_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown problem_id: {problem_id}")
        if old.status != SolveStatus.PENDING:
            raise RuntimeCoreInvariantError(
                f"Cannot start problem in {old.status.value} state (must be PENDING)"
            )
        updated = self._replace_problem(problem_id, status=SolveStatus.RUNNING)
        _emit(self._events, "problem_started", {
            "problem_id": problem_id,
        }, problem_id, self._now())
        return updated

    def solve_problem(
        self,
        solution_id: str,
        tenant_id: str,
        problem_ref: str,
        objective_value: float = 0.0,
        iterations: int = 0,
        duration_ms: float = 0.0,
    ) -> SolverSolution:
        """Record a solution and mark the problem as SOLVED."""
        if solution_id in self._solutions:
            raise RuntimeCoreInvariantError(f"Duplicate solution_id: {solution_id}")
        problem = self._problems.get(problem_ref)
        if problem is None:
            raise RuntimeCoreInvariantError(f"Unknown problem_ref: {problem_ref}")
        now = self._now()
        solution = SolverSolution(
            solution_id=solution_id,
            tenant_id=tenant_id,
            problem_ref=problem_ref,
            status=SolveStatus.SOLVED,
            objective_value=objective_value,
            iterations=iterations,
            duration_ms=duration_ms,
            solved_at=now,
        )
        self._solutions[solution_id] = solution
        self._replace_problem(problem_ref, status=SolveStatus.SOLVED)
        _emit(self._events, "problem_solved", {
            "solution_id": solution_id, "problem_ref": problem_ref,
        }, solution_id, self._now())
        return solution

    def fail_problem(self, problem_id: str) -> SolverProblem:
        """Mark a problem as FAILED."""
        old = self._problems.get(problem_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown problem_id: {problem_id}")
        updated = self._replace_problem(problem_id, status=SolveStatus.FAILED)
        _emit(self._events, "problem_failed", {
            "problem_id": problem_id,
        }, problem_id, self._now())
        return updated

    def timeout_problem(self, problem_id: str) -> SolverProblem:
        """Mark a problem as TIMEOUT."""
        old = self._problems.get(problem_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown problem_id: {problem_id}")
        updated = self._replace_problem(problem_id, status=SolveStatus.TIMEOUT)
        _emit(self._events, "problem_timeout", {
            "problem_id": problem_id,
        }, problem_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Graph Nodes / Edges
    # ------------------------------------------------------------------

    def add_graph_node(
        self,
        node_id: str,
        tenant_id: str,
        label: str,
        weight: float = 1.0,
    ) -> GraphNode:
        """Add a graph node. Duplicate node_id raises."""
        if node_id in self._nodes:
            raise RuntimeCoreInvariantError(f"Duplicate node_id: {node_id}")
        now = self._now()
        node = GraphNode(
            node_id=node_id,
            tenant_id=tenant_id,
            label=label,
            weight=weight,
            created_at=now,
        )
        self._nodes[node_id] = node
        _emit(self._events, "graph_node_added", {
            "node_id": node_id, "label": label,
        }, node_id, self._now())
        return node

    def add_graph_edge(
        self,
        edge_id: str,
        tenant_id: str,
        from_node: str,
        to_node: str,
        weight: float = 1.0,
    ) -> GraphEdge:
        """Add a graph edge. Both nodes must exist. Duplicate edge_id raises."""
        if edge_id in self._edges:
            raise RuntimeCoreInvariantError(f"Duplicate edge_id: {edge_id}")
        if from_node not in self._nodes:
            raise RuntimeCoreInvariantError(f"from_node not found: {from_node}")
        if to_node not in self._nodes:
            raise RuntimeCoreInvariantError(f"to_node not found: {to_node}")
        now = self._now()
        edge = GraphEdge(
            edge_id=edge_id,
            tenant_id=tenant_id,
            from_node=from_node,
            to_node=to_node,
            weight=weight,
            created_at=now,
        )
        self._edges[edge_id] = edge
        _emit(self._events, "graph_edge_added", {
            "edge_id": edge_id, "from_node": from_node, "to_node": to_node,
        }, edge_id, self._now())
        return edge

    # ------------------------------------------------------------------
    # Graph Algorithms
    # ------------------------------------------------------------------

    def _build_adjacency(self, tenant_id: str) -> dict[str, list[tuple[str, float]]]:
        """Build adjacency list for a tenant's graph (directed)."""
        adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for node in self._nodes.values():
            if node.tenant_id == tenant_id:
                if node.node_id not in adj:
                    adj[node.node_id] = []
        for edge in self._edges.values():
            if edge.tenant_id == tenant_id:
                adj[edge.from_node].append((edge.to_node, edge.weight))
        return dict(adj)

    def find_shortest_path(
        self,
        tenant_id: str,
        from_node: str,
        to_node: str,
    ) -> list[str]:
        """Find shortest path using BFS (unweighted) or Dijkstra (weighted).
        Returns list of node_ids or empty list if unreachable."""
        adj = self._build_adjacency(tenant_id)
        if from_node not in adj or to_node not in adj:
            return []

        # Check if all edges have weight 1.0 (use BFS) else Dijkstra
        all_unit = all(
            edge.weight == 1.0
            for edge in self._edges.values()
            if edge.tenant_id == tenant_id
        )

        if all_unit:
            return self._bfs_path(adj, from_node, to_node)
        return self._dijkstra_path(adj, from_node, to_node)

    def _bfs_path(
        self,
        adj: dict[str, list[tuple[str, float]]],
        start: str,
        end: str,
    ) -> list[str]:
        """BFS shortest path."""
        visited: set[str] = {start}
        queue: deque[list[str]] = deque([[start]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == end:
                return path
            for neighbor, _ in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return []

    def _dijkstra_path(
        self,
        adj: dict[str, list[tuple[str, float]]],
        start: str,
        end: str,
    ) -> list[str]:
        """Dijkstra shortest path."""
        import heapq
        dist: dict[str, float] = {start: 0.0}
        prev: dict[str, str | None] = {start: None}
        heap: list[tuple[float, str]] = [(0.0, start)]
        while heap:
            d, current = heapq.heappop(heap)
            if current == end:
                # Reconstruct path
                path: list[str] = []
                node: str | None = end
                while node is not None:
                    path.append(node)
                    node = prev.get(node)
                return list(reversed(path))
            if d > dist.get(current, float("inf")):
                continue
            for neighbor, weight in adj.get(current, []):
                nd = d + weight
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    prev[neighbor] = current
                    heapq.heappush(heap, (nd, neighbor))
        return []

    def topological_sort(self, tenant_id: str) -> tuple[str, ...]:
        """Topological sort of tenant's graph. Raises if cycle detected."""
        adj = self._build_adjacency(tenant_id)
        in_degree: dict[str, int] = {n: 0 for n in adj}
        for neighbors in adj.values():
            for neighbor, _ in neighbors:
                in_degree[neighbor] = in_degree.get(neighbor, 0) + 1

        queue: deque[str] = deque(
            sorted(n for n, d in in_degree.items() if d == 0)
        )
        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor, _ in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(adj):
            raise RuntimeCoreInvariantError("Cycle detected in graph")
        return tuple(result)

    # ------------------------------------------------------------------
    # Schedule Slots
    # ------------------------------------------------------------------

    def create_schedule_slot(
        self,
        slot_id: str,
        tenant_id: str,
        resource_ref: str,
        start_at: str,
        end_at: str,
        priority: int = 0,
    ) -> ScheduleSlot:
        """Create a schedule slot. Duplicate slot_id raises."""
        if slot_id in self._slots:
            raise RuntimeCoreInvariantError(f"Duplicate slot_id: {slot_id}")
        now = self._now()
        slot = ScheduleSlot(
            slot_id=slot_id,
            tenant_id=tenant_id,
            resource_ref=resource_ref,
            start_at=start_at,
            end_at=end_at,
            priority=priority,
            created_at=now,
        )
        self._slots[slot_id] = slot
        _emit(self._events, "schedule_slot_created", {
            "slot_id": slot_id, "resource_ref": resource_ref,
        }, slot_id, self._now())
        return slot

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def assign_resource(
        self,
        assignment_id: str,
        tenant_id: str,
        resource_ref: str,
        task_ref: str,
        strategy: AssignmentStrategy = AssignmentStrategy.GREEDY,
        cost: float = 0.0,
    ) -> AssignmentRecord:
        """Assign a resource to a task. Duplicate assignment_id raises."""
        if assignment_id in self._assignments:
            raise RuntimeCoreInvariantError(f"Duplicate assignment_id: {assignment_id}")
        now = self._now()
        assignment = AssignmentRecord(
            assignment_id=assignment_id,
            tenant_id=tenant_id,
            resource_ref=resource_ref,
            task_ref=task_ref,
            strategy=strategy,
            cost=cost,
            created_at=now,
        )
        self._assignments[assignment_id] = assignment
        _emit(self._events, "resource_assigned", {
            "assignment_id": assignment_id, "resource_ref": resource_ref,
        }, assignment_id, self._now())
        return assignment

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def add_dependency(
        self,
        chain_id: str,
        tenant_id: str,
        source_ref: str,
        target_ref: str,
        lag: int = 0,
    ) -> DependencyChain:
        """Add a dependency chain link. Duplicate chain_id raises."""
        if chain_id in self._dependencies:
            raise RuntimeCoreInvariantError(f"Duplicate chain_id: {chain_id}")
        now = self._now()
        dep = DependencyChain(
            chain_id=chain_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            target_ref=target_ref,
            lag=lag,
            created_at=now,
        )
        self._dependencies[chain_id] = dep
        _emit(self._events, "dependency_added", {
            "chain_id": chain_id, "source_ref": source_ref, "target_ref": target_ref,
        }, chain_id, self._now())
        return dep

    def critical_path(self, tenant_id: str) -> tuple[str, ...]:
        """Compute the critical path (longest dependency path) for a tenant.
        Returns chain_ids of the longest path."""
        tenant_deps = [d for d in self._dependencies.values() if d.tenant_id == tenant_id]
        if not tenant_deps:
            return ()

        # Build dependency graph: source_ref -> [(target_ref, chain_id, lag)]
        dep_adj: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
        all_refs: set[str] = set()
        for dep in tenant_deps:
            dep_adj[dep.source_ref].append((dep.target_ref, dep.chain_id, dep.lag))
            all_refs.add(dep.source_ref)
            all_refs.add(dep.target_ref)

        # Find longest path using DFS + memoization
        longest: dict[str, tuple[int, list[str]]] = {}

        def _dfs(node: str, visited: set[str]) -> tuple[int, list[str]]:
            if node in longest:
                return longest[node]
            if node in visited:
                return (0, [])  # cycle guard
            visited.add(node)
            best_len = 0
            best_chain: list[str] = []
            for target, chain_id, lag in dep_adj.get(node, []):
                sub_len, sub_chain = _dfs(target, visited)
                total = lag + 1 + sub_len
                if total > best_len:
                    best_len = total
                    best_chain = [chain_id] + sub_chain
            visited.discard(node)
            longest[node] = (best_len, best_chain)
            return (best_len, best_chain)

        overall_best: list[str] = []
        overall_len = 0
        for ref in all_refs:
            length, chain = _dfs(ref, set())
            if length > overall_len:
                overall_len = length
                overall_best = chain

        return tuple(overall_best)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def constraint_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> ConstraintSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = ConstraintSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_constraints=sum(1 for c in self._constraints.values() if c.tenant_id == tenant_id),
            total_problems=sum(1 for p in self._problems.values() if p.tenant_id == tenant_id),
            total_solutions=sum(1 for s in self._solutions.values() if s.tenant_id == tenant_id),
            total_nodes=sum(1 for n in self._nodes.values() if n.tenant_id == tenant_id),
            total_edges=sum(1 for e in self._edges.values() if e.tenant_id == tenant_id),
            total_violations=sum(
                1 for v in self._violations if v.get("tenant_id") == tenant_id
            ),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_constraint_violations(self, tenant_id: str) -> tuple[dict[str, str], ...]:
        """Detect constraint violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[dict[str, str]] = []

        # 1) unsolved_problem: PENDING/RUNNING problem with no solution
        for problem in self._problems.values():
            if problem.tenant_id != tenant_id:
                continue
            if problem.status in (SolveStatus.PENDING, SolveStatus.RUNNING):
                has_solution = any(
                    s.problem_ref == problem.problem_id
                    for s in self._solutions.values()
                )
                if not has_solution:
                    key = f"unsolved_problem:{problem.problem_id}"
                    if key not in self._violation_keys:
                        v = {
                            "tenant_id": tenant_id,
                            "operation": "unsolved_problem",
                            "reason": f"Problem {problem.problem_id} is {problem.status.value} with no solution",
                            "detected_at": now,
                        }
                        self._violations.append(v)
                        self._violation_keys.add(key)
                        new_violations.append(v)

        # 2) cycle_in_dependencies: circular dependency chain
        tenant_deps = [d for d in self._dependencies.values() if d.tenant_id == tenant_id]
        if tenant_deps:
            dep_adj: dict[str, list[str]] = defaultdict(list)
            all_refs: set[str] = set()
            for dep in tenant_deps:
                dep_adj[dep.source_ref].append(dep.target_ref)
                all_refs.add(dep.source_ref)
                all_refs.add(dep.target_ref)

            # Detect cycles with DFS
            WHITE, GRAY, BLACK = 0, 1, 2
            color: dict[str, int] = {r: WHITE for r in all_refs}

            def _has_cycle(node: str) -> bool:
                color[node] = GRAY
                for neighbor in dep_adj.get(node, []):
                    if color.get(neighbor) == GRAY:
                        return True
                    if color.get(neighbor) == WHITE and _has_cycle(neighbor):
                        return True
                color[node] = BLACK
                return False

            for ref in all_refs:
                if color[ref] == WHITE and _has_cycle(ref):
                    key = f"cycle_in_dependencies:{tenant_id}"
                    if key not in self._violation_keys:
                        v = {
                            "tenant_id": tenant_id,
                            "operation": "cycle_in_dependencies",
                            "reason": f"Circular dependency detected in tenant {tenant_id}",
                            "detected_at": now,
                        }
                        self._violations.append(v)
                        self._violation_keys.add(key)
                        new_violations.append(v)
                    break

        # 3) schedule_conflict: overlapping slots for same resource
        tenant_slots = [s for s in self._slots.values() if s.tenant_id == tenant_id]
        by_resource: dict[str, list[ScheduleSlot]] = defaultdict(list)
        for slot in tenant_slots:
            by_resource[slot.resource_ref].append(slot)

        for resource_ref, slots in by_resource.items():
            sorted_slots = sorted(slots, key=lambda s: s.start_at)
            for i in range(len(sorted_slots)):
                for j in range(i + 1, len(sorted_slots)):
                    a, b = sorted_slots[i], sorted_slots[j]
                    # Overlap if a.start_at < b.end_at and b.start_at < a.end_at
                    if a.start_at < b.end_at and b.start_at < a.end_at:
                        key = f"schedule_conflict:{a.slot_id}:{b.slot_id}"
                        if key not in self._violation_keys:
                            v = {
                                "tenant_id": tenant_id,
                                "operation": "schedule_conflict",
                                "reason": f"Schedule conflict between {a.slot_id} and {b.slot_id} for resource {resource_ref}",
                                "detected_at": now,
                            }
                            self._violations.append(v)
                            self._violation_keys.add(key)
                            new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "assignments": self._assignments,
            "constraints": self._constraints,
            "dependencies": self._dependencies,
            "edges": self._edges,
            "nodes": self._nodes,
            "problems": self._problems,
            "slots": self._slots,
            "solutions": self._solutions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (SHA256 sorted keys)."""
        parts = [
            f"assignments={self.assignment_count}",
            f"constraints={self.constraint_count}",
            f"dependencies={self.dependency_count}",
            f"edges={self.edge_count}",
            f"nodes={self.node_count}",
            f"problems={self.problem_count}",
            f"slots={self.slot_count}",
            f"solutions={self.solution_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
