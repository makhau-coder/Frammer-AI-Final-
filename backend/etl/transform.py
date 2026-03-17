"""
etl/transform.py — ETL Layer 3: Clean, enrich, and write processed outputs

Steps:
  1. Transform aggregate CSVs (users, channels, input_types, output_types, languages)
  2. Build monthly time-series (counts + durations merged)
  3. Build publishing platform breakdown (long format)
  4. Clean video list
  5. Load star schema (with fixed dim_date from real monthly data)
  6. Fix null input_type_id rows in fact_video
  7. Apportion user-level durations to individual fact rows
  8. Write summary_stats table to DuckDB
  9. Write processed Parquet files
 10. Build cross-dimension Parquet files

Run standalone:
    python etl/transform.py

Or import:
    from etl.transform import run_transform
    run_transform(con)
"""

import os
import sys

import duckdb
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import (
    CSV_FILES,
    COLUMN_MAPPINGS,
    DATABASE_PATH,
    NULL_EQUIVALENTS,
    PROCESSED_PATH,
    QA_ACCOUNTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load(key: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_FILES[key], encoding="utf-8")
    df = df.rename(columns={k: v for k, v in COLUMN_MAPPINGS.items() if k in df.columns})
    df = df.replace(NULL_EQUIVALENTS, np.nan)
    return df


def _hms_to_minutes(value) -> float:
    """Convert h:mm:ss or hh:mm:ss (or mm:ss) string → decimal minutes."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    try:
        parts = str(value).strip().split(":")
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return round(h * 60 + m + s / 60, 4)
        if len(parts) == 2:
            m, s = int(parts[0]), float(parts[1])
            return round(m + s / 60, 4)
    except (ValueError, TypeError):
        pass
    return 0.0


def _add_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add publish_rate, multiplication_ratio, unpublished_gap columns.
    Works on any DataFrame with uploaded_count, created_count, published_count.
    """
    df = df.copy()
    u = pd.to_numeric(df.get("uploaded_count", 0), errors="coerce").fillna(0)
    c = pd.to_numeric(df.get("created_count",  0), errors="coerce").fillna(0)
    p = pd.to_numeric(df.get("published_count", 0), errors="coerce").fillna(0)

    df["publish_rate"]         = (p / c.replace(0, np.nan) * 100).round(2)
    df["multiplication_ratio"] = (c / u.replace(0, np.nan)).round(4)
    df["unpublished_gap"]      = (c - p).astype(int)
    return df


def _ensure_processed_dir() -> None:
    os.makedirs(PROCESSED_PATH, exist_ok=True)


def _save(df: pd.DataFrame, name: str) -> None:
    """Write a DataFrame to data/processed/<name>.parquet"""
    _ensure_processed_dir()
    path = os.path.join(PROCESSED_PATH, f"{name}.parquet")
    df.to_parquet(path, index=False)
    print(f"       saved → data/processed/{name}.parquet  ({len(df)} rows)")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Aggregate CSV transforms
# ─────────────────────────────────────────────────────────────────────────────

_DIM_DURATION_COLS = {
    "uploaded_duration" : "uploaded_mins",
    "created_duration"  : "created_mins",
    "published_duration": "published_mins",
}


def _transform_aggregate(key: str) -> pd.DataFrame:
    """
    Generic transform for users / channels / input_types / output_types / languages.
    - Converts duration strings to minutes
    - Casts count cols to int
    - Adds KPI columns
    """
    df = _load(key)
    for src, dst in _DIM_DURATION_COLS.items():
        if src in df.columns:
            df[dst] = df[src].apply(_hms_to_minutes)
            df = df.drop(columns=[src])

    for col in ["uploaded_count", "created_count", "published_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    df = _add_kpis(df)
    return df


def transform_users()        -> pd.DataFrame: return _transform_aggregate("users")
def transform_channels()     -> pd.DataFrame: return _transform_aggregate("channels")
def transform_input_types()  -> pd.DataFrame: return _transform_aggregate("input_types")
def transform_output_types() -> pd.DataFrame: return _transform_aggregate("output_types")
def transform_languages()    -> pd.DataFrame: return _transform_aggregate("languages")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Monthly time-series
# ─────────────────────────────────────────────────────────────────────────────

_MONTH_ORDER = {
    "jan": 1, "feb": 2, "mar": 3,  "apr": 4,
    "may": 5, "jun": 6, "jul": 7,  "aug": 8,
    "sep": 9, "oct": 10,"nov": 11, "dec": 12,
}


def _parse_month_label(label: str):
    """'Apr, 2025' → (month_number=4, year=2025, sort_key=202504)"""
    label = str(label).strip().rstrip(",")
    parts = label.replace(",", "").split()
    if len(parts) == 2:
        abbr = parts[0][:3].lower()
        try:
            year = int(parts[1])
        except ValueError:
            year = 0
        month_num = _MONTH_ORDER.get(abbr, 0)
        sort_key  = year * 100 + month_num
        return month_num, year, sort_key
    return 0, 0, 0


def transform_monthly() -> pd.DataFrame:
    """
    Merge monthly-chart.csv (counts) + month-wise-duration.csv (durations),
    standardise the month label, and sort chronologically.
    """
    counts = _load("monthly").rename(columns={
        "Total Uploaded" : "uploaded_count",
        "Total Created"  : "created_count",
        "Total Published": "published_count",
    })
    durs = _load("monthly_dur").rename(columns={
        "Total Uploaded Duration" : "uploaded_duration",
        "Total Created Duration"  : "created_duration",
        "Total Published Duration": "published_duration",
    })

    df = counts.merge(durs, on="month", how="left")

    for src, dst in _DIM_DURATION_COLS.items():
        if src in df.columns:
            df[dst] = df[src].apply(_hms_to_minutes)
            df = df.drop(columns=[src])

    for col in ["uploaded_count", "created_count", "published_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    parsed = df["month"].apply(_parse_month_label)
    df["month_number"] = parsed.apply(lambda t: t[0])
    df["year"]         = parsed.apply(lambda t: t[1])
    df["sort_key"]     = parsed.apply(lambda t: t[2])
    df = df.sort_values("sort_key").drop(columns=["sort_key"]).reset_index(drop=True)

    df = _add_kpis(df)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. Publishing platform breakdown (long format)
# ─────────────────────────────────────────────────────────────────────────────

_PLATFORM_COLS = ["Facebook", "Instagram", "Linkedin", "Reels", "Shorts", "X", "Youtube", "Threads"]


def transform_publishing() -> pd.DataFrame:
    """
    Melt channel × platform count + duration into long format:
        channel_name | platform | publish_count | published_mins
    """
    counts = _load("publishing").rename(columns={"Channels": "channel_name"})
    durs   = _load("pub_duration").rename(columns={"Channels": "channel_name"})

    count_long = counts.melt(
        id_vars="channel_name",
        value_vars=[c for c in _PLATFORM_COLS if c in counts.columns],
        var_name="platform",
        value_name="publish_count",
    )

    dur_rename = {f"{p} Duration": p for p in _PLATFORM_COLS}
    durs = durs.rename(columns=dur_rename)
    dur_long = durs.melt(
        id_vars="channel_name",
        value_vars=[c for c in _PLATFORM_COLS if c in durs.columns],
        var_name="platform",
        value_name="published_duration",
    )
    dur_long["published_mins"] = dur_long["published_duration"].apply(_hms_to_minutes)
    dur_long = dur_long.drop(columns=["published_duration"])

    df = count_long.merge(dur_long, on=["channel_name", "platform"], how="left")
    df["publish_count"] = pd.to_numeric(df["publish_count"], errors="coerce").fillna(0).astype(int)

    df = df[(df["publish_count"] > 0) | (df["published_mins"] > 0)].reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. Video list clean
# ─────────────────────────────────────────────────────────────────────────────

def transform_video_list() -> pd.DataFrame:
    """Clean the video_list CSV."""
    df = _load("video_list")

    df = df.rename(columns={
        "Video ID"          : "video_id",
        "Headline"          : "headline",
        "Uploaded By"       : "uploaded_by",
        "Type"              : "input_type",
        "Published"         : "is_published",
        "Published Platform": "published_platform",
        "Published URL"     : "published_url",
        "Team Name"         : "team_name",
        "Source"            : "source",
    })

    df["input_type"] = df["input_type"].fillna("unknown")
    df = df.drop_duplicates(subset=["video_id"])

    df["is_published"] = (
        df["is_published"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["yes", "true", "1"])
    )

    df["published_platform"] = df["published_platform"].fillna("Not Published")
    df["team_name"]          = df["team_name"].fillna("Unknown")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. Star schema loader  (FIX: dim_date built from real monthly data)
# ─────────────────────────────────────────────────────────────────────────────

def load_star_schema(con: duckdb.DuckDBPyConnection, video_df: pd.DataFrame) -> None:

    print("\n      Loading star schema tables ...")

    # ── dim_user ──────────────────────────────────────────────────────────────
    users = (
        video_df[["uploaded_by"]]
        .drop_duplicates()
        .reset_index(drop=True)
        .rename(columns={"uploaded_by": "user_name"})
    )
    users["user_id"] = users.index + 1

    # FIX: use exact match instead of str.contains to avoid false positives
    qa_lower = {q.lower() for q in QA_ACCOUNTS}
    users["is_qa_account"] = users["user_name"].str.lower().isin(qa_lower)

    con.execute("DELETE FROM dim_user")
    con.register("users_df", users)
    con.execute("INSERT INTO dim_user SELECT user_id, user_name, is_qa_account FROM users_df")

    # ── dim_input_type ────────────────────────────────────────────────────────
    inputs = (
        video_df[["input_type"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    inputs["input_type_id"] = inputs.index + 1

    con.execute("DELETE FROM dim_input_type")
    con.register("inputs_df", inputs)
    con.execute("INSERT INTO dim_input_type SELECT input_type_id, input_type FROM inputs_df")

    # ── dim_platform ──────────────────────────────────────────────────────────
    platforms = (
        video_df[["published_platform"]]
        .drop_duplicates()
        .reset_index(drop=True)
        .rename(columns={"published_platform": "platform_name"})
    )
    platforms["platform_id"] = platforms.index + 1

    con.execute("DELETE FROM dim_platform")
    con.register("platforms_df", platforms)
    con.execute("INSERT INTO dim_platform SELECT platform_id, platform_name FROM platforms_df")

    # ── dim_team ──────────────────────────────────────────────────────────────
    teams = (
        video_df[["team_name"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    teams["team_id"] = teams.index + 1

    con.execute("DELETE FROM dim_team")
    con.register("teams_df", teams)
    con.execute("INSERT INTO dim_team SELECT team_id, team_name FROM teams_df")

    # ── dim_date  FIX: build from real monthly data, not just today ───────────
    monthly_df = transform_monthly()
    dates = monthly_df[["month", "year", "month_number"]].drop_duplicates().copy()
    dates["date_id"] = range(1, len(dates) + 1)
    dates["quarter"] = dates["month_number"].apply(lambda m: (int(m) - 1) // 3 + 1)

    con.execute("DELETE FROM dim_date")
    con.register("dates_df", dates)
    con.execute("""
        INSERT INTO dim_date
        SELECT date_id, month, year, month_number, quarter
        FROM dates_df
    """)

    # ── fact_video ────────────────────────────────────────────────────────────
    fact = video_df.copy()

    fact["uploaded_count"]       = 1
    fact["created_count"]        = 1
    fact["published_count"]      = fact["is_published"].astype(int)
    fact["uploaded_mins"]        = 0.0
    fact["created_mins"]         = 0.0
    fact["published_mins"]       = 0.0
    fact["publish_rate"]         = fact["published_count"].astype(float) * 100
    fact["multiplication_ratio"] = 1.0
    fact["unpublished_gap"]      = (1 - fact["published_count"]).astype(int)

    # FIX: use exact isin match for QA exclusion (was str.contains — false positives)
    fact = fact[~fact["uploaded_by"].str.lower().isin(qa_lower)]

    # join dimension keys
    fact = fact.merge(users,     left_on="uploaded_by",       right_on="user_name",    how="left")
    fact = fact.merge(inputs,    on="input_type",                                       how="left")
    fact = fact.merge(platforms, left_on="published_platform", right_on="platform_name", how="left")
    fact = fact.merge(teams,     on="team_name",                                        how="left")

    # attach a date_id — use a simple default (date_id=1) since we have no
    # per-video upload timestamp in the dataset; month-level analysis uses
    # the monthly parquet, not fact_video joins
    fact["date_id"] = 1

    con.execute("DELETE FROM fact_video")
    con.register("fact_df", fact)
    con.execute("""
        INSERT INTO fact_video
        SELECT
            video_id,
            headline,
            user_id,
            input_type_id,
            platform_id,
            team_id,
            date_id,
            uploaded_count,
            created_count,
            published_count,
            uploaded_mins,
            created_mins,
            published_mins,
            is_published,
            published_url,
            publish_rate,
            multiplication_ratio,
            unpublished_gap
        FROM fact_df
    """)

    print("      Star schema loaded successfully.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Fix null input_type_id rows
# ─────────────────────────────────────────────────────────────────────────────

def fix_null_input_types(con: duckdb.DuckDBPyConnection) -> int:
    existing = con.execute(
        "SELECT input_type_id FROM dim_input_type WHERE LOWER(input_type_name) = 'unknown'"
    ).fetchone()

    if existing:
        unknown_id = existing[0]
    else:
        max_id = con.execute("SELECT COALESCE(MAX(input_type_id), 0) FROM dim_input_type").fetchone()[0]
        unknown_id = max_id + 1
        con.execute(
            "INSERT INTO dim_input_type (input_type_id, input_type_name) VALUES (?, ?)",
            [unknown_id, "unknown"],
        )

    updated = con.execute(
        "SELECT COUNT(*) FROM fact_video WHERE input_type_id IS NULL"
    ).fetchone()[0]
    con.execute(
        "UPDATE fact_video SET input_type_id = ? WHERE input_type_id IS NULL",
        [unknown_id],
    )
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# 7. Apportion user durations to fact rows
# ─────────────────────────────────────────────────────────────────────────────

def apportion_user_durations(con: duckdb.DuckDBPyConnection, users_df: pd.DataFrame) -> int:
    """
    Distribute per-user aggregate durations to individual fact_video rows.
    Strategy: per_video = total_user_duration / user_video_count (approximation).
    """
    user_totals = users_df.set_index("user_name")[
        ["uploaded_mins", "created_mins", "published_mins"]
    ].to_dict(orient="index")

    rows = con.execute("""
        SELECT u.user_name, COUNT(*) as cnt, SUM(f.is_published::INT) as pub_cnt
        FROM fact_video f
        JOIN dim_user u ON f.user_id = u.user_id
        GROUP BY u.user_name
    """).fetchall()

    updated = 0
    for user_name, cnt, pub_cnt in rows:
        totals = user_totals.get(user_name)
        if not totals or cnt == 0:
            continue

        per_uploaded  = round(totals["uploaded_mins"]  / cnt, 4)
        per_created   = round(totals["created_mins"]   / cnt, 4)
        per_published = round(totals["published_mins"] / pub_cnt, 4) if pub_cnt > 0 else 0.0

        con.execute("""
            UPDATE fact_video
            SET uploaded_mins = ?,
                created_mins  = ?
            WHERE user_id = (SELECT user_id FROM dim_user WHERE user_name = ?)
        """, [per_uploaded, per_created, user_name])

        con.execute("""
            UPDATE fact_video
            SET published_mins = ?
            WHERE is_published = TRUE
              AND user_id = (SELECT user_id FROM dim_user WHERE user_name = ?)
        """, [per_published, user_name])

        updated += cnt

    return updated


# ─────────────────────────────────────────────────────────────────────────────
# 8. Summary stats table
# ─────────────────────────────────────────────────────────────────────────────

def write_summary_stats(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create (or replace) the summary_stats table with all pre-computed KPIs.
    """
    channels_df = _load("channels")
    users_df    = _load("users")
    langs_df    = _load("languages")
    monthly_df  = _load("monthly")
    pub_dur_df  = _load("pub_duration")
    vl_df       = pd.read_csv(CSV_FILES["video_list"], encoding="utf-8")

    def _to_hours(val):
        if pd.isna(val) or str(val).strip() == "":
            return 0.0
        try:
            p = str(val).strip().split(":")
            if len(p) == 3:
                return int(p[0]) + int(p[1]) / 60 + float(p[2]) / 3600
            if len(p) == 2:
                return int(p[0]) / 60 + float(p[1]) / 3600
        except (ValueError, TypeError):
            pass
        return 0.0

    def _to_secs(val):
        return round(_to_hours(val) * 3600, 2)

    # rename columns
    channels_df = channels_df.rename(columns=COLUMN_MAPPINGS)
    users_df    = users_df.rename(columns=COLUMN_MAPPINGS)
    langs_df    = langs_df.rename(columns=COLUMN_MAPPINGS)

    total_uploaded  = int(channels_df["uploaded_count"].sum())
    total_created   = int(channels_df["created_count"].sum())
    total_published = int(channels_df["published_count"].sum())

    global_publish_rate       = round(total_published / total_created * 100, 2)
    upload_to_publish_conv    = round(total_published / total_uploaded * 100, 2)
    ai_compute_waste_rate     = round(100 - global_publish_rate, 2)
    total_server_compute_hrs  = round(channels_df["created_duration"].apply(_to_hours).sum(), 2)
    total_published_hrs       = round(channels_df["published_duration"].apply(_to_hours).sum(), 4)
    avg_compute_cost_per_pub  = round(total_created / total_published, 2)
    ai_content_multiplier     = round(total_created / total_uploaded, 2)

    # Language KPIs
    en_row = langs_df[langs_df["language"] == "en"]
    hi_row = langs_df[langs_df["language"] == "hi"]

    if len(en_row) and len(hi_row):
        en_pub_rate = round(en_row.iloc[0]["published_count"] / en_row.iloc[0]["created_count"] * 100, 2)
        hi_pub_rate = round(hi_row.iloc[0]["published_count"] / hi_row.iloc[0]["created_count"] * 100, 2)
        en_hi_efficacy_multiplier = round(en_pub_rate / max(hi_pub_rate, 0.001), 2)
        en_gen_cost = round(en_row.iloc[0]["created_count"] / max(en_row.iloc[0]["published_count"], 1), 0)
        hi_gen_cost = round(hi_row.iloc[0]["created_count"] / max(hi_row.iloc[0]["published_count"], 1), 0)
    else:
        en_pub_rate = hi_pub_rate = en_hi_efficacy_multiplier = en_gen_cost = hi_gen_cost = 0.0

    # Channel health
    total_channels    = len(channels_df)
    dead_channels     = int((channels_df["published_count"] == 0).sum())
    active_channels   = total_channels - dead_channels
    dead_channel_pct  = round(dead_channels / total_channels * 100, 2)
    active_channel_ratio = round(active_channels / total_channels * 100, 2)

    # FIX: use isin for QA exclusion
    qa_lower = {q.lower() for q in QA_ACCOUNTS}
    non_qa = users_df[~users_df["user_name"].str.lower().isin(qa_lower)]
    zero_value_users = int((non_qa["published_count"] == 0).sum())

    channels_df = channels_df.copy()
    channels_df["ch_pub_rate"] = (
        channels_df["published_count"] / channels_df["created_count"].replace(0, np.nan) * 100
    ).round(2)
    best_ch_row               = channels_df.loc[channels_df["ch_pub_rate"].idxmax()]
    best_channel_name         = str(best_ch_row["channel_name"])
    best_channel_publish_rate = float(best_ch_row["ch_pub_rate"])

    ch_a = channels_df[channels_df["channel_name"] == "A"]
    ch_a_contribution_pct = round(
        float(ch_a["published_count"].values[0]) / total_published * 100, 2
    ) if len(ch_a) else 0.0

    top_vol_user  = non_qa.loc[non_qa["uploaded_count"].idxmax(), "user_name"]
    non_qa_pub    = non_qa[non_qa["published_count"] > 0].copy()
    non_qa_pub["eff_rate"] = (non_qa_pub["published_count"] / non_qa_pub["created_count"] * 100).round(2)
    best_eff_user     = non_qa_pub.loc[non_qa_pub["eff_rate"].idxmax(), "user_name"]
    best_eff_pub_rate = float(non_qa_pub["eff_rate"].max())

    avg_monthly_uploads   = round(float(monthly_df["Total Uploaded"].mean()), 2)
    avg_monthly_created   = round(float(monthly_df["Total Created"].mean()), 2)
    avg_monthly_published = round(float(monthly_df["Total Published"].mean()), 2)

    peak_wl_idx         = monthly_df["Total Created"].idxmax()
    peak_workload_month = str(monthly_df.loc[peak_wl_idx, "month"])
    peak_workload_clips = int(monthly_df.loc[peak_wl_idx, "Total Created"])
    peak_slice_ratio    = round(
        monthly_df.loc[peak_wl_idx, "Total Created"] /
        monthly_df.loc[peak_wl_idx, "Total Uploaded"], 2)

    peak_val_idx         = monthly_df["Total Published"].idxmax()
    peak_value_month     = str(monthly_df.loc[peak_val_idx, "month"])
    peak_value_pub_count = int(monthly_df.loc[peak_val_idx, "Total Published"])

    dec_row = monthly_df[monthly_df["month"].str.contains("Dec", na=False)]
    feb_row = monthly_df[monthly_df["month"].str.contains("Feb", na=False)]
    dec_uploads = int(dec_row["Total Uploaded"].values[0]) if len(dec_row) else 0
    feb_uploads = int(feb_row["Total Uploaded"].values[0]) if len(feb_row) else 0
    dec_to_feb_upload_surge_pct = round(
        (feb_uploads - dec_uploads) / dec_uploads * 100, 1) if dec_uploads else 0.0

    youtube_workload_secs = round(pub_dur_df["Youtube Duration"].apply(_to_secs).sum(), 0)

    total_vl_rows = len(vl_df)
    unknown_mask  = (
        vl_df["Team Name"].isna() |
        vl_df["Team Name"].isin(["Unknown", "unknown", "", "None", "N/A", "none"])
    )
    unknown_team_pct = round(unknown_mask.sum() / total_vl_rows * 100, 2)

    con.execute("DROP TABLE IF EXISTS summary_stats")
    con.execute("""
        CREATE TABLE summary_stats (
            total_uploaded              INTEGER,
            total_ai_generated_clips    INTEGER,
            total_published_clips       INTEGER,
            global_publish_rate         DOUBLE,
            upload_to_publish_conv_rate DOUBLE,
            ai_compute_waste_rate       DOUBLE,
            total_server_compute_hrs    DOUBLE,
            total_published_hrs         DOUBLE,
            avg_compute_cost_per_pub    DOUBLE,
            ai_content_multiplier       DOUBLE,
            en_hi_efficacy_multiplier   DOUBLE,
            en_publish_rate             DOUBLE,
            hi_publish_rate             DOUBLE,
            en_gen_cost                 DOUBLE,
            hi_gen_cost                 DOUBLE,
            dead_channel_pct            DOUBLE,
            zero_value_users            INTEGER,
            best_channel_name           VARCHAR,
            best_channel_publish_rate   DOUBLE,
            ch_a_contribution_pct       DOUBLE,
            active_channel_ratio        DOUBLE,
            top_volume_user             VARCHAR,
            best_efficiency_user        VARCHAR,
            best_efficiency_pub_rate    DOUBLE,
            avg_monthly_uploads         DOUBLE,
            avg_monthly_created         DOUBLE,
            avg_monthly_published       DOUBLE,
            peak_workload_month         VARCHAR,
            peak_workload_clips         INTEGER,
            peak_slice_ratio            DOUBLE,
            peak_value_month            VARCHAR,
            peak_value_pub_count        INTEGER,
            dec_to_feb_upload_surge_pct DOUBLE,
            youtube_workload_secs       DOUBLE,
            unknown_team_attribution_pct DOUBLE
        )
    """)
    con.execute("""
        INSERT INTO summary_stats VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
    """, [
        total_uploaded, total_created, total_published,
        global_publish_rate, upload_to_publish_conv, ai_compute_waste_rate,
        total_server_compute_hrs, total_published_hrs,
        avg_compute_cost_per_pub, ai_content_multiplier,
        en_hi_efficacy_multiplier, en_pub_rate, hi_pub_rate,
        en_gen_cost, hi_gen_cost,
        dead_channel_pct, zero_value_users,
        best_channel_name, best_channel_publish_rate, ch_a_contribution_pct,
        active_channel_ratio,
        top_vol_user, best_eff_user, best_eff_pub_rate,
        avg_monthly_uploads, avg_monthly_created, avg_monthly_published,
        peak_workload_month, peak_workload_clips, peak_slice_ratio,
        peak_value_month, peak_value_pub_count, dec_to_feb_upload_surge_pct,
        youtube_workload_secs,
        unknown_team_pct,
    ])




# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_transform(con: duckdb.DuckDBPyConnection = None) -> None:
    close_after = con is None
    if con is None:
        con = duckdb.connect(DATABASE_PATH)

    print("=" * 60)
    print("  FRAMMER ANALYTICS — ETL TRANSFORM")
    print("=" * 60)

    # 1. Aggregate CSVs
    print("\n[1/9]  Transforming aggregate CSVs …")
    users_df        = transform_users()
    channels_df     = transform_channels()
    input_types_df  = transform_input_types()
    output_types_df = transform_output_types()
    languages_df    = transform_languages()
    print(f"       users={len(users_df)}  channels={len(channels_df)}  "
          f"input_types={len(input_types_df)}  output_types={len(output_types_df)}  "
          f"languages={len(languages_df)}")

    # 2. Monthly
    print("\n[2/9]  Building monthly time-series …")
    monthly_df = transform_monthly()
    print(f"       {len(monthly_df)} months  "
          f"({monthly_df['month'].iloc[0]} → {monthly_df['month'].iloc[-1]})")

    # 3. Publishing breakdown
    print("\n[3/9]  Building publishing platform breakdown …")
    publishing_df = transform_publishing()
    print(f"       {len(publishing_df)} active channel × platform combinations")

    # 4. Video list
    print("\n[4/9]  Cleaning video list …")
    video_df = transform_video_list()
    null_remaining = video_df["input_type"].isna().sum() if "input_type" in video_df.columns else 0
    print(f"       {len(video_df)} rows loaded  |  null input_type remaining: {null_remaining}")

    # 5. Star schema
    load_star_schema(con, video_df)

    # 6. Fix null input types
    print("\n[5/9]  Fixing null input_type_id in fact_video …")
    updated = fix_null_input_types(con)
    print(f"       {updated} row(s) updated")

    # 7. Apportion durations
    print("\n[6/9]  Apportioning user durations to fact_video …")
    if users_df is not None and len(users_df) > 0:
        n = apportion_user_durations(con, users_df)
        print(f"       Duration columns updated for {n} fact rows")
    else:
        print("       Skipped duration apportioning (users_df empty)")

    # 8. Summary stats
    print("\n[7/9]  Writing summary_stats table to DuckDB …")
    write_summary_stats(con)
    stats = con.execute("SELECT * FROM summary_stats").fetchdf()
    print(f"       total_uploaded={stats['total_uploaded'].iloc[0]:,}  "
          f"publish_rate={stats['global_publish_rate'].iloc[0]}%  "
          f"compute_hrs={stats['total_server_compute_hrs'].iloc[0]}")

    con.commit()

    # 9. Write processed Parquet files
    print("\n[8/9]  Writing processed Parquet files …")
    _save(users_df,        "users")
    _save(channels_df,     "channels")
    _save(input_types_df,  "input_types")
    _save(output_types_df, "output_types")
    _save(languages_df,    "languages")
    _save(monthly_df,      "monthly")
    _save(publishing_df,   "publishing_platform")
    _save(video_df,        "video_list")

    # 10. Cross-dimension Parquets
    print("\n[9/9]  Building cross-dimension parquets …")
    from etl.cross_parquet import build_cross_parquets
    cross_results = build_cross_parquets(force=True)
    for name, status in cross_results.items():
        print(f"       {name}: {status}")

    if close_after:
        con.close()

    print("\n✅  Transform complete.\n")


if __name__ == "__main__":
    run_transform()
