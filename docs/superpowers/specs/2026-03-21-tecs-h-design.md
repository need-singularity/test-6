# TECS-H Design Spec

**Topological Emergence Computation System — Hypothesis**

"학습 데이터에 없던 가설" 생산기

## 배경

TECS-L(test-4)은 Wikidata 지식 그래프에서 위상 분석으로 구조적 갭을 탐지하는 1회성 파이프라인이다. TECS-H는 이를 발전시켜, LLM의 예측을 위상 계산으로 **반증(falsification)**하여 학습 데이터에 없던 가설을 생성하는 시스템이다.

### LLM 천장의 정의

- Shannon DPI + Chaitin 불완전성: 고정된 LLM은 파라미터에 없는 정보를 신뢰 가능하게 추가할 수 없다
- 천장을 깨는 공식: **외부 생성기 + 자동 검증기(evaluator) + 반복 루프** (FunSearch, AlphaGeometry, AlphaEvolve의 공통 구조)
- LLM의 올바른 역할: "진실 생성기"가 아니라 "후보 제안기/압축기"

### 핵심 설계 원칙

1. **충돌 생성** — LLM이 먼저 예측 → 위상 계산으로 반증 → 새로운 프레임 강제
2. **쓰레기 제거기** — evaluator는 "의미 판정기"가 아니라 "나쁜 것 제거기"
3. **새로움 필터** — 기존 지식의 재포장/자명한 특수케이스/표현 변환 자동 제거
4. **진화적 반복** — 1회성이 아닌 배치 반복 루프

## 확정된 요구사항

| 항목 | 결정 |
|---|---|
| LLM | Claude CLI (`subprocess`, `-p` 플래그, 비용 0) |
| 도메인 | Wikidata 수학 엔티티 (A+B 통합) |
| 루프 규모 | B: 반자동 배치 (기본), C: 완전 자동 전환 가능 |
| 출력 형식 | JSON + 자연어 |
| 언어 | Python (test-6 독립 프로젝트, test-4의 tecs-python import) |
| 접근법 | Evaluator-First + Collision-First 하이브리드 |

## 프로젝트 구조

```
test-6/
├── tecs_h/
│   ├── collision/        # 충돌 생성 엔진
│   │   ├── predictor.py  # Claude CLI로 예측 요청
│   │   ├── clash.py      # 예측 vs 실제 비교 → 충돌 감지
│   │   └── resolver.py   # Claude CLI로 모순 해소 → 가설 생성
│   ├── evaluator/        # 3중 필터 쓰레기 제거기
│   │   ├── random_baseline.py
│   │   ├── scale_test.py
│   │   └── non_topo_baseline.py
│   ├── novelty/          # 새로움 필터
│   │   └── filter.py     # Wikidata 기존 관계 대조
│   ├── loop/             # 반복 루프 제어
│   │   ├── batch.py      # B모드: 반자동 배치
│   │   └── auto.py       # C모드: 완전 자동 (인터페이스만)
│   ├── graph/            # 서브그래프 구축 (Python 자체 구현)
│   │   └── builder.py    # Wikidata SPARQL → 서브그래프 추출
│   ├── claude_io/        # Claude CLI 인터페이스
│   │   └── client.py     # subprocess 래퍼, JSON 파싱, 재시도
│   ├── verify/           # 2차 검증
│   │   └── cross_check.py # 다른 엔티티 조합으로 패턴 재현 확인
│   ├── output/           # 결과 출력
│   │   └── formatter.py  # JSON + 자연어
│   └── cli.py            # 진입점
├── configs/
│   └── domains.yaml      # 도메인별 수학 엔티티 시드
├── results/              # 생성된 가설 저장
├── logs/                 # 실행 로그
└── pyproject.toml
```

## 모듈 상세 설계

### 0. Claude CLI 인터페이스 (claude_io/)

#### client.py — subprocess 래퍼

모든 Claude CLI 호출의 단일 진입점. JSON 파싱과 에러 처리를 중앙화.

- `claude_call(prompt: str, timeout: int = 120) -> dict`
- 프롬프트 끝에 항상 추가: `"반드시 JSON만 출력해. 코드 블록이나 설명 없이 순수 JSON만."`
- JSON 추출 전략: (1) 전체 stdout을 `json.loads` 시도 → (2) 실패 시 ```json``` 코드 블록 regex 추출 → (3) 실패 시 첫 `{`부터 마지막 `}`까지 추출
- 재시도: 파싱 실패 시 최대 2회 재시도 (프롬프트에 "이전 응답이 JSON이 아니었다" 추가)
- 타임아웃: subprocess 120초, 초과 시 `TimeoutError`
- 에러 처리: 비정상 종료(exit code != 0)는 `ClaudeCliError` 예외

