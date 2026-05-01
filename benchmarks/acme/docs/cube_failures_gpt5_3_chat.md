# Cube 벤치마크 실패 분석 (gpt-5.3-chat-latest)
전체 43개 질문 중 Exact Match < 80% 질문 12개

---
## [Q02] [LQLS] Return all the policies we have by policy number, effective date and expiration date?
**Exact Match: 0% (0/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.policy_effective_date",
      "acme_ops.policy_expiration_date"
    ],
    "order": {
      "acme_ops.policy_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.policy_effective_date",
      "acme_ops.policy_expiration_date"
    ],
    "measures": [
      "acme_ops.policy_count"
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.policy_effective_date",
      "acme_ops.policy_expiration_date"
    ],
    "measures": [
      "acme_ops.policy_count"
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.policy_effective_date",
      "acme_ops.policy_expiration_date"
    ],
    "measures": [
      "acme_ops.policy_count"
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.policy_effective_date",
      "acme_ops.policy_expiration_date"
    ],
    "measures": [
      "acme_ops.policy_count"
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.policy_effective_date",
      "acme_ops.policy_expiration_date"
    ],
    "measures": [
      "acme_ops.policy_count"
    ]
  }
}
```

---
## [Q05] [LQLS] What are all our policies that have a claim associated to them by policy and claim number?
**Exact Match: 0% (0/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.company_claim_number"
    ],
    "order": {
      "acme_ops.policy_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.company_claim_number"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.company_claim_number"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.company_claim_number"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.company_claim_number"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.company_claim_number"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

---
## [Q30] [HQLS] What is the total amount of premiums that a policy holder has paid by policy number?
**Exact Match: 0% (0/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      },
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ],
    "order": {
      "acme_ops.total_policy_amount": "desc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.total_policy_amount": "desc"
    }
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.total_policy_amount": "desc"
    }
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.total_policy_amount": "desc"
    }
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.total_policy_amount": "desc"
    }
  }
}
```

---
## [Q18] [LQHS] Return agents and the policy they have sold that have had a claim and the corresponding catastrophe it had.
**Exact Match: 0% (0/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ],
    "order": {
      "acme_ops.party_identifier": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.policy_number",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

---
## [Q41] [HQHS] What is the loss ratio of each policy and agent who sold it by policy number and agent id?
**Exact Match: 0% (0/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_full_loss_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.policy_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_loss_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_loss_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_loss_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_loss_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_loss_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "AG"
        ]
      }
    ]
  }
}
```

---
## [Q14] [LQHS] What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder and premium amount paid?
**Exact Match: 20% (1/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.company_claim_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_full_legal_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_full_legal_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_full_legal_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

---
## [Q16] [LQHS] What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid, the catastrophe it had, and the agent who sold it?
**Exact Match: 20% (1/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.company_claim_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_name",
      "acme_ops.party_role_code",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code",
      "acme_ops.party_full_legal_name",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code",
      "acme_ops.party_full_legal_name",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code",
      "acme_ops.party_name",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

---
## [Q17] [LQHS] Return policy holders and the claims they have made and the corresponding catastrophe
**Exact Match: 20% (1/5)**

### 정답 쿼리
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
        "values": [
          "PH"
        ]
      }
    ],
    "order": {
      "acme_ops.party_identifier": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 4 ✓**
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
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier",
      "acme_ops.company_claim_number",
      "acme_ops.catastrophe_name"
    ],
    "measures": [
      "acme_ops.claim_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

---
## [Q15] [LQHS] What are the loss payment, loss reserve, expense payment, expense reserve amount by claim number and corresponding policy number, policy holder, premium amount paid and the agent who sold it?
**Exact Match: 20% (1/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.company_claim_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_role_code",
      "acme_ops.party_identifier",
      "acme_ops.party_full_legal_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_name",
      "acme_ops.party_role_code"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 3 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_full_legal_name",
      "acme_ops.party_role_code"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.policy_number",
      "acme_ops.party_identifier",
      "acme_ops.party_role_code",
      "acme_ops.party_name"
    ],
    "measures": [
      "acme_ops.loss_payment_amount",
      "acme_ops.loss_reserve_amount",
      "acme_ops.expense_payment_amount",
      "acme_ops.expense_reserve_amount",
      "acme_ops.total_policy_amount"
    ]
  }
}
```

---
## [Q01] [LQLS] Return all the claims we have by claim number, open date and close date?
**Exact Match: 40% (2/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.claim_close_date"
    ],
    "order": {
      "acme_ops.company_claim_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✓**
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

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.claim_close_date"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.claim_close_date"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.company_claim_number",
      "acme_ops.claim_open_date",
      "acme_ops.claim_close_date"
    ],
    "measures": [
      "acme_ops.claim_count"
    ]
  }
}
```

**Iter 5 ✓**
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

---
## [Q03] [LQLS] Return all the policies and their policy holder by id
**Exact Match: 40% (2/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ],
    "order": {
      "acme_ops.policy_number": "asc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 2 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.policy_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 4 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.policy_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

**Iter 5 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.policy_count"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      }
    ]
  }
}
```

---
## [Q06] [LQLS] What are all the premiums that have been paid by policy holders?
**Exact Match: 60% (3/5)**

### 정답 쿼리
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ],
    "order": {
      "acme_ops.total_policy_amount": "desc"
    }
  }
}
```

### 생성된 쿼리 (5회)
**Iter 1 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 2 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 3 ✗**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.policy_number",
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 4 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

**Iter 5 ✓**
```json
{
  "query": {
    "dimensions": [
      "acme_ops.party_identifier"
    ],
    "measures": [
      "acme_ops.total_policy_amount"
    ],
    "filters": [
      {
        "member": "acme_ops.party_role_code",
        "operator": "equals",
        "values": [
          "PH"
        ]
      },
      {
        "member": "acme_ops.has_premium",
        "operator": "equals",
        "values": [
          "1"
        ]
      }
    ]
  }
}
```

