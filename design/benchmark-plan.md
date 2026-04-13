# NL2SQL Benchmark Plan: Cube vs dbt Semantic Layer

## 1. Objective

Replicate the [dbt Semantic Layer LLM Benchmarking](https://github.com/dbt-labs/semantic-layer-llm-benchmarking) experiment using **Cube** as the semantic layer, and compare NL2SQL accuracy between the two approaches on the same ACME Insurance dataset.

---

## 2. Reference Experiment (dbt SL) — Exact Methodology

The original experiment runs **two parallel tracks** and compares both against gold:

| Track | Generator | Prompt context |
|---|---|---|
| **SL track** | GPT-4 → dbt SL SQL query | metrics + dimensions + entities (NAME, DESCRIPTION) from `/semantic_layer.*()` |
| **SQL track** | GPT-4 → raw SQL query | full DDL text (`ACME_small.ddl`) |

Both generated queries are executed against the same dbt Cloud JDBC endpoint and compared to the **gold result DataFrame** using `compare_query_results()`.

### Evaluation metric (original)

**Single binary metric: `is_result_equivalent` (True / False)**

```python
def compare_query_results(gold_df, comparison_df):
    # 1. Match columns by type + sorted values (fuzzy column mapping)
    # 2. Sort rows in both DataFrames
    # 3. Return gold_df.equals(comparison_df)  ← exact match only
```

- No partial credit — only exact DataFrame match counts
- No structural comparison (dimensions / measures / filters not checked)
- No JSON parse rate (dbt SL syntax is SQL string, not JSON)
- Repeated 5 iterations, result is pass rate per question across runs

### Schema context (original)

For the **SL track**: calls `/semantic_layer.metrics()`, `/semantic_layer.dimensions(metrics=[...])`, `/semantic_layer.entities(metrics=[...])` and passes the resulting DataFrames (NAME + DESCRIPTION columns) as strings into the prompt.

For the **SQL track**: passes raw `ACME_small.ddl` text.

---

## 3. This Experiment (Cube)

### 3-1. Comparison Table

| Item | dbt SL (reference) | Cube (this) | Notes |
|---|---|---|---|
| Semantic model | `omg_semantics/*.yaml` | `model/cubes/acme/*.yml` + `acme_ops` view | ✅ aligned 1:1 |
| Query format | SQL-like string | JSON object | ⚠️ different format — JSON parse step added |
| Schema context | metrics + dimensions + entities (NAME + DESCRIPTION) via SL API | `acme_ops` view members (name + description) via `/meta` | ✅ equivalent intent |
| Schema delivery | stringified DataFrames in prompt | formatted text block in prompt | ⚠️ minor difference |
| Execution endpoint | dbt Cloud JDBC | Cube REST API `/load` | ⚠️ different |
| Gold source | `.ttl` RDF ontology → SPARQL | `acme_questions.md` (manually authored) | ⚠️ different |
| LLM model | GPT-4 | GPT-4o | ⚠️ different model |
| Temperature | 0.3 | 0.3 | ✅ same |
| Iterations | 5 | 5 | ✅ same |
| Questions | 11 English (same set) | 11 English (same set) | ✅ same |
| SQL comparison track | ✅ (parallel SQL track) | ❌ not included | ⚠️ not replicated |

### 3-2. Evaluation Metrics Comparison

| Metric | dbt SL (reference) | Cube (this) | Notes |
|---|---|---|---|
| **Execution accuracy** (`is_result_equivalent`) | ✅ exact DataFrame match | ✅ Soft Result F1 (partial credit) | ⚠️ original is binary; this is more lenient |
| **JSON parse rate** | ❌ not applicable (SQL string) | ✅ added | new — required for JSON output |
| **Execution success rate** | implicit (failed queries → False) | ✅ explicit column | ✅ equivalent |
| **Structural accuracy** (dim/msr/filter) | ❌ not in original | ✅ added (F1) | new — enables failure diagnosis |
| **LLM-as-Judge** | ❌ not in original | ✅ added for edge cases | new |

**Key difference**: the original uses **strict exact match** (`DataFrame.equals()`). This experiment uses **Soft Result F1** (row-set intersection / union), which gives partial credit. To align with the original, use `result_f1 == 1.0` as the equivalent of `is_result_equivalent = True`.

### 3-2. Semantic Model Alignment

Cube models are aligned 1:1 with `omg_semantics`:

| omg_semantics | Cube cube | Public surface (acme_ops view) |
|---|---|---|
| `claim.yaml` | `acme_claim` | `claim_count`, `avg_days_to_settle`, `company_claim_number` |
| `claim_amount.yaml` | `acme_claim_amount` | `total_claim_amount`, `loss_payment_amount`, `loss_reserve_amount`, `total_loss_amount` |
| `loss_payment.yaml` | `acme_loss_payment` | _(filter via `has_loss_payment`)_ |
| `loss_reserve.yaml` | `acme_loss_reserve` | _(filter via `has_loss_reserve`)_ |
| `expense_payment.yaml` | `acme_expense_payment` | — (not a metric in reference) |
| `expense_reserve.yaml` | `acme_expense_reserve` | — (not a metric in reference) |
| `policy.yaml` | `acme_policy` | `policy_number`, `policy_count` |
| `policy_amount.yaml` | `acme_policy_amount` | `total_policy_amount` |
| `premium.yaml` | `acme_premium` | `has_premium` |
| `agreement_party_role.yaml` | `acme_agreement_party_role` | `party_identifier`, `party_role_code`, `policy_count_by_agent` |
| `catastrophe.yaml` | `acme_catastrophe` | `catastrophe_type_code` |
| `claim_coverage.yaml` | `acme_claim_coverage` | _(join bridge)_ |
| `policy_coverage_detail.yaml` | `acme_policy_coverage_detail` | _(join bridge)_ |

---

## 4. Environment

### 4-1. Infrastructure

```
[Local]
  └── ssh dev_mcp
        ├── ~/heartcube/              ← Cube project (git: heartcube-1.6.25)
        │   ├── model/cubes/acme/     ← acme_* cubes (public: false)
        │   ├── model/views/          ← acme_ops (public: true)
        │   ├── acme_questions.md     ← 11 gold queries
        │   └── acme_benchmark_pipeline.py
        │
        ├── Docker: heartcube container
        │   ├── Cube server (port 4000, internal only)
        │   └── Connected to PostgreSQL 20.0.1.10:5432
        │
        └── PostgreSQL: sampledb.oda_benchmark
            └── 13 acme_* tables (data loaded)
```

### 4-2. Current State (Already Done)

- [x] 13 ACME tables created in `oda_benchmark` schema
- [x] CSV data loaded into all tables
- [x] Cube models created (`model/cubes/acme/*.yml`)
- [x] `acme_ops` view created (`model/views/acme_ops.yml`)
- [x] Cube compiles without errors — all 14 cubes loaded
- [x] 11 gold queries validated (all return results)
- [x] `acme_benchmark_pipeline.py` written on dev_mcp
- [x] Cube container IP confirmed: `172.20.0.3:4000`

---

## 5. Benchmark Questions

11 questions matching the original dbt SL benchmark (`selected_challenges`), with Cube JSON gold queries.

File: `dev_mcp:~/heartcube/acme_questions.md`

### HQLS — Simple Aggregations (6)

| # | Question | Key members |
|---|---|---|
| 1 | How many claims do we have? | `claim_count` |
| 2 | How many policies do we have? | `policy_count` |
| 3 | How many claims have been placed by policy number? | `policy_number`, `claim_count` |
| 4 | How many policies have agents sold by agent id? | `party_identifier`, `policy_count_by_agent`, filter `AG` |
| 5 | What is the total amount of premiums paid by policy number? | `policy_number`, `total_policy_amount`, filter `has_premium=1` |
| 6 | What is the average time to settle a claim by policy number? | `policy_number`, `avg_days_to_settle` |

### HQHS — Complex Aggregations (5)

| # | Question | Key members |
|---|---|---|
| 7 | Total loss amounts (loss payment + loss reserve) by claim number? | `company_claim_number`, `total_loss_amount` |
| 8 | Total premiums paid by policy holder? | `party_identifier`, `total_policy_amount`, filter `has_premium=1` + `PH` |
| 9 | Total premiums paid by policy holder by policy number? | `policy_number`, `party_identifier`, `total_policy_amount`, filter `has_premium=1` + `PH` |
| 10 | How many policies does each policy holder have? | `party_identifier`, `policy_count`, filter `PH` |
| 11 | Average policy size (total premium / number of policies)? | `total_policy_amount`, `policy_count`, filter `has_premium=1` |

---

## 6. Evaluation Methodology

### 6-1. Prompt Design

```
[System]
You are a Cube Semantic Layer expert.
Convert the natural language question into a Cube REST API JSON query.
Output only the raw JSON object.

[Few-shot examples]
3 examples showing dimension/measure/filter usage with acme_ops.* prefix

[Schema context]
## acme_ops
dimensions: acme_ops.company_claim_number, acme_ops.policy_number, ...
            (name — description)
measures:   acme_ops.claim_count, acme_ops.total_policy_amount, ...
            (name — description)

[Question]
{natural language question}
```

Key design decisions:
- Schema context = `acme_ops` view only (mirrors dbt SL single-surface approach)
- Include `description` field from `/meta` for each member
- Prompt in English to match original benchmark language

### 6-2. Metrics

| Metric | Description |
|---|---|
| **JSON Parse Rate** | % of LLM outputs that are valid JSON |
| **Execution Success Rate** | % of generated queries that run without error on Cube |
| **Dimension F1** | F1 score comparing gold vs generated dimension sets |
| **Measure F1** | F1 score comparing gold vs generated measure sets |
| **Filter F1** | F1 score comparing gold vs generated filter member sets |
| **Soft Result F1** | F1 score on result row sets (float-normalized) |
| **LLM-as-Judge** | GPT-4o pass/fail for edge cases where result F1 is partial |

### 6-3. Scoring Flow

```
Question → LLM → generated query
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   execute generated          execute gold
         │                       │
         └───────────┬───────────┘
                     ▼
              compare results
         → Structural F1 + Result F1
         → LLM-as-Judge if 0 < Result F1 < 0.9
```

---

## 7. Running the Benchmark

### Prerequisites

```bash
ssh dev_mcp
cd ~/heartcube

# Check Cube is running
docker exec heartcube node -e "
const http = require('http');
http.request({hostname:'localhost',port:4000,path:'/cubejs-api/v1/meta',
  headers:{'Authorization':'Bearer dev_token'}}, res => {
  let d=''; res.on('data',c=>d+=c);
  res.on('end',()=>console.log('cubes:', JSON.parse(d).cubes.length));
}).end();"

# Set OpenAI key
export OPENAI_API_KEY="sk-..."
```

### Run

```bash
source venv/bin/activate
python3 acme_benchmark_pipeline.py
```

Expected runtime: ~15 min (11 questions × 5 iterations × ~15s/call)

### Output

```
acme_benchmark_results.csv
```

| Column | Description |
|---|---|
| iteration | 1–5 |
| category | HQLS / HQHS |
| question | Natural language question |
| json_parse_ok | 1/0 |
| exec_ok | 1/0 |
| gold_exec_ok | 1/0 |
| dim_f1 | 0–1 |
| msr_f1 | 0–1 |
| filter_f1 | 0–1 |
| result_f1 | 0–1 |
| llm_judge | 1/0/-1 |
| gen_query | Generated JSON |
| gold_query | Gold JSON |

---

## 8. Remaining Tasks

| Task | Status |
|---|---|
| Set OPENAI_API_KEY on dev_mcp | Pending |
| Add `description` fields to `acme_ops` view members | Pending |
| Update `build_schema_context` to include descriptions | Pending |
| Run benchmark (5 iterations × 11 questions) | Pending |
| Compare results with dbt SL reference results | Pending |

---

## 9. References

- Original benchmark: `hex_notebook/Semantic Layer LLM Benchmarking.yaml`
- Reference semantic models: `semantic-layer-llm-benchmarking/models/omg_semantics/`
- Gold queries: `dev_mcp:~/heartcube/acme_questions.md`
- Pipeline: `dev_mcp:~/heartcube/acme_benchmark_pipeline.py`
- Results (reference): `hex_notebook/results_pt*.csv`
