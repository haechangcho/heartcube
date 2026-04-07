#!/usr/bin/env python3
"""
Cube LLM Benchmarking Pipeline
dev_mcp:~/heartcube/questions.md 기반 자연어 → Cube JSON 쿼리 정확도 평가
"""

import json
import re
import time
import os
import requests
import pandas as pd
from openai import OpenAI

# ── 설정 ──────────────────────────────────────────────────────────────────────
CUBE_BASE_URL   = "http://172.20.0.2:4000/cubejs-api/v1"
CUBE_TOKEN      = "heartcube-secret-change-in-production"
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL       = "gpt-4o"
N_ITERATIONS    = 5
QUESTIONS_FILE  = os.path.expanduser("~/heartcube/questions.md")
RESULTS_CSV     = os.path.expanduser("~/heartcube/cube_benchmark_results.csv")

# LLM-as-Judge: result_match가 이 임계값 미만일 때만 판정 요청
LLM_JUDGE_THRESHOLD = 0.9

client = OpenAI(api_key=OPENAI_API_KEY)

# ── Cube API ──────────────────────────────────────────────────────────────────
HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}

def fetch_meta():
    resp = requests.get(f"{CUBE_BASE_URL}/meta", headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["cubes"]

def build_schema_context(cubes, only=None, exclude=None):
    """only: 지정한 큐브만 포함 / exclude: 지정한 큐브만 제외"""
    lines = []
    for cube in cubes:
        if only and cube["name"] not in only:
            continue
        if exclude and cube["name"] in exclude:
            continue
        lines.append(f"\n## {cube['name']}")
        dims = [d["name"] for d in cube.get("dimensions", [])]
        msrs = [m["name"] for m in cube.get("measures", [])]
        if dims:
            lines.append("dimensions: " + ", ".join(dims))
        if msrs:
            lines.append("measures:   " + ", ".join(msrs))
    return "\n".join(lines)

def execute_cube_query(query_json, timeout=20):
    try:
        resp = requests.post(
            f"{CUBE_BASE_URL}/load",
            headers=HEADERS,
            json=query_json,
            timeout=timeout,
        )
        if resp.status_code == 200:
            return True, resp.json().get("data", [])
        return False, []
    except Exception:
        return False, []

# ── 질문 파서 ─────────────────────────────────────────────────────────────────
def parse_questions(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    # 취소선(~~) 블록 제거
    text = re.sub(r"~~.*?~~", "", text, flags=re.DOTALL)

    questions = []

    # ── 1. LQLS / LQHS / HQLS / HQHS 섹션 ──
    # 헤더: ## LQLS — ...  질문: "1. 텍스트\n`힌트`\n```json...```"
    cat_section = re.compile(
        r"^## (LQLS|LQHS|HQLS|HQHS)[^\n]*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    # 번호 질문 + 선택적 힌트 라인 + json 블록
    numbered_q = re.compile(
        r"^\d+\.\s+(.+?)(?:\n`[^`\n]+`)?\s*```json\s*(\{.*?\})\s*```",
        re.MULTILINE | re.DOTALL,
    )
    for m in cat_section.finditer(text):
        cat, body = m.group(1), m.group(2)
        for qm in numbered_q.finditer(body):
            q_text = qm.group(1).strip()
            q_text = re.sub(r"\n`[^`\n]+`\s*$", "", q_text, flags=re.MULTILINE).strip()
            try:
                gold = json.loads(qm.group(2))
            except json.JSONDecodeError:
                continue
            questions.append({"category": cat, "question": q_text, "gold_query": gold})

    # ── 2. KDL 섹션 ──
    # 헤더: **P1.** / **Q1.** / **E1.** 등
    kdl_section_m = re.search(
        r"^## KDL.*?\n(.*)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if kdl_section_m:
        kdl_body = kdl_section_m.group(1)
        kdl_q = re.compile(
            r"^\*\*[PQE]\d+\.\*\*\s+(.+?)\s*```json\s*(\{.*?\})\s*```",
            re.MULTILINE | re.DOTALL,
        )
        for qm in kdl_q.finditer(kdl_body):
            # KPI/Driver/Lever 라인 제거 후 첫 줄만
            raw = qm.group(1).strip()
            q_text = raw.split("\n")[0].strip()
            try:
                gold = json.loads(qm.group(2))
            except json.JSONDecodeError:
                continue
            questions.append({"category": "KDL", "question": q_text, "gold_query": gold})

    return questions

# ── 채점 ──────────────────────────────────────────────────────────────────────

# 1. Component-level F1 (Spider 표준)
#    Jaccard 대신 precision/recall 분리 → "과다 생성" vs "누락" 패턴 구분 가능
def component_f1(gold_set, gen_set):
    """gold_set, gen_set: set of strings (dimensions / measures / filter members)"""
    if not gold_set and not gen_set:
        return 1.0, 1.0, 1.0
    if not gold_set or not gen_set:
        return 0.0, 0.0, 0.0
    tp        = len(gold_set & gen_set)
    precision = tp / len(gen_set)
    recall    = tp / len(gold_set)
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1

def structural_accuracy(gold, gen):
    gq, gg = gold.get("query", {}), gen.get("query", {})
    _, _, dim_f1 = component_f1(set(gq.get("dimensions", [])), set(gg.get("dimensions", [])))
    _, _, msr_f1 = component_f1(set(gq.get("measures",   [])), set(gg.get("measures",   [])))
    gf = {f["member"] for f in gq.get("filters", [])}
    af = {f["member"] for f in gg.get("filters", [])}
    _, _, flt_f1 = component_f1(gf, af)
    return dim_f1, msr_f1, flt_f1

# 2. Soft F1 결과 비교 (BIRD Mini-Dev 2024)
#    float 타입 차이(5.2 vs 5.20) 흡수, 행이 부분적으로 겹쳐도 점수 부여
def _normalize_row(row):
    normalized = {}
    for k, v in row.items():
        try:
            normalized[k] = str(round(float(v), 4))
        except (TypeError, ValueError):
            normalized[k] = str(v)
    return frozenset(normalized.items())

def soft_result_f1(gold_rows, gen_rows):
    if not gold_rows and not gen_rows:
        return 1.0
    if not gold_rows or not gen_rows:
        return 0.0
    gold_set = {_normalize_row(r) for r in gold_rows}
    gen_set  = {_normalize_row(r) for r in gen_rows}
    tp        = len(gold_set & gen_set)
    precision = tp / len(gen_set)
    recall    = tp / len(gold_set)
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return f1

# 4. LLM-as-Judge (FLEX, NAACL 2025)
#    exec_ok=True이지만 result_match < LLM_JUDGE_THRESHOLD인 케이스만 호출
#    반환값: 1 (PASS) / 0 (FAIL) / -1 (미호출)
def llm_judge(question, gold_query, gen_query, gold_rows, gen_rows):
    prompt = f"""두 Cube 쿼리가 동일한 비즈니스 질문에 의미적으로 동등하게 답하는지 판단하세요.

질문: {question}

Gold 쿼리:
{json.dumps(gold_query, ensure_ascii=False, indent=2)}

생성된 쿼리:
{json.dumps(gen_query, ensure_ascii=False, indent=2)}

Gold 결과 샘플 (최대 5행):
{json.dumps(gold_rows[:5], ensure_ascii=False)}

생성 결과 샘플 (최대 5행):
{json.dumps(gen_rows[:5], ensure_ascii=False)}

판단 기준:
- 두 쿼리가 같은 비즈니스 의도를 충족하면 PASS
- 집계 방식, 필드 선택, 필터 조건이 다르면 FAIL

PASS 또는 FAIL 중 하나만 출력하세요."""
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        verdict = resp.choices[0].message.content.strip().upper()
        return 1 if "PASS" in verdict else 0
    except Exception as e:
        print(f"  [Judge 오류] {e}")
        return -1

# ── 프롬프트 ─────────────────────────────────────────────────────────────────
FEW_SHOT = """
Cube REST API는 다음 JSON 형식으로 쿼리합니다:
{
  "query": {
    "dimensions": ["cube_name.dimension_name"],
    "measures":   ["cube_name.measure_name"],
    "filters":    [{"member": "cube_name.field", "operator": "equals", "values": ["value"]}],
    "timeDimensions": [{"dimension": "cube_name.dt_field", "dateRange": "last 6 months", "granularity": "month"}],
    "order":  {"cube_name.measure_name": "desc"},
    "limit":  10
  }
}

예시 1) 보상센터별 평균처리기간을 내림차순으로 조회
{"query": {"dimensions": ["fact_review.claim_center_nm"], "measures": ["fact_review.avg_processing_days"], "order": {"fact_review.avg_processing_days": "desc"}}}

예시 2) 최근 3개월 사고유형별 손해율 추이
{"query": {"dimensions": ["fact_accident.accident_type_l1"], "measures": ["fact_accident.loss_ratio"], "timeDimensions": [{"dimension": "fact_accident.accident_dt", "granularity": "month", "dateRange": "last 3 months"}]}}

예시 3) 사기의심 라벨이 있는 사고번호·심사자 목록
{"query": {"dimensions": ["fact_accident.accident_no", "fact_review.adjuster_id"], "filters": [{"member": "fact_review.anomaly_label", "operator": "notEquals", "values": ["정상"]}], "order": {"fact_accident.accident_no": "desc"}}}
"""

FEW_SHOT_KDL = """
Cube REST API는 다음 JSON 형식으로 쿼리합니다:
{
  "query": {
    "dimensions": ["kpi.dimension_name"],
    "measures":   ["kpi.measure_name"],
    "filters":    [{"member": "kpi.field", "operator": "equals", "values": ["value"]}],
    "timeDimensions": [{"dimension": "kpi.dt_field", "dateRange": "last 3 months", "granularity": "month"}],
    "order":  {"kpi.measure_name": "desc"},
    "limit":  10
  }
}

반드시 모든 dimensions·measures·filters·timeDimensions·order에 "kpi." prefix만 사용하세요.
다른 큐브(fact_accident, fact_review 등)의 prefix는 절대 사용하지 마세요.

예시 1) 손해율이 높은 담보를 내림차순으로 조회
{"query": {"dimensions": ["kpi.coverage_nm"], "measures": ["kpi.loss_ratio", "kpi.claim_count"], "order": {"kpi.loss_ratio": "desc"}}}

예시 2) 모집채널별·상품별 손해율을 최근 3개월 월별로 조회
{"query": {"dimensions": ["kpi.sales_division", "kpi.product_nm"], "measures": ["kpi.loss_ratio", "kpi.claim_count"], "timeDimensions": [{"dimension": "kpi.accident_dt", "granularity": "month", "dateRange": "last 3 months"}], "order": {"kpi.loss_ratio": "desc"}}}

예시 3) 과지급율이 높은 심사자 TOP10
{"query": {"dimensions": ["kpi.adjuster_id", "kpi.claim_center_nm"], "measures": ["kpi.overpayment_rate", "kpi.claim_count"], "filters": [{"member": "kpi.claim_count", "operator": "gte", "values": ["5"]}], "order": {"kpi.overpayment_rate": "desc"}, "limit": 10}}
"""

def build_prompt(schema_context, question, category=None):
    if category == "KDL":
        return f"""당신은 Cube Semantic Layer 전문가입니다.
아래 스키마와 예시를 참고해 자연어 질문을 Cube REST API JSON 쿼리로 변환하세요.
JSON 객체만 출력하세요. 설명·마크다운 코드블록 없이 순수 JSON만 반환하세요.

{FEW_SHOT_KDL}

## 사용 가능한 스키마 (kpi 뷰만 사용하세요)
{schema_context}

## 질문
{question}
"""
    return f"""당신은 Cube Semantic Layer 전문가입니다.
아래 스키마와 예시를 참고해 자연어 질문을 Cube REST API JSON 쿼리로 변환하세요.
JSON 객체만 출력하세요. 설명·마크다운 코드블록 없이 순수 JSON만 반환하세요.

{FEW_SHOT}

## 사용 가능한 스키마
{schema_context}

## 질문
{question}
"""

def generate_cube_query(prompt):
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        return True, json.loads(raw)
    except json.JSONDecodeError:
        return False, {}
    except Exception as e:
        print(f"  [LLM 오류] {e}")
        return False, {}

# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("=== Cube LLM Benchmark ===")
    print("메타데이터 수집 중...")
    cubes = fetch_meta()
    schema_context        = build_schema_context(cubes)
    schema_context_kdl    = build_schema_context(cubes, only=["kpi"])
    schema_context_no_kpi = build_schema_context(cubes, exclude=["kpi"])
    print(f"  큐브 {len(cubes)}개 로드 완료")

    print("질문 파싱 중...")
    questions = parse_questions(QUESTIONS_FILE)
    print(f"  질문 {len(questions)}개 파싱 완료")
    for cat in ["LQLS", "LQHS", "HQLS", "HQHS", "KDL"]:
        n = sum(1 for q in questions if q["category"] == cat)
        print(f"    {cat}: {n}개")

    print(f"\n평가 시작 (모델={LLM_MODEL}, 반복={N_ITERATIONS}회, 총 {len(questions)*N_ITERATIONS}건)\n")

    results = []
    total = len(questions) * N_ITERATIONS
    done  = 0

    for iteration in range(N_ITERATIONS):
        print(f"── Iteration {iteration+1}/{N_ITERATIONS} ──")
        for q in questions:
            done += 1
            ctx    = schema_context_kdl if q["category"] == "KDL" else schema_context_no_kpi
            prompt = build_prompt(ctx, q["question"], category=q["category"])

            parse_ok, gen_query = generate_cube_query(prompt)
            gold_ok, gold_rows  = execute_cube_query(q["gold_query"])
            exec_ok, gen_rows   = (False, [])
            if parse_ok:
                exec_ok, gen_rows = execute_cube_query(gen_query)

            # 1. Component F1 (dimensions / measures / filters)
            dim_f1 = msr_f1 = flt_f1 = 0.0
            if parse_ok:
                dim_f1, msr_f1, flt_f1 = structural_accuracy(q["gold_query"], gen_query)

            # 2. Soft Result F1
            res_f1 = 0.0
            if exec_ok and gold_ok:
                res_f1 = soft_result_f1(gold_rows, gen_rows)

            # 4. LLM-as-Judge: 실행은 됐지만 결과가 완전히 일치하지 않는 엣지케이스만
            judge = -1
            if exec_ok and gold_ok and 0 < res_f1 < LLM_JUDGE_THRESHOLD:
                judge = llm_judge(
                    q["question"], q["gold_query"], gen_query, gold_rows, gen_rows
                )

            results.append({
                "iteration":       iteration + 1,
                "category":        q["category"],
                "question":        q["question"],
                # 3. 단계별 Valid Query Rate (parse → exec → result)
                "json_parse_ok":   int(parse_ok),
                "exec_ok":         int(exec_ok),
                "gold_exec_ok":    int(gold_ok),
                # 1. Component F1
                "dim_f1":          round(dim_f1, 4),
                "msr_f1":          round(msr_f1, 4),
                "filter_f1":       round(flt_f1, 4),
                # 2. Soft Result F1
                "result_f1":       round(res_f1, 4),
                # 4. LLM Judge (-1=미호출, 0=FAIL, 1=PASS)
                "llm_judge":       judge,
                "gen_query":       json.dumps(gen_query, ensure_ascii=False),
                "gold_query":      json.dumps(q["gold_query"], ensure_ascii=False),
            })

            status = "✓" if exec_ok else ("P" if parse_ok else "✗")
            judge_str = f" J={'✓' if judge==1 else ('✗' if judge==0 else '-')}" if judge != -1 else ""
            print(f"  [{done:3d}/{total}] [{q['category']}] {status}{judge_str} "
                  f"dim={dim_f1:.2f} msr={msr_f1:.2f} res={res_f1:.2f} | {q['question'][:50]}")

            time.sleep(0.5)

    df = pd.DataFrame(results)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: {RESULTS_CSV}")

    # 3. 단계별 drop-off 포함 카테고리별 집계
    print("\n=== 카테고리별 집계 ===")
    summary = df.groupby("category").agg(
        n=("question", "count"),
        parse_rate=("json_parse_ok", "mean"),   # 파싱 성공률
        exec_rate=("exec_ok", "mean"),           # 실행 성공률
        dim_f1=("dim_f1", "mean"),
        msr_f1=("msr_f1", "mean"),
        result_f1=("result_f1", "mean"),
    ).round(3)
    print(summary.to_string())

    # 3. 전체 단계별 funnel
    print("\n=== 단계별 Funnel (전체) ===")
    total_n = len(df)
    print(f"  파싱 성공:  {df['json_parse_ok'].sum():4d} / {total_n}  ({df['json_parse_ok'].mean():.1%})")
    print(f"  실행 성공:  {df['exec_ok'].sum():4d} / {total_n}  ({df['exec_ok'].mean():.1%})")
    result_ok = (df["result_f1"] >= 1.0).sum()
    print(f"  결과 일치:  {result_ok:4d} / {total_n}  ({result_ok/total_n:.1%})")

    # 4. LLM Judge 집계 (호출된 케이스만)
    judged = df[df["llm_judge"] != -1]
    if not judged.empty:
        print(f"\n=== LLM Judge 결과 ({len(judged)}건 판정) ===")
        print(f"  PASS: {(judged['llm_judge']==1).sum()}  FAIL: {(judged['llm_judge']==0).sum()}")

    print("\n=== 전체 평균 ===")
    overall = df[["json_parse_ok", "exec_ok", "dim_f1", "msr_f1", "result_f1"]].mean().round(3)
    print(overall.to_string())

if __name__ == "__main__":
    main()
