# ACME Insurance × Cube NL2SQL 테스트 시나리오

> `nl2sql_query_test_scenario.md`(dbt Semantic Layer 기반)의 방법론을 heartcube(Cube REST API 기반)에 동일하게 적용한 구현 계획.
> 데이터셋은 ACME Insurance를 그대로 사용하며, 쿼리 형식만 dbt SL SQL → Cube REST API JSON으로 교체한다.

---

## 0. 운영 환경 및 DB 권한 현황

```
[로컬 머신]  →  ssh dev_mcp  →  heartcube 컨테이너 (172.20.0.2:4000)
                                       │
                                       └─ PostgreSQL 20.0.1.10:5432 (sampledb)
```

### 실제 확인된 제약사항

| 항목 | 내용 |
|------|------|
| Cube 서버 | `dev_mcp`의 Docker 컨테이너 `heartcube` (포트 4000, 외부 미노출) |
| Cube API 접근 | `dev_mcp` 내부에서 `http://172.20.0.2:4000` 또는 `http://localhost:4000` |
| DB 호스트 | `20.0.1.10:5432`, DB명 `sampledb` |
| Cube 사용 계정 | `abiuser` |
| **`abiuser` 권한** | `oda` 스키마 **SELECT/INSERT 가능, CREATE TABLE 불가** |
| **스키마 생성** | `sampleuser`(스키마 오너) 권한 필요 → **별도 DBA 요청 필요** |
| 기존 Cube 데이터 스키마 | `oda` (fact_accident, dim_* 등 11개 테이블) |
| Python 환경 | `dev_mcp`의 `~/heartcube/venv` (pandas, openai 설치됨) |
| 파이프라인 실행 | `dev_mcp`에서 직접 실행 |

### 데이터 적재 전략

`abiuser`는 새 스키마를 만들 수 없으므로, **`oda` 스키마에 `acme_` prefix 테이블**로 적재한다.

```
oda.acme_claim
oda.acme_policy
oda.acme_claim_amount
...
```

> 테이블 생성(`CREATE TABLE`)은 `sampleuser` 권한이 필요하므로 DBA에게 요청하거나,
> `dev_mcp`에서 `sampleuser` 계정으로 DDL을 실행한 후 `abiuser`에게 INSERT 권한을 부여한다.

---

## 1. 기존 벤치마크와의 비교

| 항목 | dbt Semantic Layer (원본) | Cube (이번 계획) |
|------|--------------------------|----------------|
| 쿼리 형식 | SQL-like (`select * from {{ semantic_layer.query() }}`) | JSON (`{ "query": { "dimensions", "measures", ... } }`) |
| 스키마 제공 | DDL 텍스트 (`ACME_small.ddl`) | Cube `/meta` API |
| 실행 엔드포인트 | dbt Cloud JDBC | Cube REST API `/load` (`dev_mcp` 내부) |
| 데이터셋 | ACME Insurance (20 테이블) | ACME Insurance (동일, `oda.acme_*`에 적재) |
| 평가 반복 | 5회 | 5회 (동일) |
| 평가 지표 | Execution Accuracy (True/False) | JSON Parse Rate · Execution Success · Soft Result F1 · LLM-as-Judge |
| 모델 | GPT-4 | GPT-4o (변경 가능) |
| 실행 위치 | Hex 노트북 (클라우드) | `dev_mcp` SSH 직접 실행 |

---

## 2. 전체 구현 흐름

```
[로컬] CSV 파일 전송
  scp ACME_Insurance/data/*.csv  dev_mcp:~/heartcube/acme_data/
       │
       ▼
[dev_mcp] 테이블 생성 (sampleuser 또는 DBA)
  PGPASSWORD=... psql -U sampleuser -d sampledb
  → CREATE TABLE oda.acme_claim (...);
  → GRANT INSERT, SELECT ON oda.acme_* TO abiuser;
       │
       ▼
[dev_mcp] 데이터 적재 (abiuser)
  source ~/heartcube/venv/bin/activate
  python3 ~/heartcube/acme_load_data.py
       │
       ▼
[dev_mcp] Cube 모델 파일 배포
  model/cubes/acme_*.yml, model/views/acme_ops.yml 작성
  → Cube 자동 리로드 (CUBEJS_DEV_MODE=true)
       │
       ▼
[dev_mcp] Gold 쿼리 검증
  curl http://172.20.0.2:4000/cubejs-api/v1/load ...
       │
       ▼
[dev_mcp] 벤치마크 파이프라인 실행
  python3 ~/heartcube/acme_benchmark_pipeline.py
       │
       ▼
[dev_mcp → 로컬] 결과 수집
  scp dev_mcp:~/heartcube/acme_benchmark_results.csv ./
```

