# ACME Benchmark

This package contains the ACME benchmark implementation for comparing Cube Semantic Layer NL2JSON against raw DDL SQL NL2SQL.

The source baseline is `/Users/hc.cho/Projects/semantic-layer-llm-benchmarking`.

## Layout

- `source/`: source snapshots and `question_manifest.yaml`
- `questions/`: executable Cube and DDL gold query files plus exclusions
- `pipelines/`: benchmark runners and shared scoring code
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
python3 benchmarks/acme/pipelines/cube_benchmark_pipeline.py
python3 benchmarks/acme/pipelines/ddl_benchmark_pipeline.py
```

## Current Status

The manifest tracks all 44 source questions. Q44 is excluded because it duplicates Q42, leaving a 43-question executable target. The migrated gold files currently contain the prior 11-question seed and are the next files to expand to the full executable target.

The package also includes a row-level entity retrieval extension in `questions/entity_retrieval_questions.md`. That extension requires the Party/Person model additions and is not counted in the source 43-question denominator.

To load source CSVs into PostgreSQL:

```bash
export DATABASE_URL=postgresql://...
export ACME_DATA_DIR=/path/to/ACME_Insurance/data
python3 benchmarks/acme/pipelines/load_acme_data.py
```
