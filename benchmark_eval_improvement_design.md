# Cube Benchmark 평가 지표 개선 — 기능 개발 설계서

> 작성일: 2026-04-07  
> 대상 파일: `dev_mcp:~/heartcube/benchmark_pipeline.py`  
> 목적: Jaccard 기반 평가의 한계를 극복하고, 논문 수준의 멀티 지표 평가 체계를 구축한다.

---

## 1. 현재 상태 (As-Is)

`benchmark_pipeline.py`의 현재 평가 지표:

| 지표 | 함수 | 상태 |
|---|---|---|
| Component F1 (dim/msr/filter) | `component_f1()`, `structural_accuracy()` | ✅ 구현 완료 |
| Soft Result F1 (값 정규화) | `soft_result_f1()`, `_normalize_row()` | ✅ 구현 완료 |
| Valid Query Rate 단계별 집계 | `json_parse_ok`, `exec_ok` 컬럼 + funnel 출력 | ✅ 구현 완료 |
| LLM-as-Judge (엣지케이스) | `llm_judge()` | ✅ 구현 완료 |
| KDL prefix 준수율 | — | ❌ 미구현 |
| 반복(iteration)별 신뢰구간 리포트 | — | ❌ 미구현 |
| 카테고리×지표 히트맵 시각화 | — | ❌ 미구현 |

---

## 2. 개발할 기능 목록 (To-Do)

### Feature 1: KDL Prefix 준수율 (`prefix_compliance_score`)

**배경**  
KDL 카테고리 질문은 반드시 `kpi.` prefix를 사용해야 한다. 현재 파이프라인은 프롬프트로 강제 유도만 하고, 준수 여부를 정량적으로 측정하지 않는다.

**설계**

```python
def prefix_compliance_score(gen_query: dict, required_prefix: str = "kpi") -> float:
    """
    생성된 쿼리의 dimensions·measures·filters·timeDimensions·order에서
    지정 prefix를 얼마나 지키는지 비율로 반환한다.

    반환값: 0.0 ~ 1.0 (1.0 = 전체 필드가 required_prefix. 로 시작)
    """
    q = gen_query.get("query", {})

    # 수집 대상 필드
    fields = []
    fields.extend(q.get("dimensions", []))
    fields.extend(q.get("measures", []))
    fields.extend(f["member"] for f in q.get("filters", []) if "member" in f)
    fields.extend(
        td["dimension"] for td in q.get("timeDimensions", []) if "dimension" in td
    )
    # order는 key가 필드명
    fields.extend(q.get("order", {}).keys())

    if not fields:
        return 0.0

    correct = sum(1 for f in fields if f.startswith(f"{required_prefix}."))
    return correct / len(fields)
```

**결과 컬럼 추가 위치** (`main()` 내 results.append 블록):

```python
# KDL 전용: prefix 준수율
kdl_prefix_score = -1.0   # -1: 비KDL 질문 (N/A)
if q["category"] == "KDL" and parse_ok:
    kdl_prefix_score = prefix_compliance_score(gen_query, required_prefix="kpi")

results.append({
    ...
    "kdl_prefix_score": round(kdl_prefix_score, 4),
    ...
})
```

**집계 리포트 추가**:

```python
# KDL 카테고리만 필터링
kdl_df = df[df["category"] == "KDL"].copy()
if not kdl_df.empty:
    print("\n=== KDL Prefix 준수율 ===")
    valid = kdl_df[kdl_df["kdl_prefix_score"] >= 0]
    print(f"  평균 준수율: {valid['kdl_prefix_score'].mean():.1%}")
    print(f"  완전 준수(1.0): {(valid['kdl_prefix_score'] == 1.0).sum()} / {len(valid)}")
    # prefix 위반이 있는 케이스 출력
    violations = kdl_df[kdl_df["kdl_prefix_score"] < 1.0][
        ["question", "kdl_prefix_score", "gen_query"]
    ]
    if not violations.empty:
        print("\n  위반 케이스:")
        for _, row in violations.iterrows():
            print(f"    [{row['kdl_prefix_score']:.2f}] {row['question'][:60]}")
```

**기대 효과**  
- KDL 프롬프트 품질 측정 가능  
- `kpi.` 대신 `fact_accident.` 등을 혼용하는 패턴 탐지  
- few-shot 예시 개선의 before/after 비교 기준 확보

---

### Feature 2: 반복 실행 신뢰구간 리포트

**배경**  
현재 5회 반복의 평균만 출력하고 분산(표준편차, 95% CI)을 리포트하지 않아서 모델의 일관성을 알 수 없다.

**설계**

