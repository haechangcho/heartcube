-- ACME Party/Person extension for entity retrieval benchmark questions.
-- Apply with a database user that can create tables in oda_benchmark.

CREATE TABLE IF NOT EXISTS oda_benchmark.acme_party (
  party_identifier bigint NOT NULL,
  party_name character varying,
  begin_date timestamp,
  end_date timestamp,
  party_type_code character varying
);

CREATE TABLE IF NOT EXISTS oda_benchmark.acme_person (
  person_identifier bigint NOT NULL,
  first_name character varying,
  middle_name character varying,
  last_name character varying,
  full_legal_name character varying,
  nickname character varying,
  suffix_name character varying,
  birth_date timestamp,
  birth_place_name character varying,
  gender_code character varying,
  prefix_name character varying
);
