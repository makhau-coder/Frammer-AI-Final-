"""
validation.py — ETL Layer 2: Data-quality checks after ingestion

Checks cover two surfaces:
A) Raw CSVs  — schema, nulls, negatives, duplicates, logical consistency
B) DuckDB    — row counts and referential integrity

Run standalone:
    python etl/validation.py
"""

import os
import sys
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import (
    CSV_FILES,
    COLUMN_MAPPINGS,
    DATABASE_PATH,
    NULL_EQUIVALENTS,
    REQUIRED_COLUMNS,
)

# ─────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    count: int = 0


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _load(key: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_FILES[key], encoding="utf-8")
    df = df.rename(columns={k: v for k, v in COLUMN_MAPPINGS.items() if k in df.columns})
    return df


_COUNT_COLS = ["uploaded_count", "created_count", "published_count"]
_DURATION_COLS = ["uploaded_duration", "created_duration", "published_duration"]

# ─────────────────────────────────────────────
# CSV Checks
# ─────────────────────────────────────────────

def check_required_columns(results: list):

    for csv_key, cols in REQUIRED_COLUMNS.items():

        if csv_key not in CSV_FILES:
            continue

        df = _load(csv_key)

        missing = [c for c in cols if c not in df.columns]

        if missing:
            results.append(
                CheckResult(
                    f"schema:{csv_key}",
                    FAIL,
                    f"Required column(s) missing: {missing}",
                    len(missing),
                )
            )
        else:
            results.append(
                CheckResult(
                    f"schema:{csv_key}",
                    PASS,
                    f"All required columns present ({cols})",
                )
            )


def check_null_required(results: list):

    identity_cols = {"video_id", "uploaded_by"}

    for csv_key, req_cols in REQUIRED_COLUMNS.items():

        if csv_key not in CSV_FILES:
            continue

        df = _load(csv_key).replace(NULL_EQUIVALENTS, np.nan)

        for col in req_cols:

            if col not in df.columns:
                continue

            n = int(df[col].isna().sum())

            if n == 0:
                status = PASS
                message = "No nulls"

            elif col in identity_cols:
                status = FAIL
                message = f"{n} null(s) in identity column"

            else:
                status = WARN
                message = f"{n} null(s) — handled by transform"

            results.append(CheckResult(f"null_required:{csv_key}.{col}", status, message, n))


def check_negative_values(results: list):

    agg_keys = ["users", "channels", "input_types", "output_types", "languages"]

    for key in agg_keys:

        if key not in CSV_FILES:
            continue

        df = _load(key).replace(NULL_EQUIVALENTS, np.nan)

        for col in _COUNT_COLS:

            if col not in df.columns:
                continue

            neg = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())

            results.append(
                CheckResult(
                    f"negative:{key}.{col}",
                    FAIL if neg > 0 else PASS,
                    f"{neg} negative value(s)" if neg > 0 else "All non-negative",
                    neg,
                )
            )


def check_monotonicity(results: list):

    agg_keys = ["users", "channels", "input_types", "output_types", "languages"]

    for key in agg_keys:

        if key not in CSV_FILES:
            continue

        df = _load(key).replace(NULL_EQUIVALENTS, np.nan)

        if all(c in df.columns for c in ["published_count", "created_count"]):

            n = int((df["published_count"] > df["created_count"]).sum())

            results.append(
                CheckResult(
                    f"monotonicity:{key}.pub_le_created",
                    FAIL if n > 0 else PASS,
                    f"{n} row(s) where published > created",
                    n,
                )
            )


def check_duplicate_video_ids(results: list):

    df = _load("video_list").replace(NULL_EQUIVALENTS, np.nan)

    if "video_id" not in df.columns:
        return

    dupes = int(df["video_id"].dropna().duplicated().sum())

    results.append(
        CheckResult(
            "duplicates:video_list.video_id",
            WARN if dupes > 0 else PASS,
            f"{dupes} duplicate video_id(s)",
            dupes,
        )
    )


def check_publish_consistency(results: list):

    df = _load("video_list").replace(NULL_EQUIVALENTS, np.nan)

    if "is_published" not in df.columns or "published_platform" not in df.columns:
        return

    published_mask = df["is_published"].astype(str).str.lower() == "yes"

    platform_missing = published_mask & df["published_platform"].isna()

    n = int(platform_missing.sum())

    results.append(
        CheckResult(
            "consistency:published_without_platform",
            WARN if n > 0 else PASS,
            f"{n} published video(s) missing platform",
            n,
        )
    )


# ─────────────────────────────────────────────
# DuckDB Checks
# ─────────────────────────────────────────────

def check_table_row_counts(con, results):

    tables = [
        "dim_user",
        "dim_input_type",
        "dim_platform",
        "dim_team",
        "dim_date",
        "fact_video",
    ]

    for table in tables:

        try:

            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

            results.append(
                CheckResult(
                    f"rowcount:{table}",
                    PASS if n > 0 else FAIL,
                    f"{n} row(s)",
                    n,
                )
            )

        except Exception as exc:

            results.append(CheckResult(f"rowcount:{table}", FAIL, str(exc), 0))


