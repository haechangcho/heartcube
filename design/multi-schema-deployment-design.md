# Heartcube 멀티 스키마 배포 설계

## 1. 배경 및 결론

### 왜 별도 컨테이너인가

Cube Cloud 공식 문서 및 아키텍처 조사 결과:

- **별도 Deployment** = 완전히 다른 도메인/프로젝트 분리 (ODA vs ACME)
- **Multi-tenancy** = 같은 앱에서 고객별 데이터 필터링 (SaaS 패턴)

멀티테넌시(`contextToAppId` + `repositoryFactory`)는 브라우저에서 스키마가 고정되는 구조적 한계가 있고, 완전히 다른 스키마를 운영하는 패턴이 아님. Cube Cloud 유료 플랜도 동일하게 스키마 단위 Deployment 분리를 권장.

**자체 호스팅 대응:**

| Cube Cloud | 자체 호스팅 |
|---|---|
| 별도 Deployment | 별도 Docker 컨테이너 |
| 무제한 Deployment (Starter+) | `docker-compose.yml` 서비스 블록 추가 |
| 독립 API endpoint | 포트 분리 |

---

## 2. 목표 아키텍처

```
dev_mcp
├── heartcube     (포트 4000)  ← ODA 스키마, 상시 운영
├── acme-cube     (포트 4001)  ← ACME 벤치마크, 필요 시 운영
└── heartcube-auth (포트 5101) ← ODA 전용 브라우저 프록시 (기존 유지)

향후 추가 시:
└── xyz-cube      (포트 4002)  ← 신규 스키마, docker-compose 블록 추가만
```

### 핵심 설계 원칙

1. **동일 Docker 이미지 공유** — `heartcube:latest` 이미지를 모든 스키마 컨테이너가 공유. 빌드 1회로 유지.
2. **`CUBE_MODEL_PATH` 환경변수로 모델 경로 분기** — `cube.js` 하나로 모든 컨테이너 지원.
3. **스키마 추가 = 폴더 + 서비스 블록 추가** — 기존 파일 수정 없이 확장.
4. **`.env.{schema}`로 환경 분리** — DB 접속정보, API Secret, 포트를 스키마별로 관리.

---

## 3. 디렉토리 구조

```
~/heartcube/
├── cube.js                    ← 신규: CUBE_MODEL_PATH 기반 repositoryFactory
├── docker-compose.yml         ← 수정: acme-cube 서비스 블록 추가
├── .env                       ← 기존: ODA (heartcube용)
├── .env.acme                  ← 신규: ACME (acme-cube용)
│
├── model/                     ← 기존: ODA 스키마 (변경 없음)
│   ├── cubes/
│   └── views/
│
└── model_acme/                ← 신규: ACME 스키마
    ├── cubes/
    └── views/

향후 xyz 스키마 추가 시:
└── model_xyz/
    ├── cubes/
    └── views/
```

---

## 4. 구현 단계

### Phase 1 — `cube.js` 추가

`CUBE_MODEL_PATH` 환경변수로 모델 디렉토리를 지정. 미설정 시 기본값 `model` (ODA).

```js
// ~/heartcube/cube.js
const { FileRepository } = require('@cubejs-backend/server-core');

module.exports = {
  repositoryFactory: () => {
    const modelPath = process.env.CUBE_MODEL_PATH || 'model';
    return new FileRepository(modelPath);
  },
};
```

> **기존 heartcube 영향 없음** — `CUBE_MODEL_PATH` 미설정 시 현재와 동일하게 `model/` 로드.

---

### Phase 2 — `docker-compose.yml` 업데이트

```yaml
services:
  # ── 기존 ODA 스키마 ────────────────────────────────────────────────────────
  cube:
    image: heartcube:latest
    container_name: heartcube
    ports:
      - "15432:15432"
    env_file:
      - .env
    volumes:
      - .:/cubejs/conf
    restart: unless-stopped
    networks:
      - heartcube_net

  # ── ACME 벤치마크 스키마 ───────────────────────────────────────────────────
  acme-cube:
    image: heartcube:latest           # 동일 이미지 재사용, 빌드 불필요
    container_name: acme-cube
    ports:
      - "4001:4000"
    env_file:
      - .env.acme
    volumes:
      - .:/cubejs/conf                # 동일 repo 마운트, 모델 경로만 다름
    restart: unless-stopped
    networks:
      - heartcube_net

  auth:
    image: heartcube-auth:latest
    container_name: heartcube-auth
    ports:
      - "5101:3000"
    env_file:
      - .env
    depends_on:
      - cube
    restart: unless-stopped
    networks:
      - heartcube_net

networks:
  heartcube_net:
    driver: bridge
```

