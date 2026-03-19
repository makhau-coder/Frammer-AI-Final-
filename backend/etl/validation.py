"""
etl/validation.py — Per-file data-quality checks for all 11 raw CSVs

Checks every file individually:
  1.  monthly-chart.csv               → check_monthly()
  2.  month-wise-duration.csv         → check_duration()
  3.  CLIENT 1 combined_data...csv    → check_channels()
  4.  ...by channel and user.csv      → check_channel_user()
  5.  ...by user.csv                  → check_users()
  6.  ...by input type.csv            → check_input_types()
  7.  ...by output type.csv           → check_output_types()
  8.  ...by language.csv              → check_languages()
  9.  channel-wise-publishing.csv     → check_publishing()
  10. channel-wise-publishing duration.csv → check_pub_duration()
  11. video_list_data_obfuscated.csv  → check_video_list()

Plus DuckDB structural checks: row counts, FK integrity, KPI bounds.

Results are:
  - Printed to console with PASS / WARN / FAIL
  - Saved to `validation_results` DuckDB table for the API to serve
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime

import duckdb
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import (
    CSV_FILES,
    COLUMN_MAPPINGS,
    DATABASE_PATH,
    DATA_PATH,
    NULL_EQUIVALENTS,
    REQUIRED_COLUMNS,
)

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

# channel_user is not in CSV_FILES — path built directly
_CHANNEL_USER_PATH = os.path.join(
    DATA_PATH, "combined_data(2025-3-1-2026-2-28) by channel and user.csv"
)

_NULLISH = set(NULL_EQUIVALENTS) | {
    "", " ", "N/A", "n/a", "none", "None", "Unknown", "unknown", "NULL", "null",
}

_HMS_RE = re.compile(r"^\d+:\d{2}:\d{2}$")
_MON_RE = re.compile(r"^[A-Za-z]{3},\s*\d{4}$")

_PLATFORM_COLS = ["Facebook", "Instagram", "Linkedin", "Reels",
                  "Shorts", "X", "Youtube", "Threads"]


# ─────────────────────────────────────────────────────────────────────────────
# CheckResult dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name:    str
    status:  str
    message: str
    count:   int   = 0
    pct:     float = 0.0
    field:   str   = ""
    table:   str   = ""    # which CSV / DB table this check belongs to


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load(key: str) -> pd.DataFrame:
    """Load a CSV by its CSV_FILES key, applying column renames."""
    df = pd.read_csv(CSV_FILES[key], encoding="utf-8-sig")
    df = df.rename(
        columns={k: v for k, v in COLUMN_MAPPINGS.items() if k in df.columns}
    )
    return df


def _load_path(path: str) -> pd.DataFrame:
    """Load a CSV by absolute path."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.rename(
        columns={k: v for k, v in COLUMN_MAPPINGS.items() if k in df.columns}
    )
    return df


def _missing(series: pd.Series) -> int:
    """Count null + nullish-string values."""
    return int(
        series.isna().sum() +
        series.fillna("").astype(str).str.strip().isin(_NULLISH).sum()
    )


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 1) if total else 0.0


def _r(results: list, name, status, message, count=0, pct=0.0, field="", table=""):
    results.append(CheckResult(name, status, message, int(count), float(pct), field, table))


# ─────────────────────────────────────────────────────────────────────────────
# FILE 1 — monthly-chart.csv
# ─────────────────────────────────────────────────────────────────────────────

