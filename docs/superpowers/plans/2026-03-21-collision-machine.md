# Collision Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows PC에서 llama 8B + TECS-L로 초고속 충돌 루프를 돌리고, Mac에서 HTTP로 결과를 받아 필터링하는 분산 시스템 구축

**Architecture:** Windows PC가 FastAPI 서버로 충돌 엔진을 노출. Mac의 TECS-H가 HTTP로 원격 충돌 요청 또는 결과 수집. 충돌 머신은 llama-cpp-python으로 예측/해소를 로컬 처리하고, TECS-L Rust 엔진으로 위상 계산.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, llama-cpp-python, Llama 3.1 8B Q4_K_M, TECS-L Rust engine (tecs_rs), httpx

---

## 시스템 구조

```
[Windows PC — 충돌 머신]                    [Mac — 필터 머신]
┌─────────────────────────┐               ┌─────────────────────────┐
│ FastAPI (포트 8000)      │               │ tecs-h CLI              │
│                          │               │                          │
│ POST /collision          │  ←── HTTP ──  │ 원격 충돌 요청            │
│   llama 8B 예측          │               │                          │
│   TECS-L 위상 계산       │  ──→ JSON ──→ │ Evaluator 3중 필터       │
│   llama 8B 모순 해소     │               │ Novelty Filter           │
│                          │               │ Cross-check              │
│ POST /batch              │               │ Claude CLI 정제 (선택)   │
│   자동 반복 충돌         │               │                          │
│   결과 누적              │               │ 결과 저장                │
│                          │               │                          │
│ GET /results             │  ←── HTTP ──  │ 결과 수집                │
│ GET /status              │               │                          │
│ DELETE /results          │               │                          │
└─────────────────────────┘               └─────────────────────────┘
```

## 충돌 루프 1회당 호출

| 단계 | 처리 | 예상 시간 |
|---|---|---|
| llama 8B 예측 | 로컬 GPU/CPU | 3-10초 |
| Wikidata SPARQL | HTTP | 1-3초 |
| TECS-L 위상 계산 | Rust CPU | <1초 |
| llama 8B 모순 해소 | 로컬 GPU/CPU | 5-15초 |
| **합계** | | **10-30초** |

Claude CLI 없음 → rate limit 없음 → 24시간 무한 반복 가능

---

## File Map

### Windows 측 (collision_machine/)

| File | Responsibility |
|------|---------------|
| `collision_machine/server.py` | FastAPI 서버, 엔드포인트 정의 |
| `collision_machine/llm.py` | llama-cpp-python 래퍼, JSON 파싱 |
| `collision_machine/engine.py` | 충돌 루프 (예측→위상→충돌→해소) |
| `collision_machine/config.py` | 설정 (모델 경로, 포트 등) |
| `collision_machine/requirements.txt` | Python 의존성 |
| `collision_machine/setup.md` | Windows 설치 가이드 |

### Mac 측 (tecs_h에 추가)

| File | Responsibility |
|------|---------------|
| `tecs_h/remote/client.py` | 원격 충돌 머신 HTTP 클라이언트 |
| `tecs_h/cli.py` (수정) | `tecs-h remote` 커맨드 추가 |

---

## Phase 1: Windows 충돌 머신

### Task 1: llama-cpp-python 래퍼

**Files:**
- Create: `collision_machine/llm.py`
- Create: `collision_machine/config.py`

- [ ] **Step 1: Create config.py**

```python
from dataclasses import dataclass

@dataclass
class Config:
    model_path: str = "models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
    n_ctx: int = 4096
    n_gpu_layers: int = -1  # -1 = 전부 GPU, 0 = CPU만
    temperature: float = 0.3
    max_tokens: int = 1024
    server_host: str = "0.0.0.0"
    server_port: int = 8000
```

- [ ] **Step 2: Create llm.py**

