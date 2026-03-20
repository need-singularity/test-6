# TECS-H Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a collision-based hypothesis generator that breaks LLM ceilings by falsifying Claude CLI predictions with topological computation from TECS-L.

**Architecture:** Claude CLI predicts topological invariants of Wikidata math entity subgraphs, TECS-L computes actual values, clashes drive hypothesis generation, and a multi-stage filter pipeline removes garbage. Batch loop orchestrates repeated collision rounds.

**Tech Stack:** Python 3.11+, Claude CLI (subprocess), TECS-L Rust engine (tecs_rs via PyO3), NetworkX, requests, PyYAML, click

**Spec:** `docs/superpowers/specs/2026-03-21-tecs-h-design.md`

**Important API correction:** `RustEngine.compute_hyperbolicity(edges, n_nodes)` takes edges+n_nodes, NOT a distance_matrix. No NetworkX floyd_warshall needed.

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project config, dependencies, CLI entry point |
| `tecs_h/__init__.py` | Package init |
| `tecs_h/claude_io/__init__.py` | Package init |
| `tecs_h/claude_io/client.py` | Claude CLI subprocess wrapper, JSON parsing, retry |
| `tecs_h/graph/__init__.py` | Package init |
| `tecs_h/graph/builder.py` | Wikidata SPARQL → subgraph extraction |
| `tecs_h/collision/__init__.py` | Package init |
| `tecs_h/collision/predictor.py` | Claude CLI prediction requests |
| `tecs_h/collision/clash.py` | Prediction vs actual comparison, clash detection |
| `tecs_h/collision/resolver.py` | Claude CLI contradiction resolution → hypothesis |
| `tecs_h/evaluator/__init__.py` | Package init |
| `tecs_h/evaluator/random_baseline.py` | Erdos-Renyi random graph comparison filter |
| `tecs_h/evaluator/scale_test.py` | Hop expansion pattern persistence filter |
| `tecs_h/evaluator/non_topo_baseline.py` | Graph-stats-only comparison filter |
| `tecs_h/evaluator/pipeline.py` | Evaluator pipeline orchestration |
| `tecs_h/novelty/__init__.py` | Package init |
| `tecs_h/novelty/filter.py` | Wikidata dedup + trivial specialization + repackaging check |
| `tecs_h/verify/__init__.py` | Package init |
| `tecs_h/verify/cross_check.py` | Pattern reproduction on sibling entities |
| `tecs_h/output/__init__.py` | Package init |
| `tecs_h/output/formatter.py` | JSON + natural language output formatting |
| `tecs_h/loop/__init__.py` | Package init |
| `tecs_h/loop/batch.py` | B-mode semi-automatic batch loop |
| `tecs_h/loop/auto.py` | C-mode interface (stub) |
| `tecs_h/cli.py` | Click CLI entry point |
| `configs/domains.yaml` | Seed entity groups by domain |
| `tests/test_claude_io.py` | Claude IO tests |
| `tests/test_graph.py` | Graph builder tests |
| `tests/test_collision.py` | Collision engine tests |
| `tests/test_evaluator.py` | Evaluator filter tests |
| `tests/test_novelty.py` | Novelty filter tests |
| `tests/test_loop.py` | Batch loop tests |
| `tests/test_formatter.py` | Output formatter tests |
| `tests/test_verify.py` | Cross-check verification tests |
| `tests/test_e2e.py` | End-to-end integration tests |
| `tests/conftest.py` | Shared fixtures |

---

## Phase 1: MVP — Collision Loop + Simple Evaluator

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `tecs_h/__init__.py`
- Create: `configs/domains.yaml`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "tecs-h"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "requests>=2.31",
    "pyyaml>=6.0",
    "networkx>=3.0",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-mock>=3.0"]

[project.scripts]
tecs-h = "tecs_h.cli:main"
```

- [ ] **Step 2: Create package init files**

`tecs_h/__init__.py`:
```python
"""TECS-H: Topological Emergence Computation System — Hypothesis"""
```

Create empty `__init__.py` in: `tecs_h/claude_io/`, `tecs_h/graph/`, `tecs_h/collision/`, `tecs_h/evaluator/`, `tecs_h/novelty/`, `tecs_h/verify/`, `tecs_h/output/`, `tecs_h/loop/`

- [ ] **Step 3: Create configs/domains.yaml**

```yaml
domains:
  topology_basics:
    description: "위상수학 기본 개념 간 관계"
    seed_groups:
      - entities: ["Q11348", "Q192439"]
        hop: 2
      - entities: ["Q1753656", "Q1322614"]
        hop: 2
  number_theory:
    description: "수론 핵심 추측"
    seed_groups:
      - entities: ["Q131752", "Q200227"]
        hop: 2
```

- [ ] **Step 4: Create tests/conftest.py with shared fixtures**

```python
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
```

- [ ] **Step 5: Install in dev mode and verify**

Run: `cd /Users/ghost/Dev/test-6 && pip install -e ".[dev]"`
Expected: Successfully installed tecs-h

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tecs_h/ configs/ tests/conftest.py
git commit -m "feat: scaffold TECS-H project structure"
```

---

### Task 2: Claude CLI Client

**Files:**
- Create: `tecs_h/claude_io/client.py`
- Create: `tests/test_claude_io.py`

- [ ] **Step 1: Write failing tests**

`tests/test_claude_io.py`:
```python
import json
import subprocess
import pytest
from tecs_h.claude_io.client import claude_call, extract_json, ClaudeCliError


class TestExtractJson:
    def test_pure_json(self):
        raw = '{"beta0": 1, "beta1": 3}'
        assert extract_json(raw) == {"beta0": 1, "beta1": 3}

    def test_json_in_code_block(self):
        raw = 'Here is the result:\n```json\n{"beta0": 1}\n```\nDone.'
        assert extract_json(raw) == {"beta0": 1}

    def test_json_with_surrounding_text(self):
        raw = 'Sure! {"beta0": 1, "beta1": 2} hope that helps'
        assert extract_json(raw) == {"beta0": 1, "beta1": 2}

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON found"):
            extract_json("no json here at all")

    def test_nested_json(self):
        raw = '{"a": {"b": 1}, "c": [1, 2]}'
        assert extract_json(raw) == {"a": {"b": 1}, "c": [1, 2]}


class TestClaudeCall:
    def test_successful_call(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='{"beta0": 1}', stderr=""
        )
        result = claude_call("test prompt")
        assert result == {"beta0": 1}
        call_args = mock_run.call_args
        assert "claude" in call_args[0][0]

    def test_nonzero_exit_raises(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout="", stderr="error"
        )
        with pytest.raises(ClaudeCliError):
            claude_call("test prompt")

    def test_timeout_raises(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)
        with pytest.raises(TimeoutError):
            claude_call("test prompt")

    def test_retry_on_parse_failure(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout='{"ok": true}', stderr=""),
        ]
        result = claude_call("test prompt")
        assert result == {"ok": True}
        assert mock_run.call_count == 2

    def test_max_retries_exceeded(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="still not json", stderr=""
        )
        with pytest.raises(ValueError, match="No JSON found"):
            claude_call("test prompt")
        assert mock_run.call_count == 3  # 1 original + 2 retries

    def test_json_suffix_appended(self, mocker):
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"ok": true}', stderr=""
        )
        claude_call("my prompt")
        prompt_sent = mock_run.call_args[0][0]
        # -p flag should contain the prompt
        assert "-p" in prompt_sent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_claude_io.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement claude_io/client.py**

```python
"""Claude CLI subprocess wrapper with JSON parsing and retry."""

import json
import re
import subprocess


class ClaudeCliError(Exception):
    """Raised when Claude CLI exits with non-zero status."""
    pass


JSON_SUFFIX = "\n\n반드시 JSON만 출력해. 코드 블록이나 설명 없이 순수 JSON만."


