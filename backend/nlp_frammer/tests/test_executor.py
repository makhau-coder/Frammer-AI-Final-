# tests/test_executor.py

import pytest
from nlp.executor import execute


class TestExecuteSuccess:

    def test_simple_select(self):
        result = execute('SELECT "Month", "Total Uploaded" FROM monthly_chart ORDER BY "Total Uploaded" DESC LIMIT 1;')
        assert result.success is True
        assert result.row_count == 1
        assert result.data[0]["Total Uploaded"] == 210
        assert result.data[0]["Month"] == "Jan, 2026"

    def test_returns_all_rows(self):
        result = execute('SELECT "Month" FROM monthly_chart;')
        assert result.success is True
        assert result.row_count == 12

    def test_empty_result(self):
        result = execute("SELECT * FROM monthly_chart WHERE \"Month\" = 'Mar, 2099';")
        assert result.success is True
        assert result.row_count == 0
        assert result.data == []

    def test_aggregation(self):
        result = execute('SELECT SUM("Total Uploaded") AS total FROM monthly_chart;')
        assert result.success is True
        assert result.data[0]["total"] == 1575

    def test_computed_column(self):
        result = execute("""
            SELECT "Month",
                   ROUND("Total Published" * 100.0 / NULLIF("Total Created", 0), 2)
                       AS publish_rate_pct
            FROM monthly_chart
            ORDER BY publish_rate_pct DESC
            LIMIT 1;
        """)
        assert result.success is True
        assert result.data[0]["publish_rate_pct"] > 0

    def test_user_table_correct_columns(self):
        result = execute('SELECT "User", "Uploaded Count" FROM combined_data_2025_3_1_2026_2_28_by_user ORDER BY "Uploaded Count" DESC LIMIT 1;')
        assert result.success is True
        assert result.data[0]["User"] == "Chandan"
        assert result.data[0]["Uploaded Count"] == 489

    def test_channel_wise_publishing_sum(self):
        result = execute("""
            SELECT "Channel",
                   "Facebook" + "Instagram" + "Linkedin" + "Reels"
                   + "Shorts" + "X" + "Youtube" + "Threads" AS total_published
            FROM channel_wise_publishing
            ORDER BY total_published DESC
            LIMIT 1;
        """)
        assert result.success is True
        assert result.data[0]["Channel"] == "A"

    def test_duration_conversion(self):
        result = execute("""
            SELECT ROUND("Total Uploaded Duration_secs" / 3600.0, 2) AS uploaded_hours
            FROM month_wise_duration
            WHERE "Month" = 'Jan, 2026';
        """)
        assert result.success is True
        assert result.data[0]["uploaded_hours"] == 122.0


class TestExecuteFailure:

    def test_nonexistent_table(self):
        result = execute("SELECT * FROM nonexistent_table;")
        assert result.success is False
        assert result.error is not None
        assert result.data == []
        assert result.row_count == 0

    def test_nonexistent_column(self):
        result = execute('SELECT "Uploaded By" FROM combined_data_2025_3_1_2026_2_28_by_user;')
        assert result.success is False
        assert result.error is not None

    def test_syntax_error(self):
        result = execute("SELEKT broken sql")
        assert result.success is False

    def test_old_column_name_total_uploaded_on_combined(self):
        result = execute('SELECT "Total Uploaded" FROM combined_data_2025_3_1_2026_2_28_by_user;')
        assert result.success is False

    def test_old_column_name_uploaded_by(self):
        result = execute('SELECT "Uploaded By" FROM combined_data_2025_3_1_2026_2_28_by_user;')
        assert result.success is False
