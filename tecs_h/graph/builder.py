"""Wikidata SPARQL subgraph builder."""

import time
import requests

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

WHITELIST = [
    "P279", "P31", "P361", "P527",  # hierarchical
    "P737", "P101", "P2578", "P517", "P921", "P1269", "P461", "P1382",  # semantic
]

BLACKLIST = [
    "P1343", "P973", "P910", "P1424", "P935", "P1151", "P8408", "P646", "P2959",
]


def build_sparql_query(entities: list[str], hop: int = 1) -> str:
    """Build SPARQL query for BFS subgraph extraction."""
    entity_values = " ".join(f"wd:{e}" for e in entities)
    whitelist_filter = " ".join(f"wdt:{p}" for p in WHITELIST)
    # VALUES clause already restricts to whitelist, no separate blacklist FILTER needed

    if hop == 1:
        return f"""
        SELECT ?source ?prop ?target WHERE {{
            VALUES ?source {{ {entity_values} }}
            ?source ?prop ?target .
            VALUES ?prop {{ {whitelist_filter} }}
            FILTER(STRSTARTS(STR(?target), "http://www.wikidata.org/entity/Q"))
        }}
        LIMIT 1000
        """
    else:
        return f"""
        SELECT ?source ?prop ?target WHERE {{
            VALUES ?seed {{ {entity_values} }}
            ?seed (wdt:P279|wdt:P31|wdt:P361|wdt:P527|wdt:P737|wdt:P101){{0,{hop}}} ?source .
            ?source ?prop ?target .
            VALUES ?prop {{ {whitelist_filter} }}
            FILTER(STRSTARTS(STR(?target), "http://www.wikidata.org/entity/Q"))
        }}
        LIMIT 5000
        """


def _sparql_query(query: str) -> dict:
    """Execute SPARQL query against Wikidata endpoint."""
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "TECS-H/0.1 (hypothesis generator)",
    }
    response = requests.get(
        SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=60
    )
    response.raise_for_status()
    time.sleep(1)  # rate limit
    return response.json()


def parse_sparql_response(response: dict) -> tuple[set[str], list[tuple[str, str]]]:
    """Parse SPARQL response into nodes and edge pairs."""
    nodes = set()
    edges = []
    for binding in response["results"]["bindings"]:
        source_uri = binding["source"]["value"]
        target_uri = binding["target"]["value"]
        source = source_uri.split("/")[-1]
        target = target_uri.split("/")[-1]
        nodes.add(source)
        nodes.add(target)
        edges.append((source, target))
    return nodes, edges


def build_subgraph(
    entities: list[str], hop: int = 2, max_nodes: int = 300
) -> dict:
    """Build subgraph from Wikidata via SPARQL.

    Returns dict with nodes (list), edges (list of int tuples), n_nodes (int).
    Edges use integer indices for TECS-L compatibility.
    """
    query = build_sparql_query(entities, hop=hop)
    response = _sparql_query(query)
    all_nodes, raw_edges = parse_sparql_response(response)

    # Add seed entities even if no results
    for e in entities:
        all_nodes.add(e)

    # Truncate to max_nodes
    node_list = list(all_nodes)[:max_nodes]
    node_set = set(node_list)
    node_to_idx = {n: i for i, n in enumerate(node_list)}

    # Convert to integer index edges, filtering out-of-set nodes
    int_edges = []
    seen = set()
    for src, tgt in raw_edges:
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
