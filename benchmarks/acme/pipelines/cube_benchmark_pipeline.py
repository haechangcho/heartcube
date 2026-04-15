#!/usr/bin/env python3
"""ACME Cube Semantic Layer LLM benchmark pipeline."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from openai import OpenAI

from common import QUESTIONS_DIR, RESULTS_DIR, env_float, env_required, iterations, llm_model, parse_cube_questions
from evaluator import cube_structural_accuracy, result_scores


load_dotenv(os.path.expanduser("~/heartcube/.env"))
load_dotenv()

CUBE_BASE_URL = env_required("CUBE_BASE_URL").rstrip("/")
CUBE_TOKEN = env_required("CUBE_TOKEN")
OPENAI_API_KEY = env_required("OPENAI_API_KEY")
LLM_MODEL = llm_model()
N_ITERATIONS = iterations()
LLM_JUDGE_THRESHOLD = env_float("ACME_LLM_JUDGE_THRESHOLD", 0.9)
QUESTIONS_FILE = QUESTIONS_DIR / "cube_questions.md"
RESULTS_CSV = RESULTS_DIR / "acme_cube_results.csv"

client = OpenAI(api_key=OPENAI_API_KEY)
HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}


def fetch_meta() -> list[dict[str, Any]]:
    response = requests.get(f"{CUBE_BASE_URL}/meta", headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()["cubes"]


def build_schema_context(cubes: list[dict[str, Any]], only: set[str] | None = None) -> str:
    lines: list[str] = []
    for cube in cubes:
        if only and cube["name"] not in only:
            continue
        lines.append(f"\n## {cube['name']}")
        for dimension in cube.get("dimensions", []):
            description = f" - {dimension['description']}" if dimension.get("description") else ""
            lines.append(f"  dim  {dimension['name']}{description}")
        for measure in cube.get("measures", []):
            description = f" - {measure['description']}" if measure.get("description") else ""
            lines.append(f"  msr  {measure['name']}{description}")
    return "\n".join(lines)


def execute_cube_query(query_json: dict[str, Any], timeout: int = 20) -> tuple[bool, list[dict[str, Any]]]:
    try:
        response = requests.post(
            f"{CUBE_BASE_URL}/load",
            headers=HEADERS,
            json=query_json,
            timeout=timeout,
        )
        if response.status_code == 200:
            return True, response.json().get("data", [])
        return False, []
    except Exception:
        return False, []


def llm_judge(
    question: str,
    gold_query: dict[str, Any],
    gen_query: dict[str, Any],
    gold_rows: list[dict[str, Any]],
    gen_rows: list[dict[str, Any]],
) -> int:
    prompt = f"""Determine whether the two Cube queries semantically answer the same business question.

Question: {question}

Gold query:
{json.dumps(gold_query, ensure_ascii=False, indent=2)}

Generated query:
{json.dumps(gen_query, ensure_ascii=False, indent=2)}

Gold result sample (up to 5 rows):
{json.dumps(gold_rows[:5], ensure_ascii=False)}

Generated result sample (up to 5 rows):
{json.dumps(gen_rows[:5], ensure_ascii=False)}

Criteria:
- PASS if both queries satisfy the same business intent
- FAIL if aggregation method, field selection, or filter conditions differ materially

Output only PASS or FAIL."""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        verdict = response.choices[0].message.content.strip().upper()
        return 1 if "PASS" in verdict else 0
    except Exception as exc:
        print(f"  [Judge error] {exc}")
        return -1


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


def build_prompt(schema_context: str, question: str) -> str:
    return f"""You are a Cube Semantic Layer expert.
Convert the natural language question below into a Cube REST API JSON query using the schema provided.
Output only the raw JSON object. Do not include explanation or markdown.

{FEW_SHOT}

## Available schema
Use the acme_ops prefix only.

{schema_context}

