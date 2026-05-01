# Semantic Layer로 완성하는 Analytics Agent: SQL 생성부터 비즈니스 인사이트까지

자연어로 데이터를 질의하는 AI Agent 환경이 빠르게 현실화되고 있습니다. 지금 가장 많이 논의되는 접근은 두 가지입니다. AI가 SQL을 직접 생성하는 Text-to-SQL, 그리고 비즈니스 로직을 미리 구조화해두는 Semantic Layer입니다.

저희는 분석이 의사결정으로 이어지는 AI Data Analyst를 만들고 있습니다. 숫자를 꺼내오는 것보다, 그 숫자가 왜 그렇게 나오는지, 그리고 어떤 행동으로 이어져야 하는지까지 연결되는 구조가 목표입니다.

이를 위해 Semantic Layer를 저희 서비스 아키텍처에 넣는 PoC를 진행했고, 그 과정에서 실제 인사이트를 주는 분석이 되게 하기 위해 무엇이 필요한지를 확인했습니다.

## Semantic Layer vs Text-to-SQL

dbt Labs는 올해 [Semantic Layer vs. Text-to-SQL 벤치마크](https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026?version=1.12)에서 이 문제를 직접 수치로 확인했습니다.


| 접근 방식                        | 정확도   |
| ---------------------------- | ----- |
| GPT-5.3 + DDL                | 84.1% |
| GPT-5.3 + dbt Semantic Layer | 100%  |


결과는 명확했습니다. 하지만 이 실험은 지표(metric) 중심 질문에 한정됐고, 3-hop 이상의 복잡한 조인이나 집계 없는 목록 조회는 포함되지 않았습니다. 실제 비즈니스 질문은 이보다 다양합니다.

