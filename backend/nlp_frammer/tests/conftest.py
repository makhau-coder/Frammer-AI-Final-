# tests/conftest.py
#
# Shared fixtures for the entire test suite.

import pytest
import duckdb
import pandas as pd
from unittest.mock import patch

# ── Minimal in-memory DuckDB with all tables ──────────────────────────

@pytest.fixture(scope="session")
def db():
    """
    In-memory DuckDB pre-loaded with small representative versions of
    every table the pipeline queries. Scoped to session for speed.
    """
    conn = duckdb.connect(":memory:")

    conn.execute("""
        CREATE TABLE monthly_chart AS
        SELECT * FROM (VALUES
            ('Mar, 2025', 120, 540, 30),
            ('Apr, 2025', 95,  380, 12),
            ('May, 2025', 200, 900, 85),
            ('Jun, 2025', 180, 810, 70),
            ('Jul, 2025', 60,  240, 5),
            ('Aug, 2025', 75,  300, 8),
            ('Sep, 2025', 110, 495, 20),
            ('Oct, 2025', 130, 650, 45),
            ('Nov, 2025', 160, 720, 60),
            ('Dec, 2025', 90,  405, 15),
            ('Jan, 2026', 210, 945, 90),
            ('Feb, 2026', 145, 652, 55)
        ) t("Month", "Total Uploaded", "Total Created", "Total Published")
    """)

    conn.execute("""
        CREATE TABLE month_wise_duration AS
        SELECT * FROM (VALUES
            ('Mar, 2025', '121:30:00', 437400, '54:40:00', 196800, '2:30:00', 9000),
            ('Apr, 2025', '95:15:00',  343000, '42:55:00', 154500, '1:00:00', 3600),
            ('May, 2025', '200:00:00', 720000, '90:00:00', 324000, '7:30:00', 27000),
            ('Jan, 2026', '122:00:00', 439200, '54:54:00', 197640, '8:00:00', 28800),
            ('Feb, 2026', '145:00:00', 522000, '65:15:00', 234900, '5:00:00', 18000)
        ) t(
            "Month",
            "Total Uploaded Duration_raw",  "Total Uploaded Duration_secs",
            "Total Created Duration_raw",   "Total Created Duration_secs",
            "Total Published Duration_raw", "Total Published Duration_secs"
        )
    """)

    conn.execute("""
        CREATE TABLE client_1_combined_data_2025_3_1_2026_2_28 AS
        SELECT * FROM (VALUES
            ('A', 300, 1350, 120, '270:00:00', 243000, '121:30:00', 97200, '10:00:00', 36000),
            ('B', 250, 1000, 80,  '225:00:00', 210000, '101:15:00', 81000, '7:00:00',  25200),
            ('C', 180, 720,  45,  '162:00:00', 151200, '72:54:00',  58140, '3:45:00',  13500),
            ('D', 71,  284,  12,  '63:54:00',  57540,  '28:45:00',  23100, '1:00:00',  3600)
        ) t(
            "Channel", "Uploaded Count", "Created Count", "Published Count",
            "Uploaded Duration (hh:mm:ss)_raw", "Uploaded Duration (hh:mm:ss)_secs",
            "Created Duration (hh:mm:ss)_raw",  "Created Duration (hh:mm:ss)_secs",
            "Published Duration (hh:mm:ss)_raw","Published Duration (hh:mm:ss)_secs"
        )
    """)

    conn.execute("""
        CREATE TABLE combined_data_2025_3_1_2026_2_28_by_user AS
        SELECT * FROM (VALUES
            ('Chandan',  489, 2200, 180, '440:06:00', 1584360, '198:03:00', 712980, '16:12:00', 58320),
            ('Alice',    200, 800,  95,  '180:00:00', 648000,  '81:00:00',  291600, '7:30:00',  27000),
            ('Bob',      150, 675,  30,  '135:00:00', 486000,  '60:45:00',  218700, '2:30:00',  9000),
            ('Carol',    90,  360,  20,  '81:00:00',  291600,  '36:27:00',  131220, '1:40:00',  6000),
            ('Dave',     72,  288,  0,   '64:48:00',  233280,  '29:09:00',  104940, '0:00:00',  0)
        ) t(
            "User", "Uploaded Count", "Created Count", "Published Count",
            "Uploaded Duration (hh:mm:ss)_raw", "Uploaded Duration (hh:mm:ss)_secs",
            "Created Duration (hh:mm:ss)_raw",  "Created Duration (hh:mm:ss)_secs",
            "Published Duration (hh:mm:ss)_raw","Published Duration (hh:mm:ss)_secs"
        )
    """)

    conn.execute("""
        CREATE TABLE combined_data_2025_3_1_2026_2_28_by_channel_and_user AS
        SELECT * FROM (VALUES
            ('A', 'Chandan', 200, 900,  80),
            ('A', 'Alice',   100, 450,  40),
            ('B', 'Chandan', 150, 600,  60),
            ('B', 'Bob',     100, 400,  20),
            ('C', 'Carol',    90, 360,  20),
            ('D', 'Dave',     71, 284,  12)
        ) t("Channel", "User", "Uploaded Count", "Created Count", "Published Count")
    """)

    conn.execute("""
        CREATE TABLE channel_wise_publishing AS
        SELECT * FROM (VALUES
            ('A', 20, 15, 10, 30, 25, 5, 40, 5),
            ('B', 15, 10, 5,  20, 10, 2, 25, 3),
            ('C', 10, 8,  3,  10, 5,  1, 15, 2),
            ('D', 2,  1,  0,  3,  2,  0, 5,  1)
        ) t(
            "Channel",
            "Facebook", "Instagram", "Linkedin", "Reels",
            "Shorts", "X", "Youtube", "Threads"
        )
    """)

    conn.execute("""
        CREATE TABLE channel_wise_publishing_duration AS
        SELECT * FROM (VALUES
            ('A', '5:00:00', 18000, '4:00:00', 14400, '2:00:00', 7200,
                  '6:00:00', 21600, '5:00:00', 18000, '1:00:00', 3600,
                  '8:00:00', 28800, '1:00:00', 3600),
            ('B', '3:00:00', 10800, '2:00:00', 7200,  '1:00:00', 3600,
                  '4:00:00', 14400, '2:00:00', 7200,  '0:30:00', 1800,
                  '5:00:00', 18000, '0:30:00', 1800),
            ('C', '2:00:00', 7200,  '1:30:00', 5400,  '0:45:00', 2700,
                  '2:00:00', 7200,  '1:00:00', 3600,  '0:15:00', 900,
                  '3:00:00', 10800, '0:15:00', 900),
            ('D', '0:30:00', 1800,  '0:15:00', 900,   '0:00:00', 0,
                  '0:30:00', 1800,  '0:30:00', 1800,  '0:00:00', 0,
                  '1:00:00', 3600,  '0:15:00', 900)
        ) t(
            "Channel",
            "Facebook Duration_raw",  "Facebook Duration_secs",
            "Instagram Duration_raw", "Instagram Duration_secs",
            "Linkedin Duration_raw",  "Linkedin Duration_secs",
            "Reels Duration_raw",     "Reels Duration_secs",
            "Shorts Duration_raw",    "Shorts Duration_secs",
            "X Duration_raw",         "X Duration_secs",
            "Youtube Duration_raw",   "Youtube Duration_secs",
            "Threads Duration_raw",   "Threads Duration_secs"
        )
    """)

    conn.execute("""
        CREATE TABLE combined_data_2025_3_1_2026_2_28_by_input_type AS
        SELECT * FROM (VALUES
            ('Live Stream',  400, 1800, 150),
            ('Studio Video', 300, 1200, 100),
            ('Podcast',      200,  800,  60),
            ('Interview',    100,  400,  15)
        ) t("Input Type", "Uploaded Count", "Created Count", "Published Count")
    """)

    conn.execute("""
        CREATE TABLE combined_data_2025_3_1_2026_2_28_by_output_type AS
        SELECT * FROM (VALUES
            ('Highlight Clip', 2000, 250),
            ('Summary',        1500, 100),
            ('Short',          1000, 80),
            ('Full Edit',       500, 50)
        ) t("Output Type", "Created Count", "Published Count")
    """)

    conn.execute("""
        CREATE TABLE combined_data_2025_3_1_2026_2_28_by_language AS
        SELECT * FROM (VALUES
            ('English', 600, 2700, 250),
            ('Hindi',   200,  900,  60),
            ('Tamil',    80,  320,  15),
            ('Telugu',   40,  160,   0)
        ) t("Language", "Uploaded Count", "Created Count", "Published Count")
    """)

    conn.execute("""
        CREATE TABLE video_list AS
        SELECT * FROM (VALUES
            ('v001', 'Budget 2025 highlights',    'Chandan', 'Live Stream',  TRUE,  'Youtube',  'https://yt.com/1', '2025-05-01 10:00:00'),
            ('v002', 'IPL match recap',           'Alice',   'Studio Video', TRUE,  'Instagram','https://ig.com/2', '2025-05-02 11:00:00'),
            ('v003', 'Tech podcast episode 12',   'Bob',     'Podcast',      FALSE, NULL,       NULL,               '2025-06-01 09:00:00'),
            ('v004', 'Startup interview series',  'Carol',   'Interview',    TRUE,  'Facebook', 'https://fb.com/4', '2025-07-15 14:00:00'),
            ('v005', 'Budget analysis deep dive', 'Chandan', 'Studio Video', FALSE, NULL,       NULL,               '2025-08-10 16:00:00'),
            ('v006', 'Live Q&A session',          'Dave',    'Live Stream',  FALSE, NULL,       NULL,               '2025-09-01 18:00:00'),
            ('v007', 'Weekly news digest',        'Alice',   'Studio Video', TRUE,  'Youtube',  'https://yt.com/7', '2025-10-05 08:00:00'),
            ('v008', 'Product launch coverage',   'Chandan', 'Live Stream',  TRUE,  'Youtube',  'https://yt.com/8', '2025-11-01 12:00:00')
        ) t(
            video_id, headline, uploaded_by, input_type,
            published, published_platform, published_url, ingested_at
        )
    """)

    yield conn
    conn.close()