---

## 3. Phase 1 — 데이터 적재

### 3-1. CSV 파일 전송

로컬에서 `dev_mcp`로 ACME 데이터 파일을 전송한다.

```bash
# 로컬에서 실행
ssh dev_mcp "mkdir -p ~/heartcube/acme_data"

scp /Users/hc.cho/Projects/semantic-layer-llm-benchmarking/ACME_Insurance/data/*.csv \
    dev_mcp:~/heartcube/acme_data/
```

### 3-2. DDL 생성 및 권한 부여 (DBA 요청)

`abiuser`는 `CREATE TABLE` 권한이 없으므로, `sampleuser` 또는 DBA가 아래 DDL을 실행해야 한다.

```sql
-- sampleuser로 실행
-- PGPASSWORD=<sampleuser_pw> psql -h 20.0.1.10 -U sampleuser -d sampledb

CREATE TABLE oda.acme_claim (
    claim_identifier        INTEGER PRIMARY KEY,
    catastrophe_identifier  INTEGER,
    claim_description       VARCHAR(5000),
    claims_made_date        TIMESTAMP,
    company_claim_number    VARCHAR(20),
    company_subclaim_number VARCHAR(5),
    insurable_object_identifier INTEGER,
    occurrence_identifier   INTEGER,
    claim_open_date         TIMESTAMP,
    claim_close_date        TIMESTAMP,
    claim_reopen_date       TIMESTAMP,
    claim_status_code       VARCHAR(5),
    claim_reported_date     TIMESTAMP
);

CREATE TABLE oda.acme_claim_amount (
    claim_amount_identifier BIGINT PRIMARY KEY,
    claim_identifier        INTEGER,
    claim_offer_identifier  INTEGER,
    amount_type_code        VARCHAR(20),
    event_date              TIMESTAMP,
    claim_amount            DECIMAL(15,2),
    insurance_type_code     CHAR(1)
);

CREATE TABLE oda.acme_loss_payment (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda.acme_loss_reserve (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda.acme_expense_payment (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda.acme_expense_reserve (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda.acme_policy (
    policy_identifier               INTEGER PRIMARY KEY,
    effective_date                  TIMESTAMP,
    expiration_date                 TIMESTAMP,
    policy_number                   VARCHAR(50),
    status_code                     VARCHAR(20),
    geographic_location_identifier  INTEGER
);

CREATE TABLE oda.acme_policy_amount (
    policy_amount_identifier        BIGINT PRIMARY KEY,
    geographic_location_identifier  INTEGER,
    policy_identifier               INTEGER,
    effective_date                  TIMESTAMP,
    amount_type_code                VARCHAR(5),
    policy_coverage_detail_identifier INTEGER,
    policy_amount                   DECIMAL(15,2)
);

CREATE TABLE oda.acme_premium (
    policy_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda.acme_policy_coverage_detail (
    policy_coverage_detail_identifier INTEGER,
    effective_date                    TIMESTAMP,
    coverage_identifier               INTEGER,
    insurable_object_identifier       INTEGER,
    policy_identifier                 INTEGER,
    coverage_part_code                VARCHAR(20),
    coverage_description              VARCHAR(2000),
    expiration_date                   TIMESTAMP
);

CREATE TABLE oda.acme_claim_coverage (
    claim_identifier                  INTEGER,
    effective_date                    TIMESTAMP,
    policy_coverage_detail_identifier INTEGER
);

CREATE TABLE oda.acme_agreement_party_role (
    agreement_identifier INTEGER,
    party_identifier     BIGINT,
    party_role_code      VARCHAR(20),   -- 'AG'=Agent, 'PH'=PolicyHolder
    effective_date       TIMESTAMP,
    expiration_date      TIMESTAMP
);

CREATE TABLE oda.acme_catastrophe (
    catastrophe_identifier    INTEGER PRIMARY KEY,
    catastrophe_type_code     VARCHAR(20),
    catastrophe_name          VARCHAR(100),
    industry_catastrophe_code VARCHAR(20),
    company_catastrophe_code  VARCHAR(20)
);

-- abiuser에게 접근 권한 부여
GRANT SELECT, INSERT, UPDATE, DELETE ON
    oda.acme_claim,
    oda.acme_claim_amount,
    oda.acme_loss_payment,
    oda.acme_loss_reserve,
    oda.acme_expense_payment,
    oda.acme_expense_reserve,
    oda.acme_policy,
    oda.acme_policy_amount,
    oda.acme_premium,
    oda.acme_policy_coverage_detail,
    oda.acme_claim_coverage,
    oda.acme_agreement_party_role,
    oda.acme_catastrophe
TO abiuser;
```

