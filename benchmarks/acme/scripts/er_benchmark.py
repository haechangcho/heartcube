#!/usr/bin/env python3
"""ACME Entity Retrieval extension benchmark — Cube and DDL SQL tracks."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from acme_benchmark.common import RESULTS_DIR, env_required, iterations, llm_model
from acme_benchmark.evaluator import dataframe_to_rows, result_scores

load_dotenv(os.path.expanduser("~/heartcube/.env"))
load_dotenv()

CUBE_BASE_URL = env_required("CUBE_BASE_URL").rstrip("/")
CUBE_TOKEN = env_required("CUBE_TOKEN")
DB_URL = env_required("DATABASE_URL")
OPENAI_API_KEY = env_required("OPENAI_API_KEY")
LLM_MODEL = llm_model()
N_ITERATIONS = iterations()

QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "questions" / "extensions" / "entity_retrieval_questions.md"
RESULTS_CSV = RESULTS_DIR / "acme_er_results.csv"

CUBE_HEADERS = {"Authorization": f"Bearer {CUBE_TOKEN}", "Content-Type": "application/json"}
client = OpenAI(api_key=OPENAI_API_KEY)


# ── Parsers ──────────────────────────────────────────────────────────────────

def parse_er_questions(path: Path) -> list[dict[str, Any]]:
    """Parse ER extension questions — each has a json block AND a sql block."""
    text = path.read_text(encoding="utf-8")
    questions: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^\d+\.\s+(.+?)\n+```json\s*(\{.*?\})\s*```\s*```sql\s*(.*?)\s*```",
        re.MULTILINE | re.DOTALL,
    )
    for m in pattern.finditer(text):
        question_text = re.sub(r"\s+", " ", m.group(1)).strip()
        questions.append({
            "category": "ER",
            "answer_shape": "entity_row_retrieval",
            "requires_entity_resolution": "peyton manning" in question_text.lower(),
            "question": question_text,
            "gold_cube_query": json.loads(m.group(2)),
            "gold_sql": m.group(3).strip(),
        })
    return questions


# ── Cube helpers ─────────────────────────────────────────────────────────────

def fetch_cube_meta() -> list[dict[str, Any]]:
    r = requests.get(f"{CUBE_BASE_URL}/meta", headers=CUBE_HEADERS, timeout=15)
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


def execute_cube(query: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    try:
        r = requests.post(f"{CUBE_BASE_URL}/load", headers=CUBE_HEADERS, json=query, timeout=20)
        if r.status_code == 200:
            return True, r.json().get("data", [])
        return False, []
    except Exception:
        return False, []


CUBE_FEW_SHOT = """
Cube REST API accepts queries in this JSON format:
{"query": {"dimensions": ["view.dim"], "measures": ["view.msr"], "filters": [{"member": "view.field", "operator": "equals", "values": ["value"]}], "order": {"view.field": "asc"}}}

Use the acme_ops prefix. Use party_role_code filter to distinguish policyholders (PH) from agents (AG).
party_full_legal_name is the person's full name (e.g. "Mary Policy Holder").
party_identifier is the numeric party/person id.
"""


def generate_cube_query(schema_ctx: str, question: str) -> tuple[bool, dict[str, Any]]:
    prompt = f"""You are a Cube Semantic Layer expert.
Convert the natural language question into a Cube REST API JSON query.
Output only the raw JSON object.

{CUBE_FEW_SHOT}

## Available schema
{schema_ctx}

