# PRD: Cube/View 의존성 그래프 시각화

## 개요

| 항목 | 내용 |
|------|------|
| 기능명 | Cube/View Lineage 의존성 그래프 |
| 브랜치 | `feature/lineage-graph` |
| 우선순위 | P3 |
| 난이도 | 높음 |

## 배경 및 문제

Cube 모델이 늘어날수록 cubes ↔ views 사이의 참조 관계, join 관계를 파악하기 어려워진다.  
현재는 YAML 파일을 직접 열어 읽어야 하며, 관계를 한눈에 파악할 수 있는 UI가 없다.

## 목표

- cubes / views 간 의존 관계를 그래프로 시각화
- join 관계와 view 참조 관계를 구분하여 표현
- 노드 클릭 시 해당 모델의 dimensions/measures 목록 확인
- 단일 HTML 파일로 배포 가능 (별도 서버 불필요)

## 범위

### In Scope
- Cube `/meta` API 응답 파싱으로 그래프 데이터 추출
- ReactFlow 또는 D3.js 기반 인터랙티브 그래프
- cube / view 노드 타입 구분 (색상)
- join 관계(실선) / view 참조(점선) 구분
- 노드 클릭 시 상세 패널 (dimensions, measures, joins 목록)
- 검색으로 특정 노드 하이라이트

### Out of Scope
- 모델 파일 직접 편집 (별도 `feature/model-editor-ui`)
- 실시간 자동 갱신 (새로고침으로 최신 상태 반영)
- ERD 수준의 컬럼 레벨 lineage

## 기능 명세

### 1. 데이터 파싱 (`lineage_parser.py`)

Cube `/meta` API 응답에서 노드와 엣지를 추출한다.

**노드:**

| 속성 | 설명 |
|------|------|
| `id` | cube/view 이름 |
| `type` | `cube` 또는 `view` |
| `dimensions` | dimension 목록 |
| `measures` | measure 목록 |
| `sqlTable` | 원본 테이블명 (cube인 경우) |

**엣지:**

| 속성 | 설명 |
|------|------|
| `source` | 출발 노드 |
| `target` | 도착 노드 |
| `edgeType` | `join` 또는 `view_ref` |
| `relationship` | `many_to_one`, `one_to_many` 등 (join인 경우) |

### 2. 그래프 UI

```
┌────────────────────────────────────────────────────┐
│  Heartcube Lineage     [검색창]    [새로고침]       │
├────────────────────────────────────────────────────┤
│                                                    │
│   [dim_customer] ──────────── [fact_contract]      │
│                    many_to_one      │               │
│   [dim_product]  ──────────────────┘               │
│                                    │               │
│                              (점선) ↓               │
│                          [view: kpi]               │
│                                                    │
├────────────────────────────────────────────────────┤
│  [선택된 노드: fact_contract]                       │
│  Type: cube  |  Table: fact_contract               │
│  Dimensions: status, created_at, company_id ...    │
│  Measures: count, total_premium ...                │
│  Joins: dim_customer, dim_product                  │
└────────────────────────────────────────────────────┘
```

**범례:**
- 파란 노드: cube
- 초록 노드: view
- 실선 화살표: join 관계 (relationship 라벨 표시)
- 점선 화살표: view가 cube를 참조하는 관계

### 3. 배포 방식

- 단일 `lineage.html` 파일로 빌드 (인라인 JS/CSS)
- Cube `/meta` API URL을 URL 파라미터로 받아 동적 로드
  - 예: `lineage.html?api=http://localhost:4000`
- 또는 `tools/lineage_server.py`로 로컬 서버 실행 후 접속

```bash
# 로컬 서버 방식
python tools/lineage_server.py --cube-url http://localhost:4000 --port 8888

# 정적 파일 방식 (브라우저에서 직접 열기)
open docs/lineage.html?api=http://localhost:4000
```

## 구현 파일 목록

```
heartcube/
├── tools/
│   ├── lineage_parser.py      # /meta API 파싱 → 그래프 데이터
│   └── lineage_server.py      # 로컬 서버 (선택)
├── docs/
│   ├── lineage.html           # 빌드 결과 (정적 파일)
│   └── prd/04-lineage-graph.md
└── lineage-ui/                # 소스 (React + ReactFlow)
    ├── src/
    │   ├── App.tsx
    │   ├── GraphView.tsx
    │   ├── DetailPanel.tsx
    │   └── parser.ts
    └── package.json
```

## 수용 기준 (Acceptance Criteria)

- [ ] Cube `/meta` API를 읽어 모든 cube/view 노드가 그래프에 표시됨
- [ ] join 관계가 실선으로 표시되고 relationship 타입이 라벨로 표시됨
- [ ] view와 cube 노드가 색상으로 구분됨
- [ ] 노드 클릭 시 dimensions/measures 목록이 사이드 패널에 표시됨
- [ ] 검색창에서 노드 이름 입력 시 해당 노드 하이라이트
- [ ] `lineage.html` 단일 파일로 배포 가능

## 의존성

**Python:**
```
httpx>=0.24
```

**Node (lineage-ui):**
```
react, reactflow, @xyflow/react
vite (빌드)
```
