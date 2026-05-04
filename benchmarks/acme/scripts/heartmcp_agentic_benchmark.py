#!/usr/bin/env python3
"""ACME benchmark using HeartMCP CubeAdapter directly.

헤아엠씨피(HeartMCP)의 cube_query 툴을 직접 호출해 agentic loop를 구성.
- CubeAdapter.cube_query()의 자동교정 로직(measure↔dimension 오배치 자동수정)을 그대로 활용
- LLM이 cube_query를 tool call로 호출 → 실패 시 에러+힌트 피드백 → 재시도
- LQLS / LQHS 카테고리만 타겟

실행:
    cd ~/heartcube/benchmarks/acme
    CUBE_SCHEMA_MODE=acme python3 scripts/heartmcp_agentic_benchmark.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ── HeartMCP import ──────────────────────────────────────────────────────────
# heartmcp는 ~/heartmcp에 있음. config를 import하기 전에 환경변수 주입.
HEARTMCP_DIR = Path.home() / "heartmcp"
sys.path.insert(0, str(HEARTMCP_DIR))

# heartcube .env에서 Cube 접속 정보 로드
from dotenv import load_dotenv
load_dotenv(Path.home() / "heartcube" / ".env")
load_dotenv()

# CUBE_API_URL은 heartcube .env 기준으로 override
# CUBE_SCHEMA_MODE=acme 로 실행해야 acme_ops 뷰가 노출됨
os.environ.setdefault("CUBE_SCHEMA_MODE", "acme")
# heartcube .env의 CUBE_BASE_URL → heartmcp가 쓰는 CUBE_API_URL로 매핑
_cube_base = os.environ.get("CUBE_BASE_URL", "")
if _cube_base and not os.environ.get("CUBE_API_URL"):
    # CUBE_BASE_URL = http://<cube-host>:4000/cubejs-api/v1 → strip /cubejs-api/v1
    os.environ["CUBE_API_URL"] = _cube_base.replace("/cubejs-api/v1", "")
if not os.environ.get("CUBE_API_TOKEN"):
    os.environ["CUBE_API_TOKEN"] = os.environ.get("CUBE_TOKEN", "")

import config as heartmcp_config  # noqa: E402 — must come after env setup
from adapters.cube_adapter import CubeAdapter  # noqa: E402

# ── benchmark 공통 모듈 ───────────────────────────────────────────────────────
ACME_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACME_DIR / "src"))

from acme_benchmark.common import QUESTIONS_DIR, RESULTS_DIR, env_int, iterations, llm_model, parse_cube_questions
from acme_benchmark.evaluator import cube_structural_accuracy, robust_result_scores

import requests
from openai import OpenAI

# ── 설정 ──────────────────────────────────────────────────────────────────────
LLM_MODEL = llm_model()
N_ITERATIONS = iterations()
MAX_RETRIES = env_int("ACME_MAX_RETRIES", 3)
TARGET_CATEGORIES = {"LQLS", "LQHS"}

_suffix = os.environ.get("ACME_RESULTS_SUFFIX", "").strip()
RESULTS_CSV = RESULTS_DIR / (
    f"acme_heartmcp_agentic_results_{_suffix}.csv" if _suffix else "acme_heartmcp_agentic_results.csv"
)
QUESTIONS_FILE = QUESTIONS_DIR / "cube_questions.md"

openai_client = OpenAI()
adapter = CubeAdapter()

CUBE_HEADERS = {
    "Authorization": f"Bearer {os.environ.get('CUBE_TOKEN', '')}",
    "Content-Type": "application/json",
}
CUBE_LOAD_URL = os.environ.get("CUBE_BASE_URL", "").rstrip("/").rstrip("/v1").rstrip("/cubejs-api") + "/cubejs-api/v1/load"


# ── raw Cube REST 실행 (gold + 생성 쿼리 비교용) ─────────────────────────────

def execute_raw(query: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    """HeartMCP를 거치지 않고 raw Cube API로 직접 실행. 컬럼키 = acme_ops.xxx 형식."""
    try:
        r = requests.post(CUBE_LOAD_URL, headers=CUBE_HEADERS, json=query, timeout=20)
        if r.status_code == 200:
            return True, r.json().get("data", [])
        return False, []
    except Exception:
        return False, []


# ── cube_query tool 스펙 (OpenAI function calling) ────────────────────────────

CUBE_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "cube_query",
        "description": (
            "Cube Semantic Layer에 집계 쿼리를 실행합니다. "
            "measures와 dimensions 중 최소 하나는 반드시 포함해야 합니다. "
            "measure 필드는 반드시 measures에, dimension 필드는 반드시 dimensions에 넣으세요. "
            "acme_ops 뷰 prefix만 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "measures": {
                    "type": "array", "items": {"type": "string"},
                    "description": "집계 measure 목록 (예: ['acme_ops.claim_count'])",
                },
                "dimensions": {
                    "type": "array", "items": {"type": "string"},
                    "description": "GROUP BY dimension 목록 (예: ['acme_ops.company_claim_number'])",
                },
                "filters": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "필터 조건 목록",
                },
                "order": {
                    "type": "object",
                    "description": "정렬 조건 (예: {'acme_ops.claim_count': 'desc'})",
                },
                "limit": {"type": "integer", "description": "최대 반환 행 수 (기본 100)"},
            },
        },
    },
}

SYSTEM_PROMPT = """You are a Cube Semantic Layer expert for the ACME insurance dataset.
Convert the user's natural language question into a cube_query tool call using the schema provided.

