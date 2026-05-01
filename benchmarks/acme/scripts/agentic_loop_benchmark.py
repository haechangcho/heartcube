#!/usr/bin/env python3
"""ACME Cube benchmark with agentic retry loop.

Extends cube_benchmark.py by adding an error-feedback loop:
if a generated query fails to execute, the agent receives the error
message and the available field list, then retries up to MAX_RETRIES times.

Focused on LQLS and LQHS categories where single-shot accuracy was weakest.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acme_benchmark.common import QUESTIONS_DIR, RESULTS_DIR, env_int, env_required, iterations, llm_model, parse_cube_questions
from acme_benchmark.evaluator import cube_structural_accuracy, robust_result_scores

load_dotenv(os.path.expanduser("~/heartcube/.env"))
load_dotenv()

CUBE_BASE_URL = env_required("CUBE_BASE_URL").rstrip("/")
CUBE_TOKEN = env_required("CUBE_TOKEN")
OPENAI_API_KEY = env_required("OPENAI_API_KEY")
LLM_MODEL = llm_model()
N_ITERATIONS = iterations()
MAX_RETRIES = env_int("ACME_MAX_RETRIES", 3)

# Only test the categories that had lowest single-shot accuracy
TARGET_CATEGORIES = {"LQLS", "LQHS"}

_results_suffix = os.environ.get("ACME_RESULTS_SUFFIX", "").strip()
RESULTS_CSV = RESULTS_DIR / (
    f"acme_agentic_results_{_results_suffix}.csv" if _results_suffix else "acme_agentic_results.csv"
)

QUESTIONS_FILE = QUESTIONS_DIR / "cube_questions.md"
HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}
client = OpenAI(api_key=OPENAI_API_KEY)


# ── Cube helpers ──────────────────────────────────────────────────────────────

def fetch_meta() -> list[dict[str, Any]]:
    r = requests.get(f"{CUBE_BASE_URL}/meta", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()["cubes"]


def build_schema_context(cubes: list[dict[str, Any]]) -> str:
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


def execute_cube(query: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], str]:
    """Returns (success, rows, error_message)."""
    try:
        r = requests.post(f"{CUBE_BASE_URL}/load", headers=HEADERS, json=query, timeout=20)
        if r.status_code == 200:
            return True, r.json().get("data", []), ""
        # Extract error detail from response body
        try:
            err = r.json().get("error", r.text[:200])
        except Exception:
            err = r.text[:200]
        return False, [], str(err)
    except Exception as e:
        return False, [], str(e)[:200]


# ── Prompt helpers ────────────────────────────────────────────────────────────

FEW_SHOT = """
Cube REST API accepts queries in this JSON format:
{
  "query": {
    "dimensions": ["cube_name.dimension_name"],
    "measures":   ["cube_name.measure_name"],
    "filters":    [{"member": "cube_name.field", "operator": "equals", "values": ["value"]}],
    "order":      {"cube_name.measure_name": "desc"},
    "limit":      10
  }
}

Example 1) Show number of claims by policy number in descending order
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.claim_count"], "order": {"acme_ops.claim_count": "desc"}}}

Example 2) Show total premium paid by policyholder in descending order
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.total_policy_amount": "desc"}}}

Example 3) Show total loss amount (loss payment + loss reserve) by claim number in descending order
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.total_loss_amount"], "order": {"acme_ops.total_loss_amount": "desc"}}}
"""

SYSTEM_PROMPT = """You are a Cube Semantic Layer expert.
Convert the natural language question below into a Cube REST API JSON query using the schema provided.
Output only the raw JSON object. Do not include explanation or markdown.
Use the acme_ops prefix only."""


def _initial_user_message(schema_ctx: str, question: str) -> str:
    return f"""{FEW_SHOT}

## Available schema
{schema_ctx}

## Question
{question}
"""


def _retry_user_message(schema_ctx: str, question: str, prev_query: dict, error: str) -> str:
    return f"""Your previous query failed with this error:

Error: {error}

Previous query:
{json.dumps(prev_query, ensure_ascii=False, indent=2)}

Please fix the query. Common issues:
- Fields must exist in the schema (check names carefully)
- dimensions go in "dimensions", measures go in "measures" — do not mix them
- Do not add measures when the question only asks for a list of values

## Available schema
{schema_ctx}

## Question
{question}

