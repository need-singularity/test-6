"""Contradiction resolution: generate hypotheses from clashes."""

import json
from tecs_h.claude_io.router import llm_call

RESOLVER_PROMPT_TEMPLATE = """
너는 Wikidata 수학 엔티티 서브그래프의 위상 불변량을 다음과 같이 예측했어:
{prediction}

실제 위상 계산 결과:
{actual}

충돌:
{clashes}

이 모순을 설명할 수 있는 가설을 생성해줘.
기존에 알려진 사실을 반복하지 말고, 이 충돌이 시사하는 새로운 구조적 관계를 제안해.

JSON으로 답해:
- hypothesis: 가설 서술 (한국어)
- explanation: 왜 이 가설이 모순을 설명하는지 (한국어)
- testable_prediction: 이 가설이 맞다면 검증할 수 있는 구체적 예측 (한국어)
- involved_entities: 관련 엔티티 QID 목록
- confidence: 가설의 확신도 (0~1)
"""


def resolve(prediction: dict, actual: dict, clashes: list[dict]) -> dict:
    """Generate a hypothesis by asking Claude to resolve the contradiction."""
    prompt = RESOLVER_PROMPT_TEMPLATE.format(
        prediction=json.dumps(prediction, ensure_ascii=False, indent=2),
        actual=json.dumps(actual, ensure_ascii=False, indent=2),
        clashes=json.dumps(clashes, ensure_ascii=False, indent=2),
    )
    return llm_call(prompt, role="resolver")