Rules:
- Use ONLY acme_ops as the view prefix (e.g. acme_ops.claim_count)
- measures: aggregated fields only (counts, sums, averages) — listed under "msr" in schema
- dimensions: grouping/listing/filtering fields — listed under "dim" in schema
- Do NOT add measures when the question only asks for a list of values
- Call cube_query exactly once per question
"""

FEW_SHOT = """
Example queries:
Q: Return all claims by claim number, open date, and status
→ dimensions: [acme_ops.company_claim_number, acme_ops.claim_open_date, acme_ops.claim_status_code]

Q: Total premium amount by policy number
→ measures: [acme_ops.total_policy_amount], dimensions: [acme_ops.policy_number]

Q: All policies and their policyholders (party_role_code=PH)
→ dimensions: [acme_ops.policy_number, acme_ops.party_identifier],
   filters: [party_role_code equals PH]
"""


def build_schema_context_from_meta() -> str:
    """Cube /meta를 fetch해서 acme_ops 스키마 컨텍스트를 문자열로 반환."""
    r = requests.get(
        CUBE_LOAD_URL.replace("/load", "/meta"),
        headers=CUBE_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    cubes = r.json()["cubes"]
    lines: list[str] = []
    for cube in cubes:
        if cube["name"] != "acme_ops":
            continue
        lines.append(f"\n## {cube['name']}")
        for d in cube.get("dimensions", []):
            desc = f" - {d['description']}" if d.get("description") else ""
            lines.append(f"  dim  {d['name']}{desc}")
        for m in cube.get("measures", []):
            desc = f" - {m['description']}" if m.get("description") else ""
            lines.append(f"  msr  {m['name']}{desc}")
    return "\n".join(lines)


# ── agentic loop ──────────────────────────────────────────────────────────────

async def run_heartmcp_agentic_loop(
    question: str,
    schema_ctx: str,
) -> tuple[bool, dict[str, Any], int, list[str]]:
    """
    HeartMCP CubeAdapter를 통해 agentic loop 실행.
    Returns: (exec_ok, final_cube_query_body, attempts, error_log)
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + FEW_SHOT + "\n\n## Available schema\n" + schema_ctx},
        {"role": "user", "content": question},
    ]

    error_log: list[str] = []
    last_query_body: dict = {}

    for attempt in range(1, MAX_RETRIES + 2):
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=[CUBE_QUERY_TOOL],
            tool_choice="required" if attempt == 1 else "auto",
            max_completion_tokens=1024,
        )
        msg = response.choices[0].message

        # tool call 없이 끝난 경우
        if not msg.tool_calls:
            error_log.append(f"attempt {attempt}: LLM produced no tool call")
            break

        tool_call = msg.tool_calls[0]
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            error_log.append(f"attempt {attempt}: JSON parse failed")
            break

        # HeartMCP CubeAdapter 호출 — 자동교정 포함
        result = await adapter.cube_query(
            measures=args.get("measures"),
            dimensions=args.get("dimensions"),
            filters=args.get("filters"),
            order=args.get("order"),
            limit=args.get("limit", 100),
            user_question=question,
        )

        # HeartMCP가 실제로 Cube에 보낸 query body 추출 (auto-corrected 포함)
        if "cube_query" in result:
            last_query_body = {"query": result["cube_query"]}
        elif result.get("auto_corrected") and "corrected_query" in result:
            last_query_body = {"query": result["corrected_query"]}
        else:
            q: dict[str, Any] = {}
            if args.get("measures"):
                q["measures"] = args["measures"]
            if args.get("dimensions"):
                q["dimensions"] = args["dimensions"]
            if args.get("filters"):
                q["filters"] = args["filters"]
            if args.get("order"):
                q["order"] = args["order"]
            q["limit"] = args.get("limit", 100)
            last_query_body = {"query": q}

        if "error" in result and not result.get("data"):
            # 에러 — 피드백 후 재시도
            error_msg = result.get("error", "")
            causes = result.get("possible_causes", [])
            feedback = f"Error: {error_msg}"
            if causes:
                feedback += "\nHints:\n" + "\n".join(f"- {c}" for c in causes)
            error_log.append(f"attempt {attempt}: {error_msg[:120]}")

            if attempt >= MAX_RETRIES + 1:
                break

            messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
            messages.append({
                "role": "user",
                "content": f"The query failed. Please fix and retry.\n\n{feedback}",
            })
            continue

        # 성공 — HeartMCP data는 버리고 raw Cube API로 재실행해 비교 가능한 형태로 가져옴
        return True, last_query_body, attempt, error_log

    return False, last_query_body, attempt, error_log




# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== ACME HeartMCP Agentic Loop Benchmark ===")
    print(f"Model: {LLM_MODEL}  |  Max retries: {MAX_RETRIES}  |  Iterations: {N_ITERATIONS}")
    print(f"CUBE_API_URL: {heartmcp_config.CUBE_API_URL}")
    print(f"CUBE_SCHEMA_MODE: {heartmcp_config.CUBE_SCHEMA_MODE}\n")

    all_questions = parse_cube_questions(QUESTIONS_FILE)
    questions = [q for q in all_questions if q["category"] in TARGET_CATEGORIES]
    print("Fetching schema from Cube /meta...")
    schema_ctx = build_schema_context_from_meta()
    print(f"  Schema loaded ({len(schema_ctx.splitlines())} lines)\n")

    print(f"Questions: {len(questions)}")
    for cat in sorted(TARGET_CATEGORIES):
        print(f"  {cat}: {sum(1 for q in questions if q['category'] == cat)}")
    print(f"Total runs: {len(questions) * N_ITERATIONS}\n")

    records = []
    done = 0
    total = len(questions) * N_ITERATIONS

    for iteration in range(1, N_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{N_ITERATIONS} --")
        for q in questions:
            done += 1
            qtext = q["question"]

            gold_ok, gold_rows = execute_raw(q["gold_query"])

            exec_ok, gen_query_body, attempts, error_log = asyncio.run(
                run_heartmcp_agentic_loop(qtext, schema_ctx)
            )

            # HeartMCP가 확정한 query body를 raw Cube API로 실행 → 동일 key 포맷으로 비교
            gen_ok, gen_rows = (False, [])
            if exec_ok and gen_query_body:
                gen_ok, gen_rows = execute_raw(gen_query_body)
            gold_rows_norm = gold_rows

            dim_f1 = measure_f1 = filter_f1 = 0.0
            if gen_query_body:
                # filters가 string으로 잘못 생성된 경우 방어 처리
                safe_body = dict(gen_query_body)
                inner = dict(safe_body.get("query", {}))
                if "filters" in inner:
                    inner["filters"] = [f for f in inner["filters"] if isinstance(f, dict)]
                safe_body["query"] = inner
                try:
                    dim_f1, measure_f1, filter_f1 = cube_structural_accuracy(q["gold_query"], safe_body)
                except Exception:
                    pass

            scores = {"result_f1": 0.0, "exact_match": 0.0, "subset_match": 0.0, "column_f1": 0.0, "cell_f1": 0.0}
            if gen_ok and gold_ok:
                scores = robust_result_scores(gold_rows_norm, gen_rows)

            status = f"ok(x{attempts})" if exec_ok else f"fail(x{attempts})"
            print(
                f"  [{done:3d}/{total}] [{q['category']}] {status} "
                f"dim={dim_f1:.2f} msr={measure_f1:.2f} res={scores['result_f1']:.2f} "
                f"exact={int(scores['exact_match'])} subset={int(scores['subset_match'])} | "
                f"{qtext[:55]}"
            )

            records.append({
                "iteration": iteration,
                "id": q.get("id", ""),
                "category": q["category"],
                "answer_shape": q.get("answer_shape", ""),
                "question": qtext,
                "attempts": attempts,
                "exec_ok": int(gen_ok),
                "gold_exec_ok": int(gold_ok),
                "dim_f1": round(dim_f1, 4),
                "measure_f1": round(measure_f1, 4),
                "filter_f1": round(filter_f1, 4),
                "result_f1": round(scores["result_f1"], 4),
                "exact_match": int(scores["exact_match"] == 1.0),
                "subset_match": int(scores["subset_match"] == 1.0),
                "column_f1": round(scores["column_f1"], 4),
                "cell_f1": round(scores["cell_f1"], 4),
                "error_log": " | ".join(error_log),
                "gen_query": json.dumps(gen_query_body, ensure_ascii=False),
                "gold_query": json.dumps(q["gold_query"], ensure_ascii=False),
            })
            time.sleep(0.3)

    import pandas as pd
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\nResults saved: {RESULTS_CSV}")

    if df.empty:
        return

    print("\n=== By category ===")
    summary = df.groupby("category").agg(
        n=("question", "count"),
        exec_rate=("exec_ok", "mean"),
        avg_attempts=("attempts", "mean"),
        exact_match=("exact_match", "mean"),
        subset_match=("subset_match", "mean"),
        result_f1=("result_f1", "mean"),
        column_f1=("column_f1", "mean"),
    ).round(3)
    print(summary.to_string())

    print("\n=== vs. single-shot baseline ===")
    for cat, base in {"LQLS": 0.683, "LQHS": 0.580}.items():
        cat_df = df[df["category"] == cat]
        if cat_df.empty:
            continue
        new = cat_df["exact_match"].mean()
        print(f"  {cat}: {base:.1%} → {new:.1%}  (Δ {new - base:+.1%})")

    print("\n=== Retry distribution ===")
    print(df["attempts"].value_counts().sort_index().to_string())

    print("\n=== Auto-correction triggered ===")
    ac = df[df["error_log"].str.contains("auto_correct", case=False, na=False)]
    print(f"  {len(ac)} / {len(df)} runs had auto-correction")


if __name__ == "__main__":
    main()
