# Article Outline: Cube Semantic Layer As The Data Interface For LLMs

## Working Title Options

1. Semantic Layer as the Data Interface for LLMs, Revisited with Cube
2. Beyond Metrics: Testing Cube as an LLM Data Interface
3. Can a Semantic Layer Answer Both Metrics and Row-Level Questions?
4. Cube, LLMs, and the Missing Half of Semantic Layer Benchmarks

## Core Thesis

The dbt Roundup experiment showed that semantic context can help LLMs produce better metric queries. A Cube-based replication can test a broader claim:

> A semantic layer can be a governed interface not only for metrics, but also for dimensional and selected row-level analytical retrieval.

This is where Cube can add something new to the conversation. Cube exposes a query API over dimensions, measures, filters, joins, and public views. That makes it possible to compare metric-style questions and non-aggregate retrieval questions within one governed interface.

## Article Positioning

This should not be framed as "Cube beats dbt." A stronger and more credible framing is:

- The dbt Roundup experiment was intentionally scoped to metric-friendly questions.
- That was the right scope for dbt Semantic Layer at the time.
- Cube has a different semantic-layer surface area.
- Therefore, Cube lets us ask a broader benchmark question.

Recommended phrasing:

> The original dbt experiment was not wrong to focus on metrics. It was testing the part of the semantic layer that dbt SL was designed to expose. But if we treat "semantic layer as the LLM data interface" seriously, we also need to test questions whose answer shape is not a metric.

## Narrative Structure

### 1. Open With The Existing Benchmark Story

Summarize:

- data.world paper compared SQL from DDL vs SPARQL from knowledge graph.
- Knowledge graph context improved LLM query accuracy.
- dbt Roundup replicated the idea with dbt Semantic Layer.
- dbt focused on the HQLS subset because those were closest to metric questions.

Key point:

> The dbt experiment was a semantic-layer-for-metrics experiment, not a semantic-layer-for-all-data-access experiment.

### 2. Explain The Limitation In Plain Terms

Use the "Peyton Manning" example.

Question:

```text
List all the claims that were filed by Peyton Manning.
```

Why this matters:

- It is not asking for a metric.
- It is asking for entity resolution plus row retrieval.
- A metric-only semantic interface has no natural way to express it.

Important nuance:

> This is not a failure of the semantic layer. It is a mismatch between the question's answer shape and the interface being tested.

### 3. Introduce Cube's Different Surface Area

Cube can expose:

- dimensions
- measures
- filters
- time dimensions
- public views
- join paths
- query-time ordering and limits
- dimension-only result sets

Explain with a simple contrast:

Metric-style query:

```json
{
  "query": {
    "dimensions": ["acme_ops.policy_number"],
    "measures": ["acme_ops.claim_count"]
  }
}
```

Dimension-listing query:

```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.claim_close_date"
    ]
  }
}
```

Entity-filtered retrieval:

```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.policy_number",
      "acme_ops.party_full_legal_name"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": ["PH"]
      },
      {
        "member": "acme_ops.party_full_legal_name",
        "operator": "equals",
        "values": ["Mary Policy Holder"]
      }
    ]
  }
}
```

### 4. Define The Benchmark Expansion

Original 2x2:

| | Low Schema Complexity | High Schema Complexity |
|---|---|---|
| Low Question Complexity | LQLS | LQHS |
| High Question Complexity | HQLS | HQHS |

dbt Roundup focus:

```text
HQLS subset
```

Cube benchmark target:

```text
All 44 source questions, excluding duplicate Q44 before execution
```

Add a second lens:

| Answer Shape | Meaning |
|---|---|
| aggregate | metric or KPI answer |
| dimension_listing | non-metric list of dimension values |
| entity_row_retrieval | rows filtered by business entity |
| entity_resolution_required | name/alias must be resolved to an entity |

### 5. Show What Works Today

Use the current `acme_ops` model.

Currently answerable non-aggregate examples:

```text
Return all the claims we have by claim number, open date and close date.
Return all the policies and their policy holder by id.
Return all the policies and the agents that sold them by policy number and agent id.
Return policy holders and the claims they have made and the corresponding catastrophe.
```

Example Cube query:

```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": ["PH"]
      }
    ]
  }
}
```

### 6. Show What Requires More Modeling

Name-based lookup requires Party/Person modeling.

Current blocker:

- `acme_ops` exposes `party_identifier`, not `party_full_legal_name`.
- Source `Person.csv` has names, but the current Cube model does not expose them.
- Peyton Manning does not exist in the source data.

