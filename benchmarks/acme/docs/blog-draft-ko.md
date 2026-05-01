# LLM을 위한 데이터 인터페이스로서의 시맨틱 레이어 — Cube로 다시 검증하다

> 초안 — robust 평가 지표로 전체 벤치마크 재실행 완료.

---

2023년 말, dbt Roundup에 LLM과 엔터프라이즈 데이터의 교차점에서 일하는 사람이라면 누구나 주목했을 글이 올라왔다. Jason Ganz가 data.world의 ACME 벤치마크를 dbt Semantic Layer로 재현하면서, 구조화된 시맨틱 컨텍스트가 LLM 쿼리 정확도를 극적으로 높인다는 것을 보여준 것이다.

원 논문의 수치는 무시하기 어려웠다:

| 접근 방식 | 정확도 |
|---|---:|
| GPT-4 + 원본 DDL SQL | 16.7% |
| GPT-4 + 지식 그래프 (SPARQL) | 54.2% |
| dbt Semantic Layer (HQLS 서브셋) | 83% |

시맨틱 레이어가 LLM 인터페이스로 충분히 가치 있다는 주장을 뒷받침하는 숫자다. 그런데 방법론 안에 묻혀 있는 범위 제한이 하나 있다. 이 글은 그 제한이 어디서 시작되는지를 출발점으로 삼는다.

---

## 범위 제한

dbt Roundup 실험은 명시적으로 HQLS 서브셋 — "질문 복잡도 높음, 스키마 복잡도 낮음" — 에 집중했고, 구체적으로는 지표(metric) 중심 질문들만 테스트했다. 세 개 질문은 당시 MetricFlow가 지원하지 못하는 조인이 필요해서 제외됐고, 11개 중 8개 질문만 실행됐다.

dbt 팀이 그렇게 범위를 잡은 건 옳은 결정이었다. 그들은 dbt Semantic Layer가 설계된 목적, 즉 문서화된 리니지와 자연어 설명이 달린 지표와 비즈니스 KPI를 테스트하고 있었다. 83%라는 결과가 의미 있는 이유는 정확히 그 도구의 설계 범위 안에서 측정됐기 때문이다.

그런데 전체 ACME 벤치마크는 2×2 매트릭스에 걸쳐 44개 질문을 담고 있다:

|  | 스키마 복잡도 낮음 | 스키마 복잡도 높음 |
|---|---|---|
| **질문 복잡도 낮음** | LQLS (12개) | LQHS (10개) |
| **질문 복잡도 높음** | HQLS (11개) | HQHS (11개) |

그리고 이 질문들이 전부 지표를 묻는 건 아니다. 많은 질문이 차원 목록을 요구하고, 일부는 로우 레벨 엔티티 조회를 요구한다 — "이 계약자가 접수한 클레임을 모두 보여줘." 이런 질문들은 지표 쿼리가 아니고, 지표 전용 인터페이스로 테스트하는 건 범주 오류다.

이 글이 탐구하는 건 그 간극이다.

---

## 무엇을 테스트했나