### 3-3. 데이터 적재 스크립트

**`~/heartcube/acme_load_data.py`** — `dev_mcp`에서 실행, `abiuser`로 INSERT

```python
#!/usr/bin/env python3
"""
ACME Insurance CSV → PostgreSQL (sampledb.oda 스키마, acme_ prefix 테이블) 적재
실행: ssh dev_mcp "cd ~/heartcube && source venv/bin/activate && python3 acme_load_data.py"
"""

import pandas as pd
from sqlalchemy import create_engine

# Cube .env 기준 접속 정보 (abiuser)
DB_URL   = "postgresql://abiuser:<db_password>@<db_host>:5432/sampledb"
SCHEMA   = "oda"
DATA_DIR = "/home/ubuntu/heartcube/acme_data"

# CSV 파일명 → oda.acme_* 테이블명 매핑
CSV_TABLE_MAP = {
    "Agreement_Party_Role.csv":   "acme_agreement_party_role",
    "Catastrophe.csv":            "acme_catastrophe",
    "Claim.csv":                  "acme_claim",
    "Claim_Amount.csv":           "acme_claim_amount",
    "Claim_Coverage.csv":         "acme_claim_coverage",
    "Expense_Payment.csv":        "acme_expense_payment",
    "Expense_Reserve.csv":        "acme_expense_reserve",
    "Loss_Payment.csv":           "acme_loss_payment",
    "Loss_Reserve.csv":           "acme_loss_reserve",
    "Policy.csv":                 "acme_policy",
    "Policy_Amount.csv":          "acme_policy_amount",
    "Policy_Coverage_Detail.csv": "acme_policy_coverage_detail",
    "Premium.csv":                "acme_premium",
}

engine = create_engine(DB_URL)

for csv_file, table_name in CSV_TABLE_MAP.items():
    path = f"{DATA_DIR}/{csv_file}"
    try:
        df = pd.read_csv(path)
        df.columns = [c.lower() for c in df.columns]  # 컬럼명 소문자
        df.to_sql(
            table_name,
            engine,
            schema=SCHEMA,
            if_exists="replace",  # 재실행 시 덮어쓰기
            index=False,
        )
        print(f"✅ {SCHEMA}.{table_name}: {len(df)}행 적재 완료")
    except FileNotFoundError:
        print(f"⚠️  파일 없음: {csv_file}")
    except Exception as e:
        print(f"❌ {table_name} 적재 실패: {e}")
```

### 3-4. 실행 방법

```bash
# dev_mcp에서 실행
ssh dev_mcp "cd ~/heartcube && source venv/bin/activate && python3 acme_load_data.py"
```

### 3-5. 적재 검증

```bash
ssh dev_mcp "PGPASSWORD='<db_password>' psql -h <db_host> -U abiuser -d sampledb -c \"
  SELECT tablename, n_live_tup AS rows
  FROM pg_stat_user_tables
  WHERE schemaname = 'oda' AND tablename LIKE 'acme_%'
  ORDER BY tablename;
\""
```

---

## 4. Phase 2 — Cube 모델 정의

`dev_mcp`의 `~/heartcube/model/` 디렉토리에 파일을 작성한다.
`CUBEJS_DEV_MODE=true`이므로 파일 저장 즉시 Cube가 자동 리로드된다.

### 4-1. 디렉토리 구조

