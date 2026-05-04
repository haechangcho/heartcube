# ACME Insurance — Cube NL2SQL Benchmark Questions

## LQLS — Simple Queries on Simple Schema

1. Return all the claims we have by claim number, open date and close date?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.claim_open_date", "acme_ops.claim_close_date"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

2. Return all the policies we have by policy number, effective date and expiration date?
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.policy_effective_date", "acme_ops.policy_expiration_date"], "order": {"acme_ops.policy_number": "asc"}}}
```

3. Return all the policies and their policy holder by id
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.party_identifier"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.policy_number": "asc"}}}
```

4. Return all the policies and the agents that sold them by policy number and agent id
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.party_identifier"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.policy_number": "asc"}}}
```

5. What are all our policies that have a claim associated to them by policy and claim number?
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.company_claim_number"], "order": {"acme_ops.policy_number": "asc"}}}
```

6. What are all the premiums that have been paid by policy holders?
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}, {"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.total_policy_amount": "desc"}}}
```

7. What is the premium amount of all policies by policy number?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.policy_number": "asc"}}}
```

8. What is the premium amount of all policies by policy number, coverage effective date and coverage expiration date
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.coverage_effective_date", "acme_ops.coverage_expiration_date"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.policy_number": "asc"}}}
```

9. What are the loss payment amount of all claims by claim number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.loss_payment_amount"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

10. What are the loss reserve amount of all claims by claim number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.loss_reserve_amount"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

11. What are the expense payment amount of all claims by claim number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.expense_payment_amount"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

12. What are the expense reserve amount of all claims by claim number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.expense_reserve_amount"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

---

## LQHS — Simple Queries on Complex Schema

1. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.loss_payment_amount", "acme_ops.loss_reserve_amount", "acme_ops.expense_payment_amount", "acme_ops.expense_reserve_amount"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

2. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.policy_number", "acme_ops.party_identifier"], "measures": ["acme_ops.loss_payment_amount", "acme_ops.loss_reserve_amount", "acme_ops.expense_payment_amount", "acme_ops.expense_reserve_amount", "acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}, {"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

3. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid and the agent who sold it?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.policy_number", "acme_ops.party_identifier", "acme_ops.party_role_code"], "measures": ["acme_ops.loss_payment_amount", "acme_ops.loss_reserve_amount", "acme_ops.expense_payment_amount", "acme_ops.expense_reserve_amount", "acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

4. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid, the catastrophe it had, and the agent who sold it?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.policy_number", "acme_ops.party_identifier", "acme_ops.party_role_code", "acme_ops.catastrophe_name"], "measures": ["acme_ops.loss_payment_amount", "acme_ops.loss_reserve_amount", "acme_ops.expense_payment_amount", "acme_ops.expense_reserve_amount", "acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

5. Return policy holders and the claims they have made and the corresponding catastrophe
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.company_claim_number", "acme_ops.catastrophe_name"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

6. Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had.
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.company_claim_number", "acme_ops.catastrophe_name"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

7. Return agents and the policies they have sold that have had a claim and the corresponding loss payment amount by agent id, policy number and claim number
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.company_claim_number"], "measures": ["acme_ops.loss_payment_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

8. Return agents and the policy they have sold that have had a claim and the corresponding loss reserve amount by agent id, policy number and claim number
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.company_claim_number"], "measures": ["acme_ops.loss_reserve_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

9. Return agents and the policy they have sold that have had a claim and the corresponding expense payment amount by agent id, policy number and claim number
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.company_claim_number"], "measures": ["acme_ops.expense_payment_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

10. Return agents and the policy they have sold that have had a claim and the corresponding expense reserve amount by agent id, policy number and claim number
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number", "acme_ops.company_claim_number"], "measures": ["acme_ops.expense_reserve_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

---

## HQLS — Complex Queries on Simple Schema

1. How many claims do we have?
```json
{"query": {"measures": ["acme_ops.claim_count"]}}
```

2. How many policies do we have?
```json
{"query": {"measures": ["acme_ops.policy_count"]}}
```

3. How many claims have been placed by policy number?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.claim_count"], "order": {"acme_ops.claim_count": "desc"}}}
```

