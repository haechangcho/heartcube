# NL2SQL 성능 측정 방법 — Semantic Layer LLM Benchmarking

## 1. 프로젝트 개요

보험사 데이터셋(ACME Insurance)을 기반으로 **두 가지 NL2SQL 접근 방식**의 성능을 비교합니다.

| 접근 방식 | 프롬프트 컨텍스트 | 실행 엔진 |
|-----------|-----------------|----------|
| Standard SQL | DDL 스키마 전체 | Snowflake 직접 실행 |
| dbt Semantic Layer | 메트릭/디멘션/엔티티 메타데이터 | dbt Cloud SL JDBC API |

- 모델: GPT-4 (`gpt-4`, temperature=0.3)
- 반복 횟수: 질문당 20회 (비결정성 측정)
- 평가 방식: Execution Accuracy (쿼리 실행 결과값 비교)

---

## 2. 파일 구조

```
semantic-layer-llm-benchmarking/
│
├── hex_notebook/
│   ├── Semantic Layer LLM Benchmarking.yaml   ★ 전체 실험 로직 (Hex 노트북)
│   ├── ACME_small.ddl                         ★ SQL 경로용 DDL 스키마 프롬프트
│   ├── benchmark_questions.ttl                ★ 자연어 질문 + Gold Query (RDF/TTL)
│   ├── results_pt1~4.csv                        실험 결과 데이터 (총 220회)
│   └── README.md
│
├── models/
│   ├── omg_models/                            # dbt 모델 (Snowflake 뷰 정의)
│   │   ├── claim.sql
│   │   ├── policy.sql
│   │   └── ... (20개 테이블)
│   └── omg_semantics/                         ★ dbt Semantic Layer 정의
│       ├── claim.yaml                           메트릭/디멘션/엔티티 정의
│       ├── claim_amount.yaml                    파생 메트릭 정의
│       ├── policy.yaml
│       ├── premium.yaml
│       └── ...
│
├── ACME_Insurance/
│   ├── DDL/ACME_small.ddl                     원본 DDL
│   └── data/*.csv                             시드 데이터
│
└── dbt_project.yml                            dbt 프로젝트 설정
```

---

## 3. 벤치마크 질문 로딩

**파일**: `hex_notebook/benchmark_questions.ttl`, `Semantic Layer LLM Benchmarking.yaml`

`benchmark_questions.ttl`에 자연어 질문과 Gold Query가 RDF 형식으로 저장되어 있습니다.
노트북에서 SPARQL로 파싱하여 데이터프레임으로 변환합니다.

### 질문 분류 체계 (2×2 매트릭스)

| | **LS** (단순 스키마: 1~3 테이블) | **HS** (복잡 스키마: 4+ 테이블, 다중 조인) |
|---|---|---|
| **LQ** (단순 조회: SELECT) | LQLS | LQHS |
| **HQ** (복잡 쿼리: 집계·계산·KPI) | HQLS | HQHS |

실험에는 전체 44개 질문 중 **11개**(주로 HQLS 범주)를 선별하여 사용합니다.

### Gold Query 파싱 코드

```python
from rdflib import Graph, Namespace, RDF
import pandas as pd

graph = Graph()
graph.parse("benchmark_questions.ttl", format="ttl")

# TTL에서 SqlQuery 타입만 추출
sparql_query = """
PREFIX QandA: <http://models.data.world/benchmarks/QandA#>
PREFIX dct:   <http://purl.org/dc/terms/>
PREFIX dwt:   <https://templates.data.world/>
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?title ?description ?queryText ?query 
WHERE {
  ?query rdf:type dwt:SqlQuery ;
         QandA:queryText ?queryText ;
         dct:description ?description ;
         dct:title ?title ;
}
"""
results = graph.query(sparql_query)
all_challenges = pd.DataFrame(
    results,
    columns=['title', 'challenge_text', 'gold_query_text', 'gold_query_id']
)

# 실험에 사용할 11개 질문 필터링
selected_challenges = [
    "What is the total amount of premiums that a policy holder has paid by policy number?",
    "What is the average time to settle a claim by policy number?",
    "What is the total amount of premiums that a policy holder has paid?",
    "How many policies have agents sold by agent id?",
    "What is the total loss amounts, which is the sum of loss payment, loss reserve amount by claim number?",
    "How many policies does each policy holder have by policy holder id?",
    "What is the total amount of premiums paid by policy number?",
    "How many claims have been placed by policy number?",
    "What is the average policy size which is the the total amount of premium divided by the number of policies?",
    "How many policies do we have?",
    "How many claims do we have?"
]
filtered_challenges = all_challenges[all_challenges["challenge_text"].isin(selected_challenges)]
```

---

## 4. SQL 경로 프롬프트

**파일**: `hex_notebook/ACME_small.ddl`, `Semantic Layer LLM Benchmarking.yaml`