### 0.5. 서브그래프 구축 (graph/)

#### builder.py — Wikidata SPARQL → 서브그래프

TECS-L의 `build_candidate_graph`가 스텁이므로, Python에서 직접 구현.

- `build_subgraph(entities: list[str], hop: int = 2, max_nodes: int = 300) -> SubGraph`
- Wikidata SPARQL endpoint (`https://query.wikidata.org/sparql`)로 BFS 쿼리
- 수학 관련 프로퍼티 우선: P279(subclass), P31(instance), P361(part of), P527(has part), P737(influenced by)
- TECS-L의 `edge_types.yaml` 블랙리스트 적용 (P1343 등 노이즈 제거)
- 반환값: `{"nodes": [...], "edges": [(u, v), ...], "n_nodes": int}` — TECS-L `compute_topology_from_edges`에 바로 입력 가능
- 거리 행렬 계산: `compute_topology_from_edges`는 내부적으로 Floyd-Warshall을 실행하므로 별도 거리 행렬 불필요. `compute_hyperbolicity`에 필요한 거리 행렬은 `networkx.floyd_warshall_numpy()`로 edges에서 생성
- Rate limit: 요청 간 1초 딜레이 (Wikidata 정책 준수)

### 1. 충돌 생성 엔진 (collision/)

#### predictor.py — Claude CLI 예측 요청

- 입력: 시드 엔티티 목록 (예: `["Q11348", "Q192439"]`)
- `claude_io.client.claude_call()`을 통해 호출
- 프롬프트: 엔티티의 서브그래프에 대해 `beta0`, `beta1`, `hierarchy_score`, `reasoning`을 JSON으로 예측하도록 요청
- 출력: 파싱된 예측 딕셔너리

#### clash.py — 충돌 감지

- 입력: 예측값, 실제 위상 계산 결과 (TECS-L의 `compute_topology_from_edges` + `compute_hyperbolicity`)
- 비교 대상: `beta0`, `beta1`, `hierarchy_score`, `max_persistence_h1`
- `max_persistence_h1 < 0.01`인 경우 β₁ 충돌을 무시 (노이즈성 위상 특성)
- 충돌 강도 기준:
  - `max(predicted, actual) == 0`인 경우: 충돌 없음으로 처리 (0/0 방지)
  - `gap / max(predicted, actual) > 0.5` → 강한 충돌 (반드시 해소)
  - `0.2 ~ 0.5` → 중간 충돌 (해소 시도)
  - `< 0.2` → 약한 충돌 (스킵)
- 충돌 없으면 빈 리스트 반환 → 해당 라운드 스킵

#### resolver.py — 모순 해소 → 가설 생성

- 입력: 예측값, 실제값, 충돌 목록
- `claude_io.client.claude_call()`을 통해 호출
- Claude가 "왜 틀렸는지" 설명하는 과정에서 가설 생성
- 출력 JSON: `hypothesis`, `explanation`, `testable_prediction`, `involved_entities`, `confidence` (0~1, 모순 해소의 확신도)

### 2. Evaluator 3중 필터 (evaluator/)

"좋은 것 판정"이 아니라 "나쁜 것 제거" 설계. 순서는 비용 순(저→고).

#### 필터 1: random_baseline.py — 랜덤 대조

- Erdos-Renyi 모델로 같은 (node_count, edge_count)의 랜덤 그래프 10개 생성
- 랜덤 그래프에서도 동일 패턴이 70% 이상 재현 → REJECT
- 비용: TECS-L 계산만 (Claude 호출 없음)

#### 필터 2: scale_test.py — 크기 확장

- 서브그래프 hop을 2→3→4로 확장 (max_nodes 캡 적용, 캡에 도달한 hop은 비교에서 제외)
- 패턴 유지율 50% 미만 → REJECT (국소적 아티팩트)
- 비용: TECS-L 계산만 (Claude 호출 없음)

#### 필터 3: non_topo_baseline.py — 비위상 대조

