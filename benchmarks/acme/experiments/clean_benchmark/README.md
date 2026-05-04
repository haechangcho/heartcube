# Clean 3-Phase Benchmark: 설계 문서 & 실행 상태

이 문서는 다른 에이전트(Codex 등)가 이어서 작업할 수 있도록 작성되었습니다.
**Status 섹션을 반드시 확인하고 이어서 진행하세요.**

---

## 목적

기존 실험이 파편화되어 있어, 아래 3단계를 깔끔하게 재현:

| 단계 | 변수 | 목적 |
|------|------|------|
| Exp 1 | Few-shot 3개 (balanced) | 새 기준선 수립 |
| Exp 2 | Exp 1 + Agentic loop | Loop 효과 측정 |
| Exp 3 | Exp 2 + Schema fix | Schema 설계 효과 측정 |

각 실험은 변수 하나씩만 추가하여 독립적으로 비교 가능.

---

## 핵심 설계 결정

### Few-shot (3개, DDL과 동일 수)
DDL 벤치마크 3개와 동일한 구조로 맞춤:
- Example 1: aggregate (dimension + measure + order)
- Example 2: **listing (dimension만, measure 없음)** + implicit JOIN 설명
- Example 3: aggregate + filter

Exp 1/2/3 모두 동일한 few-shot 사용.
**Example 3 내용이 다름**: Exp 1/2는 party_identifier 기반, Exp 3는 policyholder_id 기반.

### Schema 버전
- **V1 (Exp 1/2용)**: party_identifier + party_role_code in acme_ops view
- **V2 (Exp 3용)**: policyholder_id + agent_id, party_identifier 제거

### Gold Query 버전
- **V1**: party_identifier + party_role_code filter 사용
  - 파일: `questions/cube_questions_v1.md`
  - git ref: `4dc117b1b`
- **V2**: policyholder_id / agent_id 사용, role filter 제거
  - 파일: `questions/cube_questions_v2.md`
  - git ref: current HEAD (heartcube-1.6.25)

---

## 파일 구조

```
experiments/clean_benchmark/
├── README.md                          ← 이 파일 (설계 + 상태)
├── scripts/
│   ├── exp1_single_shot.py            ← 전체 43문, single-shot, V1 schema/gold
│   ├── exp2_agentic_loop.py           ← LQLS+LQHS, agentic loop, V1 schema/gold
│   └── exp3_schema_fix.py             ← LQLS+LQHS, agentic loop, V2 schema/gold
├── questions/
│   ├── cube_questions_v1.md           ← 원본 gold (party_identifier 기반)
│   ├── cube_questions_v2.md           ← 수정된 gold (policyholder_id 기반)
│   └── acme_ops_v1.yml                ← 원본 view 참조용 (실제 적용은 model/views/)
├── results/
│   ├── exp1_single_shot.csv           ← Exp 1 결과 (실행 후 생성)
│   ├── exp2_agentic_loop.csv          ← Exp 2 결과 (실행 후 생성)
│   └── exp3_schema_fix.csv            ← Exp 3 결과 (실행 후 생성)
└── report.md                          ← 최종 보고서 (실험 완료 후 작성)
```

---

## 실행 환경

- **서버**: dev_mcp (AWS EC2, `ssh dev_mcp`)
- **SSH**: `ssh-add ~/.ssh/id_ed25519` (passphrase: roqhrcl) → `ssh dev_mcp`
- **Cube URL**: `http://172.20.0.3:4000/cubejs-api/v1`
- **Cube restart**: `cd ~/heartcube && docker compose restart cube`
- **작업 디렉토리**: `~/heartcube/benchmarks/acme/experiments/clean_benchmark`
- **Python 실행**: `ACME_LLM_MODEL=gpt-5.3-chat-latest python3 scripts/exp{N}.py`

---

## 실행 순서

### Step 1: Exp 1 실행 준비 — V1 Schema 적용

Exp 1/2는 OLD schema가 필요합니다. 현재 서버는 NEW schema 상태입니다.

```bash
# 로컬에서:
# 1. V1 view를 model/views/acme_ops.yml에 복원
cp benchmarks/acme/experiments/clean_benchmark/questions/acme_ops_v1.yml model/views/acme_ops.yml
git add model/views/acme_ops.yml
git commit -m "temp: revert acme_ops to v1 for Exp1/2"
git push origin benchmark/clean-3phase

# 2. 서버에서 pull + restart
ssh dev_mcp "cd ~/heartcube && git checkout benchmark/clean-3phase && git pull && docker compose restart cube"
```

### Step 2: Exp 1 실행

```bash
ssh dev_mcp "cd ~/heartcube/benchmarks/acme/experiments/clean_benchmark && ACME_LLM_MODEL=gpt-5.3-chat-latest python3 scripts/exp1_single_shot.py 2>&1 | tee /tmp/exp1.log"
```

**완료 후**: results/exp1_single_shot.csv 생성됨. README Status 업데이트.

### Step 3: Exp 2 실행 (V1 schema 유지)

