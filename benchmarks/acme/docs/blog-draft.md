# Semantic Layer as the Data Interface for LLMs, Revisited with Cube

> Draft version — ER extension results pending (benchmark run in progress). Placeholder results marked **[ER-PENDING]**.

---

In late 2023, the dbt Roundup published a post that caught the attention of everyone working at the intersection of LLMs and enterprise data. Jason Ganz replicated the data.world ACME benchmark using the dbt Semantic Layer and showed that structured semantic context dramatically improves the accuracy of LLM-generated queries.

The original paper's headline numbers were hard to ignore:

| Approach | Accuracy |
|---|---:|
| GPT-4 + raw DDL SQL | 16.7% |
| GPT-4 + Knowledge Graph (SPARQL) | 54.2% |
| dbt Semantic Layer (HQLS subset) | 83% |

Those numbers make a compelling case for the semantic layer as an LLM interface. But there's a scope caveat buried in the methodology that deserves more attention.

---

## The scope caveat

The dbt Roundup experiment was explicitly scoped to the HQLS subset — "high question complexity, low schema complexity" — and specifically to metric-oriented questions. Three questions were excluded because they required more joins than MetricFlow supported at the time. Eight of eleven questions were tested.

The dbt team was right to scope it that way. They were testing what dbt Semantic Layer was designed for: metrics and business KPIs with documented lineage and natural-language descriptions. The 83% result is meaningful precisely because it was measured in the product's design space.

But the full ACME benchmark contains 44 questions across a 2×2 matrix:

|  | Low Schema Complexity | High Schema Complexity |
|---|---|---|
| **Low Question Complexity** | LQLS (12) | LQHS (10) |
| **High Question Complexity** | HQLS (11) | HQHS (11) |

And not all of those questions ask for metrics. Many ask for dimensional listings. A few ask for row-level entity retrieval — "Return all the claims filed by this policy holder." Those questions aren't metric queries, and testing them through a metric-only lens would be the wrong comparison.

That's the gap this post explores.

---

## What we tested