Needed model expansion:

```text
acme_claim
  -> acme_claim_coverage
  -> acme_policy_coverage_detail
  -> acme_policy
  -> acme_agreement_party_role
  -> acme_party
  -> acme_person
```

Then this becomes expressible:

```text
List all claims for policy holder named Mary Policy Holder.
```

### 7. Be Precise About "Filed By"

This section is important for credibility.

"Filed by Peyton Manning" can mean different things:

- Peyton Manning is the policyholder.
- Peyton Manning is the claimant.
- Peyton Manning submitted the claim.
- Peyton Manning is a party related to the claim through another role.

The ACME data currently links claims to policies, and policies to parties through agreement party roles. That supports:

```text
claims associated with policies held by Peyton Manning
```

It does not automatically prove:

```text
claims filed by Peyton Manning
```

unless "filed by" is explicitly modeled that way.

Suggested wording:

> A semantic layer can only be as precise as the business relationship it models. If "filed by" means "policyholder on the policy associated with the claim," Cube can expose that. If it means "person who submitted the claim," the underlying data needs that relationship.

### 8. Compare Against Raw DDL SQL

The raw DDL path asks the LLM to infer:

- table names
- join paths
- role filters
- measure definitions
- entity names
- grouping behavior

The Cube path gives the LLM:

- a smaller public surface
- named dimensions/measures
- documented role filters
- hidden join paths
- stable query syntax

Expected hypothesis:

> Cube should reduce failures caused by join-path discovery, especially in LQHS/HQHS questions.

### 9. Results Section Template

Use this structure after running:

#### Overall

| Track | Parse Rate | Exec Rate | Exact Match | Result F1 |
|---|---:|---:|---:|---:|
| Cube SL | TBD | TBD | TBD | TBD |
| Raw DDL SQL | TBD | TBD | TBD | TBD |

#### By Original Category

| Category | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|
| LQLS | TBD | TBD | TBD | TBD |
| LQHS | TBD | TBD | TBD | TBD |
| HQLS | TBD | TBD | TBD | TBD |
| HQHS | TBD | TBD | TBD | TBD |

#### By Answer Shape

| Answer Shape | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|
| aggregate | TBD | TBD | TBD | TBD |
| dimension_listing | TBD | TBD | TBD | TBD |
| entity_row_retrieval | TBD | TBD | TBD | TBD |

### 10. Caveats

Include these explicitly:

- The ACME dataset is small and synthetic.
- Source questions include duplicates and typos.
- Some "row-level" questions return distinct dimension combinations, not necessarily physical rows.
- Name-based retrieval requires modeled Party/Person entities.
- "Filed by" semantics must be defined before evaluation.
- Semantic layers do not replace operational APIs or document stores.
- Access control and PII masking are essential for production row retrieval.

### 11. Conclusion

Recommended conclusion:

> The interesting result is not just whether Cube improves accuracy over raw SQL. The more important finding is whether a semantic layer can provide a single governed interface for multiple answer shapes: metrics, dimensional listings, and selected entity-level retrieval. That is the broader version of "semantic layer as the data interface for LLMs."

## Suggested Visuals

1. Benchmark scope diagram:

```text
data.world paper: DDL SQL vs Knowledge Graph
dbt Roundup: HQLS metric subset
Cube benchmark: full 2x2 + answer shape lens
```

2. Join path diagram:

```text
Claim -> Claim Coverage -> Policy Coverage Detail -> Policy
      -> Agreement Party Role -> Party -> Person
```

3. Query surface contrast:

```text
Raw DDL prompt: many tables + implicit joins
Cube prompt: acme_ops dimensions/measures + documented filters
```

4. Answer shape table:

```text
aggregate vs dimension_listing vs entity_row_retrieval
```

## Draft Abstract

In 2023, the dbt Roundup replicated a knowledge-graph benchmark using the dbt Semantic Layer and showed promising results for metric-oriented business questions. I wanted to revisit the same ACME insurance benchmark using Cube, but with a broader question: can a semantic layer serve as the LLM's data interface beyond metrics? Cube exposes dimensions, measures, filters, and governed public views through a query API, which makes it possible to test not only aggregate questions, but also dimensional listings and selected row-level retrieval patterns. This post walks through the benchmark design, where Cube helps, where raw DDL SQL fails, and why questions like "List all claims filed by Peyton Manning" are really tests of entity modeling, not just SQL generation.
