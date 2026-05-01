# ACME Entity Retrieval Extension Questions

These questions extend the original ACME benchmark with row-level analytical retrieval intent. They are not part of the source 44-question denominator unless explicitly included in a separate extension run.

## ER — Entity Retrieval

1. List all claims for policy holder id 1.

```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date", "acme_ops.policy_number", "acme_ops.party_identifier"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}, {"member": "acme_ops.party_identifier", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

```sql
SELECT c.company_claim_number,
       c.claim_open_date,
       c.claim_close_date,
       p.policy_number,
       apr.party_identifier
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc
  ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd
  ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p
  ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr
  ON p.policy_identifier = apr.agreement_identifier
WHERE apr.party_role_code = 'PH'
  AND apr.party_identifier = 1
ORDER BY c.company_claim_number ASC
```

2. List all claims for policy holder named Mary Policy Holder.

```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date", "acme_ops.policy_number", "acme_ops.party_full_legal_name"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}, {"member": "acme_ops.party_full_legal_name", "operator": "equals", "values": ["Mary Policy Holder"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

```sql
SELECT c.company_claim_number,
       c.claim_open_date,
       c.claim_close_date,
       p.policy_number,
       COALESCE(NULLIF(person.full_legal_name, ''), TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) AS party_full_legal_name
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc
  ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd
  ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p
  ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr
  ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_person person
  ON apr.party_identifier = person.person_identifier
WHERE apr.party_role_code = 'PH'
  AND COALESCE(NULLIF(person.full_legal_name, ''), TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) = 'Mary Policy Holder'
ORDER BY c.company_claim_number ASC
```

3. List all policies sold by agent named Bob Insurance Agent.

```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.party_full_legal_name"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}, {"member": "acme_ops.party_full_legal_name", "operator": "equals", "values": ["Bob Insurance Agent"]}], "order": {"acme_ops.policy_number": "asc"}}}
```

```sql
SELECT p.policy_number,
       COALESCE(NULLIF(person.full_legal_name, ''), TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) AS party_full_legal_name
FROM oda_benchmark.acme_policy p
JOIN oda_benchmark.acme_agreement_party_role apr
  ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_person person
  ON apr.party_identifier = person.person_identifier
WHERE apr.party_role_code = 'AG'
  AND COALESCE(NULLIF(person.full_legal_name, ''), TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) = 'Bob Insurance Agent'
ORDER BY p.policy_number ASC
```

4. List all claims connected to policies sold by Bob Insurance Agent.

```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.policy_number", "acme_ops.party_full_legal_name"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}, {"member": "acme_ops.party_full_legal_name", "operator": "equals", "values": ["Bob Insurance Agent"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

```sql
SELECT c.company_claim_number,
       p.policy_number,
       COALESCE(NULLIF(person.full_legal_name, ''), TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) AS party_full_legal_name
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc
  ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd
  ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p
  ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr
  ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_person person
  ON apr.party_identifier = person.person_identifier
WHERE apr.party_role_code = 'AG'
  AND COALESCE(NULLIF(person.full_legal_name, ''), TRIM(CONCAT_WS(' ', person.first_name, person.middle_name, person.last_name))) = 'Bob Insurance Agent'
ORDER BY c.company_claim_number ASC
```
