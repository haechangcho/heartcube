# ACME Cube Benchmark Planning Direction

## Purpose

This benchmark should not only replicate the dbt Roundup experiment on Cube. It should also expand the scope to answer a broader question:

> Can a semantic layer serve as the governed interface for both aggregate metrics and selected row-level analytical retrieval?

The dbt Roundup article focused on the HQLS subset because those questions are closest to metric-oriented semantic layer usage. This Cube benchmark should use the full ACME benchmark shape and explicitly include non-aggregate retrieval intent.

## Source Baseline

Source repository:

```text
/Users/hc.cho/Projects/semantic-layer-llm-benchmarking
```

Key source files:

```text
benchmark_questions.md
ACME_Insurance/DDL/ACME_small.ddl
ACME_Insurance/data/*.csv
ACME_Insurance/investigation/acme-benchmark.ttl
models/omg_semantics/*.yaml
```

The benchmark package snapshots source files under:

```text
benchmarks/acme/source/
```

## Benchmark Scope

The source benchmark contains 44 questions:

| Category | Meaning | Count |
|---|---|---:|
| LQLS | low question complexity, low schema complexity | 12 |
| LQHS | low question complexity, high schema complexity | 10 |
| HQLS | high question complexity, low schema complexity | 11 |
| HQHS | high question complexity, high schema complexity | 11 |

Q44 duplicates Q42 and is excluded before execution. The executable target is 43 questions.

## Why The Scope Changes

The dbt Roundup replication intentionally focused on HQLS. That was a reasonable fit for dbt Semantic Layer because MetricFlow/dbt SL was primarily metric-oriented at the time.

Cube has a broader query surface:

- dimensions
- measures
- filters
- ordering and limits
- joined public views
- drilldown-style query paths
- potential row-level/dimension-only retrieval patterns

Therefore the Cube article should not stop at HQLS. It should test:

- aggregate metric questions
- multi-hop aggregate questions
- dimension listing questions
- entity-filtered row retrieval questions

## Answer Shape Taxonomy

Add an answer-shape lens on top of the original 2x2 benchmark.

| Answer Shape | Description | Example |
|---|---|---|
| `aggregate` | Returns measures grouped by dimensions or scalar KPIs | How many claims by policy number? |
| `dimension_listing` | Returns selected dimensions without metric intent | Return all claims by claim number, open date, close date |
| `entity_row_retrieval` | Returns rows filtered by a business entity | List all claims for policy holder Mary Policy Holder |
| `entity_resolution_required` | Requires resolving a name or alias to an entity ID | List all claims filed by Peyton Manning |

The manifest should eventually include:

```yaml
answer_shape: aggregate | dimension_listing | entity_row_retrieval
requires_entity_resolution: true | false
```

## Current Cube Capability

Currently possible with `acme_ops`:

- claim listing by claim number and dates
- policy and claim listing
- policyholder/agent lookup by `party_identifier`
- policyholder/agent filtered query via `party_role_code`
- catastrophe lookup through the claim path
- loss/premium aggregate measures

Not currently possible:

- policyholder lookup by person name
- agent lookup by person name
- Peyton Manning style lookup
- precise "filed by" semantics if the data only links claim to policyholder indirectly

The blocker is not Cube's query model. The blocker is missing semantic model coverage for `Party` and `Person`.

## Raw Row Retrieval Position

Cube can represent dimension-only and entity-filtered analytical retrieval if the model exposes the right dimensions and joins. This is different from a metric-only interface.

However, this must be described carefully:

- Cube does not magically infer unmodeled relationships.
- A semantic layer still needs a modeled join path.
- "Filed by" must be defined: policyholder, claimant, submitter, or another role.
- PII and row-level access control matter for person-level queries.
- Operational document retrieval remains outside the semantic layer's core job.

Recommended wording:

> Cube can model selected row-level analytical retrieval patterns, but only when the entity, relationship, and access semantics are modeled explicitly.

