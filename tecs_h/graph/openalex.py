"""OpenAlex local TSV subgraph builder.

Loads triples from data/openalex_math_topology.tsv and builds subgraphs
via in-memory BFS. No network calls — fast.
"""

import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

_graph = None
_entities = None

DEFAULT_TRIPLES_PATH = "data/openalex_math_topology.tsv"
DEFAULT_ENTITIES_PATH = "data/openalex_entities.tsv"


def _load_graph(triples_path: str | None = None) -> dict:
    """Load TSV triples into adjacency list. Cached after first load."""
    global _graph
    if _graph is not None:
        return _graph

    path = triples_path or DEFAULT_TRIPLES_PATH
    adj = defaultdict(list)  # entity -> [(relation, target), ...]
    count = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 3:
                continue
            head, rel, tail = parts
            adj[head].append((rel, tail))
            adj[tail].append((rel + "_inv", head))  # bidirectional
            count += 1

    logger.info("Loaded %d triples, %d entities", count, len(adj))
    _graph = dict(adj)
    return _graph


def _load_entities(entities_path: str | None = None) -> dict:
    """Load entity ID -> name mapping."""
    global _entities
    if _entities is not None:
        return _entities

    path = entities_path or DEFAULT_ENTITIES_PATH
    ents = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                ents[parts[0]] = parts[1]

    _entities = ents
    return _entities


def get_entity_name(entity_id: str) -> str:
    """Get human-readable name for an entity."""
    ents = _load_entities()
    return ents.get(entity_id, entity_id)


def build_subgraph(
    entities: list[str], hop: int = 2, max_nodes: int = 300
) -> dict:
    """Build subgraph via BFS from seed entities.

    Returns dict with nodes (list), edges (list of int tuples), n_nodes (int).
    Same interface as wikidata builder for TECS-L compatibility.
    """
    graph = _load_graph()

    visited = set(entities)
    frontier = set(entities)
    raw_edges = []

    for _ in range(hop):
        if not frontier or len(visited) >= max_nodes:
            break
        next_frontier = set()
        for node in frontier:
            for rel, neighbor in graph.get(node, []):
                raw_edges.append((node, neighbor, rel))
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
                    if len(visited) >= max_nodes:
                        break
            if len(visited) >= max_nodes:
                break
        frontier = next_frontier

    # Convert to integer-indexed edges
    node_list = list(visited)[:max_nodes]
    node_set = set(node_list)
    node_to_idx = {n: i for i, n in enumerate(node_list)}

    int_edges = []
    seen = set()
    for src, tgt, rel in raw_edges:
        if src in node_set and tgt in node_set:
            pair = (node_to_idx[src], node_to_idx[tgt])
            if pair not in seen:
                seen.add(pair)
                int_edges.append(pair)

    return {
        "nodes": node_list,
        "edges": int_edges,
        "n_nodes": len(node_list),
    }


def find_concept_papers(concept_name: str, limit: int = 10) -> list[str]:
    """Find paper IDs that have a specific concept."""
    graph = _load_graph()
    ents = _load_entities()

    # Find concept ID by name
    concept_id = None
    for eid, name in ents.items():
        if name.lower() == concept_name.lower() and eid.startswith("C"):
            concept_id = eid
            break

    if not concept_id:
        return []

    # Find papers with P_has_concept_inv to this concept
    papers = []
    for rel, node in graph.get(concept_id, []):
        if rel == "P_has_concept_inv" and node.startswith("W"):
            papers.append(node)
            if len(papers) >= limit:
                break

    return papers
