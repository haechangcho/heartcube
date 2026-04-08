# 보험 데이터셋 기반 질문

## 분류 체계

큐브 스키마(`/model/cubes`) 기준 2×2 매트릭스:

|  | **LS** (단순 스키마: 1~3 테이블) | **HS** (복잡 스키마: 4+ 테이블, 다중 조인) |
| --- | --- | --- |
| **LQ** (단순 조회: SELECT) | LQLS | LQHS |
| **HQ** (복잡 쿼리: 집계·계산·KPI) | HQLS | HQHS |

> **`[KDL]`** KPI → Driver → Lever 흐름으로 액션 아이템을 도출할 수 있는 질문.
`kpi` 뷰 기반 쿼리는 모두 KDL 해당.
> 

> **비KDL(LQLS·LQHS·HQLS·HQHS)** 은 모두 `ops` 뷰 기반 쿼리.
`ops.*` 단일 prefix로 모든 fact/dim 멤버에 접근한다.
> 

---

## LQLS — 단순 조회 × 단순 스키마

> 필터링·정렬·목록 조회만 수행. GROUP BY·집계 없음. 1~3개 테이블 사용.
> 
1. 이번 달 감액지급된 건의 사고번호·담보명·감액사유·지급금액 목록을 보여줘
`fact_accident + fact_payment`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.accident_no",
          "ops.final_coverage_nm",
          "ops.reduction_reason"
        ],
        "measures": ["ops.total_payment_amt"],
        "timeDimensions": [{"dimension": "ops.claim_dt", "dateRange": "this month"}],
        "filters": [{"member": "ops.final_payment_cd", "operator": "equals", "values": ["감액지급"]}],
        "order": {"ops.total_payment_amt": "desc"}
      }
    }
    ```
    
2. 이상징후가 탐지된 건(사고번호·이상유형라벨·보상센터·담당자사번)을 목록으로 보여줘
`fact_accident + fact_review`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.accident_no",
          "ops.anomaly_label",
          "ops.claim_center_nm",
          "ops.adjuster_id"
        ],
        "filters": [{"member": "ops.anomaly_label", "operator": "notEquals", "values": ["정상"]}],
        "order": {"ops.accident_no": "desc"}
      }
    }
    ```
    
3. SLA 기준(5영업일)을 초과한 건의 사고번호·처리기간·담당자·보상센터를 조회해줘
`fact_accident + fact_review`

```json
{
  "query": {
    "dimensions": [
      "ops.accident_no",
      "ops.processing_biz_days",
      "ops.adjuster_id",
      "ops.claim_center_nm"
    ],
    "filters": [{"member": "ops.processing_biz_days", "operator": "gt", "values": ["5"]}],
    "order": {"ops.processing_biz_days": "desc"}
  }
}
```

1. 특정 고객의 과거 사고 청구 이력 전체를 시간순으로 보여줘
`fact_accident + dim_customer`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.accident_no",
          "ops.accident_dt",
          "ops.claim_dt",
          "ops.accident_type_l1",
          "ops.accident_type_l2",
          "ops.gender",
          "ops.age_group"
        ],
        "filters": [{"member": "ops.customer_id", "operator": "equals", "values": ["{{customer_id}}"]}],
        "order": {"ops.accident_dt": "asc"}
      }
    }
    ```
    

---

## LQHS — 단순 조회 × 복잡 스키마

> 필터링·정렬·목록 조회만 수행. GROUP BY·집계 없음. 4개 이상 테이블을 조인.
> 
1. 특정 사고번호의 고객·계약·상품·담보·지급 상세를 한 화면에 조회해줘
`fact_accident + dim_customer + fact_contract + dim_product + dim_coverage + fact_payment`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.accident_no",
          "ops.accident_dt",
          "ops.accident_type_l1",
          "ops.gender",
          "ops.age_group",
          "ops.sales_division",
          "ops.product_nm",
          "ops.coverage_nm",
          "ops.coverage_type",
          "ops.final_payment_cd",
          "ops.reduction_reason"
        ],
        "measures": ["ops.total_payment_amt"],
        "filters": [{"member": "ops.accident_no", "operator": "equals", "values": ["{{accident_no}}"]}]
      }
    }
    ```
    