def check_monthly(results: list):
    key = "monthly"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "monthly-chart.csv"

    # Row count — expect exactly 12 months
    if n == 12:
        _r(results, f"rowcount:{tbl}", PASS, "12 months present — correct", n, table=tbl)
    else:
        extra = n - 12
        _r(results, f"rowcount:{tbl}", FAIL if n > 13 else WARN,
           f"{n} rows found (expected 12) — {extra} extra/duplicate row(s)", n, table=tbl)

    # Month column (may be renamed)
    mc = "month" if "month" in df.columns else "Month"
    if mc in df.columns:
        # Duplicate month labels
        dupes = int(df[mc].dropna().duplicated().sum())
        if dupes:
            dup_vals = df[mc][df[mc].duplicated(keep=False)].unique().tolist()
            _r(results, f"duplicates:{tbl}.Month", FAIL,
               f"{dupes} duplicate month(s): {dup_vals} — likely blank row with same label",
               dupes, _pct(dupes, n), field="Month", table=tbl)
        else:
            _r(results, f"duplicates:{tbl}.Month", PASS, "No duplicate months", table=tbl)

        # Month format
        bad = int(df[mc].dropna().astype(str).apply(
            lambda v: not _MON_RE.match(v.strip())).sum())
        _r(results, f"format:{tbl}.Month",
           WARN if bad else PASS,
           f"{bad} label(s) not in 'Mon, YYYY' format" if bad else "Month format OK",
           bad, _pct(bad, n), field="Month", table=tbl)

    # Missing counts
    for col_key, col_name in [
        ("Total Uploaded", "Total Uploaded"),
        ("Total Created",  "Total Created"),
        ("Total Published","Total Published"),
    ]:
        col = next((c for c in df.columns if col_key.lower() in c.lower()), None)
        if col:
            miss = _missing(df[col])
            p    = _pct(miss, n)
            _r(results, f"missing:{tbl}.{col_key}",
               FAIL if miss > 0 else PASS,
               f"{miss} empty cell(s) — likely the blank duplicate row" if miss else "No missing",
               miss, p, field=col_key, table=tbl)

    # Monotonicity
    cc = next((c for c in df.columns if "created" in c.lower()), None)
    pc = next((c for c in df.columns if "published" in c.lower()), None)
    if cc and pc:
        bad = int((pd.to_numeric(df[pc], errors="coerce") >
                   pd.to_numeric(df[cc], errors="coerce")).sum())
        _r(results, f"monotonicity:{tbl}",
           FAIL if bad else PASS,
           f"{bad} month(s) where published > created" if bad else "Monotonicity OK",
           bad, _pct(bad, n), table=tbl)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 2 — month-wise-duration.csv
# ─────────────────────────────────────────────────────────────────────────────

def check_duration(results: list):
    key = "monthly_dur"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "month-wise-duration.csv"

    _r(results, f"rowcount:{tbl}",
       PASS if n == 12 else WARN,
       f"{n} rows (expected 12)", n, table=tbl)

    for col in ["Total Uploaded Duration", "Total Created Duration", "Total Published Duration"]:
        if col not in df.columns:
            _r(results, f"missing_col:{tbl}.{col}", FAIL, f"Column '{col}' not found", table=tbl)
            continue
        miss = _missing(df[col])
        _r(results, f"missing:{tbl}.{col}",
           WARN if miss else PASS,
           f"{miss} missing duration(s)" if miss else "No missing", miss, _pct(miss, n),
           field=col, table=tbl)
        bad = int(df[col].dropna().astype(str).apply(
            lambda v: not _HMS_RE.match(v.strip())).sum())
        _r(results, f"format:{tbl}.{col}",
           WARN if bad else PASS,
           f"{bad} malformed hh:mm:ss value(s)" if bad else "Duration format OK",
           bad, _pct(bad, n), field=col, table=tbl)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 3 — CLIENT 1 combined_data (channels)
# ─────────────────────────────────────────────────────────────────────────────

def check_channels(results: list):
    key = "channels"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "CLIENT1_channels.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} channels", n, table=tbl)

    chan_col = "channel_name" if "channel_name" in df.columns else "Channel"
    if chan_col in df.columns:
        miss  = _missing(df[chan_col])
        dupes = int(df[chan_col].dropna().duplicated().sum())
        _r(results, f"missing:{tbl}.Channel",
           FAIL if miss else PASS,
           f"{miss} missing channel name(s)" if miss else "No missing channel names",
           miss, _pct(miss, n), field="Channel", table=tbl)
        _r(results, f"duplicates:{tbl}.Channel",
           WARN if dupes else PASS,
           f"{dupes} duplicate channel name(s)" if dupes else "No duplicate channels",
           dupes, _pct(dupes, n), field="Channel", table=tbl)

    _check_counts_durations(df, n, tbl, results)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 4 — combined_data by channel and user
