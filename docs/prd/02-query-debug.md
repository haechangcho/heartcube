# PRD: Query 로깅 및 디버깅 대시보드

## 개요

| 항목 | 내용 |
|------|------|
| 기능명 | Query 로깅 미들웨어 + 디버깅 대시보드 |
| 브랜치 | `feature/query-debug` |
| 우선순위 | P1 |
| 난이도 | 중간 |

## 배경 및 문제

Superset 등 BI 툴에서 Cube를 통해 실행되는 쿼리의 실제 SQL, 사용된 cube/view, pre-aggregation 적용 여부를 확인할 방법이 없다.  
문제 발생 시 원인 추적이 불가능하고, 성능 최적화를 위한 데이터도 수집되지 않는다.

## 목표

- Cube API로 들어오는 모든 쿼리와 실행 결과를 로깅
- 웹 UI로 Query History 조회 (SQL, cube, duration, pre-agg 여부 등)
- pre-aggregation 적용 상태 모니터링

## 범위

### In Scope
- Cube API 앞단 프록시 미들웨어 (쿼리 로깅)
- 로그 저장소 (SQLite 또는 JSON 파일)
- Query History 조회 API
- 간단한 조회 UI (React 또는 순수 HTML)
- pre-aggregation 상태 조회 API 래퍼

### Out of Scope
- 알림(Alert) 기능
- 외부 모니터링 시스템 연동 (Grafana 등)
- 쿼리 실행 계획(Explain) 분석

## 기능 명세

### 1. 쿼리 로깅 미들웨어

Cube API 앞단에 Express 기반 프록시를 두어 `/cubejs-api/v1/load` 요청을 가로채 로깅한다.

**로깅 항목:**

| 필드 | 설명 |
|------|------|
| `requestId` | UUID |
| `timestamp` | 요청 시각 |
| `userId` | JWT에서 추출 |
| `cubeQuery` | 원본 Cube 쿼리 JSON |
| `generatedSql` | Cube가 생성한 실제 SQL |
| `usedCubes` | 사용된 cube/view 목록 |
| `preAggregationUsed` | pre-agg 적용 여부 (boolean) |
| `preAggregationName` | 적용된 pre-agg 이름 |
| `duration` | 응답 시간 (ms) |
| `rowCount` | 반환된 행 수 |
| `statusCode` | HTTP 상태 코드 |

### 2. Query History API

```
GET  /api/query-history
     ?limit=50
     &userId=hc
     &from=2026-04-01
     &to=2026-04-07
     &preAggOnly=false

GET  /api/query-history/:requestId    # 특정 쿼리 상세
DELETE /api/query-history             # 로그 전체 삭제 (관리용)
```

### 3. Pre-aggregation 상태 API

Cube의 `/cubejs-api/v1/pre-aggregations/jobs`를 래핑하여 제공한다.

```
GET /api/pre-aggregations/status
Response:
[
  {
    "cube": "fact_contract",
    "preAggName": "monthly_summary",
    "status": "done",        # scheduled / processing / done / error
    "lastRefresh": "2026-04-07T02:00:00Z",
    "rowCount": 12048
  }
]
```

### 4. Query History UI

단일 페이지(SPA 불필요, 서버사이드 렌더링 가능):

```
┌─────────────────────────────────────────────────┐
│  Query History              [필터: 사용자/날짜]  │
├──────┬──────────┬──────┬──────┬─────┬───────────┤
│ 시각 │ 사용자   │ cube │ 시간 │ 행수│ pre-agg   │
├──────┼──────────┼──────┼──────┼─────┼───────────┤
│ ...  │ hc       │ fact_│ 42ms │ 320 │ ✓ monthly │
│      │          │ cont │      │     │           │
└──────┴──────────┴──────┴──────┴─────┴───────────┘
[클릭 시] → SQL 전문, Cube 쿼리 JSON 펼쳐보기
```

## 구현 파일 목록

```
heartcube/
├── query-logger/
│   ├── proxy.js               # Express 프록시 미들웨어
│   ├── storage.js             # SQLite 로그 저장
│   ├── api.js                 # History / pre-agg API
│   ├── ui/
│   │   └── index.html         # Query History UI
│   └── package.json
├── docker-compose.yml         # query-logger 서비스 추가
└── docs/prd/02-query-debug.md
```

## 수용 기준 (Acceptance Criteria)

- [ ] Superset → Cube 쿼리 실행 시 로그에 자동 기록됨
- [ ] `GET /api/query-history` 로 최근 쿼리 목록 조회 가능
- [ ] 로그에 실제 실행 SQL이 포함됨
- [ ] pre-aggregation 사용 여부가 로그에 표시됨
- [ ] UI에서 쿼리 클릭 시 SQL 전문 확인 가능
- [ ] `GET /api/pre-aggregations/status` 로 pre-agg 상태 조회 가능

## 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `CUBE_API_URL` | 프록시 대상 Cube URL | `http://localhost:4000` |
| `QUERY_LOG_DB` | SQLite 파일 경로 | `./query-logger/logs.db` |
| `QUERY_LOG_MAX_ROWS` | 최대 보관 로그 수 | `10000` |
| `LOGGER_PORT` | 프록시 서버 포트 | `4001` |
