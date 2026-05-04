# Cube Benchmark 실패 분석

벤치마크 결과(`acme_cube_results.csv`) 기준으로 Cube Semantic Layer 방식의 실패 케이스를 분석한다.
모델: gpt-5.3-chat-latest, 반복: 5회, 평가: exact_match (결과 데이터 집합 동일 여부)

---

## 요약

| 카테고리 | 단일 쿼리 | Agentic loop |
|----------|-----------|--------------|
| LQLS (12문) | 68.3% | 91.7% |
| LQHS (10문) | 58.0% | 70.0% |

LQLS 실패: **Q01, Q05** (2문)
LQHS 실패: **Q15, Q16, Q18** (3문)

---

## LQLS 실패

### Q01 — "Return all the claims we have by claim number, open date and close date?"

**실패율**: 20% (5회 중 1회)

**Gold query**
```json
{
  "query": {
    "dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date"],
    "order": {"acme_ops.company_claim_number": "asc"}
  }
}
```

**생성된 query (iter3, 실패)**
```json
{
  "query": {
    "dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date"],
    "measures": ["acme_ops.claim_count"]
  }
}
```

**실패 원인**
"all the claims **we have**"에서 "we have"를 집계로 해석해 `claim_count` measure를 추가했다.
`claim_count`가 들어가면 GROUP BY가 걸리며 결과 데이터 구조가 달라진다.

**분류**: 컨텍스트 문제 (모델 비일관성)

**해결책**
- Few-shot 예시 추가: 목록 조회 질문에는 measure 불필요함을 명시
- "Return all X" 패턴은 dimension만 사용하는 예시

---

### Q05 — "What are all our policies that have a claim associated to them by policy and claim number?"

**실패율**: 60% (5회 중 3회)

**Gold query**
```json
{
  "query": {
    "dimensions": ["acme_ops.policy_number", "acme_ops.company_claim_number"],
    "order": {"acme_ops.policy_number": "asc"}
  }
}
```

**생성된 query (iter2~4, 실패)**
```json
{
  "query": {
    "dimensions": ["acme_ops.policy_number", "acme_ops.company_claim_number"],
    "measures": ["acme_ops.claim_count"],
    "filters": [{"member": "acme_ops.claim_count", "operator": "greaterThan", "values": ["0"]}]
  }
}
```

**실패 원인**
"**that have a claim**"을 SQL 방식으로 해석했다.

- SQL 사고방식: claim이 있는 policy만 가져오려면 `COUNT(*) > 0` 명시 필요
- Cube 동작 방식: `company_claim_number`를 dimension에 넣으면 해당 테이블로 INNER JOIN이 걸리면서 claim이 있는 row만 자동으로 반환됨. 별도 필터 불필요

모델의 접근이 틀린 게 아니다. SQL이었으면 맞는 방식이다. Cube의 implicit JOIN 동작을 모르는 것이 원인이다.

**분류**: 컨텍스트 문제 (Cube의 implicit JOIN 동작을 모름)

**해결책**
- Few-shot 예시 추가: "have a claim" 패턴에서 dimension 추가만으로 충분함을 보여주는 예시
- 시스템 프롬프트에 명시: "Cube에서 dimension을 추가하면 해당 테이블로 INNER JOIN이 걸린다. 존재 여부 필터는 별도로 추가하지 않아도 된다."

---

## LQHS 실패

### Q15 (LQHS #3) — "What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid and the agent who sold it?"

**실패율**: 100% (5회 전부)

**Gold query**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}],
    "order": {"acme_ops.company_claim_number": "asc"}
  }
}
```

**생성된 query (모든 반복)**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]},
      {"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}
    ]
  }
}
```

**실패 원인**
"policy holder ... **and** ... the agent who sold it" → PH와 AG를 동시에 요구하는 질문.

모델은 PH 필터 + AG 필터를 동시에 건다. AND 조건이라 결과가 0건이 된다.

Gold의 접근: `party_role_code`를 **filter가 아닌 dimension**으로 넣어 PH 행과 AG 행이 각각 출력되게 한다. 그리고 `has_premium = '1'` 필터만 건다.

그러나 이 gold query 자체도 원본 SQL 의도를 완전히 담지 못한다.

**원본 SQL (acme-benchmark.ttl)**
```sql
SELECT
    apr2.party_identifier as AgentID,
    apr1.party_identifier as PolicyHolderID,
    ...
FROM agreement_party_role apr1
INNER JOIN agreement_party_role apr2
  ON apr1.agreement_identifier = apr2.agreement_identifier
WHERE apr1.party_role_code = 'PH' AND apr2.party_role_code = 'AG'
```

원본 SQL은 `agreement_party_role`을 **self-join**해서 한 행에 PolicyHolderID와 AgentID를 동시에 컬럼으로 노출한다. Cube flat view 구조로는 같은 테이블을 두 역할로 self-join하는 것이 불가능하다.

**분류**: **Cube 구조적 한계** — any 프롬프트/description 개선으로 해결 불가

**해결책**
self-join 로직을 Cube 모델 안으로 흡수하는 신규 cube 추가:

