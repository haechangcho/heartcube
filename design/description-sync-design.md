# Description Sync Design: Cube View Members

## 1. 배경

dbt Semantic Layer 벤치마크는 LLM 프롬프트에 **NAME + DESCRIPTION** 두 필드를 함께 제공한다.

```python
# dbt SL 원본 방식
metrics_df     = sl.metrics()          # name, description, ...
dimensions_df  = sl.dimensions(...)    # name, description, ...
entities_df    = sl.entities(...)      # name, description, ...
```

Cube 벤치마크에서 동일한 맥락을 만들려면 `acme_ops` view의 각 member에 description이 있어야 하고, 그 내용이 LLM 프롬프트의 schema context에 포함되어야 한다.

---

## 2. Cube에서 Description이 흐르는 방식

```
acme_claim.yml                  acme_ops.yml
─────────────────               ──────────────────────────────────
measures:                       - join_path: acme_claim
  - name: claims                  includes:
    description: "Total           - claims          ← description 없음
      number of claims."
```

Cube는 view member에 `description`이 명시되지 않아도 `/meta` API 응답에서 **원본 cube member의 description을 자동 상속**한다.

```json
// GET /cubejs-api/v1/meta
{
  "cubes": [{
    "name": "acme_ops",
    "measures": [{
      "name": "acme_ops.claims",
      "description": "Total number of claims."   ← cube에서 자동 상속
    }]
  }]
}
```

따라서 **view YAML에 description을 별도로 쓰지 않아도** `/meta`에서 description을 읽으면 cube의 description이 이미 반영되어 있다.

---

## 3. 문제: `build_schema_context`가 description을 무시함

현재 파이프라인의 `build_schema_context`는 name만 나열한다.

```python
# 현재 (name만)
## acme_ops
dimensions: acme_ops.policy_number, acme_ops.company_claim_number, ...
measures:   acme_ops.claims, acme_ops.total_policy_amount, ...
```

```
# 목표 (name + description — dbt SL과 동일한 정보량)
## acme_ops
  dim  acme_ops.policy_number — The policy number.
  dim  acme_ops.company_claim_number — Unique claim identifier assigned by the company.
  msr  acme_ops.claims — Total number of claims.
  msr  acme_ops.total_policy_amount — The total amount associated with the policy.
```

---

## 4. 해결 방안

### 4-1. `build_schema_context` 수정 (필수)

`/meta` 응답에서 description을 읽어 포맷에 포함시킨다.

```python
def build_schema_context(cubes, only=None):
    lines = []
    for cube in cubes:
        if only and cube["name"] not in only:
            continue
        lines.append(f"\n## {cube['name']}")
        for d in cube.get("dimensions", []):
            desc = f" — {d['description']}" if d.get("description") else ""
            lines.append(f"  dim  {d['name']}{desc}")
        for m in cube.get("measures", []):
            desc = f" — {m['description']}" if m.get("description") else ""
            lines.append(f"  msr  {m['name']}{desc}")
    return "\n".join(lines)
```

이것만으로 벤치마크 파이프라인에서 description이 LLM 프롬프트에 포함된다.

### 4-2. View YAML에 description 명시 (선택)

view YAML에 description이 없어도 런타임에는 자동 상속된다. 그러나 **명시적으로 관리**하고 싶은 경우(override, 문서화 목적) 별도 동기화 스크립트를 만들 수 있다.

---

## 5. "Button" 접근법 설계 (선택적 도구)

### 개념

view YAML 편집 화면 상단에 **"Sync Descriptions from Cubes"** 버튼을 두고, 클릭하면 `/meta`에서 읽어온 description을 view YAML의 각 member에 기록한다.

### 우선순위 규칙

| view YAML description | 동작 |
|---|---|
| **있음** (`kpi.yml`, `ops.yml` 등) | 유지 — 절대 덮어쓰지 않음 |
| **없음** (`acme_ops.yml` 등) | `/meta`에서 읽어 채움 |

> `/meta`는 이미 "최종 description"을 반환한다. view member에 명시된 description이 있으면 그것을, 없으면 cube member의 description을 상속해서 내려준다. 따라서 YAML의 기존 description이 있는 member는 sync 대상에서 제외하는 것으로 충분하다.

### 동작 흐름

```
[버튼 클릭]
     │
     ▼
view YAML 파싱
     │
     ▼
include 항목 순회
     │
     ├── 이미 description 있음 (kpi.yml, ops.yml 방식)
     │     └── skip — 변경 없음
     │
     └── description 없음 (acme_ops.yml 방식)
           │
           ▼
     GET /cubejs-api/v1/meta
           │
           └── 해당 member의 description 조회
                 (view 명시 없으면 cube 상속값이 이미 반영되어 있음)
                 │
                 └── view YAML에 description 추가
```

### 구현 방식

```python
# sync_view_descriptions.py
import yaml, requests

META_URL = "http://<cube-host>:4000/cubejs-api/v1/meta"
VIEW_PATH = "model/views/acme_ops.yml"
TOKEN = os.environ.get("CUBE_TOKEN")

def sync_descriptions():
    # 1. /meta에서 view member descriptions 읽기
    cubes = requests.get(META_URL, headers={"Authorization": f"Bearer {TOKEN}"}).json()["cubes"]
    view = next(c for c in cubes if c["name"] == "acme_ops")

    desc_map = {}
    for d in view.get("dimensions", []):
        desc_map[d["name"].split(".")[-1]] = d.get("description", "")
    for m in view.get("measures", []):
        desc_map[m["name"].split(".")[-1]] = m.get("description", "")

    # 2. view YAML 읽기
    with open(VIEW_PATH) as f:
        doc = yaml.safe_load(f)

    # 3. include 항목에 description 주입
    for join in doc["views"][0].get("cubes", []):
        for i, member in enumerate(join.get("includes", [])):
            if isinstance(member, str) and member in desc_map and desc_map[member]:
                join["includes"][i] = {
                    "name": member,
                    "description": desc_map[member]
                }

    # 4. 다시 쓰기
    with open(VIEW_PATH, "w") as f:
        yaml.dump(doc, f, allow_unicode=True, sort_keys=False)

    print(f"Synced {len(desc_map)} member descriptions to {VIEW_PATH}")

if __name__ == "__main__":
    sync_descriptions()
```

### 주의사항

- `kpi.yml`, `ops.yml`처럼 view 레벨에서 직접 작성한 description은 **절대 건드리지 않음**
- `acme_ops.yml`처럼 description이 없는 member에만 적용
- Cube `/meta`는 이미 "최종 description"을 반환하므로, `/meta` 응답을 그대로 사용하면 됨
- 이 도구는 런타임 동작에 영향 없음 — 가시성·문서화 목적

---

## 6. 우선순위

| 작업 | 목적 | 필수 여부 |
|---|---|---|
| `build_schema_context` description 포함 | 벤치마크 LLM 프롬프트 품질 향상 | **필수** |
| cube member description 보완 | `/meta` 상속으로 view에 전달 | **필수** |
| view YAML에 description 명시 (`sync_view_descriptions.py`) | 문서화, override 가능성 | 선택 |

---

## 7. 다음 단계

1. `build_schema_context` 수정 → dev_mcp에 반영
2. description 누락된 cube member 보완 (현재 일부 member는 description 없음)
3. 수정 후 프롬프트 출력 검증 (`--dry-run` 옵션 추가)
4. 벤치마크 실행
