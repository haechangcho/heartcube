# PRD: 스마트 모델 생성기 (Merge-safe Generator + FK Join 자동생성)

## 개요

| 항목 | 내용 |
|------|------|
| 기능명 | Merge-safe 모델 생성기 + FK 기반 Join 자동생성 |
| 브랜치 | `feature/smart-generator` |
| 우선순위 | P2 |
| 난이도 | 중간 |

## 배경 및 문제

Cube OSS의 `generate` 명령은 기존 모델 파일을 덮어써 커스텀 작업(계산 필드, 커스텀 measures 등)이 사라진다.  
또한 DB의 FK 관계를 읽어 join을 자동으로 생성하지 않아 매번 수작업으로 join을 정의해야 한다.

## 목표

- 기존 모델 파일을 보존하면서 새 컬럼/테이블만 추가하는 merge 방식 생성기 구현
- DB의 FOREIGN KEY 제약 정보를 읽어 join 관계 자동 생성
- CLI로 실행 가능한 Python 스크립트로 제공

## 범위

### In Scope
- DB 스키마 조회 (PostgreSQL 우선, 추후 BigQuery/Snowflake 확장 가능 구조)
- 기존 YAML과 신규 스키마 diff 후 신규 컬럼만 추가
- FK 기반 join YAML 자동 생성
- Dry-run 모드 (파일 수정 없이 변경 내용 미리보기)
- CLI 인터페이스

### Out of Scope
- UI 통합 (별도 `feature/model-editor-ui`에서 연동)
- Cube JS (JavaScript) 형식 지원 (YAML만)
- 자동 measure 타입 추론 (컬럼명 기반 추론 정도만)

## 기능 명세

### 1. Merge-safe 생성 로직

```
실행 흐름:
1. DB에서 테이블/컬럼 목록 조회
2. 기존 YAML 파일 로드
3. diff: 기존에 없는 컬럼/테이블만 추출
4. 신규 항목만 YAML에 추가 (기존 내용 유지)
5. 저장 (또는 dry-run 시 stdout 출력)
```

**병합 규칙:**
- 기존 dimension/measure 이름이 같으면 → 건너뜀 (기존 우선)
- 신규 컬럼이 추가됐으면 → dimension으로 추가
- 테이블이 신규이면 → 새 cube 파일 생성
- 테이블이 삭제됐으면 → 경고만 출력, 파일은 삭제 안 함

### 2. FK 기반 Join 자동생성

```sql
-- 조회 쿼리 (PostgreSQL)
SELECT
    tc.table_name       AS from_table,
    kcu.column_name     AS from_column,
    ccu.table_name      AS to_table,
    ccu.column_name     AS to_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public';
```

**생성 결과 예시:**
```yaml
cubes:
  - name: fact_contract
    sql_table: fact_contract
    joins:
      - name: dim_customer
        relationship: many_to_one
        sql: "{CUBE}.customer_id = {dim_customer}.id"
      - name: dim_product
        relationship: many_to_one
        sql: "{CUBE}.product_id = {dim_product}.id"
```

**relationship 추론 규칙:**
- FK가 있는 테이블 → 참조 테이블: `many_to_one`
- 참조 컬럼이 unique/PK: `many_to_one` 유지
- 기본값: `many_to_one` (가장 일반적인 케이스)

### 3. CLI 인터페이스

```bash
# 전체 테이블 스캔 후 merge 방식으로 생성/업데이트
python tools/smart_generator.py generate \
  --db-url postgresql://user:pass@localhost/db \
  --output ./model/cubes \
  --dry-run   # 선택: 실제 파일 수정 없이 미리보기

# FK 기반 join만 생성 (기존 cubes에 join 추가)
python tools/smart_generator.py generate-joins \
  --db-url postgresql://user:pass@localhost/db \
  --output ./model/cubes \
  --dry-run

# 특정 테이블만 처리
python tools/smart_generator.py generate \
  --tables fact_contract,fact_payment \
  --db-url postgresql://user:pass@localhost/db \
  --output ./model/cubes
```

### 4. 컬럼 타입 → Cube 타입 매핑

| DB 타입 | Cube dimension type |
|---------|---------------------|
| `integer`, `bigint`, `numeric` | `number` |
| `varchar`, `text`, `char` | `string` |
| `boolean` | `boolean` |
| `date` | `time` |
| `timestamp`, `timestamptz` | `time` |
| 기타 | `string` |

컬럼명 기반 measure 추론:
- `_count`, `_cnt` 포함 → `count` type measure 후보 주석 추가
- `_amount`, `_amt`, `_sum` 포함 → `sum` type measure 후보 주석 추가

## 구현 파일 목록

```
heartcube/
├── tools/
│   ├── smart_generator.py     # 메인 CLI
│   ├── db_inspector.py        # DB 스키마 조회
│   ├── yaml_merger.py         # YAML diff & merge 로직
│   ├── fk_join_generator.py   # FK 기반 join 생성
│   └── requirements.txt       # psycopg2, pyyaml, click
└── docs/prd/03-smart-generator.md
```

## 수용 기준 (Acceptance Criteria)

- [ ] 기존 cube YAML에 커스텀 measure가 있을 때 `generate` 실행해도 사라지지 않음
- [ ] 신규 컬럼이 DB에 추가되면 해당 dimension만 YAML에 추가됨
- [ ] FK가 있는 테이블의 join이 YAML에 자동 생성됨
- [ ] `--dry-run` 옵션으로 실제 파일 변경 없이 diff 확인 가능
- [ ] `--tables` 옵션으로 특정 테이블만 처리 가능

## 의존성

```
psycopg2-binary>=2.9
pyyaml>=6.0
click>=8.0
```