```python
"""Local LLM wrapper using llama-cpp-python."""

import json
import re
from llama_cpp import Llama
from config import Config

_llm = None

def get_llm(config: Config | None = None) -> Llama:
    global _llm
    if _llm is None:
        config = config or Config()
        _llm = Llama(
            model_path=config.model_path,
            n_ctx=config.n_ctx,
            n_gpu_layers=config.n_gpu_layers,
            verbose=False,
        )
    return _llm

def extract_json(raw: str) -> dict:
    """Extract JSON dict from LLM output."""
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"```json\s*\n(.*?)\n\s*```", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last > first:
        try:
            parsed = json.loads(raw[first:last + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No JSON dict found: {raw[:200]}")

def llm_call(prompt: str, config: Config | None = None) -> dict:
    """Call local LLM and return parsed JSON dict."""
    config = config or Config()
    llm = get_llm(config)
    suffix = "\n\nRespond with ONLY a JSON object. No markdown, no explanation."
    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt + suffix}],
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    text = response["choices"][0]["message"]["content"]
    return extract_json(text)
```

- [ ] **Step 3: Commit**

```bash
git add collision_machine/
git commit -m "feat: add local LLM wrapper with llama-cpp-python"
```

---

### Task 2: 충돌 엔진 (필터 없는 순수 충돌)

**Files:**
- Create: `collision_machine/engine.py`

- [ ] **Step 1: Create engine.py**

```python
"""Pure collision engine — no filters, maximum speed."""

import json
import uuid
import logging
from datetime import date, datetime

from llm import llm_call
from config import Config

logger = logging.getLogger("collision_machine")

# TECS-L engine (lazy load)
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        from tecs.tecs_rs import RustEngine
        _engine = RustEngine()
    return _engine

# Prompts
PREDICT_PROMPT = """
Predict the topological invariants of a Wikidata math entity subgraph.

Entities: {entities}
BFS hops: {hop}

Predict as JSON:
- beta0: number of connected components (integer)
- beta1: number of 1-dimensional holes/cycles (integer)
- hierarchy_score: hierarchy (0-1, 1=perfect tree)
- max_persistence_h1: max persistence of H1 (0-2)
- reasoning: brief explanation
"""

RESOLVE_PROMPT = """
You predicted these topological invariants for a math entity subgraph:
{prediction}

Actual computed values:
{actual}

Clashes (where you were wrong):
{clashes}

Generate a NEW hypothesis explaining this contradiction.
Do NOT repeat known facts. Propose a novel structural relationship.

JSON response:
- hypothesis: hypothesis statement
- explanation: why this explains the contradiction
- testable_prediction: a concrete prediction to verify this hypothesis
- involved_entities: list of relevant Wikidata QIDs
- confidence: confidence score (0-1)
"""

def detect_clashes(prediction: dict, actual: dict) -> list[dict]:
    """Detect clashes between predicted and actual values."""
    clashes = []
    actual_persistence = actual.get("max_persistence_h1", 0)
    for field in ["beta0", "beta1", "hierarchy_score", "max_persistence_h1"]:
        pred_val = prediction.get(field, 0)
        actual_val = actual.get(field, 0)
        if field == "beta1" and actual_persistence < 0.01:
            continue
        gap = abs(pred_val - actual_val)
        max_val = max(pred_val, actual_val)
        if max_val == 0:
            continue
        ratio = gap / max_val
        if ratio > 0.2:
            clashes.append({
                "field": field,
                "predicted": pred_val,
                "actual": actual_val,
                "gap": gap,
                "strength": "strong" if ratio > 0.5 else "medium",
            })
    return clashes

def run_collision(entities: list[str], edges: list[tuple], n_nodes: int, hop: int = 2) -> dict | None:
    """Run a single collision round. Returns raw result or None."""
    engine = _get_engine()

    # 1. Predict
    prompt = PREDICT_PROMPT.format(entities=", ".join(entities), hop=hop)
    try:
        prediction = llm_call(prompt)
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        return None

    # 2. Compute actual topology
    try:
        topo = engine.compute_topology_from_edges(edges, n_nodes)
        hyper = engine.compute_hyperbolicity(edges, n_nodes)
        actual = {**topo, "hierarchy_score": hyper["hierarchy_score"]}
    except Exception as e:
        logger.error("Topology computation failed: %s", e)
        return None

    # 3. Detect clashes
    clashes = detect_clashes(prediction, actual)
    if not clashes:
        return None

    # 4. Resolve
    resolve_prompt = RESOLVE_PROMPT.format(
        prediction=json.dumps(prediction, indent=2),
        actual=json.dumps(actual, indent=2),
        clashes=json.dumps(clashes, indent=2),
    )
    try:
        hypothesis = llm_call(resolve_prompt)
    except Exception as e:
        logger.error("Resolution failed: %s", e)
        return None

    today = date.today().strftime("%Y%m%d")
    hex_id = uuid.uuid4().hex[:6]

    return {
        "id": f"raw_{today}_{hex_id}",
        "timestamp": datetime.now().isoformat(),
        "entities": entities,
        "prediction": prediction,
        "actual": actual,
        "clashes": clashes,
        "hypothesis": hypothesis,
        "status": "unfiltered",
    }
```

