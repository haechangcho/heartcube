# PRD: 웹 기반 모델 에디터 UI

## 개요

| 항목 | 내용 |
|------|------|
| 기능명 | 웹 기반 YAML 모델 에디터 + Git 버전 관리 + 로그인 UI |
| 브랜치 | `feature/model-editor-ui` |
| 우선순위 | P4 |
| 난이도 | 높음 |

## 배경 및 문제

현재 Cube 모델 수정은 SSH로 접속하여 파일을 직접 편집해야 한다.  
비개발자는 사용 불가능하고, 수정 후 컴파일 오류를 확인하려면 로그를 직접 봐야 한다.  
변경 이력도 별도 관리가 필요하다.

## 목표

- 브라우저에서 cube/view YAML 파일을 직접 편집
- 저장 시 자동으로 컴파일 검증 후 결과 표시
- Git commit으로 변경 이력 자동 관리
- `feature/auth-jwt`의 로그인과 통합하여 권한 기반 편집 제어

## 범위

### In Scope
- 파일 목록 사이드바 (cubes/, views/ 디렉토리)
- Monaco Editor (YAML 신택스 하이라이팅)
- 저장 시 Cube `/meta` API로 컴파일 검증
- 저장마다 Git commit 자동 생성
- 파일별 변경 이력 조회 (git log)
- 특정 커밋으로 롤백
- 로그인 UI (JWT 연동)

### Out of Scope
- 실시간 협업 편집 (Google Docs 스타일)
- Visual(GUI) 모델러 (드래그앤드롭 방식)
- Cube JS (JavaScript) 형식 지원

## 기능 명세

### 1. 전체 화면 구성

```
┌──────────┬──────────────────────────────┬──────────────┐
│  파일목록 │      Monaco Editor           │  상태 패널   │
│          │                              │              │
│ cubes/   │  dimensions:                 │ ✓ 컴파일 OK  │
│  fact_.. │    - name: status            │              │
│  dim_..  │      sql: "{CUBE}.status"    │ 최근 커밋:   │
│          │      type: string            │ hc - 2분전   │
│ views/   │                              │ "add status" │
│  kpi.yml │                              │              │
│          │                              │ [이력보기]   │
│ [+ 신규] │              [저장]  [되돌리기]│ [롤백]       │
└──────────┴──────────────────────────────┴──────────────┘
```

### 2. 파일 관리 API (백엔드)

```
GET    /api/models                    # 파일 목록 (cubes/, views/)
GET    /api/models/:path              # 파일 내용 조회
PUT    /api/models/:path              # 파일 저장 + 컴파일 검증 + Git commit
DELETE /api/models/:path              # 파일 삭제
POST   /api/models                    # 신규 파일 생성

GET    /api/models/:path/history      # git log (파일별)
GET    /api/models/:path/diff/:hash   # 특정 커밋과의 diff
POST   /api/models/:path/rollback     # 특정 커밋으로 롤백
  Body: { "commitHash": "abc123" }
```

### 3. 컴파일 검증

파일 저장 시 자동 실행:

```
저장 요청
   ↓
파일 쓰기 (임시)
   ↓
Cube /meta API 호출 (타임아웃 10초)
   ↓
성공 → 정식 저장 + Git commit + 성공 메시지
실패 → 이전 내용 복원 + 오류 메시지 표시
```

오류 메시지는 Monaco Editor의 해당 라인에 인라인 표시.

### 4. Git 자동 커밋

```python
# 커밋 메시지 형식
f"[editor] {action}: {filename} by {userId}"
# 예: "[editor] update: model/cubes/fact_contract.yml by hc"
```

- 작성자(author): 로그인한 userId
- 이메일: `{userId}@heartcube` (더미)

### 5. 변경 이력 / 롤백 UI

```
┌─────────────────────────────────────────┐
│  fact_contract.yml 변경 이력             │
├──────────────┬───────┬──────────────────┤
│ 시각         │ 작성자 │ 커밋 메시지      │
├──────────────┼───────┼──────────────────┤
│ 2026-04-07   │ hc    │ add status dim   │
│ 15:32        │       │              [↩] │
├──────────────┼───────┼──────────────────┤
│ 2026-04-06   │ hc    │ init            │
│ 09:10        │       │              [↩] │
└──────────────┴───────┴──────────────────┘
```

`[↩]` 클릭 → 해당 버전으로 파일 복원 (새 commit 생성)

### 6. 로그인 UI

- `/login` 페이지: userId + password 입력
- `feature/auth-jwt`의 `POST /auth/token` 호출로 JWT 발급
- JWT를 sessionStorage에 저장, 이후 모든 API 요청 헤더에 첨부
- 역할이 `viewer`인 경우 에디터 저장 버튼 비활성화

## 구현 파일 목록

```
heartcube/
├── editor-api/                    # 백엔드 (FastAPI)
│   ├── main.py
│   ├── file_manager.py            # 파일 읽기/쓰기
│   ├── git_manager.py             # Git commit/log/rollback
│   ├── cube_validator.py          # /meta API 호출로 검증
│   └── requirements.txt
├── editor-ui/                     # 프론트엔드 (React)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   └── Editor.tsx
│   │   ├── components/
│   │   │   ├── FileTree.tsx
│   │   │   ├── MonacoEditor.tsx
│   │   │   ├── StatusPanel.tsx
│   │   │   └── HistoryModal.tsx
│   │   └── api/
│   │       └── client.ts
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml             # editor-api 서비스 추가
└── docs/prd/05-model-editor-ui.md
```

## 수용 기준 (Acceptance Criteria)

- [ ] 브라우저에서 cube/view YAML 파일 조회 및 편집 가능
- [ ] 저장 시 컴파일 오류가 있으면 파일이 변경되지 않고 오류 메시지 표시
- [ ] 저장 성공 시 Git commit이 자동 생성됨
- [ ] 파일별 변경 이력 조회 가능
- [ ] 특정 커밋으로 롤백 가능 (새 commit으로 생성)
- [ ] 로그인 후 JWT 기반으로 에디터 접근 제어 동작
- [ ] `viewer` 역할은 저장 버튼 비활성화

## 의존성

**Python (editor-api):**
```
fastapi>=0.110
uvicorn>=0.29
gitpython>=3.1
httpx>=0.24
pyyaml>=6.0
python-jose>=3.3    # JWT 검증
```

**Node (editor-ui):**
```
react, react-dom
@monaco-editor/react
vite
typescript
```
