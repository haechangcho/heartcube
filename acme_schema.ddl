-- ACME Insurance Schema
-- Database: PostgreSQL, Schema: oda_benchmark

CREATE TABLE oda_benchmark.acme_claim (
  claim_identifier integer NOT NULL,
  catastrophe_identifier integer,
  claim_description character varying,
  claims_made_date timestamp,
  company_claim_number character varying,
  company_subclaim_number character varying,
  claim_open_date timestamp,
  claim_close_date timestamp,
  claim_reopen_date timestamp,
  claim_status_code character varying,
  claim_reported_date timestamp
);

CREATE TABLE oda_benchmark.acme_claim_amount (
  claim_amount_identifier bigint NOT NULL,
  claim_identifier integer,
  amount_type_code character varying,
  event_date timestamp,
  claim_amount numeric,
  insurance_type_code character
);

CREATE TABLE oda_benchmark.acme_loss_payment (
  claim_amount_identifier bigint NOT NULL  -- FK to acme_claim_amount; presence means this amount is a loss payment
);

CREATE TABLE oda_benchmark.acme_loss_reserve (
  claim_amount_identifier bigint NOT NULL  -- FK to acme_claim_amount; presence means this amount is a loss reserve
);

CREATE TABLE oda_benchmark.acme_expense_payment (
  claim_amount_identifier bigint NOT NULL  -- FK to acme_claim_amount; presence means this amount is an expense payment
);

CREATE TABLE oda_benchmark.acme_expense_reserve (
  claim_amount_identifier bigint NOT NULL  -- FK to acme_claim_amount; presence means this amount is an expense reserve
);

CREATE TABLE oda_benchmark.acme_claim_coverage (
  claim_identifier integer,
  effective_date timestamp,
  policy_coverage_detail_identifier integer
);

CREATE TABLE oda_benchmark.acme_policy (
  policy_identifier integer NOT NULL,
  effective_date timestamp,
  expiration_date timestamp,
  policy_number character varying,
  status_code character varying
);

CREATE TABLE oda_benchmark.acme_policy_coverage_detail (
  policy_coverage_detail_identifier integer,
  effective_date timestamp,
  policy_identifier integer,
  coverage_part_code character varying,
  expiration_date timestamp
);

CREATE TABLE oda_benchmark.acme_policy_amount (
  policy_amount_identifier bigint NOT NULL,
  policy_identifier integer,
  effective_date timestamp,
  amount_type_code character varying,
  policy_amount numeric
);

CREATE TABLE oda_benchmark.acme_premium (
  policy_amount_identifier bigint NOT NULL  -- FK to acme_policy_amount; presence means this amount is a premium
);

CREATE TABLE oda_benchmark.acme_agreement_party_role (
  agreement_identifier integer,  -- references acme_policy.policy_identifier
  party_identifier bigint,
  party_role_code character varying,  -- 'PH' = policyholder, 'AG' = agent
  effective_date timestamp,
  expiration_date timestamp
);

CREATE TABLE oda_benchmark.acme_catastrophe (
  catastrophe_identifier integer NOT NULL,
  catastrophe_type_code character varying,
  catastrophe_name character varying,
  industry_catastrophe_code character varying,
  company_catastrophe_code character varying
);
