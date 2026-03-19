import pandas as pd
import logging
import re
from ingestion.config import FILE_CONFIG

logger = logging.getLogger(__name__)

# --- Cleaners ---

def _strip_all_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns and column names."""
    df.columns = [c.strip() for c in df.columns]
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())
    return df

def _normalize_channel_col(df: pd.DataFrame) -> pd.DataFrame:
    """Rename 'Channels' → 'Channel' if present."""
    if "Channels" in df.columns:
        df = df.rename(columns={"Channels": "Channel"})
    return df

def _normalize_duration_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert all hh:mm:ss duration columns to total seconds (integer).
    Original string column is kept as _raw for reference.
    """
    duration_cols = [c for c in df.columns if "duration" in c.lower()]
    for col in duration_cols:
        df[col + "_raw"] = df[col]  # preserve original
        df[col + "_secs"] = df[col].apply(_hhmmss_to_secs)
        df = df.drop(columns=[col])
    return df

def _hhmmss_to_secs(value: str) -> int:
    """'137:29:46' → 495586 seconds. Returns 0 for nulls or malformed values."""
    try:
        parts = str(value).strip().split(":")
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except Exception:
        return 0

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Master cleaner — runs all fixes in order."""
    df = _strip_all_strings(df)
    df = _normalize_channel_col(df)
    df = _normalize_duration_cols(df)
    return df

# --- Main Strategy Function ---

def ingest_full_replace(filepath: str, filename: str, duckdb_conn) -> int:
    df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8-sig', on_bad_lines='warn')
    df = _clean(df)

    table_name = (
    filename
    .replace(".csv", "")
    .replace("(", "_")      # ← preserves separator as underscore
    .replace(")", "")
    .replace("-", "_")
    .replace(" ", "_")
    .lower()
    )
    table_name = re.sub(r"_+", "_", table_name).strip("_")
    # ↑ collapses any double/triple underscores from multiple replacements

    # Atomic wipe + reload
    duckdb_conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    duckdb_conn.register("_temp_df", df)
    duckdb_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM _temp_df")
    duckdb_conn.unregister("_temp_df")

    logger.info(f"Table '{table_name}' replaced with {len(df)} rows.")
    return len(df)