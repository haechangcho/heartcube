# ACME Insurance — DDL SQL Benchmark Gold Queries

Schema: `oda_benchmark` (PostgreSQL)

## HQLS — Complex Queries on Simple Schema

1. How many claims do we have?
```sql
SELECT COUNT(company_claim_number) AS claim_count
FROM oda_benchmark.acme_claim
```

2. How many policies do we have?
```sql
SELECT COUNT(*) AS number_of_policies
FROM oda_benchmark.acme_policy
```

3. How many claims have been placed by policy number?
```sql
SELECT p.policy_number, COUNT(c.company_claim_number) AS claim_count
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY p.policy_number
ORDER BY claim_count DESC
```

4. How many policies have agents sold by agent id?
```sql
SELECT party_identifier, COUNT(DISTINCT agreement_identifier) AS policy_count
FROM oda_benchmark.acme_agreement_party_role
WHERE party_role_code = 'AG'
GROUP BY party_identifier
ORDER BY policy_count DESC
```

5. What is the total amount of premiums paid by policy number?
```sql
SELECT p.policy_number, SUM(pa.policy_amount) AS total_policy_amount
FROM oda_benchmark.acme_policy p
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
GROUP BY p.policy_number
ORDER BY total_policy_amount DESC
```

6. What is the average time to settle a claim by policy number?
```sql
SELECT p.policy_number, AVG(EXTRACT(DAY FROM (c.claim_close_date - c.claim_open_date))) AS avg_days_to_settle
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY p.policy_number
ORDER BY avg_days_to_settle DESC
```

7. What is the total loss amounts, which is the sum of loss payment, loss reserve amount by claim number?
```sql
SELECT c.company_claim_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
GROUP BY c.company_claim_number
HAVING COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) > 0
ORDER BY total_loss_amount DESC
```

8. What is the total amount of premiums that a policy holder has paid?
```sql
SELECT apr.party_identifier, SUM(pa.policy_amount) AS total_policy_amount
FROM oda_benchmark.acme_agreement_party_role apr
JOIN oda_benchmark.acme_policy p ON apr.agreement_identifier = p.policy_identifier
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
WHERE apr.party_role_code = 'PH'
GROUP BY apr.party_identifier
ORDER BY total_policy_amount DESC
```

9. What is the total amount of premiums that a policy holder has paid by policy number?
```sql
SELECT p.policy_number, apr.party_identifier, SUM(pa.policy_amount) AS total_policy_amount
FROM oda_benchmark.acme_agreement_party_role apr
JOIN oda_benchmark.acme_policy p ON apr.agreement_identifier = p.policy_identifier
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
WHERE apr.party_role_code = 'PH'
GROUP BY p.policy_number, apr.party_identifier
ORDER BY total_policy_amount DESC
```

10. How many policies does each policy holder have by policy holder id?
```sql
SELECT party_identifier, COUNT(DISTINCT agreement_identifier) AS policy_count
FROM oda_benchmark.acme_agreement_party_role
WHERE party_role_code = 'PH'
GROUP BY party_identifier
ORDER BY policy_count DESC
```

11. What is the average policy size which is the total amount of premium divided by the number of policies?
```sql
SELECT SUM(pa.policy_amount) / NULLIF(COUNT(DISTINCT pa.policy_identifier), 0) AS avg_policy_size
FROM oda_benchmark.acme_policy_amount pa
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
```