## Question
{question}"""
    try:
        rsp = client.chat.completions.create(
            model=LLM_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=512,
        )
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", rsp.choices[0].message.content.strip(), flags=re.DOTALL).strip()
        return True, json.loads(raw)
    except Exception:
        return False, {}


# ── SQL helpers ──────────────────────────────────────────────────────────────

DDL_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "postgres" / "acme_schema_postgres.ddl"
DDL_SCHEMA = DDL_SCHEMA_PATH.read_text(encoding="utf-8").strip()


def execute_sql(sql: str) -> tuple[bool, pd.DataFrame | str]:
    try:
        conn = psycopg2.connect(DB_URL)
        conn.set_session(readonly=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SET statement_timeout = 20000")
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        cur.close()
        conn.close()
        return True, pd.DataFrame(rows, columns=cols)
    except Exception as e:
        return False, str(e)[:120]


SQL_SYSTEM = """You are a PostgreSQL expert.
Convert the natural language question into a valid PostgreSQL SELECT query using the schema.
The schema is oda_benchmark. Tables include acme_person (first_name, last_name, full_legal_name)
and acme_party, joined via acme_agreement_party_role (party_identifier, party_role_code PH/AG).
Output only raw SQL."""


def generate_sql(question: str) -> str | None:
    try:
        rsp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SQL_SYSTEM},
                {"role": "user", "content": f"## DDL\n{DDL_SCHEMA}\n\nQ: {question}"},
            ],
            temperature=0.3, max_tokens=512,
        )
        raw = re.sub(r"^```(?:sql)?\s*|\s*```$", "", rsp.choices[0].message.content.strip(), flags=re.DOTALL).strip()
        return raw
    except Exception:
        return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== ACME Entity Retrieval Extension Benchmark ===")
    questions = parse_er_questions(QUESTIONS_FILE)
    print(f"Questions: {len(questions)}")
    for q in questions:
        print(f"  [{q['category']}] {q['question'][:70]}")

    print("\nPre-validating gold queries...")
    cubes = fetch_cube_meta()
    schema_ctx = build_schema_context(cubes)

    for q in questions:
        ok_c, rows_c = execute_cube(q["gold_cube_query"])
        ok_s, result_s = execute_sql(q["gold_sql"])
        cube_status = f"{len(rows_c)} rows" if ok_c else "FAIL"
        sql_status = f"{len(result_s)} rows" if ok_s else f"FAIL: {result_s}"
        print(f"  {q['question'][:55]}")
        print(f"    Cube gold: {cube_status} | SQL gold: {sql_status}")

    total = len(questions) * N_ITERATIONS
    print(f"\nStarting benchmark (model={LLM_MODEL}, iterations={N_ITERATIONS}, total={total * 2} LLM calls)\n")

    records: list[dict[str, Any]] = []
    idx = 0

    for iteration in range(1, N_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{N_ITERATIONS} --")
        for q in questions:
            idx += 1
            qtext = q["question"]

            # ── Cube track ──
            gold_cube_ok, gold_cube_rows = execute_cube(q["gold_cube_query"])
            parse_ok, gen_cube = generate_cube_query(schema_ctx, qtext)
            cube_exec_ok, gen_cube_rows = (False, [])
            if parse_ok:
                cube_exec_ok, gen_cube_rows = execute_cube(gen_cube)
            cube_scores = result_scores(gold_cube_rows, gen_cube_rows) if (cube_exec_ok and gold_cube_ok) else {"result_f1": 0.0, "exact_match": 0.0}

            # ── SQL track ──
            gold_sql_ok, gold_df = execute_sql(q["gold_sql"])
            gen_sql = generate_sql(qtext)
            sql_exec_ok, gen_df = (False, pd.DataFrame())
            if gen_sql:
                sql_exec_ok, gen_df = execute_sql(gen_sql)
            sql_scores = {"result_f1": 0.0, "exact_match": 0.0}
            if sql_exec_ok and gold_sql_ok:
                sql_scores = result_scores(dataframe_to_rows(gold_df), dataframe_to_rows(gen_df))

            print(
                f"  [{idx:2d}/{total}] {qtext[:50]}"
                f"\n         Cube: parse={int(parse_ok)} exec={int(cube_exec_ok)} f1={cube_scores['result_f1']:.2f}"
                f"\n         SQL:  exec={int(sql_exec_ok)} f1={sql_scores['result_f1']:.2f}"
            )

            records.append({
                "iteration": iteration,
                "question": qtext,
                "requires_entity_resolution": int(q["requires_entity_resolution"]),
                # Cube
                "cube_parse_ok": int(parse_ok),
                "cube_exec_ok": int(cube_exec_ok),
                "cube_gold_exec_ok": int(gold_cube_ok),
                "cube_result_f1": round(cube_scores["result_f1"], 4),
                "cube_exact_match": int(cube_scores["exact_match"] == 1.0),
                "gen_cube_query": json.dumps(gen_cube, ensure_ascii=False),
                "gold_cube_query": json.dumps(q["gold_cube_query"], ensure_ascii=False),
                # SQL
                "sql_parse_ok": int(bool(gen_sql)),
                "sql_exec_ok": int(sql_exec_ok),
                "sql_gold_exec_ok": int(gold_sql_ok),
                "sql_result_f1": round(sql_scores["result_f1"], 4),
                "sql_exact_match": int(sql_scores["exact_match"] == 1.0),
                "gen_sql": gen_sql or "",
                "gold_sql": q["gold_sql"],
            })
            time.sleep(0.5)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\nResults saved: {RESULTS_CSV}")

    if df.empty:
        return

    print("\n=== Entity Retrieval Summary ===")
    print(f"  Cube  — parse: {df.cube_parse_ok.mean():.1%}  exec: {df.cube_exec_ok.mean():.1%}  exact: {df.cube_exact_match.mean():.1%}")
    print(f"  SQL   — parse: {df.sql_parse_ok.mean():.1%}   exec: {df.sql_exec_ok.mean():.1%}  exact: {df.sql_exact_match.mean():.1%}")
    print()
    for _, row in df[df.iteration == 1].iterrows():
        print(f"  {row.question[:55]}")
        print(f"    Cube exact={row.cube_exact_match}  SQL exact={row.sql_exact_match}")


if __name__ == "__main__":
    main()
