# ACME Insurance — DDL SQL Benchmark Gold Queries

Schema: `oda_benchmark` (PostgreSQL)

---

## LQLS — Simple Queries on Simple Schema

1. Return all the claims we have by claim number, open date and close date?
```sql
SELECT company_claim_number, claim_open_date, claim_close_date
FROM oda_benchmark.acme_claim
ORDER BY company_claim_number ASC
```

2. Return all the policies we have by policy number, effective date and expiration date?
```sql
SELECT policy_number, effective_date, expiration_date
FROM oda_benchmark.acme_policy
ORDER BY policy_number ASC
```

3. Return all the policies and their policy holder by id
```sql
SELECT p.policy_number, apr.party_identifier AS policyholder_id
FROM oda_benchmark.acme_policy p
JOIN oda_benchmark.acme_agreement_party_role apr
  ON p.policy_identifier = apr.agreement_identifier
WHERE apr.party_role_code = 'PH'
ORDER BY p.policy_number ASC
```

4. Return all the policies and the agents that sold them by policy number and agent id
```sql
SELECT p.policy_number, apr.party_identifier AS agent_id
FROM oda_benchmark.acme_policy p
JOIN oda_benchmark.acme_agreement_party_role apr
  ON p.policy_identifier = apr.agreement_identifier
WHERE apr.party_role_code = 'AG'
ORDER BY p.policy_number ASC
```

5. What are all our policies that have a claim associated to them by policy and claim number?
```sql
SELECT DISTINCT p.policy_number, c.company_claim_number
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc
  ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd
  ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p
  ON pcd.policy_identifier = p.policy_identifier
ORDER BY p.policy_number ASC
```

6. What are all the premiums that have been paid by policy holders?
```sql
SELECT apr.party_identifier AS policyholder_id,
       SUM(pa.policy_amount) AS total_premiums_paid
FROM oda_benchmark.acme_agreement_party_role apr
JOIN oda_benchmark.acme_policy p
  ON apr.agreement_identifier = p.policy_identifier
JOIN oda_benchmark.acme_policy_amount pa
  ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr
  ON pa.policy_amount_identifier = pr.policy_amount_identifier
WHERE apr.party_role_code = 'PH'
GROUP BY apr.party_identifier
ORDER BY total_premiums_paid DESC
```

7. What is the premium amount of all policies by policy number?
```sql
SELECT p.policy_number,
       SUM(pa.policy_amount) AS premium_amount
FROM oda_benchmark.acme_policy p
JOIN oda_benchmark.acme_policy_amount pa
  ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr
  ON pa.policy_amount_identifier = pr.policy_amount_identifier
GROUP BY p.policy_number
ORDER BY p.policy_number ASC
```

8. What is the premium amount of all policies by policy number, coverage effective date and coverage expiration date
```sql
SELECT p.policy_number,
       pcd.effective_date AS coverage_effective_date,
       pcd.expiration_date AS coverage_expiration_date,
       SUM(pa.policy_amount) AS premium_amount
FROM oda_benchmark.acme_policy p
JOIN oda_benchmark.acme_policy_coverage_detail pcd
  ON p.policy_identifier = pcd.policy_identifier
JOIN oda_benchmark.acme_policy_amount pa
  ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr
  ON pa.policy_amount_identifier = pr.policy_amount_identifier
GROUP BY p.policy_number, pcd.effective_date, pcd.expiration_date
ORDER BY p.policy_number ASC
```

9. What are the loss payment amount of all claims by claim number?
```sql
SELECT c.company_claim_number,
       SUM(ca.claim_amount) AS loss_payment_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca
  ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_loss_payment lp
  ON ca.claim_amount_identifier = lp.claim_amount_identifier
GROUP BY c.company_claim_number
ORDER BY c.company_claim_number ASC
```

10. What are the loss reserve amount of all claims by claim number?
```sql
SELECT c.company_claim_number,
       SUM(ca.claim_amount) AS loss_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca
  ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_loss_reserve lr
  ON ca.claim_amount_identifier = lr.claim_amount_identifier
GROUP BY c.company_claim_number
ORDER BY c.company_claim_number ASC
```

