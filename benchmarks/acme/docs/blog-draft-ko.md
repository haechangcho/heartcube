# LLM을 위한 데이터 인터페이스로서의 시맨틱 레이어 — Cube로 다시 검증하다

> 초안 — ER 확장 실험 결과 대기 중 (벤치마크 실행 중). 미확정 수치는 **[ER-PENDING]** 으로 표시.

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
| `entity_resolution_required` | 이름/별칭을 엔티티로 해석해야 함 | "Peyton Manning이 접수한 클레임 전부" |

Answer Shape 렌즈가 중요한 이유는, dbt SL이 `entity_row_retrieval` 쿼리를 서비스하도록 설계된 적이 없고, 지표 전용 인터페이스로 그런 질문을 테스트하는 건 범주 오류이기 때문이다.

채점은 실제 DB 실행 결과를 골드 쿼리와 비교해 result F1과 exact match를 사용한다.

---

## 결과: 43개 질문, 5회 반복

### 전체 퍼널

| 트랙 | 파싱 성공률 | 실행 성공률 | Exact Match | Result F1 |
|---|---:|---:|---:|---:|
| Cube SL | 100.0% | 99.2% | **83.7%** | 83.7% |
| Raw DDL SQL | 100.0% | 75.2% | **29.5%** | 29.5% |

격차는 상당하다: **83.7% vs. 29.5% exact match**. 파싱 성공률은 동일하다 — GPT-4o는 두 형식 모두 문법적으로 유효한 결과물을 안정적으로 만들어낸다. 차이는 실행 성공률과 결과 정확도에서 난다.

DDL 트랙의 75% 실행 성공률은 원 논문도 관찰한 패턴을 반영한다: LLM은 정규화된 스키마에서 조인 경로 탐색에 취약하다. ACME 스키마에는 판별자 테이블(`acme_loss_payment`, `acme_expense_payment`), 멀티롤 당사자 테이블(`party_role_code`가 있는 `acme_agreement_party_role`), 동일 엔티티로 가는 여러 경로가 있다. GPT-4o는 필요한 조인을 빠뜨리거나 집계 그루핑을 잘못 적용하는 경우가 잦았다.

Cube는 이 모든 걸 숨긴다. LLM이 할 일은 public view에서 올바른 dimensions와 measures를 고르는 것뿐이다.

### 원본 카테고리별

| 카테고리 | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|
| LQLS | 83.3% | 33.3% | 83.3% | 33.3% |
| LQHS | 70.0% | 10.0% | 70.0% | 10.0% |
| HQLS | 90.9% | 51.5% | 90.9% | 51.5% |
| HQHS | 90.0% | 20.0% | 90.0% | 20.0% |

몇 가지 눈에 띄는 점이 있다:

**HQLS와 HQHS가 Cube에서 가장 강한 카테고리다.** 이것들이 바로 지표 중심 질문들 — `total_policy_amount`, `avg_full_loss_amount`, `loss_payment_amount` 같은 measure들에 대한 집계. LLM이 이 질문들을 올바른 Cube 쿼리로 안정적으로 변환하고, measure 정의가 모델 안에 이미 들어 있기 때문에 실행도 정확하게 된다.

**LQHS가 Cube에서 가장 약한 카테고리로 70%다.** 격차는 멀티롤 질문에서 나온다. LQHS Q15, Q16은 계약자(policyholder)와 담당 에이전트를 동시에 같은 결과에 담아달라는 질문이다. 기반 데이터에서 `acme_agreement_party_role` 한 로우는 `party_role_code = 'PH'` 또는 `'AG'` 둘 중 하나다 — 셀프 조인 없이 두 역할을 Cube 한 로우에 담을 수 없다. LLM은 `party_role_code` 필터를 하나만 선택하는 경향이 있어 관계의 한쪽만 반환한다. LQHS 질문 5회 중 3회에서 구조는 맞지만 양쪽 역할이 필요한 상황에 한쪽 역할만 필터링했다.

**DDL HQHS는 20%로 최악이다.** 손해율, 비용 적립금, 다중 테이블 집계가 얽힌 복잡한 질문들이다. LLM이 모든 조인 경로, 모든 판별자, 모든 그루핑 키를 혼자 발견해야 한다. 이걸 동시에 전부 맞추는 경우는 드물다.

