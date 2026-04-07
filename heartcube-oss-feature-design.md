# Heartcube OSS 기능 개발 설계서

> Cube OSS의 유료 기능 한계를 자체 구현으로 대체하기 위한 기능 설계 문서

---

## 개요

| 구분 | 내용 |
|------|------|
| 대상 시스템 | Heartcube (Cube OSS 기반 Semantic Layer) |
| 작성일 | 2026-04-07 |
| 목적 | Cube OSS 한계 극복을 위한 자체 기능 개발 |

---

## 1. 권한 / 사용자 관리

### 문제
- Cube OSS는 로그인 기능 없음 → 팀 단위 운영 시 접근 통제 불가
- Role 기반 접근 제어(RBAC) 미지원

### 설계 방향

#### 1-1. JWT 기반 인증 미들웨어
Cube OSS는 `checkAuth` 컨텍스트 훅을 제공하므로, 이를 활용해 자체 JWT 인증을 구현한다.

```
[Client] → JWT Token → [Nginx/Proxy] → [Cube API]
                                          ↓
                                    checkAuth hook
                                          ↓
                                    Token 검증 + securityContext 주입
```

**구현 파일:** `cube.js` (또는 `cube.py`)

```javascript
// cube.js
module.exports = {
  checkAuth: async (auth, securityContext) => {
    const token = auth; // Authorization: Bearer <token>
    const payload = verifyJWT(token, process.env.JWT_SECRET);
    // payload: { userId, role, allowedCubes }
    securityContext.userId = payload.userId;
    securityContext.role = payload.role;
    securityContext.allowedCubes = payload.allowedCubes;
  },

  queryRewrite: (query, { securityContext }) => {
    // RBAC: role에 따라 쿼리 필터 자동 주입
    if (securityContext.role === 'viewer') {
      // viewer는 특정 dimension만 조회 가능
      query.dimensions = query.dimensions?.filter(d =>
        securityContext.allowedDimensions?.includes(d)
      );
    }
    return query;
  }
};
```

#### 1-2. 관리 API 서버 (별도 서비스)
사용자/역할 관리를 위한 경량 Admin API를 별도로 구축한다.

**기술 스택:** FastAPI (Python) 또는 Express (Node.js)

**엔드포인트:**
```
POST   /auth/login          → JWT 발급
POST   /auth/refresh        → 토큰 갱신
GET    /admin/users         → 사용자 목록
POST   /admin/users         → 사용자 생성
PATCH  /admin/users/:id     → 역할/권한 수정
DELETE /admin/users/:id     → 사용자 삭제
GET    /admin/roles         → 역할 목록
POST   /admin/roles         → 역할 생성 (허용 cube/view 지정)
```

**역할(Role) 스키마:**
```json
{
  "role": "analyst",
  "allowedCubes": ["orders", "customers"],
  "allowedDimensions": ["orders.status", "customers.region"],
  "rowFilters": {
    "orders": { "company_id": "{userId}" }
  }
}
```

#### 1-3. 간이 로그인 UI
- 별도 웹페이지(또는 Nginx 앞단)에 로그인 폼 제공
- 로그인 성공 시 JWT를 localStorage에 저장 후 Cube API 호출에 헤더로 첨부
- Superset 연동 시 Superset의 `JINJA_CONTEXT_ADDONS` + 커스텀 헤더로 토큰 전달

---

## 2. 모델 관리 UI

### 문제
- 파일 기반 수정만 가능 → 비개발자 사용 어려움
- 컴파일 오류 직접 확인 필요
- 버전 관리 내장 없음

### 설계 방향

#### 2-1. 웹 기반 YAML 에디터
Monaco Editor(VS Code와 동일한 에디터 엔진)를 내장한 간단한 웹 UI를 구축한다.

```
[브라우저 UI]
  ├── 파일 목록 사이드바 (cubes/, views/ 디렉토리)
  ├── Monaco Editor (YAML 신택스 하이라이팅)
  ├── 저장 버튼 → REST API → 파일 시스템 업데이트
  └── 오류 패널 → Cube /meta API 호출로 컴파일 결과 확인
```

**기술 스택:** React + Monaco Editor + FastAPI

**백엔드 API:**
```
GET    /api/models              → 모델 파일 목록
GET    /api/models/:filename    → 파일 내용 조회
PUT    /api/models/:filename    → 파일 저장
DELETE /api/models/:filename    → 파일 삭제
POST   /api/models/validate     → Cube /meta 호출로 컴파일 검증
```

#### 2-2. 컴파일 오류 자동 검증
파일 저장 시 자동으로 Cube의 `/cubejs-api/v1/meta` API를 호출하여 오류 여부를 확인한다.

```python
# validate.py
import httpx

async def validate_cube_models():
    try:
        resp = await httpx.get("http://localhost:4000/cubejs-api/v1/meta",
                               headers={"Authorization": f"Bearer {CUBE_TOKEN}"})
        if resp.status_code == 200:
            return {"valid": True}
        else:
            return {"valid": False, "error": resp.json()}
    except Exception as e:
        return {"valid": False, "error": str(e)}
```