@pytest.fixture
def sample_monthly_data():
    return [
        {"Month": "Mar, 2025", "Total Uploaded": 120, "Total Created": 540, "Total Published": 30},
        {"Month": "Apr, 2025", "Total Uploaded": 95,  "Total Created": 380, "Total Published": 12},
        {"Month": "May, 2025", "Total Uploaded": 200, "Total Created": 900, "Total Published": 85},
        {"Month": "Jan, 2026", "Total Uploaded": 210, "Total Created": 945, "Total Published": 90},
        {"Month": "Feb, 2026", "Total Uploaded": 145, "Total Created": 652, "Total Published": 55},
    ]


@pytest.fixture
def sample_monthly_with_rate():
    return [
        {"Month": "Mar, 2025", "Total Uploaded": 120, "Total Created": 540, "publish_rate_pct": 5.56},
        {"Month": "Apr, 2025", "Total Uploaded": 95,  "Total Created": 380, "publish_rate_pct": 3.16},
        {"Month": "May, 2025", "Total Uploaded": 200, "Total Created": 900, "publish_rate_pct": 9.44},
        {"Month": "Jan, 2026", "Total Uploaded": 210, "Total Created": 945, "publish_rate_pct": 9.52},
    ]


@pytest.fixture
def sample_user_data():
    return [
        {"User": "Chandan", "Uploaded Count": 489, "Created Count": 2200, "Published Count": 180},
        {"User": "Alice",   "Uploaded Count": 200, "Created Count": 800,  "Published Count": 95},
        {"User": "Bob",     "Uploaded Count": 150, "Created Count": 675,  "Published Count": 30},
        {"User": "Carol",   "Uploaded Count": 90,  "Created Count": 360,  "Published Count": 20},
        {"User": "Dave",    "Uploaded Count": 72,  "Created Count": 288,  "Published Count": 0},
    ]


