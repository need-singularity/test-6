"""Topological invariant prediction via LLM."""

from tecs_h.claude_io.router import llm_call

PREDICTION_PROMPT_TEMPLATE = """
다음 Wikidata 수학 엔티티들의 서브그래프(BFS {hop}홉)에 대해 위상 불변량을 예측해줘.

엔티티: {entities}

다음 값을 JSON으로 예측해:
- beta0: 연결 컴포넌트 수 (정수)
- beta1: 1차원 구멍/순환 수 (정수)
- hierarchy_score: 계층성 (0~1, 1=완전 트리형)
- max_persistence_h1: H1의 최대 지속성 (0~2, 높을수록 강한 위상 특성)
- reasoning: 왜 그렇게 예측했는지 (한국어)
"""


def predict(entities: list[str], hop: int = 2) -> dict:
    """Ask Claude CLI to predict topological invariants of a subgraph."""
    prompt = PREDICTION_PROMPT_TEMPLATE.format(
        entities=", ".join(entities),
        hop=hop,
    )
    return llm_call(prompt, role="predictor")
