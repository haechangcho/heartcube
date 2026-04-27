"""Shared result scoring for ACME benchmark tracks."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any


def component_f1(gold_set: set[str], gen_set: set[str]) -> tuple[float, float, float]:
    if not gold_set and not gen_set:
        return 1.0, 1.0, 1.0
    if not gold_set or not gen_set:
        return 0.0, 0.0, 0.0
    tp = len(gold_set & gen_set)
    precision = tp / len(gen_set)
    recall = tp / len(gold_set)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def cube_structural_accuracy(gold: dict[str, Any], gen: dict[str, Any]) -> tuple[float, float, float]:
    gold_query = gold.get("query", {})
    gen_query = gen.get("query", {})
    _, _, dim_f1 = component_f1(
        set(gold_query.get("dimensions", [])),
        set(gen_query.get("dimensions", [])),
    )
    _, _, measure_f1 = component_f1(
        set(gold_query.get("measures", [])),
        set(gen_query.get("measures", [])),
    )
    gold_filters = {f.get("member", "") for f in gold_query.get("filters", [])}
    gen_filters = {f.get("member", "") for f in gen_query.get("filters", [])}
    gold_filters.discard("")
    gen_filters.discard("")
    _, _, filter_f1 = component_f1(gold_filters, gen_filters)
    return dim_f1, measure_f1, filter_f1


def result_scores(gold_rows: list[dict[str, Any]], gen_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Strict row-level result scoring.

    Rows match only when the full set of (column, value) pairs is identical.
    This conservative score is kept under the existing result_f1/exact_match
    names for backwards-compatible reporting.
    """
    if not gold_rows and not gen_rows:
        return {"result_f1": 1.0, "exact_match": 1.0}
    if not gold_rows or not gen_rows:
        return {"result_f1": 0.0, "exact_match": 0.0}

    gold_set = {_normalize_row(row) for row in gold_rows}
    gen_set = {_normalize_row(row) for row in gen_rows}
    tp = len(gold_set & gen_set)
    precision = tp / len(gen_set) if gen_set else 0.0
    recall = tp / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = 1.0 if gold_set == gen_set else 0.0
    return {"result_f1": f1, "exact_match": exact}


def projection_column_scores(gold_rows: list[dict[str, Any]], gen_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Column-set precision/recall/F1 for projection quality."""
    precision, recall, f1 = component_f1(_column_set(gold_rows), _column_set(gen_rows))
    return {
        "column_precision": precision,
        "column_recall": recall,
        "column_f1": f1,
    }


def cell_value_scores(gold_rows: list[dict[str, Any]], gen_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Cell-level overlap over (column, value) pairs across the full result."""
    precision, recall, f1 = _counter_f1(_cell_counter(gold_rows), _cell_counter(gen_rows))
    return {
        "cell_precision": precision,
        "cell_recall": recall,
        "cell_f1": f1,
    }


def subset_result_scores(gold_rows: list[dict[str, Any]], gen_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Return 1 when the generated result contains the gold answer.

    Extra generated columns are allowed. Every gold row, projected onto the gold
    columns, must appear in the generated rows after the same normalization used
    by the other result metrics.
    """
    if not gold_rows:
        return {"subset_match": 1.0 if not gen_rows else 0.0}
    if not gen_rows:
        return {"subset_match": 0.0}

    gold_cols = _column_set(gold_rows)
    gen_cols = _column_set(gen_rows)
    if not gold_cols.issubset(gen_cols):
        return {"subset_match": 0.0}

    gold_projected = {_project_row(row, gold_cols) for row in gold_rows}
    gen_projected = {_project_row(row, gold_cols) for row in gen_rows}
    return {"subset_match": 1.0 if gold_projected.issubset(gen_projected) else 0.0}


def robust_result_scores(gold_rows: list[dict[str, Any]], gen_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Combined result metrics for benchmark reporting."""
    scores: dict[str, float] = {}
    scores.update(result_scores(gold_rows, gen_rows))
    scores.update(subset_result_scores(gold_rows, gen_rows))
    scores.update(projection_column_scores(gold_rows, gen_rows))
    scores.update(cell_value_scores(gold_rows, gen_rows))
    return scores


def dataframe_to_rows(df: Any) -> list[dict[str, Any]]:
    if df is None:
        return []
    return df.to_dict(orient="records")


def _normalize_row(row: dict[str, Any]) -> frozenset[tuple[str, str]]:
    return frozenset((_normalize_column(key), _normalize_value(value)) for key, value in row.items())


def _normalize_column(key: str) -> str:
    return key.lower().replace(" ", "_")


def _column_set(rows: list[dict[str, Any]]) -> set[str]:
    return {_normalize_column(key) for row in rows for key in row}


def _cell_counter(rows: list[dict[str, Any]]) -> Counter[tuple[str, str]]:
    return Counter(
        (_normalize_column(key), _normalize_value(value))
        for row in rows
        for key, value in row.items()
    )


def _counter_f1(
    gold_counter: Counter[tuple[str, str]],
    gen_counter: Counter[tuple[str, str]],
) -> tuple[float, float, float]:
    if not gold_counter and not gen_counter:
        return 1.0, 1.0, 1.0
    if not gold_counter or not gen_counter:
        return 0.0, 0.0, 0.0
    tp = sum((gold_counter & gen_counter).values())
    precision = tp / sum(gen_counter.values())
    recall = tp / sum(gold_counter.values())
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _project_row(row: dict[str, Any], columns: set[str]) -> frozenset[tuple[str, str]]:
    normalized = {_normalize_column(key): _normalize_value(value) for key, value in row.items()}
    return frozenset((column, normalized.get(column, "")) for column in sorted(columns))


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        decimal = Decimal(str(value))
        return str(decimal.quantize(Decimal("0.0001")).normalize())
    except (InvalidOperation, ValueError):
        return str(value).strip()
