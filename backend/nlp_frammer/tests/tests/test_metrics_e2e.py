# tests/test_metrics_e2e.py
#
# Comprehensive end-to-end regression suite for all natural language → SQL → answer paths.
# Organised into 12 test classes covering every metric, edge case, phrasing variation,
# and pipeline guard (CANNOT_ANSWER / CLARIFY).
#
# Expected values are pre-computed from source CSVs (verified 2026-03-19).
#
# Run all:            pytest tests/test_metrics_e2e.py -v
# Run one class:      pytest tests/test_metrics_e2e.py::TestMonthlyAverages -v
# Stop on first fail: pytest tests/test_metrics_e2e.py -x -v
# ─────────────────────────────────────────────────────────────────────────────

import re
import pytest
from nlp.engine import query   # ← change to match your entry point


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def ask(question: str) -> str:
    result = query(question)
    answer = result.message
    assert answer, f"Pipeline returned empty answer for: {question!r}"
    return answer


def assert_contains(answer: str, *candidates):
    """Pass if any candidate string appears in the answer."""
    for c in candidates:
        if str(c) in answer:
            return
    pytest.fail(f"None of {candidates!r} found in:\n\n{answer}")


def assert_not_contains(answer: str, *forbidden):
    """Fail if any forbidden string appears in the answer."""
    for f in forbidden:
        assert str(f) not in answer, f"{f!r} should not appear in:\n\n{answer}"


def assert_is_numeric(answer: str, label: str = ""):
    assert re.search(r"\d+\.?\d*", answer), \
        f"Expected a numeric value{' for ' + label if label else ''} in:\n\n{answer}"


def assert_is_percentage(answer: str, min_val: float = 0, max_val: float = 100):
    m = re.search(r"(\d+\.?\d*)\s*%", answer)
    assert m, f"Expected a percentage in:\n\n{answer}"
    val = float(m.group(1))
    assert min_val <= val <= max_val, \
        f"Percentage {val}% outside expected range [{min_val}, {max_val}]"


def assert_no_clarify(answer: str):
    assert "CLARIFY" not in answer, f"Unexpected clarification request:\n\n{answer}"


def assert_cannot_answer(answer: str):
    assert "CANNOT_ANSWER" in answer or any(
        phrase in answer.lower() for phrase in [
            "cannot answer", "not available", "no financial", "no revenue",
            "outside the", "not include", "does not contain", "out of scope"
        ]
    ), f"Expected CANNOT_ANSWER response, got:\n\n{answer}"


