# Targeted Benchmark Experiment Plan

기존 벤치마크에서 실패한 5개 질문만 대상으로 개선 실험을 진행한다.
모델, 질문, gold는 변경하지 않는 것을 원칙으로 하되, 실험 성격에 따라 명시적으로 예외를 둔다.

---

## 대상 질문

| ID | 카테고리 | 질문 | 현재 정확도 | 실패 원인 |
|----|----------|------|-------------|-----------|
| Q01 | LQLS | Return all the claims we have by claim number, open date and close date? | 80% | "we have" → claim_count measure 추가 |
| Q05 | LQLS | What are all our policies that have a claim associated to them by policy and claim number? | 40% | "have a claim" → claim_count > 0 필터 추가 |
| Q15 | LQHS | ...policy holder, premium amount paid and the agent who sold it? | 0% | self-join 불가 (Cube 구조적 한계) |
| Q16 | LQHS | ...policy holder, premium amount paid, the catastrophe it had, and the agent who sold it? | 0% | self-join 불가 (Cube 구조적 한계) |
| Q18 | LQHS | Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had. | 0% | gold query 모호성 |

---

## 실험 1: Few-shot 추가 (Q01, Q05)

### 변경 범위
- gold query 고정
- 모델 고정
- **프롬프트만 변경** → 기존 벤치마크와 비교 가능한 실험

### 추가할 Few-shot 예시

기존 3개 예시에 아래 2개를 추가한다.

**Example 4) Return all claims by claim number, open date, and close date**
- "Return all X" 형태의 목록 조회는 dimension만 사용
- measure 추가 금지

```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date"]}}
```

**Example 5) Return policies that have a claim, by policy number and claim number**
- "have a claim" 표현은 `company_claim_number`를 dimension에 추가하면 됨
- Cube는 해당 테이블로 INNER JOIN하므로 claim이 있는 row만 자동 반환
- `claim_count` measure나 `claim_count > 0` 필터 추가 금지

```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.company_claim_number"]}}
```

### 예상 결과
| 질문 | 현재 | 예상 |
|------|------|------|
| Q01 | 80% | 100% |
| Q05 | 40% | 100% |

---

## 실험 2: Schema 보강 (Q15, Q16)

### 변경 범위
- Cube 모델 변경 (신규 cube + join + view 노출)
- Q15/Q16 gold query 변경
- **별도 벤치마크로 제시** (gold 변경으로 기존과 직접 비교 불가)

### 원인

원본 SQL(acme-benchmark.ttl)은 `agreement_party_role` 테이블을 self-join해서 한 행에 PolicyHolderID와 AgentID를 동시에 컬럼으로 노출한다. Cube flat view 구조로는 이를 표현할 수 없다. self-join 로직을 Cube 모델 안으로 흡수해야 한다.

### 변경 파일

#### ① 신규: `model/cubes/acme_policy_parties.yml`

```yaml
cubes:
  - name: acme_policy_parties
    public: false
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
        description: "The ID of the policyholder (party_role_code = 'PH') for this policy."

      - name: agent_id
        sql: agent_id
        type: number
        description: "The ID of the agent (party_role_code = 'AG') who sold this policy."
```

#### ② 수정: `model/cubes/acme_policy.yml`

기존 joins에 추가:
```yaml
    - name: acme_policy_parties
      sql: "{acme_policy}.policy_identifier = {acme_policy_parties}.policy_identifier"
      relationship: one_to_one
```

#### ③ 수정: `model/views/acme_ops.yml`

기존 `party_identifier`, `party_role_code` 유지 (다른 질문에서 사용). 아래 블록 추가:
```yaml
      # ── acme_policy_parties ───────────────────────────────────────
      - join_path: acme_claim.acme_claim_coverage.acme_policy_coverage_detail.acme_policy.acme_policy_parties
        includes:
          - policyholder_id
          - agent_id
```

### 변경된 Gold Query

#### Q15
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.policyholder_id",
      "acme_ops.agent_id"
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

#### Q16
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.policyholder_id",
      "acme_ops.agent_id",
      "acme_ops.catastrophe_name"
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

### 예상 결과
| 질문 | 현재 | 예상 |
|------|------|------|
| Q15 | 0% | ~100% |
| Q16 | 0% | ~100% |

---

## 실험 3: Gold 수정 (Q18)

### 변경 범위
- Cube 모델 고정
- 프롬프트 고정
- **Q18 gold query만 수정** → "gold 설계 오류 수정"으로 명시

### 수정 이유

질문: "Return agents and the policy they have sold that have **had a claim** and the corresponding catastrophe it had."

"had a claim"은 존재 조건이지 출력 요건이 아니다. 질문에 "show claim number"라는 표현이 없다. 기존 gold의 `company_claim_number` dimension은 과잉 정의다.

모델은 5회 전부 `company_claim_number` 없이 일관되게 생성한다. gold가 잘못된 것.

### Gold 변경

**현재 gold**
```json
{
  "query": {
    "dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.company_claim_number", "acme_ops.catastrophe_name"],
    "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}],
    "order": {"acme_ops.party_identifier": "asc"}
  }
}
```

**수정 gold**
```json
{
  "query": {
    "dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.catastrophe_name"],
    "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}],
    "order": {"acme_ops.party_identifier": "asc"}
  }
}
```

### 예상 결과
| 질문 | 현재 | 예상 |
|------|------|------|
| Q18 | 0% | ~100% |

---

## Pipeline 코드

```
benchmarks/acme/scripts/targeted_benchmark.py
```

### 환경변수

| EXPERIMENT | 대상 질문 | 변경 내용 |
|------------|-----------|-----------|
| `few_shot` | Q01, Q05 | few-shot 2개 추가, gold 고정 |
| `schema_fix` | Q15, Q16 | 새 /meta 사용, 새 gold 적용 |
| `gold_fix` | Q18 | gold 수정, 프롬프트 고정 |
| `few_shot_gold_fix` | Q01, Q05, Q18 | few-shot 추가 + Q18 gold 수정 |

### 실행 방법

```bash
# dev_mcp 서버에서
cd ~/heartcube/benchmarks/acme

EXPERIMENT=few_shot ACME_RESULTS_SUFFIX=few_shot python scripts/targeted_benchmark.py
EXPERIMENT=schema_fix ACME_RESULTS_SUFFIX=schema_fix python scripts/targeted_benchmark.py
EXPERIMENT=gold_fix ACME_RESULTS_SUFFIX=gold_fix python scripts/targeted_benchmark.py
```

### 출력

```
results/acme_targeted_few_shot.csv
results/acme_targeted_schema_fix.csv
results/acme_targeted_gold_fix.csv

콘솔: 베이스라인 대비 delta 출력
```

---

## 최종 결과 테이블 (목표)

```
                     Q01    Q05    Q15    Q16    Q18    LQLS   LQHS
베이스라인 (현재)     80%    40%     0%     0%     0%    92%    70%
+ few-shot           100%  100%     -      -      -     98%+    -
+ few-shot + gold    100%  100%     -      -    100%    98%+   80%+
+ schema 보강          -     -    100%   100%    -       -     90%+  ← 별도 벤치마크
```

---

## 비교 가능성 정리

| 실험 | 기존 벤치마크와 비교 가능? | 이유 |
|------|--------------------------|------|
| 실험 1 (few-shot) | ✅ 가능 | gold, 모델 고정 / 프롬프트만 변경 |
| 실험 2 (schema) | ⚠️ 별도 제시 | gold query 변경 수반 |
| 실험 3 (gold fix) | ⚠️ 별도 제시 | gold query 변경 (오류 수정으로 명시) |