DDL 스키마 전체를 프롬프트에 주입하여 GPT-4가 SQL을 생성합니다.

### 프롬프트

```python
# YAML 셀: "Generate SQL query"
def generate_sql_query(question):
    prompt = f"""
Given the database described by the following DDL:
{sql_ddl}

Write a SQL query that answers the following question. 
Do not explain the query. Return just the query, 
so it can be run verbatim from your response.

Here's the question: 
{question}
"""
    completion = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )
    return completion.choices[0].message["content"]
```

### DDL 스키마 주요 구조 (`ACME_small.ddl`)

```sql
CREATE TABLE Claim (
    Claim_Identifier        int NOT NULL,
    Catastrophe_Identifier  int NULL,
    Company_Claim_Number    varchar(20) NULL,
    Claim_Open_Date         datetime NULL,
    Claim_Close_Date        datetime NULL,
    Claim_Status_Code       varchar(5) NULL,
    FOREIGN KEY (Catastrophe_Identifier) REFERENCES Catastrophe(...)
)
CREATE TABLE Policy_Coverage_Detail (
    Policy_Coverage_Detail_Identifier int NOT NULL,
    Policy_Identifier    int NOT NULL,
    Coverage_Part_Code   varchar(20) NOT NULL,
    ...
)
CREATE TABLE Agreement_Party_Role (
    Agreement_Identifier int NOT NULL,
    Party_Identifier     bigint NOT NULL,
    Party_Role_Code      varchar(20) NOT NULL,  -- 'AG'=Agent, 'PH'=PolicyHolder
    ...
)
-- + Premium, Loss_Payment, Loss_Reserve, Expense_Payment, Expense_Reserve 등 20개 테이블
```

---

## 5. Semantic Layer 경로 프롬프트

**파일**: `hex_notebook/Semantic Layer LLM Benchmarking.yaml`, `models/omg_semantics/*.yaml`

dbt SL 쿼리 문법 설명 + 런타임에 실제 환경에서 조회한 메타데이터를 few-shot으로 주입합니다.

### SL 메타데이터 런타임 조회

```python
# YAML 셀: "Fetch SL metadata for prompt"
def list_metrics():
    return execute_sl_query("select * from {{ semantic_layer.metrics() }}")

def list_dimensions_for_metric(metric):
    return execute_sl_query(f"""
        select * from {{
            semantic_layer.dimensions(metrics=['{metric}'])
        }}
    """)

def list_entities_for_metric(metric):
    return execute_sl_query(f"""
        select * from {{
            semantic_layer.entities(metrics=['{metric}'])
        }}
    """)
```

### 프롬프트

```python
# YAML 셀: "Generate Semantic Layer query"
def generate_semantic_layer_query(question, metric_details, dimension_details, entity_details):
    prompt = """
Queries to the dbt semantic layer look like this:

select * from {{
    semantic_layer.query(
        metrics=['food_order_amount', 'order_gross_profit'], 
        group_by=[Dimension('primary_entity__dimension').grain('month'), 
                  'customer__customer_type'],
        where="{{ Dimension('primary_entity__filter_dim_1') }} = 'A' AND 
               {{ Dimension('secondary_entity__filter_dim_2') }} = False"
    )
}}

| Parameter | Description                                                        | Example                                  | Type     |
|-----------|--------------------------------------------------------------------|------------------------------------------|----------|
| metrics   | 메트릭 이름 (dbt 정의 기준)                                         | metrics=['revenue']                      | Required |
| group_by  | 그룹핑할 dimension/entity (entity__dimension 형식)                  | group_by=['user__country']               | Optional |
| grain     | 시간 디멘션의 granularity                                           | Dimension('metric_time').grain('month')  | Optional |
| where     | 필터 조건 (Dimension/Entity 객체 사용)                              | where="..."                              | Optional |
| limit     | 결과 행 수 제한                                                     | limit=10                                 | Optional |
| order     | 정렬 (- 접두사로 내림차순, 또는 Metric 객체 사용)                   | order_by=['-revenue']                    | Optional |
| compile   | True이면 SQL만 반환하고 실행하지 않음                               | compile=True                             | Optional |

The following is the definition for the metrics and dimensions available 
to you in the dbt Semantic Layer:

Metrics:
{metric_details}

Dimensions:
{dimension_details}

{entity_details}

Write a query to answer the following question. Do not explain the query, 
and do not say 'here is the query'. Return just the query, 
so it can be run verbatim from your response.

Here's the question:
{question}
"""
```

### dbt Semantic Layer 정의 파일 (`models/omg_semantics/`)

**`claim.yaml`** — 기본 메트릭 정의

