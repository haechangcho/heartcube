"""Shared result scoring for ACME benchmark tracks."""

from __future__ import annotations

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


def dataframe_to_rows(df: Any) -> list[dict[str, Any]]:
    if df is None:
        return []
    return df.to_dict(orient="records")


def _normalize_row(row: dict[str, Any]) -> frozenset[tuple[str, str]]:
    return frozenset((key, _normalize_value(value)) for key, value in row.items())


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        decimal = Decimal(str(value))
        return str(decimal.quantize(Decimal("0.0001")).normalize())
    except (InvalidOperation, ValueError):
        return str(value).strip()
