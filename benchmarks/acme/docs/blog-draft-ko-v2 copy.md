# 정확한 NL2SQL AI Agent부터 비즈니스 가치를 만드는 Analytics Agent

복잡한 기업 데이터 환경에서 자연어로 데이터를 조회하면 두 가지 문제가 생깁니다.

- AI Agent가 조인 경로, 파생 지표 계산, 필터 조건을 비즈니스 맥락 없이 한 번에 추론해야 합니다.
- 우연히 맞는 답이 나왔다 해도, 같은 질문에 항상 같은 결과를 보장할 수 없습니다.

저희는 Cube Semantic Layer를 데이터 인터페이스로 두고 기업 데이터 환경을 반영한 벤치마크를 진행했습니다. 그 과정에서 발견한 한계를 HeartCount 2.0의 agentic flow로 어떻게 보완하고, 실제 비즈니스 인사이트까지 연결되도록 설계했는지를 함께 정리했습니다.

## 먼저 결론부터 보자면

벤치마크 43개 질문을 5회씩 반복해 비교했습니다.


| 방식             | 실행 성공률 | Strict Exact | Cell F1 |
| -------------- | ------ | ------------ | ------- |
| Semantic Layer | 98.1%  | **85.6%**    | 91.7%   |
| DDL            | 73.0%  | **29.3%**    | 42.2%   |


DDL 방식의 실행 성공률부터 73%에 그쳤습니다. 집계 수식, 조인 경로, 필터 조건을 자연어 질문에 맞게 한 번에 생성하기 어렵고, 실행 단계부터 실패하는 경우가 많았습니다.

Semantic Layer는 이 복잡성을 모델 안에 미리 정의합니다. AI Agent는 어떤 필드가 필요한지만 고르면 되고,  복잡한 조인과 집계는 Semantic Layer 내부에서 처리합니다. 덕분에 실행 성공률(98.1%)이 높을 뿐 아니라, 결과도 정답에 훨씬 가까웠습니다.

다만 벤치마크는 Semantic Layer가 더 나은 인터페이스라는 점을 보여줬을 뿐, 실제 서비스에서 그것만으로 충분하지는 않았습니다. 그 한계가 HeartCount 2.0의 agentic loop 설계로 이어졌습니다.

## 왜 이 비교가 필요했을까

