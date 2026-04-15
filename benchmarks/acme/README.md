# ACME Benchmark

This package contains the ACME benchmark implementation for comparing Cube Semantic Layer NL2JSON against raw DDL SQL NL2SQL.

The source baseline is `/Users/hc.cho/Projects/semantic-layer-llm-benchmarking`.

## Layout

- `docs/`: implementation, planning, and article outline documents
- `manifests/`: source-aligned question manifest
- `schemas/`: source DDL snapshots, PostgreSQL prompt DDL, and extension DDL
- `data/source/`: small benchmark source CSV snapshots
- `questions/core/`: executable Cube and DDL gold query seed files plus exclusions
- `questions/extensions/`: extension question sets outside the source denominator
- `src/acme_benchmark/`: shared benchmark library code
- `scripts/`: benchmark runners and data loading scripts
- `results/`: generated benchmark CSV outputs
- `reports/`: benchmark reports

## Run

Required environment:

```bash
export OPENAI_API_KEY=...
export CUBE_BASE_URL=http://host:4000/cubejs-api/v1
export CUBE_TOKEN=...
export DATABASE_URL=postgresql://...
```

Optional environment:

```bash
export ACME_LLM_MODEL=gpt-4o
export ACME_BENCHMARK_ITERATIONS=5
```

Run from the repository root:

```bash
python3 benchmarks/acme/scripts/cube_benchmark.py
python3 benchmarks/acme/scripts/ddl_benchmark.py
```

## Current Status

The manifest tracks all 44 source questions. Q44 is excluded because it duplicates Q42, leaving a 43-question executable target. The migrated gold files currently contain the prior 11-question seed and are the next files to expand to the full executable target.

The package also includes a row-level entity retrieval extension in `questions/extensions/entity_retrieval_questions.md`. That extension requires the Party/Person model additions and is not counted in the source 43-question denominator.

To load source CSVs into PostgreSQL:

```bash
# First apply benchmarks/acme/schemas/extensions/party_person_extension.sql with a user
# that can create tables in oda_benchmark.
export DATABASE_URL=postgresql://...
export ACME_DATA_DIR=/path/to/ACME_Insurance/data
python3 benchmarks/acme/scripts/load_data.py
```
