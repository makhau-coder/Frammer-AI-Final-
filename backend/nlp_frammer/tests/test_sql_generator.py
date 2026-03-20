# tests/test_sql_generator.py
#
# Unit tests for nlp/sql_generator.py
# Tests the _parse() logic only — no real Gemini calls.


import pytest
from nlp.sql_generator import _parse, GenerationResult


class TestParseCannotAnswer:

    def test_basic_cannot_answer(self):
        raw = "CANNOT_ANSWER: No revenue data exists."
        result = _parse(raw)
        assert result.cannot_answer is True
        assert result.success is False
        assert result.sql == ""
        assert "revenue" in result.reason.lower()

    def test_cannot_answer_no_colon(self):
        """CANNOT_ANSWER with no colon — reason should be empty string not crash."""
        raw = "CANNOT_ANSWER"
        result = _parse(raw)
        assert result.cannot_answer is True
        assert result.success is False

    def test_cannot_answer_multiline_reason(self):
        raw = "CANNOT_ANSWER: The dataset only covers March 2025 to February 2026.\nMarch 2026 is not available."
        result = _parse(raw)
        assert result.cannot_answer is True
        assert "2026" in result.reason


class TestParseValidSQL:

    def test_plain_select(self):
        raw = 'SELECT "User", "Uploaded Count" FROM combined_data_2025_3_1_2026_2_28_by_user ORDER BY "Uploaded Count" DESC LIMIT 1;'
        result = _parse(raw)
        assert result.success is True
        assert result.cannot_answer is False
        assert result.sql.endswith(";")
        assert "SELECT" in result.sql

    def test_adds_semicolon_if_missing(self):
        raw = 'SELECT "Month", "Total Uploaded" FROM monthly_chart'
        result = _parse(raw)
        assert result.success is True
        assert result.sql.endswith(";")

    def test_does_not_double_semicolon(self):
        raw = 'SELECT "Month" FROM monthly_chart;'
        result = _parse(raw)
        assert result.sql.count(";") == 1

    def test_with_clause(self):
        raw = 'WITH cte AS (SELECT 1) SELECT * FROM cte;'
        result = _parse(raw)
        assert result.success is True

    def test_multiline_sql(self):
        raw = '''SELECT "Channel",
       "Uploaded Count",
       "Created Count"
FROM client_1_combined_data_2025_3_1_2026_2_28
ORDER BY "Uploaded Count" DESC;'''
        result = _parse(raw)
        assert result.success is True
        assert "client_1_combined_data" in result.sql


class TestParseMarkdownFences:

    def test_sql_fenced(self):
        raw = "```sql\nSELECT \"Month\" FROM monthly_chart;\n```"
        result = _parse(raw)
        assert result.success is True
        assert "```" not in result.sql

    def test_generic_code_fence(self):
        raw = "```\nSELECT \"Month\" FROM monthly_chart;\n```"
        result = _parse(raw)
        assert result.success is True
        assert "```" not in result.sql

    def test_fence_with_explanation_before(self):
        """Gemini sometimes adds preamble before the fence."""
        raw = "Here is the SQL:\n```sql\nSELECT 1;\n```"
        result = _parse(raw)
        assert result.success is True


class TestParseInvalidResponses:

    def test_plain_text_not_sql(self):
        raw = "I cannot determine this from the available data."
        result = _parse(raw)
        assert result.success is False
        assert result.cannot_answer is False
        assert result.reason != ""

    def test_empty_string(self):
        raw = ""
        result = _parse(raw)
        assert result.success is False

    def test_only_whitespace(self):
        raw = "   \n  "
        result = _parse(raw)
        assert result.success is False

    def test_json_response(self):
        raw = '{"sql": "SELECT 1", "explanation": "blah"}'
        result = _parse(raw)
        assert result.success is False
