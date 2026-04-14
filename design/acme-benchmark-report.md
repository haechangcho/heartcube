# ACME Insurance NL2SQL Benchmark Report
# Cube Semantic Layer vs Raw DDL SQL

**Date**: 2026-04-14  
**Branch**: `heartcube-1.6.25`  
**Model**: GPT-4o (temperature=0.3, 5 iterations × 11 questions = 55 runs)

---

## 1. 목표

[dbt Labs의 Semantic Layer LLM Benchmarking](https://github.com/dbt-labs/semantic-layer-llm-benchmarking) 실험을 **Cube Semantic Layer** 환경으로 재현하고, Cube SL 기반 NL2SQL과 Raw DDL 기반 NL2SQL의 정확도를 비교한다.

| 트랙 | 컨텍스트 | 출력 형식 | 실행 엔드포인트 |
|---|---|---|---|
| **Cube SL** | `/meta` view member name+description | Cube REST API JSON | `POST /cubejs-api/v1/load` |
| **DDL SQL** | 실제 PostgreSQL DDL (82줄) | raw SQL | PostgreSQL 직접 실행 |

---

## 2. 환경

```
[Local: /Users/hc.cho/Workspace/idk/6.0/heartcube]
  └── ssh dev_mcp
        ├── ~/heartcube/              ← Cube 프로젝트 (git)
        │   ├── model/cubes/          ← acme_* cubes (public: false)
        │   ├── model/views/          ← acme_ops view (public: true)
        │   ├── acme_questions.md     ← Cube SL gold queries (11개)
        │   ├── acme_sql_questions.md ← DDL SQL gold queries (11개)
        │   ├── acme_benchmark_pipeline.py
        │   └── acme_ddl_benchmark_pipeline.py
        │
        ├── Docker: heartcube container
        │   └── Cube server (172.20.0.3:4000)
        │
        └── PostgreSQL (20.0.1.10:5432)
            └── oda_benchmark.acme_* (13개 테이블)
```

---

## 3. 데이터 모델

### 3-1. 참조: omg_semantics (dbt SL)

`/Users/hc.cho/Projects/semantic-layer-llm-benchmarking/models/omg_semantics/` — dbt SL 원본 시맨틱 모델 (13개 yaml).

### 3-2. Cube 모델 구성

omg_semantics와 1:1로 대응하도록 구성. 모든 cube는 `public: false`로 설정하고 `acme_ops` view를 단일 퍼블릭 서페이스로 노출.

| omg_semantics | Cube cube | acme_ops 노출 |
|---|---|---|
| `claim.yaml` | `acme_claim` | `claim_count`, `avg_days_to_settle`, `company_claim_number`, 날짜 dimensions |
| `claim_amount.yaml` | `acme_claim_amount` | `total_claim_amount`, `loss_payment_amount`, `loss_reserve_amount`, `total_loss_amount` |
| `loss_payment.yaml` | `acme_loss_payment` | `has_loss_payment` (flag) |
| `loss_reserve.yaml` | `acme_loss_reserve` | `has_loss_reserve` (flag) |
| `policy.yaml` | `acme_policy` | `policy_number`, `status_code`, `policy_count` |
| `policy_amount.yaml` | `acme_policy_amount` | `total_policy_amount` |
| `premium.yaml` | `acme_premium` | `has_premium` (flag) |
| `agreement_party_role.yaml` | `acme_agreement_party_role` | `party_identifier`, `party_role_code`, `policy_count_by_agent` |
| `catastrophe.yaml` | `acme_catastrophe` | `catastrophe_name`, `catastrophe_type_code` |
| `claim_coverage.yaml` | `acme_claim_coverage` | (join bridge) |
| `policy_coverage_detail.yaml` | `acme_policy_coverage_detail` | (join bridge) |

### 3-2. 주요 설계 결정

**Cross-cube SQL 제한 우회**  
Cube는 measure의 `sql` 필드에서 다른 cube 테이블을 직접 참조할 수 없다. `loss_payment_amount` 같은 필터 기반 measure는 `filters: EXISTS (subquery)` 패턴으로 구현.

```yaml
# acme_claim_amount.yml
- name: loss_payment_amount
  sql: claim_amount
  type: sum
  filters:
    - sql: "EXISTS (SELECT 1 FROM oda_benchmark.acme_loss_payment lp
            WHERE lp.claim_amount_identifier = {CUBE}.claim_amount_identifier)"
```

**omg_semantics flag 패턴 재현**  
dbt SL의 `has_*` dimension (`expr: "1"`)을 Cube의 `sql: "1"` dimension으로 동일하게 구현.

```yaml
# acme_premium.yml
- name: has_premium
  sql: "1"
  type: string
  description: "Filter on this to determine if row represents a premium.
                Filter should evaluate to 'has_premium = 1' if a premium and not if not a premium"
```

**Description 상속**  
Cube view member에 description을 명시하지 않아도 `/meta` API가 하위 cube member의 description을 자동 상속. 모든 description은 omg_semantics 원문 그대로 사용.

---

## 4. 워크플로우

### 4-1. 인프라 구성

1. PostgreSQL에 `oda_benchmark` 스키마 생성 및 13개 ACME 테이블 CSV 로드 (`acme_load_data.py`)
2. Cube Docker 컨테이너 실행, `heartcube` 프로젝트 마운트
3. `model/cubes/acme_*.yml` 작성 — omg_semantics 기준 1:1 대응
4. `model/views/acme_ops.yml` 작성 — 단일 퍼블릭 서페이스
5. `/meta` 응답으로 전체 14개 cube 컴파일 확인

### 4-2. Gold Query 작성

**Cube SL (`acme_questions.md`)**: 11개 영어 질문 + Cube REST API JSON gold query  
**DDL SQL (`acme_sql_questions.md`)**: 동일 11개 질문 + PostgreSQL raw SQL gold query  
Gold SQL은 dev_mcp PostgreSQL에서 사전 실행 검증 후 확정.

### 4-3. 파이프라인 구성

**공통 흐름:**
```
질문 → GPT-4o → 생성 쿼리
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  생성 쿼리 실행            gold 쿼리 실행
        │                       │
        └───────────┬───────────┘
                    ▼
             result_f1 계산
        (fuzzy column match + DataFrame 비교)
```

**Cube SL 파이프라인 (`acme_benchmark_pipeline.py`)**:
- Schema context: `/meta`에서 `acme_ops` view만 필터링, name+description 포맷
- 프롬프트: system + 3개 few-shot + schema context + 질문
- 생성: Cube JSON → `POST /cubejs-api/v1/load` 실행
- 평가: dim_f1 / msr_f1 / result_f1

**DDL SQL 파이프라인 (`acme_ddl_benchmark_pipeline.py`)**:
- Schema context: 실제 PostgreSQL DDL 82줄 (acme_* 테이블 11개)
- 프롬프트: system + 3개 few-shot + DDL + 질문
- 생성: raw SQL → psycopg2 직접 실행
- 평가: result_f1 (fuzzy column match)

---

## 5. 결과

### 5-1. 전체 비교

| 지표 | Cube SL | DDL SQL | 차이 |
|---|---|---|---|
| **JSON/SQL 파싱 성공** | 100% | 100% | = |
| **실행 성공** | **100%** | 92.7% | +7.3%p |
| **결과 일치 (전체)** | **90.9%** (50/55) | 67.3% (37/55) | **+23.6%p** |

### 5-2. 카테고리별

| 카테고리 | Cube SL result_f1 | DDL SQL result_f1 | 차이 |
|---|---|---|---|
| **HQLS** (단순 6문항) | **1.000** | 0.733 | +26.7%p |
| **HQHS** (복합 5문항) | **0.800** | 0.600 | +20.0%p |

### 5-3. 문항별 결과

| # | 질문 (요약) | Cube SL | DDL SQL |
|---|---|---|---|
| Q1 | How many claims? | ✅ | ✅ |
| Q2 | How many policies? | ✅ | ✅ |
| Q3 | Claims by policy number | ✅ | ❌ (5/5 실패) |
| Q4 | Policies sold by agent id | ✅ | ✅ |
| Q5 | Total premiums by policy number | ✅ | ✅ |
| Q6 | Avg days to settle by policy number | ✅ | ❌ (4/5 실패) |
| Q7 | Total loss amount by claim number | ✅ | ✅ |
| Q8 | Total premiums by policy holder | ✅ | ✅ |
| Q9 | Total premiums by policy holder+policy number | ❌ (5/5 실패) | ❌ (5/5 실패) |
| Q10 | Policy count by policy holder | ✅ | ✅ |
| Q11 | Average policy size | ✅ | ❌ (5/5 실패) |

### 5-4. 실패 분석

**Q9 (양쪽 공통 실패)**  
"by policy holder by policy number" — 두 dimension을 동시에 groupby 해야 하는 질문.  
- Cube SL: `party_identifier` dimension 누락 (`dim_f1=0.67`)  
- DDL SQL: 동일 패턴으로 실패

**Q3, Q6 (DDL SQL만 실패)**  
Policy number를 가져오려면 `acme_claim → acme_claim_coverage → acme_policy_coverage_detail → acme_policy` 3단계 JOIN이 필요.  
Cube SL에서는 `acme_ops` view가 이 JOIN 경로를 이미 추상화해 노출하므로 LLM이 `acme_ops.policy_number`만 쓰면 됨.  
DDL SQL에서는 LLM이 JOIN 경로를 직접 추론해야 하므로 실패.

**Q11 (DDL SQL만 실패)**  
gold는 `total_policy_amount`, `number_of_policies` 두 컬럼 반환.  
LLM이 "average = total / count"로 직접 계산해 단일 값(avg_policy_size)을 반환 → 컬럼 구조 불일치.  
Cube SL에서는 두 measure를 각각 요청하는 것이 자연스러워 정상 통과.

---

## 6. 결론

### Cube SL의 강점

1. **JOIN 추상화**: 3단계 JOIN이 필요한 `policy_number` 같은 dimension도 `acme_ops.policy_number` 단일 참조로 해결 — LLM이 스키마 구조를 몰라도 됨
2. **실행 안정성**: Cube schema validation으로 잘못된 member 참조 시 실행 전에 에러 → 실행 성공률 100%
3. **측정 정의 명확성**: `has_premium = 1` 같은 필터 조건이 measure 레벨에 캡슐화 — LLM이 비즈니스 로직을 직접 알 필요 없음

### DDL SQL의 한계

1. **복잡한 JOIN 추론 필요**: 중간 bridge 테이블(claim_coverage, policy_coverage_detail) 경로를 LLM이 직접 조립해야 함
2. **실행 오류 발생**: 잘못된 테이블명/컬럼명이 실행 시점에야 발견 (7.3% 실패)
3. **출력 형식 불일치**: 같은 의미라도 컬럼명·집계 방식이 gold와 달라질 수 있음

### dbt SL 원본과의 차이점

| 항목 | dbt SL 원본 | 이 실험 |
|---|---|---|
| 시맨틱 모델 | omg_semantics YAML | acme_* cubes + acme_ops view (1:1 대응) |
| 쿼리 형식 | SQL-like string | JSON (SL) / raw SQL (DDL) |
| Gold 기준 | RDF 온톨로지 → SPARQL | 수작업 gold query |
| LLM 모델 | GPT-4 | GPT-4o |
| 평가 방식 | 엄격한 DataFrame.equals() | Soft Result F1 (부분 점수 허용) |
| SQL track | 병렬 실행 | 별도 파이프라인으로 순차 비교 |

> Soft F1 기준 Cube SL 90.9% vs DDL SQL 67.3%.  
> 엄격한 exact match 기준(result_f1 == 1.0)으로도 동일한 수치.

---

## 7. 파일 목록

| 파일 | 설명 |
|---|---|
| `model/cubes/acme_*.yml` | Cube cube 모델 (omg_semantics 1:1 대응) |
| `model/views/acme_ops.yml` | 단일 퍼블릭 서페이스 view |
| `acme_questions.md` | Cube SL gold queries (11개) |
| `acme_sql_questions.md` | DDL SQL gold queries (11개) |
| `acme_benchmark_pipeline.py` | Cube SL 벤치마크 파이프라인 |
| `acme_ddl_benchmark_pipeline.py` | DDL SQL 벤치마크 파이프라인 |
| `acme_benchmark_results.csv` | Cube SL 결과 (55행) |
| `acme_ddl_benchmark_results.csv` | DDL SQL 결과 (55행) |
| `design/benchmark-plan.md` | 벤치마크 설계 계획 |
| `design/description-sync-design.md` | View description 상속 설계 |

---

## 8. 향후 과제

| 항목 | 내용 |
|---|---|
| Q9 gold 재검토 | 두 dimension 동시 요구 질문 — few-shot 보강 또는 질문 문구 수정 |
| Q3/Q6 (DDL) 개선 | JOIN 경로 힌트를 DDL 주석으로 추가 |
| Q11 (DDL) gold 수정 | avg_policy_size 단일 값으로 gold 변경 검토 |
| 실험 재현 | dbt SL 원본 GPT-4 결과와 직접 수치 비교 |
