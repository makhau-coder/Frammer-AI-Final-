import sqlite3, hashlib, os
from datetime import datetime

"""This Class handles the registry database associated with the data files, used to track for file changes"""

class FileRegistry:
    def __init__(self, db_path="registry.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False) #opens the database file, same thread disabled cause of 
        self._init_table()                                            #observer thread and main thread usage simulataneously

    def _init_table(self): #Create the registry table if it does not exist
        self.conn.execute("""                         
            CREATE TABLE IF NOT EXISTS file_registry (
                filename        TEXT PRIMARY KEY,
                last_hash       TEXT,
                last_processed  TEXT,
                row_count       INTEGER,
                status          TEXT
            )
        """)
        self.conn.commit()

    def compute_hash(self, filepath: str) -> str: #Computes hash of the file
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def has_changed(self, filename: str, current_hash: str) -> bool: #Checks if file with fileName has changed 
        row = self.conn.execute(
            "SELECT last_hash FROM file_registry WHERE filename = ?", (filename,)
        ).fetchone()
        return row is None or row[0] != current_hash #If either file is new or hash has changed then file has changed

    def update(self, filename, file_hash, row_count, status): #Update the file row in the registry using new values
        self.conn.execute("""
            INSERT INTO file_registry (filename, last_hash, last_processed, row_count, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                last_hash=excluded.last_hash,
                last_processed=excluded.last_processed,
                row_count=excluded.row_count,
                status=excluded.status
        """, (filename, file_hash, datetime.utcnow().isoformat(), row_count, status))
        self.conn.commit()
