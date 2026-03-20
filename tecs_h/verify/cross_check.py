"""2nd verification: cross-check pattern reproduction on sibling entities."""

import logging
import time
import requests

logger = logging.getLogger(__name__)
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from tecs.tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine

def _sparql_query(query: str) -> dict:
    headers = {"Accept": "application/sparql-results+json", "User-Agent": "TECS-H/0.1"}
    resp = requests.get(SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=30)
    resp.raise_for_status()
    time.sleep(1)
    return resp.json()

def find_sibling_entities(entity: str, limit: int = 5) -> list[str]:
    query = f"""
    SELECT DISTINCT ?sibling WHERE {{
        wd:{entity} wdt:P279 ?parent .
        ?sibling wdt:P279 ?parent .
        FILTER(?sibling != wd:{entity})
    }} LIMIT {limit}
    """
    try:
        result = _sparql_query(query)
        return [b["sibling"]["value"].split("/")[-1] for b in result.get("results", {}).get("bindings", [])]
    except Exception as e:
        logger.warning("Sibling query failed for %s: %s", entity, e)
        return []

def _compute_and_check(entities: list[str], expected_topology: dict, hop: int = 2) -> bool:
    from tecs_h.graph.builder import build_subgraph
    engine = _get_engine()
    try:
        subgraph = build_subgraph(entities, hop=hop)
        if not subgraph["edges"]:
            return False
        topo = engine.compute_topology_from_edges(subgraph["edges"], subgraph["n_nodes"])
        expected_beta1 = expected_topology.get("beta1", 0)
        actual_beta1 = topo.get("beta1", 0)
        if expected_beta1 == 0:
            return actual_beta1 == 0
        return actual_beta1 >= expected_beta1 * 0.5
    except Exception as e:
        logger.warning("Cross-check computation failed: %s", e)
        return False

def cross_check(hypothesis: dict, actual_topology: dict, min_checks: int = 2, hop: int = 2) -> dict:
    entities = hypothesis.get("involved_entities", [])
    if not entities:
        return {"reproduced": False, "warning": "엔티티 없음", "confidence_adjustment": 0}
    siblings = find_sibling_entities(entities[0])
    if len(siblings) < min_checks:
        return {"reproduced": False, "warning": "형제 엔티티 부족", "confidence_adjustment": 0}
    reproduce_count = 0
    checks_done = 0
    for sibling in siblings[:min_checks * 2]:
        alt_entities = [sibling] + entities[1:]
        result = _compute_and_check(alt_entities, actual_topology, hop=hop)
        checks_done += 1
        if result:
            reproduce_count += 1
        if checks_done >= min_checks:
            break
    if checks_done == 0:
        return {"reproduced": False, "warning": "검증 불가", "confidence_adjustment": 0}
    reproduce_rate = reproduce_count / checks_done
    if reproduce_rate >= 0.5:
        return {"reproduced": True, "reproduce_rate": reproduce_rate, "confidence_adjustment": 0.1, "warning": None}
    return {"reproduced": False, "reproduce_rate": reproduce_rate, "confidence_adjustment": 0, "warning": "단일 사례"}
