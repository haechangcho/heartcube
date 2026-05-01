# AI Agent를 위한 데이터 인터페이스로서의 Semantic Layer

Semantic Layer를 AI Agent의 데이터 인터페이스로 구축하고, 보험 벤치마크 데이터셋으로 NL2SQL의 성능을 검증합니다.

[data.world](https://data.world/) 팀은 지식 그래프 기반의 [SPARQL](https://en.wikipedia.org/wiki/SPARQL) 컨텍스트가 DDL 기반 SQL 생성보다 더 높은 정확도를 보인다는 점을 가상의 보험사 데이터셋으로 검증했습니다. ([논문](https://arxiv.org/pdf/2311.07509))

또한 [dbt Labs](https://www.getdbt.com/)의 The Analytics Engineering Roundup에서는 이를 dbt Semantic Layer로 재현하며 더 유의미한 결론에 도달했습니다. ([아티클](https://roundup.getdbt.com/p/semantic-layer-as-the-data-interface))

이 글은 dbt Labs 실험에서 충분히 다루지 못했던 질문 유형까지 확장해, 보다 견고한 NL2SQL을 위한 Semantic Layer의 성능을 검증합니다.

## 기존 실험의 범위와 한계

dbt Labs 실험은 "질문 복잡도가 높고, 스키마 복잡도가 낮은"(HQLS) 유형 중에서도 지표(metric) 중심 질문에 집중했습니다. 


| 접근 방식                   | 정확도   |
| ----------------------- | ----- |
| GPT-4 + 원본 DDL SQL      | 37.4% |
| GPT-4 + 지식 그래프 (SPARQL) | 66.9% |
| dbt Semantic Layer      | 83%   |


이 결과는 시맨틱 레이어가 복잡한 자연어 질문을 SQL로 변환하는 인터페이스로 가치 있다는 점을 뒷받침합니다.

다만, 실험에서 다루지 못한 질문 유형도 있습니다.

- 정규화된 스키마 구조로 인해 조인 경로가 길어지는 질문
  이러한 경우 MetricFlow의 [multi-hop join 제한](https://docs.getdbt.com/docs/build/join-logic#multi-hop-joins)(최대 2-hop)으로 인해 일부 질문은 평가에서 제외되었습니다.
- measure 없이 차원 값 목록만 반환하는 질문
  예를 들어, “담당자별로 연결된 청구 건과 사고 유형을 보여줘”처럼 집계가 필요 없고 dimension 조회만으로 답하는 질문들입니다. 당시 MetricFlow는 지표 중심으로 설계되어 있어 dimension-only 쿼리가 자연스럽게 지원되지 않았습니다. ([당시 논의](https://roundup.getdbt.com/p/semantic-layer-as-the-data-interface/comment/44307700)) 
  > 현재는 [PR #1720](https://github.com/dbt-labs/metricflow/pull/1720), [PR #1359](https://github.com/dbt-labs/metricflow/pull/1359) 등을 통해 지표 없는 쿼리가 공식 지원됩니다.

이처럼 기존 실험은 특정 유형의 질문에 집중되어 있어, 실제 엔터프라이즈 환경이나 최근의 AI-Native 활용 맥락을 충분히 반영한다고 보기는 어렵습니다.

[원본 논문](https://arxiv.org/pdf/2311.07509)에서는 이러한 점을 고려해 벤치마크를 네 가지 카테고리로 구성합니다.


|               | 스키마 복잡도 낮음 | 스키마 복잡도 높음 |
| ------------- | ---------- | ---------- |
| **질문 복잡도 낮음** | LQLS (12개) | LQHS (10개) |
| **질문 복잡도 높음** | HQLS (11개) | HQHS (11개) |


이 벤치마크에는 지표 중심의 질문만 있지않습니다. 집계 없이 차원 값 목록을 그대로 반환해야 하는 질문들도 함께 포함되어 있습니다.

예를 들어 “담당자별로 연결된 청구 건과 사고 유형을 보여줘”처럼, measure 없이 dimension만으로 답해야 하는 경우입니다.

이번 실험은 이러한 유형까지 포함해, 보다 현실적인 범위에서 Semantic Layer의 성능을 검증합니다.

## Cube Semantic Layer 구조

같은 벤치마크를 [Cube](https://cube.dev)로 재현했습니다. Cube는 내부 데이터 모델을 정의하는 [cube](https://cube.dev/docs/product/data-modeling/reference/cube)와, 이를 외부에 노출하는 [view](https://cube.dev/docs/product/data-modeling/reference/view)로 구성됩니다. dbt가 MetricFlow 기반으로 메트릭과 시맨틱 모델을 정의하는 반면, Cube는 이 두 레이어의 분리를 통해 복잡성을 모델 내부로 숨깁니다.

### 모델 정의

cube에 조인 경로와 집계 로직을 정의하고, view에서 AI Agent에 노출할 필드를 선택합니다.

```yaml
# acme_policy_amount.yml — cube 정의
cubes:
  - name: acme_policy_amount
    public: false
    sql_table: oda_benchmark.acme_policy_amount

    measures:
      - name: total_policy_amount
        sql: policy_amount
        type: sum
        description: “The total amount associated with the policy.”

      - name: avg_policy_size
        sql: “{total_policy_amount} / NULLIF({policy_count_for_amounts}, 0)”
        type: number
        description: “Total premium amount divided by the number of distinct policies.”
```

view는 내부 cube들을 조합해 AI Agent가 사용할 단일 네임스페이스를 만듭니다. 조인 경로가 5단계여도 view를 통해 단일 필드로 노출됩니다.

```yaml
# acme_ops.yml — view 정의
views:
  - name: acme_ops
    cubes:
      - join_path: acme_claim.acme_claim_coverage.acme_policy_coverage_detail.acme_policy.acme_policy_amount
        includes:
          - total_policy_amount
          - avg_policy_size
```

### AI Agent 컨텍스트

AI Agent는 view를 기반으로 생성된 `[/meta](https://cube.dev/docs/product/apis-integrations/core-data-apis/rest-api/reference#base_pathv1meta)` 응답을 컨텍스트로 사용합니다:

```json
{
  “name”: “acme_ops”,
  “dimensions”: [
    {
      “name”: “acme_ops.party_role_code”,
      “shortTitle”: “Party Role Code”,
      “type”: “string”,
      “description”: “Must filter using this dimension if referring to agents or policyholders. If party_role_code = 'PH' then Party_Identifier refers to policy_holder_id, if party_role_code = 'AG' then Party_Identifier refers to agent_id.”
    },
    ...
  ],
  “measures”: [
    {
      “name”: “acme_ops.avg_policy_size”,
      “shortTitle”: “Average Policy Size”,
      “type”: “number”,
      “description”: “Total premium amount divided by the number of distinct policies.”
    },
    ...
  ]
}
```

cube 정의에 설정한 description과 type은 `/meta` 응답에 자동으로 상속됩니다. 

덕분에 AI Agent는 `total_policy_amount`처럼 단순 합계인지, `avg_policy_size`처럼 여러 테이블을 거치는 파생 지표인지 알 필요가 없습니다. 구현 세부사항은 모델 안에 캡슐화되어 있기 때문입니다.

### 쿼리 인터페이스

AI Agent는 `/meta`를 컨텍스트로 사용하여 JSON 쿼리를 생성합니다:

```json
{
  “query”: {
    “dimensions”: [“acme_ops.policy_number”, “acme_ops.party_full_legal_name”],
    “measures”: [“acme_ops.total_policy_amount”],
    “filters”: [
      {
        “member”: “acme_ops.party_role_code”,
        “operator”: “equals”,
        “values”: [“PH”]
      }
    ]
  }
}
```

테이블 구조, 조인 경로, 집계 로직은 시맨틱 레이어 내부에서 처리됩니다. AI Agent는 무엇을 원하는지만 표현하면 됩니다.

## 실험 설계

두 방식을 비교합니다.


|             | 컨텍스트              | 출력           | 실행 대상            |
| ----------- | ----------------- | ------------ | ---------------- |
| **Cube 방식** | `/meta` API 응답    | Cube JSON 쿼리 | Cube `/load` API |
| **DDL 방식**  | 전체 PostgreSQL DDL | SQL          | PostgreSQL 직접 실행 |


두 방식 모두 GPT-4o, temperature 0.3, few-shot 프롬프팅(예시 3개), 동일한 질문 43개로 수행했습니다. 데이터 인터페이스(Cube vs DDL)를 제외한 실험 조건은 동일해, 두 방식의 차이가 순수하게 인터페이스 선택에서 비롯된 것인지를 측정합니다. LLM의 확률적 특성을 고려해 질문당 5회 반복 실험하고 결과를 집계했습니다. 데이터셋은 data.world 논문과 동일한 보험 데이터셋으로, 손해보험 업계 표준인 OMG P&C Data Model을 기반으로 합니다.

### 질문 분류

소스 논문의 2×2 카테고리(LQLS/LQHS/HQLS/HQHS)를 그대로 사용합니다.


|               | 스키마 복잡도 낮음 | 스키마 복잡도 높음 |
| ------------- | ---------- | ---------- |
| **질문 복잡도 낮음** | LQLS (12개) | LQHS (10개) |
| **질문 복잡도 높음** | HQLS (11개) | HQHS (11개) |


43개 질문에는 지표 집계와 차원 값 목록 반환이 섞여있습니다. dbt Semantic Layer 실험이 주로 다룬 영역은 전자였습니다. 추가적으로 이름 기반 조회("Mary Policy Holder의 클레임 전부")도 별도로 다룹니다.

### 평가 지표

생성된 쿼리를 실제 DB에서 실행하고, 결과를 정답 쿼리 결과와 비교합니다.


| 지표           | 설명                                                                            |
| ------------ | ----------------------------------------------------------------------------- |
| Strict Exact | 결과셋이 정답과 완전히 일치하면 1, 아니면 0. 맞거나 틀리거나입니다.                                      |
| Cell F1      | 결과의 (컬럼명, 값) 쌍이 정답과 얼마나 겹치는지 측정합니다. 컬럼이 더 많거나 적거나, 값이 일부만 맞아도 겹치는 만큼 점수를 줍니다. |


## 실험 결과

### 전체 요약


| 방식   | 실행 성공률 | Strict Exact | Cell F1 |
| ---- | ------ | ------------ | ------- |
| Cube | 98.1%  | **85.6%**    | 91.7%   |
| DDL  | 73.0%  | **29.3%**    | 42.2%   |


두 방식의 격차는 Strict Exact 85.6% vs. 29.3%로 뚜렷합니다. DDL 방식은 실행 성공률 자체가 73%에 그칩니다.

DDL 방식에서는 자연어 질문 하나를 SQL로 바꾸려면 어떤 테이블을 어떤 순서로 조인할지, 중간에 어떤 조건을 걸어야 할지를 AI Agent가 스스로 파악해야 합니다. "고객별 손해 지급액 합계"처럼 단순해 보이는 질문도 클레임 테이블부터 시작해 금액 테이블, 계약 역할 테이블까지 여러 단계를 거쳐야 하고, 중간에 고객만 필터링하는 조건도 직접 찾아야 합니다.

Cube는 이 복잡성을 모델 안에 숨깁니다. AI Agent는 어떤 필드가 필요한지만 고르면 되고, 조인 경로, 집계 수식, 필터 조건은 Cube가 내부적으로 SQL로 변환합니다.

### 카테고리별 결과


| 카테고리 | Cube Strict Exact | DDL Strict Exact |
| ---- | ----------------- | ---------------- |
| LQLS | 93.3%             | 33.3%            |
| LQHS | 70.0%             | 10.0%            |
| HQLS | 90.9%             | 49.1%            |
| HQHS | 86.0%             | 22.0%            |


- **집계 카테고리(HQLS, HQHS)에서 Cube가 특히 강합니다.** 

  보험료 합계, 평균 클레임 처리 기간, 손해율처럼 집계 공식이 명확한 질문들입니다. 집계 로직이 모델 안에 이미 정의되어 있어 AI Agent는 어떤 수치가 필요한지만 고르면 됩니다. 특히 dbt Roundup 실험에서 제외되었던 세 질문도 Cube에서는 5회 반복 실험 모두 정확히 답했습니다.

- **LQHS는 Cube에서 가장 약한 카테고리(70%)입니다.** 

  실패 패턴은 두 가지입니다. 하나는 dimension의 역할을 잘못 해석해 결과가 나올 수 없는 조건을 만드는 경우, 다른 하나는 필요한 dimension을 출력에서 빠뜨리는 경우입니다. 두 케이스 모두 모델 구조 문제라기보다 각 dimension의 설명이 부족해 AI Agent가 용도를 잘못 판단한 패턴입니다.

- **DDL은 LQHS 10%, HQHS 22%로 복잡한 스키마에서 특히 취약합니다.** 

  조인 경로와 필터 조건, 그루핑 기준을 전부 스스로 파악해야 하는데, 이를 동시에 맞추는 경우가 드뭅니다.

### 질문 유형별 결과

집계 질문과 차원 목록 질문을 나눠 봅니다.


| 질문 유형 | Cube Strict Exact | DDL Strict Exact |
| ----- | ----------------- | ---------------- |
| 집계    | **88.6%**         | 36.2%            |
| 차원 목록 | **82.7%**         | 22.7%            |


Cube는 집계 질문에서 더 강합니다. 집계 로직이 모델에 이미 정의되어 있어 AI Agent가 틀릴 여지가 적기 때문입니다. 차원 목록 질문도 DDL 22.7% 대비 82.7%로 격차가 뚜렷합니다. 집계가 없는 질문도 조인 경로를 모델이 내부에서 처리하는 구조적 이점을 그대로 받습니다.

### 이름 기반 조회

43개 핵심 질문에는 이름 기반 엔티티 조회가 없습니다. 이 확장은 "Mary Policy Holder의 클레임을 모두 보여줘"처럼 사람 이름을 필터 값으로 해석해야 하는 4개 질문을 추가했습니다.

1. 고객 ID 1의 클레임을 모두 보여줘.
2. Mary Policy Holder 이름의 고객 클레임을 모두 보여줘.
3. Bob Insurance Agent가 판매한 계약을 모두 보여줘.
4. Bob Insurance Agent가 판매한 계약에 연결된 클레임을 모두 보여줘.

이름 기반 조회는 집계 measure 없이 차원 조회와 필터만으로 구성됩니다. 결과셋 전체 일치보다 어떤 컬럼과 값을 얼마나 맞췄는지가 더 유의미한 신호이므로 Cell F1로 비교합니다.


| 방식   | 실행 성공률 | Cell F1   |
| ---- | ------ | --------- |
| Cube | 100.0% | **56.1%** |
| DDL  | 100.0% | 9.1%      |


DDL은 "Mary Policy Holder의 클레임"을 찾으려면 AI Agent가 여러 테이블의 조인 경로, 역할 조건, 이름 정규화 로직을 전부 직접 조합해야 합니다.

```sql
SELECT c.company_claim_number, p.policy_number
FROM claim c
JOIN claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN policy p ON pcd.policy_identifier = p.policy_identifier
JOIN agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN person ON apr.party_identifier = person.person_identifier
WHERE apr.party_role_code = 'PH'
  AND COALESCE(NULLIF(person.full_legal_name, ''),
      TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) = 'Mary Policy Holder'
```

Cube는 조인 경로와 이름 정규화 로직이 모델 안에 정의되어 있어 AI Agent는 이름을 필터 값으로 넘기기만 하면 됩니다.

```json
{
  "query": {
    "dimensions": ["ops.company_claim_number", "ops.policy_number"],
    "filters": [
      { "member": "ops.party_full_legal_name", "operator": "equals", "values": ["Mary Policy Holder"] },
      { "member": "ops.party_role_code", "operator": "equals", "values": ["PH"] }
    ]
  }
}
```

Cube 56.1%가 낮아 보일 수 있지만, 대부분은 정답보다 컬럼을 더 많이 반환해서 점수가 깎이는 패턴입니다. 필요한 데이터는 찾아오되 어떤 컬럼까지 출력할지를 정확히 맞추지 못하는 경우입니다.

## 남아 있는 과제

이번 실험에서는 시맨틱 레이어가 NL2SQL 정확도를 크게 향상시킨다는 점을 보여줍니다. 다만, 정확도 개선만으로는 AI-Native 환경에서 실제 비즈니스 가치로 이어지기에는 아직 부족한 부분이 많습니다.

- **시맨틱 레이어 자체가 노동집약적입니다.** 

  Cube, dbt Semantic Layer, LookML 모두 dimensions, measures, join 경로, 집계 로직을 수작업으로 정의해야 합니다. 스키마가 바뀌면 관련 정의도 함께 수정해야 하고, 잘못된 로직이 있어도 별다른 오류 없이 결과가 반환됩니다. 
  [dbt 2025 설문](https://www.getdbt.com/resources/state-of-analytics-engineering-2025#download-the-report)에 따르면 AI 기반 데이터 질의 환경에서 시맨틱 레이어를 쓰는 곳은 3분의 1에 불과합니다. 나머지 3분의 2는 여전히 raw SQL 생성을 씁니다. 채택율이 낮은 이유 중 하나는 "한 번 정의하면 어디서나"라는 약속과 달리, 실제로는 초기 구축, 유지보수, 마이그레이션에 드는 숨은 비용이 크기 때문입니다.

- **비즈니스 맥락은 모델 밖에 있습니다.** 

  가령 시맨틱 레이어에서는 "활성 사용자"를 하나의 정의로 고정합니다. 하지만 마케팅팀, 제품팀, 수익팀이 각자 다른 기준으로 이 지표를 쓰고 있다면, 어느 정의가 지금 이 질문에 맞는지는 모델 밖의 문제입니다.

- **데이터 조회에서 비즈니스 액션까지의 간극.** 
  
  올바른 숫자를 뽑아오는 것은 시작일 뿐입니다. "Q3 매출이 12% 감소했습니다"라는 답이 "왜 그랬는가", "무엇을 해야 하는가", "누구에게 알려야 하는가"로 이어지려면 비즈니스 맥락, 인과 추론, 워크플로우 연결이 필요합니다. [맥킨지 조사](https://www.mckinsey.com/capabilities/mckinsey-technology/our-insights/building-the-foundations-for-agentic-ai-at-scale)에 따르면 전 세계 기업의 3분의 2가 AI 에이전트를 사용했지만, 실질적인 가치로 스케일한 곳은 10% 미만입니다. 데이터를 읽는 것과 그것으로 KPI를 움직이는 것 사이의 간극입니다.

시맨틱 레이어는 AI Agent가 데이터를 더 정확하게 읽도록 도와 그 간극의 첫 번째 단계를 좁힙니다. 나머지는 아직 풀어야 할 문제입니다.

## 부록: 기술 설정

- **Cube 모델**: 9개 기반 큐브 위에 단일 public view `ops`. Dimensions에는 계약, 클레임, 당사자, 사람, 커버리지, 재해, 금액 데이터가 포함됩니다. Measures에는 보험료, 손해 구성요소, 클레임 기간에 대한 count, sum, avg 집계가 포함됩니다.

- **벤치마크 스크립트**: Cube `/load` API를 호출하는 Python 스크립트와, DDL 방식에서 생성된 SQL을 직접 실행하는 PostgreSQL 연결로 구성됩니다. 두 방식 모두 few-shot 프롬프팅(예시 3개)을 사용하며, 결과는 골드 쿼리 실행 결과와 비교해 Strict Exact와 Cell F1로 채점합니다.

- **모델**: GPT-4o, temperature 0.3.

- **반복**: 질문당 5회 (Cube 총 215회 호출, DDL SQL 총 215회 호출).