2. 사기의심 라벨 건의 고객·진료내역·진단 상세 정보를 조회해줘
`fact_accident + fact_review + dim_customer + fact_treatment + dim_diagnosis`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.accident_no",
          "ops.accident_dt",
          "ops.accident_type_l1",
          "ops.gender",
          "ops.age_group",
          "ops.claim_center_nm",
          "ops.treatment_pattern",
          "ops.dx_analysis_l1",
          "ops.diagnosis_nm",
          "ops.diagnosis_type"
        ],
        "filters": [{"member": "ops.anomaly_label", "operator": "equals", "values": ["사기의심"]}],
        "order": {"ops.accident_dt": "desc"}
      }
    }
    ```
    
3. 소송이 제기된 건의 고객·계약·담보·병원·진단 상세를 조회해줘
`fact_accident + fact_review + dim_customer + fact_contract + dim_coverage + fact_treatment + dim_hospital + dim_diagnosis`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.accident_no",
          "ops.accident_dt",
          "ops.accident_type_l1",
          "ops.gender",
          "ops.age_group",
          "ops.claim_center_nm",
          "ops.processing_biz_days",
          "ops.sales_division",
          "ops.coverage_nm",
          "ops.coverage_type",
          "ops.hospital_nm",
          "ops.hospital_grade_cd",
          "ops.diagnosis_nm",
          "ops.diagnosis_type"
        ],
        "filters": [{"member": "ops.lawsuit_yn", "operator": "equals", "values": ["Y"]}],
        "order": {"ops.accident_dt": "desc"}
      }
    }
    ```
    

---

## HQLS — 복잡 쿼리 × 단순 스키마

> 1~3개 테이블에서 집계·비율·순위 등을 계산하는 쿼리
> 
1. 최근 6개월 **손해율** 추이를 사고유형별로 보여줘. 악화되는 유형이 있어?
`fact_accident + fact_payment + fact_contract`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.accident_type_l1"],
        "measures": ["ops.loss_ratio"],
        "timeDimensions": [{"dimension": "ops.accident_dt", "granularity": "month", "dateRange": "last 6 months"}],
        "order": {"ops.accident_dt": "asc"}
      }
    }
    ```
    
2. **청구인용율**이 낮은 담보 TOP5는 어떤 거야? 감액 이유가 뭐야?
`fact_payment`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.final_coverage_nm"],
        "measures": ["ops.approval_rate", "ops.payment_count", "ops.reduction_count"],
        "order": {"ops.approval_rate": "asc"},
        "limit": 5
      }
    }
    ```
    
3. **과지급율**이 가장 높은 심사자 TOP5는 누구이고, 어떤 센터에서 발생하고 있어?
`fact_review`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.adjuster_id", "ops.claim_center_nm"],
        "measures": ["ops.overpayment_rate", "ops.overpayment_count", "ops.inspect_count"],
        "order": {"ops.overpayment_rate": "desc"},
        "limit": 5
      }
    }
    ```
    
4. 동일 고객이 같은 날 여러 건 청구한 **중복지급** 의심 건을 찾아줘
`fact_accident + dim_customer`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.customer_id", "ops.claim_dt"],
        "measures": ["ops.claim_count"],
        "filters": [{"member": "ops.claim_count", "operator": "gt", "values": ["1"]}],
        "order": {"ops.claim_count": "desc"}
      }
    }
    ```
    
