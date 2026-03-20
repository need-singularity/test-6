"""Filter 1: Random baseline — reject if pattern appears in random graphs."""

import random

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from tecs.tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine

def generate_random_graph(n_nodes: int, n_edges: int) -> dict:
    edges = set()
    max_possible = n_nodes * (n_nodes - 1) // 2
    n_edges = min(n_edges, max_possible)
    while len(edges) < n_edges:
        u = random.randint(0, n_nodes - 1)
        v = random.randint(0, n_nodes - 1)
        if u != v and (u, v) not in edges and (v, u) not in edges:
            edges.add((u, v))
    return {"edges": list(edges), "n_nodes": n_nodes}

def _topology_matches(actual: dict, random_topo: dict) -> bool:
    return (
        random_topo.get("beta0", 0) == actual.get("beta0", 0)
        and abs(random_topo.get("beta1", 0) - actual.get("beta1", 0))
        <= max(1, actual.get("beta1", 0) * 0.2)
    )

def filter_random(actual_topology: dict, n_nodes: int, n_edges: int, n_random: int = 10) -> dict:
    engine = _get_engine()
    match_count = 0
    for _ in range(n_random):
        rg = generate_random_graph(n_nodes, n_edges)
        if not rg["edges"]:
            continue
        try:
            random_topo = engine.compute_topology_from_edges(rg["edges"], rg["n_nodes"])
            if _topology_matches(actual_topology, random_topo):
                match_count += 1
        except Exception:
            continue
    match_rate = match_count / n_random if n_random > 0 else 0
    if match_rate >= 0.7:
        return {"status": "reject", "reason": f"랜덤 그래프에서 {match_rate:.0%} 재현", "match_rate": match_rate}
    return {"status": "pass", "match_rate": match_rate}
