"""Pure graph algorithms over task dependencies (no scheduling semantics)."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping

Edge = tuple[str, str]


class CycleError(ValueError):
    def __init__(self, remaining: Iterable[str]) -> None:
        self.remaining = sorted(remaining)
        super().__init__(f"dependency cycle among: {', '.join(self.remaining)}")


def topological_order(
    nodes: Iterable[str],
    edges: Iterable[Edge],
    priority: Callable[[str], tuple[int, str]] | None = None,
) -> list[str]:
    """Kahn's algorithm with a deterministic tie-break; raises ``CycleError``."""
    node_list = list(nodes)
    key = priority or (lambda n: (0, n))
    indegree: dict[str, int] = {n: 0 for n in node_list}
    succ: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        succ[a].append(b)
        indegree[b] += 1
    heap = [(key(n), n) for n, d in indegree.items() if d == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        _, n = heapq.heappop(heap)
        order.append(n)
        for m in succ[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                heapq.heappush(heap, (key(m), m))
    if len(order) != len(node_list):
        raise CycleError(set(node_list) - set(order))
    return order


def bfs_waves(sources: Iterable[str], edges: Iterable[Edge]) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    """Breadth-first reachability. Returns node->wave and the tree edges with their wave.

    Wave 0 nodes are the sources; an edge's wave is the wave of its target.
    """
    succ: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        succ[a].append(b)
    for v in succ.values():
        v.sort()
    wave: dict[str, int] = {}
    frontier = sorted(set(sources))
    for s in frontier:
        wave[s] = 0
    tree: list[tuple[str, str, int]] = []
    depth = 0
    while frontier:
        depth += 1
        nxt: list[str] = []
        for n in frontier:
            for m in succ[n]:
                if m not in wave:
                    wave[m] = depth
                    tree.append((n, m, depth))
                    nxt.append(m)
        frontier = sorted(set(nxt))
    return wave, tree


def longest_path_earliest(
    order: list[str],
    preds: Mapping[str, list[tuple[str, int]]],
    release: Mapping[str, int],
    duration: Mapping[str, int],
) -> dict[str, int]:
    """Earliest start per node given precedence (with lags) and release times only."""
    es: dict[str, int] = {}
    for n in order:
        start = release[n]
        for p, lag in preds.get(n, []):
            start = max(start, es[p] + duration[p] + lag)
        es[n] = start
    return es