```
~/heartcube/model/
├── cubes/
│   ├── acme_claim.yml              ★ 기준 팩트 큐브
│   ├── acme_claim_amount.yml       파생 메트릭 (loss/expense)
│   ├── acme_policy.yml
│   ├── acme_policy_amount.yml
│   ├── acme_policy_coverage_detail.yml
│   ├── acme_premium.yml
│   ├── acme_loss_payment.yml
│   ├── acme_loss_reserve.yml
│   ├── acme_expense_payment.yml
│   ├── acme_expense_reserve.yml
│   ├── acme_agreement_party_role.yml
│   ├── acme_claim_coverage.yml
│   └── acme_catastrophe.yml
└── views/
    └── acme_ops.yml                ★ 통합 뷰 (prefix: acme_ops.*)
```

### 4-2. 핵심 큐브 정의

**`model/cubes/acme_claim.yml`** — 기준 팩트

```yaml
cubes:
  - name: acme_claim
    sql_table: oda.acme_claim
    title: ACME 청구

    joins:
      - name: acme_catastrophe
        sql: "{acme_claim}.catastrophe_identifier = {acme_catastrophe}.catastrophe_identifier"
        relationship: many_to_one

      - name: acme_claim_amount
        sql: "{acme_claim}.claim_identifier = {acme_claim_amount}.claim_identifier"
        relationship: one_to_many

      - name: acme_claim_coverage
        sql: "{acme_claim}.claim_identifier = {acme_claim_coverage}.claim_identifier"
        relationship: one_to_many

    dimensions:
      - name: claim_identifier
        sql: claim_identifier
        type: number
        primary_key: true

      - name: company_claim_number
        sql: company_claim_number
        type: string
        title: 청구번호

      - name: claim_status_code
        sql: claim_status_code
        type: string
        title: 청구상태코드

      - name: claim_open_date
        sql: "CAST(claim_open_date AS DATE)"
        type: time
        title: 청구개시일

      - name: claim_close_date
        sql: "CAST(claim_close_date AS DATE)"
        type: time
        title: 청구종료일

    measures:
      - name: claim_count
        sql: company_claim_number
        type: count
        title: 청구건수

      - name: avg_days_to_settle
        sql: "EXTRACT(DAY FROM (claim_close_date - claim_open_date))"
        type: avg
        title: 평균처리기간(일)
```

**`model/cubes/acme_claim_amount.yml`** — 파생 메트릭

```yaml
cubes:
  - name: acme_claim_amount
    sql_table: oda.acme_claim_amount

    joins:
      - name: acme_loss_payment
        sql: "{acme_claim_amount}.claim_amount_identifier = {acme_loss_payment}.claim_amount_identifier"
        relationship: one_to_one
      - name: acme_loss_reserve
        sql: "{acme_claim_amount}.claim_amount_identifier = {acme_loss_reserve}.claim_amount_identifier"
        relationship: one_to_one
      - name: acme_expense_payment
        sql: "{acme_claim_amount}.claim_amount_identifier = {acme_expense_payment}.claim_amount_identifier"
        relationship: one_to_one
      - name: acme_expense_reserve
        sql: "{acme_claim_amount}.claim_amount_identifier = {acme_expense_reserve}.claim_amount_identifier"
        relationship: one_to_one

    dimensions:
      - name: claim_amount_identifier
        sql: claim_amount_identifier
        type: number
        primary_key: true

    measures:
      - name: loss_payment_amount
        sql: "CASE WHEN {acme_loss_payment}.claim_amount_identifier IS NOT NULL THEN claim_amount ELSE 0 END"
        type: sum
        title: 손해지급금액

      - name: loss_reserve_amount
        sql: "CASE WHEN {acme_loss_reserve}.claim_amount_identifier IS NOT NULL THEN claim_amount ELSE 0 END"
        type: sum
        title: 손해준비금

      - name: total_loss_amount
        sql: "{loss_payment_amount} + {loss_reserve_amount}"
        type: number
        title: 총손해금액
```

**`model/cubes/acme_policy.yml`**

```yaml
cubes:
  - name: acme_policy
    sql_table: oda.acme_policy

    dimensions:
      - name: policy_identifier
        sql: policy_identifier
        type: number
        primary_key: true

      - name: policy_number
        sql: policy_number
        type: string
        title: 증권번호

      - name: status_code
        sql: status_code
        type: string

    measures:
      - name: policy_count
        type: count
        title: 증권건수
```