5. **이상탐지율**을 보상센터별로 비교해줘.
`fact_accident + fact_review`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.claim_center_nm"],
        "measures": ["ops.anomaly_rate", "ops.claim_count", "ops.anomaly_count"],
        "order": {"ops.anomaly_rate": "desc"}
      }
    }
    ```
    
6. 지난달 **SLA 준수율**이 떨어진 팀은 어디야? 지연 건 분포를 보여줘
`fact_accident + fact_review`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.claim_team_nm", "ops.claim_center_nm"],
        "measures": ["ops.claim_count"],
        "filters": [{"member": "ops.processing_biz_days", "operator": "gt", "values": ["5"]}],
        "timeDimensions": [{"dimension": "ops.accident_dt", "dateRange": "last month"}],
        "order": {"ops.claim_count": "desc"}
      }
    }
    ```
    
7. 심사자별 **평균처리기간** 편차를 보여줘. 누가 가장 오래 걸리고 있어?
`fact_accident + fact_review`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.adjuster_id", "ops.claim_center_nm"],
        "measures": ["ops.avg_processing_days", "ops.claim_count"],
        "order": {"ops.avg_processing_days": "desc"}
      }
    }
    ```
    
8. **~~재심** 후 최초 결정이 뒤집히는(과소지급→추가지급) 비율은 얼마야?~~
`~~fact_accident + fact_review + fact_payment~~`
    
    ```json
    ~~{
      "query": {
        "measures": [
          "ops.review_reversal_count",
          "ops.review_reversal_rate",
          "ops.review_count"
        ]
      }
    }~~
    ```
    

---

## HQHS — 복잡 쿼리 × 복잡 스키마

> 4개 이상 테이블을 조인하면서 복합 집계·KPI·원인 분석까지 수행하는 가장 어려운 유형
> 
1. 손해율이 목표(80%)를 초과한 담보를 찾아줘. 어디서 초과가 발생하고 있어?
`fact_accident + fact_payment + fact_contract + dim_coverage`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.coverage_nm", "ops.coverage_type"],
        "measures": ["ops.loss_ratio", "ops.claim_count"],
        "filters": [{"member": "ops.loss_ratio", "operator": "gt", "values": ["0.8"]}],
        "order": {"ops.loss_ratio": "desc"}
      }
    }
    ```
    
2. 모집채널별·상품별 **손해율** 매트릭스를 보여줘. 어떤 조합이 가장 위험해?
`fact_accident + fact_payment + fact_contract + dim_product`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.sales_division", "ops.product_nm"],
        "measures": ["ops.loss_ratio", "ops.claim_count"],
        "order": {"ops.loss_ratio": "desc"}
      }
    }
    ```
    
3. **사기의심율**이 높은 병원 TOP10을 찾아줘. 어떤 진단에서 집중돼?
`fact_accident + fact_review + dim_hospital + fact_treatment + dim_diagnosis`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.hospital_nm",
          "ops.hospital_grade_cd",
          "ops.diagnosis_type"
        ],
        "measures": ["ops.fraud_suspicion_rate", "ops.claim_count"],
        "order": {"ops.fraud_suspicion_rate": "desc"},
        "limit": 10
      }
    }
    ```
    
4. **재심율**이 높은 보상센터는 어디야? 어떤 담보에서 집중돼?
`fact_accident + fact_review + fact_contract + dim_coverage`
    
    ```json
    {
      "query": {
        "dimensions": ["ops.claim_center_nm", "ops.coverage_nm"],
        "measures": ["ops.review_rate", "ops.claim_count"],
        "order": {"ops.review_rate": "desc"}
      }
    }
    ```
    
5. **비급여 비중**이 높은 병원을 찾아줘. 어떤 비급여 항목이 집중돼?
`fact_accident + dim_hospital + fact_treatment`
    
    ```json
    {
      "query": {
        "dimensions": [
          "ops.hospital_nm",
          "ops.hospital_grade_cd",
          "ops.dx_analysis_l1"
        ],
        "measures": ["ops.noninsured_ratio", "ops.total_treat_amt_noninsured"],
        "order": {"ops.noninsured_ratio": "desc"}
      }
    }
    ```
    

