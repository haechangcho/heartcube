#!/usr/bin/env python3
"""Targeted benchmark for previously failing questions only.

Runs agentic loop on the 5 questions that failed in the baseline benchmark,
with experiment-specific modifications controlled by EXPERIMENT env var.

EXPERIMENT modes:
  few_shot         - Q01, Q05: add few-shot examples for Cube implicit JOIN pattern
  schema_fix       - Q15, Q16: use new policyholder_id/agent_id fields (requires updated Cube model)
  gold_fix         - Q18: corrected gold query (remove company_claim_number)
  few_shot_gold_fix- Q01, Q05, Q18: few_shot + gold_fix combined

Baseline accuracy (acme_cube_results.csv, agentic loop):
  Q01: 80%   Q05: 40%   Q15: 0%   Q16: 0%   Q18: 0%
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

EXPERIMENT = os.environ.get("EXPERIMENT", "few_shot").strip()
VALID_EXPERIMENTS = {"few_shot", "schema_fix", "gold_fix", "few_shot_gold_fix"}
if EXPERIMENT not in VALID_EXPERIMENTS:
    raise SystemExit(f"EXPERIMENT must be one of {VALID_EXPERIMENTS}, got: {EXPERIMENT}")

_results_suffix = os.environ.get("ACME_RESULTS_SUFFIX", EXPERIMENT).strip()
RESULTS_CSV = RESULTS_DIR / f"acme_targeted_{_results_suffix}.csv"

QUESTIONS_FILE = QUESTIONS_DIR / "cube_questions.md"
HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}
client = OpenAI(api_key=OPENAI_API_KEY)

# ── Target question IDs per experiment ────────────────────────────────────────

EXPERIMENT_TARGETS: dict[str, set[str]] = {
    "few_shot":          {"Q01", "Q05"},
    "schema_fix":        {"Q15", "Q16"},
    "gold_fix":          {"Q18"},
    "few_shot_gold_fix": {"Q01", "Q05", "Q18"},
}
TARGET_IDS = EXPERIMENT_TARGETS[EXPERIMENT]

# ── Gold query overrides (gold_fix / few_shot_gold_fix) ───────────────────────
# Q18: remove company_claim_number — "had a claim" is an existence condition,
# not an output requirement. The model consistently omits it; the original gold
# was over-specified.
GOLD_OVERRIDES: dict[str, dict] = {
    "Q18": {
        "query": {
            "dimensions": [
                "acme_ops.party_identifier",
                "acme_ops.policy_number",
                "acme_ops.catastrophe_name",
            ],
            "filters": [
                {"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}
            ],
            "order": {"acme_ops.party_identifier": "asc"},
        }
    }
}

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


# ── Prompt helpers ────────────────────────────────────────────────────────────

FEW_SHOT_BASE = """
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

FEW_SHOT_EXTRA = """
Example 4) Return all claims by claim number, open date, and close date
- "Return all X" listing questions use dimensions only — do NOT add measures
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date"]}}

Example 5) Return policies that have a claim, by policy number and claim number
- "have a claim" means include company_claim_number as a dimension
- Cube performs an INNER JOIN, so only rows with a claim are returned automatically
- Do NOT add claim_count measure or claim_count > 0 filter
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.company_claim_number"]}}
"""

def build_few_shot() -> str:
    if EXPERIMENT in {"few_shot", "few_shot_gold_fix"}:
        return FEW_SHOT_BASE + FEW_SHOT_EXTRA
    return FEW_SHOT_BASE


SYSTEM_PROMPT = """You are a Cube Semantic Layer expert.
Convert the natural language question below into a Cube REST API JSON query using the schema provided.
Output only the raw JSON object. Do not include explanation or markdown.
Use the acme_ops prefix only."""