**`model/cubes/acme_agreement_party_role.yml`** — Agent/PolicyHolder 역할

```yaml
cubes:
  - name: acme_agreement_party_role
    sql_table: oda.acme_agreement_party_role

    dimensions:
      - name: agreement_identifier
        sql: agreement_identifier
        type: number

      - name: party_identifier
        sql: party_identifier
        type: number
        title: 당사자ID

      - name: party_role_code
        sql: party_role_code
        type: string
        title: "역할코드 (AG=에이전트, PH=계약자)"

    measures:
      - name: policy_count_by_agent
        sql: agreement_identifier
        type: count_distinct
        filters:
          - sql: "{party_role_code} = 'AG'"
        title: 에이전트별증권수
```

**`model/views/acme_ops.yml`** — 통합 뷰

```yaml
views:
  - name: acme_ops
    title: ACME 보험 통합 뷰
    description: >
      ACME Insurance 청구·증권·지급·당사자 데이터를 통합한 뷰.
      단일 prefix(acme_ops.*)로 모든 멤버에 접근한다.

    cubes:
      - join_path: acme_claim
        includes:
          - company_claim_number
          - claim_status_code
          - claim_open_date
          - claim_close_date
          - claim_count
          - avg_days_to_settle

      - join_path: acme_claim.acme_catastrophe
        includes:
          - catastrophe_name

      - join_path: acme_claim.acme_claim_coverage.acme_policy_coverage_detail.acme_policy
        includes:
          - policy_number
          - policy_count

      - join_path: acme_claim.acme_claim_coverage.acme_policy_coverage_detail.acme_policy.acme_agreement_party_role
        includes:
          - party_identifier
          - party_role_code
          - policy_count_by_agent

      - join_path: acme_claim.acme_claim_amount
        includes:
          - loss_payment_amount
          - loss_reserve_amount
          - total_loss_amount

      - join_path: acme_claim.acme_claim_coverage.acme_policy_coverage_detail.acme_policy.acme_policy_amount.acme_premium
        includes:
          - name: premium_amount
```

### 4-3. Cube 리로드 확인

```bash
# dev_mcp에서 /meta 응답에 acme_ops 포함 여부 확인
ssh dev_mcp "curl -s http://172.20.0.2:4000/cubejs-api/v1/meta \
  -H 'Authorization: Bearer heartcube-secret-change-in-production' \
  | python3 -c \"import sys,json; cubes=[c['name'] for c in json.load(sys.stdin)['cubes']]; print([c for c in cubes if 'acme' in c])\""
```

---

## 5. Phase 3 — 벤치마크 질문 정의

**파일**: `~/heartcube/acme_questions.md`

기존 11개 질문을 한국어로 번역하고 Gold Cube JSON 쿼리를 작성한다.

### HQLS (단순 집계)

**1. 청구건수가 몇 건이야?**
```json
{"query": {"measures": ["acme_ops.claim_count"]}}
```

**2. 증권이 몇 건이야?**
```json
{"query": {"measures": ["acme_ops.policy_count"]}}
```

**3. 증권번호별 청구건수를 보여줘**
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.claim_count"], "order": {"acme_ops.claim_count": "desc"}}}
```

**4. 에이전트별 판매 증권 수를 보여줘**
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.policy_count_by_agent"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.policy_count_by_agent": "desc"}}}
```

**5. 증권번호별 납입 보험료 합계를 보여줘**
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.premium_amount"], "order": {"acme_ops.premium_amount": "desc"}}}
```

**6. 평균 증권 규모(총 보험료 ÷ 증권 수)를 알려줘**
```json
{"query": {"measures": ["acme_ops.premium_amount", "acme_ops.policy_count"]}}
```

### HQHS (복합 집계)

**7. 청구번호별 총손해금액(손해지급 + 손해준비금)을 보여줘**
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.total_loss_amount"], "order": {"acme_ops.total_loss_amount": "desc"}}}
```

**8. 계약자별 총 납입 보험료를 보여줘**
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.premium_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.premium_amount": "desc"}}}
```

**9. 증권번호별 계약자가 납입한 총 보험료를 보여줘**
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.party_identifier"], "measures": ["acme_ops.premium_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.premium_amount": "desc"}}}
```