```yaml
semantic_models:
  - name: claim
    model: ref('claim')
    defaults:
      agg_time_dimension: claims_made_date
    entities:
      - name: claim_identifier
        type: primary
      - name: catastrophe_identifier
        type: foreign
    dimensions:
      - name: company_claim_number
        type: categorical
      - name: claim_open_date
        type: time
        type_params:
          time_granularity: day
      - name: claim_close_date
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: claims                          # COUNT 메트릭
        expr: company_claim_number
        agg: count
        create_metric: true
      - name: avg_time_to_settle_claim        # AVERAGE 메트릭
        expr: DATEDIFF('day', claim_open_date, claim_close_date)
        agg: average
        create_metric: true
```

**`claim_amount.yaml`** — 파생(derived) 메트릭 정의

```yaml
semantic_models:
  - name: claim_amount
    model: ref('claim_amount')
    entities:
      - name: claim_amount
        type: primary
        expr: claim_amount_identifier
      - name: claim_identifier
        type: foreign        # claim 테이블과 join
    measures:
      - name: total_claim_amount
        agg: sum
        expr: claim_amount

metrics:
  - name: loss_payment_amount
    type: simple
    type_params:
      measure: total_claim_amount
    filter: "{{ Dimension('claim_amount__has_loss_payment') }} = 1"

  - name: loss_reserve_amount
    type: simple
    type_params:
      measure: total_claim_amount
    filter: "{{ Dimension('claim_amount__has_loss_reserve') }} = 1"

  - name: total_loss_amount
    type: derived              # 파생 메트릭: 두 메트릭의 합산
    type_params:
      expr: loss_payment_amount + loss_reserve_amount
      metrics:
        - name: loss_reserve_amount
        - name: loss_payment_amount
```

**`policy.yaml`** — policy 메트릭 정의

```yaml
semantic_models:
  - name: policy
    model: ref('policy')
    entities:
      - name: policy
        type: primary
        expr: Policy_Identifier
      - name: geographic_location_identifier
        type: foreign
    dimensions:
      - name: policy_number
        type: categorical
      - name: status_code
        type: categorical
      - name: policy_effective_date
        type: time
        type_params:
          time_granularity: day
        expr: Effective_Date
    measures:
      - name: number_of_policies
        agg: sum
        expr: 1
        create_metric: true
```

---

## 6. 결과 비교 로직 (Execution Accuracy)

**파일**: `hex_notebook/Semantic Layer LLM Benchmarking.yaml`

생성된 쿼리를 실제로 실행하여 Gold Query 결과값과 비교합니다.
컬럼명이 달라도 **데이터 타입과 값**이 동일하면 정답으로 인정합니다.

```python
# YAML 셀: "Compare Query Results"
def compare_query_results(gold_df, comparison):
    alphabetical_gold_columns = sorted(gold_df.columns)
    gold_comparison_column_map = {}

    for gold_column in alphabetical_gold_columns:
        gold_col_type = gold_df[gold_column].dtype
        gold_col_vals = gold_df[gold_column].sort_values().reset_index(drop=True)

        for comparison_column in comparison.columns:
            if comparison_column in gold_comparison_column_map:
                continue
            # dtype이 같고 값이 동일한 컬럼을 매핑 (컬럼명 무관)
            if comparison[comparison_column].dtype == gold_col_type:
                comparison_vals = comparison[comparison_column].sort_values().reset_index(drop=True)
                if gold_col_vals.equals(comparison_vals):
                    gold_comparison_column_map[comparison_column] = gold_column
                    break

    # 컬럼명 매핑 후 행/열 정렬하여 최종 비교
    comparison = comparison.rename(columns=gold_comparison_column_map)
    comparison = comparison[alphabetical_gold_columns]
    gold_df    = gold_df.reindex(columns=alphabetical_gold_columns)

    gold_df    = gold_df.sort_values(by=alphabetical_gold_columns).reset_index(drop=True)
    comparison = comparison.sort_values(by=alphabetical_gold_columns).reset_index(drop=True)

    return gold_df.equals(comparison)  # True/False
```

### 비교 예시 (`How many claims do we have?`)

| | 쿼리 | 컬럼명 | 값 | 결과 |
|--|------|-------|----|------|
| Gold | `SELECT COUNT(*) AS NoOfClaims FROM claim` | NOOFCLAIMS | 2 | 기준 |
| SQL 생성 | `SELECT COUNT(*) FROM Claim;` | COUNT(*) | 2 | ✅ dtype·값 일치 |
| SL 생성 | `select * from {{ semantic_layer.query(metrics=['claims']) }}` | CLAIMS | 2 | ✅ dtype·값 일치 |

---

## 7. 실험 실행 루프

**파일**: `hex_notebook/Semantic Layer LLM Benchmarking.yaml`