```python
def iteration_stats_report(df: pd.DataFrame) -> pd.DataFrame:
    """
    질문별 5회 반복의 주요 지표 평균·표준편차·95% CI를 계산한다.
    Bernoulli 지표(json_parse_ok, exec_ok)는 Wilson score interval 사용.
    연속 지표(dim_f1, msr_f1, result_f1)는 t-분포 기반 CI.
    """
    from scipy import stats

    metric_cols = ["json_parse_ok", "exec_ok", "dim_f1", "msr_f1", "result_f1"]
    rows = []
    for (cat, question), grp in df.groupby(["category", "question"]):
        row = {"category": cat, "question": question[:60]}
        for col in metric_cols:
            vals = grp[col].dropna()
            n = len(vals)
            mean = vals.mean()
            sem  = vals.sem() if n > 1 else 0.0
            ci_lo, ci_hi = stats.t.interval(0.95, df=max(n-1,1), loc=mean, scale=sem if sem > 0 else 1e-9)
            row[f"{col}_mean"] = round(mean, 3)
            row[f"{col}_std"]  = round(vals.std(), 3)
            row[f"{col}_ci95"] = f"[{max(ci_lo,0):.3f}, {min(ci_hi,1):.3f}]"
        rows.append(row)

    return pd.DataFrame(rows)
```

**저장**:

```python
stats_df = iteration_stats_report(df)
stats_csv = RESULTS_CSV.replace(".csv", "_stats.csv")
stats_df.to_csv(stats_csv, index=False, encoding="utf-8-sig")
print(f"신뢰구간 리포트 저장: {stats_csv}")
```

---

### Feature 3: 카테고리×지표 히트맵 시각화

**배경**  
터미널 텍스트 출력으로는 카테고리별 강약점을 한눈에 파악하기 어렵다.

**설계**

```python
def save_heatmap(df: pd.DataFrame, out_path: str):
    """
    카테고리(행) × 지표(열) 히트맵을 PNG로 저장.
    seaborn 없을 경우 matplotlib fallback.
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    metric_labels = {
        "json_parse_ok": "Parse Rate",
        "exec_ok":       "Exec Rate",
        "dim_f1":        "Dim F1",
        "msr_f1":        "Msr F1",
        "result_f1":     "Result F1",
    }
    cats = ["LQLS", "LQHS", "HQLS", "HQHS", "KDL"]
    pivot = (
        df.groupby("category")[list(metric_labels.keys())]
        .mean()
        .reindex(cats)
        .rename(columns=metric_labels)
    )

    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=11)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=11)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not pd.isna(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=10, color="black" if 0.3 < val < 0.7 else "white")
    plt.colorbar(im, ax=ax, label="Score (0–1)")
    ax.set_title(f"Cube Benchmark — 카테고리별 지표 ({LLM_MODEL})", fontsize=13)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"히트맵 저장: {out_path}")
```

**호출**:

```python
heatmap_path = RESULTS_CSV.replace(".csv", "_heatmap.png")
save_heatmap(df, heatmap_path)
```

---

### Feature 4: Markdown 자동 리포트 생성

**배경**  
CSV + 터미널 출력 외에 공유 가능한 Markdown 리포트가 없다.

**설계**