---

## KDL 질문

> fact_accident를 기준 큐브로 join_path를 통해 모든 fact/dim 멤버를 `kpi.*` 단일 prefix로 노출하는 통합 뷰 (`model/views/kpi.yml`).
> 

---

**P1.** 손해율 목표(80%) 초과 담보를 찾아줘. 어떤 담보 카테고리에서 발생하고 있어?

- **KPI** `loss_ratio` → **Driver** `coverage_nm`, `coverage_cat1` → **Lever** 고위험 담보 인수기준 강화

```json
{
  "query": {
    "dimensions": [
      "kpi.coverage_nm",
      "kpi.coverage_cat1"
    ],
    "measures": [
      "kpi.loss_ratio",
      "kpi.claim_count"
    ],
    "filters": [
      {"member": "kpi.loss_ratio", "operator": "gt", "values": ["0.8"]}
    ],
    "order": {"kpi.loss_ratio": "desc"}
  }
}
```

---

**P2.** 모집채널별·상품별 손해율 매트릭스를 보여줘. 최근 3개월 추이로 악화되는 조합은?

- **KPI** `loss_ratio` → **Driver** `sales_division`, `product_nm` → **Lever** GA·방카 채널 고위험 상품 인수 조건 재검토

```json
{
  "query": {
    "dimensions": [
      "kpi.sales_division",
      "kpi.product_nm"
    ],
    "measures": [
      "kpi.loss_ratio",
      "kpi.claim_count"
    ],
    "timeDimensions": [
      {"dimension": "kpi.accident_dt", "granularity": "month", "dateRange": "last 3 months"}
    ],
    "order": {"kpi.loss_ratio": "desc"},
    "limit": 10
  }
}
```

---

**P3.** 청구인용율이 가장 낮은 담보 TOP5는 뭐야? 감액율과 함께 보여줘.

- **KPI** `claim_approval_rate` → **Driver** `coverage_nm`, `coverage_cat1` → **Lever** 담보별 지급기준 명확화, 심사룰 재정비

```json
{
  "query": {
    "dimensions": [
      "kpi.coverage_nm",
      "kpi.coverage_cat1"
    ],
    "measures": [
      "kpi.claim_approval_rate",
      "kpi.reduction_rate",
      "kpi.claim_count"
    ],
    "filters": [
      {"member": "kpi.claim_count", "operator": "gte", "values": ["30"]}
    ],
    "order": {"kpi.claim_approval_rate": "asc"},
    "limit": 5
  }
}
```

---

**Q1.** 과지급율이 높은 심사자는 어떤 사고유형을 주로 담당하고 있어? 교육·재배치 대상을 찾아줘.

- **KPI** `overpayment_rate` → **Driver** `adjuster_id`, `accident_type_l1` → **Lever** 과지급 다발 심사자 재교육, 고위험 사고유형 이중심사

```json
{
  "query": {
    "dimensions": [
      "kpi.adjuster_id",
      "kpi.claim_center_nm",
      "kpi.accident_type_l1"
    ],
    "measures": [
      "kpi.overpayment_rate",
      "kpi.claim_count"
    ],
    "filters": [
      {"member": "kpi.claim_count", "operator": "gte", "values": ["5"]}
    ],
    "order": {"kpi.overpayment_rate": "desc"},
    "limit": 10
  }
}
```

---

**Q2.** 사기의심율이 높은 병원 TOP10은 어디야? 어떤 진단군에서 집중되고 있어?

- **KPI** `fraud_suspicion_rate` → **Driver** `hospital_nm`, `diagnosis_type` → **Lever** 의심 병원 집중심사 지정, SIU 조사 의뢰

```json
{
  "query": {
    "dimensions": [
      "kpi.hospital_nm",
      "kpi.hospital_grade_cd",
      "kpi.diagnosis_type"
    ],
    "measures": [
      "kpi.fraud_suspicion_rate",
      "kpi.claim_count"
    ],
    "filters": [
      {"member": "kpi.claim_count", "operator": "gte", "values": ["10"]}
    ],
    "order": {"kpi.fraud_suspicion_rate": "desc"},
    "limit": 10
  }
}
```

