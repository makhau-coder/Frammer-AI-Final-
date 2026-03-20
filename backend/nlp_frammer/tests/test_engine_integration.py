# tests/test_engine_integration.py

import pytest
from unittest.mock import MagicMock, patch
from nlp.engine import query, NLPResult


def _mock_sql_gen(sql: str):
    from nlp.sql_generator import GenerationResult
    return GenerationResult(
        success=True,
        sql=sql,
        cannot_answer=False,
        reason="",
        raw_response=sql,
    )


def _mock_cannot_answer(reason: str):
    from nlp.sql_generator import GenerationResult
    return GenerationResult(
        success=False,
        sql="",
        cannot_answer=True,
        reason=reason,
        raw_response=f"CANNOT_ANSWER: {reason}",
    )


def _mock_synthesis(text: str = "Mocked insight. Explainability: table used."):
    from nlp.synthesiser import SynthesisResult
    return SynthesisResult(
        success=True,
        insight=text,
        raw_response=text,
        error=None,
    )


# ──────────────────────────────────────────────────────────────────────

class TestEngineHappyPath:

    def test_top_user_by_uploads(self):
        sql = 'SELECT "User", "Uploaded Count" FROM combined_data_2025_3_1_2026_2_28_by_user ORDER BY "Uploaded Count" DESC LIMIT 1;'
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[],
                referenced_tables=["combined_data_2025_3_1_2026_2_28_by_user"],
            )
            result = query("Which user uploaded the most videos?")

        assert result.success is True
        assert result.cannot_answer is False
        assert result.row_count == 1
        assert result.data[0]["User"] == "Chandan"
        assert result.data[0]["Uploaded Count"] == 489
        assert result.insight is not None
        assert result.error is None

    def test_monthly_trend(self):
        sql = 'SELECT "Month", "Total Uploaded", "Total Created", "Total Published" FROM monthly_chart ORDER BY "Month";'
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=["monthly_chart"],
            )
            result = query("Show me the monthly upload trend")

        assert result.success is True
        assert result.row_count == 12
        assert result.chart_path is not None
        assert result.chart_type in ("line", "dual_axis")

    def test_hours_uploaded_jan_2026(self):
        sql = "SELECT ROUND(\"Total Uploaded Duration_secs\" / 3600.0, 2) AS uploaded_hours FROM month_wise_duration WHERE \"Month\" = 'Jan, 2026';"
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=["month_wise_duration"],
            )
            result = query("How many hours were uploaded in Jan 2026?")

        assert result.success is True
        assert result.row_count == 1
        assert result.data[0]["uploaded_hours"] == 122.0
        assert result.chart_path is None   # single stat row → no chart

    def test_channel_published_most(self):
        sql = """SELECT "Channel",
               "Facebook" + "Instagram" + "Linkedin" + "Reels" + "Shorts"
               + "X" + "Youtube" + "Threads" AS total_published
        FROM channel_wise_publishing
        ORDER BY total_published DESC
        LIMIT 1;"""
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=["channel_wise_publishing"],
            )
            result = query("Which channel published the most videos?")

        assert result.success is True
        assert result.data[0]["Channel"] == "A"


class TestEngineCannotAnswer:

    def _run_cannot_answer(self, question: str, reason: str):
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_cannot_answer(reason)):

            mock_retrieve.return_value = MagicMock(
                total_chunks=0, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=[],
            )
            return query(question)

    def test_revenue_question(self):
        result = self._run_cannot_answer(
            "What is the revenue per channel?",
            "No financial or revenue data exists in this dataset."
        )
        assert result.cannot_answer is True
        assert result.success is False
        assert result.data == []
        assert result.chart_path is None
        assert result.chart_type is None

    def test_future_month(self):
        result = self._run_cannot_answer(
            "How many uploads in March 2026?",
            "The dataset only covers March 2025 to February 2026."
        )
        assert result.cannot_answer is True
        assert "2026" in result.error

    def test_team_question(self):
        result = self._run_cannot_answer(
            "Which team has the best publish rate?",
            "Team data is not available."
        )
        assert result.cannot_answer is True

    def test_cannot_answer_insight_is_reason(self):
        result = self._run_cannot_answer("Revenue?", "No revenue data.")
        assert result.insight is not None
        assert result.insight != ""


class TestEngineEdgeCases:

    def test_empty_query(self):
        result = query("")
        assert result.success is False
        assert "empty" in result.error.lower()
        assert result.chart_path is None
        assert result.insight is None

    def test_whitespace_only_query(self):
        result = query("   \n  ")
        assert result.success is False

    def test_sql_generation_failure(self):
        from nlp.sql_generator import GenerationResult
        bad_gen = GenerationResult(
            success=False, sql="", cannot_answer=False,
            reason="Unexpected response from Gemini.",
            raw_response="something weird",
        )
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=bad_gen):

            mock_retrieve.return_value = MagicMock(
                total_chunks=0, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=[],
            )
            result = query("Something that breaks generation")

        assert result.success is False
        assert result.cannot_answer is False
        assert result.error is not None
        assert result.chart_path is None

    def test_synthesis_failure_does_not_crash_pipeline(self):
        sql = 'SELECT "User", "Uploaded Count" FROM combined_data_2025_3_1_2026_2_28_by_user LIMIT 3;'
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", side_effect=Exception("Synthesis exploded")):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[],
                referenced_tables=["combined_data_2025_3_1_2026_2_28_by_user"],
            )
            result = query("Show me users")

        assert result.success is True
        assert result.row_count == 3
        assert result.insight is None   # data intact, insight gracefully None

    def test_chart_failure_does_not_crash_pipeline(self):
        sql = 'SELECT "Month", "Total Uploaded" FROM monthly_chart;'
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=100), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()), \
             patch("nlp.engine.generate_chart", side_effect=Exception("Plotly exploded")):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=["monthly_chart"],
            )
            result = query("Monthly trend")

        assert result.success is True
        assert result.chart_path is None
        assert result.chart_type is None

    def test_debug_mode_populates_fields(self):
        sql = 'SELECT "Month" FROM monthly_chart LIMIT 1;'
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="assembled_prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=3465), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=["monthly_chart"],
            )
            result = query("test", debug=True)

        assert result.prompt_tokens == 3465
        assert result.raw_response != ""

    def test_debug_false_hides_fields(self):
        sql = 'SELECT "Month" FROM monthly_chart LIMIT 1;'
        with patch("nlp.engine.retrieve") as mock_retrieve, \
             patch("nlp.engine.build_prompt", return_value="prompt"), \
             patch("nlp.engine.estimate_tokens", return_value=3465), \
             patch("nlp.engine.generate", return_value=_mock_sql_gen(sql)), \
             patch("nlp.engine.synthesise", return_value=_mock_synthesis()):

            mock_retrieve.return_value = MagicMock(
                total_chunks=3, table_chunks=[], metric_chunks=[],
                example_chunks=[], referenced_tables=["monthly_chart"],
            )
            result = query("test", debug=False)

        assert result.prompt_tokens == 0
        assert result.raw_response == ""
