# tests/test_synthesiser.py
#
# Unit tests for nlp/synthesiser.py
# Tests helper functions with no Gemini calls,
# and one integration test that mocks the API.


import pytest
from unittest.mock import MagicMock, patch
from nlp.synthesiser import (
    _extract_filters,
    _compress_data,
    _build_prompt,
    synthesise,
    SynthesisResult,
    _MAX_ROWS_IN_PROMPT,
)


class TestExtractFilters:

    def test_where_clause(self):
        sql = 'SELECT "Month" FROM monthly_chart\nWHERE "Month" = \'Jan, 2026\';'
        result = _extract_filters(sql)
        assert "WHERE" in result
        assert "Jan, 2026" in result

    def test_order_by_and_limit(self):
        sql = 'SELECT "User" FROM tbl\nORDER BY "Uploaded Count" DESC\nLIMIT 1;'
        result = _extract_filters(sql)
        assert "ORDER BY" in result
        assert "LIMIT" in result

    def test_no_filters(self):
        sql = 'SELECT "Month", "Total Uploaded" FROM monthly_chart;'
        result = _extract_filters(sql)
        assert "full table scan" in result.lower()

    def test_group_by_excluded(self):
        """GROUP BY should not appear in filters — not useful for explainability."""
        sql = 'SELECT "Channel", SUM("Uploaded Count") FROM tbl\nGROUP BY "Channel";'
        result = _extract_filters(sql)
        assert "GROUP BY" not in result

    def test_having_clause(self):
        sql = 'SELECT "Channel" FROM tbl\nGROUP BY "Channel"\nHAVING SUM("Uploaded Count") > 100;'
        result = _extract_filters(sql)
        assert "HAVING" in result


class TestCompressData:

    def test_basic_table_format(self, sample_user_data):
        result = _compress_data(sample_user_data)
        assert "User" in result           # header present
        assert "Chandan" in result        # data present
        assert "489" in result
        assert "---" in result            # separator present

    def test_respects_max_rows(self):
        data = [{"col": i} for i in range(50)]
        result = _compress_data(data)
        lines = result.strip().split("\n")
        # header + separator + _MAX_ROWS_IN_PROMPT data rows + truncation line
        assert len(lines) == 2 + _MAX_ROWS_IN_PROMPT + 1

    def test_truncation_message(self):
        data = [{"col": i} for i in range(30)]
        result = _compress_data(data)
        assert "more rows not shown" in result
        assert str(30 - _MAX_ROWS_IN_PROMPT) in result

    def test_no_truncation_when_small(self, sample_monthly_data):
        result = _compress_data(sample_monthly_data)
        assert "more rows not shown" not in result

    def test_empty_data(self):
        result = _compress_data([])
        assert result == "(no rows)"

    def test_single_row(self):
        result = _compress_data([{"uploaded_hours": 122.0}])
        assert "122.0" in result
        assert "uploaded_hours" in result

    def test_no_json_curly_braces(self, sample_user_data):
        """Compact format must NOT contain JSON syntax."""
        result = _compress_data(sample_user_data)
        assert "{" not in result
        assert "}" not in result

    def test_pipe_separated(self, sample_user_data):
        result = _compress_data(sample_user_data)
        assert " | " in result


class TestBuildPrompt:

    def test_prompt_contains_question(self, sample_user_data):
        prompt = _build_prompt(
            question="Who is the top uploader?",
            sql='SELECT "User" FROM tbl ORDER BY "Uploaded Count" DESC LIMIT 1;',
            tables=["combined_data_2025_3_1_2026_2_28_by_user"],
            data=sample_user_data,
        )
        assert "Who is the top uploader?" in prompt

    def test_prompt_contains_table_names(self, sample_user_data):
        prompt = _build_prompt(
            question="test",
            sql="SELECT 1;",
            tables=["combined_data_2025_3_1_2026_2_28_by_user", "monthly_chart"],
            data=sample_user_data,
        )
        assert "combined_data_2025_3_1_2026_2_28_by_user" in prompt
        assert "monthly_chart" in prompt

    def test_prompt_contains_compressed_data(self, sample_user_data):
        prompt = _build_prompt(
            question="test",
            sql="SELECT 1;",
            tables=[],
            data=sample_user_data,
        )
        assert "Chandan" in prompt
        assert "489" in prompt

    def test_empty_tables_fallback(self, sample_single_row):
        prompt = _build_prompt("test", "SELECT 1;", [], sample_single_row)
        assert "unknown" in prompt


class TestSynthesiseEmptyData:

    def test_empty_data_returns_success(self):
        result = synthesise("test", "SELECT 1;", [], [])
        assert result.success is True
        assert "no results" in result.insight.lower()
        assert result.error is None


class TestSynthesiseMocked:

    def _make_mock_response(self, text: str):
        candidate = MagicMock()
        candidate.finish_reason = "STOP"
        response = MagicMock()
        response.text = text
        response.candidates = [candidate]
        return response

    def test_successful_synthesis(self, sample_user_data):
        mock_response = self._make_mock_response(
            "Chandan is the top uploading user with 489 videos. "
            "He leads by a significant margin over Alice at 200 uploads. "
            "Explainability: Used combined_data_..._by_user, ordered by Uploaded Count DESC, LIMIT 1."
        )
        with patch("nlp.synthesiser._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            result = synthesise(
                question="Which user uploaded the most?",
                sql='SELECT "User", "Uploaded Count" FROM combined_data_2025_3_1_2026_2_28_by_user ORDER BY "Uploaded Count" DESC LIMIT 1;',
                tables=["combined_data_2025_3_1_2026_2_28_by_user"],
                data=sample_user_data[:1],
            )
        assert result.success is True
        assert "Chandan" in result.insight
        assert "Explainability" in result.insight
        assert result.error is None

    def test_api_failure_returns_soft_fail(self, sample_user_data):
        with patch("nlp.synthesiser._get_client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("API down")
            result = synthesise("test", "SELECT 1;", [], sample_user_data)
        assert result.success is False
        assert result.insight != ""     # still returns a fallback message
        assert result.error is not None

    def test_empty_gemini_response(self, sample_user_data):
        mock_response = self._make_mock_response("")
        with patch("nlp.synthesiser._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            result = synthesise("test", "SELECT 1;", [], sample_user_data)
        assert result.success is False

    def test_max_tokens_warning_logged(self, sample_user_data, caplog):
        candidate = MagicMock()
        candidate.finish_reason = "MAX_TOKENS"
        mock_response = MagicMock()
        mock_response.text = "Partial insight..."
        mock_response.candidates = [candidate]

        import logging
        with patch("nlp.synthesiser._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            with caplog.at_level(logging.WARNING, logger="nlp.synthesiser"):
                synthesise("test", "SELECT 1;", [], sample_user_data)
        assert any("MAX_TOKENS" in r.message for r in caplog.records)