저희는 같은 데이터셋을 질문 복잡도 × 스키마 복잡도 기준으로 나눈 43개 질문으로 확장해, [Cube](https://cube.dev/) Semantic Layer로 5회씩 반복 실험했습니다.


|               | 스키마 복잡도 낮음 | 스키마 복잡도 높음 |
| ------------- | ---------- | ---------- |
| **질문 복잡도 낮음** | LQLS (12개) | LQHS (10개) |
| **질문 복잡도 높음** | HQLS (11개) | HQHS (10개) |


결과와 함께, 실험에서 발견한 한계를 HeartCount 2.0의 agentic flow로 어떻게 보완했는지 정리했습니다.

## Semantic Layer: AI Agent가 읽기 쉽게 구조화하기

Cube는 내부 데이터 모델을 정의하는 `cube`와, 이를 외부에 노출하는 `view`로 구성됩니다. 조인 경로, 집계 로직, 파생 지표 계산은 모델 내부에 숨기고, AI Agent에는 질문에 필요한 필드만 노출합니다.

```yaml
# claim.yml - cube 정의
cubes:
	- name: claim
		sql_table: claim
	
	joins:
		- name: claim_amount
			sql: "{claim}.claim_identifier = {claim_amount}.claim_identifier"
			relationship: one_to_many
	
	dimensions:
		- name: company_claim_number
			sql: company_claim_number
			type: string
			title: Claim Number
	
	measures:
		- name: claim_count
			sql: company_claim_number
			type: count
			title: Claim Count
	
		- name: avg_full_loss_amount
			sql:"{claim_amount.total_full_loss_amount} / NULLIF({claim_count}, 0)"
			type: number
			title: Avg Full Loss Amount per Claim
			description: "Average full loss (loss payment + loss reserve + expense payment + expense reserve) per claim."
```

```yaml
# ops.yml — view 정의
views:
	- name: ops
		cubes:
	- join_path: claim
		includes:
			- company_claim_number
			- claim_count
			- avg_full_loss_amount
```

join 로직과 집계 수식은 cube 안에 숨겨져 있습니다. `avg_full_loss_amount`는 내부적으로 `claim_amount`를 조인해 계산하지만, view는 그 구조를 알 필요 없이 필드 이름만 선언합니다. Agent도 마찬가지로 조인이 몇 단계인지 알 필요 없이, 노출된 필드 이름과 설명만 보고 쿼리를 만들면 됩니다.

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

이 구조 덕분에 AI Agent는 “어떻게 SQL을 짤 것인가”보다 “무엇을 조회할 것인가”에 집중할 수 있습니다.

## 실험 결과: Semantic Layer vs DDL


| 방식   | 실행 성공률 | Strict Exact |
| ---- | ------ | ------------ |
| Cube | 100%   | **76.3%**    |
| DDL  | 99.5%  | **35.3%**    |


실행 성공률은 두 방식 모두 높았습니다. 하지만 실행은 정확한 답을 보장하지 않습니다. DDL 방식에서는 에이전트가 조인 경로, 집계 수식, 필터 조건을 처음부터 추론해야 하지만 Cube는 앞서 본 것처럼 이 로직을 모델 안에 미리 정의해두기 때문에 에이전트는 어떤 필드와 조건을 쓸지에만 집중하면 됩니다.

카테고리별로 나눠보면 예상과 다른 패턴이 보입니다.


| 카테고리 | Cube Strict Exact | DDL Strict Exact |
| ---- | ----------------- | ---------------- |
| LQLS | 68.3%             | 35.0%            |
| LQHS | 58.0%             | 22.0%            |
| HQLS | 89.1%             | 54.5%            |
| HQHS | 90.0%             | 28.0%            |


**질문이 복잡할수록 오히려 정확도가 높습니다.** HQLS 89.1%, HQHS 90.0%인 반면, LQLS 68.3%, LQHS 58.0%입니다. LQLS/LQHS는 집계 없이 특정 값의 목록을 반환하는 질문이 집중된 반면, HQLS/HQHS는 집계 중심 질문이 많기 때문입니다. 질문 유형으로 나눠보면 차이가 명확합니다.


| 질문 유형 | Cube Strict Exact | DDL Strict Exact |
| ----- | ----------------- | ---------------- |
| 집계    | **89.5%**         | 41.9%            |
| 차원 목록 | **63.6%**         | 29.1%            |


집계 로직은 모델에 미리 정의되어 있어 에이전트가 틀릴 여지가 줄어듭니다. 반면 집계 없이 차원 목록만 조회하는 질문에서는 63.6%로 떨어졌는데, 실패한 유형은 크게 두 가지입니다.

- dimension만 반환하면 되는 질문에 불필요한 measure를 추가하는 경우
- 필요한 dimension을 빠뜨리거나 measure/dimension 배치를 혼동하는 경우

## 정확한 조회, 그다음 문제

DDL 대비 성능은 충분히 납득할 만합니다. 다만 Cube만 놓고 보면, 집계 질문에서 10%, 차원 목록 질문에서 36%가 아직 틀립니다. 두 가지 문제가 남아 있습니다.

**정확도를 더 높여야 합니다.** `description` 같은 메타 정보를 구체적으로 작성할수록 정확도는 올라가지만, 그것만으로는 충분하지 않습니다. 에이전트가 오류를 스스로 감지하고 재시도하는 루프가 필요합니다.

**데이터 조회가 분석의 끝이 아닙니다.** KPI가 왜 움직였는지, 다음에 무엇을 봐야 하는지, 어떤 조치가 필요한지까지 답하려면 단순 조회 이상의 맥락이 필요합니다. KPI와 연결된 driver/lever 관계가 이 역할을 합니다.

HeartCount 2.0은 이 두 문제를 구조적으로 풀기 위해 설계했습니다.

## HeartCount 2.0의 Analytics Agent 구조

```mermaid
---
config:
  layout: dagre
---
flowchart LR
    subgraph App["HeartCount 2.0"]
        direction TB
        User("<b>사용자 질문</b>") h 
        Agent("<b>AI Agent</b><br>Reasoning / Tool Selection")
        User -->|"자연어 질문"| Agent
        Agent -->|"결과 반환"| User
    end

    subgraph SemanticLayer["Semantic Layer (Cube)"]
        direction TB
        MCP("<b>Cube MCP</b><br>지표 · 차원 탐색<br>비즈니스 맥락 탐색<br>쿼리 실행 · 오류 자동 수정")
        Cube("<b>Cube Core</b><br>Measure · Dimension 정의<br>캐시 · 사전 집계<br>비즈니스 맥락")
        MCP --> Cube
    end

    DW("<b>Data Warehouse</b><br>(BigQuery / Snowflake 등)")

    Agent -->|"tool calling"| MCP
    MCP -->|"오류 메시지 반환 → 재시도"| Agent
    Cube -->|"SQL 생성 & 실행"| DW
    DW -->|"Raw 결과"| Cube

    style App fill:#fde8e4,stroke:#e8503a,color:#1a1a1a
    style SemanticLayer fill:#e4f4fb,stroke:#5ab8e8,color:#1a1a1a

    classDef appNode fill:#ffffff,stroke:#e8503a,color:#1a1a1a
    classDef slNode fill:#ffffff,stroke:#5ab8e8,color:#1a1a1a
    classDef dwNode fill:#3d3d3d,stroke:#1a1a1a,color:#ffffff

    class User,Agent appNode
    class MCP,Cube slNode
    class DW dwNode

```



### 기존 분석 맥락에서 출발

image (3).png

사용자는 빈 화면이 아니라 미리 정의된 KPI 목록에서 분석을 시작합니다. 덕분에 에이전트도 전체 데이터 웨어하우스 대신 이미 검증된 지표 집합 위에서 추론합니다.

KPI에 연결된 비즈니스 지식으로는 “이 지표가 떨어지면 어떤 변수를 먼저 봐야 하는가”를 사전 정의합니다. 에이전트는 이 관계를 참고해 분석 경로를 좁힙니다.

### 더 정확한 쿼리를 위한 Agentic Loop

쿼리가 실패하면 MCP는 해당 오류를 에이전트에 전달합니다. 에이전트는 오류 메시지를 분석해 잘못된 필드나 조건을 수정한 뒤 다시 시도합니다. 질문이 모호한 경우에는 사용자에게 추가로 확인합니다.

```mermaid
flowchart TB
  User("<b>사용자 질문</b><br>자연어로 분석 요청")
  Context("<b>비즈니스 맥락 확인</b><br>KPI · Driver · Lever 로드<br>관련 Cube view 식별")

  subgraph Loop["Iterative Reasoning Loop"]
    direction TB
    QueryGen("<b>쿼리 생성</b><br>measure · dimension · filter 선택")
    Execute("<b>Cube 실행</b><br>MCP → Cube REST API 호출")
    Inspect("<b>결과 확인</b><br>오류 여부 · 결과 유효성 판단")
  end

  Output("<b>결과 반환</b><br>차트 · 표 · 인사이트 도출")

  User --> Context --> QueryGen
  QueryGen --> Execute --> Inspect
  Inspect -->|"쿼리 오류? 필드 수정 후 재시도"| QueryGen
  Inspect -->|"완료"| Output

  style Loop fill:#e4f4fb,stroke:#5ab8e8,color:#1a1a1a

  classDef userNode fill:#fde8e4,stroke:#e8503a,color:#1a1a1a
  classDef contextNode fill:#fdf8e4,stroke:#f0a830,color:#1a1a1a
  classDef loopNode fill:#ffffff,stroke:#5ab8e8,color:#1a1a1a
  classDef outputNode fill:#e4f4ec,stroke:#4cb87a,color:#1a1a1a

  class User userNode
  class Context contextNode
  class QueryGen,Execute,Inspect loopNode
  class Output outputNode

```



예를 들어 measure/dimension 위치가 잘못된 경우 자동 보정 후 재실행하고, 존재하지 않는 필드를 요청하면 해당 view의 전체 필드 목록을 반환해 에이전트가 다시 선택할 수 있게 합니다.

agentic loop를 벤치마크에 적용했을 때, LQLS는 68.3%에서 91.7%로, LQHS는 58.0%에서 70.0%로 올랐습니다. LQHS가 덜 오른 건 description이 충분하지 않았기 때문입니다. `has_premium = 1`처럼 필드 이름만 봐선 알 수 없는 조건은 description에 비즈니스 맥락이 담겨 있다면 에이전트가 더 정확하게 추론할 수 있습니다.

### 비즈니스 인사이트로 이어지는 분석

HeartCount 2.0에서는 쿼리 조회 결과만 돌려주지 않습니다. 차트와 표를 함께 보여주고, driver/lever 기반의 다음 분석과 액션을 제안합니다. 사용자가 결과를 다른 도구로 옮기지 않아도 바로 검토하고, 다음 질문으로 이어갈 수 있습니다.

image (4).pngimage (2).png

## 앞으로의 과제

지금 구조는 실제로 동작하지만, 아직 개선해야 할 부분이 남아있습니다.

**시맨틱 레이어 자체가 노동집약적입니다.**
Cube, dbt Semantic Layer, LookML 모두 dimensions, measures, join 경로, 집계 로직을 수작업으로 정의해야 합니다. 스키마가 바뀌면 관련 정의도 함께 수정해야 하고, 잘못된 로직이 있어도 별다른 오류 없이 결과가 반환됩니다. [dbt 2025 설문](https://www.getdbt.com/resources/state-of-analytics-engineering-2025#download-the-report)에 따르면 AI 기반 데이터 질의 환경에서 시맨틱 레이어를 쓰는 곳은 3분의 1에 불과합니다. 나머지 3분의 2는 여전히 raw SQL 생성을 씁니다. “한 번 정의하면 어디서나”라는 약속과 달리, 실제로는 초기 구축, 유지보수, 마이그레이션에 드는 숨은 비용이 큽니다.

**비즈니스 맥락은 시맨틱 레이어 밖에서 관리해야 합니다.**

팀마다 지표를 해석하는 방식이 다르고, 같은 KPI라도 상황에 따라 봐야 할 driver와 lever가 달라집니다. 이런 맥락을 semantic layer 안에 모두 넣으면 관리가 어려워지고 구조도 빠르게 복잡해집니다. KPI 정의와 분석 맥락은 협업하고 확장하기 쉬운 별도 구조로 관리해야 합니다.

## 마치며

벤치마크를 통해 Semantic Layer가 AI Agent에 더 나은 데이터 인터페이스라는 점을 확인했습니다. HeartCount 2.0은 그 위에서 실제 비즈니스 분석 워크플로를 구현하려는 다음 단계의 시도입니다. 데이터 팀의 역할이 쿼리 작성에서 지표 정의와 분석 경로 설계로 이동하는 변화의 시작점이기도 합니다.

## 부록: 실험 설정

- **비교 대상**: Cube `/meta` 기반 JSON 쿼리 vs. 전체 PostgreSQL DDL 기반 SQL 생성
- **모델**: gpt-5.3-chat-latest, few-shot 예시 3개
- **반복 횟수**: 질문 43개, 각 5회 반복
- **평가 방식**: 실행 성공률, Strict Exact, Cell F1
- **Cube 모델**: 9개 기반 cube 위에 단일 public view