# ─────────────────────────────────────────────────────────────────────────────
# PRE-COMPUTED EXPECTED VALUES (from source CSVs)
# ─────────────────────────────────────────────────────────────────────────────
#
# monthly_chart totals (12 months: Mar 2025 – Feb 2026):
#   total_uploaded        = 4453
#   total_created         = 14916
#   total_published       = 111
#   avg_monthly_uploads   = 371.08
#   avg_monthly_created   = 1243.0
#   avg_monthly_published = 9.25
#   peak_workload_month   = 'Feb, 2026'  (2756 created)
#   peak_workload_clips   = 2756
#   peak_slice_ratio      = 4.08        (2756 / 676)
#   peak_value_month      = 'Apr, 2025' (44 published)
#   peak_value_pub_count  = 44
#   dec_uploads           = 194
#   feb_uploads           = 676
#   dec_to_feb_surge      = 248.45%
#
# language CSV:
#   en: created=8861, published=91  → en_publish_rate=1.03%
#   hi: created=6021, published=20  → hi_publish_rate=0.33%
#   en_hi_efficacy_multiplier = 3.12
#   en_gen_cost = 97.37
#   hi_gen_cost = 301.05
#
# client_1_combined_data:
#   Channel A published=71 of total 111 → ch_a_contribution_pct = 63.96%
#   Active channels (≥1 publish): A, D, G, I, P, Q → 6 of 18 → 33.33%
#   Dead channels: 12 of 18 → 66.67%
#
# by_user CSV (non-QA):
#   top_volume_user = 'Chandan' (489 uploads)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CORE COUNT METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestCoreCounts:

    def test_total_uploaded_direct(self):
        answer = ask("How many source videos were uploaded to the platform in total?")
        assert_no_clarify(answer)
        assert_contains(answer, "4453", "4,453")

    def test_total_uploaded_synonym_raw(self):
        answer = ask("How many raw videos were ingested into Frammer?")
        assert_no_clarify(answer)
        assert_contains(answer, "4453", "4,453")

    def test_total_created_direct(self):
        answer = ask("How many clips were created in total by the platform?")
        assert_no_clarify(answer)
        assert_contains(answer, "14916", "14,916")

    def test_total_created_ai_phrasing(self):
        # "AI-generated" must map to Created — key domain mapping test
        answer = ask("How many AI-generated clips were produced in total?")
        assert_no_clarify(answer)
        assert_contains(answer, "14916", "14,916")

    def test_total_created_output_phrasing(self):
        answer = ask("What is the total number of output videos generated?")
        assert_no_clarify(answer)
        assert_contains(answer, "14916", "14,916")

    def test_total_published_direct(self):
        answer = ask("How many clips were published across all channels and platforms?")
        assert_no_clarify(answer)
        assert_contains(answer, "111")

    def test_total_published_delivered_phrasing(self):
        answer = ask("How much content was delivered to external platforms in total?")
        assert_no_clarify(answer)
        assert_contains(answer, "111")

    def test_all_three_counts_together(self):
        answer = ask("Give me the total uploaded, created, and published counts.")
        assert_no_clarify(answer)
        assert_contains(answer, "4453", "4,453")
        assert_contains(answer, "14916", "14,916")
        assert_contains(answer, "111")