# ─────────────────────────────────────────────────────────────────────────────

def check_channel_user(results: list):
    if not os.path.exists(_CHANNEL_USER_PATH):
        _r(results, "rowcount:channel_user.csv", FAIL,
           "File not found: channel_user CSV", table="channel_user.csv")
        return
    df  = _load_path(_CHANNEL_USER_PATH)
    n   = len(df)
    tbl = "channel_user.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} rows", n, table=tbl)

    # Compound key uniqueness (Channel + User) — Channel alone repeats by design
    chan_col = "channel_name" if "channel_name" in df.columns else "Channel"
    user_col = "user_name"    if "user_name"    in df.columns else "User"
    if chan_col in df.columns and user_col in df.columns:
        dupes = int(df.duplicated(subset=[chan_col, user_col]).sum())
        _r(results, f"duplicates:{tbl}.Channel+User",
           FAIL if dupes else PASS,
           f"{dupes} duplicate (Channel, User) pair(s)" if dupes else
           "All (Channel, User) pairs unique — Channel repeats by design",
           dupes, _pct(dupes, n), table=tbl)

    _check_counts_durations(df, n, tbl, results)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 5 — combined_data by user
# ─────────────────────────────────────────────────────────────────────────────

def check_users(results: list):
    key = "users"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "users.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} users", n, table=tbl)

    u_col = "user_name" if "user_name" in df.columns else "User"
    if u_col in df.columns:
        miss  = _missing(df[u_col])
        dupes = int(df[u_col].dropna().duplicated().sum())
        _r(results, f"missing:{tbl}.User",
           FAIL if miss else PASS,
           f"{miss} missing user name(s)" if miss else "No missing user names",
           miss, _pct(miss, n), field="User", table=tbl)
        _r(results, f"duplicates:{tbl}.User",
           WARN if dupes else PASS,
           f"{dupes} duplicate user name(s)" if dupes else "No duplicate users",
           dupes, _pct(dupes, n), field="User", table=tbl)

    _check_counts_durations(df, n, tbl, results)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 6 — combined_data by input type
# ─────────────────────────────────────────────────────────────────────────────

def check_input_types(results: list):
    key = "input_types"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "input_types.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} input types", n, table=tbl)

    it_col = "input_type" if "input_type" in df.columns else "Input Type"
    if it_col in df.columns:
        miss = _missing(df[it_col])
        _r(results, f"missing:{tbl}.InputType",
           WARN if miss else PASS,
           f"{miss} row(s) have no input type label — will be tagged 'unknown' by ETL"
           if miss else "All input types labeled",
           miss, _pct(miss, n), field="Input Type", table=tbl)

    _check_counts_durations(df, n, tbl, results)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 7 — combined_data by output type
# ─────────────────────────────────────────────────────────────────────────────

def check_output_types(results: list):
    key = "output_types"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "output_types.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} output types", n, table=tbl)
    _check_counts_durations(df, n, tbl, results)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 8 — combined_data by language
# ─────────────────────────────────────────────────────────────────────────────

def check_languages(results: list):
    key = "languages"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "languages.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} languages", n, table=tbl)

    # EN and HI must be present
    lang_col = "language" if "language" in df.columns else "Language"
    if lang_col in df.columns:
        langs = set(df[lang_col].dropna().astype(str).str.lower().str.strip())
        for expected in ["en", "hi"]:
            _r(results, f"required_value:{tbl}.{expected}",
               PASS if expected in langs else WARN,
               f"Language '{expected}' found" if expected in langs else
               f"Language '{expected}' NOT present — language analytics may be incomplete",
               0 if expected in langs else 1, field="Language", table=tbl)

    _check_counts_durations(df, n, tbl, results)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 9 — channel-wise-publishing.csv
# ─────────────────────────────────────────────────────────────────────────────

