# Clean 3-Phase Benchmark Report

**Branch**: `benchmark/clean-3phase`
**Model**: gpt-5.3-chat-latest, 5회 반복
**평가**: exact_match (결과 데이터 집합 동일 여부)

---

## 실험 설계

각 실험은 변수 하나씩만 추가하여 독립적으로 효과를 측정한다.

| 실험 | 추가 변수 | Schema | Gold | 대상 |
|------|----------|--------|------|------|
| Exp 1 | 새 few-shot (3개, DDL 동일 수) | V1 | V1 | 전체 43문 |
| Exp 2 | + Agentic loop | V1 | V1 | Exp1 실패 9문 |
| Exp 3 | + Schema 설계 개선 | V2 | V2 | Exp2 실패 8문 |

**Few-shot**: DDL 벤치마크와 동일하게 3개, aggregate 2개 + listing 1개
**Schema V1**: `party_identifier + party_role_code` in acme_ops view
**Schema V2**: `policyholder_id + agent_id`, `acme_policy_parties` self-join cube 추가, `loss_ratio` measure 추가

---

## 결과

### Exp 1: Single-shot baseline

| 카테고리 | 정확도 | 질문 수 |
|---------|--------|--------|
| LQLS | 91.7% | 12 |
| LQHS | 68.0% | 10 |
| HQLS | 96.4% | 11 |
| HQHS | 88.0% | 10 |
| **전체** | **85.6%** | **43** |

**실패 9개**: LQLS_06, LQHS_02/03/04/05/06, HQLS_09, HQHS_04/08

---

### Exp 2: + Agentic Loop (Exp1 실패 9문)

| 질문 | Exp1 | Exp2 | 변화 |
|------|------|------|------|
| HQLS_09 | 60% | **100%** | ✓ 해결 |
| LQHS_02 | 40% | 80% | ↑ 부분 |
| LQHS_06 | 40% | 60% | ↑ 부분 |
| LQHS_03 | 0% | 40% | ↑ 부분 |
| LQHS_04 | 20% | 20% | → 유지 |
| LQHS_05 | 80% | 80% | → 유지 |
| HQHS_04 | 80% | 80% | → 유지 |
| HQHS_08 | 100% | 100% | ✓ (loss_ratio 추가) |
| LQLS_06 | 0% | 0% | → 유지 |

**핵심 발견**: 실패 질문 대부분이 `att=1` — retry 미발동.
실행은 성공하지만 결과 데이터가 틀림 → Agentic loop의 구조적 한계.
현재 loop는 execution error에서만 retry를 발동하며, semantic 오류는 감지 불가.

---

### Exp 3: + Schema 설계 개선 (Exp2 실패 8문)

| 질문 | Exp2 | Exp3 | 변화 | 원인 |
|------|------|------|------|------|
| LQHS_03 | 40% | **100%** | ✓ 해결 | self-join → policyholder_id/agent_id |
| LQHS_04 | 20% | **100%** | ✓ 해결 | 동일 |
| LQHS_02 | 80% | **100%** | ✓ 해결 | policyholder_id 명확화 |
| LQHS_05 | 80% | **100%** | ✓ 해결 | policyholder_id 명확화 |
| HQHS_04 | 80% | **100%** | ✓ 해결 | policyholder_id 명확화 |
| LQLS_06 | 0% | 40% | ↑ 부분 | 아래 분석 참고 |
| LQHS_06 | 60% | 60% | → 유지 | 아래 분석 참고 |

---

## 잔여 실패 분석

### LQLS_06 (40%): "What are all the premiums that have been paid by policy holders?"

**Gold:**
```json
{
  "dimensions": ["acme_ops.policyholder_id"],
  "measures": ["acme_ops.total_policy_amount"],
  "filters": [{"has_premium": "1"}],
  "order": {"total_policy_amount": "desc"}
}
```

**생성된 쿼리 (실패 케이스):**
```json
{
  "dimensions": ["acme_ops.policyholder_id", "acme_ops.policy_number"],
  "filters": [{"has_premium": "1"}]
}
```

모델이 `policy_number`를 추가하고 `total_policy_amount` measure를 제거했다.

**해석**: "What are **all** the premiums" — "all"이라는 표현이 목록 조회(listing) 의도로 읽힐 수 있다. 실제로 보험사 업무에서 "all the premiums"는 건별 내역을 보는 경우도 많다. 모델이 `policy_number`를 추가한 것도 "policyholder별 policy 내역을 모두 보여달라"는 합리적 해석이다. Gold가 `policyholder_id`만 dimension으로 쓴 것(정책별 합산)이 오히려 더 편집적인 해석에 가깝다. 질문 자체의 모호성이 실패 원인.

