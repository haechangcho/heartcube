# Cube 기반 LLM 자연어 쿼리 평가 계획

> 기존 dbt Semantic Layer 벤치마크(`hex_notebook/`)의 방법론을 `dev_mcp` 서버의 Cube 환경에 적용한 평가 계획.

---

## 1. 개요

### 목표

자연어 질문을 입력했을 때 LLM이 **Cube REST API JSON 쿼리**를 얼마나 정확하게 생성하는지 측정한다.

### 기존 dbt SL 벤치마크와의 차이

| 항목 | dbt Semantic Layer | Cube (이번 평가) |
|---|---|---|
| 쿼리 형식 | SQL-like 문자열 (`select ... from {{ semantic_layer.query() }}`) | JSON 객체 (`{ query: { dimensions, measures, ... } }`) |
| 평가 질문 | ACME Insurance 영문 44개 | 보험 도메인 한국어 29개 |
| 스키마 제공 방식 | DDL 텍스트 (`ACME_small.ddl`) | Cube 메타데이터 API (`/meta`) |
| 실행 엔드포인트 | dbt Cloud JDBC | Cube REST API (`/load`) |
| 평가 반복 | 5회 | 5회 (동일) |

---

## 2. 평가 질문 목록

`dev_mcp:~/heartcube/questions.md` 기준. 총 **29개** (취소선 항목 1개 제외).

### 2×2 분류

| | **LS** (1~3 테이블) | **HS** (4+ 테이블) |
|---|---|---|
| **LQ** (단순 조회) | LQLS 4개 | LQHS 3개 |
| **HQ** (집계·KPI) | HQLS 7개 | HQHS 5개 |

추가로 **KDL** (KPI→Driver→Lever) 통합 뷰(`kpi.*`) 기반 질문 **10개** (P1-P3, Q1-Q4, E1-E3).

### 질문 분포 요약

| 카테고리 | 수 | 주요 큐브 |
|---|---|---|
| LQLS | 4 | fact_accident, fact_payment, fact_review, dim_customer |
| LQHS | 3 | fact_accident + dim_customer + fact_contract + dim_product + dim_coverage + fact_payment 등 |
| HQLS | 7 | fact_payment, fact_review, fact_accident |
| HQHS | 5 | fact_accident + dim_coverage + dim_hospital + fact_treatment + dim_diagnosis 등 |
| KDL | 10 | kpi (통합 뷰) |
| **합계** | **29** | |

---

## 3. 평가 아키텍처

```
[자연어 질문]
      │
      ▼
[LLM 프롬프트]
  ├─ System: Cube REST API 문법 few-shot 예시
  ├─ Context: /meta 에서 가져온 큐브 스키마 (dimensions, measures, joins)
  └─ User: 자연어 질문
      │
      ▼
[LLM 생성 Cube JSON 쿼리]
      │
      ├──────────────────────┐
      ▼                      ▼
[Cube /load 실행]     [Gold JSON 쿼리 /load 실행]
      │                      │
      ▼                      ▼
[결과 DataFrame]      [Gold DataFrame]
      │                      │
      └──────────┬───────────┘
                 ▼
          [비교 & 채점]
```

---

## 4. 평가 단계

### Step 1. 환경 구성

```bash
# dev_mcp 서버 Cube 실행 확인
ssh dev_mcp "cd ~/heartcube && docker-compose up -d"

# REST API 헬스체크
curl http://dev_mcp:4000/cubejs-api/v1/meta \
  -H "Authorization: Bearer $CUBEJS_API_SECRET"
```

**필요 시크릿:**
- `CUBEJS_API_SECRET`: Cube 서비스 토큰
- `LLM_API_KEY`: OpenAI 또는 Claude API 키

---

### Step 2. 스키마 메타데이터 수집

Cube `/meta` 엔드포인트에서 프롬프트용 컨텍스트를 생성한다.

