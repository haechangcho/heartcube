# ACME Benchmark Implementation Plan

## Goal

Rebuild the ACME benchmark as a dedicated benchmark package under `benchmarks/acme/`, using `/Users/hc.cho/Projects/semantic-layer-llm-benchmarking` as the source baseline.

The final benchmark must compare:

- Cube Semantic Layer: natural language to Cube REST JSON
- Raw DDL SQL: natural language to PostgreSQL SQL

The target corpus is the full ACME 44-question benchmark from the baseline repository, with ambiguous questions excluded before execution and documented separately.

## Source Baseline

- Source repository: `/Users/hc.cho/Projects/semantic-layer-llm-benchmarking`
- Source question list: `benchmark_questions.md`
- Source ACME DDL: `ACME_Insurance/DDL/ACME_small.ddl`
- Source ACME data: `ACME_Insurance/data/*.csv`
- Source investigation TTL: `ACME_Insurance/investigation/acme-benchmark.ttl`

The benchmark package keeps immutable snapshots of the source files under `benchmarks/acme/schemas/source/`.

## Folder Layout

```text
benchmarks/acme/
  README.md

  docs/
    implementation-plan.md
    planning-direction.md
    article-outline.md

  manifests/
    question_manifest.yaml

  schemas/source/
    benchmark_questions.md
    ACME_small.ddl
    acme-benchmark.ttl

  schemas/postgres/
    acme_schema_postgres.ddl

  schemas/extensions/
    party_person_extension.sql

  data/source/
    Party.csv
    Person.csv

  questions/core/
    cube_questions.md
    ddl_sql_questions.md
    excluded_questions.md

  questions/extensions/
    entity_retrieval_questions.md

  src/acme_benchmark/
    common.py
    evaluator.py

  scripts/
    cube_benchmark.py
    ddl_benchmark.py
    load_data.py

  results/
    .gitkeep

  reports/
    acme-benchmark-report.md
```

## Inclusion Policy

The starting point is all 44 source questions.

Questions are excluded only before benchmark execution and only for one of these reasons:

- The question has more than one defensible result shape.
- The source wording conflicts with the source gold query shape.
- The question is a duplicate whose variants differ only by typo or whitespace.
- The required business metric is not expressible without adding a new semantic definition not present in the source baseline.

Excluded questions are recorded in `questions/core/excluded_questions.md` and marked in `manifests/question_manifest.yaml`.

## Required Implementation

1. Create the benchmark package layout under `benchmarks/acme/`.
2. Snapshot the source benchmark files from the baseline repository.
3. Build a 44-question manifest with stable IDs, source index, category, inclusion flag, and question text.
4. Move the current 11-question Cube/DDL files into `benchmarks/acme/questions/core/` as the initial editable benchmark files.
5. Move the current ACME benchmark runners into `benchmarks/acme/scripts/`.
6. Add shared benchmark utilities:
   - `common.py` for path resolution, environment loading, question parsing, CSV writing, and manifest loading
   - `evaluator.py` for shared result normalization and F1/exact-match scoring
7. Update both pipelines to:
   - use the new folder layout
   - support `LQLS`, `LQHS`, `HQLS`, and `HQHS`
   - use environment variables instead of hard-coded credentials
   - share the same evaluator
   - fail early when required environment variables are missing
8. Replace the DDL prompt context with the ACME schema used by the benchmark package.
9. Correct known prompt defects, including the obsolete Cube member `acme_ops.premium_amount`.
10. Add source-aligned reporting under `benchmarks/acme/reports/`.
11. Verify syntax and parser behavior locally.
12. Commit and push the completed benchmark package changes.
13. Sync the pushed branch on `ssh dev_mcp`.

## Environment Variables

The pipelines must read configuration from environment variables:

- `OPENAI_API_KEY`
- `ACME_LLM_MODEL`, default `gpt-4o`
- `ACME_BENCHMARK_ITERATIONS`, default `5`
- `CUBE_BASE_URL`
- `CUBE_TOKEN`
- `DATABASE_URL`

No credentials or private IP defaults are stored in the benchmark code.

## Execution Commands

From the repository root:

```bash
python3 benchmarks/acme/scripts/cube_benchmark.py
python3 benchmarks/acme/scripts/ddl_benchmark.py
```

Expected outputs:

```text
benchmarks/acme/results/acme_cube_results.csv
benchmarks/acme/results/acme_ddl_results.csv
```

## Verification

Local static verification:

```bash
python3 -m py_compile \
  benchmarks/acme/src/acme_benchmark/common.py \
  benchmarks/acme/src/acme_benchmark/evaluator.py \
  benchmarks/acme/scripts/cube_benchmark.py \
  benchmarks/acme/scripts/ddl_benchmark.py
```

Question parser verification:

```bash
python3 benchmarks/acme/src/acme_benchmark/common.py
```

Remote sync verification:

```bash
ssh dev_mcp "cd ~/heartcube && git status --short && git branch --show-current"
```

## Completion Criteria

- Benchmark files live under `benchmarks/acme/`.
- Source snapshots are present.
- Manifest contains all 44 source questions.
- Ambiguous/excluded questions are documented.
- Current pipelines run from the new paths and use shared evaluator logic.
- No benchmark code contains hard-coded credentials.
- Local Python syntax verification passes.
- Changes are committed and pushed.
- `dev_mcp:~/heartcube` is synced to the pushed branch.