**10. 계약자별 보유 증권 수를 보여줘**
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.policy_count"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.policy_count": "desc"}}}
```

**11. 증권번호별 평균 처리기간을 보여줘**
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.avg_days_to_settle"], "order": {"acme_ops.avg_days_to_settle": "desc"}}}
```

---

## 6. Phase 4 — 파이프라인 실행

**파일**: `~/heartcube/acme_benchmark_pipeline.py`

기존 `benchmark_pipeline.py`의 구조를 그대로 활용하고 아래 설정값만 교체한다.

```python
# acme_benchmark_pipeline.py 변경 설정값
CUBE_BASE_URL   = "http://172.20.0.2:4000/cubejs-api/v1"  # dev_mcp 내부 접근
CUBE_TOKEN      = "heartcube-secret-change-in-production"
LLM_MODEL       = "gpt-4o"
N_ITERATIONS    = 5
QUESTIONS_FILE  = os.path.expanduser("~/heartcube/acme_questions.md")
RESULTS_CSV     = os.path.expanduser("~/heartcube/acme_benchmark_results.csv")
```

### few-shot 프롬프트 (ACME 도메인)

```python
FEW_SHOT_ACME = """
Cube REST API는 다음 JSON 형식으로 쿼리합니다:
{
  "query": {
    "dimensions": ["acme_ops.dimension_name"],
    "measures":   ["acme_ops.measure_name"],
    "filters":    [{"member": "acme_ops.field", "operator": "equals", "values": ["value"]}],
    "order":      {"acme_ops.measure_name": "desc"},
    "limit":      10
  }
}

반드시 "acme_ops." prefix만 사용하세요.

예시 1) 청구건수 조회
{"query": {"measures": ["acme_ops.claim_count"]}}

예시 2) 증권번호별 청구건수 내림차순
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.claim_count"], "order": {"acme_ops.claim_count": "desc"}}}

예시 3) 에이전트(AG)별 판매 증권 수
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.policy_count_by_agent"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.policy_count_by_agent": "desc"}}}
"""
```

### 실행 명령

```bash
# dev_mcp에서 실행
ssh dev_mcp "cd ~/heartcube && source venv/bin/activate && \
  OPENAI_API_KEY=<your_key> python3 acme_benchmark_pipeline.py"

# 백그라운드 실행 (55건, 시간 소요 예상)
ssh dev_mcp "cd ~/heartcube && source venv/bin/activate && \
  nohup env OPENAI_API_KEY=<your_key> python3 acme_benchmark_pipeline.py \
  > acme_benchmark_run.log 2>&1 &"
```

### 평가 지표

| 지표 | 설명 |
|------|------|
| **JSON Parse Rate** | LLM 출력이 유효한 JSON인 비율 |
| **Execution Success Rate** | `/load` API 에러 없이 실행되는 비율 |
| **Component F1** | dimensions·measures·filters 필드 단위 F1 (Spider 표준) |
| **Soft Result F1** | Gold 결과와 LLM 결과의 row 집합 일치율 (부분 점수 허용) |
| **LLM-as-Judge** | Result F1 < 0.9인 경계 케이스만 LLM으로 재판정 |

---

## 7. Phase 5 — 결과 수집 및 분석

### 결과 파일 수집

```bash
# dev_mcp → 로컬
scp dev_mcp:~/heartcube/acme_benchmark_results.csv \
    /Users/hc.cho/Projects/semantic-layer-llm-benchmarking/
```

### dbt SL 원본 결과와 비교 기준

| 질문 | dbt SL 정확도 | Cube 목표 정확도 |
|------|-------------|----------------|
| 청구건수? | 100% | ≥ 95% |
| 증권건수? | 100% | ≥ 95% |
| 에이전트별 증권 수? | 100% | ≥ 90% |
| 계약자별 보유 증권 수? | 100% | ≥ 90% |
| 증권번호별 보험료 합계? | 100% | ≥ 90% |
| 청구번호별 총손해금액? | 60% | ≥ 70% |
| 계약자별 납입 보험료? | 15% | ≥ 50% |
| 평균처리기간 (증권번호별)? | 0% | ≥ 60% |
| 평균 증권 규모? | 0% | ≥ 40% |