---

### Phase 3 — `.env.acme` 생성

```bash
# .env.acme
CUBEJS_DB_TYPE=postgres
CUBEJS_DB_HOST=20.0.1.10
CUBEJS_DB_PORT=5432
CUBEJS_DB_NAME=sampledb
CUBEJS_DB_USER=abiuser
CUBEJS_DB_PASS=#tbvjtpt

# ODA와 다른 값
CUBE_MODEL_PATH=model_acme               # acme 모델 경로
CUBEJS_API_SECRET=acme-secret-change-me  # ODA와 분리된 secret
CUBEJS_DEV_MODE=true
CUBEJS_CACHE_AND_QUEUE_DRIVER=cubestore
CUBEJS_SCHEDULED_REFRESH_DEFAULT=true
CUBE_API_KEY=<acme_api_key>
```

---

### Phase 4 — `model_acme/` 구조 준비

DBA 승인 후 테이블 생성 완료 시점에 모델 파일 작성.

```
model_acme/
├── cubes/
│   ├── acme_claim.yml
│   ├── acme_claim_amount.yml
│   ├── acme_loss_payment.yml
│   ├── acme_loss_reserve.yml
│   ├── acme_expense_payment.yml
│   ├── acme_expense_reserve.yml
│   ├── acme_claim_coverage.yml
│   ├── acme_policy_coverage_detail.yml
│   ├── acme_policy.yml
│   ├── acme_policy_amount.yml
│   ├── acme_premium.yml
│   ├── acme_agreement_party_role.yml
│   └── acme_catastrophe.yml
└── views/
    └── acme_ops.yml
```

---

### Phase 5 — 벤치마크 파이프라인 연결

`acme_benchmark_pipeline.py`에서 acme-cube 엔드포인트 사용.

```python
# acme_benchmark_pipeline.py
CUBE_BASE_URL = "http://172.20.0.2:4001/cubejs-api/v1"  # 포트 4001
CUBE_TOKEN    = "<acme secret으로 생성한 토큰>"
```

---

## 5. 향후 스키마 추가 절차

새로운 스키마(예: `xyz`) 추가 시 작업 범위:

```
1. model_xyz/ 디렉토리 생성 후 cubes/ views/ 작성
2. .env.xyz 파일 생성 (CUBE_MODEL_PATH=model_xyz)
3. docker-compose.yml에 xyz-cube 서비스 블록 추가 (포트 4002)
4. docker compose up -d xyz-cube
```

`cube.js`, Dockerfile, 기존 서비스 — 변경 없음.

---

## 6. 구현 체크리스트

### 사전 조건
- [ ] DBA에게 `oda.acme_*` 테이블 13개 DDL 실행 및 `abiuser` 권한 부여 요청

### Phase 1 — cube.js
- [ ] `cube.js` 작성 및 커밋
- [ ] 기존 heartcube 정상 동작 확인 (모델 로드 regression 없음)

### Phase 2 — docker-compose
- [ ] `docker-compose.yml`에 `acme-cube` 서비스 블록 추가
- [ ] `.env.acme` 파일 생성 (`.gitignore`에 추가)

### Phase 3 — ACME 모델
- [ ] `model_acme/cubes/` — acme_*.yml 13개 작성
- [ ] `model_acme/views/acme_ops.yml` 작성
- [ ] `acme-cube` 컨테이너 기동: `docker compose up -d acme-cube`
- [ ] `/meta` 응답에 `acme_ops` 포함 확인

### Phase 4 — 데이터 적재
- [ ] CSV → dev_mcp 전송
- [ ] `acme_load_data.py` 실행
- [ ] 테이블별 행 수 검증

### Phase 5 — 벤치마크
- [ ] `acme_benchmark_pipeline.py` CUBE_BASE_URL 포트 4001로 변경
- [ ] Gold 쿼리 11개 curl 검증
- [ ] 전체 파이프라인 실행 (5 iter × 11 질문 = 55건)

---

## 7. 참고

- Cube Cloud 공식 문서: 스키마 단위 분리 = 별도 Deployment 권장
- Cube Cloud Starter 이상: Deployment 무제한
- Multi-tenancy(`contextToAppId`)는 SaaS 고객별 데이터 필터링 패턴으로, 완전히 다른 스키마 분리에는 부적합