---

**Q3.** 비급여비중도 높고 사기의심율도 높은 병원을 찾아줘. 집중 모니터링 대상은?

- **KPI** `noninsured_ratio` + `fraud_suspicion_rate` → **Driver** `hospital_nm` → **Lever** 병원 계약 재검토, 현장 조사 의뢰

```json
{
  "query": {
    "dimensions": [
      "kpi.hospital_nm",
      "kpi.hospital_grade_cd"
    ],
    "measures": [
      "kpi.noninsured_ratio",
      "kpi.fraud_suspicion_rate",
      "kpi.claim_count"
    ],
    "filters": [
      {"member": "kpi.claim_count", "operator": "gte", "values": ["10"]},
      {"member": "kpi.hospital_nm", "operator": "set"}
    ],
    "order": {"kpi.noninsured_ratio": "desc"},
    "limit": 10
  }
}
```

---

**Q4.** 재심율이 높은 보상센터와 담보 조합을 찾아줘. 초심 오류가 집중된 영역은?

- **KPI** `review_rate` → **Driver** `claim_center_nm`, `coverage_nm` → **Lever** 담보별 심사 가이드라인 보완, 고오류 센터 집중 교육

```json
{
  "query": {
    "dimensions": [
      "kpi.claim_center_nm",
      "kpi.coverage_nm"
    ],
    "measures": [
      "kpi.review_rate",
      "kpi.claim_count"
    ],
    "filters": [
      {"member": "kpi.claim_count", "operator": "gte", "values": ["20"]}
    ],
    "order": {"kpi.review_rate": "desc"},
    "limit": 10
  }
}
```

---

**E1.** SLA 준수율이 가장 낮은 팀은 어디야? 평균처리기간과 함께 보여줘.

- **KPI** `sla_compliance_rate` → **Driver** `claim_center_nm`, `claim_team_nm` → **Lever** 해당 팀 배당 정책 재조정, 인력 보강

```json
{
  "query": {
    "dimensions": [
      "kpi.claim_center_nm",
      "kpi.claim_team_nm"
    ],
    "measures": [
      "kpi.sla_compliance_rate",
      "kpi.avg_processing_days",
      "kpi.claim_count"
    ],
    "order": {"kpi.sla_compliance_rate": "asc"},
    "limit": 10
  }
}
```

---

**E2.** 사고유형별·조직유형별 SLA 위반 분포를 보여줘. 자동화 심사 확대가 필요한 영역은?

- **KPI** `sla_compliance_rate` → **Driver** `accident_type_l1`, `org_type` → **Lever** 협력사·보상부 내 특정 사고유형 간편심사 전환 확대

```json
{
  "query": {
    "dimensions": [
      "kpi.accident_type_l1",
      "kpi.org_type"
    ],
    "measures": [
      "kpi.sla_compliance_rate",
      "kpi.avg_processing_days",
      "kpi.claim_count"
    ],
    "order": {"kpi.sla_compliance_rate": "asc"}
  }
}
```

---

**E3.** 처리기간이 가장 긴 심사자는 누구야? 센터별로 편차가 큰 팀은?

- **KPI** `avg_processing_days` → **Driver** `adjuster_id`, `claim_center_nm` → **Lever** 처리지연 심사자 코칭, 건수 재배분

```json
{
  "query": {
    "dimensions": [
      "kpi.adjuster_id",
      "kpi.claim_center_nm",
      "kpi.claim_team_nm"
    ],
    "measures": [
      "kpi.avg_processing_days",
      "kpi.sla_compliance_rate",
      "kpi.claim_count"
    ],
    "order": {"kpi.avg_processing_days": "desc"},
    "limit": 15
  }
}
```
