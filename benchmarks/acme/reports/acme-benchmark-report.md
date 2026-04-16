# ACME Benchmark Report

## Status

This report has been reset for the full ACME benchmark implementation under `benchmarks/acme/`.

The previous 11-question subset results are no longer treated as the final benchmark. They were migrated only as seed gold files for the new package layout.

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

Pending before final benchmark execution:

- Preload Party/Person data in the remote benchmark database before running entity retrieval extension questions
- Pre-execute every Cube and SQL gold query against the live database to validate correctness
- Run both tracks for the configured iteration count
- Replace this status report with measured results

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
