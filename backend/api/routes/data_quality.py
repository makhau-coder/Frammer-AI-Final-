"""
api/routes/data_quality.py

GET /api/data-quality          → full quality report per file from raw CSVs
GET /api/data-quality/checks   → validation check results (PASS/WARN/FAIL) from last ETL run
"""

import csv
import os
import re
import sys
from collections import Counter

import duckdb
from fastapi import APIRouter, HTTPException

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ETL_ROOT     = os.path.join(_BACKEND_ROOT, "etl")
for _p in [_BACKEND_ROOT, _ETL_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import DATABASE_PATH, CSV_FILES, DATA_PATH

router = APIRouter(prefix="/api", tags=["data-quality"])

_NULLISH = {
    "", " ", "N/A", "n/a", "none", "None", "Unknown", "unknown", "NULL", "null",
}
_HMS_RE = re.compile(r"^\d+:\d{2}:\d{2}$")
_MON_RE = re.compile(r"^[A-Za-z]{3},\s*\d{4}$")

_CHANNEL_USER_PATH = os.path.join(
    DATA_PATH, "combined_data(2025-3-1-2026-2-28) by channel and user.csv"
)
_PLATFORM_COLS = ["Facebook", "Instagram", "Linkedin", "Reels",
                  "Shorts", "X", "Youtube", "Threads"]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_null(v: str) -> bool:
    return v.strip() in _NULLISH


def _load_csv(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _missing(vals: list) -> int:
    return sum(1 for v in vals if _is_null(v))


def _pct(n: int, total: int) -> float:
    return round(n / total * 100, 1) if total else 0.0


def _file_summary(label: str, path: str, rows: list, issues: list) -> dict:
    """Build a per-file quality summary dict."""
    n         = len(rows)
    cols      = list(rows[0].keys()) if rows else []
    score     = 100
    for iss in issues:
        score -= 15 if iss["severity"] == "fail" else 8 if iss["severity"] == "warn" else 2
    score = max(0, score)

    return {
        "file"       : label,
        "path"       : os.path.basename(path),
        "total_rows" : n,
        "columns"    : cols,
        "column_count": len(cols),
        "issues"     : issues,
        "issue_count": len(issues),
        "fail_count" : sum(1 for i in issues if i["severity"] == "fail"),
        "warn_count" : sum(1 for i in issues if i["severity"] == "warn"),
        "quality_score": score,
        "status"     : "fail" if any(i["severity"] == "fail" for i in issues)
                       else "warn" if issues else "pass",
    }


def _issue(severity, field, title, detail, count=0, pct=0.0):
    return {"severity": severity, "field": field, "title": title,
            "detail": detail, "count": count, "pct": pct}


def _check_missing(rows, col, n, severity="warn"):
    vals    = [r.get(col, "") for r in rows]
    missing = _missing(vals)
    p       = _pct(missing, n)
    if missing:
        return _issue(severity, col,
                      f"'{col}': {missing:,} missing/unknown ({p}%)",
                      f"{missing:,} out of {n:,} rows have empty or 'Unknown' values.",
                      missing, p)
    return None


def _check_dupes(rows, col, n, severity="warn", expect_dupes=False):
    if expect_dupes:
        return None
    vals  = [r.get(col, "").strip() for r in rows if r.get(col, "").strip()]
    seen  = Counter(vals)
    dupes = sum(1 for v, c in seen.items() if c > 1)
    if dupes:
        sample = [v for v, c in seen.items() if c > 1][:3]
        return _issue(severity, col,
                      f"'{col}': {dupes} duplicate value(s)",
                      f"Duplicated values found. Sample: {sample}",
                      dupes, _pct(dupes, n))
    return None


def _check_negatives(rows, col, n):
    try:
        negs = sum(1 for r in rows if float(r.get(col, "0") or "0") < 0)
        if negs:
            return _issue("fail", col, f"'{col}': {negs} negative value(s)",
                          f"Count columns should not be negative.", negs, _pct(negs, n))
    except Exception:
        pass
    return None


def _check_monotonicity(rows, cc, pc, n):
    try:
        bad = sum(1 for r in rows
                  if float(r.get(pc, 0) or 0) > float(r.get(cc, 0) or 0))
        if bad:
            return _issue("fail", pc,
                          f"Published > Created in {bad} row(s)",
                          "Published count exceeds Created count, which is logically impossible.",
                          bad, _pct(bad, n))
    except Exception:
        pass
    return None


def _check_hms(rows, col, n):
    bad = sum(1 for r in rows
              if r.get(col, "").strip() and not _HMS_RE.match(r.get(col, "").strip()))
    if bad:
        return _issue("warn", col,
                      f"'{col}': {bad} malformed duration(s)",
                      "Expected format hh:mm:ss. Malformed values will be skipped by ETL.",
                      bad, _pct(bad, n))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Per-file audit functions
# ─────────────────────────────────────────────────────────────────────────────

def _audit_monthly(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []

    if n != 12:
        extra = n - 12
        issues.append(_issue("fail" if abs(n-12) > 2 else "warn", "Month",
                             f"{n} rows found, expected 12",
                             f"{extra} extra row(s) detected. The duplicate is likely a blank 'Oct, 2025' row.",
                             abs(n - 12)))

    # Duplicate months
    months = [r.get("Month", "").strip() for r in rows]
    seen   = Counter(months)
    for m, c in seen.items():
        if c > 1:
            issues.append(_issue("fail", "Month",
                                 f"Duplicate month: '{m}' appears {c} times",
                                 "One row is blank with empty counts. Should be removed from CSV.",
                                 c - 1))

    for col in ["Total Uploaded", "Total Created", "Total Published"]:
        iss = _check_missing(rows, col, n, "fail")
        if iss:
            issues.append(iss)
        neg = _check_negatives(rows, col, n)
        if neg:
            issues.append(neg)

    iss = _check_monotonicity(rows, "Total Created", "Total Published", n)
    if iss:
        issues.append(iss)

    return _file_summary("monthly-chart.csv", path, rows, issues)


def _audit_duration(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    for col in ["Total Uploaded Duration", "Total Created Duration", "Total Published Duration"]:
        iss = _check_hms(rows, col, n)
        if iss:
            issues.append(iss)
    return _file_summary("month-wise-duration.csv", path, rows, issues)


def _audit_channels(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    for col in ["Channel", "Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_missing(rows, col, n, "fail" if col == "Channel" else "warn")
        if iss:
            issues.append(iss)
    iss = _check_dupes(rows, "Channel", n, "warn")
    if iss:
        issues.append(iss)
    for col in ["Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_negatives(rows, col, n)
        if iss:
            issues.append(iss)
    iss = _check_monotonicity(rows, "Created Count", "Published Count", n)
    if iss:
        issues.append(iss)
    for col in ["Uploaded Duration (hh:mm:ss)", "Created Duration (hh:mm:ss)", "Published Duration (hh:mm:ss)"]:
        iss = _check_hms(rows, col, n)
        if iss:
            issues.append(iss)
    return _file_summary("CLIENT1-channels.csv", path, rows, issues)


def _audit_channel_user(path):
    if not os.path.exists(path):
        return {"file": "channel_user.csv", "status": "fail",
                "issues": [_issue("fail", "", "File not found", path)],
                "quality_score": 0, "total_rows": 0, "columns": []}
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []

    # Compound key uniqueness
    pairs  = [(r.get("Channel", ""), r.get("User", "")) for r in rows]
    c_pairs = Counter(pairs)
    dupes   = sum(1 for v in c_pairs.values() if v > 1)
    if dupes:
        issues.append(_issue("fail", "Channel+User",
                             f"{dupes} duplicate (Channel, User) pair(s)",
                             "Each (Channel, User) combination should be unique.",
                             dupes, _pct(dupes, n)))

    for col in ["Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_negatives(rows, col, n)
        if iss:
            issues.append(iss)
    iss = _check_monotonicity(rows, "Created Count", "Published Count", n)
    if iss:
        issues.append(iss)
    return _file_summary("channel-user.csv", path, rows, issues)


def _audit_users(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    iss = _check_missing(rows, "User", n, "fail")
    if iss:
        issues.append(iss)
    iss = _check_dupes(rows, "User", n, "warn")
    if iss:
        issues.append(iss)
    for col in ["Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_negatives(rows, col, n)
        if iss:
            issues.append(iss)
    iss = _check_monotonicity(rows, "Created Count", "Published Count", n)
    if iss:
        issues.append(iss)
    return _file_summary("users.csv", path, rows, issues)


def _audit_input_types(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    iss = _check_missing(rows, "Input Type", n, "warn")
    if iss:
        iss["detail"] = f"{iss['count']} row(s) have no Input Type label — will be tagged 'unknown' by ETL."
        issues.append(iss)
    for col in ["Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_negatives(rows, col, n)
        if iss:
            issues.append(iss)
    iss = _check_monotonicity(rows, "Created Count", "Published Count", n)
    if iss:
        issues.append(iss)
    return _file_summary("input-types.csv", path, rows, issues)


def _audit_output_types(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    for col in ["Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_negatives(rows, col, n)
        if iss:
            issues.append(iss)
    return _file_summary("output-types.csv", path, rows, issues)


def _audit_languages(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    langs  = {r.get("Language", "").strip().lower() for r in rows}
    for expected in ["en", "hi"]:
        if expected not in langs:
            issues.append(_issue("warn", "Language",
                                 f"Language '{expected}' not present",
                                 "EN and HI are expected. Missing language breaks language analytics.",
                                 1))
    for col in ["Uploaded Count", "Created Count", "Published Count"]:
        iss = _check_negatives(rows, col, n)
        if iss:
            issues.append(iss)
    return _file_summary("languages.csv", path, rows, issues)


def _audit_publishing(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    iss = _check_missing(rows, "Channels", n, "fail")
    if iss:
        issues.append(iss)
    present = [p for p in _PLATFORM_COLS if rows and p in rows[0]]
    missing = [p for p in _PLATFORM_COLS if p not in (rows[0] if rows else {})]
    if missing:
        issues.append(_issue("fail", "schema",
                             f"Missing platform columns: {missing}",
                             "All 8 platform columns are required.", len(missing)))
    for col in present:
        try:
            negs = sum(1 for r in rows if float(r.get(col, 0) or 0) < 0)
            if negs:
                issues.append(_issue("fail", col, f"'{col}': {negs} negative count(s)",
                                     "Publish counts cannot be negative.", negs))
        except Exception:
            pass
    # Dead channels
    if present:
        dead = sum(1 for r in rows if all(float(r.get(p, 0) or 0) == 0 for p in present))
        if dead > n * 0.3:
            issues.append(_issue("warn", "platform_totals",
                                 f"{dead}/{n} channels have zero publishes on all platforms",
                                 "More than 30% of channels have never published anywhere.", dead,
                                 _pct(dead, n)))
    return _file_summary("channel-wise-publishing.csv", path, rows, issues)


def _audit_pub_duration(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []
    dur_cols = [f"{p} Duration" for p in _PLATFORM_COLS]
    cols     = rows[0].keys() if rows else []
    missing  = [c for c in dur_cols if c not in cols]
    if missing:
        issues.append(_issue("fail", "schema",
                             f"Missing duration columns: {missing[:3]}{'...' if len(missing) > 3 else ''}",
                             "All 8 platform duration columns are required.", len(missing)))
    for col in [c for c in dur_cols if c in (rows[0].keys() if rows else {})]:
        iss = _check_hms(rows, col, n)
        if iss:
            issues.append(iss)
    return _file_summary("channel-wise-publishing-duration.csv", path, rows, issues)


def _audit_video_list(path):
    rows   = _load_csv(path)
    n      = len(rows)
    issues = []

    # Per-field missing
    field_severities = {
        "Video ID"          : "fail",
        "Uploaded By"       : "fail",
        "Team Name"         : "fail",
        "Headline"          : "warn",
        "Type"              : "warn",
        "Published Platform": "warn",
        "Published URL"     : "warn",
    }
    for col, sev in field_severities.items():
        iss = _check_missing(rows, col, n, sev)
        if iss:
            issues.append(iss)

    # Duplicate Video IDs
    ids   = [r.get("Video ID", "").strip() for r in rows if r.get("Video ID", "").strip()]
    seen  = Counter(ids)
    dupes = sum(1 for v, c in seen.items() if c > 1)
    if dupes:
        sample = [v for v, c in seen.items() if c > 1][:5]
        issues.append(_issue("fail", "Video ID",
                             f"{dupes} duplicate Video ID(s)",
                             f"Duplicates may cause double-counting. Sample IDs: {sample}",
                             dupes, _pct(dupes, n)))

    # Duplicate Headlines (non-null)
    hls = [r.get("Headline", "").strip() for r in rows
           if r.get("Headline", "").strip() and not _is_null(r.get("Headline", ""))]
    dup_hl = sum(1 for v, c in Counter(hls).items() if c > 1)
    if dup_hl > n * 0.05:
        issues.append(_issue("warn", "Headline",
                             f"{dup_hl:,} duplicate headline(s)",
                             "Same headline appearing multiple times may mean re-processed clips.",
                             dup_hl, _pct(dup_hl, n)))

    # Published without platform
    pub_rows = [r for r in rows if r.get("Published", "").strip().lower() == "yes"]
    total_p  = len(pub_rows)
    no_plat  = sum(1 for r in pub_rows if _is_null(r.get("Published Platform", "")))
    if no_plat:
        issues.append(_issue("warn", "Published Platform",
                             f"{no_plat}/{total_p} published videos missing platform ({_pct(no_plat, total_p)}%)",
                             "Published videos without a platform cannot appear in platform analytics.",
                             no_plat, _pct(no_plat, total_p)))

    # Published without URL
    no_url = sum(1 for r in pub_rows if _is_null(r.get("Published URL", "")))
    if no_url:
        issues.append(_issue("warn", "Published URL",
                             f"{no_url}/{total_p} published videos missing URL ({_pct(no_url, total_p)}%)",
                             "Published clips without URLs cannot be audited or linked.",
                             no_url, _pct(no_url, total_p)))

    return _file_summary("video_list.csv", path, rows, issues)


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _db_query(sql):
    try:
        con    = duckdb.connect(DATABASE_PATH, read_only=True)
        result = con.execute(sql).fetchall()
        con.close()
        return result
    except Exception:
        return []


def _table_exists(tbl):
    return any(r[0] == tbl for r in _db_query("SHOW TABLES"))


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/data-quality", operation_id="get_data_quality_report")
def get_data_quality():
    """
    Per-file quality audit of all 11 raw CSV files.
    Returns individual file reports plus an overall summary.
    """
    # Return cached result if fresh
    now = _time.time()
    if _DQ_CACHE.get("ts", 0) + _DQ_CACHE_TTL > now:
        return _DQ_CACHE["result"]

    file_reports = []
    errors       = []

    audit_map = [
        ("monthly",       CSV_FILES.get("monthly",      ""), _audit_monthly),
        ("monthly_dur",   CSV_FILES.get("monthly_dur",  ""), _audit_duration),
        ("channels",      CSV_FILES.get("channels",     ""), _audit_channels),
        ("channel_user",  _CHANNEL_USER_PATH,                _audit_channel_user),
        ("users",         CSV_FILES.get("users",        ""), _audit_users),
        ("input_types",   CSV_FILES.get("input_types",  ""), _audit_input_types),
        ("output_types",  CSV_FILES.get("output_types", ""), _audit_output_types),
        ("languages",     CSV_FILES.get("languages",    ""), _audit_languages),
        ("publishing",    CSV_FILES.get("publishing",   ""), _audit_publishing),
        ("pub_duration",  CSV_FILES.get("pub_duration", ""), _audit_pub_duration),
        ("video_list",    CSV_FILES.get("video_list",   ""), _audit_video_list),
    ]

    for key, path, audit_fn in audit_map:
        if not path or not os.path.exists(path):
            errors.append(f"File not found for '{key}': {path}")
            continue
        try:
            report = audit_fn(path)
            file_reports.append(report)
        except Exception as e:
            errors.append(f"Error auditing '{key}': {e}")

    # Overall summary
    total_issues = sum(r["issue_count"] for r in file_reports)
    total_fails  = sum(r["fail_count"]  for r in file_reports)
    total_warns  = sum(r["warn_count"]  for r in file_reports)
    avg_score    = round(sum(r["quality_score"] for r in file_reports) / max(len(file_reports), 1), 1)

    # Last validation timestamp from DB
    last_ran = None
    if _table_exists("validation_results"):
        rows = _db_query("SELECT MAX(ran_at) FROM validation_results")
        if rows and rows[0][0]:
            last_ran = rows[0][0]

    result = {
        "summary": {
            "files_checked"   : len(file_reports),
            "total_issues"    : total_issues,
            "total_fails"     : total_fails,
            "total_warns"     : total_warns,
            "overall_score"   : avg_score,
            "last_validated_at": last_ran,
            "errors"          : errors,
        },
        "files": file_reports,
    }
    _DQ_CACHE["result"] = result
    _DQ_CACHE["ts"]     = _time.time()
    return result


@router.get("/data-quality/checks", operation_id="get_validation_checks")
def get_validation_checks():
    """
    Returns all individual validation check results from the last ETL run.
    Stored in the `validation_results` DuckDB table by run_validation().
    Grouped by file for easy display.
    """
    if not _table_exists("validation_results"):
        return {
            "ran_at": None,
            "total": 0, "pass": 0, "warn": 0, "fail": 0,
            "by_file": {},
            "checks": [],
            "message": "No validation results yet. Save a CSV or call POST /api/etl/run.",
        }

    rows = _db_query("""
        SELECT name, status, message, count, pct, field, tbl, ran_at
        FROM validation_results
        ORDER BY
            CASE status WHEN 'FAIL' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END,
            tbl, name
    """)

    checks = [
        {"name": r[0], "status": r[1], "message": r[2], "count": r[3],
         "pct": r[4], "field": r[5], "table": r[6], "ran_at": r[7]}
        for r in rows
    ]

    # Group by file/table
    by_file = {}
    for c in checks:
        tbl = c["table"] or "other"
        if tbl not in by_file:
            by_file[tbl] = {"pass": 0, "warn": 0, "fail": 0, "checks": []}
        by_file[tbl][c["status"].lower()] += 1
        by_file[tbl]["checks"].append(c)

    ran_at = checks[0]["ran_at"] if checks else None
    # Append Z so JavaScript correctly treats this as UTC (not local time)
    if ran_at and not ran_at.endswith("Z"):
        ran_at = ran_at + "Z"
    return {
        "ran_at" : ran_at,
        "total"  : len(checks),
        "pass"   : sum(1 for c in checks if c["status"] == "PASS"),
        "warn"   : sum(1 for c in checks if c["status"] == "WARN"),
        "fail"   : sum(1 for c in checks if c["status"] == "FAIL"),
        "by_file": by_file,
        "checks" : checks,
    }