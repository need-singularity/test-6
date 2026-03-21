"""B-mode: semi-automatic batch collision loop."""

import logging
import sys

from tecs_h.collision.predictor import predict
from tecs_h.collision.clash import detect_clashes
from tecs_h.collision.resolver import resolve
from tecs_h.graph.builder import build_subgraph as wikidata_build_subgraph
from tecs_h.graph.openalex import build_subgraph as openalex_build_subgraph

import os

def build_subgraph(entities, hop=2, max_nodes=300):
    """Route to correct graph builder based on TECS_H_GRAPH env var."""
    source = os.environ.get("TECS_H_GRAPH", "openalex")
    if source == "wikidata":
        return wikidata_build_subgraph(entities, hop=hop, max_nodes=max_nodes)
    return openalex_build_subgraph(entities, hop=hop, max_nodes=max_nodes)
from tecs_h.output.formatter import format_hypothesis, save_result
from tecs_h.evaluator.pipeline import evaluate
from tecs_h.novelty.filter import filter_novelty
from tecs_h.verify.cross_check import cross_check

logger = logging.getLogger("tecs_h.loop")

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from tecs.tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine


def compute_topology(subgraph: dict) -> dict:
    """Compute topology + hyperbolicity from a pre-built subgraph."""
    engine = _get_engine()
    if not subgraph["edges"]:
        raise ValueError("Empty subgraph")
    topo = engine.compute_topology_from_edges(subgraph["edges"], subgraph["n_nodes"])
    hyper = engine.compute_hyperbolicity(subgraph["edges"], subgraph["n_nodes"])
    return {**topo, "hierarchy_score": hyper["hierarchy_score"]}


def run_collision_round(entities: list[str], hop: int = 2) -> dict | None:
    """Run a single collision round."""
    subgraph = build_subgraph(entities, hop=hop)
    prediction = predict(entities, hop=hop)
    actual = compute_topology(subgraph)
    clashes = detect_clashes(prediction, actual)
    if not clashes:
        logger.info("No clash detected for %s, skipping", entities)
        return None
    hypothesis = resolve(prediction, actual, clashes)

    # Evaluator 3-filter pipeline
    eval_result = evaluate(
        hypothesis=hypothesis, actual_topology=actual, entities=entities,
        n_nodes=subgraph["n_nodes"], n_edges=len(subgraph["edges"]),
        subgraph_edges=subgraph["edges"], original_hop=hop,
    )
    if eval_result["status"] == "rejected":
        logger.info("Hypothesis rejected by evaluator: %s", eval_result.get("reason", ""))
        return None

    # Novelty filter
    novelty_result = filter_novelty(hypothesis)
    if novelty_result["status"] == "reject":
        logger.info("Hypothesis rejected by novelty filter: %s", novelty_result.get("reason", ""))
        return None

    # Cross-check (2nd verification)
    cross_result = cross_check(hypothesis, actual)
    if cross_result.get("confidence_adjustment", 0) > 0:
        hypothesis["confidence"] = min(1.0, hypothesis.get("confidence", 0) + cross_result["confidence_adjustment"])

    return {"hypothesis": hypothesis, "prediction": prediction, "actual": actual,
            "clashes": clashes, "subgraph": subgraph, "evaluation": eval_result, "novelty": novelty_result,
            "cross_check": cross_result}


def run_batch(seed_groups: list[dict], rounds_per_group: int = 5, results_dir: str = "results") -> list[dict]:
    """Run batch collision loop over seed groups."""
    all_results = []
    for group in seed_groups:
        entities = group["entities"]
        hop = group.get("hop", 2)
        logger.info("Starting group: %s (hop=%d)", entities, hop)
        for round_num in range(rounds_per_group):
            try:
                result = run_collision_round(entities, hop=hop)
                if result is None:
                    continue
                formatted = format_hypothesis(
                    hypothesis=result["hypothesis"], prediction=result["prediction"],
                    actual=result["actual"], clashes=result["clashes"],
                    evaluation=result.get("evaluation"), novelty=result.get("novelty"),
                )
                save_result(formatted, base_dir=results_dir)
                all_results.append(formatted)
                logger.info("Round %d: hypothesis generated — %s", round_num, formatted["id"])
            except Exception as e:
                logger.error("Round %d failed for %s: %s", round_num, entities, e)
                continue
    logger.info("Batch complete: %d hypotheses generated", len(all_results))
    return all_results