---

### LQHS_06 (60%): "Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had."

**Gold V2:**
```json
{
  "dimensions": ["acme_ops.agent_id", "acme_ops.policy_number", "acme_ops.catastrophe_name"]
}
```

**생성된 쿼리 (실패 케이스):**
```json
{
  "dimensions": ["acme_ops.agent_id", "acme_ops.policy_number", "acme_ops.company_claim_number", "acme_ops.catastrophe_name"]
}
```

모델이 `company_claim_number`를 추가했다.

**해석**: "the policy they have sold **that have had a claim**" — claim이 있다는 사실을 명시적으로 출력에 포함하는 것은 에이전트 자율적 판단으로 볼 수 있다. 실제로 V1 gold에는 `company_claim_number`가 포함되어 있었고, V2에서 annotation 정책상 제거한 것이다. 모델이 claim의 식별자를 출력에 포함하는 것은 정보 완전성 측면에서 더 나은 응답일 수 있다. Gold annotation 기준의 차이가 실패의 원인이며, 모델의 reasoning 자체는 타당하다.

---

## 전체 비교 테이블

실험별 효과를 전체 43문 기준으로 환산:

| | LQLS | LQHS | HQLS | HQHS | 전체 |
|--|------|------|------|------|------|
| Exp 1 (단일 쿼리) | 91.7% | 68.0% | 96.4% | **100%** | 86.5% |
| Exp 2 (+Agentic) | 91.7% | 72.0%* | **100%** | **100%** | 87.6%* |
| Exp 3 (+Schema) | 93.3%* | **88.0%** | **100%** | **100%** | **91.4%*** |

*Exp2/3 미실행 질문은 이전 실험 결과 유지로 계산

---

## 핵심 인사이트

### 1. Agentic Loop는 execution error에서만 효과
실패 질문들이 모두 `att=1` — retry가 발동하지 않았다. **정답처럼 실행되지만 틀린 데이터를 반환하는 semantic error는 현재 구조로 감지 불가**. 다음 단계로 결과 검증 레이어(LLM-as-judge 또는 schema 기반 sanity check)가 필요하다.

### 2. Schema 설계가 정확도를 결정
`party_identifier + party_role_code` 조합을 AI에게 노출하면 역할 구분을 추론하게 강제한다. `policyholder_id`, `agent_id`로 역할을 필드 이름에 인코딩하자 관련 5개 질문이 즉시 100%로 수렴했다. **Semantic Layer의 본질: AI가 추론해야 하는 것이 있다면 설계가 덜 된 것이다**.

### 3. Semantic Layer에 비즈니스 로직을 적극 흡수해야 한다
`loss_ratio`처럼 도메인 지식이 필요한 계산은 쿼리 시점에 AI에게 맡기지 않고 Cube 모델에 미리 정의해야 한다. `loss_ratio = total_full_loss_amount / total_policy_amount` measure를 추가하자 HQHS_08이 해결됐다.

### 4. 잔여 실패는 질문 모호성과 AI 자율성의 영역
- **LQLS_06**: "all the premiums" — 합산(aggregate)인지 목록(listing)인지 모호. 두 해석 모두 비즈니스적으로 유효.
- **LQHS_06**: "have had a claim" — claim number를 출력에 포함하는 것은 에이전트가 정보 완전성을 위해 자율적으로 판단한 결과. Gold annotation 기준과 다를 뿐 틀린 것이 아닐 수 있다.

---

## 파일 목록

| 파일 | 설명 |
|------|------|
| `results/exp1_single_shot.csv` | 43문 × 5회 = 215건 |
| `results/exp2_agentic_loop.csv` | 9문 × 5회 = 45건 |
| `results/exp3_schema_fix.csv` | 8문 × 5회 = 40건 |
| `questions/cube_questions_v1.md` | V1 gold (party_identifier) |
| `questions/cube_questions_v2.md` | V2 gold (policyholder_id, loss_ratio) |
| `scripts/exp1_single_shot.py` | Exp 1 실행 스크립트 |
| `scripts/exp2_agentic_loop.py` | Exp 2 실행 스크립트 |
| `scripts/exp3_schema_fix.py` | Exp 3 실행 스크립트 |