def check_publishing(results: list):
    key = "publishing"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "channel-wise-publishing.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} channels", n, table=tbl)

    # Channel col
    chan_col = "channel_name" if "channel_name" in df.columns else "Channels"
    if chan_col in df.columns:
        miss  = _missing(df[chan_col])
        dupes = int(df[chan_col].dropna().duplicated().sum())
        _r(results, f"missing:{tbl}.Channel",
           FAIL if miss else PASS,
           f"{miss} missing channel name(s)" if miss else "No missing channels",
           miss, _pct(miss, n), field="Channel", table=tbl)
        _r(results, f"duplicates:{tbl}.Channel",
           WARN if dupes else PASS,
           f"{dupes} duplicate channel(s)" if dupes else "No duplicate channels",
           dupes, _pct(dupes, n), field="Channel", table=tbl)

    # Platform columns presence
    present  = [p for p in _PLATFORM_COLS if p in df.columns]
    missing_p = [p for p in _PLATFORM_COLS if p not in df.columns]
    _r(results, f"schema:{tbl}.platforms",
       FAIL if missing_p else PASS,
       f"Missing platform columns: {missing_p}" if missing_p else
       f"All {len(present)} platform columns present",
       len(missing_p), table=tbl)

    # Negative publish counts per platform
    for col in present:
        neg = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())
        if neg:
            _r(results, f"negative:{tbl}.{col}", FAIL,
               f"{neg} negative count(s) in {col}", neg, _pct(neg, n), field=col, table=tbl)

    # Total published across row — check none are all zeros (dead channels)
    if present:
        row_totals = df[present].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        dead = int((row_totals == 0).sum())
        _r(results, f"zero_pub:{tbl}.dead_channels",
           WARN if dead > n * 0.3 else PASS,
           f"{dead}/{n} channels have zero published videos on any platform"
           if dead else "All channels have at least one published video",
           dead, _pct(dead, n), table=tbl)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 10 — channel-wise-publishing duration.csv
# ─────────────────────────────────────────────────────────────────────────────

def check_pub_duration(results: list):
    key = "pub_duration"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "channel-wise-publishing-duration.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL, f"{n} rows", n, table=tbl)

    dur_cols     = [f"{p} Duration" for p in _PLATFORM_COLS if f"{p} Duration" in df.columns]
    missing_cols = [f"{p} Duration" for p in _PLATFORM_COLS if f"{p} Duration" not in df.columns]

    if missing_cols:
        _r(results, f"schema:{tbl}.duration_cols",
           FAIL, f"Missing columns: {missing_cols}", len(missing_cols), table=tbl)

    for col in dur_cols:
        bad = int(df[col].dropna().astype(str).apply(
            lambda v: not _HMS_RE.match(v.strip())).sum())
        _r(results, f"format:{tbl}.{col}",
           WARN if bad else PASS,
           f"{bad} malformed hh:mm:ss value(s)" if bad else "Duration format OK",
           bad, _pct(bad, n), field=col, table=tbl)


# ─────────────────────────────────────────────────────────────────────────────
# FILE 11 — video_list_data_obfuscated.csv
# ─────────────────────────────────────────────────────────────────────────────