```yaml
# model/cubes/acme_policy_parties.yml (신규)
cubes:
  - name: acme_policy_parties
    sql: >
      SELECT
        ph.agreement_identifier AS policy_identifier,
        ph.party_identifier     AS policyholder_id,
        ag.party_identifier     AS agent_id
      FROM oda_benchmark.acme_agreement_party_role ph
      INNER JOIN oda_benchmark.acme_agreement_party_role ag
        ON ph.agreement_identifier = ag.agreement_identifier
      WHERE ph.party_role_code = 'PH'
        AND ag.party_role_code = 'AG'

    dimensions:
      - name: policy_identifier
        sql: policy_identifier
        type: number
        primary_key: true
        public: false

      - name: policyholder_id
        sql: policyholder_id
        type: number
        description: "계약자 ID"

      - name: agent_id
        sql: agent_id
        type: number
        description: "이 policy를 판매한 agent ID"
```

이후 `acme_ops` view에 `policyholder_id`, `agent_id` 노출. Q15 gold query는 자연스럽게:

```json
{
  "dimensions": ["acme_ops.company_claim_number", "acme_ops.policy_number", "acme_ops.policyholder_id", "acme_ops.agent_id"],
  "measures": [...],
  "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}]
}
```

단, gold query 변경이 수반되므로 기존 벤치마크와 별도 실험으로 제시해야 한다.

---

### Q16 (LQHS #4) — "...policy holder, premium amount paid, the catastrophe it had, and the agent who sold it?"

Q15와 동일한 구조적 원인. `catastrophe_name` dimension이 추가된 버전.

**실패율**: 100% (5회 전부)

**생성된 query**: Q15와 동일 패턴 (PH+AG 동시 필터, has_premium 누락)

**해결책**: Q15와 동일 (`acme_policy_parties` 추가)

---

### Q18 (LQHS #6) — "Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had."

**실패율**: 100% (5회 전부)

**Gold query**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}],
    "order": {"acme_ops.party_identifier": "asc"}
  }
}
```

**생성된 query (모든 반복)**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.catastrophe_name"
    ],
    "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}]
  }
}
```

**실패 원인**
filter(party_role_code=AG)는 완벽하게 맞다. `company_claim_number`만 dimension에서 빠졌다.

질문이 "the policy **that have had a claim**"이라고 표현하여 claim을 존재 조건으로 기술한다. 모델은 claim number를 출력 컬럼으로 포함시키지 않았다. Gold는 claim number를 dimension에 포함시킨다.

이 케이스는 gold query 설계 자체가 다소 모호하다. 질문에 "show claim number"라는 표현이 없기 때문이다.

**분류**: Gold query 모호성 + 컨텍스트 문제

**해결책**
- Few-shot 예시: "have had a claim" → `company_claim_number`를 dimension에 포함
- 또는 gold query에서 `company_claim_number`를 제거하고 재평가 (질문 의도 재검토 필요)

---

## 실패 분류 요약

| 질문 | 실패율 | 원인 분류 | 해결 가능 여부 |
|------|--------|-----------|----------------|
| Q01 (LQLS) | 20% | 컨텍스트 (목록 조회에 measure 추가) | ✅ few-shot으로 해결 |
| Q05 (LQLS) | 60% | 컨텍스트 (Cube implicit JOIN 모름) | ✅ few-shot으로 해결 |
| Q15 (LQHS) | 100% | **Cube 구조적 한계** (self-join 불가) | ⚠️ schema 변경 필요 (별도 실험) |
| Q16 (LQHS) | 100% | **Cube 구조적 한계** (self-join 불가) | ⚠️ schema 변경 필요 (별도 실험) |
| Q18 (LQHS) | 100% | Gold 모호성 + 컨텍스트 | ✅ few-shot 또는 gold 재검토 |

---

## Agentic Loop 한계

현재 agentic loop는 **실행 오류(exec_ok=0)** 에서만 retry를 발동한다.

위 5개 실패 질문은 **모두 실행 성공(exec_ok=1)** 이다. 결과 데이터가 틀린 것이라 retry가 발동하지 않는다.

```
현재: 생성 → 실행 → 실행 오류? → retry
문제: Q01, Q05, Q15, Q16, Q18은 실행은 성공하지만 데이터가 틀림
```

**개선 방향**: 결과 검증 단계 추가
- 질문에 집계 표현이 없는데 measure가 포함된 경우 → retry 신호
- 예상 외 filter가 동일 member로 중복 적용된 경우 → retry 신호

---

## 비교 가능한 실험 설계

Schema 변경(Q15/Q16)은 gold query도 같이 바꿔야 하므로 기존 벤치마크와 직접 비교 불가.
아래는 **동일 벤치마크(gold 고정)** 위에서 비교 가능한 실험이다.

```
[A] Cube single-shot                    LQLS 68% / LQHS 58%
[B] A + agentic loop                    LQLS 92% / LQHS 70%
[C] B + few-shot 추가 (Q01/Q05/Q18)     LQLS ?   / LQHS ?
[D] C + result validation retry         LQLS ?   / LQHS ?

[E] schema 변경 (acme_policy_parties)   별도 벤치마크로 제시
    Q15/Q16 gold query 갱신 후 재실험
```

[C]와 [D]는 모델, 질문, gold query 모두 동일하므로 공정한 비교다.
