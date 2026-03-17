import os
import logging
from ingestion.registry import FileRegistry
from ingestion.router import route_file
from ingestion.config import FILE_CONFIG

logger = logging.getLogger(__name__)

def run_backfill(watch_dir: str, registry: FileRegistry, duckdb_conn, force: bool = False):
    """
    On startup: process all known CSVs in watch_dir.
    
    force=False (normal restart) → still skips files whose hash matches registry
                                   (avoids reload if DB is intact and file unchanged)
    force=True  (--reset)        → ignores registry entirely, wipes + reloads everything
    """
    csv_files = [f for f in os.listdir(watch_dir) if f.endswith(".csv")]

    if not csv_files:
        logger.warning(f"No CSV files found in {watch_dir} — nothing to backfill.")
        return

    logger.info(f"Starting backfill — {len(csv_files)} CSV(s) found in {watch_dir}")

    # Separate known vs unknown files
    known   = [f for f in csv_files if f in FILE_CONFIG]
    unknown = [f for f in csv_files if f not in FILE_CONFIG]

    if unknown:
        logger.warning(f"UNKNOWN files — skipped (not in FILE_CONFIG): {unknown}")

    success, skipped, failed = 0, 0, 0

    for filename in known:
        filepath = os.path.join(watch_dir, filename)
        try:
            current_hash = registry.compute_hash(filepath)

            if not force and not registry.has_changed(filename, current_hash):
                # DB is intact and file hasn't changed since last run — safe to skip
                logger.info(f"SKIP {filename} — hash unchanged, DB already in sync")
                skipped += 1
                continue

            logger.info(f"BACKFILL {filename} ({'forced' if force else 'hash changed or new'})")
            row_count = route_file(filepath, filename, duckdb_conn)
            registry.update(filename, current_hash, row_count, "success")
            logger.info(f"OK {filename} → {row_count} rows")
            success += 1

        except Exception as e:
            logger.error(f"FAILED {filename}: {e}")
            registry.update(filename, "", 0, "failed")
            failed += 1

    logger.info(
        f"Backfill complete — "
        f"{success} loaded | {skipped} skipped | {failed} failed"
    )