[dbt Labs](https://www.getdbt.com/)의 The Analytics Engineering Roundup에서는 [data.world](https://data.world/)의 보험사 데이터셋 실험([논문](https://arxiv.org/pdf/2311.07509))을 참고해, 지식 그래프 대신 dbt Semantic Layer로 같은 비교를 재현했습니다. ([아티클](https://roundup.getdbt.com/p/semantic-layer-as-the-data-interface))


| 접근 방식                   | 정확도   |
| ----------------------- | ----- |
| GPT-4 + 원본 DDL SQL      | 37.4% |
| GPT-4 + 지식 그래프 (SPARQL) | 66.9% |
| dbt Semantic Layer      | 83%   |


다만 기존 실험은 지표(metric) 중심 질문에 집중되어 있었습니다. 조인 경로가 길어지는 질문이나, 집계 없이 dimension 목록만 반환해야 하는 질문은 다루지 않았습니다.

원본 논문은 이런 점을 반영해 질문을 네 가지 카테고리로 나눕니다.


|               | 스키마 복잡도 낮음 | 스키마 복잡도 높음 |
| ------------- | ---------- | ---------- |
| **질문 복잡도 낮음** | LQLS (12개) | LQHS (10개) |
| **질문 복잡도 높음** | HQLS (11개) | HQHS (11개) |


저희는 이 전체 범위를 Cube로 재현해, Semantic Layer가 AI Agent의 데이터 인터페이스로서 실제로 얼마나 잘 동작하는지 보다 견고하게 검증했습니다.

## Cube Semantic Layer 구조

Cube는 내부 데이터 모델을 정의하는 `cube`와, 이를 외부에 노출하는 `view`로 구성됩니다. 조인 경로, 집계 로직, 파생 지표 계산은 모델 내부에 숨기고, AI Agent에는 질문에 필요한 필드만 노출합니다.

```yaml
# policy_amount.yml
cubes:
  - name: policy_amount
    measures:
      - name: total_policy_amount
        sql: policy_amount
        type: sum
        title: Total Policy Amount
        description: "The total amount associated with the policy."

      - name: avg_policy_size
        sql: "{total_policy_amount} / NULLIF({policy_count_for_amounts}, 0)"
        type: number
        title: Average Policy Size
        description: "Total premium amount divided by the number of distinct policies."
```

```yaml
# ops.yml
views:
  - name: ops
    cubes:
      - join_path: claim.claim_coverage.policy_coverage_detail.policy.policy_amount
        includes:
          - total_policy_amount
          - avg_policy_size
```

view에 포함된 필드들은 cube에서 정의한 description과 type을 자동으로 상속받습니다. Agent는 `avg_policy_size`가 몇 단계 조인을 거치는지 알 필요 없이, 노출된 필드 이름과 설명만 보고 쿼리를 만들면 됩니다.

```json
{
  "query": {
    "measures": ["ops.total_policy_amount"],
    "dimensions": ["ops.policy_number"],
    "filters": [
      {
        "member": "ops.party_role_code",
        "operator": "equals",
        "values": ["PH"]
      }
    ]
  }
}
```

이 구조 덕분에 AI Agent는 "어떻게 SQL을 짤 것인가"보다 "무엇을 조회할 것인가"에 집중할 수 있습니다.

## 벤치마크는 무엇을 보여줬을까


| 방식   | 실행 성공률 | Strict Exact | Cell F1 |
| ---- | ------ | ------------ | ------- |
| Cube | 98.1%  | **85.6%**    | 91.7%   |
| DDL  | 73.0%  | **29.3%**    | 42.2%   |


DDL 방식은 정확도 이전에 쿼리 실행부터 흔들렸습니다. 반면 Cube는 조인 경로와 집계 수식을 모델 안에 숨기기 때문에, 에이전트가 필요한 필드와 조건을 맞추는 문제로 난이도를 낮출 수 있었습니다.

카테고리별로 나눠 보면 패턴이 더 선명해집니다.


| 카테고리 | Cube Strict Exact | DDL Strict Exact |
| ---- | ----------------- | ---------------- |
| LQLS | 93.3%             | 33.3%            |
| LQHS | 70.0%             | 10.0%            |
| HQLS | 90.9%             | 49.1%            |
| HQHS | 86.0%             | 22.0%            |


질문 유형으로 나눠 봐도 방향은 같습니다.


| 질문 유형 | Cube Strict Exact | DDL Strict Exact |
| ----- | ----------------- | ---------------- |
| 집계    | **88.6%**         | 36.2%            |
| 차원 목록 | **82.7%**         | 22.7%            |


집계 질문에서는 semantic layer의 이점이 분명했습니다. 집계 로직이 모델에 이미 정의되어 있어 에이전트가 틀릴 여지가 줄어들기 때문입니다. 차원 목록 질문도 DDL보다 훨씬 안정적이었지만, 완전히 해결되지는 않았습니다.

특히 LQHS는 Cube에서 가장 약한 카테고리였습니다. 이 구간의 실패 패턴은 비교적 선명했습니다.

- measure가 아닌 필드를 잘못 배치하는 경우
- 필요한 dimension을 빠뜨리는 경우

즉, semantic layer는 복잡성을 크게 줄여주지만, 한 번의 생성으로 항상 정확한 답을 보장해 주지는 않았습니다.

## 여기서 제품의 요구사항이 달라졌다

벤치마크를 하고 나니 방향은 더 명확해졌습니다. ChatGPT + Cube 조합은 DDL보다 훨씬 나은 출발점이었습니다. 하지만 제품에서는 "한 번 생성해서 맞으면 끝"인 구조보다, 
- 더 정확한 쿼리를 생성하기 위해 실패를 복구하고 
- 비즈니스 인사이트를 도출하기 위해 맥락을 보강하는 구조가 더 중요했습니다.

특히 HeartCount 2.0처럼 데이터 분석 SaaS를 만들 때는 정확한 조회만으로 충분하지 않습니다.


- 분석가는 처음부터 빈 화면에서 질문하지 않아도 됩니다. 주요 지표는 미리 kpi로 정의해두고 미리 pre aggregation 해두어 시각화해서 표시합니다.
- 사용자는 해당 지표를 선택하고, 이를 기준으로 질문을 날리면 mcp에서는 관련 필드에 대한 semantic model 정보만 기준으로 하기 때문에 정확도는 올라감
- 더 정확한 쿼리 생성을 위해 mcp server에서 구체적인 에러를 전달해 heartcount2.0 에서 더 정확한 쿼리를 만들 수 있게합ㄴ디ㅏ.
  - measure인데 dimensions에 넣은 경우, 
  - 필드 자체가 없는 경우
- 그리고 상태 파악에 대한 질문 만에 그치지 않고, 기존 비즈니스 맥락을 반영하여, kpi 에 ...(예를 들어 순수익에 관한 kpi에 dau 라는 상태를 파악하고 기존 실험 처치 맥락을 반영하여 dau 등 driver 데이터와 kpi 데이터를 고려한 처치를 추천합니다.)

즉, semantic layer는 필요조건이었지만 충분조건은 아니었습니다.

## 그래서 HeartCount 2.0에서는 어떻게 풀고 있을까

HeartCount 2.0은 데이터 분석 SaaS입니다. 

현재 구조는 크게 Web App, AI Agent, MCP 서버, Cube Semantic Layer, Data Warehouse로 이어집니다.

> **이미지 제안 1. HeartCount 2.0 서비스 아키텍처 도식**  
> 위치: 이 문단 바로 아래  
> 내용: `Web App ↔ HeartCount2.0 ↔ MCP Server ↔ Cube Semantic Layer / Cube Meta ↔ Data Warehouse` 흐름. 여기에 `KPI`를 시작점으로 두고, 결과가 차트와 표로 다시 Web App에 렌더링되는 흐름까지 함께 표시하면 좋습니다.  
> 목적: 벤치마크에서 확인한 semantic layer의 역할이 실제 서비스 구조 안에서 어디에 놓이는지 한 번에 보여주기 위함입니다.

여기서 MCP 서버는 Cube 쿼리를 실행하고 KPI, driver, lever 같은 비즈니스 맥락을 해석하는 경로입니다. 현재 이 메타 정보는 semantic layer에서 함께 붙어 있습니다. 베스트한 구조라고 보기는 어렵지만, 적어도 에이전트가 "무슨 수치를 볼 것인가"에서 "왜 이 수치를 봐야 하는가"로 넘어갈 수 있는 발판은 제공합니다.

또 한 가지 중요한 점은, 사용자가 완전히 열린 탐색에서 시작하지 않는다는 점입니다. HeartCount 2.0은 visible 기준의 pre-aggregated KPI를 먼저 보여주고, 사용자가 이를 기준으로 질문을 확장할 수 있게 합니다. 이렇게 하면 에이전트도 이미 관리되고 검증된 지표 집합 위에서 추론을 시작할 수 있습니다.

> **이미지 제안 2. HeartCount 2.0 웹앱 결과 화면 스크린샷**
> 위치: 이 문단 바로 아래
> 내용: KPI 카드, 차트, 표, 그리고 driver/lever 기반 해석이나 액션 제안 영역이 함께 보이는 실제 제품 화면 또는 목업
> 목적: HeartCount 2.0이 단순 챗 인터페이스가 아니라, 분석 결과를 소비하고 다음 액션까지 연결하는 웹앱이라는 점을 제품 관점에서 보여주기 위함입니다.

## HeartCount 2.0의 Agentic Loop는 어떻게 동작할까

HeartCount 2.0에서는 semantic layer 위에 agentic loop를 올렸습니다. 목표는 한 번에 정답을 맞히는 것보다, 실패했을 때 더 안정적으로 복구하고 맥락을 보강하는 것입니다.

> **이미지 제안 3. HeartCount 2.0 Agentic Loop 도식**
> 위치: 이 문단 바로 아래
> 내용: `사용자 질문 해석 → KPI/맥락 탐색 → 쿼리 가이드 확인 → 쿼리 생성 → 실행 → 실패 진단/자동 수정 → 필요시 사용자 재질문 → 최종 답변(차트, 표, 액션 제안)`의 순환 구조
> 목적: Cube만으로는 해결되지 않는 문제를 agentic loop가 어떻게 보완하는지 직관적으로 보여주기 위함입니다.

현재 흐름은 대략 다음과 같습니다.

1. 사용자 질문을 해석한다.
2. visible KPI 목록과 KPI/driver/lever 맥락을 확인해 어떤 지표와 관점을 먼저 볼지 좁힌다.
3. MCP 도구를 통해 쿼리 가능한 필드와 가이드를 확인한 뒤 쿼리를 생성한다.
4. Cube에서 실행한다.
5. 실패하면 원인을 진단하고 재시도한다.
6. 질문이 모호하면 사용자에게 다시 묻는다.
7. 최종적으로 웹앱 안에 차트와 표를 함께 보여주고, 가능하면 데이터 기반 액션까지 제안한다.

이 루프가 중요한 이유는 실패 유형이 꽤 예측 가능하기 때문입니다. 예를 들어 에이전트가 measure를 dimension 자리에 넣는 실수는 SQL 생성에서는 곧바로 실패로 끝나기 쉽지만, 도구 계층에서 이를 감지해 자동 보정하고 다시 실행하도록 만들면 더 로버스트한 시스템을 만들 수 있습니다.

또한 HeartCount 2.0의 답변은 숫자 하나에서 끝나지 않습니다. KPI를 시작점으로 삼고, 연결된 driver와 lever 정보를 함께 해석해 "무슨 일이 일어났는가"뿐 아니라 "어디를 더 봐야 하는가"와 "어떤 액션을 고려할 수 있는가"까지 이어지게 설계하고 있습니다. 차트와 표를 함께 보여주는 이유도 같은 맥락입니다. 사용자가 숫자를 다시 해석하기 위해 별도의 분석 도구로 이동하지 않게 하려는 것입니다.

## 앞으로 HeartCount 2.0은 어떻게 발전해야 할까

시맨틱 레이어와 agentic loop만으로 모든 문제가 해결되지는 않았습니다. 지금 구조는 시작점에 가깝고, 앞으로는 세 가지를 더 풀어야 합니다.

- **권한과 거버넌스**
더 많은 팀과 더 다양한 질문을 수용하려면, 어떤 사용자가 어떤 KPI와 어떤 컨텍스트를 볼 수 있는지까지 포함한 제어가 필요합니다. 데이터 접근 권한과 분석 맥락 권한은 같은 문제가 아닙니다.
- **비즈니스 맥락을 모델 밖으로 분리하는 구조**
현재 KPI, driver, lever 정보는 Cube meta에 함께 붙어 있습니다. 빠르게 시작하기에는 괜찮았지만, 팀별 기준과 상황별 해석을 관리하기에는 좋은 구조가 아닙니다. 앞으로는 KPI 간 관계와 분석 맥락을 YAML 기반 구조로 옮기고, 팀별 비즈니스/분석 지식을 Git 기반 문서나 LLM-friendly wiki 형태로 관리하는 레이어가 필요합니다.
- **데이터 조회에서 인과 추론과 액션으로**
semantic layer는 "무슨 숫자를 읽을 것인가"를 안정화합니다. 하지만 "왜 이런 결과가 나왔는가"와 "무엇을 해야 하는가"는 다른 층위의 문제입니다. 저희가 앞으로 만들고 싶은 것은 KPI와 driver, lever 사이의 관계를 더 구조적으로 표현하고, 질문에 따라 더 적절한 분석 경로를 제안할 수 있는 방향성입니다.

정리하면, 벤치마크는 ChatGPT 기반 AI Agent에 semantic layer가 더 나은 데이터 인터페이스라는 점을 보여줬고, HeartCount 2.0은 그 위에 실제로 동작하는 에이전트 시스템을 어떻게 쌓아야 하는지를 보여주는 다음 단계에 가깝습니다.

## 부록: 실험 설정

- **비교 대상**: Cube `/meta` 기반 JSON 쿼리 vs. 전체 PostgreSQL DDL 기반 SQL 생성
- **모델**: GPT-4o, temperature 0.3, few-shot 예시 3개
- **반복 횟수**: 질문 43개, 각 5회 반복
- **평가 방식**: 실행 성공률, Strict Exact, Cell F1
- **Cube 모델**: 9개 기반 cube 위에 단일 public view `ops`