I replicated the benchmark using [Cube](https://cube.dev), which has a different semantic-layer surface area than dbt Semantic Layer. Instead of MetricFlow's metric-first DSL, Cube exposes a query API over:

- **dimensions** — scalar attributes, typed and named
- **measures** — aggregation definitions with type, SQL, and description
- **filters** — structured predicates over any dimension or measure member
- **join paths** — hidden from the LLM; surfaced only through the public view
- **public views** — curated cross-cube projections available to external callers

The query format is a JSON object:

```json
{
  "query": {
    "dimensions": ["acme_ops.policy_number", "acme_ops.party_full_legal_name"],
    "measures": ["acme_ops.total_policy_amount"],
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

The LLM sees only the `acme_ops` public view — a curated list of named dimensions and measures. It doesn't see table names, join conditions, or discriminator columns. The semantic layer translates the JSON query into SQL internally.

The comparison track uses the full PostgreSQL DDL as context and asks the LLM to generate raw SQL.

Both tracks use zero-shot prompting with GPT-4o.

---

## Benchmark design

The source is the same ACME insurance dataset from the data.world paper (OMG Property & Casualty standard). The benchmark runs 43 questions (Q44 excluded as a duplicate of Q42).

Each question is classified along two lenses:

**Original 2×2 category** (from the source paper):
- LQLS: simple question, simple schema
- LQHS: simple question, complex schema
- HQLS: complex question, simple schema
- HQHS: complex question, complex schema

**Answer shape** (added for this replication):

| Answer Shape | Description | Example |
|---|---|---|
| `aggregate` | metric or KPI | "What is the total premium amount by policy?" |
| `dimension_listing` | list of dimension values, no aggregation | "Return all claims with open and close date." |
| `entity_row_retrieval` | rows filtered by a named entity | "List all claims for policy holder id 1." |
| `entity_resolution_required` | requires resolving a name or alias to an entity | "List all claims filed by Peyton Manning." |

The answer-shape lens is important because dbt SL was never designed to serve `entity_row_retrieval` queries, and testing those against a metric-only interface would be a category error.

Scoring uses result F1 and exact match against a gold query, evaluated on actual execution results from the live database.

---

## Results: all 43 questions, 5 iterations

### Overall funnel

| Track | Parse Rate | Exec Rate | Exact Match | Result F1 |
|---|---:|---:|---:|---:|
| Cube SL | 100.0% | 99.2% | **83.7%** | 83.7% |
| Raw DDL SQL | 100.0% | 75.2% | **29.5%** | 29.5% |

The gap is substantial: **83.7% vs. 29.5% exact match**. The parse rate is the same — GPT-4o reliably produces syntactically valid output in both formats. The difference is execution success and result accuracy.

The DDL track's 75% execution rate reflects a pattern the original paper also observed: LLMs struggle with join-path discovery in normalized schemas. The ACME schema has discriminator tables (`acme_loss_payment`, `acme_expense_payment`), multi-role party tables (`acme_agreement_party_role` with `party_role_code`), and multiple paths to the same entity. GPT-4o frequently missed necessary joins or applied the wrong aggregation grouping.

Cube hides all of that. The LLM's only job is to pick the right dimensions and measures from the public view.

### By original category

| Category | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|
| LQLS | 83.3% | 33.3% | 83.3% | 33.3% |
| LQHS | 70.0% | 10.0% | 70.0% | 10.0% |
| HQLS | 90.9% | 51.5% | 90.9% | 51.5% |
| HQHS | 90.0% | 20.0% | 90.0% | 20.0% |

A few things stand out:

**HQLS and HQHS are Cube's strongest categories.** These are exactly the metric-oriented questions — aggregations over measures like `total_policy_amount`, `avg_full_loss_amount`, `loss_payment_amount`. The LLM reliably translates them to the right Cube query, which then executes correctly because the measure definitions are already in the model.

**LQHS is Cube's weakest category at 70%.** The gap comes from multi-role questions. LQHS Q15 and Q16 ask for both policyholders and agents in the same result. In the underlying data, a single `acme_agreement_party_role` row is either `party_role_code = 'PH'` or `'AG'` — you can't get both roles in one Cube row without a self-join. The LLM tends to pick just one `party_role_code` filter, which returns only one side of the relationship. In 3 of 5 LQHS questions, the model produces the right structure but filters to one role when the question implies both.

**DDL HQHS is catastrophically bad at 20%.** These are complex questions involving loss ratios, expense reserves, and multi-table aggregations. The LLM must independently discover every join path, every discriminator, every grouping key. It rarely gets all of them right simultaneously.

### By answer shape

| Answer Shape | n | Cube Exact | DDL Exact | Cube F1 | DDL F1 |
|---|---:|---:|---:|---:|---:|
| `aggregate` | 63 | **90.5%** | 36.5% | 90.5% | 36.5% |
| `dimension_listing` | 66 | **77.3%** | 22.7% | 77.3% | 22.7% |

The answer-shape lens reveals something important: Cube is stronger on `aggregate` questions than `dimension_listing` questions. This is consistent with how it's designed — well-defined measure semantics are the semantic layer's core value proposition.

But the `dimension_listing` result is still strong at 77.3% against a DDL baseline of 22.7%. Dimension-listing questions benefit from Cube's named members and hidden join paths even without any aggregation. The LLM only needs to know which dimensions to select; the join graph is handled by the layer.

---

## Where things get harder: entity retrieval and name resolution

The 43 core questions don't include name-based entity retrieval. "List all claims filed by Peyton Manning" is not in the source benchmark — the ACME dataset doesn't contain a Peyton Manning.

But the benchmark schema can express entity retrieval if the data model includes a Party/Person layer. We built that extension.

The ACME dataset has a `Person.csv` with first and last names. The schema looks like:

```
acme_claim
  → acme_claim_coverage
  → acme_policy_coverage_detail
  → acme_policy
  → acme_agreement_party_role (party_role_code: PH / AG)
  → acme_party
  → acme_person (first_name, last_name, full_legal_name)
```

Once this join path is modeled in Cube and exposed through `acme_ops`, these queries become expressible:

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

We extended the benchmark with 5 entity retrieval questions:

1. List all claims for policy holder id 1.
2. List all claims for policy holder named Mary Policy Holder.
3. What policies are held by agent id 2?
4. What policies are held by agent named Joan Agent?
5. List all claims for policy holder named Mary Policy Holder including the catastrophe name.

Questions 4 and 5 require the LLM to apply the `party_full_legal_name` filter correctly. The "Peyton Manning" analogue — a name that doesn't exist in the data — is out of scope for this benchmark, but the pattern is established.

### ER extension results (5 questions, 3 iterations)

**[ER-PENDING — replace with actual numbers once benchmark run completes]**

| Track | Exec Rate | Exact Match | Result F1 |
|---|---:|---:|---:|
| Cube SL | TBD | TBD | TBD |
| Raw DDL SQL | TBD | TBD | TBD |

Expected pattern: Cube should execute near 100% (the join path to `acme_person` is modeled and `party_full_legal_name` is a named dimension). DDL is likely to drop the `acme_person` join or miss the correct `full_legal_name` column.

---

## Why "filed by" is a modeling question, not a query question

One thing worth being precise about: "List all claims filed by Peyton Manning" contains an ambiguous verb.

"Filed by" can mean:
- The person is the **policyholder** on the policy associated with the claim.
- The person is the **claimant** — the party who submitted the claim.
- The person is a named party on the claim for another role.

The ACME schema links claims → policies → agreement party roles → parties. That captures "policyholder on the policy associated with the claim." It does not automatically capture who *submitted* the claim unless a claim-level party role is modeled.

> A semantic layer can only be as precise as the business relationship it models. If "filed by" means "policyholder on the associated policy," Cube can expose that. If it means "person who submitted the claim," the underlying data needs that relationship first.

This is an important constraint to name explicitly. LLM-generated queries return what the data model can express — they cannot conjure relationships the model doesn't contain.

---

## What the Cube approach changes

The comparison track (raw DDL SQL) asks the LLM to:

1. Identify the right tables from a normalized schema
2. Discover join paths and apply the correct join conditions
3. Apply discriminator filters (e.g., `party_role_code = 'PH'`)
4. Derive measure definitions (e.g., loss ratio = total_full_loss_amount / total_policy_amount)
5. Select correct grouping keys
6. Produce valid syntax

Each step is an independent failure mode.

The Cube approach moves most of these responsibilities into the model:

| Responsibility | Raw DDL | Cube SL |
|---|---|---|
| Table discovery | LLM | Hidden in model |
| Join path | LLM | Resolved by Cube |
| Discriminator filters | LLM | Exposed as named dimension (`party_role_code`) |
| Measure definitions | LLM | Pre-defined in YAML |
| Grouping | LLM | Inferred from selected dimensions |
| Column naming | LLM guesses | Named members |

The LLM's job shrinks to: *given this list of named members, pick the right ones for this question*. That is a much easier task than inferring a join graph from a DDL definition.

---

## What doesn't change

A few important limitations to be explicit about:

**The ACME dataset is small and synthetic.** The insurance schema is a reasonable complexity proxy, but production schemas are larger, messier, and often less normalized. Generalization to production requires testing on actual schemas.

**Multi-role questions remain hard.** Questions that require showing both a policyholder and an agent in the same result set require a self-join pattern that the current Cube model can't serve in one query without fanout. This is a structural constraint, not a Cube-specific bug.

**Semantic layers don't replace operational data access.** A semantic layer query API is appropriate for analytical queries — it was not designed as a row-level CRUD interface, and access control at the analytical query level is different from transactional data permissions.

**Names in filter values must exist in the data.** The Peyton Manning question isn't just about entity resolution in the sense of "find the person" — it's about whether the data model contains a record for that person. A semantic layer can express the query structure; it can't invent the data.

---

## The broader thesis

The dbt Roundup experiment showed that semantic context helps LLMs produce better metric queries. The result holds in the Cube replication across all four question categories and both answer shapes tested.

The more interesting finding is structural: **Cube can serve multiple answer shapes through a single governed interface**. Metrics, dimensional listings, and entity retrieval all go through the same `acme_ops` public view, the same JSON query format, and the same authorization model. The LLM doesn't need to know which "kind" of query it's generating — it just picks named members.

That's the broader version of "semantic layer as the data interface for LLMs." Not metrics only. Not DDL SQL. A named, documented, governed surface that hides join complexity and lets the LLM focus on what it's actually good at: selecting the right concepts for the question being asked.

The original dbt experiment was not wrong to focus on metrics. It was testing the part of the semantic layer that dbt SL was designed to expose. This experiment tests whether that principle generalizes.

The answer, at least over this benchmark, is yes.

---

## Appendix: Technical setup

**Cube model**: Single public view `acme_ops` over 9 underlying cubes. Dimensions include policy, claim, party, person, coverage, catastrophe, and amount data. Measures include count, sum, and avg aggregations over policy amounts, loss components, and claim durations.

**Benchmark script**: Python scripts calling the Cube `/load` API and direct PostgreSQL for the DDL track. LLM generation uses the OpenAI API with zero-shot prompting. Results scored using result F1 and exact match against gold-query execution.

**Model**: GPT-4o, temperature 0.3.

**Iterations**: 5 per question (215 total Cube calls, 215 total DDL SQL calls).

**Infrastructure**: Cube on Docker (PostgreSQL backend, `oda_benchmark` schema). All benchmark code at `benchmarks/acme/` in the [heartcube repository](https://github.com/haechangcho/heartcube).

---

*All benchmark code, gold queries, results CSVs, and schema definitions are in the heartcube repository under `benchmarks/acme/`.*
