# HeartMCP 활성화된 툴 정리

> 기준 파일: `~/heartmcp/tools/definitions.py` (`ENABLED_TOOLS`)
> 라우팅: `cube_*` → CubeAdapter (Cube REST API :4000) / 나머지 → SemanticAdapter

---

## 목차

1. [지표 탐색](#지표-탐색)
   - [get_all_measure_list](#get_all_measure_list)
   - [get_all_dimension_list](#get_all_dimension_list)
   - [get_measure_info](#get_measure_info)
   - [get_measure_kdl](#get_measure_kdl)
   - [get_measure_query_guide](#get_measure_query_guide)
   - [get_dimension_values](#get_dimension_values)
   - [get_measure_description](#get_measure_description)
   - [get_dimension_description](#get_dimension_description)
2. [데이터 조회](#데이터-조회)
   - [cube_query](#cube_query)
   - [cube_query_test](#cube_query_test)
   - [get_all_kpi_list](#get_all_kpi_list)
   - [get_measure_stat](#get_measure_stat)

---

## 지표 탐색

### `get_all_measure_list`

전체 Cube 시맨틱 레이어에 정의된 **모든 measure 목록**을 반환한다.

- **입력**: 없음 (항상 인자 없이 호출)
- **출력**: `measures[]` (name, cube_name, title, type, agg_type, description), `total`
- **용도**: 어떤 measure가 존재하는지 파악할 때 가장 먼저 호출. 사용 가능한 view prefix(`kpi.*`, `ops.*` 등) 확인에도 활용.

---

### `get_all_dimension_list`

특정 measure와 **같은 cube에 속한 모든 dimension** 목록을 반환한다.

- **입력**: `measure_name` — `'cube_name.measure_name'` 형식 (예: `fact_treatment.total_amount`)
- **출력**: `cube_name`, `dimensions[]` (name, title, type, description), `total`
- **용도**: `cube_query` 작성 전 어떤 dimension으로 GROUP BY/필터를 걸 수 있는지 확인. primaryKey dimension은 자동 제외됨.

---

### `get_measure_info`

특정 measure의 **상세 정보 + 소속 cube 전체 스키마 + 참조 view 목록**을 반환한다.

- **입력**: `measure_name` — `'cube_name.measure_name'` 형식
- **출력**:
  - `measure` — name, title, type, agg_type, description
  - `source_cube` — name, title, description, measures[], dimensions[], joins[]
  - `views[]` — 해당 cube를 포함하는 view 목록 (name, title, includes)
- **용도**: measure 하나를 깊이 파고들 때. 어떤 view에서 접근 가능한지, join 구조가 어떤지 한 번에 파악.

---

### `get_measure_kdl`

특정 measure의 **KPI / Driver / Lever** 메타 정보를 반환한다.

- **입력**: `measure_name` — `'cube_name.measure_name'` 형식 (예: `kpi.loss_ratio`)
- **출력**:
  - `kpi` — visible, target 등 KPI 목표 정보
  - `driver[]` — 연관 dimension/measure와 각각의 title·description
  - `lever[]` — 개선 action 목록
- **용도**: KPI 이상 감지 후 근본 원인(driver) 파악 및 개선 방향(lever) 탐색. `get_all_kpi_list`와 함께 쓰이는 경우가 많음.

---

### `get_measure_query_guide`

특정 measure로 **`cube_query`를 어떻게 구성해야 하는지** 안내한다.

- **입력**: `measure_name` — `'cube_name.measure_name'` 형식
- **출력**: `measure_name`, `guide` (사용 가능한 time dimension·categorical dimension 목록 + 예시 cube_query)
- **용도**: `cube_query` 호출 전 필수 확인 도구. 올바른 파라미터 구성(특히 timeDimensions·dimensions)을 예시와 함께 제공.

---

### `get_dimension_values`

특정 dimension의 **distinct 값 목록**을 count 내림차순으로 반환한다.

- **입력**: `dimension_name` — `'cube_name.dimension_name'` 형식, `limit` (기본 30)
- **출력**: `dimension_name`, `values[]`, `total_distinct`, `truncated` (limit 초과 여부), `note`
- **용도**: 필터 조건의 실제 값 확인. 예: `accident_type_l1`에 어떤 카테고리 값들이 있는지 조회.

---

### `get_measure_description`

measure 이름 배열을 받아 **각 measure의 title과 description**을 반환한다.

- **입력**: `measure_names[]` — `'cube_name.measure_name'` 형식 배열
- **출력**: 각 measure의 title, description
- **용도**: 쿼리 결과에 포함된 measure들의 정확한 의미를 해석할 때. 특히 LLM이 인사이트를 생성하기 전 용어 정의 확인에 활용.

---

### `get_dimension_description`

dimension 이름 배열을 받아 **각 dimension의 title과 description**을 반환한다.

- **입력**: `dimension_names[]` — `'cube_name.dimension_name'` 형식 배열
- **출력**: 각 dimension의 title, description
- **용도**: 쿼리 결과에 포함된 dimension들의 분류 기준 및 의미 파악. `get_measure_description`의 dimension 버전.

---

## 데이터 조회

### `cube_query`

**Cube REST API로 집계 쿼리를 실행**하고 데이터를 반환한다. 에러 발생 시 원인 진단 및 자동 수정을 시도한다.

- **입력**:

  | 파라미터 | 타입 | 필수 | 설명 |
  |---|---|---|---|
  | `measures` | `string[]` | 조건부 | 집계 measure 목록. `'view.measure_name'` 형식 |
  | `dimensions` | `string[]` | 조건부 | GROUP BY dimension 목록. measure를 여기 넣으면 에러 |
  | `timeDimensions` | `object[]` | 선택 | 시간 필터/그룹핑. `dimension`, `granularity`(선택), `dateRange` 지정 |
  | `filters` | `object[]` | 선택 | WHERE/HAVING 조건. 단일 필터 또는 `and`/`or` 논리 블록 |
  | `segments` | `string[]` | 선택 | 사전 정의된 named filter segment |
  | `order` | `object\|array` | 선택 | 정렬. 객체(`{'field': 'desc'}`) 또는 순서 보장 배열 형식 |
  | `limit` | `integer` | 선택 | 최대 반환 행 수. 기본 100, 최대 5000 |
  | `offset` | `integer` | 선택 | 페이지네이션 offset. 기본 0 |
  | `timezone` | `string` | 선택 | IANA 시간대 (예: `'Asia/Seoul'`) |
  | `total` | `boolean` | 선택 | 전체 행 수 포함 여부. 기본 false |
  | `ungrouped` | `boolean` | 선택 | GROUP BY 없이 raw row 조회. 기본 false |
  | `user_question` | `string` | 선택 | 로깅용 원본 질문 (쿼리 실행에 영향 없음) |

  > `measures`와 `dimensions` 중 최소 하나는 반드시 있어야 한다.

- **출력**: `data[]`, `rowcount`, `cubes_used[]`, `cube_query`

- **에러 처리** (에러 응답에 `possible_causes` 포함):
  - `measures`·`dimensions` 모두 없으면 API 호출 전 차단
  - `not found for path 'xxx'` 에러 시 `/meta` 재조회 후 원인 진단:
    - 해당 필드가 **measure인데 dimensions에 넣은 경우**: 자동으로 measures로 이동 후 **쿼리 재실행** (응답에 `auto_corrected: true`)
    - **view 자체가 없는 경우**: 사용 가능한 view 이름 목록 제공
    - **필드 자체가 없는 경우**: 해당 view의 실제 dimensions/measures 전체 목록 제공
  - 네트워크 에러: 재시도 안내 포함

- **`timeDimensions.dateRange` 형식 주의**:
  - 상대 날짜: 반드시 **문자열**로 전달 (`'last 6 months'`, `'this month'`) — 배열로 감싸면 안 됨
  - 절대 날짜: 정확히 2개짜리 배열 (`['2025-01-01', '2025-12-31']`)

- **`filters.operator` 목록**:
  - 문자열: `equals`, `notEquals`, `contains`, `notContains`, `startsWith`, `endsWith` 등
  - 숫자: `gt`, `gte`, `lt`, `lte` — values는 문자열로 전달 (예: `['100']`)
  - NULL: `set`, `notSet`
  - 날짜: `inDateRange`, `beforeDate`, `afterDate` 등
  - measure 전용: `measureFilter`
  - dimension 필터와 measure 필터를 같은 `and`/`or` 블록 안에 **혼용 불가** (WHERE vs HAVING)

---

### `cube_query_test`

`cube_query` 직후 호출하여 **생성된 쿼리를 정답 쿼리와 비교·평가**한다. 벤치마크 전용 툴.

- **입력**: `question` (questions.md 기준 질문 텍스트), `generated_query` (cube_query에 넘긴 쿼리 body)
- **출력**:
  - `matched_question`, `category`
  - `generated_query`, `gold_query`
  - `generated_result[]`, `gold_result[]`
  - `metrics` — `exec_ok`, `gold_exec_ok`, `dim_jaccard`, `msr_jaccard`, `filter_jaccard`, `result_match`
- **용도**: 자동화 벤치마크. questions.md에 없는 질문이면 error 반환.

---

### `get_all_kpi_list`

`kpi` 뷰에서 `meta.kpi.visible=true`인 **KPI measure를 전부 조회하고 각각 쿼리 자동 실행**한다.

- **입력**:
  - `date_range` (선택) — 조회 기간. shorthand: `'3M'`, `'6M'`, `'1Y'`, `'YTD'`, `'MTD'`, `'QTD'` 또는 Cube 형식 직접 입력 (예: `'last 6 months'`)
  - `include_kdl` (기본 `true`) — 각 KPI에 KDL(목표·Driver·Lever) 정보 포함 여부
- **출력**: `date_range`, `kpi_count`, `kpis[]`
  - 각 항목: `measure`, `title`, `description`, `query`, `exec_ok`, `rowcount`, `data[]`, `error`(실패 시), `kdl`(include_kdl=true 시)
- **용도**: KPI 대시보드 초기 로딩. 전체 KPI 현황을 한 번에 파악. `include_kdl=true`면 Driver/Lever까지 포함되어 분석 컨텍스트 제공.

---

### `get_measure_stat`

특정 measure의 **통계값(min, max, mean, stddev, count)**을 반환한다.

- **입력**: `measure_name` — `'view.measure_name'` 형식 (예: `kpi.loss_ratio`)
- **출력**: `measure`, `title`, `time_dimension`, `granularity`, `stat` (min, max, mean, stddev, count)
- **동작**: measure에 정의된 pre-aggregation granularity로 전체 기간 데이터를 `cube_query`로 조회한 뒤 Python에서 통계 계산
- **용도**: 필터 범위 설정, 이상값 탐지 기준 수립, measure 값 분포 파악.

---

## 툴 호출 순서 패턴

### 일반 데이터 조회
```
get_all_measure_list()               # 어떤 measure가 있는지 파악
  → get_measure_query_guide()        # 해당 measure의 올바른 쿼리 구성 확인
  → (필요시) get_dimension_values()  # 필터 값 확인
  → cube_query()                     # 쿼리 실행
```

### KPI 분석
```
get_all_kpi_list(include_kdl=true)  # 전체 KPI + KDL 한 번에 조회
  → get_measure_kdl()               # 특정 KPI 상세 Driver/Lever 확인
  → cube_query()                    # Driver 기준 drill-down
```

### 인사이트 생성
```
cube_query()                        # 데이터 조회
  → get_measure_description()       # 결과 measure의 정확한 의미 확인
  → get_dimension_description()     # 결과 dimension의 분류 기준 확인
```
