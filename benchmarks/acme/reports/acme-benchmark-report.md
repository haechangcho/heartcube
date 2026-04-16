# ACME Benchmark Report

## Status

**Run completed: 2026-04-16**

- Model: gpt-4o
- Iterations: 3
- Questions: 43 (Q01–Q43, Q44 excluded as duplicate)
- Tracks: Cube Semantic Layer vs Raw DDL SQL

## Source Baseline

- Source repository: `/Users/hc.cho/Projects/semantic-layer-llm-benchmarking`
- Source question list: `benchmarks/acme/schemas/source/benchmark_questions.md`
- Source DDL snapshot: `benchmarks/acme/schemas/source/ACME_small.ddl`
- PostgreSQL execution DDL context: `benchmarks/acme/schemas/postgres/acme_schema_postgres.ddl`
- Source TTL snapshot: `benchmarks/acme/schemas/source/acme-benchmark.ttl`

## Question Scope

The source benchmark contains 44 questions:

| Category | Source Questions |
|---|---:|
| LQLS | 12 |
| LQHS | 10 |
| HQLS | 11 |
| HQHS | 11 |

Q44 is excluded because it duplicates Q42. The executable target is therefore 43 questions.

The manifest is `benchmarks/acme/manifests/question_manifest.yaml`.

## Current Implementation

Implemented:

- Dedicated benchmark package structure under `benchmarks/acme/`
- Source snapshots from the baseline repository
- 44-question manifest with inclusion flags
- Exclusion record for Q44
- Migrated Cube and DDL seed question files
- Migrated Cube and DDL benchmark scripts
- Shared path/env/manifest utilities
- Shared result evaluator
- Environment-variable based pipeline configuration
- Cube prompt member fix: `acme_ops.premium_amount` -> `acme_ops.total_policy_amount`
- Average policy size gold fix for the seed HQLS question
- Cube expense measures exposed for full-loss questions:
  `expense_payment_amount`, `expense_reserve_amount`, `total_full_loss_amount`
- Answer-shape tags added to `question_manifest.yaml`
- Party/Person DDL, loader support, Cube models, and `acme_ops` name dimensions added
- Entity retrieval extension questions added under `questions/extensions/entity_retrieval_questions.md`

## Results

### Overall Funnel

| Track | Parse Rate | Exec Rate | Exact Match | Result F1 |
|---|---:|---:|---:|---:|
| Cube SL | 100.0% | 99.2% | 83.7% | 83.7% |
| Raw DDL SQL | 100.0% | 75.2% | 29.5% | 29.5% |

### By Original Category

| Category | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|
| LQLS | 83.3% | 33.3% | 83.3% | 33.3% |
| LQHS | 70.0% | 10.0% | 70.0% | 10.0% |
| HQLS | 90.9% | 51.5% | 90.9% | 51.5% |
| HQHS | 90.0% | 20.0% | 90.0% | 20.0% |

### By Answer Shape

| Answer Shape | n | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|---:|
| aggregate | 63 | 90.5% | 36.5% | 90.5% | 36.5% |
| dimension_listing | 66 | 77.3% | 22.7% | 77.3% | 22.7% |

### Notes

- Cube exec failure (1/129): LQHS Q05 — LLM omitted `company_claim_number` dimension, only selected `policy_number`, producing a mismatched result shape.
- DDL exec failures (32/129): concentrated in LQHS (70% failure) and HQHS (37% failure). Primary causes: missing joins to discriminator tables (`acme_loss_payment`, `acme_expense_*`), wrong aggregation grouping for multi-role party queries.
- Cube LQHS gap (70% vs 90%+ other categories): multi-role questions (Q15, Q16, Q18) where LLM omitted `party_role_code` as a dimension, producing fan-out rows that don't match the gold shape.
- HQHS loss ratio (Q41): Cube query correctly returned both `total_full_loss_amount` and `total_policy_amount`; 1 iteration returned only one measure.

## Pending

- Run entity retrieval extension questions (ER-1 through ER-5) as a separate track after Party/Person data is confirmed joined
- Increase iterations to 5 for final publication run

Recently completed:

- Expanded `questions/core/cube_questions.md` from 11 HQLS seed to all 43 included questions (LQLS, LQHS, HQLS, HQHS)
- Expanded `questions/core/ddl_sql_questions.md` from 11 HQLS seed to all 43 included questions
- Added `avg_full_loss_amount` measure to `acme_claim` cube
- Added `policy_effective_date`, `policy_expiration_date` to `acme_ops` view (from `acme_policy`)
- Added `coverage_effective_date`, `coverage_expiration_date` to `acme_ops` view (from `acme_policy_coverage_detail`)
- Added `avg_full_loss_amount` to `acme_ops` view (from `acme_claim`)
- Saved source article snapshot: `docs/source-article-dbt-roundup.md`

## Execution

Required environment:

```bash
export OPENAI_API_KEY=...
export CUBE_BASE_URL=...
export CUBE_TOKEN=...
export DATABASE_URL=...
```

Run from repo root:

```bash
python3 benchmarks/acme/scripts/cube_benchmark.py
python3 benchmarks/acme/scripts/ddl_benchmark.py
```

Outputs:

```text
benchmarks/acme/results/acme_cube_results.csv
benchmarks/acme/results/acme_ddl_results.csv
```