def extract_json(raw: str) -> dict:
    """Extract JSON dict from Claude CLI output.

    Strategy: (1) full parse, (2) ```json``` block, (3) first { to last }.
    """
    raw = raw.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: ```json ... ``` code block
    match = re.search(r"```json\s*\n(.*?)\n\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: first { to last }
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(raw[first:last + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No JSON found in output: {raw[:200]}")


def claude_call(prompt: str, timeout: int = 120, max_retries: int = 2) -> dict:
    """Call Claude CLI with -p flag and return parsed JSON.

    Retries up to max_retries times on JSON parse failure.
    """
    full_prompt = prompt + JSON_SUFFIX
    last_error = None

    for attempt in range(1 + max_retries):
        if attempt > 0:
            full_prompt = (
                f"이전 응답이 JSON이 아니었다. 다시 시도해줘.\n\n{prompt}{JSON_SUFFIX}"
            )

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Claude CLI timed out after {timeout}s")

        if result.returncode != 0:
            raise ClaudeCliError(
                f"Claude CLI exited with code {result.returncode}: {result.stderr}"
            )

        try:
            return extract_json(result.stdout)
        except ValueError as e:
            last_error = e
            continue

    raise last_error
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_claude_io.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/claude_io/client.py tests/test_claude_io.py
git commit -m "feat: add Claude CLI client with JSON parsing and retry"
```

---

### Task 3: Wikidata Subgraph Builder

**Files:**
- Create: `tecs_h/graph/builder.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write failing tests**

`tests/test_graph.py`:
```python
import pytest
from tecs_h.graph.builder import (
    build_sparql_query,
    parse_sparql_response,
    build_subgraph,
    BLACKLIST,
    WHITELIST,
)


class TestSparqlQuery:
    def test_builds_valid_sparql(self):
        query = build_sparql_query(["Q11348"], hop=1)
        assert "Q11348" in query
        assert "SELECT" in query

    def test_excludes_blacklisted_properties(self):
        query = build_sparql_query(["Q11348"], hop=1)
        for prop in BLACKLIST:
            assert prop not in query or f"FILTER" in query


class TestParseSparqlResponse:
    def test_parses_bindings(self):
        response = {
            "results": {
                "bindings": [
                    {
                        "source": {"value": "http://www.wikidata.org/entity/Q11348"},
                        "target": {"value": "http://www.wikidata.org/entity/Q192439"},
                        "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
                    }
                ]
            }
        }
        nodes, edges = parse_sparql_response(response)
        assert "Q11348" in nodes
        assert "Q192439" in nodes
        assert len(edges) == 1

    def test_empty_response(self):
        response = {"results": {"bindings": []}}
        nodes, edges = parse_sparql_response(response)
        assert len(nodes) == 0
        assert len(edges) == 0


class TestBuildSubgraph:
    def test_returns_correct_shape(self, mocker):
        mock_query = mocker.patch("tecs_h.graph.builder._sparql_query")
        mock_query.return_value = {
            "results": {
                "bindings": [
                    {
                        "source": {"value": "http://www.wikidata.org/entity/Q1"},
                        "target": {"value": "http://www.wikidata.org/entity/Q2"},
                        "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
                    },
                    {
                        "source": {"value": "http://www.wikidata.org/entity/Q2"},
                        "target": {"value": "http://www.wikidata.org/entity/Q3"},
                        "prop": {"value": "http://www.wikidata.org/prop/direct/P31"},
                    },
                ]
            }
        }
        result = build_subgraph(["Q1"], hop=1)
        assert "nodes" in result
        assert "edges" in result
        assert "n_nodes" in result
        assert result["n_nodes"] == len(result["nodes"])
        assert all(isinstance(e, tuple) and len(e) == 2 for e in result["edges"])

    def test_respects_max_nodes(self, mocker):
        bindings = [
            {
                "source": {"value": f"http://www.wikidata.org/entity/Q{i}"},
                "target": {"value": f"http://www.wikidata.org/entity/Q{i+1}"},
                "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
            }
            for i in range(50)
        ]
        mock_query = mocker.patch("tecs_h.graph.builder._sparql_query")
        mock_query.return_value = {"results": {"bindings": bindings}}
        result = build_subgraph(["Q1"], hop=1, max_nodes=10)
        assert result["n_nodes"] <= 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_graph.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement graph/builder.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_graph.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/graph/builder.py tests/test_graph.py
git commit -m "feat: add Wikidata SPARQL subgraph builder"
```

---

### Task 4: Collision Engine — Predictor

**Files:**
- Create: `tecs_h/collision/predictor.py`
- Create: `tests/test_collision.py`

- [ ] **Step 1: Write failing tests**

`tests/test_collision.py`:
```python
import pytest
from tecs_h.collision.predictor import predict, PREDICTION_PROMPT_TEMPLATE


class TestPredict:
    def test_returns_prediction_dict(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.predictor.claude_call")
        mock_claude.return_value = {
            "beta0": 1,
            "beta1": 5,
            "hierarchy_score": 0.7,
            "max_persistence_h1": 0.4,
            "reasoning": "test"
        }
        result = predict(["Q11348", "Q192439"], hop=2)
        assert "beta0" in result
        assert "beta1" in result
        assert "hierarchy_score" in result
        assert "reasoning" in result

    def test_prompt_contains_entities(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.predictor.claude_call")
        mock_claude.return_value = {"beta0": 1, "beta1": 0, "hierarchy_score": 0.5, "max_persistence_h1": 0.1, "reasoning": "x"}
        predict(["Q11348", "Q192439"], hop=2)
        prompt = mock_claude.call_args[0][0]
        assert "Q11348" in prompt
        assert "Q192439" in prompt

    def test_prompt_template_has_required_fields(self):
        assert "beta0" in PREDICTION_PROMPT_TEMPLATE
        assert "beta1" in PREDICTION_PROMPT_TEMPLATE
        assert "hierarchy_score" in PREDICTION_PROMPT_TEMPLATE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_collision.py -v`
Expected: FAIL

- [ ] **Step 3: Implement collision/predictor.py**

```python
"""Claude CLI prediction requests for topological invariants."""

from tecs_h.claude_io.client import claude_call

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
    return claude_call(prompt)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_collision.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/collision/predictor.py tests/test_collision.py
git commit -m "feat: add topological prediction via Claude CLI"
```

---

### Task 5: Collision Engine — Clash Detection

**Files:**
- Create: `tecs_h/collision/clash.py`
- Modify: `tests/test_collision.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_collision.py`:
```python
from tecs_h.collision.clash import detect_clashes, ClashStrength


class TestDetectClashes:
    def test_strong_clash(self, sample_prediction, sample_actual):
        clashes = detect_clashes(sample_prediction, sample_actual)
        assert len(clashes) > 0
        beta1_clash = next(c for c in clashes if c["field"] == "beta1")
        assert beta1_clash["strength"] == ClashStrength.STRONG

    def test_no_clash_when_close(self):
        pred = {"beta0": 1, "beta1": 5, "hierarchy_score": 0.7, "max_persistence_h1": 0.5}
        actual = {"beta0": 1, "beta1": 6, "hierarchy_score": 0.65, "max_persistence_h1": 0.5}
        clashes = detect_clashes(pred, actual)
        assert len(clashes) == 0

    def test_zero_division_safe(self):
        pred = {"beta0": 0, "beta1": 0, "hierarchy_score": 0.0, "max_persistence_h1": 0.0}
        actual = {"beta0": 0, "beta1": 0, "hierarchy_score": 0.0, "max_persistence_h1": 0.0}
        clashes = detect_clashes(pred, actual)
        assert len(clashes) == 0

    def test_low_persistence_ignores_beta1(self):
        pred = {"beta0": 1, "beta1": 1, "hierarchy_score": 0.5, "max_persistence_h1": 0.005}
        actual = {"beta0": 1, "beta1": 50, "hierarchy_score": 0.5, "max_persistence_h1": 0.005}
        clashes = detect_clashes(pred, actual)
        beta1_clashes = [c for c in clashes if c["field"] == "beta1"]
        assert len(beta1_clashes) == 0

    def test_clash_includes_gap(self, sample_prediction, sample_actual):
        clashes = detect_clashes(sample_prediction, sample_actual)
        for c in clashes:
            assert "predicted" in c
            assert "actual" in c
            assert "gap" in c
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_collision.py::TestDetectClashes -v`
Expected: FAIL

- [ ] **Step 3: Implement collision/clash.py**

```python
"""Clash detection: compare predicted vs actual topological invariants."""

from enum import Enum


class ClashStrength(str, Enum):
    STRONG = "strong"    # gap/max > 0.5
    MEDIUM = "medium"    # 0.2 < gap/max <= 0.5
    WEAK = "weak"        # gap/max <= 0.2


FIELDS = ["beta0", "beta1", "hierarchy_score", "max_persistence_h1"]
PERSISTENCE_THRESHOLD = 0.01


def detect_clashes(prediction: dict, actual: dict) -> list[dict]:
    """Detect clashes between predicted and actual topological values.

    Returns list of clash dicts with field, predicted, actual, gap, strength.
    Skips beta1 clash if max_persistence_h1 < PERSISTENCE_THRESHOLD.
    """
    clashes = []
    actual_persistence = actual.get("max_persistence_h1", 0)

    for field in FIELDS:
        pred_val = prediction.get(field, 0)
        actual_val = actual.get(field, 0)

        # Skip beta1 if persistence is too low (noisy topology)
        if field == "beta1" and actual_persistence < PERSISTENCE_THRESHOLD:
            continue

        gap = abs(pred_val - actual_val)
        max_val = max(pred_val, actual_val)

        if max_val == 0:
            continue

        ratio = gap / max_val

        if ratio > 0.5:
            strength = ClashStrength.STRONG
        elif ratio > 0.2:
            strength = ClashStrength.MEDIUM
        else:
            continue  # weak — skip

        clashes.append({
            "field": field,
            "predicted": pred_val,
            "actual": actual_val,
            "gap": gap,
            "strength": strength,
        })

    return clashes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_collision.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/collision/clash.py tests/test_collision.py
git commit -m "feat: add clash detection with persistence quality gate"
```

---

### Task 6: Collision Engine — Resolver

**Files:**
- Create: `tecs_h/collision/resolver.py`
- Modify: `tests/test_collision.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_collision.py`:
```python
from tecs_h.collision.resolver import resolve, RESOLVER_PROMPT_TEMPLATE


class TestResolve:
    def test_returns_hypothesis_dict(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.resolver.claude_call")
        mock_claude.return_value = {
            "hypothesis": "test hypothesis",
            "explanation": "test explanation",
            "testable_prediction": "test prediction",
            "involved_entities": ["Q1", "Q2"],
            "confidence": 0.7
        }
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        pred = {"beta0": 1, "beta1": 3}
        actual = {"beta0": 1, "beta1": 47}
        result = resolve(pred, actual, clashes)
        assert "hypothesis" in result
        assert "confidence" in result
        assert "involved_entities" in result

    def test_prompt_includes_clash_data(self, mocker):
        mock_claude = mocker.patch("tecs_h.collision.resolver.claude_call")
        mock_claude.return_value = {
            "hypothesis": "h", "explanation": "e",
            "testable_prediction": "t", "involved_entities": [], "confidence": 0.5
        }
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        resolve({"beta1": 3}, {"beta1": 47}, clashes)
        prompt = mock_claude.call_args[0][0]
        assert "47" in prompt
        assert "3" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_collision.py::TestResolve -v`
Expected: FAIL

- [ ] **Step 3: Implement collision/resolver.py**

```python
"""Contradiction resolution: generate hypotheses from clashes."""

import json
from tecs_h.claude_io.client import claude_call

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
    return claude_call(prompt)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_collision.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/collision/resolver.py tests/test_collision.py
git commit -m "feat: add contradiction resolver for hypothesis generation"
```

---

### Task 7: Output Formatter

**Files:**
- Create: `tecs_h/output/formatter.py`
- Create: `tests/test_formatter.py`

- [ ] **Step 1: Write failing tests**

`tests/test_formatter.py`:
```python
import json
import os
import pytest
from tecs_h.output.formatter import format_hypothesis, save_result


class TestFormatHypothesis:
    def test_generates_id(self, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(
            hypothesis=sample_hypothesis,
            prediction=sample_prediction,
            actual=sample_actual,
            clashes=clashes,
        )
        assert result["id"].startswith("hyp_")
        assert len(result["id"]) == len("hyp_YYYYMMDD_XXXXXX")

    def test_includes_all_fields(self, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(
            hypothesis=sample_hypothesis,
            prediction=sample_prediction,
            actual=sample_actual,
            clashes=clashes,
        )
        assert "topological_basis" in result
        assert "natural_language" in result
        assert "confidence" in result

    def test_topological_basis_has_predicted_and_actual(self, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(
            hypothesis=sample_hypothesis,
            prediction=sample_prediction,
            actual=sample_actual,
            clashes=clashes,
        )
        assert "predicted" in result["topological_basis"]
        assert "actual" in result["topological_basis"]


class TestSaveResult:
    def test_saves_to_correct_path(self, tmp_path, sample_hypothesis, sample_prediction, sample_actual):
        clashes = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]
        result = format_hypothesis(
            hypothesis=sample_hypothesis,
            prediction=sample_prediction,
            actual=sample_actual,
            clashes=clashes,
        )
        path = save_result(result, base_dir=str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["id"] == result["id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_formatter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement output/formatter.py**

```python
"""JSON + natural language hypothesis output formatter."""

import json
import os
import uuid
from datetime import date


def format_hypothesis(
    hypothesis: dict,
    prediction: dict,
    actual: dict,
    clashes: list[dict],
    evaluation: dict | None = None,
    novelty: dict | None = None,
) -> dict:
    """Format a hypothesis into the standard output schema."""
    today = date.today().strftime("%Y%m%d")
    hex_id = uuid.uuid4().hex[:6]

    # Extract primary clash for topological_basis
    primary_clash = clashes[0] if clashes else {}

    result = {
        "id": f"hyp_{today}_{hex_id}",
        "hypothesis": hypothesis.get("hypothesis", ""),
        "explanation": hypothesis.get("explanation", ""),
        "confidence": hypothesis.get("confidence", 0.0),
        "involved_entities": hypothesis.get("involved_entities", []),
        "topological_basis": {
            "predicted": {
                "beta0": prediction.get("beta0"),
                "beta1": prediction.get("beta1"),
            },
            "actual": {
                "beta0": actual.get("beta0"),
                "beta1": actual.get("beta1"),
            },
            "clash_type": f"{primary_clash.get('field', 'unknown')}_mismatch",
            "clash_gap": primary_clash.get("gap", 0),
        },
        "evaluation": evaluation or {},
        "novelty": novelty or {},
        "testable_prediction": hypothesis.get("testable_prediction", ""),
        "natural_language": _generate_natural_language(hypothesis, prediction, actual, clashes),
    }
    return result


def _generate_natural_language(
    hypothesis: dict, prediction: dict, actual: dict, clashes: list[dict]
) -> str:
    """Generate a human-readable summary."""
    entities = ", ".join(hypothesis.get("involved_entities", []))
    parts = [f"엔티티 [{entities}]의 서브그래프 분석 결과:"]
    for clash in clashes:
        parts.append(
            f"  {clash['field']}: 예측={clash['predicted']}, 실제={clash['actual']} (차이={clash['gap']})"
        )
    parts.append(f"가설: {hypothesis.get('hypothesis', '')}")
    parts.append(f"확신도: {hypothesis.get('confidence', 0):.2f}")
    return "\n".join(parts)


def save_result(result: dict, base_dir: str = "results") -> str:
    """Save formatted hypothesis to JSON file."""
    today = date.today().strftime("%Y-%m-%d")
    dir_path = os.path.join(base_dir, today)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{result['id']}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return file_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_formatter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/output/formatter.py tests/test_formatter.py
git commit -m "feat: add hypothesis output formatter with JSON + natural language"
```

---

### Task 8: Batch Loop MVP + CLI

**Files:**
- Create: `tecs_h/loop/batch.py`
- Create: `tecs_h/loop/auto.py`
- Create: `tecs_h/cli.py`
- Create: `tests/test_loop.py`

- [ ] **Step 1: Write failing tests**

`tests/test_loop.py`:
```python
import pytest
from unittest.mock import MagicMock
from tecs_h.loop.batch import run_collision_round, run_batch


class TestRunCollisionRound:
    def test_skips_when_no_clash(self, mocker):
        mock_predict = mocker.patch("tecs_h.loop.batch.predict")
        mock_predict.return_value = {"beta0": 1, "beta1": 5, "hierarchy_score": 0.7, "max_persistence_h1": 0.5}

        mock_compute = mocker.patch("tecs_h.loop.batch.compute_topology")
        mock_compute.return_value = (
            {"beta0": 1, "beta1": 5, "hierarchy_score": 0.7, "max_persistence_h1": 0.5, "long_h1": []},
        )

        mock_clash = mocker.patch("tecs_h.loop.batch.detect_clashes")
        mock_clash.return_value = []

        result = run_collision_round(["Q1", "Q2"], hop=2)
        assert result is None

    def test_returns_hypothesis_on_clash(self, mocker):
        mock_predict = mocker.patch("tecs_h.loop.batch.predict")
        mock_predict.return_value = {"beta0": 1, "beta1": 3, "hierarchy_score": 0.8, "max_persistence_h1": 0.5}

        mock_compute = mocker.patch("tecs_h.loop.batch.compute_topology")
        mock_compute.return_value = (
            {"beta0": 1, "beta1": 47, "hierarchy_score": 0.3, "max_persistence_h1": 0.85, "long_h1": []},
        )

        mock_clash = mocker.patch("tecs_h.loop.batch.detect_clashes")
        mock_clash.return_value = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]

        mock_resolve = mocker.patch("tecs_h.loop.batch.resolve")
        mock_resolve.return_value = {
            "hypothesis": "test", "explanation": "test",
            "testable_prediction": "test", "involved_entities": ["Q1"],
            "confidence": 0.7
        }

        result = run_collision_round(["Q1", "Q2"], hop=2)
        assert result is not None
        assert "hypothesis" in result


class TestRunBatch:
    def test_collects_results(self, mocker):
        mock_round = mocker.patch("tecs_h.loop.batch.run_collision_round")
        mock_round.side_effect = [
            {"hypothesis": "h1", "prediction": {}, "actual": {}, "clashes": []},
            None,
            {"hypothesis": "h2", "prediction": {}, "actual": {}, "clashes": []},
        ]
        seed_groups = [
            {"entities": ["Q1", "Q2"], "hop": 2},
        ]
        results = run_batch(seed_groups, rounds_per_group=3)
        assert len(results) == 2

    def test_handles_round_error(self, mocker):
        mock_round = mocker.patch("tecs_h.loop.batch.run_collision_round")
        mock_round.side_effect = [Exception("test error"), None]
        seed_groups = [{"entities": ["Q1"], "hop": 2}]
        results = run_batch(seed_groups, rounds_per_group=2)
        assert len(results) == 0  # no crash, just empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_loop.py -v`
Expected: FAIL

- [ ] **Step 3: Implement loop/batch.py**

```python
"""B-mode: semi-automatic batch collision loop."""

import logging
import sys

from tecs_h.collision.predictor import predict
from tecs_h.collision.clash import detect_clashes
from tecs_h.collision.resolver import resolve
from tecs_h.graph.builder import build_subgraph
from tecs_h.output.formatter import format_hypothesis, save_result

logger = logging.getLogger("tecs_h.loop")

# Late import to avoid hard dependency when tecs_rs unavailable
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from tecs_rs import RustEngine
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


def run_collision_round(
    entities: list[str], hop: int = 2
) -> dict | None:
    """Run a single collision round. Returns result dict or None if no clash."""
    # 1. Build subgraph (once, reused by evaluator)
    subgraph = build_subgraph(entities, hop=hop)

    # 2. Predict
    prediction = predict(entities, hop=hop)

    # 3. Compute actual
    actual = compute_topology(subgraph)

    # 4. Detect clashes
    clashes = detect_clashes(prediction, actual)
    if not clashes:
        logger.info("No clash detected for %s, skipping", entities)
        return None

    # 5. Resolve
    hypothesis = resolve(prediction, actual, clashes)

    return {
        "hypothesis": hypothesis,
        "prediction": prediction,
        "actual": actual,
        "clashes": clashes,
        "subgraph": subgraph,
    }


def run_batch(
    seed_groups: list[dict],
    rounds_per_group: int = 5,
    results_dir: str = "results",
) -> list[dict]:
    """Run batch collision loop over seed groups.

    Each seed_group: {"entities": [...], "hop": int}
    """
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
                    hypothesis=result["hypothesis"],
                    prediction=result["prediction"],
                    actual=result["actual"],
                    clashes=result["clashes"],
                )
                save_result(formatted, base_dir=results_dir)
                all_results.append(formatted)
                logger.info(
                    "Round %d: hypothesis generated — %s",
                    round_num, formatted["id"]
                )

            except Exception as e:
                logger.error(
                    "Round %d failed for %s: %s", round_num, entities, e
                )
                continue

    # Rank by EmergenceDetector score
    try:
        sys.path.insert(0, "/Users/ghost/dev/test-4/python")
        from tecs.emergence import EmergenceDetector
        detector = EmergenceDetector()
        for r in all_results:
            topo_bundle = r.get("topological_basis", {}).get("actual", {})
            hier_bundle = {"hierarchy_score": topo_bundle.get("hierarchy_score", 0.5)}
            try:
                score = detector.score(topo_bundle, hier_bundle)
                r["emergence_score"] = score.total_score
            except Exception:
                r["emergence_score"] = 0.0
        all_results.sort(key=lambda x: x.get("emergence_score", 0), reverse=True)
    except ImportError:
        logger.warning("EmergenceDetector not available, skipping ranking")

    logger.info("Batch complete: %d hypotheses generated", len(all_results))
    return all_results
```

- [ ] **Step 4: Implement loop/auto.py (stub)**

```python
"""C-mode: automatic loop interface (stub for future implementation)."""


class AutoLoop:
    """Automatic collision loop with evolutionary refinement.

    Wraps batch mode with automatic iteration and hypothesis mutation.
    """

    def __init__(self, max_rounds: int = 1000, rate_limit_per_min: int = 10):
        self.max_rounds = max_rounds
        self.rate_limit_per_min = rate_limit_per_min

    def run(self, seed_groups: list[dict]) -> list[dict]:
        raise NotImplementedError("C-mode not yet implemented")

    def evolve(self, previous_results: list[dict]) -> list[dict]:
        raise NotImplementedError("C-mode evolution not yet implemented")
```

- [ ] **Step 5: Implement cli.py**

```python
"""TECS-H CLI entry point."""

import logging
import sys

import click
import yaml


def _setup_logging(log_dir: str = "logs"):
    import os
    from datetime import date

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{date.today().isoformat()}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


@click.group()
def main():
    """TECS-H: Topological Emergence Computation System — Hypothesis"""
    _setup_logging()


@main.command()
@click.option("--entities", required=True, help="Comma-separated Wikidata QIDs")
@click.option("--rounds", default=5, help="Number of collision rounds")
@click.option("--hop", default=2, help="BFS hop depth")
def run(entities: str, rounds: int, hop: int):
    """Run collision loop for a single entity group."""
    from tecs_h.loop.batch import run_batch

    entity_list = [e.strip() for e in entities.split(",")]
    seed_groups = [{"entities": entity_list, "hop": hop}]
    results = run_batch(seed_groups, rounds_per_group=rounds)
    click.echo(f"\n{len(results)} hypotheses generated.")


@main.command()
@click.option("--domain", required=True, help="Domain name from configs/domains.yaml")
@click.option("--rounds-per-group", default=5, help="Rounds per seed group")
@click.option("--config", default="configs/domains.yaml", help="Config file path")
def batch(domain: str, rounds_per_group: int, config: str):
    """Run batch collision loop for a domain."""
    from tecs_h.loop.batch import run_batch

    with open(config) as f:
        domains = yaml.safe_load(f)

    if domain not in domains["domains"]:
        click.echo(f"Domain '{domain}' not found. Available: {list(domains['domains'].keys())}")
        sys.exit(1)

    seed_groups = domains["domains"][domain]["seed_groups"]
    results = run_batch(seed_groups, rounds_per_group=rounds_per_group)
    click.echo(f"\n{len(results)} hypotheses generated.")


@main.command()
@click.option("--date", "target_date", default=None, help="Date (YYYY-MM-DD)")
def results(target_date: str):
    """Show generated hypotheses."""
    import json
    import os
    from datetime import date as dt_date

    if target_date is None:
        target_date = dt_date.today().isoformat()

    results_dir = os.path.join("results", target_date)
    if not os.path.exists(results_dir):
        click.echo(f"No results for {target_date}")
        return

    files = sorted(f for f in os.listdir(results_dir) if f.endswith(".json"))
    click.echo(f"\n{len(files)} hypotheses found for {target_date}:\n")
    for fname in files:
        with open(os.path.join(results_dir, fname)) as f:
            hyp = json.load(f)
        click.echo(f"  [{hyp['id']}] confidence={hyp['confidence']:.2f}")
        click.echo(f"    {hyp['hypothesis'][:100]}")
        click.echo()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_loop.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add tecs_h/loop/ tecs_h/cli.py tests/test_loop.py
git commit -m "feat: add batch collision loop and CLI entry point"
```

---

## Phase 2: Evaluator 3-Filter Pipeline

### Task 9: Random Baseline Filter

**Files:**
- Create: `tecs_h/evaluator/random_baseline.py`
- Create: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

`tests/test_evaluator.py`:
```python
import pytest
from tecs_h.evaluator.random_baseline import filter_random, generate_random_graph


class TestGenerateRandomGraph:
    def test_correct_shape(self):
        graph = generate_random_graph(n_nodes=10, n_edges=15)
        assert graph["n_nodes"] == 10
        assert len(graph["edges"]) <= 15

    def test_no_self_loops(self):
        graph = generate_random_graph(n_nodes=10, n_edges=15)
        for u, v in graph["edges"]:
            assert u != v


class TestFilterRandom:
    def test_passes_unique_topology(self, mocker, sample_actual):
        mock_engine = mocker.patch("tecs_h.evaluator.random_baseline._get_engine")
        engine = mock_engine.return_value
        # Random graphs produce very different topology
        engine.compute_topology_from_edges.return_value = {"beta0": 5, "beta1": 0, "max_persistence_h1": 0.01}
        result = filter_random(sample_actual, n_nodes=10, n_edges=15)
        assert result["status"] == "pass"

    def test_rejects_common_topology(self, mocker, sample_actual):
        mock_engine = mocker.patch("tecs_h.evaluator.random_baseline._get_engine")
        engine = mock_engine.return_value
        # Random graphs produce same topology
        engine.compute_topology_from_edges.return_value = {
            "beta0": sample_actual["beta0"],
            "beta1": sample_actual["beta1"],
            "max_persistence_h1": sample_actual["max_persistence_h1"],
        }
        result = filter_random(sample_actual, n_nodes=10, n_edges=15)
        assert result["status"] == "reject"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement evaluator/random_baseline.py**

```python
"""Filter 1: Random baseline — reject if pattern appears in random graphs."""

import random

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine


def generate_random_graph(n_nodes: int, n_edges: int) -> dict:
    """Generate Erdos-Renyi random graph with given node/edge count."""
    edges = set()
    max_possible = n_nodes * (n_nodes - 1) // 2
    n_edges = min(n_edges, max_possible)
    while len(edges) < n_edges:
        u = random.randint(0, n_nodes - 1)
        v = random.randint(0, n_nodes - 1)
        if u != v and (u, v) not in edges and (v, u) not in edges:
            edges.add((u, v))
    return {"edges": list(edges), "n_nodes": n_nodes}


def _topology_matches(actual: dict, random_topo: dict) -> bool:
    """Check if random topology matches actual pattern."""
    return (
        random_topo.get("beta0", 0) == actual.get("beta0", 0)
        and abs(random_topo.get("beta1", 0) - actual.get("beta1", 0))
        <= max(1, actual.get("beta1", 0) * 0.2)
    )


def filter_random(
    actual_topology: dict, n_nodes: int, n_edges: int, n_random: int = 10
) -> dict:
    """Reject if 70%+ of random graphs show the same topological pattern."""
    engine = _get_engine()
    match_count = 0

    for _ in range(n_random):
        rg = generate_random_graph(n_nodes, n_edges)
        if not rg["edges"]:
            continue
        try:
            random_topo = engine.compute_topology_from_edges(rg["edges"], rg["n_nodes"])
            if _topology_matches(actual_topology, random_topo):
                match_count += 1
        except Exception:
            continue

    match_rate = match_count / n_random if n_random > 0 else 0

    if match_rate >= 0.7:
        return {"status": "reject", "reason": f"랜덤 그래프에서 {match_rate:.0%} 재현", "match_rate": match_rate}
    return {"status": "pass", "match_rate": match_rate}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/evaluator/random_baseline.py tests/test_evaluator.py
git commit -m "feat: add random baseline evaluator filter"
```

---

### Task 10: Scale Test Filter

**Files:**
- Create: `tecs_h/evaluator/scale_test.py`
- Modify: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_evaluator.py`:
```python
from tecs_h.evaluator.scale_test import filter_scale


class TestFilterScale:
    def test_passes_persistent_pattern(self, mocker):
        mock_build = mocker.patch("tecs_h.evaluator.scale_test.build_subgraph")
        mock_engine = mocker.patch("tecs_h.evaluator.scale_test._get_engine")
        engine = mock_engine.return_value

        # Each hop returns subgraph under max_nodes
        mock_build.side_effect = [
            {"edges": [(0, 1)], "n_nodes": 10, "nodes": list(range(10))},
            {"edges": [(0, 1)], "n_nodes": 50, "nodes": list(range(50))},
            {"edges": [(0, 1)], "n_nodes": 100, "nodes": list(range(100))},
        ]
        engine.compute_topology_from_edges.return_value = {"beta0": 1, "beta1": 10, "max_persistence_h1": 0.5}

        result = filter_scale(
            actual_topology={"beta0": 1, "beta1": 10},
            entities=["Q1"], original_hop=2, max_nodes=300
        )
        assert result["status"] == "pass"

    def test_rejects_vanishing_pattern(self, mocker):
        mock_build = mocker.patch("tecs_h.evaluator.scale_test.build_subgraph")
        mock_engine = mocker.patch("tecs_h.evaluator.scale_test._get_engine")
        engine = mock_engine.return_value

        mock_build.side_effect = [
            {"edges": [(0, 1)], "n_nodes": 10, "nodes": list(range(10))},
            {"edges": [(0, 1)], "n_nodes": 50, "nodes": list(range(50))},
            {"edges": [(0, 1)], "n_nodes": 100, "nodes": list(range(100))},
        ]
        # Pattern vanishes at larger scales
        engine.compute_topology_from_edges.side_effect = [
            {"beta0": 5, "beta1": 0, "max_persistence_h1": 0.01},
            {"beta0": 1, "beta1": 0, "max_persistence_h1": 0.01},
            {"beta0": 1, "beta1": 0, "max_persistence_h1": 0.01},
        ]
        result = filter_scale(
            actual_topology={"beta0": 1, "beta1": 10},
            entities=["Q1"], original_hop=2, max_nodes=300
        )
        assert result["status"] == "reject"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py::TestFilterScale -v`
Expected: FAIL

- [ ] **Step 3: Implement evaluator/scale_test.py**

```python
"""Filter 2: Scale test — reject if pattern vanishes at larger subgraph sizes."""

import logging
from tecs_h.graph.builder import build_subgraph

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine


def _pattern_persists(original: dict, scaled: dict) -> bool:
    """Check if the topological pattern persists at larger scale."""
    orig_beta1 = original.get("beta1", 0)
    scaled_beta1 = scaled.get("beta1", 0)
    if orig_beta1 == 0:
        return scaled_beta1 == 0
    return scaled_beta1 >= orig_beta1 * 0.5


def filter_scale(
    actual_topology: dict,
    entities: list[str],
    original_hop: int = 2,
    max_nodes: int = 300,
    test_hops: list[int] | None = None,
) -> dict:
    """Reject if pattern doesn't persist when subgraph size increases."""
    engine = _get_engine()
    if test_hops is None:
        test_hops = [original_hop + 1, original_hop + 2]

    persist_count = 0
    valid_tests = 0

    for hop in test_hops:
        try:
            subgraph = build_subgraph(entities, hop=hop, max_nodes=max_nodes)
            if subgraph["n_nodes"] >= max_nodes:
                logger.info("Hop %d hit max_nodes cap, excluding from comparison", hop)
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
        return {"status": "pass", "reason": "스케일 테스트 불가 (모든 hop이 max_nodes 초과)", "persist_rate": None}

    persist_rate = persist_count / valid_tests
    if persist_rate < 0.5:
        return {"status": "reject", "reason": f"규모 확장 시 패턴 소멸 ({persist_rate:.0%})", "persist_rate": persist_rate}
    return {"status": "pass", "persist_rate": persist_rate}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/evaluator/scale_test.py tests/test_evaluator.py
git commit -m "feat: add scale test evaluator filter"
```

---

### Task 11: Non-Topological Baseline Filter

**Files:**
- Create: `tecs_h/evaluator/non_topo_baseline.py`
- Modify: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_evaluator.py`:
```python
from tecs_h.evaluator.non_topo_baseline import filter_non_topo


class TestFilterNonTopo:
    def test_passes_unique_hypothesis(self, mocker, sample_hypothesis):
        mock_claude = mocker.patch("tecs_h.evaluator.non_topo_baseline.claude_call")
        # First call: baseline hypothesis from graph stats
        # Second call: comparison judgment
        mock_claude.side_effect = [
            {"hypothesis": "completely different hypothesis about degree distribution"},
            {"same_core_claim": False, "confidence": 0.9},
        ]
        result = filter_non_topo(sample_hypothesis, graph_stats={"avg_degree": 3.2})
        assert result["status"] == "pass"

    def test_rejects_duplicate_hypothesis(self, mocker, sample_hypothesis):
        mock_claude = mocker.patch("tecs_h.evaluator.non_topo_baseline.claude_call")
        mock_claude.side_effect = [
            {"hypothesis": "basically the same thing"},
            {"same_core_claim": True, "confidence": 0.85},
        ]
        result = filter_non_topo(sample_hypothesis, graph_stats={"avg_degree": 3.2})
        assert result["status"] == "reject"

    def test_passes_when_comparison_low_confidence(self, mocker, sample_hypothesis):
        mock_claude = mocker.patch("tecs_h.evaluator.non_topo_baseline.claude_call")
        mock_claude.side_effect = [
            {"hypothesis": "somewhat similar"},
            {"same_core_claim": True, "confidence": 0.5},  # below 0.8 threshold
        ]
        result = filter_non_topo(sample_hypothesis, graph_stats={"avg_degree": 3.2})
        assert result["status"] == "pass"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py::TestFilterNonTopo -v`
Expected: FAIL

- [ ] **Step 3: Implement evaluator/non_topo_baseline.py**

```python
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


def filter_non_topo(
    hypothesis: dict,
    graph_stats: dict,
    confidence_threshold: float = 0.8,
) -> dict:
    """Reject if same hypothesis is reachable from graph stats alone."""
    entities = hypothesis.get("involved_entities", [])

    # Step 1: Generate baseline hypothesis from graph stats only
    baseline_prompt = BASELINE_PROMPT.format(
        graph_stats=json.dumps(graph_stats, ensure_ascii=False),
        entities=", ".join(entities),
    )
    baseline = claude_call(baseline_prompt)

    # Step 2: Compare hypotheses
    compare_prompt = COMPARISON_PROMPT.format(
        hypothesis_a=hypothesis.get("hypothesis", ""),
        hypothesis_b=baseline.get("hypothesis", ""),
    )
    comparison = claude_call(compare_prompt)

    is_same = comparison.get("same_core_claim", False)
    confidence = comparison.get("confidence", 0)

    if is_same and confidence >= confidence_threshold:
        return {
            "status": "reject",
            "reason": f"위상 없이도 도달 가능 (confidence={confidence:.2f})",
            "baseline_hypothesis": baseline.get("hypothesis", ""),
        }
    return {"status": "pass", "confidence": confidence}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/evaluator/non_topo_baseline.py tests/test_evaluator.py
git commit -m "feat: add non-topological baseline evaluator filter"
```

---

### Task 12: Evaluator Pipeline

**Files:**
- Create: `tecs_h/evaluator/pipeline.py`
- Modify: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_evaluator.py`:
```python
from tecs_h.evaluator.pipeline import evaluate


class TestEvaluatePipeline:
    def test_passes_all_filters(self, mocker, sample_hypothesis, sample_actual):
        mocker.patch("tecs_h.evaluator.pipeline.filter_random", return_value={"status": "pass"})
        mocker.patch("tecs_h.evaluator.pipeline.filter_scale", return_value={"status": "pass"})
        mocker.patch("tecs_h.evaluator.pipeline.filter_non_topo", return_value={"status": "pass"})
        result = evaluate(sample_hypothesis, sample_actual, ["Q1"], n_nodes=10, n_edges=15)
        assert result["status"] == "passed"
        assert result["filters_cleared"] == 3

    def test_stops_at_first_rejection(self, mocker, sample_hypothesis, sample_actual):
        mocker.patch("tecs_h.evaluator.pipeline.filter_random", return_value={"status": "reject", "reason": "random"})
        mock_scale = mocker.patch("tecs_h.evaluator.pipeline.filter_scale")
        mock_nontopo = mocker.patch("tecs_h.evaluator.pipeline.filter_non_topo")
        result = evaluate(sample_hypothesis, sample_actual, ["Q1"], n_nodes=10, n_edges=15)
        assert result["status"] == "rejected"
        mock_scale.assert_not_called()
        mock_nontopo.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py::TestEvaluatePipeline -v`
Expected: FAIL

- [ ] **Step 3: Implement evaluator/pipeline.py**

```python
"""Evaluator pipeline: run 3 filters in cost order."""

import logging
from tecs_h.evaluator.random_baseline import filter_random
from tecs_h.evaluator.scale_test import filter_scale
from tecs_h.evaluator.non_topo_baseline import filter_non_topo

logger = logging.getLogger(__name__)


def _compute_graph_stats(edges: list[tuple], n_nodes: int) -> dict:
    """Compute basic graph statistics for non-topo baseline."""
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(range(n_nodes))
    G.add_edges_from(edges)
    degrees = [d for _, d in G.degree()]
    return {
        "n_nodes": n_nodes,
        "n_edges": len(edges),
        "avg_degree": sum(degrees) / max(len(degrees), 1),
        "max_degree": max(degrees) if degrees else 0,
        "clustering_coefficient": nx.average_clustering(G),
        "density": nx.density(G),
    }


def evaluate(
    hypothesis: dict,
    actual_topology: dict,
    entities: list[str],
    n_nodes: int,
    n_edges: int,
    subgraph_edges: list[tuple] | None = None,
    original_hop: int = 2,
) -> dict:
    """Run evaluator pipeline: random → scale → non-topo. Stops at first reject."""
    results = {}

    # Filter 1: Random baseline (cheapest)
    logger.info("Running filter 1: random baseline")
    r1 = filter_random(actual_topology, n_nodes=n_nodes, n_edges=n_edges)
    results["random_baseline"] = r1["status"]
    if r1["status"] == "reject":
        return {"status": "rejected", "reason": r1.get("reason", ""), "filter": "random_baseline", **results}

    # Filter 2: Scale test (medium)
    logger.info("Running filter 2: scale test")
    r2 = filter_scale(actual_topology, entities=entities, original_hop=original_hop)
    results["scale_test"] = r2["status"]
    if r2["status"] == "reject":
        return {"status": "rejected", "reason": r2.get("reason", ""), "filter": "scale_test", **results}

    # Filter 3: Non-topo baseline (most expensive — Claude call)
    logger.info("Running filter 3: non-topo baseline")
    graph_stats = _compute_graph_stats(subgraph_edges or [], n_nodes) if subgraph_edges else {}
    r3 = filter_non_topo(hypothesis, graph_stats=graph_stats)
    results["non_topo_baseline"] = r3["status"]
    if r3["status"] == "reject":
        return {"status": "rejected", "reason": r3.get("reason", ""), "filter": "non_topo_baseline", **results}

    return {"status": "passed", "filters_cleared": 3, **results}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_evaluator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/evaluator/pipeline.py tests/test_evaluator.py
git commit -m "feat: add evaluator pipeline with short-circuit rejection"
```

---

## Phase 3: Novelty Filter

### Task 13: Novelty Filter

**Files:**
- Create: `tecs_h/novelty/filter.py`
- Create: `tests/test_novelty.py`

- [ ] **Step 1: Write failing tests**

`tests/test_novelty.py`:
```python
import pytest
from tecs_h.novelty.filter import filter_novelty, check_wikidata_relation, check_trivial_specialization


class TestCheckWikidataRelation:
    def test_finds_existing_relation(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"results": {"bindings": [{"rel": {"value": "something"}}]}}
        assert check_wikidata_relation("Q1", "Q2") is True

    def test_no_relation(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"results": {"bindings": []}}
        assert check_wikidata_relation("Q1", "Q2") is False


class TestCheckTrivialSpecialization:
    def test_trivial_parent_child(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        # Q2 is a parent class of Q1
        mock_query.return_value = {
            "results": {"bindings": [{"parent": {"value": "http://www.wikidata.org/entity/Q2"}}]}
        }
        assert check_trivial_specialization("Q1", "Q2") is True

    def test_not_trivial(self, mocker):
        mock_query = mocker.patch("tecs_h.novelty.filter._sparql_query")
        mock_query.return_value = {"results": {"bindings": []}}
        assert check_trivial_specialization("Q1", "Q2") is False


class TestFilterNovelty:
    def test_rejects_existing_relation(self, mocker):
        mocker.patch("tecs_h.novelty.filter.check_wikidata_relation", return_value=True)
        hyp = {"involved_entities": ["Q1", "Q2"], "hypothesis": "test"}
        result = filter_novelty(hyp)
        assert result["status"] == "reject"

    def test_rejects_repackaging(self, mocker):
        mocker.patch("tecs_h.novelty.filter.check_wikidata_relation", return_value=False)
        mocker.patch("tecs_h.novelty.filter.check_trivial_specialization", return_value=False)
        mock_claude = mocker.patch("tecs_h.novelty.filter.claude_call")
        mock_claude.return_value = {"is_repackaging": True, "confidence": 0.9, "original_fact": "known theorem"}
        hyp = {"involved_entities": ["Q1", "Q2"], "hypothesis": "test"}
        result = filter_novelty(hyp)
        assert result["status"] == "reject"

    def test_passes_novel(self, mocker):
        mocker.patch("tecs_h.novelty.filter.check_wikidata_relation", return_value=False)
        mocker.patch("tecs_h.novelty.filter.check_trivial_specialization", return_value=False)
        mock_claude = mocker.patch("tecs_h.novelty.filter.claude_call")
        mock_claude.return_value = {"is_repackaging": False, "confidence": 0.3, "original_fact": ""}
        hyp = {"involved_entities": ["Q1", "Q2"], "hypothesis": "test"}
        result = filter_novelty(hyp)
        assert result["status"] == "pass"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_novelty.py -v`
Expected: FAIL

- [ ] **Step 3: Implement novelty/filter.py**

```python
"""Novelty filter: reject known, trivial, or repackaged hypotheses."""

import time
from itertools import combinations

import requests

from tecs_h.claude_io.client import claude_call

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

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
    """Execute SPARQL query."""
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "TECS-H/0.1",
    }
    resp = requests.get(SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=30)
    resp.raise_for_status()
    time.sleep(1)
    return resp.json()


def check_wikidata_relation(entity_a: str, entity_b: str) -> bool:
    """Check if a SEMANTIC relation exists between two entities in Wikidata.

    Only checks structural/semantic properties (WHITELIST), not meta properties.
    Most entity pairs have trivial relations (e.g. 'described by source'),
    so we only check meaningful ones to avoid rejecting everything.
    """
    whitelist_filter = " ".join(f"wdt:{p}" for p in [
        "P279", "P31", "P361", "P527", "P737", "P101", "P2578",
        "P517", "P921", "P1269", "P461", "P1382",
    ])
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
    """Check if one entity is a parent class of the other via P279 chain."""
    query = f"""
    ASK WHERE {{
        wd:{entity_a} wdt:P279+ wd:{entity_b} .
    }}
    """
    try:
        result = _sparql_query(query)
        return result.get("boolean", False) or bool(result.get("results", {}).get("bindings", []))
    except Exception:
        return False


def filter_novelty(hypothesis: dict) -> dict:
    """3-stage novelty filter: duplicate → trivial → repackaging."""
    entities = hypothesis.get("involved_entities", [])

    # Stage 1: Direct relation duplicate
    for a, b in combinations(entities, 2):
        if check_wikidata_relation(a, b):
            return {
                "status": "reject",
                "reason": f"Wikidata에 이미 {a}-{b} 관계 존재",
                "wikidata_duplicate": True,
                "trivial_specialization": False,
                "repackaging": False,
            }

    # Stage 2: Trivial specialization
    for a, b in combinations(entities, 2):
        if check_trivial_specialization(a, b) or check_trivial_specialization(b, a):
            return {
                "status": "reject",
                "reason": f"{a}와 {b}는 P279 체인으로 연결 (자명한 특수케이스)",
                "wikidata_duplicate": False,
                "trivial_specialization": True,
                "repackaging": False,
            }

    # Stage 3: Repackaging check (Claude)
    prompt = REPACKAGING_PROMPT.format(
        hypothesis=hypothesis.get("hypothesis", ""),
        entities=", ".join(entities),
    )
    check = claude_call(prompt)

    if check.get("is_repackaging", False) and check.get("confidence", 0) >= 0.7:
        return {
            "status": "reject",
            "reason": f"기존 사실의 재표현: {check.get('original_fact', '')}",
            "wikidata_duplicate": False,
            "trivial_specialization": False,
            "repackaging": True,
        }

    return {
        "status": "pass",
        "wikidata_duplicate": False,
        "trivial_specialization": False,
        "repackaging": False,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_novelty.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/novelty/filter.py tests/test_novelty.py
git commit -m "feat: add novelty filter with Wikidata dedup and repackaging check"
```

---

## Phase 4: Integration — Evaluator + Novelty in Batch Loop

### Task 14: Integrate Evaluator + Novelty into Batch Loop

**Files:**
- Modify: `tecs_h/loop/batch.py`
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_loop.py`:
```python
class TestRunCollisionRoundWithFilters:
    def test_evaluator_rejection_skips_hypothesis(self, mocker):
        mock_predict = mocker.patch("tecs_h.loop.batch.predict")
        mock_predict.return_value = {"beta0": 1, "beta1": 3, "hierarchy_score": 0.8, "max_persistence_h1": 0.5}

        mock_compute = mocker.patch("tecs_h.loop.batch.compute_topology")
        mock_compute.return_value = (
            {"beta0": 1, "beta1": 47, "hierarchy_score": 0.3, "max_persistence_h1": 0.85, "long_h1": []},
        )

        mock_clash = mocker.patch("tecs_h.loop.batch.detect_clashes")
        mock_clash.return_value = [{"field": "beta1", "predicted": 3, "actual": 47, "gap": 44, "strength": "strong"}]

        mock_resolve = mocker.patch("tecs_h.loop.batch.resolve")
        mock_resolve.return_value = {
            "hypothesis": "test", "explanation": "test",
            "testable_prediction": "test", "involved_entities": ["Q1"],
            "confidence": 0.7
        }

        mock_evaluate = mocker.patch("tecs_h.loop.batch.evaluate")
        mock_evaluate.return_value = {"status": "rejected", "reason": "random baseline"}

        result = run_collision_round(["Q1", "Q2"], hop=2)
        assert result is None  # rejected by evaluator
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_loop.py::TestRunCollisionRoundWithFilters -v`
Expected: FAIL

- [ ] **Step 3: Update loop/batch.py to include evaluator + novelty**

Add imports at top of `tecs_h/loop/batch.py`:
```python
from tecs_h.evaluator.pipeline import evaluate
from tecs_h.novelty.filter import filter_novelty
```

Update `run_collision_round` to add evaluation and novelty filtering after hypothesis generation (note: subgraph is now built once in step 1 and reused):
```python
def run_collision_round(
    entities: list[str], hop: int = 2
) -> dict | None:
    """Run a single collision round. Returns result dict or None if no clash or filtered out."""
    # 1. Build subgraph (once, reused by evaluator)
    subgraph = build_subgraph(entities, hop=hop)

    # 2. Predict
    prediction = predict(entities, hop=hop)

    # 3. Compute actual
    actual = compute_topology(subgraph)

    # 4. Detect clashes
    clashes = detect_clashes(prediction, actual)
    if not clashes:
        logger.info("No clash detected for %s, skipping", entities)
        return None

    # 5. Resolve
    hypothesis = resolve(prediction, actual, clashes)

    # 6. Evaluate (3-filter pipeline) — reuses cached subgraph
    eval_result = evaluate(
        hypothesis=hypothesis,
        actual_topology=actual,
        entities=entities,
        n_nodes=subgraph["n_nodes"],
        n_edges=len(subgraph["edges"]),
        subgraph_edges=subgraph["edges"],
        original_hop=hop,
    )
    if eval_result["status"] == "rejected":
        logger.info("Hypothesis rejected by evaluator: %s", eval_result.get("reason", ""))
        return None

    # 6. Novelty filter
    novelty_result = filter_novelty(hypothesis)
    if novelty_result["status"] == "reject":
        logger.info("Hypothesis rejected by novelty filter: %s", novelty_result.get("reason", ""))
        return None

    return {
        "hypothesis": hypothesis,
        "prediction": prediction,
        "actual": actual,
        "clashes": clashes,
        "evaluation": eval_result,
        "novelty": novelty_result,
    }
```

Update `run_batch` to pass evaluation and novelty data to formatter:
```python
                formatted = format_hypothesis(
                    hypothesis=result["hypothesis"],
                    prediction=result["prediction"],
                    actual=result["actual"],
                    clashes=result["clashes"],
                    evaluation=result.get("evaluation"),
                    novelty=result.get("novelty"),
                )
```

- [ ] **Step 4: Run all tests**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/loop/batch.py tests/test_loop.py
git commit -m "feat: integrate evaluator and novelty filter into batch loop"
```

---

### Task 15: Cross-Check Verification (Phase 4)

**Files:**
- Create: `tecs_h/verify/cross_check.py`
- Modify: `tests/test_loop.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_verify.py`:
```python
import pytest
from tecs_h.verify.cross_check import find_sibling_entities, cross_check


class TestFindSiblingEntities:
    def test_finds_siblings(self, mocker):
        mock_query = mocker.patch("tecs_h.verify.cross_check._sparql_query")
        mock_query.return_value = {
            "results": {
                "bindings": [
                    {"sibling": {"value": "http://www.wikidata.org/entity/Q100"}},
                    {"sibling": {"value": "http://www.wikidata.org/entity/Q200"}},
                ]
            }
        }
        siblings = find_sibling_entities("Q1", limit=5)
        assert "Q100" in siblings
        assert "Q200" in siblings

    def test_empty_when_no_siblings(self, mocker):
        mock_query = mocker.patch("tecs_h.verify.cross_check._sparql_query")
        mock_query.return_value = {"results": {"bindings": []}}
        assert find_sibling_entities("Q1") == []


class TestCrossCheck:
    def test_reproduces_pattern(self, mocker):
        mocker.patch("tecs_h.verify.cross_check.find_sibling_entities", return_value=["Q100", "Q200"])
        mock_compute = mocker.patch("tecs_h.verify.cross_check._compute_and_check")
        mock_compute.return_value = True  # pattern reproduces

        result = cross_check(
            hypothesis={"involved_entities": ["Q1", "Q2"]},
            actual_topology={"beta0": 1, "beta1": 10},
            min_checks=2,
        )
        assert result["reproduced"]
        assert result["confidence_adjustment"] > 0

    def test_no_reproduction(self, mocker):
        mocker.patch("tecs_h.verify.cross_check.find_sibling_entities", return_value=["Q100", "Q200"])
        mock_compute = mocker.patch("tecs_h.verify.cross_check._compute_and_check")
        mock_compute.return_value = False

        result = cross_check(
            hypothesis={"involved_entities": ["Q1", "Q2"]},
            actual_topology={"beta0": 1, "beta1": 10},
            min_checks=2,
        )
        assert not result["reproduced"]
        assert result["warning"] == "단일 사례"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_verify.py -v`
Expected: FAIL

- [ ] **Step 3: Implement verify/cross_check.py**

```python
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
        from tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine


def _sparql_query(query: str) -> dict:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "TECS-H/0.1",
    }
    resp = requests.get(SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=30)
    resp.raise_for_status()
    time.sleep(1)
    return resp.json()


def find_sibling_entities(entity: str, limit: int = 5) -> list[str]:
    """Find sibling entities via P279/P31 (same parent class)."""
    query = f"""
    SELECT DISTINCT ?sibling WHERE {{
        wd:{entity} wdt:P279 ?parent .
        ?sibling wdt:P279 ?parent .
        FILTER(?sibling != wd:{entity})
    }}
    LIMIT {limit}
    """
    try:
        result = _sparql_query(query)
        return [
            b["sibling"]["value"].split("/")[-1]
            for b in result.get("results", {}).get("bindings", [])
        ]
    except Exception as e:
        logger.warning("Sibling query failed for %s: %s", entity, e)
        return []


def _compute_and_check(entities: list[str], expected_topology: dict, hop: int = 2) -> bool:
    """Compute topology for entity group and check if pattern matches."""
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


def cross_check(
    hypothesis: dict,
    actual_topology: dict,
    min_checks: int = 2,
    hop: int = 2,
) -> dict:
    """Cross-check hypothesis by testing pattern on sibling entity combinations."""
    entities = hypothesis.get("involved_entities", [])
    if not entities:
        return {"reproduced": False, "warning": "엔티티 없음", "confidence_adjustment": 0}

    # Find siblings for first entity
    siblings = find_sibling_entities(entities[0])
    if len(siblings) < min_checks:
        return {"reproduced": False, "warning": "형제 엔티티 부족", "confidence_adjustment": 0}

    reproduce_count = 0
    checks_done = 0

    for sibling in siblings[:min_checks * 2]:  # try more to get min_checks valid results
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
        return {
            "reproduced": True,
            "reproduce_rate": reproduce_rate,
            "confidence_adjustment": 0.1,
            "warning": None,
        }
    else:
        return {
            "reproduced": False,
            "reproduce_rate": reproduce_rate,
            "confidence_adjustment": 0,
            "warning": "단일 사례",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/test_verify.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tecs_h/verify/cross_check.py tests/test_verify.py
git commit -m "feat: add cross-check verification for pattern reproduction"
```

---

### Task 16: Final Integration + End-to-End Test

**Files:**
- Modify: `tecs_h/loop/batch.py` (add cross_check)
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write end-to-end integration test**

`tests/test_e2e.py`:
```python
"""End-to-end test with all components mocked at the boundary."""

import pytest
from tecs_h.loop.batch import run_batch


class TestEndToEnd:
    def test_full_pipeline_produces_output(self, mocker, tmp_path):
        # Mock Claude CLI
        mock_claude = mocker.patch("tecs_h.claude_io.client.subprocess.run")

        import subprocess
        import json

        prediction = {"beta0": 1, "beta1": 3, "hierarchy_score": 0.8, "max_persistence_h1": 0.5, "reasoning": "test"}
        hypothesis = {
            "hypothesis": "새로운 구조적 관계",
            "explanation": "β₁ 차이가 큼",
            "testable_prediction": "유사 쌍에서도 재현",
            "involved_entities": ["Q11348", "Q192439"],
            "confidence": 0.72,
        }
        non_topo_hyp = {"hypothesis": "completely different"}
        comparison = {"same_core_claim": False, "confidence": 0.9}
        repackaging = {"is_repackaging": False, "confidence": 0.2, "original_fact": ""}

        call_count = {"n": 0}

        def mock_run_side_effect(*args, **kwargs):
            responses = [prediction, hypothesis, non_topo_hyp, comparison, repackaging]
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=json.dumps(responses[idx], ensure_ascii=False),
                stderr=""
            )

        mock_claude.side_effect = mock_run_side_effect

        # Mock SPARQL (graph builder + novelty)
        mocker.patch("tecs_h.graph.builder._sparql_query", return_value={
            "results": {"bindings": [
                {
                    "source": {"value": "http://www.wikidata.org/entity/Q11348"},
                    "target": {"value": "http://www.wikidata.org/entity/Q192439"},
                    "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
                }
            ]}
        })
        mocker.patch("tecs_h.novelty.filter._sparql_query", return_value={"results": {"bindings": []}})

        # Mock cross-check verification
        mocker.patch("tecs_h.verify.cross_check._sparql_query", return_value={"results": {"bindings": []}})
        mocker.patch("tecs_h.loop.batch.cross_check", return_value={
            "reproduced": False, "warning": "형제 엔티티 부족", "confidence_adjustment": 0
        })

        # Mock TECS-L engine
        mock_engine_cls = mocker.patch("tecs_h.loop.batch._get_engine")
        engine = mock_engine_cls.return_value
        engine.compute_topology_from_edges.return_value = {
            "beta0": 1, "beta1": 47, "max_persistence_h1": 0.85, "long_h1": []
        }
        engine.compute_hyperbolicity.return_value = {"hierarchy_score": 0.3}

        # Mock evaluator filters (pass everything for e2e)
        mocker.patch("tecs_h.evaluator.pipeline.filter_random", return_value={"status": "pass"})
        mocker.patch("tecs_h.evaluator.pipeline.filter_scale", return_value={"status": "pass"})

        seed_groups = [{"entities": ["Q11348", "Q192439"], "hop": 2}]
        results = run_batch(seed_groups, rounds_per_group=1, results_dir=str(tmp_path))

        assert len(results) >= 1
        result = results[0]
        assert result["id"].startswith("hyp_")
        assert result["hypothesis"] != ""
        assert "topological_basis" in result

    def test_empty_batch_no_crash(self, mocker):
        results = run_batch([], rounds_per_group=5)
        assert results == []
```

- [ ] **Step 2: Add cross_check to batch loop**

In `tecs_h/loop/batch.py`, add import:
```python
from tecs_h.verify.cross_check import cross_check
```

Add after novelty filter in `run_collision_round`:
```python
    # 7. Cross-check (2nd verification)
    cross_result = cross_check(hypothesis, actual)
    if cross_result.get("confidence_adjustment", 0) > 0:
        hypothesis["confidence"] = min(1.0, hypothesis.get("confidence", 0) + cross_result["confidence_adjustment"])
```

Add `cross_check` to return dict:
```python
    return {
        ...
        "cross_check": cross_result,
    }
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/ghost/Dev/test-6 && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tecs_h/loop/batch.py tests/test_e2e.py
git commit -m "feat: integrate cross-check and add end-to-end test"
```

---

### Task 17: Smoke Test with Real Data

**Files:** None (manual verification)

- [ ] **Step 1: Verify TECS-L is installed**

Run: `cd /Users/ghost/dev/test-4/crates/tecs-python && maturin develop`
Expected: Successfully installed tecs_rs

- [ ] **Step 2: Add test-4 Python path**

Run: `export PYTHONPATH="/Users/ghost/dev/test-4/python:$PYTHONPATH"`

- [ ] **Step 3: Run single collision round**

Run: `cd /Users/ghost/Dev/test-6 && tecs-h run --entities Q11348,Q192439 --rounds 1`
Expected: Either "0 hypotheses generated" (no clash) or "1 hypotheses generated" with output saved to results/

- [ ] **Step 4: Check results**

Run: `cd /Users/ghost/Dev/test-6 && tecs-h results`
Expected: Shows any generated hypotheses or "No results"

- [ ] **Step 5: Commit any config adjustments**

```bash
git add -A && git commit -m "chore: finalize Phase 1-4 integration"
```