#### 2-3. Git 기반 버전 관리 연동
모델 파일 저장 시 자동으로 Git commit을 생성하여 변경 이력을 관리한다.

```python
# git_manager.py
import subprocess

def commit_model_change(filename: str, author: str, message: str):
    subprocess.run(["git", "add", filename], cwd=MODELS_PATH)
    subprocess.run([
        "git", "commit",
        "--author", f"{author} <{author}@heartcube>",
        "-m", message
    ], cwd=MODELS_PATH)
```

**UI에서 제공:**
- 파일별 변경 이력 조회 (`git log --follow <file>`)
- 특정 커밋으로 롤백
- diff 뷰어

---

## 3. Data Model 생성 기능 개선

### 문제
- `generate` 실행 시 기존 모델 덮어씀 → 기존 작업 내용 유지/병합 불가
- FK 기반 join 자동 생성 미지원

### 설계 방향

#### 3-1. 스마트 모델 생성기 (Merge-safe Generator)
기존 파일을 덮어쓰지 않고, 신규 필드/큐브만 추가하는 병합(merge) 방식으로 생성한다.

```python
# smart_generator.py
import yaml
from pathlib import Path

def generate_or_merge(table_name: str, columns: list, existing_path: Path):
    new_model = build_cube_yaml(table_name, columns)

    if existing_path.exists():
        existing = yaml.safe_load(existing_path.read_text())
        merged = merge_cubes(existing, new_model)
        # 기존 커스텀 measures/dimensions 유지, 신규 컬럼만 추가
    else:
        merged = new_model

    existing_path.write_text(yaml.dump(merged, allow_unicode=True))

def merge_cubes(existing: dict, new: dict) -> dict:
    existing_dims = {d['name']: d for d in existing.get('dimensions', [])}
    new_dims = {d['name']: d for d in new.get('dimensions', [])}

    # 기존에 없는 dimension만 추가
    for name, dim in new_dims.items():
        if name not in existing_dims:
            existing['dimensions'].append(dim)

    return existing
```

#### 3-2. FK 기반 Join 자동 생성
DB의 FOREIGN KEY 제약 정보를 읽어 join 관계를 자동 추론한다.

```python
# fk_join_generator.py

FK_QUERY = """
SELECT
    tc.table_name AS from_table,
    kcu.column_name AS from_column,
    ccu.table_name AS to_table,
    ccu.column_name AS to_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';
"""

def generate_joins_from_fk(conn) -> dict:
    rows = conn.execute(FK_QUERY).fetchall()
    joins = {}
    for row in rows:
        from_table, from_col, to_table, to_col = row
        joins.setdefault(from_table, []).append({
            "name": to_table,
            "relationship": "many_to_one",
            "sql": f"{{CUBE}}.{from_col} = {{{to_table}}}.{to_col}"
        })
    return joins
```

**생성 결과 예시:**
```yaml
cubes:
  - name: orders
    sql_table: orders
    joins:
      - name: customers
        relationship: many_to_one
        sql: "{CUBE}.customer_id = {customers}.id"
```

---

## 4. 구조 가시성 (Lineage / Dependency Map)

### 문제
- views ↔ cubes 관계를 한눈에 파악하기 어려움
- 모델이 복잡해질수록 유지보수 어려움

### 설계 방향

#### 4-1. Cube/View 의존성 그래프 시각화
Cube의 `/meta` API 응답을 파싱하여 cubes ↔ views 관계를 시각화한다.

```
[Cube /meta API]
      ↓
[파서: 관계 추출]
      ↓
[D3.js / ReactFlow 기반 그래프 렌더링]
```

**파싱 로직:**
```python
# lineage_parser.py

def extract_lineage(meta_response: dict) -> dict:
    nodes = []
    edges = []

    for cube in meta_response.get('cubes', []):
        cube_name = cube['name']
        cube_type = 'view' if cube.get('isView') else 'cube'
        nodes.append({"id": cube_name, "type": cube_type})

        # view → cube 의존성 추출
        for dim in cube.get('dimensions', []) + cube.get('measures', []):
            if 'cubes' in dim:  # view가 참조하는 cube
                for ref_cube in dim['cubes']:
                    edges.append({
                        "from": cube_name,
                        "to": ref_cube,
                        "type": "references"
                    })

        # join 관계 추출
        for join in cube.get('joins', []):
            edges.append({
                "from": cube_name,
                "to": join['name'],
                "type": "join",
                "relationship": join['relationship']
            })

    return {"nodes": nodes, "edges": edges}
```

**UI 구성:**
- 노드: cube(파란색), view(초록색) 구분 표시
- 엣지: join 관계(실선), view 참조(점선) 구분
- 클릭 시 해당 모델 파일로 이동