## Model Expansion Plan

### 1. Add Party And Person Tables

DDL additions:

```sql
CREATE TABLE oda_benchmark.acme_party (
  party_identifier bigint NOT NULL,
  party_name character varying,
  begin_date timestamp,
  end_date timestamp,
  party_type_code character varying,
  PRIMARY KEY (party_identifier)
);

CREATE TABLE oda_benchmark.acme_person (
  person_identifier bigint NOT NULL,
  first_name character varying,
  middle_name character varying,
  last_name character varying,
  full_legal_name character varying,
  nickname character varying,
  suffix_name character varying,
  birth_date timestamp,
  birth_place_name character varying,
  gender_code character varying,
  prefix_name character varying,
  PRIMARY KEY (person_identifier)
);
```

Source CSVs:

```text
ACME_Insurance/data/Party.csv
ACME_Insurance/data/Person.csv
```

### 2. Add Cube Models

Add:

```text
model/cubes/acme_party.yml
model/cubes/acme_person.yml
```

Join path:

```text
acme_claim
  -> acme_claim_coverage
  -> acme_policy_coverage_detail
  -> acme_policy
  -> acme_agreement_party_role
  -> acme_party
  -> acme_person
```

### 3. Expose Person Dimensions In `acme_ops`

Expose:

- `party_identifier`
- `party_role_code`
- `party_name`
- `party_full_legal_name`
- `party_first_name`
- `party_last_name`

Use role filters to distinguish:

- `party_role_code = 'PH'`: policyholder
- `party_role_code = 'AG'`: agent

### 4. Add Row-Level Benchmark Extension

Add a separate extension file:

```text
benchmarks/acme/questions/entity_retrieval_questions.md
```

Candidate questions:

1. List all claims for policy holder id 1.
2. List all claims for policy holder named Mary Policy Holder.
3. List all policies sold by agent named Bob Insurance Agent.
4. List all claims connected to policies sold by Bob Insurance Agent.
5. List all claims filed by Peyton Manning.

For Peyton Manning, decide one of two designs:

- Add Peyton Manning to seed data and link him to a policy as a policyholder.
- Keep him absent and define the correct answer as an empty result.

The second option tests entity grounding and "not found" behavior.

## Data Loading Plan

1. Add DDL to create `acme_party` and `acme_person`.
2. Add loader support for `Party.csv` and `Person.csv`.
3. Normalize CSV headers to snake_case.
4. Load into `oda_benchmark`.
5. Validate:

```sql
SELECT COUNT(*) FROM oda_benchmark.acme_party;
SELECT COUNT(*) FROM oda_benchmark.acme_person;
SELECT * FROM oda_benchmark.acme_person WHERE first_name IS NOT NULL LIMIT 5;
```

6. Validate join:

```sql
SELECT apr.party_role_code, p.first_name, p.middle_name, p.last_name, COUNT(*)
FROM oda_benchmark.acme_agreement_party_role apr
JOIN oda_benchmark.acme_person p
  ON apr.party_identifier = p.person_identifier
GROUP BY apr.party_role_code, p.first_name, p.middle_name, p.last_name;
```

## Benchmark Implementation Roadmap

1. Finish 43-question gold expansion for Cube and DDL.
2. Add answer-shape tags to `question_manifest.yaml`.
3. Add Party/Person DDL and data loading.
4. Add Cube models and view exposure for Party/Person.
5. Add entity retrieval extension questions.
6. Run Cube and DDL tracks separately.
7. Report results by:
   - original category
   - answer shape
   - schema complexity
   - entity resolution requirement

## Reporting Angle

The final report should separate three claims:

1. Cube can reproduce metric-style semantic layer benchmarking.
2. Cube can reduce multi-hop join complexity by exposing a governed public view.
3. Cube can support selected row-level analytical retrieval when entity models are exposed.

The third claim is the article differentiator.