## Question
{question}
"""


def generate_cube_query(prompt: str) -> tuple[bool, dict[str, Any]]:
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        return True, json.loads(raw)
    except json.JSONDecodeError:
        return False, {}
    except Exception as exc:
        print(f"  [LLM error] {exc}")
        return False, {}


def main() -> None:
    print("=== ACME Insurance Cube LLM Benchmark ===")
    print("Fetching metadata...")
    cubes = fetch_meta()
    schema_context = build_schema_context(cubes, only={"acme_ops"})
    print(f"  Schema loaded ({len(schema_context.splitlines())} lines)")

    print("Parsing questions...")
    questions = parse_cube_questions(QUESTIONS_FILE)
    print(f"  {len(questions)} questions loaded from {QUESTIONS_FILE}")
    for category in ["LQLS", "LQHS", "HQLS", "HQHS"]:
        print(f"    {category}: {sum(1 for question in questions if question['category'] == category)}")

    print(f"\nStarting benchmark (model={LLM_MODEL}, iterations={N_ITERATIONS}, total={len(questions) * N_ITERATIONS})\n")

    results: list[dict[str, Any]] = []
    total = len(questions) * N_ITERATIONS
    done = 0

    for iteration in range(N_ITERATIONS):
        print(f"-- Iteration {iteration + 1}/{N_ITERATIONS} --")
        for question in questions:
            done += 1
            prompt = build_prompt(schema_context, question["question"])

            parse_ok, gen_query = generate_cube_query(prompt)
            gold_ok, gold_rows = execute_cube_query(question["gold_query"])
            exec_ok, gen_rows = (False, [])
            if parse_ok:
                exec_ok, gen_rows = execute_cube_query(gen_query)

            dim_f1 = measure_f1 = filter_f1 = 0.0
            if parse_ok:
                dim_f1, measure_f1, filter_f1 = cube_structural_accuracy(question["gold_query"], gen_query)

            scores = {"result_f1": 0.0, "exact_match": 0.0}
            if exec_ok and gold_ok:
                scores = result_scores(gold_rows, gen_rows)

            judge = -1
            if exec_ok and gold_ok and 0 < scores["result_f1"] < LLM_JUDGE_THRESHOLD:
                judge = llm_judge(question["question"], question["gold_query"], gen_query, gold_rows, gen_rows)

            results.append(
                {
                    "iteration": iteration + 1,
                    "category": question["category"],
                    "question": question["question"],
                    "json_parse_ok": int(parse_ok),
                    "exec_ok": int(exec_ok),
                    "gold_exec_ok": int(gold_ok),
                    "dim_f1": round(dim_f1, 4),
                    "measure_f1": round(measure_f1, 4),
                    "filter_f1": round(filter_f1, 4),
                    "result_f1": round(scores["result_f1"], 4),
                    "exact_match": int(scores["exact_match"] == 1.0),
                    "llm_judge": judge,
                    "gen_query": json.dumps(gen_query, ensure_ascii=False),
                    "gold_query": json.dumps(question["gold_query"], ensure_ascii=False),
                }
            )

            status = "ok" if exec_ok else ("parse-only" if parse_ok else "fail")
            print(
                f"  [{done:3d}/{total}] [{question['category']}] {status} "
                f"dim={dim_f1:.2f} msr={measure_f1:.2f} res={scores['result_f1']:.2f} | "
                f"{question['question'][:55]}"
            )
            time.sleep(0.5)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\nResults saved: {RESULTS_CSV}")

    if df.empty:
        return

    print("\n=== By category ===")
    summary = df.groupby("category").agg(
        n=("question", "count"),
        parse_rate=("json_parse_ok", "mean"),
        exec_rate=("exec_ok", "mean"),
        result_f1=("result_f1", "mean"),
        exact_match=("exact_match", "mean"),
    ).round(3)
    print(summary.to_string())

    print("\n=== Funnel (overall) ===")
    total_n = len(df)
    print(f"  Parse success: {df['json_parse_ok'].sum():4d} / {total_n} ({df['json_parse_ok'].mean():.1%})")
    print(f"  Exec success:  {df['exec_ok'].sum():4d} / {total_n} ({df['exec_ok'].mean():.1%})")
    print(f"  Exact match:   {df['exact_match'].sum():4d} / {total_n} ({df['exact_match'].mean():.1%})")


if __name__ == "__main__":
    main()