---

## 5. BI 연동 디버깅 도구

### 문제
- Superset 연동 시 실제 실행 쿼리 확인 어려움
- 어떤 cube/view가 사용됐는지 추적 어려움
- pre-aggregation 적용 여부 확인 어려움

### 설계 방향

#### 5-1. Query 로깅 미들웨어
Cube API 앞단에 Nginx 또는 Node.js 프록시를 두어 모든 쿼리를 로깅한다.

```javascript
// query-logger.js (Express 미들웨어)
const fs = require('fs');
const path = require('path');

function queryLogger(req, res, next) {
  if (req.path.includes('/cubejs-api/v1/load')) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      userId: req.headers['x-user-id'] || 'anonymous',
      query: req.body,
      requestId: req.headers['x-request-id']
    };

    // 응답 인터셉트
    const originalJson = res.json.bind(res);
    res.json = (data) => {
      logEntry.sql = data?.results?.[0]?.query?.sql;
      logEntry.preAggregationUsed = !!data?.results?.[0]?.usedPreAggregations?.length;
      logEntry.duration = Date.now() - req._startTime;

      // 파일 또는 DB에 저장
      appendLog(logEntry);
      return originalJson(data);
    };
  }
  next();
}
```

#### 5-2. Query History 대시보드
수집된 쿼리 로그를 조회할 수 있는 간단한 UI를 제공한다.

**기능:**
- 최근 N건 쿼리 목록
- 실제 생성된 SQL 확인
- 사용된 cube/view/dimension/measure 표시
- pre-aggregation 적용 여부 뱃지
- 실행 시간(duration) 표시
- 사용자별 필터링

**API:**
```
GET /api/query-history?limit=50&userId=...&from=...&to=...
GET /api/query-history/:requestId   → 특정 쿼리 상세
```

#### 5-3. Pre-aggregation 상태 확인 도구
Cube의 `/cubejs-api/v1/pre-aggregations/jobs` API를 래핑하여 UI로 제공한다.

```python
# pre_agg_monitor.py

async def get_pre_aggregation_status():
    resp = await httpx.get(
        "http://localhost:4000/cubejs-api/v1/pre-aggregations/jobs",
        headers={"Authorization": f"Bearer {CUBE_TOKEN}"}
    )
    jobs = resp.json()
    return [{
        "cube": job["tableName"],
        "status": job["status"],   # scheduled / processing / done / error
        "lastRefresh": job["updatedAt"],
        "rowCount": job.get("rowCount")
    } for job in jobs]
```

---

## 구현 우선순위

| 우선순위 | 기능 | 난이도 | 예상 공수 |
|----------|------|--------|----------|
| 1 | JWT 인증 미들웨어 (cube.js checkAuth) | 낮음 | 1~2일 |
| 2 | Query 로깅 미들웨어 + History UI | 중간 | 3~5일 |
| 3 | FK 기반 Join 자동 생성 | 중간 | 2~3일 |
| 4 | 스마트 모델 생성기 (Merge-safe) | 중간 | 2~3일 |
| 5 | 웹 기반 YAML 에디터 + Git 연동 | 높음 | 1~2주 |
| 6 | Cube/View 의존성 그래프 | 높음 | 1주 |
| 7 | 관리 API 서버 (Admin UI) | 높음 | 1~2주 |

---

## 시스템 구성도 (목표)

```
[사용자]
    │
    ├── 로그인 UI → Admin API → JWT 발급
    │
    ├── 모델 에디터 UI ──→ 파일시스템 (cubes/, views/)
    │        └──────────→ Git (버전 관리)
    │
    ├── 구조 시각화 UI ──→ Cube /meta API
    │
    ├── Query History UI → 로그 DB/파일
    │
    └── BI Tool (Superset)
             │ JWT 헤더
             ↓
        [Query Logger Proxy]
             ↓
        [Cube OSS :4000]
             ├── checkAuth → JWT 검증
             ├── queryRewrite → RBAC 필터 적용
             └── 결과 반환
```

---

## 디렉토리 구조 (제안)

```
/home/ubuntu/heartcube/
├── cube/                    # 기존 Cube OSS 설정
│   ├── model/
│   │   ├── cubes/
│   │   └── views/
│   └── cube.js
├── admin-api/               # 관리 API 서버 (신규)
│   ├── main.py
│   ├── auth/
│   ├── models_api/
│   └── query_log/
├── editor-ui/               # 모델 에디터 UI (신규)
│   ├── src/
│   └── public/
├── tools/                   # CLI 유틸리티 (신규)
│   ├── smart_generator.py
│   ├── fk_join_generator.py
│   └── lineage_parser.py
└── docker-compose.yml       # 전체 서비스 오케스트레이션
```

---

*본 문서는 Cube OSS 한계를 자체 구현으로 극복하기 위한 기능 설계서입니다. 구현 순서 및 범위는 팀 상황에 따라 조정 가능합니다.*
