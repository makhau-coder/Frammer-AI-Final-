import os
import time
import threading
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ingestion.registry import FileRegistry
from ingestion.router import route_file
from ingestion.config import FILE_CONFIG

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 2.0


class CSVHandler(FileSystemEventHandler):

    def __init__(self, registry: FileRegistry, duckdb_conn, watch_dir: str):
        self.registry   = registry
        self.duckdb_conn = duckdb_conn
        self.watch_dir  = watch_dir
        self._timers    = {}   # { filepath: threading.Timer }
        self._lock      = threading.Lock()

    # ── Event hooks ──────────────────────────────────────────────── #Upon these events, the debounce function is triggered

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".csv"):
            logger.debug(f"EVENT on_created → {event.src_path}")
            self._debounce(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".csv"):
            logger.debug(f"EVENT on_modified → {event.src_path}")
            self._debounce(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".csv"):
            filename = os.path.basename(event.src_path)
            logger.warning(
                f"FILE DELETED: '{filename}' — DuckDB table NOT dropped. "
                f"Manual cleanup required if intentional."
            )

    # ── Debounce logic ──────────────────────────────────────────────

    def _debounce(self, filepath: str): #Every time this is called, existing timer is cancelled and new one is started
        """
        Cancel any pending timer for this filepath and restart it.
        The actual processing only fires after DEBOUNCE_SECONDS of silence.
        """
        with self._lock:
            if filepath in self._timers:
                self._timers[filepath].cancel()

            t = threading.Timer(
                DEBOUNCE_SECONDS,
                self._process,
                args=[filepath]
            )
            self._timers[filepath] = t
            t.start()

    # ── Processing ──────────────────────────────────────────────────

    def _process(self, filepath: str): #Once the timer ends this function is called which routes file to be processed
        filename = os.path.basename(filepath)

        # Clean up timer reference now that it has fired
        with self._lock:
            self._timers.pop(filepath, None)

        # Guard: file must still exist (may have been deleted mid-debounce)
        if not os.path.exists(filepath):
            logger.warning(f"SKIP '{filename}' — file no longer exists.")
            return

        # Guard: file must be a known CSV
        if filename not in FILE_CONFIG:
            logger.warning(
                f"SKIP '{filename}' — not in FILE_CONFIG. "
                f"Add it to config.py if this file should be ingested."
            )
            return

        try:
            current_hash = self.registry.compute_hash(filepath)

            if not self.registry.has_changed(filename, current_hash):
                logger.info(f"SKIP '{filename}' — content unchanged.")
                return

            logger.info(f"PROCESSING '{filename}'...")
            row_count = route_file(filepath, filename, self.duckdb_conn)
            self.registry.update(filename, current_hash, row_count, "success")
            logger.info(f"OK '{filename}' → {row_count} rows ingested.")

        except Exception as e:
            logger.error(f"FAILED '{filename}': {e}", exc_info=True)
            self.registry.update(filename, "", 0, "failed")


def start_watcher(watch_dir: str, registry: FileRegistry, duckdb_conn) -> Observer:
    """
    Creates, schedules and starts the Observer.
    Returns the Observer so main.py can stop it on shutdown.
    """
    handler  = CSVHandler(registry, duckdb_conn, watch_dir)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=False)
    observer.start()
    logger.info(f"Watcher started — monitoring '{watch_dir}'")
    return observer