### Answer Shape별

| Answer Shape | n | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|---:|
| `aggregate` | 63 | **90.5%** | 36.5% | 90.5% | 36.5% |
| `dimension_listing` | 66 | **77.3%** | 22.7% | 77.3% | 22.7% |

Answer Shape 렌즈는 중요한 사실을 드러낸다: Cube는 `aggregate` 질문에서 `dimension_listing`보다 강하다. 이는 설계 의도와 일치한다 — 잘 정의된 measure 시맨틱이 시맨틱 레이어의 핵심 가치 제안이다.

그러나 `dimension_listing` 결과도 DDL 베이스라인 22.7% 대비 77.3%로 강하다. 차원 목록 질문도 집계 없이 Cube의 이름 붙은 멤버와 숨겨진 조인 경로의 혜택을 받는다. LLM은 어떤 dimensions를 선택할지만 알면 된다; 조인 그래프는 레이어가 처리한다.

---

## 더 어려워지는 영역: 엔티티 조회와 이름 해석

43개 핵심 질문에는 이름 기반 엔티티 조회가 없다. "Peyton Manning이 접수한 클레임 전부"는 소스 벤치마크에 없다 — ACME 데이터셋에 Peyton Manning이라는 사람이 없기 때문이다.

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

5개 엔티티 조회 질문으로 벤치마크를 확장했다:

1. 계약자 ID 1의 클레임을 모두 보여줘.
2. Mary Policy Holder 이름의 계약자 클레임을 모두 보여줘.
3. Bob Insurance Agent가 판매한 계약을 모두 보여줘.
4. Bob Insurance Agent가 판매한 계약에 연결된 클레임을 모두 보여줘.
5. Peyton Manning이 접수한 클레임을 모두 보여줘.

4번, 5번은 LLM이 `party_full_legal_name` 필터를 올바르게 적용해야 한다. 데이터에 존재하지 않는 이름인 "Peyton Manning" 유형 — 은 이번 벤치마크 범위 밖이지만, 패턴 자체는 확립됐다.

### ER 확장 결과 (5개 질문, 3회 반복)

**[ER-PENDING — 벤치마크 실행 완료 후 실제 수치로 교체]**

| 트랙 | 실행 성공률 | Exact Match | Result F1 |
|---|---:|---:|---:|
| Cube SL | TBD | TBD | TBD |
| Raw DDL SQL | TBD | TBD | TBD |

예상 패턴: Cube는 실행 성공률이 100%에 가까워야 한다(`acme_person`으로의 조인 경로가 모델링되어 있고 `party_full_legal_name`이 이름 붙은 dimension이기 때문). DDL은 `acme_person` 조인을 빠뜨리거나 `full_legal_name` 컬럼을 잘못 참조할 가능성이 높다.

---

## "접수한"은 쿼리 문제가 아니라 모델링 문제다

한 가지 짚고 넘어갈 것이 있다: "Peyton Manning이 접수한 클레임 전부"에는 모호한 동사가 들어 있다.

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

**필터 값의 이름은 데이터에 존재해야 한다.** Peyton Manning 질문은 단순히 "사람을 찾는" 엔티티 해석 문제가 아니다 — 데이터 모델에 그 사람의 레코드가 있는지의 문제다. 시맨틱 레이어는 쿼리 구조를 표현할 수 있다; 데이터를 만들어낼 수 없다.

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

**벤치마크 스크립트**: Cube `/load` API를 호출하는 Python 스크립트와 DDL 트랙용 직접 PostgreSQL 연결. LLM 생성은 OpenAI API와 제로샷 프롬프팅. 결과는 골드 쿼리 실행과 비교해 result F1과 exact match로 채점.

**모델**: GPT-4o, temperature 0.3.

**반복**: 질문당 5회 (Cube 총 215회 호출, DDL SQL 총 215회 호출).

**인프라**: Docker 위의 Cube (PostgreSQL 백엔드, `oda_benchmark` 스키마). 모든 벤치마크 코드는 [heartcube 레포지토리](https://github.com/haechangcho/heartcube) `benchmarks/acme/` 하위에 있다.

---

*모든 벤치마크 코드, 골드 쿼리, 결과 CSV, 스키마 정의는 레포지토리의 `benchmarks/acme/` 하위에 있다.*