def check_video_list(results: list):
    key = "video_list"
    if key not in CSV_FILES:
        return
    df  = _load(key)
    n   = len(df)
    tbl = "video_list.csv"

    _r(results, f"rowcount:{tbl}", PASS if n > 0 else FAIL,
       f"{n:,} video records", n, table=tbl)

    # Per-field missing — severity varies by field importance
    field_checks = [
        ("video_id",           "Video ID",           FAIL),   # identity
        ("uploaded_by",        "Uploaded By",         FAIL),   # identity
        ("headline",           "Headline",            WARN),   # 8.5% known
        ("team_name",          "Team Name",           FAIL),   # 99.3% missing — critical
        ("input_type",         "Type",                WARN),   # 0.1% missing
        ("published_platform", "Published Platform",  WARN),   # high missing but expected
        ("published_url",      "Published URL",       WARN),
    ]
    for std_col, orig_col, sev in field_checks:
        col = std_col if std_col in df.columns else orig_col
        if col not in df.columns:
            continue
        miss = _missing(df[col])
        p    = _pct(miss, n)
        status = FAIL if (miss > 0 and sev == FAIL) else WARN if miss > 0 else PASS
        _r(results, f"missing:{tbl}.{std_col}",
           status,
           f"{miss:,}/{n:,} missing or unknown ({p}%)" if miss else "No missing values",
           miss, p, field=std_col, table=tbl)

    # Duplicate Video IDs
    vid_col = "video_id" if "video_id" in df.columns else "Video ID"
    if vid_col in df.columns:
        ids       = df[vid_col].dropna().astype(str).str.strip()
        dup_ids   = ids[ids.duplicated(keep=False)].unique().tolist()
        n_dupes   = int(ids.duplicated().sum())
        p         = _pct(n_dupes, n)
        _r(results, f"duplicates:{tbl}.video_id",
           FAIL if n_dupes else PASS,
           f"{n_dupes} duplicate Video ID(s) ({p}%) — {len(dup_ids)} unique IDs repeated"
           if n_dupes else "No duplicate Video IDs",
           n_dupes, p, field="Video ID", table=tbl)

    # Duplicate Headlines (not critical — same content can be multi-clipped)
    hl_col = "headline" if "headline" in df.columns else "Headline"
    if hl_col in df.columns:
        non_empty = df[hl_col].dropna().astype(str).str.strip()
        non_empty = non_empty[~non_empty.isin(_NULLISH)]
        dup_hl    = int(non_empty.duplicated().sum())
        _r(results, f"duplicates:{tbl}.headline",
           WARN if dup_hl > n * 0.05 else PASS,
           f"{dup_hl:,} duplicate headline(s) — may indicate same video re-processed"
           if dup_hl else "No duplicate headlines",
           dup_hl, _pct(dup_hl, n), field="Headline", table=tbl)

    # Published without platform
    pub_col  = "is_published"       if "is_published"       in df.columns else "Published"
    plat_col = "published_platform" if "published_platform" in df.columns else "Published Platform"
    if pub_col in df.columns and plat_col in df.columns:
        pub_mask  = df[pub_col].astype(str).str.lower().isin(["yes", "true", "1"])
        total_pub = int(pub_mask.sum())
        no_plat   = int((pub_mask & df[plat_col].fillna("").astype(str).str.strip().isin(_NULLISH)).sum())
        p         = _pct(no_plat, total_pub)
        _r(results, f"consistency:{tbl}.published_without_platform",
           WARN if no_plat else PASS,
           f"{no_plat}/{total_pub} published videos missing platform ({p}%)"
           if no_plat else "All published videos have platform",
           no_plat, p, field="Published Platform", table=tbl)

    # Published without URL
    url_col = "published_url" if "published_url" in df.columns else "Published URL"
    if pub_col in df.columns and url_col in df.columns:
        pub_mask  = df[pub_col].astype(str).str.lower().isin(["yes", "true", "1"])
        total_pub = int(pub_mask.sum())
        no_url    = int((pub_mask & df[url_col].fillna("").astype(str).str.strip().isin(_NULLISH)).sum())
        p         = _pct(no_url, total_pub)
        _r(results, f"consistency:{tbl}.published_without_url",
           WARN if no_url else PASS,
           f"{no_url}/{total_pub} published videos missing URL ({p}%)"
           if no_url else "All published videos have URL",
           no_url, p, field="Published URL", table=tbl)


# ─────────────────────────────────────────────────────────────────────────────
# Generic helper: check count cols + duration format on any agg file
# ─────────────────────────────────────────────────────────────────────────────

