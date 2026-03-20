# TECS-H: Topological Emergence Computation System — Hypothesis

**"학습 데이터에 없던 가설" 생산기**

LLM의 예측을 위상 계산으로 **반증(falsification)**하여 학습 데이터에 없던 가설을 생성하는 시스템.

## 핵심 아이디어: 충돌 생성 (Collision Generation)

1. **Claude가 먼저 예측한다** — "이 그래프의 β₁은 3일 것"
2. **위상 계산기가 실제 값을 계산한다** — 실제 β₁ = 47
3. **충돌이 발생한다** — Claude의 기존 패턴 매칭이 틀렸음이 증명됨
4. **모순 해소를 강제한다** — "왜 틀렸는지 설명해봐" → 학습 데이터에 없던 가설 탄생

단순히 새 숫자를 보여주면 LLM이 기존 패턴으로 "해석"만 하지만, 예측을 먼저 시키고 틀리게 만들면 기존 패턴이 작동하지 않음을 증명당하므로 새로운 프레임이 필요해집니다.

## 아키텍처

```
Claude CLI (예측기)
    ↕ 충돌 루프
TECS-L (위상 계산기) ←→ Wikidata (수학 엔티티 그래프)
    ↓
Evaluator 3중 필터 (쓰레기 제거기)
  ├─ 랜덤 baseline — 랜덤 그래프에서도 같은 패턴? → 제거
  ├─ 크기 확장 — 서브그래프 키우면 패턴 사라짐? → 제거
  └─ 비위상 baseline — degree/clustering만으로 같은 결론? → 제거
    ↓
Novelty Filter (새로움 필터)
  ├─ Wikidata 기존 관계 중복 체크
  ├─ 자명한 특수케이스 체크 (P279 체인)
  └─ 표현 변환 체크 (기존 사실 재포장?)
    ↓
2차 검증 — 형제 엔티티에서 패턴 재현 확인
    ↓
살아남은 가설 (JSON + 자연어)
```

## 설치

```bash
# 1. TECS-H 설치
cd test-6
pip install -e ".[dev]"

# 2. TECS-L Rust 엔진 설치 (필수)
cd /path/to/test-4/crates/tecs-python
maturin develop

# 3. TECS-L Python 경로 추가
export PYTHONPATH="/path/to/test-4/python:$PYTHONPATH"
```

## 사용법

```bash
# 단일 시드 그룹 실행
tecs-h run --entities Q11348,Q192439 --rounds 5

# 도메인 전체 배치 실행
tecs-h batch --domain topology_basics --rounds-per-group 5

# 결과 조회
tecs-h results --date 2026-03-21
```

## 출력 예시

```json
{
  "id": "hyp_20260321_a1b2c3",
  "hypothesis": "Betti number와 Euler characteristic 사이에 문서화되지 않은 중간 매개 경로가 다수 존재",
  "confidence": 0.72,
  "topological_basis": {
    "predicted": {"beta0": 1, "beta1": 3},
    "actual": {"beta0": 1, "beta1": 47},
    "clash_type": "beta1_mismatch",
    "clash_gap": 44
  },
  "evaluation": {
    "random_baseline": "pass",
    "scale_test": "pass",
    "non_topo_baseline": "pass"
  }
}
```

## 프로젝트 구조

```
tecs_h/
├── claude_io/client.py       # Claude CLI 래퍼 (JSON 파싱, 재시도)
├── graph/builder.py           # Wikidata SPARQL 서브그래프 구축
├── collision/
│   ├── predictor.py           # LLM 예측 요청
│   ├── clash.py               # 예측 vs 실제 충돌 감지
│   └── resolver.py            # 모순 해소 → 가설 생성
├── evaluator/
│   ├── random_baseline.py     # 필터 1: 랜덤 대조
│   ├── scale_test.py          # 필터 2: 크기 확장
│   ├── non_topo_baseline.py   # 필터 3: 비위상 대조
│   └── pipeline.py            # 3중 필터 파이프라인
├── novelty/filter.py          # 새로움 필터
├── verify/cross_check.py      # 2차 검증 (형제 엔티티)
├── output/formatter.py        # JSON + 자연어 출력
├── loop/
│   ├── batch.py               # B모드: 반자동 배치
│   └── auto.py                # C모드: 완전 자동 (스텁)
└── cli.py                     # CLI 진입점
```

## 이론적 배경

- **Shannon DPI + Chaitin 불완전성**: 고정된 LLM은 파라미터에 없는 정보를 신뢰 가능하게 추가할 수 없다
- **천장을 깨는 공식**: 외부 생성기 + 자동 검증기 + 반복 루프 (FunSearch, AlphaGeometry, AlphaEvolve의 공통 구조)
- **충돌 생성 전략**: 단순히 새 숫자를 보여주는 것이 아니라, LLM의 예측을 의도적으로 반증하여 기존 패턴 매칭이 불가능한 출력을 유도

## 의존성

- [TECS-L](https://github.com/need-singularity/test-4) — Rust 기반 위상 계산 엔진
- Claude CLI — LLM 예측 및 모순 해소
- Wikidata SPARQL — 수학 엔티티 지식 그래프

## 테스트

```bash
pytest tests/ -v
```

## 라이선스

MIT