4. How many policies have agents sold by agent id?
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.policy_count_by_agent"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.policy_count_by_agent": "desc"}}}
```

5. What is the total amount of premiums paid by policy number?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.total_policy_amount": "desc"}}}
```

6. What is the average time to settle a claim by policy number?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.avg_days_to_settle"], "order": {"acme_ops.avg_days_to_settle": "desc"}}}
```

7. What is the total loss amounts, which is the sum of loss payment, loss reserve amount by claim number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.total_loss_amount"], "order": {"acme_ops.total_loss_amount": "desc"}}}
```

8. What is the total amount of premiums that a policy holder has paid?
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}, {"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.total_policy_amount": "desc"}}}
```

9. What is the total amount of premiums that a policy holder has paid by policy number?
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.party_identifier"], "measures": ["acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}, {"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.total_policy_amount": "desc"}}}
```

10. How many policies does each policy holder have by policy holder id?
```json
{"query": {"dimensions": ["acme_ops.party_identifier"], "measures": ["acme_ops.policy_count"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}], "order": {"acme_ops.policy_count": "desc"}}}
```

11. What is the average policy size which is the total amount of premium divided by the number of policies?
```json
{"query": {"measures": ["acme_ops.avg_policy_size"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}]}}
```

---

## HQHS — Complex Queries on Complex Schema

1. What is the total loss of each claim by claim number where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amount?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number"], "measures": ["acme_ops.total_full_loss_amount"], "order": {"acme_ops.total_full_loss_amount": "desc"}}}
```

2. What is the average loss of each policy by policy number where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.avg_full_loss_amount"], "order": {"acme_ops.avg_full_loss_amount": "desc"}}}
```

3. What is the total loss of each policy by policy number where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.total_full_loss_amount"], "order": {"acme_ops.total_full_loss_amount": "desc"}}}
```

4. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.policy_number", "acme_ops.party_identifier"], "measures": ["acme_ops.total_full_loss_amount", "acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["PH"]}, {"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.company_claim_number": "asc"}}}
```

5. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by catastrophe and policy number?
```json
{"query": {"dimensions": ["acme_ops.catastrophe_name", "acme_ops.policy_number"], "measures": ["acme_ops.total_full_loss_amount"], "order": {"acme_ops.total_full_loss_amount": "desc"}}}
```

6. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by claim number, catastrophe and corresponding policy number?
```json
{"query": {"dimensions": ["acme_ops.company_claim_number", "acme_ops.catastrophe_name", "acme_ops.policy_number"], "measures": ["acme_ops.total_full_loss_amount"], "order": {"acme_ops.company_claim_number": "asc"}}}
```

7. What is the total loss of each policy that an agent has sold by agent id where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```json
{"query": {"dimensions": ["acme_ops.party_identifier", "acme_ops.policy_number"], "measures": ["acme_ops.total_full_loss_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}], "order": {"acme_ops.party_identifier": "asc"}}}
```

8. What is the loss ratio of each policy and agent who sold it by policy number and agent id?
```json
{"query": {"dimensions": ["acme_ops.policy_number", "acme_ops.party_identifier"], "measures": ["acme_ops.total_full_loss_amount", "acme_ops.total_policy_amount"], "filters": [{"member": "acme_ops.party_role_code", "operator": "equals", "values": ["AG"]}, {"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.policy_number": "asc"}}}
```

9. What is the average loss of each policy by policy number and number of claims where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.avg_full_loss_amount", "acme_ops.claim_count"], "order": {"acme_ops.policy_number": "asc"}}}
```

10. What is the loss ratio, number of claims, total loss by policy number and premium where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amount and loss ratio is total loss divided by premium?
```json
{"query": {"dimensions": ["acme_ops.policy_number"], "measures": ["acme_ops.total_full_loss_amount", "acme_ops.total_policy_amount", "acme_ops.claim_count"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}], "order": {"acme_ops.policy_number": "asc"}}}
```