```python
import requests

def fetch_cube_meta(base_url, token):
    resp = requests.get(
        f"{base_url}/cubejs-api/v1/meta",
        headers={"Authorization": f"Bearer {token}"}
    )
    meta = resp.json()
    return meta["cubes"]  # cubes[].dimensions[], cubes[].measures[], cubes[].joins[]

def build_schema_context(cubes):
    """큐브별 dimensions·measures를 LLM 프롬프트용 텍스트로 변환"""
    lines = []
    for cube in cubes:
        lines.append(f"## {cube['name']}")
        lines.append("### Dimensions")
        for d in cube.get("dimensions", []):
            lines.append(f"  - {d['name']}: {d.get('shortTitle', '')} ({d['type']})")
        lines.append("### Measures")
        for m in cube.get("measures", []):
            lines.append(f"  - {m['name']}: {m.get('shortTitle', '')} ({m['type']})")
    return "\n".join(lines)
```

---

### Step 3. Few-shot 프롬프트 구성

기존 dbt SL 벤치마크의 few-shot 방식과 동일하게 Cube JSON 문법을 LLM에 주입한다.

```python
FEW_SHOT_EXAMPLES = """
Cube REST API는 다음 JSON 형식으로 쿼리합니다:

{
  "query": {
    "dimensions": ["cube_name.dimension_name"],
    "measures": ["cube_name.measure_name"],
    "filters": [{"member": "cube_name.field", "operator": "equals", "values": ["value"]}],
    "timeDimensions": [{"dimension": "cube_name.dt_field", "dateRange": "last 6 months", "granularity": "month"}],
    "order": {"cube_name.measure_name": "desc"},
    "limit": 10
  }
}

예시 1) 보상센터별 평균처리기간을 내림차순으로 조회
{
  "query": {
    "dimensions": ["fact_review.claim_center_nm"],
    "measures": ["fact_review.avg_processing_days"],
    "order": {"fact_review.avg_processing_days": "desc"}
  }
}

예시 2) 최근 3개월 사고유형별 손해율 추이
{
  "query": {
    "dimensions": ["fact_accident.accident_type_l1"],
    "measures": ["fact_accident.loss_ratio"],
    "timeDimensions": [{"dimension": "fact_accident.accident_dt", "granularity": "month", "dateRange": "last 3 months"}]
  }
}
"""

def build_prompt(schema_context, question, few_shot=FEW_SHOT_EXAMPLES):
    return f"""당신은 Cube Semantic Layer 전문가입니다.
아래 스키마와 예시를 참고해 자연어 질문을 Cube REST API JSON 쿼리로 변환하세요.
JSON만 출력하세요. 설명은 하지 마세요.

{few_shot}

## 사용 가능한 스키마
{schema_context}

## 질문
{question}
"""
```

---

### Step 4. LLM 쿼리 생성 및 실행

```python
import json
import openai  # 또는 anthropic

def generate_cube_query(prompt, model="gpt-4o"):
    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1024,
    )
    raw = resp.choices[0].message.content.strip()
    # JSON 파싱 시도
    try:
        return True, json.loads(raw)
    except json.JSONDecodeError:
        return False, {"parse_error": raw}

def execute_cube_query(query_json, base_url, token):
    resp = requests.post(
        f"{base_url}/cubejs-api/v1/load",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=query_json,
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        return True, data.get("data", [])
    else:
        return False, resp.json()
```

---

### Step 5. 채점

#### 5-1. 평가 지표

| 지표 | 설명 | 계산 방법 |
|---|---|---|
| **Execution Success Rate** | 쿼리가 에러 없이 실행되는 비율 | `실행성공건수 / 전체질문수` |
| **Structural Accuracy** | gold 쿼리와 dimensions·measures·filters가 일치하는 비율 | 필드 단위 Jaccard 유사도 |
| **Result Match Rate** | gold 결과와 LLM 결과의 row 집합이 일치하는 비율 | 결과 DataFrame 동등 비교 |
| **JSON Parse Rate** | LLM 출력이 유효한 JSON인 비율 | `파싱성공건수 / 전체질문수` |

#### 5-2. Structural Accuracy 상세

```python
def structural_accuracy(gold_query, gen_query):
    """dimensions, measures, filters 필드 단위 Jaccard 유사도"""
    scores = {}
    for field in ["dimensions", "measures"]:
        gold_set = set(gold_query.get("query", {}).get(field, []))
        gen_set  = set(gen_query.get("query", {}).get(field, []))
        if not gold_set and not gen_set:
            scores[field] = 1.0
        elif not gold_set or not gen_set:
            scores[field] = 0.0
        else:
            scores[field] = len(gold_set & gen_set) / len(gold_set | gen_set)
    return scores

def result_match(gold_rows, gen_rows):
    """결과 row 집합 일치 여부 (순서 무관)"""
    gold_set = {frozenset(r.items()) for r in gold_rows}
    gen_set  = {frozenset(r.items()) for r in gen_rows}
    if not gold_set:
        return 1.0
    return len(gold_set & gen_set) / len(gold_set | gen_set)
```