@pytest.fixture
def sample_user_with_rate():
    return [
        {"User": "Chandan", "Uploaded Count": 489, "publish_rate_pct": 8.18},
        {"User": "Alice",   "Uploaded Count": 200, "publish_rate_pct": 11.88},
        {"User": "Bob",     "Uploaded Count": 150, "publish_rate_pct": 4.44},
        {"User": "Dave",    "Uploaded Count": 72,  "publish_rate_pct": 0.0},
    ]


@pytest.fixture
def sample_channel_platform_data():
    """Two categoricals + 1 numeric — should trigger heatmap."""
    return [
        {"Channel": "A", "platform": "Youtube",   "published_count": 40},
        {"Channel": "A", "platform": "Reels",     "published_count": 30},
        {"Channel": "A", "platform": "Facebook",  "published_count": 20},
        {"Channel": "B", "platform": "Youtube",   "published_count": 25},
        {"Channel": "B", "platform": "Reels",     "published_count": 20},
        {"Channel": "C", "platform": "Youtube",   "published_count": 15},
    ]


@pytest.fixture
def sample_single_row():
    return [{"uploaded_hours": 122.0}]


class _NoCloseConn:
    """
    Wraps a DuckDB connection and turns close() into a no-op.
    Needed because executor.py calls conn.close() after every query,
    which would destroy the shared in-memory fixture connection.
    DuckDB's C extension doesn't allow patching .close directly.
    """
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass   # intentional no-op

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture(autouse=True)
def prevent_conn_close(db, monkeypatch):
    monkeypatch.setattr(
        "nlp.executor.duckdb.connect",
        lambda *args, **kwargs: _NoCloseConn(db)
    )
    
