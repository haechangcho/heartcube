#!/usr/bin/env python3
"""Experiment 3: Agentic loop + Schema fix (acme_policy_parties).

Schema: NEW (party_identifier/party_role_code removed; policyholder_id/agent_id added)
Gold:   V2  (policyholder_id / agent_id; no party_role_code filters)
Loop:   Agentic retry on execution error (max 3 retries)
Scope:  LQLS + LQHS only

Purpose: Measure improvement from schema redesign over Exp 2.
Key changes in schema:
  - acme_policy_parties cube: pre-joined agreement_party_role self-join
  - acme_ops view: exposes policyholder_id + agent_id, removes party_identifier + party_role_code
  - Gold queries updated to use role-semantic field names directly

Compares directly with Exp 2: same loop, same few-shot, only schema differs.
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

EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_DIR.parents[1] / "src"))

from acme_benchmark.common import env_int, env_required, iterations, llm_model
from acme_benchmark.evaluator import cube_structural_accuracy, robust_result_scores

load_dotenv(os.path.expanduser("~/heartcube/.env"))
load_dotenv()

CUBE_BASE_URL = env_required("CUBE_BASE_URL").rstrip("/")
CUBE_TOKEN = env_required("CUBE_TOKEN")
OPENAI_API_KEY = env_required("OPENAI_API_KEY")
LLM_MODEL = llm_model()
N_ITERATIONS = iterations()
MAX_RETRIES = env_int("ACME_MAX_RETRIES", 3)

# Questions still failing after Exp 2 (agentic loop didn't help — semantic failures)
TARGET_IDS = {
    "LQLS_06",
    "LQHS_02", "LQHS_03", "LQHS_04", "LQHS_05", "LQHS_06",
    "HQHS_04", "HQHS_08",
}
QUESTIONS_FILE = EXPERIMENT_DIR / "questions" / "cube_questions_v2.md"
RESULTS_CSV = EXPERIMENT_DIR / "results" / "exp3_schema_fix.csv"
HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}
client = OpenAI(api_key=OPENAI_API_KEY)

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

Example 1) How many claims have been placed by policy number?
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.claim_count"], "order": {"acme_ops.claim_count": "desc"}}}

Example 2) Return all claims and their associated catastrophe name
- Listing questions use dimensions only — do NOT add measures
- Cube handles JOINs automatically; do NOT add claim_count or existence filters
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.catastrophe_name"]}}

Example 3) Show total premium paid by each policyholder in descending order
{"query": {"dimensions": ["acme_ops.policyholder_id"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.total_policy_amount": "desc"}}}
"""

SYSTEM_PROMPT = """You are a Cube Semantic Layer expert.
Convert the natural language question below into a Cube REST API JSON query using the schema provided.
Output only the raw JSON object. Do not include explanation or markdown.
Use the acme_ops prefix only."""


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
    try:
        r = requests.post(f"{CUBE_BASE_URL}/load", headers=HEADERS, json=query, timeout=20)
        if r.status_code == 200:
            return True, r.json().get("data", []), ""
        try:
            err = r.json().get("error", r.text[:200])
        except Exception:
            err = r.text[:200]
        return False, [], str(err)
    except Exception as e:
        return False, [], str(e)[:200]


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


def run_agentic_loop(schema_ctx: str, question: str) -> tuple[bool, dict, list, int, list[str]]:
    initial_msg = f"""{FEW_SHOT}

## Available schema
{schema_ctx}

## Question
{question}
"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": initial_msg},
    ]
    error_log: list[str] = []
    last_query: dict = {}

    for attempt in range(1, MAX_RETRIES + 2):
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

        retry_msg = f"""Your previous query failed:

Error: {error}

Previous query:
{json.dumps(gen_query, ensure_ascii=False, indent=2)}

Common issues:
- Fields must exist in the schema
- dimensions go in "dimensions", measures go in "measures"
- Do not add measures for listing questions

## Available schema
{schema_ctx}

## Question
{question}

Output only the corrected raw JSON object.
"""
        messages.append({"role": "assistant", "content": json.dumps(gen_query, ensure_ascii=False)})
        messages.append({"role": "user", "content": retry_msg})

    return False, last_query, [], attempt, error_log


def parse_questions(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    questions: list[dict[str, Any]] = []
    cat_section = re.compile(
        r"^## (LQLS|LQHS|HQLS|HQHS)[^\n]*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    numbered_q = re.compile(
        r"^\d+\.\s+(.+?)\s*```json\s*(\{.*?\})\s*```",
        re.MULTILINE | re.DOTALL,
    )
    for section in cat_section.finditer(text):
        category, body = section.group(1), section.group(2)
        for i, match in enumerate(numbered_q.finditer(body), 1):
            question = re.sub(r"\s+", " ", match.group(1)).strip()
            questions.append({
                "id": f"{category}_{i:02d}",
                "category": category,
                "question": question,
                "gold_query": json.loads(match.group(2)),
            })
    return questions


def main() -> None:
    print("=== Experiment 3: Schema Fix (Exp2 Failing Questions) ===")
    print(f"Schema: V2 (policyholder_id / agent_id; party_identifier removed)")
    print(f"Gold:   V2 questions file")
    print(f"Loop:   Agentic retry (max {MAX_RETRIES} retries on exec error)")
    print(f"Targets: {sorted(TARGET_IDS)}")
    print(f"Model:  {LLM_MODEL}, Iterations: {N_ITERATIONS}\n")

    cubes = fetch_meta()
    schema_ctx = build_schema_context(cubes)

    all_dim_names = [d["name"] for c in cubes if c["name"] == "acme_ops" for d in c.get("dimensions", [])]
    has_old = "acme_ops.party_identifier" in all_dim_names
    has_new = "acme_ops.policyholder_id" in all_dim_names
    print(f"Schema check — party_identifier: {has_old}, policyholder_id: {has_new}")
    if not has_new:
        print("WARNING: policyholder_id not found. Exp3 requires NEW schema.")
        print("Apply acme_ops.yml (v2) and restart Cube before running.\n")

    all_questions = parse_questions(QUESTIONS_FILE)
    questions = [q for q in all_questions if q["id"] in TARGET_IDS]
    print(f"Questions: {len(questions)} (Exp2 failures only)")
    for q in questions:
        print(f"  {q['id']} [{q['category']}]: {q['question'][:60]}")
    print()

    total = len(questions) * N_ITERATIONS
    print(f"Total runs: {total}\n")

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

            status = f"ok(att={attempts})" if exec_ok else f"fail(att={attempts})"
            print(
                f"  [{done:3d}/{total}] [{q['id']}] {status} "
                f"exact={scores['exact_match']:.0f} dim={dim_f1:.2f} | "
                f"{qtext[:55]}"
            )

            records.append({
                "experiment": "exp3_schema_fix",
                "iteration": iteration,
                "id": q["id"],
                "category": q["category"],
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

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\nResults saved: {RESULTS_CSV}")

    print("\n=== Summary by category ===")
    summary = df.groupby("category").agg(
        n=("exact_match", "count"),
        exact_match=("exact_match", "mean"),
        exec_rate=("exec_ok", "mean"),
        avg_attempts=("attempts", "mean"),
    ).round(3)
    print(summary.to_string())

    print("\n=== Q15/Q16 schema fix highlight ===")
    for qid_suffix in ["03", "04"]:
        qid = f"LQHS_{qid_suffix}"
        q_df = df[df["id"] == qid]
        if not q_df.empty:
            acc = q_df["exact_match"].mean()
            print(f"  {qid}: {acc:.0%}")


if __name__ == "__main__":
    main()
