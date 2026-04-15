#!/usr/bin/env python3
"""ACME raw DDL SQL LLM benchmark pipeline."""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acme_benchmark.common import POSTGRES_SCHEMA_DIR, QUESTIONS_DIR, RESULTS_DIR, env_required, iterations, llm_model, parse_sql_questions
from acme_benchmark.evaluator import dataframe_to_rows, result_scores


load_dotenv(os.path.expanduser("~/heartcube/.env"))
load_dotenv()

DB_URL = env_required("DATABASE_URL")
OPENAI_API_KEY = env_required("OPENAI_API_KEY")
LLM_MODEL = llm_model()
N_ITERATIONS = iterations()
QUESTIONS_FILE = QUESTIONS_DIR / "ddl_sql_questions.md"
RESULTS_CSV = RESULTS_DIR / "acme_ddl_results.csv"
DDL_SCHEMA = (POSTGRES_SCHEMA_DIR / "acme_schema_postgres.ddl").read_text(encoding="utf-8").strip()

client = OpenAI(api_key=OPENAI_API_KEY)


def get_conn() -> Any:
    return psycopg2.connect(DB_URL)


def execute_sql(sql: str, timeout: int = 20) -> tuple[bool, pd.DataFrame | str]:
    conn = None
    cur = None
    try:
        conn = get_conn()
        conn.set_session(readonly=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(f"SET statement_timeout = {timeout * 1000}")
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return True, pd.DataFrame(rows, columns=cols)
    except Exception as exc:
        return False, str(exc)
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


SYSTEM_PROMPT = """You are a PostgreSQL expert.
Convert the natural language question into a valid PostgreSQL SELECT query.
Use only the schema-qualified table and column names provided in the DDL context.
The schema is oda_benchmark.
Output only the raw SQL query. Do not include explanation or markdown."""

FEW_SHOT = """
Examples:

Q: How many claims do we have?
A: SELECT COUNT(company_claim_number) AS claim_count FROM oda_benchmark.acme_claim

Q: How many policies have agents sold by agent id?
A: SELECT party_identifier, COUNT(DISTINCT agreement_identifier) AS policy_count
   FROM oda_benchmark.acme_agreement_party_role
   WHERE party_role_code = 'AG'
   GROUP BY party_identifier
   ORDER BY policy_count DESC

Q: What is the total amount of premiums paid by policy number?
A: SELECT p.policy_number, SUM(pa.policy_amount) AS total_policy_amount
   FROM oda_benchmark.acme_policy p
   JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
   JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
   GROUP BY p.policy_number
   ORDER BY total_policy_amount DESC
""".strip()


def call_llm(question: str) -> str | None:
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{FEW_SHOT}\n\n## DDL Schema\n{DDL_SCHEMA}\n\nQ: {question}"},
            ],
        )
        raw = response.choices[0].message.content.strip()
        return re.sub(r"^```(?:sql)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    except Exception as exc:
        print(f"    [LLM error] {exc}")
        return None


def main() -> None:
    print("=== ACME Insurance DDL SQL Benchmark ===")
    print(f"Schema context: {len(DDL_SCHEMA.splitlines())} lines")

    questions = parse_sql_questions(QUESTIONS_FILE)
    print(f"Questions loaded: {len(questions)} from {QUESTIONS_FILE}")
    for category in ["LQLS", "LQHS", "HQLS", "HQHS"]:
        print(f"  {category}: {sum(1 for question in questions if question['category'] == category)}")

    print("\nPre-executing gold queries...")
    gold_results: dict[str, pd.DataFrame | None] = {}
    for question in questions:
        ok, result = execute_sql(question["gold_sql"])
        if ok:
            gold_results[question["question"]] = result
            print(f"  ok {question['question'][:60]}")
        else:
            gold_results[question["question"]] = None
            print(f"  fail {question['question'][:60]} - {result}")

    total = len(questions) * N_ITERATIONS
    print(f"\nStarting benchmark (model={LLM_MODEL}, iterations={N_ITERATIONS}, total={total})")

    records: list[dict[str, Any]] = []
    index = 0
    for iteration in range(1, N_ITERATIONS + 1):
        print(f"\n-- Iteration {iteration}/{N_ITERATIONS} --")
        for question in questions:
            index += 1
            question_text = question["question"]
            category = question["category"]
            gold_df = gold_results.get(question_text)

            gen_sql = call_llm(question_text)
            sql_parse_ok = 1 if gen_sql else 0
            exec_ok = 0
            scores = {"result_f1": 0.0, "exact_match": 0.0}

            if gen_sql:
                ok, result = execute_sql(gen_sql)
                if ok and gold_df is not None:
                    exec_ok = 1
                    scores = result_scores(dataframe_to_rows(gold_df), dataframe_to_rows(result))

            print(
                f"  [{index:3d}/{total}] [{category}] "
                f"exec={exec_ok} res={scores['result_f1']:.2f} | {question_text[:60]}"
            )

            records.append(
                {
                    "iteration": iteration,
                    "id": question.get("id", ""),
                    "source_index": question.get("source_index", ""),
                    "category": category,
                    "answer_shape": question.get("answer_shape", ""),
                    "requires_entity_resolution": int(question.get("requires_entity_resolution", False)),
                    "question": question_text,
                    "sql_parse_ok": sql_parse_ok,
                    "exec_ok": exec_ok,
                    "gold_exec_ok": 1 if gold_df is not None else 0,
                    "result_f1": round(scores["result_f1"], 4),
                    "exact_match": int(scores["exact_match"] == 1.0),
                    "gen_sql": gen_sql or "",
                    "gold_sql": question["gold_sql"],
                }
            )
            time.sleep(0.3)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df_results = pd.DataFrame(records)
    df_results.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\nResults saved: {RESULTS_CSV}")

    if df_results.empty:
        return

    print("\n=== By category ===")
    summary = df_results.groupby("category")[["sql_parse_ok", "exec_ok", "result_f1", "exact_match"]].mean().round(3)
    print(summary)

    print("\n=== Funnel (overall) ===")
    n = len(df_results)
    print(f"  SQL parse success: {df_results.sql_parse_ok.sum()}/{n} ({df_results.sql_parse_ok.mean() * 100:.1f}%)")
    print(f"  Exec success:      {df_results.exec_ok.sum()}/{n} ({df_results.exec_ok.mean() * 100:.1f}%)")
    print(f"  Exact match:       {df_results.exact_match.sum()}/{n} ({df_results.exact_match.mean() * 100:.1f}%)")


if __name__ == "__main__":
    main()
