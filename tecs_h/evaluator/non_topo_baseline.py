"""Filter 3: Non-topological baseline — reject if graph stats alone reach same conclusion."""

import json
from tecs_h.claude_io.client import claude_call

BASELINE_PROMPT = """
다음 그래프 통계만 보고 가설을 세워봐.
(위상 정보 없음 — degree, clustering coefficient 등 기본 통계만 사용)

그래프 통계:
{graph_stats}

관련 엔티티: {entities}

JSON으로 답해:
- hypothesis: 가설 서술
"""

COMPARISON_PROMPT = """
두 가설의 논리적 핵심 주장이 같은지 비교해줘.
표면적 표현이 아닌 논리적 핵심 주장만 비교하라.

가설 A (위상 기반):
{hypothesis_a}

가설 B (그래프 통계 기반):
{hypothesis_b}

JSON으로 답해:
- same_core_claim: true/false
- confidence: 판단 확신도 (0~1)
"""

def filter_non_topo(hypothesis: dict, graph_stats: dict, confidence_threshold: float = 0.8) -> dict:
    entities = hypothesis.get("involved_entities", [])
    baseline_prompt = BASELINE_PROMPT.format(
        graph_stats=json.dumps(graph_stats, ensure_ascii=False),
        entities=", ".join(entities),
    )
    baseline = claude_call(baseline_prompt)
    compare_prompt = COMPARISON_PROMPT.format(
        hypothesis_a=hypothesis.get("hypothesis", ""),
        hypothesis_b=baseline.get("hypothesis", ""),
    )
    comparison = claude_call(compare_prompt)
    is_same = comparison.get("same_core_claim", False)
    confidence = comparison.get("confidence", 0)
    if is_same and confidence >= confidence_threshold:
        return {"status": "reject", "reason": f"위상 없이도 도달 가능 (confidence={confidence:.2f})", "baseline_hypothesis": baseline.get("hypothesis", "")}
    return {"status": "pass", "confidence": confidence}