---

## 8. 구현 체크리스트

### 사전 조건 (DBA 요청)
- [ ] `sampleuser`로 `oda.acme_*` 테이블 13개 DDL 실행
- [ ] `abiuser`에게 해당 테이블 SELECT/INSERT/UPDATE/DELETE 권한 부여

### Phase 1 — 데이터 적재
- [ ] 로컬 → `dev_mcp` CSV 전송 (`scp`)
- [ ] `acme_load_data.py` 작성 후 `dev_mcp`에 복사
- [ ] `dev_mcp`에서 적재 실행 (`source venv/bin/activate && python3 acme_load_data.py`)
- [ ] 테이블별 행 수 검증

### Phase 2 — Cube 모델
- [ ] `model/cubes/acme_claim.yml` 작성
- [ ] `model/cubes/acme_claim_amount.yml` 작성
- [ ] `model/cubes/acme_policy.yml` 작성
- [ ] `model/cubes/acme_policy_amount.yml` 작성
- [ ] `model/cubes/acme_policy_coverage_detail.yml` 작성
- [ ] `model/cubes/acme_premium.yml` 작성
- [ ] `model/cubes/acme_loss_payment.yml` / `acme_loss_reserve.yml` 작성
- [ ] `model/cubes/acme_expense_payment.yml` / `acme_expense_reserve.yml` 작성
- [ ] `model/cubes/acme_agreement_party_role.yml` 작성
- [ ] `model/cubes/acme_claim_coverage.yml` 작성
- [ ] `model/cubes/acme_catastrophe.yml` 작성
- [ ] `model/views/acme_ops.yml` 작성
- [ ] `/meta` 응답에 `acme_ops` 포함 확인

### Phase 3 — 벤치마크 질문
- [ ] `acme_questions.md` 작성 (11개 질문 + Gold JSON)
- [ ] `dev_mcp`에서 각 Gold 쿼리 curl로 실행 검증
- [ ] dbt SL Gold DataFrame과 결과값 교차 검증

### Phase 4 — 파이프라인
- [ ] `acme_benchmark_pipeline.py` 작성 (설정값 교체)
- [ ] `dev_mcp`에서 소규모 테스트 (1 iteration × 3 질문)
- [ ] 전체 실행 (5 iteration × 11 질문 = 55건)

### Phase 5 — 결과 분석
- [ ] `acme_benchmark_results.csv` → 로컬 수집
- [ ] dbt SL 원본 결과와 비교 분석

---

## 9. 파일 산출물 요약

| 파일 | 위치 | 내용 |
|------|------|------|
| `acme_load_data.py` | `dev_mcp:~/heartcube/` | ACME CSV → `oda.acme_*` 적재 스크립트 |
| `acme_data/*.csv` | `dev_mcp:~/heartcube/acme_data/` | 원본 ACME CSV (scp 전송) |
| `model/cubes/acme_*.yml` | `dev_mcp:~/heartcube/model/cubes/` | ACME 테이블별 Cube 모델 (13개) |
| `model/views/acme_ops.yml` | `dev_mcp:~/heartcube/model/views/` | ACME 통합 뷰 |
| `acme_questions.md` | `dev_mcp:~/heartcube/` | 11개 자연어 질문 + Gold Cube JSON |
| `acme_benchmark_pipeline.py` | `dev_mcp:~/heartcube/` | 평가 파이프라인 전체 코드 |
| `acme_benchmark_results.csv` | `dev_mcp:~/heartcube/` → 로컬 수집 | 55건 실험 결과 |

---

## 10. 참고

- 원본 벤치마크: `semantic-layer-llm-benchmarking/nl2sql_query_test_scenario.md`
- 원본 데이터: `semantic-layer-llm-benchmarking/ACME_Insurance/data/*.csv`
- 원본 DDL: `semantic-layer-llm-benchmarking/hex_notebook/ACME_small.ddl`
- 기존 파이프라인: `dev_mcp:~/heartcube/benchmark_pipeline.py`
- Cube REST API: `http://172.20.0.2:4000/cubejs-api/v1` (dev_mcp 내부)
- Cube API Token: `.env` → `CUBEJS_API_SECRET`
