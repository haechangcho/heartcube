# KPI Meta 구조화 설계

## 1. 문제 정의

`kpi.yml` view member의 `description`이 두 역할을 동시에 수행한다.

- **측정값 정의** ("지급결정금액 합계 ÷ 보험가입금액 합계") → cube 파일 소유
- **KPI 분석 컨텍스트** (목표·드라이버·레버) → kpi view 소유

kpi.yml의 `description`은 cube description을 override하므로 단순 제거할 수 없다.  
KPI 분석 컨텍스트를 `meta` 하위 구조화 필드로 이관하고, `description`을 제거해 cube 자동 상속으로 전환한다.

---

## 2. 설계 원칙

1. **meta 필드는 독립적이어야 한다** — 다른 cube member 이름을 직접 참조하지 않는다. member 이름이 바뀌어도 meta는 영향받지 않는다.
2. **driver/lever는 문자열 배열로 유지한다** — 사람과 LLM이 읽는 문서다. 구조화하면 편집 비용만 늘어난다.
3. **kpi는 처음부터 객체로** — `kpi: true` boolean에서 `kpi: {object}`로 나중에 바꾸는 것은 파괴적 변경이다. 처음부터 객체로 두면 새 속성 추가가 하위 호환적이다.

---

## 3. 스키마

### KPI measure
```yaml
- name: loss_ratio
  meta:
    kpi:
      visible: true    # 분석 노출 여부. 기존 kpi:true → true, Group B → false
      target: "40% 이하"
    driver:
      - dimension: accident_type_l1
        measure: claim_count
      - dimension: coverage_nm
        measure: avg_payment_amt
      - dimension: adjuster_id
        measure: claim_approval_rate
    lever:
      - action: "고위험 담보 인수기준 강화"
      - action: "과지급 탐지 강화"
      - action: "심사자 배당 정책 조정"
    pre_aggregation:
      time_dimension: payment_dt
      granularity: month
  # description/title 없음 → fact_accident.yml 자동 상속
```

### 비-KPI member
```yaml
# description 없음, meta 없음 → cube description 자동 상속
- accident_type_l1
- total_payment_amt
```

---

## 4. 필드 정의

### `meta.kpi` (object | 없음)
객체가 존재하면 KPI, 없으면 비-KPI. boolean 플래그를 별도로 두지 않는다.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `target` | string | 선택 | 목표치. 단위 포함. ex: `"95% 이상"`, `"5일 이내"` |

새 KPI 속성 추가 시 `kpi` 객체 안에 추가. 기존 소비자는 모르는 필드를 무시하므로 하위 호환 유지.

### `meta.driver` (string[] | 없음)
KPI 변화를 설명하는 분석 차원과 방법. `dimension — 분석방법` 패턴 권장, 강제하지 않음.  
NL2SQL 프롬프트에서 "어떤 dimension을 보면 원인을 찾을 수 있는가"의 힌트로 활용.

### `meta.lever` (string[] | 없음)
KPI 개선을 위한 비즈니스 액션 목록. 순수 문자열 배열.

### `meta.pre_aggregation` (object | 없음)
Cube 실행 힌트. KPI 분석 컨텍스트와 무관하므로 `kpi` 네임스페이스 밖에 유지.

---

## 5. /meta API 응답 형태

```json
{
  "name": "kpi.loss_ratio",
  "title": "손해율(%)",
  "description": "보험가입금액 대비 지급결정금액 비율. (← cube 자동 상속)",
  "meta": {
    "kpi": { "target": "40% 이하" },
    "driver": [
      "accident_type_l1 — 사고유형별 건수 추이",
      "coverage_nm — 담보별 payment_amt",
      "adjuster_id — 심사자별 인용율 편차"
    ],
    "lever": [
      "고위험 담보 인수기준 강화",
      "과지급 탐지 강화",
      "심사자 배당 정책 조정"
    ],
    "pre_aggregation": { "time_dimension": "payment_dt", "granularity": "month" }
  }
}
```

---

## 6. KPI 목록

| member | target | driver 수 | lever 수 |
|---|---|---|---|
| `loss_ratio` | 40% 이하 | 3 | 3 |
| `claim_approval_rate` | 85~90% | 3 | 3 |
| `review_reversal_rate` | — | 2 | 2 |
| `overpayment_rate` | 2% 이하 | 3 | 3 |
| `anomaly_rate` | — | 2 | 2 |
| `fraud_suspicion_rate` | 1% 이하 | 3 | 3 |
| `noninsured_ratio` | — | 3 | 3 |
| `review_rate` | 3% 이하 | 2 | 2 |
| `duplicate_payment_rate` | — | 2 | 2 |
| `error_payment_rate` | — | 2 | 2 |
| `sla_compliance_rate` | 95% 이상 | 4 | 3 |
| `avg_processing_days` | 5일 이내 | 3 | 2 |
| `payment_delay_rate` | — | 2 | 2 |
| `lawsuit_rate` | 1% 이하 | 2 | 2 |

`high_prior_claim_count`, `review_reversal_count` 등 나머지 member는 비-KPI. description 제거, meta 없음.

---

## 7. 마이그레이션 순서

```
1. KPI measure (14개)
   description 파싱 → meta.kpi / meta.driver / meta.lever 변환
   description 필드 제거

2. 비-KPI member (dimension, 참조 measure)
   description 필드 제거 (cube 자동 상속)
   가능하면 shorthand(- member_name)로 전환

3. /meta 응답 검증
   description이 cube 값으로 정상 상속되는지 확인
   meta 구조가 JSON으로 올바르게 직렬화되는지 확인
```
