"""
etl/cross_parquet.py

Builds all cross-dimension parquet files used by the /api/multidimensional
endpoint.

WHY THIS EXISTS
--------------
The aggregate CSVs (users, channels, input_types …) are pre-summed — they
cannot be joined to each other for cross-dimension analysis.

Cross parquets MUST be built from video-level data, so every row carries all
the dimensions at once, letting us GROUP BY any pair.

TWO DATA SOURCES
----------------
1. video_list.parquet  → uploaded_by, input_type, published_platform,
                         is_published, team_name  (per-video record)
   Supports: user×input_type, user×platform, user×published_status,
             input_type×platform, input_type×published_status

2. channel_user CSV    → channel_name, user_name + full funnel counts/durations
   Supports: channel×user

3. publishing_platform.parquet  (already built by transform_publishing)
   Supports: channel×platform   (no rebuild needed — used directly)

METRICS IN EVERY FILE
---------------------
  created_count      — total output clips (COUNT of rows)
  published_count    — published clips (SUM of is_published)
  publish_rate       — published / created * 100 (rounded 2dp)

CALLED FROM
-----------
  etl/transform.py → run_transform() → step 8.5
  api/etl.py       → POST /api/etl/run  (after transform completes)
"""

import os
import sys
import logging
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import CSV_FILES, COLUMN_MAPPINGS, NULL_EQUIVALENTS, PROCESSED_PATH

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Registry of all cross-dimension files
#
# key   → frozenset of the two dimension names (order-independent)
# value → (output_filename, col1, col2, source)
#           source: "video_list" | "channel_user" | "existing"
# ─────────────────────────────────────────────────────────────────────────────

CROSS_REGISTRY = {
    frozenset({"channel",    "user"})            : ("cross_channel_x_user",               "channel_name",       "user_name",           "channel_user"),
    frozenset({"channel",    "platform"})         : ("publishing_platform",                "channel_name",       "platform",            "existing"),
    frozenset({"user",       "input_type"})       : ("cross_user_x_input_type",            "uploaded_by",        "input_type",          "video_list"),
    frozenset({"user",       "platform"})         : ("cross_user_x_platform",              "uploaded_by",        "published_platform",  "video_list"),
    frozenset({"user",       "published_status"}) : ("cross_user_x_published_status",      "uploaded_by",        "published_status",    "video_list"),
    frozenset({"input_type", "platform"})         : ("cross_input_type_x_platform",        "input_type",         "published_platform",  "video_list"),
    frozenset({"input_type", "published_status"}) : ("cross_input_type_x_published_status","input_type",         "published_status",    "video_list"),
}

# Exposed for the API router
ALL_DIMENSIONS = sorted({d for combo in CROSS_REGISTRY for d in combo})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_video_list() -> pd.DataFrame:
    """
    Load video_list.parquet (written by transform.py step 8).
    Adds a string 'published_status' column so cross tables can label it
    clearly rather than using True/False booleans.
    """
    path = os.path.join(PROCESSED_PATH, "video_list.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"video_list.parquet not found at {path}. "
            "Run the ETL pipeline first (etl/main.py)."
        )
    df = pd.read_parquet(path)

    # Normalise boolean → readable string for published_status crosses
    if "is_published" in df.columns:
        df["published_status"] = df["is_published"].map(
            {True: "Published", False: "Not Published", 1: "Published", 0: "Not Published"}
        ).fillna("Unknown")

    return df