#### 5-3. 카테고리별 집계

```python
# 결과 DataFrame 컬럼
# question_id | category | question | gold_query | gen_query
# json_parse_ok | exec_ok | dim_jaccard | msr_jaccard | result_match | iteration
```

---

### Step 6. 반복 실행 및 결과 저장

기존 벤치마크와 동일하게 **5회 반복** 후 평균/표준편차로 안정성을 측정한다.

```python
N_ITERATIONS = 5

results = []
for iteration in range(N_ITERATIONS):
    for q in questions:  # questions.md에서 파싱한 질문 목록
        prompt = build_prompt(schema_context, q["text"])
        parse_ok, gen_query = generate_cube_query(prompt)
        
        if parse_ok:
            exec_ok, gen_rows = execute_cube_query(gen_query, BASE_URL, TOKEN)
            _, gold_rows    = execute_cube_query(q["gold_query"], BASE_URL, TOKEN)
        else:
            exec_ok, gen_rows, gold_rows = False, [], []

        struct = structural_accuracy(q["gold_query"], gen_query) if parse_ok else {}
        
        results.append({
            "iteration": iteration,
            "category": q["category"],
            "question": q["text"],
            "json_parse_ok": parse_ok,
            "exec_ok": exec_ok,
            "dim_jaccard": struct.get("dimensions", 0),
            "msr_jaccard": struct.get("measures", 0),
            "result_match": result_match(gold_rows, gen_rows) if exec_ok else 0,
            "gen_query": json.dumps(gen_query, ensure_ascii=False),
            "gold_query": json.dumps(q["gold_query"], ensure_ascii=False),
        })

import pandas as pd
df = pd.DataFrame(results)
df.to_csv("cube_benchmark_results.csv", index=False)
```

---

## 5. 비교 실험 (선택)

기존 dbt SL 벤치마크와 동일하게 두 가지 경로를 비교할 수 있다.

| 경로 | 프롬프트 컨텍스트 | 기대 효과 |
|---|---|---|
| **A. 스키마 없음** | Few-shot 예시만 | 베이스라인 |
| **B. /meta 전체** | 모든 큐브 dimensions·measures | 스키마 컨텍스트 효과 |
| **C. 관련 큐브만** | 질문과 관련된 큐브만 필터링 | 노이즈 감소 효과 |
| **D. KDL 뷰만** | `kpi.*` 단일 prefix 스키마만 | 통합 뷰의 단순화 효과 |

---

## 6. 구현 체크리스트

- [ ] `dev_mcp`에서 Cube REST API 접근 가능 여부 확인 (`/meta`, `/load`)
- [ ] `questions.md` 파서 작성 (자연어↔gold JSON 추출)
- [ ] `/meta` 스키마 컨텍스트 빌더 구현
- [ ] Few-shot 예시 3~5개 확정
- [ ] LLM 생성 → 실행 → 채점 파이프라인 구현
- [ ] 5회 반복 루프 + 결과 CSV 저장
- [ ] 카테고리별(LQLS/LQHS/HQLS/HQHS/KDL) 집계 리포트 작성
- [ ] (선택) 경로 A/B/C/D 비교 실험 실행

---

## 7. 예상 산출물

| 파일 | 내용 |
|---|---|
| `cube_benchmark_results.csv` | 질문×반복 단위 전체 결과 |
| `cube_benchmark_report.md` | 카테고리별·지표별 집계 요약 |
| `benchmark_pipeline.py` | 평가 파이프라인 전체 코드 |

---

## 8. 참고

- 기존 벤치마크: `hex_notebook/Semantic Layer LLM Benchmarking.yaml`
- 원본 논문: [arxiv.org/pdf/2311.07509](https://arxiv.org/pdf/2311.07509.pdf)
- 질문 파일: `dev_mcp:~/heartcube/questions.md`
- Cube 모델: `dev_mcp:~/heartcube/model/cubes/`, `model/views/kpi.yml`
- Cube REST API 문서: https://cube.dev/docs/product/apis-integrations/rest-api
