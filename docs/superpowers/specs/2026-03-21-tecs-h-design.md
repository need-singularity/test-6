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
│   ├── output/           # 결과 출력
│   │   └── formatter.py  # JSON + 자연어
│   └── cli.py            # 진입점
├── configs/
│   └── domains.yaml      # 도메인별 수학 엔티티 시드
├── results/              # 생성된 가설 저장
└── pyproject.toml
```

## 모듈 상세 설계

### 1. 충돌 생성 엔진 (collision/)

#### predictor.py — Claude CLI 예측 요청

- 입력: 시드 엔티티 목록 (예: `["Q11348", "Q192439"]`)
- Claude CLI에 `-p` 플래그로 프롬프트 전송
- 프롬프트: 엔티티의 서브그래프에 대해 `beta_0`, `beta_1`, `hierarchy_score`, `reasoning`을 JSON으로 예측하도록 요청
- 출력: 파싱된 예측 딕셔너리

#### clash.py — 충돌 감지

- 입력: 예측값, 실제 위상 계산 결과
- 비교 대상: `beta_0`, `beta_1`, `hierarchy_score`
- 충돌 강도 기준:
  - `gap / max(predicted, actual) > 0.5` → 강한 충돌 (반드시 해소)
  - `0.2 ~ 0.5` → 중간 충돌 (해소 시도)
  - `< 0.2` → 약한 충돌 (스킵)
- 충돌 없으면 빈 리스트 반환 → 해당 라운드 스킵

#### resolver.py — 모순 해소 → 가설 생성

- 입력: 예측값, 실제값, 충돌 목록
- Claude CLI에 모순 해소 프롬프트 전송
- Claude가 "왜 틀렸는지" 설명하는 과정에서 가설 생성
- 출력 JSON: `hypothesis`, `explanation`, `testable_prediction`, `involved_entities`

### 2. Evaluator 3중 필터 (evaluator/)

"좋은 것 판정"이 아니라 "나쁜 것 제거" 설계. 순서는 비용 순(저→고).

#### 필터 1: random_baseline.py — 랜덤 대조

- 같은 크기의 랜덤 그래프 10개 생성
- 랜덤 그래프에서도 동일 패턴이 70% 이상 재현 → REJECT
- 비용: TECS-L 계산만 (Claude 호출 없음)

#### 필터 2: scale_test.py — 크기 확장

- 서브그래프 hop을 2→3→4로 확장
- 패턴 유지율 50% 미만 → REJECT (국소적 아티팩트)
- 비용: TECS-L 계산만 (Claude 호출 없음)

#### 필터 3: non_topo_baseline.py — 비위상 대조

- 단순 그래프 통계(degree, clustering coefficient, PageRank)만으로 같은 결론 도달 가능한지
- Claude CLI에 위상 정보 없이 그래프 통계만 보여주고 가설 생성 요청
- 유사도 80% 이상 → REJECT
- 비용: Claude 호출 1회 (가장 비싼 필터)

### 3. Novelty Filter (novelty/)

#### filter.py — 3단계 새로움 검증

1. **직접 관계 중복**: Wikidata API로 엔티티 쌍 관계 조회 → 이미 등록된 관계면 REJECT
2. **자명한 특수케이스**: P279 체인(상위 개념)에서 자명하게 도출되는 관계면 REJECT
3. **표현 변환**: Claude CLI에 재포장 여부 판단 요청 → confidence 0.7 이상이면 REJECT

표현 변환 체크의 순환 의존 주의: Claude가 아는 것 중 중복만 제거하는 것이 목적. 진짜 새로운 것은 Claude도 모르니까 통과 — 이것이 정상 동작.

### 4. 반복 루프 (loop/)

#### batch.py — B모드 (반자동 배치)

- 입력: 시드 그룹 목록, 그룹당 반복 횟수 (기본 5)
- 각 그룹 × 각 라운드에서 충돌 루프 실행
- 파이프라인: 예측 → 위상 계산 → 충돌 감지 → 모순 해소 → Evaluator → Novelty → 2차 검증
- 충돌 없거나 필터 탈락 시 해당 라운드 스킵
- 2차 검증: 다른 엔티티 조합으로 패턴 재현 확인
- 결과를 `results/YYYY-MM-DD/`에 자동 저장

#### auto.py — C모드 (인터페이스 정의만)

- `AutoLoop` 클래스: `max_rounds`, `rate_limit_per_min`, `evolution` 설정
- `run()`: B모드 감싸서 자동 반복 (NotImplementedError)
- `evolve()`: 이전 결과에서 유망한 가설을 변이시켜 다음 시드 생성 (NotImplementedError)
- C모드 전환 시 구현

### 5. 출력 (output/)

#### formatter.py — JSON + 자연어

출력 스키마:
```json
{
  "id": "hyp_YYYYMMDD_NNN",
  "hypothesis": "가설 서술",
  "explanation": "모순 해소 과정 설명",
  "confidence": 0.72,
  "involved_entities": ["Q11348", "Q192439"],
  "topological_basis": {
    "predicted": {"beta_0": 1, "beta_1": 3},
    "actual": {"beta_0": 1, "beta_1": 47},
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
| 비위상 baseline | 1회 | Evaluator 필터 1,2 통과 시 |
| 표현 변환 체크 | 1회 | Evaluator 통과 시 |
| **최대** | **4회** | |
| **최소** (충돌 없음) | **1회** | |

B모드 배치 20회 = Claude CLI 호출 20~80회.

## TECS-L 의존성

test-4의 다음 기능을 import하여 사용:
- `RustEngine.compute_topology_from_edges()` — 위상 계산
- `RustEngine.compute_hyperbolicity()` — δ-hyperbolicity
- `RustEngine.build_candidate_graph()` — 서브그래프 추출
- `WikidataIngestor` — 데이터 인제스트
- `EmergenceDetector.score()` — 6:3:1 emergence 점수

## 개발 순서 (하이브리드 접근법)

1. **Phase 1**: 충돌 루프 MVP + 간단 evaluator → 첫 결과 확인
2. **Phase 2**: 결과를 보면서 evaluator 3중 필터 강화
3. **Phase 3**: Novelty filter 추가
4. **Phase 4**: 배치 자동화 + C모드 전환 인터페이스
