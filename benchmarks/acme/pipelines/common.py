#!/usr/bin/env python3
"""Shared utilities for the ACME benchmark pipelines."""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any


PIPELINES_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = PIPELINES_DIR.parent
REPO_ROOT = BENCHMARK_DIR.parent.parent
SOURCE_DIR = BENCHMARK_DIR / "source"
QUESTIONS_DIR = BENCHMARK_DIR / "questions"
RESULTS_DIR = BENCHMARK_DIR / "results"
REPORTS_DIR = BENCHMARK_DIR / "reports"


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got: {raw}") from exc


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be a number, got: {raw}") from exc


def llm_model() -> str:
    return os.environ.get("ACME_LLM_MODEL", "gpt-4o").strip() or "gpt-4o"


def iterations() -> int:
    return env_int("ACME_BENCHMARK_ITERATIONS", 5)


def parse_cube_questions(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    questions: list[dict[str, Any]] = []
    manifest = manifest_by_question()
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
        for match in numbered_q.finditer(body):
            question = re.sub(r"\s+", " ", match.group(1)).strip()
            questions.append(
                with_manifest(
                    {
                        "category": category,
                        "question": question,
                        "gold_query": json.loads(match.group(2)),
                    },
                    manifest,
                )
            )
    return questions


def parse_sql_questions(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    questions: list[dict[str, Any]] = []
    manifest = manifest_by_question()
    cat_section = re.compile(
        r"^## (LQLS|LQHS|HQLS|HQHS)[^\n]*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    numbered_q = re.compile(
        r"^\d+\.\s+(.+?)\s*```sql\s*(.*?)\s*```",
        re.MULTILINE | re.DOTALL,
    )
    for section in cat_section.finditer(text):
        category, body = section.group(1), section.group(2)
        for match in numbered_q.finditer(body):
            question = re.sub(r"\s+", " ", match.group(1)).strip()
            questions.append(
                with_manifest(
                    {
                        "category": category,
                        "question": question,
                        "gold_sql": match.group(2).strip(),
                    },
                    manifest,
                )
            )
    return questions


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    manifest_path = path or SOURCE_DIR / "question_manifest.yaml"
    questions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("  - "):
            if current:
                questions.append(current)
            current = {}
            key, value = line[4:].split(": ", 1)
            current[key] = _parse_manifest_value(value)
        elif current and line.startswith("    ") and ": " in line:
            key, value = line.strip().split(": ", 1)
            current[key] = _parse_manifest_value(value)
    if current:
        questions.append(current)
    return questions


def manifest_by_question() -> dict[str, dict[str, Any]]:
    return {normalize_question(row["question"]): row for row in load_manifest() if row.get("question")}


def with_manifest(question: dict[str, Any], manifest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = manifest.get(normalize_question(question["question"]), {})
    if row:
        question["id"] = row.get("id", "")
        question["source_index"] = row.get("source_index", "")
        question["answer_shape"] = row.get("answer_shape", "")
        question["requires_entity_resolution"] = bool(row.get("requires_entity_resolution", False))
    else:
        question["id"] = ""
        question["source_index"] = ""
        question["answer_shape"] = ""
        question["requires_entity_resolution"] = False
    return question


def normalize_question(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _parse_manifest_value(value: str) -> Any:
    value = value.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"')
    try:
        return int(value)
    except ValueError:
        return value


def print_manifest_summary() -> None:
    questions = load_manifest()
    included = [q for q in questions if q.get("included")]
    print(f"manifest_questions={len(questions)}")
    print(f"included_questions={len(included)}")
    for category in ["LQLS", "LQHS", "HQLS", "HQHS"]:
        total = sum(1 for q in questions if q.get("category") == category)
        active = sum(1 for q in included if q.get("category") == category)
        print(f"{category}: {active}/{total}")
    for shape in sorted({q.get("answer_shape", "") for q in included if q.get("answer_shape")}):
        print(f"{shape}: {sum(1 for q in included if q.get('answer_shape') == shape)}")


if __name__ == "__main__":
    print_manifest_summary()
