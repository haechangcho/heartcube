# Benchmark Questions

ACME Insurance 데이터셋 기반 총 44개 질문

## 분류 체계

원본 TTL의 `dct:title` 필드 기준 2×2 매트릭스:

| | **LS** (단순 스키마: 1~3 테이블) | **HS** (복잡 스키마: 4+ 테이블, 다중 조인) |
|---|---|---|
| **LQ** (단순 조회: SELECT) | LQLS | LQHS |
| **HQ** (복잡 쿼리: 집계·계산·KPI) | HQLS | HQHS |

---

## LQLS — 단순 조회 × 단순 스키마

> 집계 없이 몇 개 테이블에서 데이터를 가져오는 쿼리

1. Return all the claims we have by claim number, open date and close date?
2. Return all the policies we have by policy number, effective date and expiration date?
3. Return all the policies and their policy holder by id
4. Return all the policies and the agents that sold them by policy number and agent id
5. What are all our policies that have a claim associated to them by policy and claim number?
6. What are all the premiums that have been paid by policy holders?
7. What is the premium amount of all policies by policy number?
8. What is the premium amount of all policies by policy number, coverage effective date and coverage expiration date
9. What are the loss payment amount of all claims by claim number?
10. What are the loss reserve amount of all claims by claim number?
11. What are the expense payment amount of all claims by claim number?
12. What are the expense reserve amount of all claims by claim number?

---

## LQHS — 단순 조회 × 복잡 스키마

> 집계 없이 다수의 테이블을 조인해서 데이터를 가져오는 쿼리

13. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number?
14. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
15. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid and the agent who sold it?
16. What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid, the catastrophe it had, and the agent who sold it?
17. Return policy holders and the claims they have made and the corresponding catastrophe
18. Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had.
19. Return agents and the policies they have sold that have had a claim and the corresponding loss payment amount by agent id, policy number and claim number
20. Return agents and the policy they have sold that have had a claim and the corresponding loss reserve amount by agent id, policy number and claim number
21. Return agents and the policy they have sold that have had a claim and the corresponding expense payment amount by agent id, policy number and claim number
22. Return agents and the policy they have sold that have had a claim and the corresponding expense reserve amount by agent id, policy number and claim number

---

## HQLS — 복잡 쿼리 × 단순 스키마

> 적은 테이블에서 COUNT·SUM·AVG 등 집계를 수행하는 쿼리

23. How many claims do we have?
24. How many policies do we have?
25. How many claims have been placed by policy number?
26. How many policies have agents sold by agent id?
27. How many policies does each policy holder have by policy holder id?
28. What is the total amount of premiums paid by policy number?
29. What is the total amount of premiums that a policy holder has paid?
30. What is the total amount of premiums that a policy holder has paid by policy number?
31. What is the total loss amounts, which is the sum of loss payment, loss reserve amount by claim number?
32. What is the average time to settle a claim by policy number?
33. What is the average policy size which is the total amount of premium divided by the number of policies?

---

## HQHS — 복잡 쿼리 × 복잡 스키마

> 다수의 테이블을 조인하면서 복합 집계·KPI 계산까지 수행하는 가장 어려운 유형

34. What is the total loss of each claim by claim number where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amount?
35. What is the average loss of each policy by policy number where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
36. What is the total loss of each policy by policy number where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
37. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
38. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by catastrophe and policy number?
39. What are the total loss, which is the sum of loss payment, loss reserve, expense payment, expense reserve amount by claim number, catastrophe and corresponding policy number?
40. What is the total loss of each policy that an agent has sold by agent id where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
41. What is the loss ratio of each policy and agent who sold it by policy number and agent id?
42. What is the average loss of each policy by policy number and number of claims where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
43. What is the loss ratio, number of claims, total loss by policy number and premium where total loss is the sum of loss payment, loss reserve, expense payment, expense reserve amount and loss ratio is total loss divided by premium?
44. What is the average loss of each policy by policy number and number of claims where loss is the sum of loss payment, loss reserve, expense payment, expense reserve amounts?