def _load_channel_user() -> pd.DataFrame:
    """
    Load and normalise the channel × user CSV.
    Returns a DataFrame with:
        channel_name, user_name,
        uploaded_count, created_count, published_count,
        uploaded_mins, created_mins, published_mins,
        publish_rate, unpublished_gap
    """
    path = CSV_FILES.get("channel_user") or CSV_FILES.get("channels")

    # Try the channel_user key first; fall back to the combined_data by channel & user file
    channel_user_path = CSV_FILES.get(
        "channel_user",
        os.path.join(
            os.path.dirname(CSV_FILES.get("channels", "")),
            "combined_data(2025-3-1-2026-2-28) by channel and user.csv",
        ),
    )

    if not os.path.exists(channel_user_path):
        raise FileNotFoundError(
            f"Channel-user CSV not found at {channel_user_path}."
        )

    df = pd.read_csv(channel_user_path, encoding="utf-8")

    # Standardise column names
    rename_map = {k: v for k, v in COLUMN_MAPPINGS.items() if k in df.columns}
    # Also handle the Channel/User columns specifically
    rename_map.update({
        "Channel": "channel_name",
        "User": "user_name",
    })
    df = df.rename(columns=rename_map)
    df = df.replace(NULL_EQUIVALENTS, np.nan)

    # Parse duration strings to minutes
    for dur_col, min_col in [
        ("uploaded_duration", "uploaded_mins"),
        ("created_duration", "created_mins"),
        ("published_duration", "published_mins"),
    ]:
        if dur_col in df.columns:
            df[min_col] = df[dur_col].apply(_hms_to_minutes)
            df = df.drop(columns=[dur_col])

    # Cast counts to int
    for col in ["uploaded_count", "created_count", "published_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Compute KPIs
    c = df.get("created_count", pd.Series(dtype=float))
    p = df.get("published_count", pd.Series(dtype=float))
    df["publish_rate"]    = (p / c.replace(0, np.nan) * 100).round(2)
    df["unpublished_gap"] = (c - p).fillna(0).astype(int)

    return df


def _hms_to_minutes(value) -> float:
    """Convert h:mm:ss / hh:mm:ss / mm:ss string → decimal minutes."""
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


def _aggregate_video_list(df: pd.DataFrame, col1: str, col2: str) -> pd.DataFrame:
    """
    Aggregate video_list rows by (col1, col2) to produce funnel metrics.

    Metrics produced:
        created_count   — number of output clips (each row = 1 clip)
        published_count — clips that were published
        publish_rate    — published / created * 100
        unpublished_gap — created - published
    """
    if col1 not in df.columns or col2 not in df.columns:
        raise KeyError(
            f"Columns '{col1}' or '{col2}' not found in video_list. "
            f"Available: {df.columns.tolist()}"
        )

    grp = (
        df[[col1, col2, "is_published"]]
        .dropna(subset=[col1, col2])
        .assign(is_published=lambda d: d["is_published"].astype(int))
        .groupby([col1, col2], as_index=False)
        .agg(
            created_count=("is_published", "count"),
            published_count=("is_published", "sum"),
        )
    )
    grp["publish_rate"]    = (grp["published_count"] / grp["created_count"].replace(0, np.nan) * 100).round(2)
    grp["unpublished_gap"] = grp["created_count"] - grp["published_count"]

    return grp.sort_values([col1, col2]).reset_index(drop=True)


def _aggregate_channel_user(df: pd.DataFrame, col1: str, col2: str) -> pd.DataFrame:
    """
    Channel×user data is already aggregated in the CSV.
    Just select and return the relevant columns.
    """
    base_cols = [col1, col2, "uploaded_count", "created_count",
                 "published_count", "publish_rate", "unpublished_gap"]
    dur_cols  = [c for c in ["uploaded_mins", "created_mins", "published_mins"]
                 if c in df.columns]
    keep = [c for c in base_cols + dur_cols if c in df.columns]

    return (
        df[keep]
        .dropna(subset=[col1, col2])
        .sort_values([col1, col2])
        .reset_index(drop=True)
    )


def _save(df: pd.DataFrame, name: str) -> None:
    os.makedirs(PROCESSED_PATH, exist_ok=True)
    path = os.path.join(PROCESSED_PATH, f"{name}.parquet")
    df.to_parquet(path, index=False)
    logger.info(f"[cross_parquet] Saved {name}.parquet  ({len(df)} rows)")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def build_cross_parquets(force: bool = False) -> dict:
    """
    Build (or rebuild) all cross-dimension parquet files.

    Args:
        force: If False, skip files that already exist (faster restart).
               If True, always rebuild (use after new data lands).

    Returns:
        dict  {filename: status_string}  — useful for logging / ETL status.
    """
    results = {}

    # Load sources lazily — only if needed
    video_df       = None
    channel_user_df = None

    for dims, (file_name, col1, col2, source) in CROSS_REGISTRY.items():
        path = os.path.join(PROCESSED_PATH, f"{file_name}.parquet")

        # Skip if exists and force=False
        if not force and os.path.exists(path):
            logger.info(f"[cross_parquet] SKIP {file_name}.parquet (exists, force=False)")
            results[file_name] = "skipped"
            continue

        try:
            if source == "existing":
                # publishing_platform.parquet is built by transform_publishing() — skip here
                if os.path.exists(path):
                    results[file_name] = "existing"
                    continue
                else:
                    logger.warning(f"[cross_parquet] {file_name}.parquet does not exist yet — run full ETL")
                    results[file_name] = "missing"
                    continue

            elif source == "video_list":
                if video_df is None:
                    video_df = _load_video_list()
                df = _aggregate_video_list(video_df, col1, col2)

            elif source == "channel_user":
                if channel_user_df is None:
                    channel_user_df = _load_channel_user()
                df = _aggregate_channel_user(channel_user_df, col1, col2)

            else:
                logger.error(f"[cross_parquet] Unknown source '{source}' for {file_name}")
                results[file_name] = f"error: unknown source {source}"
                continue

            _save(df, file_name)
            results[file_name] = f"ok ({len(df)} rows)"

        except Exception as exc:
            logger.error(f"[cross_parquet] FAILED {file_name}: {exc}", exc_info=True)
            results[file_name] = f"error: {exc}"

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Standalone run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pprint
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Building cross parquets …")
    r = build_cross_parquets(force=True)
    pprint.pprint(r)
