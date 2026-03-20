"""Novelty filter: reject known, trivial, or repackaged hypotheses."""

import time
from itertools import combinations
import requests
from tecs_h.claude_io.client import claude_call

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

WHITELIST_PROPS = [
    "P279", "P31", "P361", "P527", "P737", "P101", "P2578",
    "P517", "P921", "P1269", "P461", "P1382",
]

REPACKAGING_PROMPT = """
다음 가설이 기존에 알려진 수학적 사실의 재표현인지 판단해줘:

가설: {hypothesis}
관련 개념: {entities}

JSON으로 답해:
- is_repackaging: true/false
- original_fact: 원본 사실 (재표현인 경우, 아니면 빈 문자열)
- confidence: 판단 확신도 (0~1)
"""


def _sparql_query(query: str) -> dict:
    headers = {"Accept": "application/sparql-results+json", "User-Agent": "TECS-H/0.1"}
    resp = requests.get(SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=30)
    resp.raise_for_status()
    time.sleep(1)
    return resp.json()


def check_wikidata_relation(entity_a: str, entity_b: str) -> bool:
    """Check if a SEMANTIC relation exists between two entities."""
    whitelist_filter = " ".join(f"wdt:{p}" for p in WHITELIST_PROPS)
    query = f"""
    ASK WHERE {{
        VALUES ?p {{ {whitelist_filter} }}
        {{ wd:{entity_a} ?p wd:{entity_b} }}
        UNION
        {{ wd:{entity_b} ?p wd:{entity_a} }}
    }}
    """
    try:
        result = _sparql_query(query)
        return result.get("boolean", False)
    except Exception:
        return False


def check_trivial_specialization(entity_a: str, entity_b: str) -> bool:
    query = f"ASK WHERE {{ wd:{entity_a} wdt:P279+ wd:{entity_b} . }}"
    try:
        result = _sparql_query(query)
        return result.get("boolean", False)
    except Exception:
        return False


def filter_novelty(hypothesis: dict) -> dict:
    entities = hypothesis.get("involved_entities", [])

    for a, b in combinations(entities, 2):
        if check_wikidata_relation(a, b):
            return {"status": "reject", "reason": f"Wikidata에 이미 {a}-{b} 관계 존재",
                    "wikidata_duplicate": True, "trivial_specialization": False, "repackaging": False}

    for a, b in combinations(entities, 2):
        if check_trivial_specialization(a, b) or check_trivial_specialization(b, a):
            return {"status": "reject", "reason": f"{a}와 {b}는 P279 체인으로 연결",
                    "wikidata_duplicate": False, "trivial_specialization": True, "repackaging": False}

    prompt = REPACKAGING_PROMPT.format(
        hypothesis=hypothesis.get("hypothesis", ""),
        entities=", ".join(entities),
    )
    check = claude_call(prompt)
    if check.get("is_repackaging", False) and check.get("confidence", 0) >= 0.7:
        return {"status": "reject", "reason": f"기존 사실의 재표현: {check.get('original_fact', '')}",
                "wikidata_duplicate": False, "trivial_specialization": False, "repackaging": True}

    return {"status": "pass", "wikidata_duplicate": False, "trivial_specialization": False, "repackaging": False}