11. What are the expense payment amount of all claims by claim number?
```sql
SELECT c.company_claim_number,
       SUM(ca.claim_amount) AS expense_payment_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca
  ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_expense_payment ep
  ON ca.claim_amount_identifier = ep.claim_amount_identifier
GROUP BY c.company_claim_number
ORDER BY c.company_claim_number ASC
```

12. What are the expense reserve amount of all claims by claim number?
```sql
SELECT c.company_claim_number,
       SUM(ca.claim_amount) AS expense_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca
  ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_expense_reserve er
  ON ca.claim_amount_identifier = er.claim_amount_identifier
GROUP BY c.company_claim_number
ORDER BY c.company_claim_number ASC
```

---

## LQHS — Simple Queries on Complex Schema

1. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number?
```sql
SELECT c.company_claim_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_payment_amount,
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_reserve_amount,
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_payment_amount,
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
GROUP BY c.company_claim_number
ORDER BY c.company_claim_number ASC
```

2. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
```sql
SELECT c.company_claim_number,
       p.policy_number,
       apr.party_identifier AS policyholder_id,
       SUM(DISTINCT pa.policy_amount) AS premium_amount,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_payment_amount,
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_reserve_amount,
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_payment_amount,
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
WHERE apr.party_role_code = 'PH'
GROUP BY c.company_claim_number, p.policy_number, apr.party_identifier
ORDER BY c.company_claim_number ASC
```

3. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid and the agent who sold it?
```sql
SELECT c.company_claim_number,
       p.policy_number,
       ph_apr.party_identifier AS policyholder_id,
       ag_apr.party_identifier AS agent_id,
       SUM(DISTINCT pa.policy_amount) AS premium_amount,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_payment_amount,
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_reserve_amount,
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_payment_amount,
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role ph_apr
  ON p.policy_identifier = ph_apr.agreement_identifier AND ph_apr.party_role_code = 'PH'
JOIN oda_benchmark.acme_agreement_party_role ag_apr
  ON p.policy_identifier = ag_apr.agreement_identifier AND ag_apr.party_role_code = 'AG'
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
GROUP BY c.company_claim_number, p.policy_number, ph_apr.party_identifier, ag_apr.party_identifier
ORDER BY c.company_claim_number ASC
```

4. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid, the catastrophe it had, and the agent who sold it?
```sql
SELECT c.company_claim_number,
       p.policy_number,
       ph_apr.party_identifier AS policyholder_id,
       ag_apr.party_identifier AS agent_id,
       cat.catastrophe_name,
       SUM(DISTINCT pa.policy_amount) AS premium_amount,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_payment_amount,
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS loss_reserve_amount,
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_payment_amount,
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS expense_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_catastrophe cat ON c.catastrophe_identifier = cat.catastrophe_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role ph_apr
  ON p.policy_identifier = ph_apr.agreement_identifier AND ph_apr.party_role_code = 'PH'
JOIN oda_benchmark.acme_agreement_party_role ag_apr
  ON p.policy_identifier = ag_apr.agreement_identifier AND ag_apr.party_role_code = 'AG'
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
GROUP BY c.company_claim_number, p.policy_number, ph_apr.party_identifier, ag_apr.party_identifier, cat.catastrophe_name
ORDER BY c.company_claim_number ASC
```

5. Return policy holders and the claims they have made and the corresponding catastrophe
```sql
SELECT apr.party_identifier AS policyholder_id,
       c.company_claim_number,
       cat.catastrophe_name
FROM oda_benchmark.acme_claim c
LEFT JOIN oda_benchmark.acme_catastrophe cat ON c.catastrophe_identifier = cat.catastrophe_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
WHERE apr.party_role_code = 'PH'
ORDER BY apr.party_identifier ASC
```

6. Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had.
```sql
SELECT apr.party_identifier AS agent_id,
       p.policy_number,
       c.company_claim_number,
       cat.catastrophe_name
FROM oda_benchmark.acme_claim c
LEFT JOIN oda_benchmark.acme_catastrophe cat ON c.catastrophe_identifier = cat.catastrophe_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
WHERE apr.party_role_code = 'AG'
ORDER BY apr.party_identifier ASC
```

7. Return agents and the policies they have sold that have had a claim and the corresponding loss payment amount by agent id, policy number and claim number
```sql
SELECT apr.party_identifier AS agent_id,
       p.policy_number,
       c.company_claim_number,
       SUM(ca.claim_amount) AS loss_payment_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
WHERE apr.party_role_code = 'AG'
GROUP BY apr.party_identifier, p.policy_number, c.company_claim_number
ORDER BY apr.party_identifier ASC
```

8. Return agents and the policy they have sold that have had a claim and the corresponding loss reserve amount by agent id, policy number and claim number
```sql
SELECT apr.party_identifier AS agent_id,
       p.policy_number,
       c.company_claim_number,
       SUM(ca.claim_amount) AS loss_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
WHERE apr.party_role_code = 'AG'
GROUP BY apr.party_identifier, p.policy_number, c.company_claim_number
ORDER BY apr.party_identifier ASC
```

9. Return agents and the policy they have sold that have had a claim and the corresponding expense payment amount by agent id, policy number and claim number
```sql
SELECT apr.party_identifier AS agent_id,
       p.policy_number,
       c.company_claim_number,
       SUM(ca.claim_amount) AS expense_payment_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
WHERE apr.party_role_code = 'AG'
GROUP BY apr.party_identifier, p.policy_number, c.company_claim_number
ORDER BY apr.party_identifier ASC
```

10. Return agents and the policy they have sold that have had a claim and the corresponding expense reserve amount by agent id, policy number and claim number
```sql
SELECT apr.party_identifier AS agent_id,
       p.policy_number,
       c.company_claim_number,
       SUM(ca.claim_amount) AS expense_reserve_amount
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
WHERE apr.party_role_code = 'AG'
GROUP BY apr.party_identifier, p.policy_number, c.company_claim_number
ORDER BY apr.party_identifier ASC
```

---

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

---

## HQHS — Complex Queries on Complex Schema

1. What is the total loss of each claim by claim number where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amount?
```sql
SELECT c.company_claim_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
GROUP BY c.company_claim_number
ORDER BY total_loss DESC
```

2. What is the average loss of each policy by policy number where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```sql
WITH claim_loss AS (
  SELECT ca.claim_identifier,
         COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
         COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
         COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
         COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS full_loss
  FROM oda_benchmark.acme_claim_amount ca
  LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
  LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
  LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
  LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
  GROUP BY ca.claim_identifier
)
SELECT p.policy_number,
       AVG(cl.full_loss) AS avg_loss
FROM oda_benchmark.acme_claim c
JOIN claim_loss cl ON c.claim_identifier = cl.claim_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY p.policy_number
ORDER BY avg_loss DESC
```

3. What is the total loss of each policy by policy number where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```sql
SELECT p.policy_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY p.policy_number
ORDER BY total_loss DESC
```

4. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
```sql
SELECT c.company_claim_number,
       p.policy_number,
       apr.party_identifier AS policyholder_id,
       SUM(DISTINCT pa.policy_amount) AS premium_amount,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
WHERE apr.party_role_code = 'PH'
GROUP BY c.company_claim_number, p.policy_number, apr.party_identifier
ORDER BY c.company_claim_number ASC
```

5. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by catastrophe and policy number?
```sql
SELECT cat.catastrophe_name,
       p.policy_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss
FROM oda_benchmark.acme_claim c
LEFT JOIN oda_benchmark.acme_catastrophe cat ON c.catastrophe_identifier = cat.catastrophe_identifier
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY cat.catastrophe_name, p.policy_number
ORDER BY total_loss DESC
```

6. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by claim number, catastrophe and corresponding policy number?
```sql
SELECT c.company_claim_number,
       cat.catastrophe_name,
       p.policy_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss
FROM oda_benchmark.acme_claim c
LEFT JOIN oda_benchmark.acme_catastrophe cat ON c.catastrophe_identifier = cat.catastrophe_identifier
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY c.company_claim_number, cat.catastrophe_name, p.policy_number
ORDER BY c.company_claim_number ASC
```

7. What is the total loss of each policy that an agent has sold by agent id where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```sql
SELECT apr.party_identifier AS agent_id,
       p.policy_number,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
WHERE apr.party_role_code = 'AG'
GROUP BY apr.party_identifier, p.policy_number
ORDER BY apr.party_identifier ASC
```

8. What is the loss ratio of each policy and agent who sold it by policy number and agent id?
```sql
SELECT p.policy_number,
       apr.party_identifier AS agent_id,
       (COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
        COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
        COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
        COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0)) /
       NULLIF(SUM(DISTINCT pa.policy_amount), 0) AS loss_ratio
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_agreement_party_role apr ON p.policy_identifier = apr.agreement_identifier
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
WHERE apr.party_role_code = 'AG'
GROUP BY p.policy_number, apr.party_identifier
ORDER BY p.policy_number ASC
```

9. What is the average loss of each policy by policy number and number of claims where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```sql
WITH claim_loss AS (
  SELECT ca.claim_identifier,
         COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
         COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
         COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
         COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS full_loss
  FROM oda_benchmark.acme_claim_amount ca
  LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
  LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
  LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
  LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
  GROUP BY ca.claim_identifier
)
SELECT p.policy_number,
       COUNT(DISTINCT c.claim_identifier) AS number_of_claims,
       AVG(cl.full_loss) AS avg_loss
FROM oda_benchmark.acme_claim c
JOIN claim_loss cl ON c.claim_identifier = cl.claim_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
GROUP BY p.policy_number
ORDER BY p.policy_number ASC
```

10. What is the loss ratio, number of claims, total loss by policy number and premium where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amount and loss ratio is total loss divided by premium?
```sql
SELECT p.policy_number,
       SUM(DISTINCT pa.policy_amount) AS premium,
       COUNT(DISTINCT c.claim_identifier) AS number_of_claims,
       COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
       COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) AS total_loss,
       (COALESCE(SUM(CASE WHEN lp.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
        COALESCE(SUM(CASE WHEN lr.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
        COALESCE(SUM(CASE WHEN ep.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0) +
        COALESCE(SUM(CASE WHEN er.claim_amount_identifier IS NOT NULL THEN ca.claim_amount END), 0)) /
       NULLIF(SUM(DISTINCT pa.policy_amount), 0) AS loss_ratio
FROM oda_benchmark.acme_claim c
JOIN oda_benchmark.acme_claim_amount ca ON c.claim_identifier = ca.claim_identifier
LEFT JOIN oda_benchmark.acme_loss_payment lp ON ca.claim_amount_identifier = lp.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_loss_reserve lr ON ca.claim_amount_identifier = lr.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_payment ep ON ca.claim_amount_identifier = ep.claim_amount_identifier
LEFT JOIN oda_benchmark.acme_expense_reserve er ON ca.claim_amount_identifier = er.claim_amount_identifier
JOIN oda_benchmark.acme_claim_coverage cc ON c.claim_identifier = cc.claim_identifier
JOIN oda_benchmark.acme_policy_coverage_detail pcd ON cc.policy_coverage_detail_identifier = pcd.policy_coverage_detail_identifier
JOIN oda_benchmark.acme_policy p ON pcd.policy_identifier = p.policy_identifier
JOIN oda_benchmark.acme_policy_amount pa ON p.policy_identifier = pa.policy_identifier
JOIN oda_benchmark.acme_premium pr ON pa.policy_amount_identifier = pr.policy_amount_identifier
GROUP BY p.policy_number
ORDER BY p.policy_number ASC
```