```python
REPORT_MD = os.path.expanduser("~/heartcube/cube_benchmark_report.md")

def generate_markdown_report(df: pd.DataFrame, model: str, n_iter: int) -> str:
    from datetime import datetime
    lines = [
        f"# Cube LLM Benchmark 리포트",
        f"",
        f"- **모델**: {model}",
        f"- **반복**: {n_iter}회",
        f"- **생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **총 질문 수**: {df['question'].nunique()}개",
        f"",
        f"---",
        f"",
        f"## 전체 Funnel",
        f"",
    ]

    total_n = len(df)
    parse_n = df["json_parse_ok"].sum()
    exec_n  = df["exec_ok"].sum()
    res_n   = (df["result_f1"] >= 1.0).sum()
    lines += [
        f"| 단계 | 건수 | 비율 |",
        f"|---|---|---|",
        f"| JSON 파싱 성공 | {int(parse_n)} / {total_n} | {parse_n/total_n:.1%} |",
        f"| 쿼리 실행 성공 | {int(exec_n)} / {total_n} | {exec_n/total_n:.1%} |",
        f"| 결과 완전 일치 | {int(res_n)} / {total_n} | {res_n/total_n:.1%} |",
        f"",
        f"---",
        f"",
        f"## 카테고리별 지표",
        f"",
        f"| 카테고리 | N | Parse% | Exec% | Dim F1 | Msr F1 | Result F1 |",
        f"|---|---|---|---|---|---|---|",
    ]
    for cat in ["LQLS", "LQHS", "HQLS", "HQHS", "KDL"]:
        sub = df[df["category"] == cat]
        if sub.empty:
            continue
        lines.append(
            f"| {cat} | {len(sub)} "
            f"| {sub['json_parse_ok'].mean():.1%} "
            f"| {sub['exec_ok'].mean():.1%} "
            f"| {sub['dim_f1'].mean():.3f} "
            f"| {sub['msr_f1'].mean():.3f} "
            f"| {sub['result_f1'].mean():.3f} |"
        )

    # KDL prefix 준수율
    if "kdl_prefix_score" in df.columns:
        kdl_valid = df[(df["category"] == "KDL") & (df["kdl_prefix_score"] >= 0)]
        if not kdl_valid.empty:
            lines += [
                f"",
                f"---",
                f"",
                f"## KDL Prefix 준수율",
                f"",
                f"- 평균: **{kdl_valid['kdl_prefix_score'].mean():.1%}**",
                f"- 완전 준수(1.0): {(kdl_valid['kdl_prefix_score'] == 1.0).sum()} / {len(kdl_valid)}",
            ]

    # LLM Judge 결과
    judged = df[df["llm_judge"] != -1]
    if not judged.empty:
        pass_n = (judged["llm_judge"] == 1).sum()
        lines += [
            f"",
            f"---",
            f"",
            f"## LLM-as-Judge (엣지케이스 판정)",
            f"",
            f"- 판정 건수: {len(judged)}",
            f"- PASS: {pass_n} / {len(judged)} ({pass_n/len(judged):.1%})",
        ]

    return "\n".join(lines)
```

---

## 3. 구현 순서 및 우선순위

| 순서 | 기능 | 예상 코드량 | 선행 조건 |
|---|---|---|---|
| 1 | KDL Prefix 준수율 | ~30줄 | 없음 |
| 2 | Markdown 리포트 자동 생성 | ~50줄 | 없음 |
| 3 | 반복 신뢰구간 리포트 | ~40줄 | scipy 설치 |
| 4 | 히트맵 시각화 | ~40줄 | matplotlib 설치 |

---

## 4. 파일 변경 계획

```
~/heartcube/
├── benchmark_pipeline.py        ← 위 4개 Feature 코드 추가
├── cube_benchmark_results.csv   ← kdl_prefix_score 컬럼 추가됨
├── cube_benchmark_results_stats.csv   ← 신뢰구간 리포트 (신규)
├── cube_benchmark_results_heatmap.png ← 히트맵 PNG (신규)
└── cube_benchmark_report.md     ← Markdown 리포트 (신규)
```

---

## 5. 의존성 추가

```bash
pip install scipy matplotlib
```

또는 `requirements.txt`에 추가:

```
scipy>=1.11
matplotlib>=3.8
```

---

## 6. 검증 방법

```bash
# dev_mcp 서버에서 단위 테스트
cd ~/heartcube

python3 - <<'EOF'
from benchmark_pipeline import (
    prefix_compliance_score,
    component_f1,
    soft_result_f1,
)

# Test 1: KDL prefix 준수율
q_ok = {"query": {"dimensions": ["kpi.coverage_nm"], "measures": ["kpi.loss_ratio"]}}
q_bad = {"query": {"dimensions": ["kpi.coverage_nm"], "measures": ["fact_accident.loss_ratio"]}}
assert prefix_compliance_score(q_ok, "kpi") == 1.0
assert prefix_compliance_score(q_bad, "kpi") == 0.5
print("✓ prefix_compliance_score")

# Test 2: Component F1
p, r, f1 = component_f1({"a","b","c"}, {"a","b","d"})
assert abs(f1 - 0.6667) < 0.001
print("✓ component_f1")

# Test 3: Soft Result F1 (float 타입 차이 흡수)
gold = [{"val": 5.2, "name": "A"}]
gen  = [{"val": 5.20, "name": "A"}]
assert soft_result_f1(gold, gen) == 1.0
print("✓ soft_result_f1 float normalization")

print("\n모든 테스트 통과")
EOF
```

---

## 7. 참고

- 기존 계획: `~/heartcube/cube_benchmark_plan.md`
- 파이프라인: `~/heartcube/benchmark_pipeline.py`
- 평가 질문: `~/heartcube/questions.md`
- BIRD 2024 Mini-Dev: https://github.com/bird-bench/mini-dev
- FLEX (NAACL 2025): LLM-as-Judge 방법론 참고
- Spider 2.0: Component F1 표준 정의 참고