def check_referential_integrity(con, results):

    fk_checks = {
        "user_id": "dim_user",
        "input_type_id": "dim_input_type",
        "platform_id": "dim_platform",
        "team_id": "dim_team",
        "date_id": "dim_date",
    }

    pk_cols = {
        "dim_user": "user_id",
        "dim_input_type": "input_type_id",
        "dim_platform": "platform_id",
        "dim_team": "team_id",
        "dim_date": "date_id",
    }

    for fk_col, dim_table in fk_checks.items():

        pk = pk_cols[dim_table]

        try:

            n = con.execute(
                f"""
                SELECT COUNT(*)
                FROM fact_video f
                WHERE f.{fk_col} IS NOT NULL
                AND f.{fk_col} NOT IN (SELECT {pk} FROM {dim_table})
                """
            ).fetchone()[0]

            results.append(
                CheckResult(
                    f"fk:fact_video.{fk_col}",
                    WARN if n > 0 else PASS,
                    f"{n} orphan FK value(s)" if n > 0 else "Referential integrity OK",
                    n,
                )
            )

        except Exception as exc:

            results.append(CheckResult(f"fk:fact_video.{fk_col}", FAIL, str(exc), 0))

def check_kpi_bounds(con: duckdb.DuckDBPyConnection, results: list) -> None:
    """publish_rate must be 0–100; multiplication_ratio must be > 0."""
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM fact_video WHERE publish_rate < 0 OR publish_rate > 100"
        ).fetchone()[0]
        results.append(CheckResult(
            "kpi_bounds:publish_rate",
            FAIL if n > 0 else PASS,
            f"{n} row(s) outside [0, 100]" if n > 0 else "All values in range",
            n,
        ))
    except Exception as exc:
        results.append(CheckResult("kpi_bounds:publish_rate", FAIL, str(exc), 0))

    try:
        n = con.execute(
            "SELECT COUNT(*) FROM fact_video WHERE multiplication_ratio IS NOT NULL AND multiplication_ratio <= 0"
        ).fetchone()[0]
        results.append(CheckResult(
            "kpi_bounds:multiplication_ratio",
            FAIL if n > 0 else PASS,
            f"{n} row(s) with ratio <= 0" if n > 0 else "All values positive",
            n,
        ))
    except Exception as exc:
        results.append(CheckResult("kpi_bounds:multiplication_ratio", FAIL, str(exc), 0))

def check_qa_account_leakage(con: duckdb.DuckDBPyConnection, results: list) -> None:
    """
    QA accounts should be flagged in dim_user (is_qa_account=TRUE) and should NOT
    appear as fact_video rows (they were filtered during ingestion).
    """
    try:
        qa_in_fact = con.execute("""
            SELECT COUNT(*) FROM fact_video f
            JOIN dim_user u ON f.user_id = u.user_id
            WHERE u.is_qa_account = TRUE
        """).fetchone()[0]
        results.append(CheckResult(
            "qa_leakage:fact_video",
            FAIL if qa_in_fact > 0 else PASS,
            f"{qa_in_fact} QA-account row(s) found in fact_video" if qa_in_fact > 0
            else "No QA accounts in fact_video",
            qa_in_fact,
        ))
    except Exception as exc:
        results.append(CheckResult("qa_leakage:fact_video", FAIL, str(exc), 0))

def check_team_name_coverage(con, results):

    try:

        total = con.execute("SELECT COUNT(*) FROM fact_video").fetchone()[0]

        missing = con.execute(
            """
            SELECT COUNT(*)
            FROM fact_video f
            JOIN dim_team t
            ON f.team_id = t.team_id
            WHERE t.team_name = 'Unknown'
            """
        ).fetchone()[0]

        pct = round(missing / total * 100, 1) if total else 0

        results.append(
            CheckResult(
                "coverage:team_name",
                WARN if pct > 50 else PASS,
                f"{pct}% unknown team_name",
                missing,
            )
        )

    except Exception as exc:

        results.append(CheckResult("coverage:team_name", FAIL, str(exc), 0))


# ─────────────────────────────────────────────
# Report printer
# ─────────────────────────────────────────────

def _print_report(results):

    passes = [r for r in results if r.status == PASS]
    warns = [r for r in results if r.status == WARN]
    fails = [r for r in results if r.status == FAIL]

    print("\n" + "=" * 65)
    print("VALIDATION REPORT")
    print("=" * 65)

    if fails:
        print("\nFAILURES")
        for r in fails:
            print(f"❌ {r.name} — {r.message}")

    if warns:
        print("\nWARNINGS")
        for r in warns:
            print(f"⚠ {r.name} — {r.message}")

    print("\nPASSED")
    for r in passes:
        print(f"✅ {r.name}")

    print("\nTotal:", len(results))
    print("Passed:", len(passes))
    print("Warnings:", len(warns))
    print("Failures:", len(fails))

    print("=" * 65)

    return len(fails) == 0


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def run_validation(con=None):

    close_after = False

    if con is None:
        con = duckdb.connect(DATABASE_PATH)
        close_after = True

    results = []

    print("Running CSV checks …")

    check_required_columns(results)
    check_null_required(results)
    check_negative_values(results)
    check_monotonicity(results)
    check_duplicate_video_ids(results)
    check_publish_consistency(results)

    print("Running DuckDB checks …")

    check_table_row_counts(con, results)
    check_referential_integrity(con, results)
    check_team_name_coverage(con, results)
    check_kpi_bounds(con, results)
    check_qa_account_leakage(con, results)

    if close_after:
        con.close()

    return _print_report(results)


if __name__ == "__main__":

    ok = run_validation()

    sys.exit(0 if ok else 1)
