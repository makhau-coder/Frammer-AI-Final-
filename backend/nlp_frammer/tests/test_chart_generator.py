# tests/test_chart_generator.py
#
# Unit tests for nlp/chart_generator.py
# Tests routing logic and chart output — no Gemini calls needed.


import os
import pytest
import pandas as pd
from nlp.chart_generator import (
    generate_chart,
    _is_time,
    _is_skip,
    _RATE_COLS,
)


class TestIsTime:

    def test_month_column_detected(self, sample_monthly_data):
        df = pd.DataFrame(sample_monthly_data)
        is_t, col = _is_time(df)
        assert is_t is True
        assert col == "Month"

    def test_no_time_column(self, sample_user_data):
        df = pd.DataFrame(sample_user_data)
        is_t, col = _is_time(df)
        assert is_t is False
        assert col == ""


class TestIsSkip:

    def test_known_categorical_cols_skipped(self):
        assert _is_skip("Month") is True
        assert _is_skip("Channel") is True
        assert _is_skip("User") is True
        assert _is_skip("Input Type") is True
        assert _is_skip("Language") is True

    def test_raw_suffix_skipped(self):
        assert _is_skip("Total Uploaded Duration_raw") is True
        assert _is_skip("Youtube Duration_raw") is True

    def test_numeric_cols_not_skipped(self):
        assert _is_skip("Uploaded Count") is False
        assert _is_skip("publish_rate_pct") is False
        assert _is_skip("uploaded_hours") is False


class TestRateCols:

    def test_rate_cols_defined(self):
        assert "publish_rate_pct" in _RATE_COLS
        assert "creation_multiplier" in _RATE_COLS
        assert "compression_ratio" in _RATE_COLS
        assert "upload_to_publish_rate_pct" in _RATE_COLS


class TestGenerateChartRouting:

    def test_empty_data_returns_none(self):
        assert generate_chart("test", [], "SELECT 1;") is None

    def test_single_stat_row_returns_none(self, sample_single_row):
        result = generate_chart("How many hours in Jan 2026?", sample_single_row, "SELECT 1;")
        assert result is None

    def test_time_series_returns_line(self, sample_monthly_data):
        result = generate_chart("Show monthly upload trend", sample_monthly_data, "SELECT 1;")
        assert result is not None
        path, chart_type = result
        assert chart_type == "line"
        assert os.path.exists(path)
        assert path.endswith(".png")

    def test_time_series_with_rate_returns_dual_axis(self, sample_monthly_with_rate):
        result = generate_chart("Monthly upload trend with publish rate",
                                sample_monthly_with_rate, "SELECT 1;")
        assert result is not None
        path, chart_type = result
        assert chart_type == "dual_axis"
        assert os.path.exists(path)

    def test_user_leaderboard_returns_bar(self, sample_user_data):
        result = generate_chart("Show user leaderboard by uploads",
                                sample_user_data, "SELECT 1;")
        assert result is not None
        path, chart_type = result
        assert chart_type == "bar"
        assert os.path.exists(path)

    def test_user_with_rate_returns_dual_axis(self, sample_user_with_rate):
        result = generate_chart("User leaderboard with publish rate",
                                sample_user_with_rate, "SELECT 1;")
        assert result is not None
        path, chart_type = result
        assert chart_type == "dual_axis"

    def test_channel_platform_returns_heatmap(self, sample_channel_platform_data):
        result = generate_chart("Channel platform breakdown",
                                sample_channel_platform_data, "SELECT 1;")
        assert result is not None
        path, chart_type = result
        assert chart_type == "heatmap"
        assert os.path.exists(path)

    def test_returns_tuple_not_string(self, sample_user_data):
        result = generate_chart("test", sample_user_data, "SELECT 1;")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_chart_path_is_png(self, sample_user_data):
        result = generate_chart("test", sample_user_data, "SELECT 1;")
        assert result is not None
        path, _ = result
        assert path.endswith(".png")

    def test_grouped_bar_multiple_numerics(self):
        data = [
            {"Channel": "A", "Uploaded Count": 300, "Created Count": 1350, "Published Count": 120},
            {"Channel": "B", "Uploaded Count": 250, "Created Count": 1000, "Published Count": 80},
            {"Channel": "C", "Uploaded Count": 180, "Created Count": 720,  "Published Count": 45},
        ]
        result = generate_chart("Channel production summary", data, "SELECT 1;")
        assert result is not None
        _, chart_type = result
        assert chart_type == "bar"
