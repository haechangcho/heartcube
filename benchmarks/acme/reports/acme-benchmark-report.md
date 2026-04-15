# ACME Benchmark Report

## Status

This report has been reset for the full ACME benchmark implementation under `benchmarks/acme/`.

The previous 11-question subset results are no longer treated as the final benchmark. They were migrated only as seed gold files for the new package layout.

## Source Baseline

- Source repository: `/Users/hc.cho/Projects/semantic-layer-llm-benchmarking`
- Source question list: `benchmarks/acme/source/benchmark_questions.md`
- Source DDL snapshot: `benchmarks/acme/source/ACME_small.ddl`
- PostgreSQL execution DDL context: `benchmarks/acme/source/acme_schema_postgres.ddl`
- Source TTL snapshot: `benchmarks/acme/source/acme-benchmark.ttl`

## Question Scope

The source benchmark contains 44 questions:

| Category | Source Questions |
|---|---:|
| LQLS | 12 |
| LQHS | 10 |
| HQLS | 11 |
| HQHS | 11 |

Q44 is excluded because it duplicates Q42. The executable target is therefore 43 questions.

The manifest is `benchmarks/acme/source/question_manifest.yaml`.

## Current Implementation

Implemented:

- Dedicated benchmark package structure under `benchmarks/acme/`
- Source snapshots from the baseline repository
- 44-question manifest with inclusion flags
- Exclusion record for Q44
- Migrated Cube and DDL seed question files
- Migrated Cube and DDL benchmark pipelines
- Shared path/env/manifest utilities
- Shared result evaluator
- Environment-variable based pipeline configuration
- Cube prompt member fix: `acme_ops.premium_amount` -> `acme_ops.total_policy_amount`
- Average policy size gold fix for the seed HQLS question
- Cube expense measures exposed for full-loss questions:
  `expense_payment_amount`, `expense_reserve_amount`, `total_full_loss_amount`

Pending before final benchmark execution:

- Expand `questions/cube_questions.md` from the 11-question seed to all 43 included questions
- Expand `questions/ddl_sql_questions.md` from the 11-question seed to all 43 included questions
- Add remaining Cube model/view members required by policy-level loss ratio and average-loss HQHS questions
- Pre-execute every Cube and SQL gold query
- Run both tracks for the configured iteration count
- Replace this status report with measured results

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
python3 benchmarks/acme/pipelines/cube_benchmark_pipeline.py
python3 benchmarks/acme/pipelines/ddl_benchmark_pipeline.py
```

Outputs:

```text
benchmarks/acme/results/acme_cube_results.csv
benchmarks/acme/results/acme_ddl_results.csv
```
