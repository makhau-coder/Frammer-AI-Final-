# tests/test_column_contracts.py
#
# Regression tests that verify the ACTUAL DuckDB tables have the exact
# column names the NLP pipeline expects.
# These catch schema drift early — if a table gets rebuilt with wrong
# column names, these fail immediately before any SQL is attempted.


import pytest
import duckdb
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.environ.get("FRAMMER_DB_PATH", "frammer.db")


@pytest.fixture(scope="module")
def prod_db():
    conn = duckdb.connect(DB_PATH, read_only=True)
    yield conn
    conn.close()


def get_columns(conn, table: str) -> set[str]:
    result = conn.execute(f'DESCRIBE "{table}"').fetchall()
    return {row[0] for row in result}


# ──────────────────────────────────────────────────────────────────────

class TestMonthlyChart:
    def test_required_columns(self, prod_db):
        cols = get_columns(prod_db, "monthly_chart")
        for col in ("Month", "Total Uploaded", "Total Created", "Total Published"):
            assert col in cols, f"monthly_chart missing: '{col}'"

    def test_no_combined_data_columns_leaked(self, prod_db):
        cols = get_columns(prod_db, "monthly_chart")
        assert "Uploaded Count" not in cols
        assert "Uploaded By" not in cols


class TestMonthWiseDuration:
    def test_required_columns(self, prod_db):
        cols = get_columns(prod_db, "month_wise_duration")
        for col in (
            "Month",
            "Total Uploaded Duration_secs",  "Total Uploaded Duration_raw",
            "Total Created Duration_secs",   "Total Created Duration_raw",
            "Total Published Duration_secs", "Total Published Duration_raw",
        ):
            assert col in cols, f"month_wise_duration missing: '{col}'"


class TestClientCombinedData:
    def test_required_columns(self, prod_db):
        cols = get_columns(prod_db, "client_1_combined_data_2025_3_1_2026_2_28")
        for col in ("Channel", "Uploaded Count", "Created Count", "Published Count"):
            assert col in cols, f"client_1_combined_data missing: '{col}'"

    def test_duration_columns(self, prod_db):
        cols = get_columns(prod_db, "client_1_combined_data_2025_3_1_2026_2_28")
        for col in (
            "Uploaded Duration (hh:mm:ss)_secs",
            "Created Duration (hh:mm:ss)_secs",
            "Published Duration (hh:mm:ss)_secs",
        ):
            assert col in cols, f"client_1_combined_data missing duration: '{col}'"

    def test_no_old_column_names(self, prod_db):
        cols = get_columns(prod_db, "client_1_combined_data_2025_3_1_2026_2_28")
        assert "Total Uploaded" not in cols
        assert "Total Created" not in cols
        assert "Total Published" not in cols


class TestCombinedDataByUser:
    def test_required_columns(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_user")
        for col in ("User", "Uploaded Count", "Created Count", "Published Count"):
            assert col in cols, f"combined_data_by_user missing: '{col}'"

    def test_no_old_column_names(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_user")
        assert "Uploaded By" not in cols, "Old 'Uploaded By' — must be 'User'"
        assert "Total Uploaded" not in cols, "Old 'Total Uploaded' — must be 'Uploaded Count'"

    def test_duration_columns(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_user")
        for col in (
            "Uploaded Duration (hh:mm:ss)_secs",
            "Created Duration (hh:mm:ss)_secs",
            "Published Duration (hh:mm:ss)_secs",
        ):
            assert col in cols, f"combined_data_by_user missing duration: '{col}'"


class TestCombinedDataByChannelAndUser:
    def test_required_columns(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_channel_and_user")
        for col in ("Channel", "User", "Uploaded Count", "Created Count", "Published Count"):
            assert col in cols, f"combined_data_by_channel_and_user missing: '{col}'"

    def test_no_uploaded_by(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_channel_and_user")
        assert "Uploaded By" not in cols


class TestChannelWisePublishing:
    def test_wide_format_platform_columns(self, prod_db):
        cols = get_columns(prod_db, "channel_wise_publishing")
        for col in ("Channel", "Facebook", "Instagram", "Linkedin",
                    "Reels", "Shorts", "X", "Youtube", "Threads"):
            assert col in cols, f"channel_wise_publishing missing: '{col}'"

    def test_no_total_published_column(self, prod_db):
        cols = get_columns(prod_db, "channel_wise_publishing")
        assert "Total Published" not in cols, (
            "'Total Published' must not exist — pipeline sums platform columns"
        )


class TestChannelWisePublishingDuration:
    def test_platform_duration_columns(self, prod_db):
        cols = get_columns(prod_db, "channel_wise_publishing_duration")
        for platform in ("Facebook", "Instagram", "Linkedin", "Reels",
                         "Shorts", "X", "Youtube", "Threads"):
            assert f"{platform} Duration_secs" in cols
            assert f"{platform} Duration_raw" in cols


class TestInputOutputLanguageTables:
    def test_input_type_columns(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_input_type")
        for col in ("Input Type", "Uploaded Count", "Created Count", "Published Count"):
            assert col in cols

    def test_output_type_columns(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_output_type")
        for col in ("Output Type", "Created Count", "Published Count"):
            assert col in cols

    def test_language_columns(self, prod_db):
        cols = get_columns(prod_db, "combined_data_2025_3_1_2026_2_28_by_language")
        for col in ("Language", "Uploaded Count", "Created Count", "Published Count"):
            assert col in cols
