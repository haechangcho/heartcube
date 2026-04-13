# ACME Benchmark Schema Plan

## Background

ACME Insurance tables were initially planned under the `oda` schema (same as production).
This plan separates benchmark data into a dedicated schema to avoid mixing with production tables.

---

## Schema Naming

| Option | Pros | Cons |
|---|---|---|
| `oda_benchmark` | Clearly scoped under oda project | Implies oda-specific |
| `benchmark` | Generic, reusable for future benchmarks | Too broad |
| `acme` | Matches dataset name exactly | Hard to extend later |

**Decision: `oda_benchmark`**

- Scope is clear (benchmark data for oda project)
- Easy to extend (`oda_benchmark.acme_*`, `oda_benchmark.xyz_*`)
- Matches existing naming convention (`oda`, `oda_benchmark`)

---

## Target Structure

```
sampledb
├── oda               ← production (unchanged)
│   ├── fact_accident
│   ├── dim_*
│   └── ...
└── oda_benchmark     ← benchmark / test datasets (new)
    ├── acme_claim
    ├── acme_claim_amount
    ├── acme_loss_payment
    ├── acme_loss_reserve
    ├── acme_expense_payment
    ├── acme_expense_reserve
    ├── acme_policy
    ├── acme_policy_amount
    ├── acme_premium
    ├── acme_policy_coverage_detail
    ├── acme_claim_coverage
    ├── acme_agreement_party_role
    └── acme_catastrophe
```

---

## DBA Request

Current `abiuser` permissions:
- `oda` schema: SELECT, INSERT (no CREATE TABLE)
- `oda_benchmark` schema: does not exist yet

Required from DBA (`sampleuser`):

```sql
-- 1. Create schema
CREATE SCHEMA oda_benchmark;

-- 2. Create tables (13 total)
CREATE TABLE oda_benchmark.acme_claim (
    claim_identifier        INTEGER PRIMARY KEY,
    catastrophe_identifier  INTEGER,
    claim_description       VARCHAR(5000),
    claims_made_date        TIMESTAMP,
    company_claim_number    VARCHAR(20),
    company_subclaim_number VARCHAR(5),
    insurable_object_identifier INTEGER,
    occurrence_identifier   INTEGER,
    claim_open_date         TIMESTAMP,
    claim_close_date        TIMESTAMP,
    claim_reopen_date       TIMESTAMP,
    claim_status_code       VARCHAR(5),
    claim_reported_date     TIMESTAMP
);

CREATE TABLE oda_benchmark.acme_claim_amount (
    claim_amount_identifier BIGINT PRIMARY KEY,
    claim_identifier        INTEGER,
    claim_offer_identifier  INTEGER,
    amount_type_code        VARCHAR(20),
    event_date              TIMESTAMP,
    claim_amount            DECIMAL(15,2),
    insurance_type_code     CHAR(1)
);

CREATE TABLE oda_benchmark.acme_loss_payment (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda_benchmark.acme_loss_reserve (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda_benchmark.acme_expense_payment (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda_benchmark.acme_expense_reserve (
    claim_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda_benchmark.acme_policy (
    policy_identifier              INTEGER PRIMARY KEY,
    effective_date                 TIMESTAMP,
    expiration_date                TIMESTAMP,
    policy_number                  VARCHAR(50),
    status_code                    VARCHAR(20),
    geographic_location_identifier INTEGER
);

CREATE TABLE oda_benchmark.acme_policy_amount (
    policy_amount_identifier          BIGINT PRIMARY KEY,
    geographic_location_identifier    INTEGER,
    policy_identifier                 INTEGER,
    effective_date                    TIMESTAMP,
    amount_type_code                  VARCHAR(5),
    policy_coverage_detail_identifier INTEGER,
    policy_amount                     DECIMAL(15,2)
);

CREATE TABLE oda_benchmark.acme_premium (
    policy_amount_identifier BIGINT PRIMARY KEY
);

CREATE TABLE oda_benchmark.acme_policy_coverage_detail (
    policy_coverage_detail_identifier INTEGER,
    effective_date                    TIMESTAMP,
    coverage_identifier               INTEGER,
    insurable_object_identifier       INTEGER,
    policy_identifier                 INTEGER,
    coverage_part_code                VARCHAR(20),
    coverage_description              VARCHAR(2000),
    expiration_date                   TIMESTAMP
);

CREATE TABLE oda_benchmark.acme_claim_coverage (
    claim_identifier                  INTEGER,
    effective_date                    TIMESTAMP,
    policy_coverage_detail_identifier INTEGER
);

CREATE TABLE oda_benchmark.acme_agreement_party_role (
    agreement_identifier INTEGER,
    party_identifier     BIGINT,
    party_role_code      VARCHAR(20),
    effective_date       TIMESTAMP,
    expiration_date      TIMESTAMP
);

CREATE TABLE oda_benchmark.acme_catastrophe (
    catastrophe_identifier    INTEGER PRIMARY KEY,
    catastrophe_type_code     VARCHAR(20),
    catastrophe_name          VARCHAR(100),
    industry_catastrophe_code VARCHAR(20),
    company_catastrophe_code  VARCHAR(20)
);

-- 3. Grant abiuser access
GRANT USAGE ON SCHEMA oda_benchmark TO abiuser;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA oda_benchmark TO abiuser;
```

---

## Changes Required After Schema Creation

### 1. Cube model files (`model/cubes/acme_*.yml`)

`sql_table` in all 13 cube files: `oda.acme_*` → `oda_benchmark.acme_*`

```yaml
# before
sql_table: oda.acme_claim

# after
sql_table: oda_benchmark.acme_claim
```

### 2. Data load script (`acme_load_data.py`)

```python
# before
SCHEMA = "oda"

# after
SCHEMA = "oda_benchmark"
```

### 3. DB connection

No change needed. `abiuser` connects to the same `sampledb`, just accesses `oda_benchmark` schema instead of `oda`.

---

## Implementation Checklist

### DBA
- [ ] `CREATE SCHEMA oda_benchmark`
- [ ] Run DDL for 13 tables
- [ ] `GRANT USAGE ON SCHEMA oda_benchmark TO abiuser`
- [ ] `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA oda_benchmark TO abiuser`

### After DBA approval
- [ ] Update `sql_table` in `model/cubes/acme_*.yml` (13 files): `oda.` → `oda_benchmark.`
- [ ] Update `SCHEMA` in `acme_load_data.py`: `"oda"` → `"oda_benchmark"`
- [ ] Transfer CSV files to dev_mcp (`scp`)
- [ ] Run `acme_load_data.py`
- [ ] Verify row counts per table
- [ ] Confirm `acme_ops` appears in `/meta`
- [ ] Validate 11 gold queries via curl
- [ ] Run benchmark pipeline (5 iter × 11 questions = 55 runs)

---

## Data Size Reference

| Table | Rows | File Size |
|---|---|---|
| acme_agreement_party_role | 3 | 124B |
| acme_catastrophe | 3 | 165B |
| acme_claim | 1 | 388B |
| acme_claim_amount | 7 | 236B |
| acme_claim_coverage | 1 | 97B |
| acme_expense_payment | 1 | 29B |
| acme_expense_reserve | 1 | 29B |
| acme_loss_payment | 1 | 29B |
| acme_loss_reserve | 1 | 29B |
| acme_policy | 1 | 183B |
| acme_policy_amount | 11 | 635B |
| acme_policy_coverage_detail | 5 | 402B |
| acme_premium | 5 | 44B |
| **Total** | **41** | **~176KB** |