def _check_counts_durations(df: pd.DataFrame, n: int, tbl: str, results: list):
    """Shared logic for all aggregated CSVs."""
    count_cols = [c for c in df.columns
                  if any(kw in c.lower() for kw in ["count", "uploaded", "created", "published"])
                  and "duration" not in c.lower()]
    dur_cols   = [c for c in df.columns if "duration" in c.lower()]

    # Missing counts
    for col in count_cols:
        miss = _missing(df[col])
        if miss:
            _r(results, f"missing:{tbl}.{col}", WARN,
               f"{miss} missing value(s) ({_pct(miss, n)}%)",
               miss, _pct(miss, n), field=col, table=tbl)

    # Negative counts
    for col in count_cols:
        try:
            neg = int((pd.to_numeric(df[col], errors="coerce") < 0).sum())
            if neg:
                _r(results, f"negative:{tbl}.{col}", FAIL,
                   f"{neg} negative value(s)", neg, _pct(neg, n), field=col, table=tbl)
        except Exception:
            pass

    # published <= created
    cc = next((c for c in count_cols if "created"   in c.lower()), None)
    pc = next((c for c in count_cols if "published" in c.lower()), None)
    if cc and pc:
        bad = int((pd.to_numeric(df[pc], errors="coerce") >
                   pd.to_numeric(df[cc], errors="coerce")).sum())
        _r(results, f"monotonicity:{tbl}",
           FAIL if bad else PASS,
           f"{bad} row(s) where published > created" if bad else "Monotonicity OK",
           bad, _pct(bad, n), table=tbl)

    # Duration format
    for col in dur_cols:
        bad = int(df[col].dropna().astype(str).apply(
            lambda v: not _HMS_RE.match(v.strip())).sum())
        if bad:
            _r(results, f"format:{tbl}.{col}", WARN,
               f"{bad} malformed hh:mm:ss value(s)", bad, _pct(bad, n), field=col, table=tbl)

    # All-pass summary if no issues
    if not any(r.table == tbl and r.status != PASS for r in results
               if r.name.startswith(("missing:", "negative:", "monotonicity:", "format:"))):
        _r(results, f"all_pass:{tbl}", PASS, "All count and duration checks passed", table=tbl)


# ─────────────────────────────────────────────────────────────────────────────
# DuckDB structural checks
# ─────────────────────────────────────────────────────────────────────────────

def check_table_row_counts(con, results: list):
    for table in ["dim_user","dim_input_type","dim_platform","dim_team","dim_date","fact_video"]:
        try:
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            _r(results, f"rowcount:db.{table}", PASS if n > 0 else FAIL,
               f"{n:,} rows", n, table=f"db:{table}")
        except Exception as exc:
            _r(results, f"rowcount:db.{table}", FAIL, str(exc), table=f"db:{table}")


def check_referential_integrity(con, results: list):
    fks = {
        "user_id"      : ("dim_user",       "user_id"),
        "input_type_id": ("dim_input_type",  "input_type_id"),
        "platform_id"  : ("dim_platform",    "platform_id"),
        "team_id"      : ("dim_team",        "team_id"),
        "date_id"      : ("dim_date",        "date_id"),
    }
    for fk_col, (dim, pk) in fks.items():
        try:
            n = con.execute(f"""
                SELECT COUNT(*) FROM fact_video f
                WHERE f.{fk_col} IS NOT NULL
                  AND f.{fk_col} NOT IN (SELECT {pk} FROM {dim})
            """).fetchone()[0]
            _r(results, f"fk:fact_video.{fk_col}",
               WARN if n else PASS,
               f"{n} orphan FK(s)" if n else "Referential integrity OK",
               n, field=fk_col, table="db:fact_video")
        except Exception as exc:
            _r(results, f"fk:fact_video.{fk_col}", FAIL, str(exc), table="db:fact_video")


def check_kpi_bounds(con, results: list):
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM fact_video WHERE publish_rate < 0 OR publish_rate > 100"
        ).fetchone()[0]
        _r(results, "kpi_bounds:publish_rate",
           FAIL if n else PASS,
           f"{n} row(s) outside [0,100]" if n else "All values in range",
           n, field="publish_rate", table="db:fact_video")
    except Exception as exc:
        _r(results, "kpi_bounds:publish_rate", FAIL, str(exc))


