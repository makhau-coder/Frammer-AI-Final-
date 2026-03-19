import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Exact column mapping: CSV header → DuckDB column name
COLUMN_MAP = {
    "Headline":           "headline",
    "Source":             "source",
    "Published":          "published",
    "Team Name":          "team_name",
    "Type":               "input_type",   # renamed for clarity
    "Uploaded By":        "uploaded_by",
    "Video ID":           "video_id",
    "Published Platform": "published_platform",
    "Published URL":      "published_url",
}

def _create_table_if_not_exists(duckdb_conn):
    """Create video_list table once. Subsequent calls are no-ops."""
    duckdb_conn.execute("""
        CREATE TABLE IF NOT EXISTS video_list (
            video_id            BIGINT PRIMARY KEY,
            headline            TEXT,
            source              TEXT,
            published           BOOLEAN,
            team_name           TEXT,
            input_type          TEXT,
            uploaded_by         TEXT,
            published_platform  TEXT,
            published_url       TEXT,
            ingested_at         TIMESTAMP DEFAULT now()
        )
    """)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalise the raw video_list dataframe."""

    # 1. Strip whitespace from column names and string values
    df.columns = [c.strip() for c in df.columns]
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

    # 2. Rename columns to clean SQL-safe names
    df = df.rename(columns=COLUMN_MAP)

    # 3. Convert 'Published' Yes/No → True/False boolean
    df["published"] = df["published"].str.upper().map(
        {"YES": True, "NO": False})

    # 4. Drop rows with null video_id — cannot be indexed or tracked
    before = len(df)
    df = df.dropna(subset=["video_id"])
    dropped = before - len(df)
    if dropped > 0:
        logger.warning(f"Dropped {dropped} rows with null video_id")

    # 5. Cast video_id to integer (CSV reads it as float due to nulls)
    df["video_id"] = df["video_id"].astype(int)

    # 6. Deduplicate within the incoming batch itself
    # (we saw duplicate headlines in the raw file — e.g. e86122100123)
    before = len(df)
    df = df.drop_duplicates(subset=["video_id"], keep="first")
    dupes = before - len(df)
    if dupes > 0:
        logger.warning(
            f"Removed {dupes} duplicate video_ids within incoming batch")

    return df


def _get_existing_ids(duckdb_conn) -> set:
    """Fetch all video_ids already in DuckDB as a Python set."""
    result = duckdb_conn.execute("SELECT video_id FROM video_list").fetchall()
    return {row[0] for row in result}


def ingest_incremental(filepath: str, filename: str, duckdb_conn) -> int:
    """
    Only inserts rows whose video_id is not already in the DB.
    Returns count of net new rows inserted.
    """
    _create_table_if_not_exists(duckdb_conn)

    df = pd.read_csv(
        filepath,
        sep=None,
        engine='python',
        encoding='utf-8-sig',
        on_bad_lines='warn',
        dtype={"Video ID": "string"}
    )

    df = _clean(df)

    # Delta detection — filter to only new video_ids
    existing_ids = _get_existing_ids(duckdb_conn)
    new_df = df[~df["video_id"].isin(existing_ids)]

    if new_df.empty:
        logger.info("No new video_ids found — skipping insert.")
        return 0

    # Safe insert using anti-join pattern (avoids DuckDB duplicate constraint bug)
    duckdb_conn.register("_new_videos", new_df)
    duckdb_conn.execute("""
        INSERT INTO video_list
            SELECT DISTINCT ON (video_id)
                video_id, headline, source, published,
                team_name, input_type, uploaded_by,
                published_platform, published_url,
                now()
            FROM _new_videos
    """)
    duckdb_conn.unregister("_new_videos")

    logger.info(f"Inserted {len(new_df)} new rows into video_list.")
    return len(new_df)
