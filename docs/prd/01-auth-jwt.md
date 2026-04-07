# PRD: JWT 기반 인증 / RBAC

## 개요

| 항목 | 내용 |
|------|------|
| 기능명 | JWT 기반 인증 및 역할(Role) 기반 접근 제어 |
| 브랜치 | `feature/auth-jwt` |
| 우선순위 | P0 |
| 난이도 | 낮음 |

## 배경 및 문제

Cube OSS는 인증/인가 기능을 제공하지 않아 누구나 API에 접근 가능하다.  
팀 단위 운영 시 데이터 접근 통제가 불가능하며, 민감한 비즈니스 지표가 무방비로 노출된다.

## 목표

- Cube API 호출 시 JWT 토큰 기반 인증 적용
- 역할(Role)에 따라 접근 가능한 Cube/Dimension/Measure 제한
- Row-level 필터를 securityContext로 자동 주입

## 범위

### In Scope
- `cube.js`의 `checkAuth` 훅을 이용한 JWT 검증
- `queryRewrite` 훅을 이용한 RBAC 필터 자동 적용
- 토큰 발급용 경량 Admin API (FastAPI)
- 역할/사용자 정의 설정 파일 (YAML 기반)
- Superset 연동 시 헤더 전달 가이드

### Out of Scope
- 로그인 UI (별도 `feature/model-editor-ui`에서 통합)
- OAuth / SSO 연동
- 토큰 Refresh 로직 (1차 구현에서 제외)

## 기능 명세

### 1. JWT 검증 (`cube.js`)

```
요청 흐름:
Client → Authorization: Bearer <JWT> → Cube API
                                          ↓
                                    checkAuth 훅
                                          ↓
                              JWT 서명 검증 (HS256)
                                          ↓
                              securityContext에 role, userId, allowedCubes 주입
```

- 토큰 만료 시 401 반환
- 서명 불일치 시 403 반환
- `CUBE_JWT_SECRET` 환경변수로 시크릿 관리

### 2. RBAC 필터 (`queryRewrite`)

역할별 접근 정책:

| 역할 | 설명 |
|------|------|
| `admin` | 모든 cube/view/dimension 접근 가능 |
| `analyst` | 허용된 cube 목록만 조회 가능 |
| `viewer` | 허용된 dimension만 조회, row-level 필터 적용 |

- 허용되지 않은 cube 접근 시 빈 결과 또는 403 반환
- row-level 필터는 `securityContext.rowFilters`를 `queryRewrite`에서 주입

### 3. 역할 설정 파일 (`auth/roles.yml`)

```yaml
roles:
  admin:
    allowedCubes: ["*"]
    allowedDimensions: ["*"]

  analyst:
    allowedCubes:
      - fact_contract
      - fact_payment
      - dim_customer
    allowedDimensions: ["*"]

  viewer:
    allowedCubes:
      - fact_contract
    allowedDimensions:
      - fact_contract.status
      - fact_contract.created_at
    rowFilters:
      fact_contract:
        company_id: "{userId}"
```

### 4. 토큰 발급 API

```
POST /auth/token
Body: { "userId": "hc", "role": "analyst" }
Response: { "token": "<JWT>", "expiresIn": 86400 }
```

- 1차 구현: API Key 방식 (헤더에 `X-Admin-Key` 필요)
- 토큰 유효기간: 24시간 (환경변수로 조정 가능)

## 구현 파일 목록

```
heartcube/
├── cube.js                        # checkAuth, queryRewrite 훅 추가
├── auth/
│   ├── roles.yml                  # 역할 정의
│   ├── users.yml                  # 사용자-역할 매핑
│   └── token_server.py            # FastAPI 토큰 발급 서버
├── .env.example                   # CUBE_JWT_SECRET 등 환경변수 예시
└── docs/prd/01-auth-jwt.md
```

## 수용 기준 (Acceptance Criteria)

- [ ] 유효한 JWT 없이 `/cubejs-api/v1/load` 호출 시 401 반환
- [ ] `analyst` 역할로 허용되지 않은 cube 쿼리 시 빈 결과 반환
- [ ] `viewer` 역할로 쿼리 시 rowFilter가 WHERE 절에 자동 주입됨
- [ ] `POST /auth/token` 으로 JWT 발급 가능
- [ ] Cube 재시작 없이 roles.yml 변경 반영 (파일 reload)

## 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `CUBE_JWT_SECRET` | JWT 서명 시크릿 | 없음 (필수) |
| `CUBE_JWT_EXPIRY` | 토큰 유효기간(초) | `86400` |
| `AUTH_ADMIN_KEY` | 토큰 발급 API 인증키 | 없음 (필수) |
| `AUTH_ROLES_PATH` | roles.yml 경로 | `./auth/roles.yml` |