```bash
ssh dev_mcp "cd ~/heartcube/benchmarks/acme/experiments/clean_benchmark && ACME_LLM_MODEL=gpt-5.3-chat-latest python3 scripts/exp2_agentic_loop.py 2>&1 | tee /tmp/exp2.log"
```

**완료 후**: results/exp2_agentic_loop.csv 생성됨. README Status 업데이트.

### Step 4: Exp 3 준비 — V2 Schema 적용

```bash
# 로컬에서:
# V2 view 복원 (현재 heartcube-1.6.25의 acme_ops.yml)
git show heartcube-1.6.25:model/views/acme_ops.yml > model/views/acme_ops.yml
git add model/views/acme_ops.yml
git commit -m "restore: acme_ops to v2 for Exp3"
git push origin benchmark/clean-3phase

# 서버에서 pull + restart
ssh dev_mcp "cd ~/heartcube && git pull && docker compose restart cube && sleep 10"
```

### Step 5: Exp 3 실행

```bash
ssh dev_mcp "cd ~/heartcube/benchmarks/acme/experiments/clean_benchmark && ACME_LLM_MODEL=gpt-5.3-chat-latest python3 scripts/exp3_schema_fix.py 2>&1 | tee /tmp/exp3.log"
```

**완료 후**: results/exp3_schema_fix.csv 생성됨. README Status 업데이트.

### Step 6: 결과 수집 & 보고서 작성

```bash
# 로컬로 결과 복사
scp dev_mcp:~/heartcube/benchmarks/acme/experiments/clean_benchmark/results/*.csv benchmarks/acme/experiments/clean_benchmark/results/

# 결과 커밋
git add benchmarks/acme/experiments/clean_benchmark/results/
git commit -m "chore(benchmark): add clean 3-phase experiment results"
git push origin benchmark/clean-3phase
```

report.md 작성 후 PR 또는 merge.

---

## Status

> **현재 담당 에이전트가 이 섹션을 업데이트해야 합니다.**

### 준비 작업
- [x] 브랜치 생성: `benchmark/clean-3phase`
- [x] 디렉토리 구조 생성
- [x] `cube_questions_v1.md` 복원 (git ref: `4dc117b1b`)
- [x] `cube_questions_v2.md` 복사 (current HEAD)
- [x] `acme_ops_v1.yml` 참조 파일 생성
- [x] `exp1_single_shot.py` 작성
- [x] `exp2_agentic_loop.py` 작성
- [x] `exp3_schema_fix.py` 작성
- [x] V1 schema를 acme_ops.yml에 적용 + 커밋 + push
- [x] 서버에서 V1 schema pull + Cube restart 확인

### Exp 1: Single-shot baseline
- [x] 완료: results/exp1_single_shot.csv 생성됨
- [x] 결과: LQLS 91.7% / LQHS 68.0% / HQLS 96.4% / HQHS 88.0%
- 실패 9개: LQLS_06, LQHS_02/03/04/05/06, HQLS_09, HQHS_04/08

### Exp 2: Agentic loop (Exp1 실패 질문 9개 대상)
- [x] 완료: results/exp2_agentic_loop.csv 생성됨
- [x] 결과: HQLS_09 100% 해결. 나머지 8개 여전히 실패
- 핵심 발견: 모든 실패가 att=1 (retry 미발동) → 실행 성공하지만 결과 틀림
- 아직 실패: LQLS_06, LQHS_02/03/04/05/06, HQHS_04/08

### Exp 3: Schema fix (Exp2 실패 질문 8개 대상)
- [x] V2 schema 적용 + Cube restart 완료
- [x] 완료: results/exp3_schema_fix.csv 생성됨
- [x] 결과 확인
  - LQHS_03: 0%→100% ✓  LQHS_04: 0%→100% ✓
  - LQHS_02: 80%→100% ✓  LQHS_05: 80%→100% ✓
  - HQHS_04: 80%→100% ✓  LQLS_06: 0%→40%
  - LQHS_06: 60%→60%     HQHS_08: 0%→0%

### 최종
- [x] 결과 로컬 복사 + 커밋
- [x] report.md 작성
- [ ] PR 생성

---

## 예상 결과 (가설)

| | LQLS | LQHS | HQLS | HQHS |
|--|------|------|------|------|
| Exp 1 (single-shot) | ~75% | ~62% | ~90% | ~88% |
| Exp 2 (+agentic) | ~90% | ~72% | - | - |
| Exp 3 (+schema) | ~93% | ~90% | - | - |

- Exp 1 vs 2: agentic loop 효과 (exec error retry)
- Exp 2 vs 3: schema 설계 효과 (Q15/Q16: 0%→100% 예상, Q18 부분 개선)

---

## 주의사항

1. Exp 1/2는 V1 schema (party_identifier in view)에서 실행해야 합니다.
   schema check 로그에서 `party_identifier: True`를 확인 후 진행하세요.

2. Exp 3은 V2 schema (policyholder_id in view)에서 실행해야 합니다.
   schema check 로그에서 `policyholder_id: True`를 확인 후 진행하세요.

3. 각 실험 후 결과 파일을 반드시 로컬로 복사하고 커밋하세요.

4. 실험 도중 토큰이 소진되면 이 README의 Status를 확인하고 이어서 진행하세요.