```python
# YAML 셀: "Run Tests"
for i in range(number_of_iterations):           # 기본값: 5회 반복
    for index, row in filtered_challenges.iterrows():   # 11개 질문
        # 1. SQL 쿼리 생성
        gen_sql_success, gen_sql = generate_sql_query(challenge_text)

        # 2. SL 쿼리 생성
        gen_sl_success, gen_sl, sl_prompt = generate_semantic_layer_query(
            challenge_text, metric_details, dimension_details, entity_details
        )

        # 3. 각 쿼리 실행
        gold_df_success,  gold_df = execute_sl_query(gold_query_text)
        sql_comp_success, sql_df  = execute_sl_query(gen_sql)
        sl_comp_success,  sl_df   = execute_sl_query(gen_sl)

        # 4. 결과 비교
        is_sql_result_equivalent      = compare_query_results(gold_df, sql_df)
        is_semantic_result_equivalent = compare_query_results(gold_df, sl_df)

        # 5. 결과 저장
        results_df = results_df.append({
            "is_sql_result_equivalent":      is_sql_result_equivalent,
            "is_semantic_result_equivalent": is_semantic_result_equivalent,
            ...
        })
```

**Rate Limit 처리**:
- Hard limit: 80,000 tokens/min
- Soft limit: 60,000 tokens/min → 초과 시 다음 분까지 자동 대기

---

## 8. 최종 집계 쿼리

**파일**: `hex_notebook/Semantic Layer LLM Benchmarking.yaml` (SQL 셀)

```sql
-- results_pt1~4.csv를 UNION하여 전체 결과 분석
with unioned as (
    select * from "results_pt1.csv"
    union all select * from "results_pt2.csv"
    union all select * from "results_pt3.csv"
    union all select * from "results_pt4.csv"
)
select *, challenge_text in (
    'How many claims have been placed by policy number?',
    'What is the average time to settle a claim by policy number?',
    'What is the average policy size...'
) as too_many_mf_hops     -- SL이 여러 hop 필요한 질문 여부
from unioned;

-- 질문별 성능 요약
select
    challenge_text,
    count(distinct generated_sql_query_text)      as unique_sql_variants,
    count(distinct generated_semantic_query_text) as unique_semlayer_variants,
    sum(case when is_sql_result_equivalent       then 1 else 0 end)
        / count(1.0)                              as sql_success_percentage,
    sum(case when is_semantic_result_equivalent  then 1 else 0 end)
        / count(1.0)                              as semlayer_success_percentage
from unioned
group by 1;

-- too_many_mf_hops 기준 분리 집계
select
    too_many_mf_hops,
    sum(case when is_sql_result_equivalent       then 1 else 0 end) / count(*) as sql_percentage,
    sum(case when is_semantic_result_equivalent  then 1 else 0 end) / count(*) as semantic_percentage,
    count(*) as num_runs
from unioned
group by 1;
```

---

## 9. 실험 결과 (총 220회, results_pt1~4.csv 합산)

### 전체 정확도

| 방식 | 정답 수 / 전체 | 정확도 |
|------|--------------|--------|
| Standard SQL | 72 / 220 | **32.7%** |
| dbt Semantic Layer | 133 / 220 | **60.5%** |

### 질문별 결과

| 질문 | SQL | Semantic Layer |
|------|-----|----------------|
| How many claims do we have? | 20/20 (100%) | 20/20 (100%) |
| How many policies do we have? | 20/20 (100%) | 20/20 (100%) |
| How many policies have agents sold by agent id? | 0/20 (0%) | 20/20 (100%) |
| How many policies does each policy holder have? | 0/20 (0%) | 20/20 (100%) |
| Total premiums paid by policy number? | 3/20 (15%) | 20/20 (100%) |
| Total premiums by policy holder by policy number? | 0/20 (0%) | 18/20 (90%) |
| Total loss amounts by claim number? | 0/20 (0%) | 12/20 (60%) |
| Average policy size? | 16/20 (80%) | 0/20 (0%) |
| Average time to settle a claim by policy number? | 12/20 (60%) | 0/20 (0%) |
| Total premiums by policy holder? | 0/20 (0%) | 3/20 (15%) |
| Claims placed by policy number? | 1/20 (5%) | 0/20 (0%) |

### 주요 관찰 사항

- **SL 전반 우세**: Semantic Layer가 Standard SQL보다 약 2배 높은 정확도 (60.5% vs 32.7%)
- **SQL 우세 케이스**: `average_time`, `average_policy_size`처럼 집계 계산이 복잡하거나 SL 메트릭으로 정의되지 않은 질문
- **SL 완패 케이스 (`too_many_mf_hops`)**: `claims by policy number`처럼 여러 semantic model을 넘나드는 join(hop)이 필요한 질문에서 SL 0%
- **비결정성**: 동일 질문도 20회 반복 시 결과가 다름 → temperature=0.3으로 낮춰도 일관성 차이 존재