- [ ] **Step 2: Commit**

```bash
git add collision_machine/engine.py
git commit -m "feat: add pure collision engine without filters"
```

---

### Task 3: FastAPI 서버

**Files:**
- Create: `collision_machine/server.py`
- Create: `collision_machine/requirements.txt`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.104
uvicorn>=0.24
llama-cpp-python>=0.3
requests>=2.31
maturin>=1.0
```

- [ ] **Step 2: Create server.py**

```python
"""FastAPI server for collision machine."""

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

from config import Config
from engine import run_collision
from llm import get_llm

logger = logging.getLogger("collision_machine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# In-memory result store
results: list[dict] = []
batch_status = {"running": False, "rounds_done": 0, "rounds_total": 0}

config = Config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load LLM on startup."""
    logger.info("Loading LLM model...")
    get_llm(config)
    logger.info("LLM loaded. Server ready.")
    yield


app = FastAPI(title="TECS-H Collision Machine", lifespan=lifespan)


class CollisionRequest(BaseModel):
    entities: list[str]
    edges: list[tuple[int, int]]
    n_nodes: int
    hop: int = 2


class BatchRequest(BaseModel):
    entities: list[str]
    edges: list[tuple[int, int]]
    n_nodes: int
    hop: int = 2
    rounds: int = 100


@app.post("/collision")
def single_collision(req: CollisionRequest):
    """Run a single collision round."""
    result = run_collision(req.entities, req.edges, req.n_nodes, req.hop)
    if result:
        results.append(result)
        return {"status": "clash_found", "result": result}
    return {"status": "no_clash"}


def _run_batch(entities, edges, n_nodes, hop, rounds):
    """Background batch runner."""
    batch_status["running"] = True
    batch_status["rounds_done"] = 0
    batch_status["rounds_total"] = rounds
    for i in range(rounds):
        try:
            result = run_collision(entities, edges, n_nodes, hop)
            if result:
                results.append(result)
                logger.info("Round %d/%d: hypothesis generated — %s", i+1, rounds, result["id"])
            else:
                logger.info("Round %d/%d: no clash", i+1, rounds)
        except Exception as e:
            logger.error("Round %d/%d failed: %s", i+1, rounds, e)
        batch_status["rounds_done"] = i + 1
    batch_status["running"] = False
    logger.info("Batch complete: %d results total", len(results))


@app.post("/batch")
def start_batch(req: BatchRequest, background_tasks: BackgroundTasks):
    """Start a batch collision loop in background."""
    if batch_status["running"]:
        return {"status": "error", "message": "Batch already running"}
    background_tasks.add_task(_run_batch, req.entities, req.edges, req.n_nodes, req.hop, req.rounds)
    return {"status": "started", "rounds": req.rounds}


@app.get("/status")
def get_status():
    """Get current status."""
    return {
        "batch": batch_status,
        "total_results": len(results),
    }


@app.get("/results")
def get_results(since: int = 0):
    """Get results. Use since=N to get results after index N."""
    return {"results": results[since:], "total": len(results)}


@app.delete("/results")
def clear_results():
    """Clear all results."""
    results.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.server_host, port=config.server_port)
```

- [ ] **Step 3: Commit**

```bash
git add collision_machine/
git commit -m "feat: add FastAPI collision machine server"
```

---

### Task 4: Windows 설치 가이드

**Files:**
- Create: `collision_machine/setup.md`

- [ ] **Step 1: Create setup.md**

```markdown
# Collision Machine — Windows 설치 가이드

## 1. Python 설치
- Python 3.11+ 설치: https://www.python.org/downloads/
- 설치 시 "Add to PATH" 체크

## 2. 프로젝트 복사
```bash
# Mac에서 Windows로 collision_machine/ 폴더 복사
# 또는 git clone
git clone https://github.com/need-singularity/test-6.git
cd test-6/collision_machine
```

## 3. 의존성 설치
```bash
pip install -r requirements.txt
```

## 4. TECS-L Rust 엔진 설치
```bash
# Rust 설치 (없는 경우)
# https://rustup.rs/ 에서 설치

# test-4 클론 및 빌드
git clone https://github.com/need-singularity/test-4.git
cd test-4/crates/tecs-python
pip install maturin
maturin develop
```

## 5. 모델 다운로드
```bash
pip install huggingface-hub
huggingface-cli download bartowski/Meta-Llama-3.1-8B-Instruct-GGUF \
    Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
    --local-dir ./models
```

## 6. 서버 실행
```bash
# PYTHONPATH에 test-4 python 경로 추가
set PYTHONPATH=C:\path\to\test-4\python;%PYTHONPATH%

python server.py
# → http://0.0.0.0:8000 에서 서버 시작
# → Mac에서 http://<Windows-IP>:8000 으로 접속
```

## 7. Windows IP 확인
```bash
ipconfig
# IPv4 주소 확인 (예: 192.168.0.10)
```

## 8. 방화벽 설정
- Windows 방화벽에서 포트 8000 인바운드 허용
- 또는: Windows Defender 방화벽 → 고급 설정 → 인바운드 규칙 → 새 규칙 → 포트 8000
```

- [ ] **Step 2: Commit**

```bash
git add collision_machine/setup.md
git commit -m "docs: add Windows collision machine setup guide"
```

---

## Phase 2: Mac 원격 클라이언트

### Task 5: HTTP 클라이언트

**Files:**
- Create: `tecs_h/remote/__init__.py`
- Create: `tecs_h/remote/client.py`

- [ ] **Step 1: Create remote/client.py**

```python
"""HTTP client for remote collision machine."""

import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://192.168.0.10:8000"


class CollisionMachineClient:
    def __init__(self, base_url: str = DEFAULT_URL):
        self.base_url = base_url.rstrip("/")

    def collision(self, entities: list[str], edges: list[tuple], n_nodes: int, hop: int = 2) -> dict | None:
        """Request a single collision round."""
        resp = requests.post(f"{self.base_url}/collision", json={
            "entities": entities, "edges": edges, "n_nodes": n_nodes, "hop": hop,
        }, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "clash_found":
            return data["result"]
        return None

    def start_batch(self, entities: list[str], edges: list[tuple], n_nodes: int, hop: int = 2, rounds: int = 100) -> dict:
        """Start a batch collision loop on the remote machine."""
        resp = requests.post(f"{self.base_url}/batch", json={
            "entities": entities, "edges": edges, "n_nodes": n_nodes, "hop": hop, "rounds": rounds,
        }, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def status(self) -> dict:
        """Check batch status."""
        resp = requests.get(f"{self.base_url}/status", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def results(self, since: int = 0) -> list[dict]:
        """Fetch results from remote machine."""
        resp = requests.get(f"{self.base_url}/results", params={"since": since}, timeout=30)
        resp.raise_for_status()
        return resp.json()["results"]

    def clear(self) -> None:
        """Clear remote results."""
        requests.delete(f"{self.base_url}/results", timeout=10)
```

- [ ] **Step 2: Commit**

```bash
git add tecs_h/remote/
git commit -m "feat: add remote collision machine HTTP client"
```

---

### Task 6: CLI 원격 커맨드

**Files:**
- Modify: `tecs_h/cli.py`

- [ ] **Step 1: Add remote commands to cli.py**

Add to `tecs_h/cli.py`:
```python
@main.group()
def remote():
    """Remote collision machine commands."""
    pass


@remote.command()
@click.option("--url", default="http://192.168.0.10:8000", help="Collision machine URL")
@click.option("--entities", required=True, help="Comma-separated Wikidata QIDs")
@click.option("--hop", default=2, help="BFS hop depth")
@click.option("--rounds", default=100, help="Number of collision rounds")
def start(url: str, entities: str, hop: int, rounds: int):
    """Start batch collision on remote machine."""
    from tecs_h.remote.client import CollisionMachineClient
    from tecs_h.graph.builder import build_subgraph

    entity_list = [e.strip() for e in entities.split(",")]
    click.echo(f"Building subgraph for {entity_list}...")
    subgraph = build_subgraph(entity_list, hop=hop)
    click.echo(f"Subgraph: {subgraph['n_nodes']} nodes, {len(subgraph['edges'])} edges")

    client = CollisionMachineClient(url)
    result = client.start_batch(entity_list, subgraph["edges"], subgraph["n_nodes"], hop, rounds)
    click.echo(f"Batch started: {result}")


@remote.command()
@click.option("--url", default="http://192.168.0.10:8000", help="Collision machine URL")
def status(url: str):
    """Check remote collision machine status."""
    from tecs_h.remote.client import CollisionMachineClient
    client = CollisionMachineClient(url)
    s = client.status()
    click.echo(f"Batch running: {s['batch']['running']}")
    click.echo(f"Progress: {s['batch']['rounds_done']}/{s['batch']['rounds_total']}")
    click.echo(f"Total results: {s['total_results']}")


@remote.command()
@click.option("--url", default="http://192.168.0.10:8000", help="Collision machine URL")
@click.option("--filter/--no-filter", default=True, help="Apply evaluator + novelty filters")
def fetch(url: str, filter: bool):
    """Fetch and optionally filter results from remote machine."""
    from tecs_h.remote.client import CollisionMachineClient
    from tecs_h.output.formatter import save_result

    client = CollisionMachineClient(url)
    raw_results = client.results()
    click.echo(f"Fetched {len(raw_results)} raw hypotheses")

    if not filter:
        for r in raw_results:
            save_result(r)
        click.echo(f"Saved {len(raw_results)} unfiltered results")
        return

    # Apply filters
    from tecs_h.evaluator.pipeline import evaluate
    from tecs_h.novelty.filter import filter_novelty

    survived = 0
    for r in raw_results:
        hypothesis = r.get("hypothesis", {})
        actual = r.get("actual", {})
        entities = r.get("entities", [])

        eval_result = evaluate(
            hypothesis=hypothesis, actual_topology=actual, entities=entities,
            n_nodes=len(entities), n_edges=0,
        )
        if eval_result["status"] == "rejected":
            continue

        novelty_result = filter_novelty(hypothesis)
        if novelty_result["status"] == "reject":
            continue

        save_result(r)
        survived += 1

    click.echo(f"{survived}/{len(raw_results)} hypotheses survived filtering")
```

- [ ] **Step 2: Commit**

```bash
git add tecs_h/cli.py
git commit -m "feat: add remote collision machine CLI commands"
```

---

## 사용 흐름

```bash
# 1. Windows PC에서 서버 시작
python server.py

# 2. Mac에서 배치 시작 (서브그래프 구축 → 원격 전송)
tecs-h remote start --url http://192.168.0.10:8000 --entities Q11348,Q192439 --rounds 1000

# 3. 진행 상황 확인
tecs-h remote status --url http://192.168.0.10:8000

# 4. 결과 가져와서 필터링
tecs-h remote fetch --url http://192.168.0.10:8000 --filter
```