같은 벤치마크를 [Cube](https://cube.dev)로 재현했다. Cube는 dbt Semantic Layer와 시맨틱 레이어의 노출 면적이 다르다. MetricFlow의 지표 중심 DSL 대신, Cube는 다음 요소들을 API로 노출한다:

- **dimensions** — 타입과 이름이 있는 스칼라 속성
- **measures** — 타입, SQL, 설명이 정의된 집계
- **filters** — 어떤 dimension이나 measure 멤버에도 걸 수 있는 구조화된 조건
- **join paths** — LLM에게 숨겨져 있음; public view를 통해서만 표면에 드러남
- **public views** — 외부 호출자에게 노출하는 큐레이션된 크로스 큐브 프로젝션

쿼리 형식은 JSON 객체다:

```json
{
  "query": {
    "dimensions": ["acme_ops.policy_number", "acme_ops.party_full_legal_name"],
    "measures": ["acme_ops.total_policy_amount"],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": ["PH"]
      }
    ]
  }
}
```

LLM은 `acme_ops` public view만 본다 — 이름이 붙은 dimensions와 measures의 큐레이션된 목록. 테이블 이름, 조인 조건, 판별자 컬럼은 보이지 않는다. 시맨틱 레이어가 JSON 쿼리를 내부적으로 SQL로 변환한다.

비교 트랙은 전체 PostgreSQL DDL을 컨텍스트로 주고 LLM에게 원본 SQL을 생성하게 한다.

두 트랙 모두 GPT-4o로 제로샷 프롬프팅을 사용한다.

---

## 벤치마크 설계

소스는 data.world 논문과 동일한 ACME 보험 데이터셋(OMG Property & Casualty 표준)이다. Q44가 Q42의 중복이어서 제외하고, 43개 질문으로 벤치마크를 실행했다.

각 질문은 두 가지 렌즈로 분류된다:

**원본 2×2 카테고리** (소스 논문 기준):
- LQLS: 단순 질문, 단순 스키마
- LQHS: 단순 질문, 복잡한 스키마
- HQLS: 복잡한 질문, 단순 스키마
- HQHS: 복잡한 질문, 복잡한 스키마

**답변 형태(Answer Shape)** (이번 재현에서 추가):

| Answer Shape | 설명 | 예시 |
|---|---|---|
| `aggregate` | 지표 또는 KPI | "계약별 보험료 합계는?" |
| `dimension_listing` | 집계 없는 차원 값 목록 | "클레임 번호, 접수일, 종결일 전체 목록" |
| `entity_row_retrieval` | 특정 엔티티로 필터링된 로우 | "계약자 ID 1의 클레임 전부 보여줘" |
| `entity_resolution_required` | 이름/별칭을 엔티티로 해석해야 함 | "Mary Policy Holder의 클레임 전부" |

Answer Shape 렌즈가 중요한 이유는, dbt SL이 `entity_row_retrieval` 쿼리를 서비스하도록 설계된 적이 없고, 지표 전용 인터페이스로 그런 질문을 테스트하는 건 범주 오류이기 때문이다.

채점은 실제 DB 실행 결과를 골드 쿼리와 비교한다. 기본 표에는 strict result F1과 exact match를 유지하되, projection 차이가 중요한 경우에는 subset match, projection F1, cell F1을 함께 본다. 이 구분은 ER 확장에서 특히 중요해진다.

---

## 결과: 43개 질문, 5회 반복

### 전체 퍼널

| 트랙 | 파싱 성공률 | 실행 성공률 | Strict Exact | Result F1 | Subset Match | Projection F1 | Cell F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cube SL | 100.0% | 100.0% | **85.1%** | 85.1% | 88.4% | 95.1% | 94.1% |
| Raw DDL SQL | 100.0% | 73.0% | **29.3%** | 29.3% | 29.3% | 43.5% | 42.2% |

격차는 상당하다: **85.1% vs. 29.3% strict exact**. 파싱 성공률은 동일하다 — GPT-4o는 두 형식 모두 문법적으로 유효한 결과물을 안정적으로 만들어낸다. 차이는 실행 성공률과 결과 정확도에서 난다.

DDL 트랙의 73.0% 실행 성공률은 원 논문도 관찰한 패턴을 반영한다: LLM은 정규화된 스키마에서 조인 경로 탐색에 취약하다. ACME 스키마에는 판별자 테이블(`acme_loss_payment`, `acme_expense_payment`), 멀티롤 당사자 테이블(`party_role_code`가 있는 `acme_agreement_party_role`), 동일 엔티티로 가는 여러 경로가 있다. GPT-4o는 필요한 조인을 빠뜨리거나 집계 그루핑을 잘못 적용하는 경우가 잦았다.

새 평가 지표를 추가해도 결론은 바뀌지 않는다. Cube는 strict exact보다 subset match가 조금 높다(85.1% → 88.4%). 일부 질문에서 gold answer는 포함했지만 추가 컬럼이 붙은 경우가 있기 때문이다. 반면 DDL은 subset match도 exact와 동일한 29.3%다. 실패가 단순 projection 차이가 아니라 조인 경로, 필터, 집계 로직 오류인 경우가 많다는 뜻이다.

Cube는 이 모든 걸 숨긴다. LLM이 할 일은 public view에서 올바른 dimensions와 measures를 고르는 것뿐이다.

### 원본 카테고리별

| 카테고리 | Cube Strict Exact | DDL Strict Exact | Cube Subset | DDL Subset | Cube Projection F1 | DDL Projection F1 |
|---|---:|---:|---:|---:|---:|---:|
| LQLS | 88.3% | 33.3% | 100.0% | 33.3% | 97.9% | 63.4% |
| LQHS | 70.0% | 10.0% | 70.0% | 10.0% | 85.9% | 10.7% |
| HQLS | 90.9% | 49.1% | 90.9% | 49.1% | 98.2% | 58.0% |
| HQHS | 90.0% | 22.0% | 90.0% | 22.0% | 97.5% | 36.4% |

몇 가지 눈에 띄는 점이 있다:

**HQLS와 HQHS가 Cube에서 가장 강한 카테고리다.** 이것들이 바로 지표 중심 질문들 — `total_policy_amount`, `avg_full_loss_amount`, `loss_payment_amount` 같은 measure들에 대한 집계. LLM이 이 질문들을 올바른 Cube 쿼리로 안정적으로 변환하고, measure 정의가 모델 안에 이미 들어 있기 때문에 실행도 정확하게 된다.

**LQHS가 Cube에서 가장 약한 카테고리로 70%다.** 격차는 멀티롤 질문에서 나온다. LQHS Q15, Q16은 계약자(policyholder)와 담당 에이전트를 동시에 같은 결과에 담아달라는 질문이다. 기반 데이터에서 `acme_agreement_party_role` 한 로우는 `party_role_code = 'PH'` 또는 `'AG'` 둘 중 하나다 — 셀프 조인 없이 두 역할을 Cube 한 로우에 담을 수 없다. LLM은 `party_role_code` 필터를 하나만 선택하는 경향이 있어 관계의 한쪽만 반환한다. LQHS 질문 5회 중 3회에서 구조는 맞지만 양쪽 역할이 필요한 상황에 한쪽 역할만 필터링했다.

**DDL LQHS는 10%로 최악이고, HQHS도 22%에 그친다.** LQHS에서는 복잡한 조인 경로가 실행 실패로 이어지는 경우가 많고, HQHS에서는 손해율, 비용 적립금, 다중 테이블 집계가 얽힌다. LLM이 모든 조인 경로, 모든 판별자, 모든 그루핑 키를 혼자 발견해야 한다. 이걸 동시에 전부 맞추는 경우는 드물다.

### Answer Shape별

| Answer Shape | n | Cube Strict Exact | DDL Strict Exact | Cube Subset | DDL Subset | Cube Projection F1 | DDL Projection F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `aggregate` | 105 | **90.5%** | 36.2% | 90.5% | 36.2% | 97.9% | 47.7% |
| `dimension_listing` | 110 | **80.0%** | 22.7% | 86.4% | 22.7% | 92.4% | 39.4% |

Answer Shape 렌즈는 중요한 사실을 드러낸다: Cube는 `aggregate` 질문에서 `dimension_listing`보다 강하다. 이는 설계 의도와 일치한다 — 잘 정의된 measure 시맨틱이 시맨틱 레이어의 핵심 가치 제안이다.

그러나 `dimension_listing` 결과도 DDL 베이스라인 22.7% 대비 80.0% strict exact, 86.4% subset match로 강하다. 차원 목록 질문도 집계 없이 Cube의 이름 붙은 멤버와 숨겨진 조인 경로의 혜택을 받는다. LLM은 어떤 dimensions를 선택할지만 알면 된다; 조인 그래프는 레이어가 처리한다.

---

## 더 어려워지는 영역: 엔티티 조회와 이름 해석

43개 핵심 질문에는 이름 기반 엔티티 조회가 없다. 예를 들어 "Mary Policy Holder의 클레임 전부"처럼 사람 이름을 필터 값으로 해석해야 하는 질문은 소스 벤치마크에 없다.

그러나 데이터 모델에 Party/Person 레이어가 있으면 벤치마크 스키마는 엔티티 조회를 표현할 수 있다. 우리는 그 확장을 구축했다.

ACME 데이터셋에는 이름과 성이 있는 `Person.csv`가 있다. 스키마 구조는 다음과 같다:

```
acme_claim
  → acme_claim_coverage
  → acme_policy_coverage_detail
  → acme_policy
  → acme_agreement_party_role (party_role_code: PH / AG)
  → acme_party
  → acme_person (first_name, last_name, full_legal_name)
```

이 조인 경로를 Cube로 모델링하고 `acme_ops`를 통해 노출하면, 이런 쿼리가 표현 가능해진다:

```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.policy_number",
      "acme_ops.party_full_legal_name"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": ["PH"]
      },
      {
        "member": "acme_ops.party_full_legal_name",
        "operator": "equals",
        "values": ["Mary Policy Holder"]
      }
    ]
  }
}
```

4개 엔티티 조회 질문으로 벤치마크를 확장했다:

1. 계약자 ID 1의 클레임을 모두 보여줘.
2. Mary Policy Holder 이름의 계약자 클레임을 모두 보여줘.
3. Bob Insurance Agent가 판매한 계약을 모두 보여줘.
4. Bob Insurance Agent가 판매한 계약에 연결된 클레임을 모두 보여줘.

2번부터 4번까지는 LLM이 `party_full_legal_name` 필터를 올바르게 적용해야 한다. 처음에는 데이터에 존재하지 않는 이름인 "Peyton Manning" 질문도 넣었지만, 이는 이름 기반 조회보다 empty-result handling을 테스트하는 negative case에 가깝다. 양쪽 트랙 모두 빈 결과셋을 반환하면서 strict exact가 1이 되었고, ER 확장의 핵심 실패 모드인 person 조인과 role 필터 선택을 설명하는 데는 도움이 되지 않았다. 따라서 최종 ER 결과에서는 제외했다.

### ER 확장 결과 (4개 질문, 5회 반복)

엔티티 조회에서는 strict result exact만으로는 평가 신호가 너무 거칠다. 반대로 `company_claim_number` 같은 key 컬럼만 비교하면 컬럼 선택 품질을 완전히 놓친다. 그래서 ER 확장은 key 전용 지표를 쓰지 않고, 실행 결과를 세 가지 렌즈로 나눠 본다.

| 지표 | 무엇을 비교하나 | 의미 |
|---|---|---|
| Strict Exact | gold 결과셋과 생성 결과셋의 완전 일치 | 가장 보수적인 하한선 |
| Subset Match | gold 결과가 생성 결과 안에 포함되는지 | 추가 컬럼 때문에 생기는 false negative 완화 |
| Projection F1 | gold 컬럼 집합과 생성 컬럼 집합의 precision/recall/F1 | 필요한 컬럼을 고르고 불필요한 컬럼을 덜 붙였는지 |

추가로 cell F1을 함께 기록한다. 이는 전체 결과에서 `(컬럼명, 값)` 쌍의 overlap을 보는 부분 점수다. row 전체가 완전히 같아야만 점수를 주는 strict result F1보다, "대부분의 값은 맞았지만 projection이 다르다"는 상황을 더 잘 보여준다.

이 방식은 Text-to-SQL 평가 관행과도 맞다. Spider/WikiSQL/BIRD 계열은 SQL 구조 일치와 실행 결과 일치를 분리해서 보고, Defog SQL-Eval 같은 실무 벤치마크도 exact dataframe match와 subset match를 함께 사용해 alias, row order, 추가 컬럼 같은 무해한 차이를 따로 처리한다.

#### 세 지표가 갈라지는 예

실제 데이터로 비교한다. 질문: *"Mary Policy Holder의 클레임을 모두 보여줘"*

**Gold 결과 (2개 로우):**

| company_claim_number | claim_open_date | claim_close_date | policy_number | party_full_legal_name |
|---|---|---|---|---|
| 12312701 | 2019-01-15 | 2019-01-31 | 31003000336 | Mary Policy Holder |
| 12312702 | 2019-06-02 | 2019-06-27 | 31003000336 | Mary Policy Holder |

**생성된 Cube 쿼리 결과 (2개 로우, 다른 컬럼 선택):**

| company_claim_number | claim_open_date | claim_close_date | policy_number | catastrophe_name | policy_effective_date | … (13개 컬럼) |
|---|---|---|---|---|---|---|
| 12312701 | 2019-01-15 | 2019-01-31 | 31003000336 | Fire | 2015-01-01 | … |
| 12312702 | 2019-06-02 | 2019-06-27 | 31003000336 | Fire | 2015-01-01 | … |

*같은 클레임 번호를 찾아왔다. 그러나 gold는 5개 컬럼, 생성 쿼리는 13개 컬럼을 반환했다.*

---

**① Strict Exact**

각 로우를 `(컬럼명, 값)` 쌍의 집합으로 변환한 뒤, gold 집합과 생성 집합의 교집합을 구한다.

```
# Gold 로우 1을 집합으로 변환
gold_row1 = {
  ("company_claim_number", "12312701"),
  ("claim_open_date",      "2019-01-15"),
  ("claim_close_date",     "2019-01-31"),
  ("policy_number",        "31003000336"),
  ("party_full_legal_name","Mary Policy Holder"),
}  # 5개 쌍

# 생성 로우 1을 집합으로 변환
gen_row1 = {
  ("company_claim_number",   "12312701"),
  ("claim_open_date",        "2019-01-15"),
  ("claim_close_date",       "2019-01-31"),
  ("policy_number",          "31003000336"),
  ("catastrophe_name",       "Fire"),
  ("policy_effective_date",  "2015-01-01"),
  …                          # 13개 쌍
}

# 두 집합이 같은가?
gold_row1 == gen_row1  →  False  (컬럼 수도, 쌍의 내용도 다름)
```

gold 로우 1과 생성 로우 1이 같은 `company_claim_number`를 갖고 있어도, 집합이 다르므로 동일 로우로 인정되지 않는다. 두 로우 모두 불일치 → 교집합 = 0개.

```
result_f1    = 0 / 2 = 0.0
exact_match  = 0          (gold_set ≠ gen_set)
```

strict exact 기준에서는 실패다. 같은 클레임을 찾아왔더라도 row의 전체 shape가 다르기 때문이다.

---

**② Subset Match**

이번에는 gold 컬럼들을 기준으로 생성 결과를 projection한 뒤 비교한다. 생성 결과가 gold보다 넓더라도, gold가 요구한 컬럼과 값 조합을 포함하면 통과한다.

```
# 생성 결과에서 gold 컬럼만 남긴다
project(gen_rows, gold_columns)

# projection한 생성 결과가 gold 결과를 포함하는가?
gold_rows ⊆ projected_gen_rows
```

```
subset_match = 0
```

이 예시에서는 `party_full_legal_name`이 생성 결과에 없으므로 subset match도 실패한다. 만약 생성 결과가 gold의 모든 컬럼과 값을 포함한 상태에서 추가 컬럼만 더 붙였다면 subset match는 성공하고 projection F1에서만 벌점을 받았을 것이다.

---

**③ Projection F1**

```
gold_columns = {
  company_claim_number,
  claim_open_date,
  claim_close_date,
  policy_number,
  party_full_legal_name
}

gen_columns = {
  company_claim_number,
  claim_open_date,
  claim_close_date,
  policy_number,
  catastrophe_name,
  policy_effective_date,
  ...
}
```

gold 컬럼 대부분을 포함했더라도 생성 컬럼이 지나치게 넓으면 precision이 낮아진다. 따라서 subset match는 "답을 포함했는가"를 보고, projection F1은 "반환 모양이 얼마나 절제되어 있는가"를 본다. 둘 중 하나만으로는 충분하지 않다.

---

**결과 표는 세 지표를 함께 읽는다.**

ER 확장에서는 strict exact와 subset match가 모두 0.0%다. 어느 트랙도 gold 결과를 완전히 재현하거나 포함하지는 못했다. 그러나 projection/cell F1은 실패의 질을 다르게 보여준다.

| 트랙 | 파싱 성공률 | 실행 성공률 | Strict Exact | Subset Match | Projection F1 | Cell F1 |
|---|---:|---:|---:|---:|---:|---:|
| Cube SL | 100.0% | 100.0% | 0.0% | 0.0% | 56.1% | 56.1% |
| Raw DDL SQL | 100.0% | 100.0% | 0.0% | 0.0% | 9.1% | 9.1% |

strict exact와 subset match만 보면 두 트랙이 동점처럼 보인다. 그러나 projection/cell F1을 보면 실패 양상이 다르다. Cube는 올바른 멤버를 일부 고르지만 gold projection을 완전히 맞추지 못한다. DDL은 이름 기반 조회에서 `acme_person` 조인과 role 필터를 놓치면서 필요한 컬럼/값 overlap 자체가 크게 떨어진다.

따라서 이 확장은 "엔티티 키 하나만 맞췄는가"가 아니라, **답 포함 여부와 반환 컬럼 품질을 동시에 본다.**

질문별 projection/cell F1 breakdown도 같은 방식으로 읽어야 한다:

| 질문 | Cube Projection F1 | DDL Projection F1 | 주된 실패 모드 |
|---|---:|---:|---|
| 계약자 ID 1의 클레임 | 59.8% | 36.3% | ID 조회라 조인 부담은 낮지만 projection 차이가 남음 |
| Mary Policy Holder의 클레임 | 61.5% | 0.0% | 이름 → person 조인 필요 |
| Bob Insurance Agent가 판매한 계약 | 66.7% | 0.0% | agent role과 person 조인 필요 |
| Bob Insurance Agent 관련 클레임 | 36.4% | 0.0% | person 조인 + 클레임 체인 필요 |

DDL의 어려움은 예상과 일치한다: 이름 기반 조회는 `acme_person` 테이블과 role 필터를 스스로 발견해야 한다. Cube는 `party_full_legal_name`이 이름 붙은 dimension으로 노출되어 있어 조인 경로 탐색 부담이 줄어든다. 최종 수치는 strict exact 하나가 아니라 subset match, projection F1, cell F1을 함께 보고 해석한다.

---

## "접수한"은 쿼리 문제가 아니라 모델링 문제다

한 가지 짚고 넘어갈 것이 있다: "누군가가 접수한 클레임 전부" 같은 질문에는 모호한 동사가 들어 있다.

"접수한"은 다음 중 무엇을 의미할 수 있다:
- 그 사람이 클레임에 연결된 계약의 **계약자(policyholder)**다.
- 그 사람이 **클레임 제출자(claimant)** — 실제로 클레임을 신청한 당사자다.
- 그 사람이 다른 역할로 클레임에 연결된 당사자다.

ACME 스키마는 클레임 → 계약 → 계약 당사자 역할 → 당사자를 연결한다. 이는 "클레임에 연결된 계약의 계약자"를 포착한다. 클레임 레벨 당사자 역할이 모델링되어 있지 않으면 "클레임을 제출한 사람"을 자동으로 포착하지 않는다.

> 시맨틱 레이어는 그것이 모델링한 비즈니스 관계만큼만 정확할 수 있다. "접수한"이 "연결된 계약의 계약자"를 의미한다면 Cube가 그걸 노출할 수 있다. "클레임을 제출한 사람"을 의미한다면 그 관계가 먼저 기반 데이터에 있어야 한다.

이건 명시적으로 짚어야 할 중요한 제약이다. LLM이 생성한 쿼리는 데이터 모델이 표현할 수 있는 것을 반환한다 — 모델에 없는 관계를 만들어낼 수 없다.

---

## Cube 접근 방식이 바꾸는 것

비교 트랙(raw DDL SQL)은 LLM에게 다음을 요구한다:

1. 정규화된 스키마에서 올바른 테이블 식별
2. 조인 경로 탐색과 올바른 조인 조건 적용
3. 판별자 필터 적용 (예: `party_role_code = 'PH'`)
4. Measure 정의 도출 (예: 손해율 = total_full_loss_amount / total_policy_amount)
5. 올바른 그루핑 키 선택
6. 유효한 SQL 문법 생성

각 단계가 독립적인 실패 포인트다.

Cube 접근 방식은 이 책임들 대부분을 모델 안으로 이동시킨다:

| 책임 | Raw DDL | Cube SL |
|---|---|---|
| 테이블 탐색 | LLM | 모델 안에 숨겨짐 |
| 조인 경로 | LLM | Cube가 해결 |
| 판별자 필터 | LLM | 이름 붙은 dimension으로 노출 (`party_role_code`) |
| Measure 정의 | LLM | YAML에 미리 정의됨 |
| 그루핑 | LLM | 선택된 dimensions에서 추론 |
| 컬럼 이름 | LLM이 추측 | 이름 붙은 멤버 |

LLM의 역할이 줄어든다: *이 이름 붙은 멤버 목록에서, 이 질문에 맞는 것을 골라라.* 이건 DDL 정의에서 조인 그래프를 추론하는 것보다 훨씬 쉬운 작업이다.

---

## 바뀌지 않는 것

명시적으로 짚어둘 중요한 한계들:

**ACME 데이터셋은 작고 합성된 것이다.** 보험 스키마는 합리적인 복잡도 대리재지만, 실제 프로덕션 스키마는 더 크고, 더 지저분하고, 종종 정규화가 덜 되어 있다. 프로덕션으로의 일반화는 실제 스키마로 테스트해야 한다.

**멀티롤 질문은 여전히 어렵다.** 계약자와 에이전트를 동일 결과셋에 보여줘야 하는 질문은 현재 Cube 모델이 팬아웃 없이 한 쿼리로 서비스할 수 없는 셀프 조인 패턴을 요구한다. 이건 Cube 특유의 버그가 아니라 구조적 제약이다.

**시맨틱 레이어는 운영 데이터 접근을 대체하지 않는다.** 시맨틱 레이어 쿼리 API는 분석 쿼리에 적합하다 — 로우 레벨 CRUD 인터페이스로 설계된 게 아니고, 분석 쿼리 레벨의 접근 제어는 트랜잭션 데이터 권한과 다르다.

**필터 값의 이름은 데이터에 존재해야 한다.** 이름 기반 조회는 단순히 "사람을 찾는" 엔티티 해석 문제가 아니다 — 데이터 모델에 그 사람의 레코드가 있는지의 문제이기도 하다. 시맨틱 레이어는 쿼리 구조를 표현할 수 있다; 데이터를 만들어낼 수 없다.

---

## 더 넓은 테제

dbt Roundup 실험은 시맨틱 컨텍스트가 LLM이 더 나은 지표 쿼리를 생성하게 돕는다는 것을 보여줬다. Cube 재현에서 그 결과는 네 가지 질문 카테고리와 두 가지 answer shape 모두에서 유지됐다.

더 흥미로운 발견은 구조적인 것이다: **Cube는 단일 거버넌스 인터페이스를 통해 여러 answer shape를 서비스할 수 있다**. 지표, 차원 목록, 엔티티 조회 모두 동일한 `acme_ops` public view, 동일한 JSON 쿼리 형식, 동일한 인가 모델을 통한다. LLM은 어떤 "종류"의 쿼리를 생성하는지 알 필요가 없다 — 그냥 이름 붙은 멤버를 고르면 된다.

이것이 "LLM을 위한 데이터 인터페이스로서의 시맨틱 레이어"의 더 넓은 버전이다. 지표만도 아니고, DDL SQL도 아닌. 조인 복잡도를 숨기고 LLM이 실제로 잘하는 것에 집중하게 해주는 이름 붙고, 문서화되고, 거버넌스된 표면 — 물어보는 질문에 맞는 개념을 고르는 것.

원래 dbt 실험이 지표에 집중한 건 틀린 게 아니었다. dbt SL이 노출하도록 설계된 부분을 테스트했던 것이다. 이 실험은 그 원칙이 일반화되는지를 테스트한다.

적어도 이 벤치마크 안에서는, 그렇다.

---

## 부록: 기술 설정

**Cube 모델**: 9개 기반 큐브 위에 단일 public view `acme_ops`. Dimensions에는 계약, 클레임, 당사자, 사람, 커버리지, 재해, 금액 데이터가 포함된다. Measures에는 보험료, 손해 구성요소, 클레임 기간에 대한 count, sum, avg 집계가 포함된다.

**벤치마크 스크립트**: Cube `/load` API를 호출하는 Python 스크립트와 DDL 트랙용 직접 PostgreSQL 연결. LLM 생성은 OpenAI API와 제로샷 프롬프팅. 결과는 골드 쿼리 실행과 비교해 strict result F1, exact match, subset match, projection F1, cell F1로 채점.

**모델**: GPT-4o, temperature 0.3.

**반복**: 질문당 5회 (Cube 총 215회 호출, DDL SQL 총 215회 호출).

**인프라**: Docker 위의 Cube (PostgreSQL 백엔드, `oda_benchmark` 스키마). 모든 벤치마크 코드는 [heartcube 레포지토리](https://github.com/haechangcho/heartcube) `benchmarks/acme/` 하위에 있다.

---

*모든 벤치마크 코드, 골드 쿼리, 결과 CSV, 스키마 정의는 레포지토리의 `benchmarks/acme/` 하위에 있다.*