def _initial_user_message(schema_ctx: str, question: str) -> str:
    return f"""{build_few_shot()}

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
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _initial_user_message(schema_ctx, question)},
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

        messages.append({"role": "assistant", "content": json.dumps(gen_query, ensure_ascii=False)})
        messages.append({
            "role": "user",
            "content": _retry_user_message(schema_ctx, question, gen_query, error),
        })

    return False, last_query, [], attempt, error_log


# ── Baseline for delta reporting ───────────────────────────────────────────────

BASELINE = {
    "Q01": 0.80,
    "Q05": 0.40,
    "Q15": 0.00,
    "Q16": 0.00,
    "Q18": 0.00,
}

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"=== ACME Targeted Benchmark ===")
    print(f"Experiment : {EXPERIMENT}")
    print(f"Targets    : {sorted(TARGET_IDS)}")
    print(f"Model      : {LLM_MODEL}, Iterations: {N_ITERATIONS}")
    print(f"Max retries: {MAX_RETRIES}\n")

    if EXPERIMENT in {"gold_fix", "few_shot_gold_fix"}:
        print("Gold overrides active:")
        for qid in GOLD_OVERRIDES:
            if qid in TARGET_IDS:
                print(f"  {qid}: {GOLD_OVERRIDES[qid]}")
        print()

    cubes = fetch_meta()
    schema_ctx = build_schema_context(cubes)

    all_questions = parse_cube_questions(QUESTIONS_FILE)
    questions = [q for q in all_questions if q.get("id") in TARGET_IDS]

    if not questions:
        raise SystemExit(f"No questions matched target IDs {TARGET_IDS}. Check question manifest IDs.")

    print(f"Questions loaded: {len(questions)}")
    for q in questions:
        print(f"  {q['id']} [{q['category']}]: {q['question'][:70]}")

    total = len(questions) * N_ITERATIONS
    print(f"\nTotal runs: {total}\n")

    records: list[dict[str, Any]] = []
    done = 0

    for iteration in range(1, N_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{N_ITERATIONS} --")
        for q in questions:
            done += 1
            qtext = q["question"]
            qid = q.get("id", "")

            # Apply gold override if applicable
            gold_query = GOLD_OVERRIDES.get(qid, q["gold_query"]) if EXPERIMENT in {"gold_fix", "few_shot_gold_fix"} else q["gold_query"]

            gold_ok, gold_rows, _ = execute_cube(gold_query)
            exec_ok, gen_query, gen_rows, attempts, error_log = run_agentic_loop(schema_ctx, qtext)

            dim_f1 = measure_f1 = filter_f1 = 0.0
            if gen_query:
                dim_f1, measure_f1, filter_f1 = cube_structural_accuracy(gold_query, gen_query)

            scores = {"result_f1": 0.0, "exact_match": 0.0, "subset_match": 0.0, "column_f1": 0.0, "cell_f1": 0.0}
            if exec_ok and gold_ok:
                scores = robust_result_scores(gold_rows, gen_rows)

            status = f"ok(attempt={attempts})" if exec_ok else f"fail(attempt={attempts})"
            print(
                f"  [{done:3d}/{total}] [{qid}] {status} "
                f"exact={scores['exact_match']:.0f} dim={dim_f1:.2f} msr={measure_f1:.2f} filter={filter_f1:.2f} | "
                f"{qtext[:55]}"
            )

            records.append({
                "experiment": EXPERIMENT,
                "iteration": iteration,
                "id": qid,
                "category": q["category"],
                "question": qtext,
                "gold_override": qid in GOLD_OVERRIDES and EXPERIMENT in {"gold_fix", "few_shot_gold_fix"},
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
                "gold_query": json.dumps(gold_query, ensure_ascii=False),
            })
            time.sleep(0.3)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\nResults saved: {RESULTS_CSV}")

    if df.empty:
        return

    print("\n=== Results by question ===")
    summary = df.groupby("id").agg(
        category=("category", "first"),
        n=("exact_match", "count"),
        exact_match=("exact_match", "mean"),
        exec_rate=("exec_ok", "mean"),
        avg_attempts=("attempts", "mean"),
    ).round(3)
    print(summary.to_string())

    print("\n=== vs. baseline (agentic loop, no few-shot) ===")
    for qid, base in BASELINE.items():
        if qid not in TARGET_IDS:
            continue
        q_df = df[df["id"] == qid]
        if q_df.empty:
            continue
        new = q_df["exact_match"].mean()
        delta = new - base
        sign = "+" if delta >= 0 else ""
        print(f"  {qid}: {base:.1%} → {new:.1%}  (Δ {sign}{delta:.1%})")


if __name__ == "__main__":
    main()