- 단순 그래프 통계(degree, clustering coefficient, PageRank)만으로 같은 결론 도달 가능한지
- Claude CLI에 위상 정보 없이 그래프 통계만 보여주고 가설 생성 요청
- 유사도 측정: Claude CLI에 두 가설을 제시하고 "같은 핵심 주장인가?" 판단 요청 (yes/no + confidence)
- confidence 0.8 이상으로 "yes" → REJECT
- 비용: Claude 호출 2회 (가설 생성 1회 + 비교 1회, 가장 비싼 필터)
- 순환 의존 주의: Claude가 두 자기 출력을 비교하므로 체계적 편향 가능. 완화: 비교 프롬프트에 "표면적 표현이 아닌 논리적 핵심 주장만 비교하라" 명시

### 3. Novelty Filter (novelty/)

#### filter.py — 3단계 새로움 검증

1. **직접 관계 중복**: Wikidata API로 엔티티 쌍 관계 조회 → 이미 등록된 관계면 REJECT
2. **자명한 특수케이스**: P279 체인(상위 개념)에서 자명하게 도출되는 관계면 REJECT
3. **표현 변환**: Claude CLI에 재포장 여부 판단 요청 → confidence 0.7 이상이면 REJECT

순환 의존 주의 (필터 3 + evaluator 필터 3 공통): Claude가 자기 출력을 판단하는 한계가 있음. Claude가 아는 것 중 중복만 제거하는 것이 목적. 진짜 새로운 것은 Claude도 모르니까 통과 — 이것이 정상 동작. 향후 외부 수학 데이터베이스(MathSciNet, zbMATH) 연동으로 보완 가능.

### 4. 반복 루프 (loop/)

#### batch.py — B모드 (반자동 배치)

- 입력: 시드 그룹 목록, 그룹당 반복 횟수 (기본 5)
- 각 그룹 × 각 라운드에서 충돌 루프 실행
- 파이프라인: 예측 → 위상 계산 → 충돌 감지 → 모순 해소 → Evaluator → Novelty → 2차 검증
- 충돌 없거나 필터 탈락 시 해당 라운드 스킵
- 2차 검증: `verify/cross_check.py` 호출
- 결과를 `results/YYYY-MM-DD/`에 자동 저장
- 로그를 `logs/YYYY-MM-DD.log`에 기록 (각 라운드의 예측/실제/충돌/필터 결과)
- 에러 정책: 개별 라운드 실패 시 로그에 기록하고 다음 라운드 계속 (배치 전체 중단 안 함)

#### auto.py — C모드 (인터페이스 정의만)

- `AutoLoop` 클래스: `max_rounds`, `rate_limit_per_min`, `evolution` 설정
- `run()`: B모드 감싸서 자동 반복 (NotImplementedError)
- `evolve()`: 이전 결과에서 유망한 가설을 변이시켜 다음 시드 생성 (NotImplementedError)
- C모드 전환 시 구현

### 5. 2차 검증 (verify/)

#### cross_check.py — 패턴 재현 확인

- 가설에 포함된 엔티티와 **유사하지만 다른** 엔티티 조합으로 같은 위상 패턴이 재현되는지 확인
- 유사 엔티티 선정: Wikidata P279(subclass) 또는 P31(instance of) 관계로 형제/사촌 엔티티 탐색
- 최소 2개 다른 조합에서 테스트
- 패턴 재현율 50% 이상 → 가설 강화 (confidence 보정)
- 패턴 재현율 0% → 가설에 "단일 사례" 경고 태그 부착 (reject는 아님)

### 6. 출력 (output/)

#### formatter.py — JSON + 자연어

출력 스키마:
```json
{
  "id": "hyp_YYYYMMDD_XXXXXX",  // 6자리 hex (uuid4 앞 6자리)
  "hypothesis": "가설 서술",
  "explanation": "모순 해소 과정 설명",
  "confidence": 0.72,
  "involved_entities": ["Q11348", "Q192439"],
  "topological_basis": {
    "predicted": {"beta0": 1, "beta1": 3},
    "actual": {"beta0": 1, "beta1": 47},
    "clash_type": "beta_1_mismatch",
    "clash_gap": 44
  },
  "evaluation": {
    "random_baseline": "pass",
    "scale_test": "pass",
    "non_topo_baseline": "pass"
  },
  "novelty": {
    "wikidata_duplicate": false,
    "trivial_specialization": false,
    "repackaging": false
  },
  "testable_prediction": "검증 가능한 예측",
  "natural_language": "사람이 읽을 수 있는 전체 요약..."
}
```

## 데이터 흐름

