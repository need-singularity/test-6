import pytest


@pytest.fixture
def sample_prediction():
    return {
        "beta0": 1,
        "beta1": 3,
        "hierarchy_score": 0.8,
        "max_persistence_h1": 0.5,
        "reasoning": "These are closely related topological concepts"
    }


@pytest.fixture
def sample_actual():
    return {
        "beta0": 1,
        "beta1": 47,
        "hierarchy_score": 0.3,
        "max_persistence_h1": 0.85,
        "long_h1": [(0.1, 0.95), (0.2, 0.8)],
    }


@pytest.fixture
def sample_edges():
    return [(0, 1), (1, 2), (2, 3), (3, 0), (1, 3)]


@pytest.fixture
def sample_hypothesis():
    return {
        "hypothesis": "Q11348과 Q192439 사이에 문서화되지 않은 중간 매개 경로가 다수 존재",
        "explanation": "β₁=47은 예측(3)보다 44개 많은 1차원 구멍을 의미",
        "testable_prediction": "유사 위상 개념 쌍에서도 β₁ > 10",
        "involved_entities": ["Q11348", "Q192439"],
        "confidence": 0.72
    }


@pytest.fixture
def sample_subgraph():
    return {
        "nodes": ["Q11348", "Q192439", "Q1753656", "Q131752"],
        "edges": [(0, 1), (1, 2), (2, 3), (3, 0), (1, 3)],
        "n_nodes": 4
    }
