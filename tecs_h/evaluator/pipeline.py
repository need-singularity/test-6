"""Evaluator pipeline: run 3 filters in cost order."""

import logging
from tecs_h.evaluator.random_baseline import filter_random
from tecs_h.evaluator.scale_test import filter_scale
from tecs_h.evaluator.non_topo_baseline import filter_non_topo

logger = logging.getLogger(__name__)

def _compute_graph_stats(edges: list[tuple], n_nodes: int) -> dict:
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(range(n_nodes))
    G.add_edges_from(edges)
    degrees = [d for _, d in G.degree()]
    return {
        "n_nodes": n_nodes, "n_edges": len(edges),
        "avg_degree": sum(degrees) / max(len(degrees), 1),
        "max_degree": max(degrees) if degrees else 0,
        "clustering_coefficient": nx.average_clustering(G),
        "density": nx.density(G),
    }

def evaluate(hypothesis: dict, actual_topology: dict, entities: list[str], n_nodes: int, n_edges: int, subgraph_edges: list[tuple] | None = None, original_hop: int = 2) -> dict:
    results = {}
    logger.info("Running filter 1: random baseline")
    r1 = filter_random(actual_topology, n_nodes=n_nodes, n_edges=n_edges)
    results["random_baseline"] = r1["status"]
    if r1["status"] == "reject":
        return {"status": "rejected", "reason": r1.get("reason", ""), "filter": "random_baseline", **results}
    logger.info("Running filter 2: scale test")
    r2 = filter_scale(actual_topology, entities=entities, original_hop=original_hop)
    results["scale_test"] = r2["status"]
    if r2["status"] == "reject":
        return {"status": "rejected", "reason": r2.get("reason", ""), "filter": "scale_test", **results}
    logger.info("Running filter 3: non-topo baseline")
    graph_stats = _compute_graph_stats(subgraph_edges or [], n_nodes) if subgraph_edges else {}
    r3 = filter_non_topo(hypothesis, graph_stats=graph_stats)
    results["non_topo_baseline"] = r3["status"]
    if r3["status"] == "reject":
        return {"status": "rejected", "reason": r3.get("reason", ""), "filter": "non_topo_baseline", **results}
    return {"status": "passed", "filters_cleared": 3, **results}
