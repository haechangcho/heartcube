# ACME Insurance — Cube NL2SQL Benchmark Questions

## HQLS — Simple Aggregations

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

## HQHS — Complex Aggregations

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
{"query": {"measures": ["acme_ops.total_policy_amount", "acme_ops.policy_count"], "filters": [{"member": "acme_ops.has_premium", "operator": "equals", "values": ["1"]}]}}
```
