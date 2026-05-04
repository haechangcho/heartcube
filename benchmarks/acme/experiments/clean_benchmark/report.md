# Clean 3-Phase Benchmark Report

**Branch**: `benchmark/clean-3phase`
**Model**: gpt-5.3-chat-latest, 5회 반복
**평가**: exact_match (결과 데이터 집합 동일 여부)

---

## 실험 설계

각 실험은 변수 하나씩만 추가하여 독립적으로 효과를 측정한다.

| 실험 | 추가 변수 | Schema | Gold | 대상 |
|------|----------|--------|------|------|
| Exp 1 | 새 few-shot (3개) | V1 | V1 | 전체 43문 |
| Exp 2 | + Agentic loop | V1 | V1 | Exp1 실패 9문 |
| Exp 3 | + Schema 설계 개선 | V2 | V2 | Exp2 실패 8문 |

**Few-shot**: DDL 벤치마크와 동일하게 3개, aggregate 2개 + listing 1개
**Schema V1**: `party_identifier + party_role_code` in acme_ops view
**Schema V2**: `policyholder_id + agent_id`, `acme_policy_parties` self-join cube 추가

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
| LQLS_06 | 0% | 0% | → 유지 |
| HQHS_08 | 0% | 0% | → 유지 |

**핵심 발견**: 모든 실패가 `att=1` (retry 미발동).
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
| LQLS_06 | 0% | 40% | ↑ 부분 | policyholder_id로 개선, 잔여 비일관성 |
| LQHS_06 | 60% | 60% | → 유지 | "have had a claim" 패턴 미해결 |
| HQHS_08 | 0% | 0% | → 유지 | 아래 분석 참고 |

---

## 잔여 실패 분석

### LQLS_06 (40%): "What are all the premiums that have been paid by policy holders?"

Gold V2: `{"dimensions": ["policyholder_id"], "measures": ["total_policy_amount"], "filters": [has_premium=1]}`

모델이 3/5 iteration에서 `policyholder_id` 대신 `policy_number`를 dimension으로 사용하거나 불필요한 필드를 추가함. Schema 개선 후 부분 개선됐으나 비일관 잔존.

### LQHS_06 (60%): "Return agents and the policy they have sold that have had a claim..."

"have had a claim" 표현이 `company_claim_number` dimension 추가를 유발 (gold에 없음). Few-shot Example 2가 이 패턴을 완전히 제거하지 못함. 비일관 40% 잔존.

### HQHS_08 (0%): "What is the loss ratio of each policy and agent who sold it?"

Gold V2: `{"dimensions": ["policy_number", "agent_id"], "measures": ["total_full_loss_amount", "total_policy_amount"], "filters": [has_premium=1]}`

모델이 `total_full_loss_amount / total_policy_amount` 비율을 별도 계산하려 시도하거나 measures를 잘못 선택. 이는 Cube 쿼리 내에서 ratio를 표현하는 패턴에 대한 이해 부족.

---

## 전체 비교 테이블

실험별 효과를 전체 43문 기준으로 환산:

| | LQLS | LQHS | HQLS | HQHS | 전체 |
|--|------|------|------|------|------|
| Exp 1 (단일 쿼리) | 91.7% | 68.0% | 96.4% | 88.0% | 85.6% |
| Exp 2 (+Agentic) | 91.7% | 72.0%* | **100%** | 88.0%* | 86.7%* |
| Exp 3 (+Schema) | 93.3%* | **88.0%** | 100%* | 90.0%* | **91.4%*** |

*Exp2/3 미실행 질문은 Exp1 결과 유지로 계산

---

## 핵심 인사이트

### 1. Agentic Loop는 execution error에서만 효과
실패 9개 질문이 모두 `att=1` — retry가 한 번도 발동되지 않았다. 현재 구조에서 loop는 실행 오류를 잡을 뿐, **정답을 실행하지만 틀린 데이터를 반환하는 semantic error는 감지하지 못한다**.

### 2. Schema 설계가 정확도를 결정
`party_identifier + party_role_code` 조합을 AI에게 노출하면 모델이 역할 구분 패턴을 학습하지 못한다. `policyholder_id`, `agent_id`로 역할을 필드 이름에 인코딩하자 관련 5개 질문이 100%로 수렴했다. **AI가 추론해야 하는 것이 있다면 Semantic Layer 설계가 덜 된 것이다**.

### 3. 잔여 실패는 다른 레이어의 문제
- LQLS_06, LQHS_06: few-shot 개선으로 일부 해결 가능 (모델 비일관 패턴)
- HQHS_08: ratio 계산 패턴 — Cube 쿼리 내에서 두 measure의 비율을 표현하는 방법을 모델이 모름

---

## 파일 목록

| 파일 | 설명 |
|------|------|
| `results/exp1_single_shot.csv` | 43문 × 5회 = 215건 |
| `results/exp2_agentic_loop.csv` | 9문 × 5회 = 45건 |
| `results/exp3_schema_fix.csv` | 8문 × 5회 = 40건 |
| `questions/cube_questions_v1.md` | V1 gold (party_identifier) |
| `questions/cube_questions_v2.md` | V2 gold (policyholder_id) |
| `scripts/exp1_single_shot.py` | Exp 1 실행 스크립트 |
| `scripts/exp2_agentic_loop.py` | Exp 2 실행 스크립트 |
| `scripts/exp3_schema_fix.py` | Exp 3 실행 스크립트 |