Output only the corrected raw JSON object.
"""


def generate_query_from_messages(messages: list[dict]) -> tuple[bool, dict[str, Any]]:
    try:
        rsp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_completion_tokens=1024,
        )
        raw = rsp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        return True, json.loads(raw)
    except json.JSONDecodeError:
        return False, {}
    except Exception as exc:
        print(f"  [LLM error] {exc}")
        return False, {}


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_agentic_loop(
    schema_ctx: str,
    question: str,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]], int, list[str]]:
    """
    Returns:
        exec_ok, final_query, final_rows, attempts_used, error_log
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _initial_user_message(schema_ctx, question)},
    ]

    error_log: list[str] = []
    last_query: dict = {}

    for attempt in range(1, MAX_RETRIES + 2):  # +1 for initial attempt
        parse_ok, gen_query = generate_query_from_messages(messages)
        if not parse_ok:
            error_log.append(f"attempt {attempt}: JSON parse failed")
            break

        last_query = gen_query
        exec_ok, rows, error = execute_cube(gen_query)

        if exec_ok:
            return True, gen_query, rows, attempt, error_log

        error_log.append(f"attempt {attempt}: {error}")

        if attempt >= MAX_RETRIES + 1:
            break

        # Feed error back into conversation for retry
        messages.append({"role": "assistant", "content": json.dumps(gen_query, ensure_ascii=False)})
        messages.append({
            "role": "user",
            "content": _retry_user_message(schema_ctx, question, gen_query, error),
        })

    return False, last_query, [], attempt, error_log


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== ACME Agentic Loop Benchmark ===")
    print(f"Target categories: {sorted(TARGET_CATEGORIES)}")
    print(f"Max retries per question: {MAX_RETRIES}")
    print(f"Model: {LLM_MODEL}, Iterations: {N_ITERATIONS}\n")

    cubes = fetch_meta()
    schema_ctx = build_schema_context(cubes)

    all_questions = parse_cube_questions(QUESTIONS_FILE)
    questions = [q for q in all_questions if q["category"] in TARGET_CATEGORIES]
    print(f"Questions loaded: {len(questions)}")
    for cat in sorted(TARGET_CATEGORIES):
        n = sum(1 for q in questions if q["category"] == cat)
        print(f"  {cat}: {n}")

    total = len(questions) * N_ITERATIONS
    print(f"\nTotal runs: {total}\n")

    records: list[dict[str, Any]] = []
    done = 0

    for iteration in range(1, N_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{N_ITERATIONS} --")
        for q in questions:
            done += 1
            qtext = q["question"]

            gold_ok, gold_rows, _ = execute_cube(q["gold_query"])
            exec_ok, gen_query, gen_rows, attempts, error_log = run_agentic_loop(schema_ctx, qtext)

            dim_f1 = measure_f1 = filter_f1 = 0.0
            if gen_query:
                dim_f1, measure_f1, filter_f1 = cube_structural_accuracy(q["gold_query"], gen_query)

            scores = {"result_f1": 0.0, "exact_match": 0.0, "subset_match": 0.0, "column_f1": 0.0, "cell_f1": 0.0}
            if exec_ok and gold_ok:
                scores = robust_result_scores(gold_rows, gen_rows)

            status = f"ok(attempt={attempts})" if exec_ok else f"fail(attempt={attempts})"
            print(
                f"  [{done:3d}/{total}] [{q['category']}] {status} "
                f"dim={dim_f1:.2f} msr={measure_f1:.2f} res={scores['result_f1']:.2f} "
                f"subset={scores['subset_match']:.0f} col={scores['column_f1']:.2f} | "
                f"{qtext[:55]}"
            )

            records.append({
                "iteration": iteration,
                "id": q.get("id", ""),
                "category": q["category"],
                "answer_shape": q.get("answer_shape", ""),
                "question": qtext,
                "attempts": attempts,
                "exec_ok": int(exec_ok),
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
                "gen_query": json.dumps(gen_query, ensure_ascii=False),
                "gold_query": json.dumps(q["gold_query"], ensure_ascii=False),
            })
            time.sleep(0.3)

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
        result_f1=("result_f1", "mean"),
        exact_match=("exact_match", "mean"),
        subset_match=("subset_match", "mean"),
        column_f1=("column_f1", "mean"),
        cell_f1=("cell_f1", "mean"),
    ).round(3)
    print(summary.to_string())

    print("\n=== vs. single-shot baseline ===")
    baseline = {"LQLS": 0.683, "LQHS": 0.580}
    for cat, base in baseline.items():
        cat_df = df[df["category"] == cat]
        if cat_df.empty:
            continue
        new = cat_df["exact_match"].mean()
        print(f"  {cat}: {base:.1%} → {new:.1%}  (Δ {new - base:+.1%})")

    print("\n=== Retry distribution ===")
    print(df["attempts"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