def check_qa_account_leakage(con, results: list):
    try:
        n = con.execute("""
            SELECT COUNT(*) FROM fact_video f
            JOIN dim_user u ON f.user_id = u.user_id
            WHERE u.is_qa_account = TRUE
        """).fetchone()[0]
        _r(results, "qa_leakage:fact_video",
           FAIL if n else PASS,
           f"{n} QA-account row(s) leaked into fact_video" if n else "No QA leakage",
           n, table="db:fact_video")
    except Exception as exc:
        _r(results, "qa_leakage:fact_video", FAIL, str(exc))


def check_team_name_coverage(con, results: list):
    try:
        total   = con.execute("SELECT COUNT(*) FROM fact_video").fetchone()[0]
        missing = con.execute("""
            SELECT COUNT(*) FROM fact_video f
            JOIN dim_team t ON f.team_id = t.team_id
            WHERE t.team_name = 'Unknown'
        """).fetchone()[0]
        p = _pct(missing, total)
        _r(results, "coverage:team_name",
           FAIL if p > 90 else WARN if p > 50 else PASS,
           f"{p}% unknown team_name ({missing:,}/{total:,})",
           missing, p, field="team_name", table="db:fact_video")
    except Exception as exc:
        _r(results, "coverage:team_name", FAIL, str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Save to DuckDB
# ─────────────────────────────────────────────────────────────────────────────

def _save_to_db(con, results: list) -> None:
    con.execute("DROP TABLE IF EXISTS validation_results")
    con.execute("""
        CREATE TABLE validation_results (
            name     VARCHAR,
            status   VARCHAR,
            message  VARCHAR,
            count    INTEGER,
            pct      DOUBLE,
            field    VARCHAR,
            tbl      VARCHAR,
            ran_at   VARCHAR
        )
    """)
    ran_at = datetime.utcnow().isoformat() + "Z"   # explicit UTC — JS parses correctly
    con.executemany(
        "INSERT INTO validation_results VALUES (?,?,?,?,?,?,?,?)",
        [(r.name, r.status, r.message, r.count, r.pct, r.field, r.table, ran_at)
         for r in results],
    )
    con.commit()
    print(f"  Saved {len(results)} validation results to DuckDB.")


# ─────────────────────────────────────────────────────────────────────────────
# Console report
# ─────────────────────────────────────────────────────────────────────────────

def _print_report(results: list) -> bool:
    passes = [r for r in results if r.status == PASS]
    warns  = [r for r in results if r.status == WARN]
    fails  = [r for r in results if r.status == FAIL]

    print("\n" + "=" * 70)
    print("VALIDATION REPORT — ALL 11 RAW FILES")
    print("=" * 70)

    if fails:
        print(f"\n❌  FAILURES ({len(fails)}):")
        for r in fails:
            print(f"    {r.table or '':<35} {r.name}")
            print(f"    {'':>35} {r.message}")

    if warns:
        print(f"\n⚠   WARNINGS ({len(warns)}):")
        for r in warns:
            print(f"    {r.table or '':<35} {r.name}")
            print(f"    {'':>35} {r.message}")

    print(f"\n✅  PASSED: {len(passes)}  |  WARN: {len(warns)}  |  FAIL: {len(fails)}  |  TOTAL: {len(results)}")
    print("=" * 70)
    return len(fails) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_validation(con=None) -> bool:
    close_after = con is None
    if con is None:
        con = duckdb.connect(DATABASE_PATH)

    results = []

    print("Running per-file CSV checks …")
    check_monthly(results)
    check_duration(results)
    check_channels(results)
    check_channel_user(results)
    check_users(results)
    check_input_types(results)
    check_output_types(results)
    check_languages(results)
    check_publishing(results)
    check_pub_duration(results)
    check_video_list(results)

    print("Running DuckDB structural checks …")
    check_table_row_counts(con, results)
    check_referential_integrity(con, results)
    check_team_name_coverage(con, results)
    check_kpi_bounds(con, results)
    check_qa_account_leakage(con, results)

    _save_to_db(con, results)

    if close_after:
        con.close()

    return _print_report(results)


if __name__ == "__main__":
    sys.exit(0 if run_validation() else 1)