# ─────────────────────────────────────────────────────────────────────────────
# 2. RATE METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestRateMetrics:

    def test_overall_publish_rate(self):
        # 111 / 14916 * 100 = 0.74%
        answer = ask("What is the overall publish rate across the entire platform?")
        assert_no_clarify(answer)
        assert_contains(answer, "0.74", "0.7")

    def test_overall_creation_multiplier(self):
        # 14916 / 4453 = 3.35
        answer = ask("What is the overall creation multiplier for the platform?")
        assert_no_clarify(answer)
        assert_contains(answer, "3.35", "3.3")

    def test_creation_multiplier_synonym(self):
        answer = ask("On average, how many output clips does Frammer generate per uploaded video?")
        assert_no_clarify(answer)
        assert_contains(answer, "3.35", "3.3")

    def test_upload_to_publish_rate(self):
        # 111 / 4453 * 100 = 2.49%
        answer = ask("What percentage of uploaded videos end up getting published?")
        assert_no_clarify(answer)
        assert_contains(answer, "2.49", "2.5")

    def test_publish_rate_by_month(self):
        answer = ask("Show me the publish rate for each month.")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "monthly publish rate")

    def test_creation_multiplier_by_channel(self):
        answer = ask("Which channel has the highest creation multiplier?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "creation multiplier")

    def test_publish_rate_by_user(self):
        answer = ask("What is the publish rate for each user?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "user publish rate")


# ─────────────────────────────────────────────────────────────────────────────
# 3. MONTHLY AGGREGATE METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestMonthlyAggregates:

    def test_avg_monthly_uploads(self):
        answer = ask("What is the average number of uploads per month?")
        assert_no_clarify(answer)
        assert_contains(answer, "371.08", "371.1", "371")

    def test_avg_monthly_created(self):
        answer = ask("On average, how many clips are created each month?")
        assert_no_clarify(answer)
        assert_contains(answer, "1243.0", "1243", "1,243")

    def test_avg_monthly_published(self):
        answer = ask("What is the average number of clips published per month?")
        assert_no_clarify(answer)
        assert_contains(answer, "9.25", "9.3", "9")

    def test_monthly_trend_all(self):
        answer = ask("Show me the monthly trend for uploads, creations, and publishes.")
        assert_no_clarify(answer)
        # Should contain multiple month labels
        assert "2025" in answer or "2026" in answer

    def test_specific_month_upload(self):
        answer = ask("How many videos were uploaded in April 2025?")
        assert_no_clarify(answer)
        assert_contains(answer, "533")

    def test_specific_month_created(self):
        answer = ask("How many clips were created in February 2026?")
        assert_no_clarify(answer)
        assert_contains(answer, "2756", "2,756")

    def test_specific_month_published(self):
        answer = ask("How many clips were published in January 2026?")
        assert_no_clarify(answer)
        assert_contains(answer, "20")

    def test_specific_month_typo(self):
        # "Februray" should still resolve to Feb, 2026 via fuzzy matching
        answer = ask("How many clips were created in Februray 2026?")
        assert_no_clarify(answer)
        assert_contains(answer, "2756", "2,756")

    def test_zero_published_month(self):
        # Mar 2025, Jul 2025, Sep 2025 all had 0 publishes
        answer = ask("How many clips were published in July 2025?")
        assert_no_clarify(answer)
        assert_contains(answer, "0")


# ─────────────────────────────────────────────────────────────────────────────
# 4. PEAK METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestPeakMetrics:

    def test_peak_workload_month(self):
        answer = ask("Which month had the highest number of AI-generated clips?")
        assert_no_clarify(answer)
        assert_contains(answer, "Feb, 2026", "February, 2026", "February 2026")

    def test_peak_workload_clips(self):
        answer = ask("What was the highest number of clips ever created in a single month?")
        assert_no_clarify(answer)
        assert_contains(answer, "2756", "2,756")

    def test_peak_slice_ratio(self):
        answer = ask("What was the creation multiplier in the busiest month for AI generation?")
        assert_no_clarify(answer)
        assert_contains(answer, "4.08", "4.1")

    def test_peak_value_month(self):
        answer = ask("Which month had the most published clips?")
        assert_no_clarify(answer)
        assert_contains(answer, "Apr, 2025", "April, 2025", "April 2025")

    def test_peak_value_pub_count(self):
        answer = ask("What is the highest number of clips published in any single month?")
        assert_no_clarify(answer)
        assert_contains(answer, "44")

    def test_peak_upload_month(self):
        # Mar 2025 had 639 uploads — the highest
        answer = ask("Which month had the most uploads?")
        assert_no_clarify(answer)
        assert_contains(answer, "Mar, 2025", "March, 2025", "March 2025")

    def test_lowest_published_month(self):
        answer = ask("Which months had zero published clips?")
        assert_no_clarify(answer)
        # Mar 2025, Jul 2025, Sep 2025 all had 0
        assert_contains(answer, "2025")


# ─────────────────────────────────────────────────────────────────────────────
# 5. UPLOAD SURGE
# ─────────────────────────────────────────────────────────────────────────────

class TestUploadSurge:

    def test_dec_to_feb_surge_direct(self):
        answer = ask(
            "What was the percentage growth in uploads from December 2025 to February 2026?"
        )
        assert_no_clarify(answer)
        assert_contains(answer, "248.45", "248.5", "248")

    def test_dec_to_feb_surge_natural(self):
        answer = ask("How much did uploads grow between December and February?")
        assert_no_clarify(answer)
        assert_contains(answer, "248.45", "248.5", "248")

    def test_dec_uploads_absolute(self):
        answer = ask("How many videos were uploaded in December 2025?")
        assert_no_clarify(answer)
        assert_contains(answer, "194")

    def test_feb_uploads_absolute(self):
        answer = ask("How many videos were uploaded in February 2026?")
        assert_no_clarify(answer)
        assert_contains(answer, "676")


# ─────────────────────────────────────────────────────────────────────────────
# 6. CHANNEL METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestChannelMetrics:

    def test_best_channel_by_publish_rate(self):
        answer = ask("Which channel has the highest publish rate?")
        assert_no_clarify(answer)
        assert re.search(r"\b[A-R]\b", answer), \
            f"Expected a channel letter (A–R) in:\n\n{answer}"

    def test_channel_publish_rate_leaderboard(self):
        answer = ask("Show me the publish rate for every channel.")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "channel publish rate")

    def test_ch_a_contribution(self):
        answer = ask("What percentage of all published clips came from Channel A?")
        assert_no_clarify(answer)
        assert_contains(answer, "63.96", "63.9", "64")

    def test_active_channel_ratio(self):
        answer = ask("What percentage of channels have published at least one clip?")
        assert_no_clarify(answer)
        assert_contains(answer, "33.33", "33.3", "33")

    def test_dead_channel_pct(self):
        answer = ask("What percentage of channels have never published anything?")
        assert_no_clarify(answer)
        assert_contains(answer, "66.67", "66.7", "66")

    def test_top_channel_by_uploads(self):
        answer = ask("Which channel has the most uploaded source videos?")
        assert_no_clarify(answer)
        assert re.search(r"\b[A-R]\b", answer)

    def test_channel_creation_multiplier(self):
        answer = ask("What is the creation multiplier for Channel A?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "Channel A creation multiplier")

    def test_youtube_workload_is_numeric(self):
        answer = ask(
            "How many total seconds of content have been published to YouTube across all channels?"
        )
        assert_no_clarify(answer)
        assert_is_numeric(answer, "youtube_workload_secs")

    def test_channel_youtube_leaders(self):
        answer = ask("Which channel has published the most YouTube content by duration?")
        assert_no_clarify(answer)
        assert re.search(r"\b[A-R]\b", answer)

    def test_platform_breakdown_for_channel(self):
        answer = ask("How many clips did Channel D publish to each platform?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "Channel D platform breakdown")


# ─────────────────────────────────────────────────────────────────────────────
# 7. USER METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestUserMetrics:

    def test_top_uploader_no_qa(self):
        answer = ask("Who uploaded the most videos? Exclude QA and test accounts.")
        assert_no_clarify(answer)
        assert_contains(answer, "Chandan")

    def test_top_uploader_leaderboard_implicit_qa_exclusion(self):
        # "leaderboard" trigger should auto-exclude QA per system prompt rule
        answer = ask("Show me the user upload leaderboard.")
        assert_no_clarify(answer)
        assert_contains(answer, "Chandan")

    def test_best_efficiency_user_is_real(self):
        answer = ask(
            "Which user has the highest publish rate, excluding QA accounts "
            "and with at least one published clip?"
        )
        assert_no_clarify(answer)
        assert_not_contains(answer, "QA-")
        assert_not_contains(answer, "Test User")
        assert_is_numeric(answer, "publish rate")

    def test_zero_value_users_count(self):
        answer = ask(
            "How many real users have never published a single clip? Exclude QA accounts."
        )
        assert_no_clarify(answer)
        assert_is_numeric(answer, "zero_value_users")

    def test_specific_user_harish(self):
        answer = ask("Show me Harish's upload, creation, and publish stats.")
        assert_no_clarify(answer)
        assert_contains(answer, "41")     # uploaded count
        assert_contains(answer, "166")    # created count
        assert_contains(answer, "7")      # published count

    def test_specific_user_chandan(self):
        answer = ask("What are Chandan's total uploads and publish rate?")
        assert_no_clarify(answer)
        assert_contains(answer, "489")

    def test_user_creation_multiplier(self):
        answer = ask("Which user generates the most AI clips per uploaded video?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "user creation multiplier")

    def test_user_stats_by_channel(self):
        answer = ask("Who are the top uploaders in Channel A?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "Channel A users")

    def test_users_with_most_published(self):
        answer = ask("Which users have published the most clips?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "most published users")


# ─────────────────────────────────────────────────────────────────────────────
# 8. LANGUAGE METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestLanguageMetrics:

    def test_en_publish_rate(self):
        answer = ask("What is the publish rate for English content?")
        assert_no_clarify(answer)
        assert_contains(answer, "1.03", "1.0")

    def test_hi_publish_rate_full_name(self):
        # "Hindi" must resolve silently to "hi" via language normalizer
        answer = ask("What is the publish rate for Hindi content?")
        assert_no_clarify(answer)
        assert_contains(answer, "0.33", "0.3")

    def test_hi_publish_rate_code(self):
        # Direct code should also work
        answer = ask("What is the publish rate for language hi?")
        assert_no_clarify(answer)
        assert_contains(answer, "0.33", "0.3")

    def test_en_hi_efficacy_multiplier(self):
        answer = ask(
            "How many times more effective is English content compared to Hindi?"
        )
        assert_no_clarify(answer)
        assert_contains(answer, "3.12", "3.1", "3.0")

    def test_en_gen_cost(self):
        answer = ask("How many AI clips are needed per published clip for English content?")
        assert_no_clarify(answer)
        assert_contains(answer, "97.37", "97.4", "97")

    def test_hi_gen_cost(self):
        answer = ask("What is the generation cost per published clip for Hindi?")
        assert_no_clarify(answer)
        assert_contains(answer, "301.05", "301.1", "301")

    def test_language_publish_rate_all(self):
        answer = ask("Compare the publish rates across all languages.")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "all languages publish rate")

    def test_english_vs_hindi_volume(self):
        answer = ask("How many clips were created for English vs Hindi content?")
        assert_no_clarify(answer)
        assert_contains(answer, "8861", "8,861")
        assert_contains(answer, "6021", "6,021")

    def test_hindi_typo(self):
        # "Hindii" should fuzzy-match to "hi" via language normalizer
        answer = ask("What is the publish rate for Hindii videos?")
        assert_no_clarify(answer)
        assert_contains(answer, "0.33", "0.3")


# ─────────────────────────────────────────────────────────────────────────────
# 9. DURATION METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestDurationMetrics:

    def test_total_uploaded_duration(self):
        answer = ask("What is the total duration of all uploaded source videos?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "uploaded duration")

    def test_total_created_duration(self):
        answer = ask("What is the total duration of all AI-generated clips?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "created duration")

    def test_total_published_duration(self):
        answer = ask("What is the total duration of all published clips?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "published duration")

    def test_compression_ratio(self):
        answer = ask(
            "What is the compression ratio — how does total created duration "
            "compare to total uploaded duration?"
        )
        assert_no_clarify(answer)
        assert_is_numeric(answer, "compression ratio")

    def test_avg_clip_duration(self):
        answer = ask("What is the average duration of a created clip?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "avg clip duration")

    def test_uploaded_duration_by_user(self):
        answer = ask("Which user uploaded the most content by total duration?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "user uploaded duration")

    def test_youtube_duration_by_channel(self):
        answer = ask("How many hours of content has each channel published to YouTube?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "youtube hours per channel")

    def test_duration_by_month(self):
        answer = ask("Show me the total uploaded and created duration for each month.")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "monthly duration")


# ─────────────────────────────────────────────────────────────────────────────
# 10. DATA QUALITY METRIC
# ─────────────────────────────────────────────────────────────────────────────

class TestDataQuality:

    def test_unknown_team_direct(self):
        # Ask using the exact column value — must not say "data unavailable"
        answer = ask(
            "What percentage of rows in the video list have team_name equal to Unknown?"
        )
        assert_no_clarify(answer)
        assert_is_percentage(answer, min_val=50)

    def test_unknown_team_natural(self):
        answer = ask("How complete is the team attribution data?")
        assert_no_clarify(answer)
        assert_is_numeric(answer, "team attribution completeness")

    def test_unknown_team_counts_unknowns(self):
        # The metric counts Unknown rows — pipeline must not refuse
        answer = ask(
            "How many video records have no valid team assigned?"
        )
        assert_no_clarify(answer)
        assert_is_numeric(answer, "unattributed records")


# ─────────────────────────────────────────────────────────────────────────────
# 11. ENTITY CLARIFICATION — ambiguous / misspelled names
# ─────────────────────────────────────────────────────────────────────────────

class TestEntityClarification:

    def test_typo_neha(self):
        # "neh" should silently resolve to "Neha" (≥0.80 confidence)
        answer = ask("Show me neh's upload stats.")
        assert_contains(answer, "Neha", "158")

    def test_typo_chandan_lowercase(self):
        # "chandan" should silently resolve to "Chandan"
        answer = ask("What is chandan's publish rate?")
        assert_no_clarify(answer)
        assert_contains(answer, "Chandan", "chandan")

    def test_ambiguous_harry_asks_for_confirmation(self):
        # "harry" is similar to "Harish" but not certain — must ask
        answer = ask("Give me information about harry.")
        assert_contains(answer, "Harish", "CLARIFY", "Did you mean")

    def test_unknown_name_alice_asks_for_clarification(self):
        # No close match — must ask user to clarify
        answer = ask("Show me alice's stats.")
        assert any(phrase in answer.lower() for phrase in [
            "couldn't find", "could not find", "did you mean", "check the spelling"
        ]), f"Expected clarification for 'alice', got:\n\n{answer}"

    def test_month_full_name_resolves(self):
        # "February 2026" must resolve to "Feb, 2026" silently
        answer = ask("How many clips were uploaded in February 2026?")
        assert_no_clarify(answer)
        assert_contains(answer, "676")

    def test_month_typo_resolves(self):
        # "Aprril" should resolve to "Apr, 2025"
        answer = ask("How many clips were published in Aprril 2025?")
        assert_no_clarify(answer)
        assert_contains(answer, "44")

    def test_language_full_name_hindi_resolves(self):
        # "Hindi" → "hi" via language normalizer, no confirmation needed
        answer = ask("How many videos were created in the Hindi language?")
        assert_no_clarify(answer)
        assert_contains(answer, "6021", "6,021")

    def test_language_full_name_english_resolves(self):
        answer = ask("How many videos were uploaded in English?")
        assert_no_clarify(answer)
        assert_contains(answer, "2647", "2,647")


# ─────────────────────────────────────────────────────────────────────────────
# 12. CANNOT_ANSWER GUARDS
# ─────────────────────────────────────────────────────────────────────────────

class TestCannotAnswer:

    def test_financial_revenue(self):
        answer = ask("What is the total revenue generated from published videos?")
        assert_cannot_answer(answer)

    def test_financial_cost(self):
        answer = ask("How much does it cost to generate one AI clip?")
        assert_cannot_answer(answer)

    def test_financial_roi(self):
        answer = ask("What is the ROI for Channel A?")
        assert_cannot_answer(answer)

    def test_team_analysis(self):
        answer = ask("Which team published the most clips?")
        assert_cannot_answer(answer)

    def test_out_of_range_future(self):
        answer = ask("How many uploads were there in March 2026?")
        assert_cannot_answer(answer)

    def test_out_of_range_past(self):
        answer = ask("What was the upload count in January 2025?")
        assert_cannot_answer(answer)

    def test_sub_monthly_date_filter(self):
        answer = ask("How many videos were uploaded on March 15, 2025?")
        assert_cannot_answer(answer)

    def test_viewer_engagement(self):
        answer = ask("How many views did the published YouTube clips get?")
        assert_cannot_answer(answer)

    def test_competitor_comparison(self):
        answer = ask("How does Channel A compare to competitors?")
        assert_cannot_answer(answer)

    def test_user_demographics(self):
        answer = ask("What is the age distribution of users on the platform?")
        assert_cannot_answer(answer)
