#!/usr/bin/env python3
"""Load ACME benchmark CSV files into PostgreSQL."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acme_benchmark.common import DATA_DIR as BENCHMARK_DATA_DIR, env_required


load_dotenv(os.path.expanduser("~/heartcube/.env"))
load_dotenv()

DB_URL = env_required("DATABASE_URL")
SCHEMA = os.environ.get("ACME_DB_SCHEMA", "oda_benchmark")
DATA_DIR = Path(os.environ.get("ACME_DATA_DIR", str(BENCHMARK_DATA_DIR / "source"))).expanduser()
TRUNCATE = os.environ.get("ACME_LOAD_TRUNCATE", "false").lower() == "true"
SKIP_EXISTING = os.environ.get("ACME_LOAD_SKIP_EXISTING", "true").lower() == "true"
CREATE_SCHEMA = os.environ.get("ACME_CREATE_SCHEMA", "false").lower() == "true"

CSV_TABLE_MAP = {
    "Agreement_Party_Role.csv": "acme_agreement_party_role",
    "Catastrophe.csv": "acme_catastrophe",
    "Claim.csv": "acme_claim",
    "Claim_Amount.csv": "acme_claim_amount",
    "Claim_Coverage.csv": "acme_claim_coverage",
    "Expense_Payment.csv": "acme_expense_payment",
    "Expense_Reserve.csv": "acme_expense_reserve",
    "Loss_Payment.csv": "acme_loss_payment",
    "Loss_Reserve.csv": "acme_loss_reserve",
    "Policy.csv": "acme_policy",
    "Policy_Amount.csv": "acme_policy_amount",
    "Policy_Coverage_Detail.csv": "acme_policy_coverage_detail",
    "Premium.csv": "acme_premium",
    "Party.csv": "acme_party",
    "Person.csv": "acme_person",
}


def snake_case(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z]+", "_", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.strip("_").lower()


def load_csvs() -> None:
    engine = create_engine(DB_URL)
    print("=== ACME data load ===")
    print(f"schema={SCHEMA}")
    print(f"data_dir={DATA_DIR}")
    print(f"truncate={TRUNCATE}")
    print(f"skip_existing={SKIP_EXISTING}")
    print(f"create_schema={CREATE_SCHEMA}")

    try:
        with engine.begin() as conn:
            if CREATE_SCHEMA:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
            ensure_party_person_tables(conn)
            if TRUNCATE:
                tables = ", ".join(f"{SCHEMA}.{table}" for table in CSV_TABLE_MAP.values())
                conn.execute(text(f"TRUNCATE {tables}"))
    except Exception as exc:
        raise SystemExit(
            "Failed to prepare ACME tables. Apply "
            "benchmarks/acme/schemas/extensions/party_person_extension.sql "
            "with a database user that can create tables in the target schema, "
            "then rerun this loader."
        ) from exc

    success = 0
    failed = 0
    for csv_file, table_name in CSV_TABLE_MAP.items():
        path = DATA_DIR / csv_file
        try:
            if SKIP_EXISTING and table_has_rows(engine, table_name):
                print(f"  skip existing data: {SCHEMA}.{table_name}")
                continue
            df = pd.read_csv(path)
            df.columns = [snake_case(column) for column in df.columns]
            df.to_sql(table_name, engine, schema=SCHEMA, if_exists="append", index=False)
            print(f"  ok {SCHEMA}.{table_name}: {len(df)} rows")
            success += 1
        except FileNotFoundError:
            print(f"  skip missing file: {csv_file}")
            failed += 1
        except Exception as exc:
            print(f"  fail {SCHEMA}.{table_name}: {exc}")
            failed += 1

    print(f"\ncomplete: success={success} failed={failed}")
    validate(engine)


def ensure_party_person_tables(conn) -> None:
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.acme_party (
              party_identifier bigint NOT NULL,
              party_name character varying,
              begin_date timestamp,
              end_date timestamp,
              party_type_code character varying
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.acme_person (
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
            )
            """
        )
    )


def table_has_rows(engine, table_name: str) -> bool:
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                  SELECT 1
                  FROM information_schema.tables
                  WHERE table_schema = :schema AND table_name = :table_name
                )
                """
            ),
            {"schema": SCHEMA, "table_name": table_name},
        ).scalar()
        if not exists:
            return False
        count = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.{table_name}")).scalar()
        return bool(count)


def validate(engine) -> None:
    print("\n=== Validation ===")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tablename, n_live_tup AS rows
                FROM pg_stat_user_tables
                WHERE schemaname = :schema AND tablename LIKE 'acme_%'
                ORDER BY tablename
                """
            ),
            {"schema": SCHEMA},
        )
        for row in rows:
            print(f"  {row.tablename}: {row.rows} rows")


if __name__ == "__main__":
    load_csvs()
