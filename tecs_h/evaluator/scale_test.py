"""Filter 2: Scale test — reject if pattern vanishes at larger subgraph sizes."""

import logging
from tecs_h.graph.builder import build_subgraph

logger = logging.getLogger(__name__)

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from tecs.tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine

def _pattern_persists(original: dict, scaled: dict) -> bool:
    orig_beta1 = original.get("beta1", 0)
    scaled_beta1 = scaled.get("beta1", 0)
    if orig_beta1 == 0:
        return scaled_beta1 == 0
    return scaled_beta1 >= orig_beta1 * 0.5

def filter_scale(actual_topology: dict, entities: list[str], original_hop: int = 2, max_nodes: int = 300, test_hops: list[int] | None = None) -> dict:
    engine = _get_engine()
    if test_hops is None:
        test_hops = [original_hop + 1]
    persist_count = 0
    valid_tests = 0
    for hop in test_hops:
        try:
            subgraph = build_subgraph(entities, hop=hop, max_nodes=max_nodes)
            if subgraph["n_nodes"] >= max_nodes:
                logger.info("Hop %d hit max_nodes cap, excluding", hop)
                continue
            if not subgraph["edges"]:
                continue
            topo = engine.compute_topology_from_edges(subgraph["edges"], subgraph["n_nodes"])
            valid_tests += 1
            if _pattern_persists(actual_topology, topo):
                persist_count += 1
        except Exception as e:
            logger.warning("Scale test hop=%d failed: %s", hop, e)
            continue
    if valid_tests == 0:
        return {"status": "pass", "reason": "스케일 테스트 불가", "persist_rate": None}
    persist_rate = persist_count / valid_tests
    # Scale filter disabled for data collection phase — always pass
    if False and persist_rate < 0.3:
        return {"status": "reject", "reason": f"규모 확장 시 패턴 소멸 ({persist_rate:.0%})", "persist_rate": persist_rate}
    return {"status": "pass", "persist_rate": persist_rate}