```
반복 루프 (batch/auto)
│
├─ Claude CLI 예측 (predictor)
├─ TECS-L 위상 계산 (test-4 import)
├─ 충돌 감지 (clash)
│   └─ 충돌 없으면 → 스킵
├─ Claude CLI 모순 해소 (resolver) → 가설 생성
├─ Evaluator 3중 필터
│   ├─ 랜덤 baseline (저비용)
│   ├─ 크기 확장 (중비용)
│   └─ 비위상 baseline (고비용, Claude 호출)
├─ Novelty Filter
│   ├─ Wikidata 중복 체크
│   ├─ 자명한 특수케이스 체크
│   └─ 표현 변환 체크 (Claude 호출)
├─ 2차 검증: 다른 엔티티 조합으로 위상 계산
└─ 결과 저장 (JSON + 자연어)
```

## 충돌 루프 1회당 Claude CLI 호출 횟수

| 단계 | 호출 수 | 조건 |
|---|---|---|
| 예측 | 1회 | 항상 |
| 모순 해소 | 1회 | 충돌 있을 때만 |
| 비위상 baseline (가설 생성) | 1회 | Evaluator 필터 1,2 통과 시 |
| 비위상 baseline (비교 판정) | 1회 | 위 가설 생성 후 |
| 표현 변환 체크 | 1회 | Evaluator 통과 시 |
| **최대** | **5회** | |
| **최소** (충돌 없음) | **1회** | |

B모드 배치 20회 = Claude CLI 호출 20~100회.

## TECS-L 의존성

test-4의 `tecs_rs` 패키지를 import. 설치: `cd /Users/ghost/dev/test-4/crates/tecs-python && maturin develop`

사용하는 API:
- `RustEngine.compute_topology_from_edges(edges, n_nodes)` → `{beta0, beta1, long_h1, max_persistence_h1}`
- `RustEngine.compute_hyperbolicity(distance_matrix)` → `{hierarchy_score}`

Python 모듈 (test-4의 `python/tecs/`를 sys.path에 추가):
- `EmergenceDetector.score()` — 6:3:1 emergence 점수. 배치 결과 랭킹에 사용: 가설 목록을 emergence score로 정렬하여 가장 유망한 가설 우선 표시

사용하지 않는 것:
- `RustEngine.build_candidate_graph()` — 스텁이므로 사용 안 함. `graph/builder.py`가 대체
- `WikidataIngestor` — PyO3 미노출. `graph/builder.py`가 SPARQL로 직접 처리

## configs/domains.yaml 스키마

```yaml
domains:
  topology_basics:
    description: "위상수학 기본 개념 간 관계"
    seed_groups:
      - entities: ["Q11348", "Q192439"]  # Betti number, Euler characteristic
        hop: 2
      - entities: ["Q1753656", "Q1322614"]  # Persistent homology, Simplicial complex
        hop: 2
  number_theory:
    description: "수론 핵심 추측"
    seed_groups:
      - entities: ["Q131752", "Q200227"]  # Prime number, Riemann hypothesis
        hop: 2
```

## CLI 인터페이스

```bash
# 단일 시드 그룹 실행
tecs-h run --entities Q11348,Q192439 --rounds 5

# 도메인 전체 배치 실행
tecs-h batch --domain topology_basics --rounds-per-group 5

# 결과 조회
tecs-h results --date 2026-03-21

# C모드 (미래)
tecs-h auto --domain topology_basics --max-rounds 1000
```

## 에러 처리 정책

| 에러 유형 | 처리 |
|---|---|
| Claude CLI 타임아웃 (120초) | 해당 라운드 스킵, 로그 기록 |
| Claude CLI JSON 파싱 실패 (재시도 2회 후) | 해당 라운드 스킵, 로그 기록 |
| Claude CLI 비정상 종료 | 해당 라운드 스킵, 로그 기록 |
| Wikidata SPARQL 실패 | 해당 시드 그룹 스킵, 로그 기록 |
| TECS-L 계산 실패 (빈 그래프 등) | 해당 라운드 스킵, 로그 기록 |
| 전체 시드 그룹 실패 | 다음 그룹으로 계속, 배치 종료 시 실패 요약 출력 |

원칙: **개별 실패가 배치 전체를 중단시키지 않는다.**

## 개발 순서 (하이브리드 접근법)

1. **Phase 1**: `claude_io/client.py` + `graph/builder.py` + 충돌 루프 MVP + 간단 evaluator → 첫 결과 확인
2. **Phase 2**: 결과를 보면서 evaluator 3중 필터 강화
3. **Phase 3**: Novelty filter 추가
4. **Phase 4**: 배치 자동화 + C모드 전환 인터페이스 + 2차 검증
