# nlp/examples.py
#
# Few-shot Q → SQL example pairs stored in ChromaDB.
# When a user query arrives, semantically similar examples are retrieved
# and included in the prompt so Gemini can follow proven patterns
# rather than inventing its own approach.
#
# GROUND TRUTH column names verified 2026-03-20:
#   monthly_chart:            "Total Uploaded", "Total Created", "Total Published"
#   all combined_data_*:      "Uploaded Count", "Created Count", "Published Count"
#   all combined_data_*:      "Uploaded Duration (hh:mm:ss)_secs/_raw"
#   month_wise_duration:      "Total Uploaded/Created/Published Duration_secs/_raw"
#   channel_wise_publishing:  WIDE — "Facebook","Instagram","Linkedin","Reels",
#                             "Shorts","X","Youtube","Threads" (no "Total Published")
#   channel_wise_publishing_duration:     "<Platform> Duration_secs/_raw" per platform
#   user column:              "User" (NOT "Uploaded By")
#   video_list:               lowercase columns, no quotes needed
#
# ORDERING RULE: Always use STRPTIME("Month", '%b, %Y') for chronological
# ordering of Month columns. Plain ORDER BY "Month" sorts alphabetically.
#
# QA FILTER: Exclude QA/test users with:
#   WHERE "User" NOT LIKE 'QA-%'
#     AND "User" NOT IN ('Test User', 'Auto Upload', 'deleteme@frammer.com')


EXAMPLES: list[dict] = [


    # ──────────────────────────────────────────────────────────────────
    # MONTHLY TREND QUERIES
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_monthly_upload_trend",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: Show me the monthly upload trend.
SQL:
SELECT "Month", "Total Uploaded", "Total Created", "Total Published"
FROM monthly_chart
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    {
        "id": "ex_peak_upload_month",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: Which month had the highest number of uploads?
SQL:
SELECT "Month", "Total Uploaded"
FROM monthly_chart
ORDER BY "Total Uploaded" DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_specific_month_stats",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: How many videos were uploaded, created, and published in February 2026?
SQL:
SELECT "Month", "Total Uploaded", "Total Created", "Total Published"
FROM monthly_chart
WHERE "Month" = 'Feb, 2026';
"""
    },


    {
        "id": "ex_monthly_publish_rate",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: What is the publish rate for each month?
SQL:
SELECT "Month",
       "Total Created",
       "Total Published",
       ROUND("Total Published" * 100.0 / NULLIF("Total Created", 0), 2)
           AS publish_rate_pct
FROM monthly_chart
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    {
        "id": "ex_monthly_creation_multiplier",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: How many output videos does Frammer generate per uploaded video each month?
SQL:
SELECT "Month",
       "Total Uploaded",
       "Total Created",
       ROUND("Total Created" * 1.0 / NULLIF("Total Uploaded", 0), 2)
           AS creation_multiplier
FROM monthly_chart
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    {
        "id": "ex_total_all_months",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: What are the total uploads, creations, and publications across all months combined?
SQL:
SELECT SUM("Total Uploaded")  AS total_uploaded,
       SUM("Total Created")   AS total_created,
       SUM("Total Published") AS total_published
FROM monthly_chart;
"""
    },


    {
        "id": "ex_monthly_averages",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: What is the average number of videos uploaded, created, and published per month?
SQL:
SELECT
    ROUND(AVG("Total Uploaded"),  2) AS avg_monthly_uploads,
    ROUND(AVG("Total Created"),   2) AS avg_monthly_created,
    ROUND(AVG("Total Published"), 2) AS avg_monthly_published
FROM monthly_chart;
"""
    },


    {
        "id": "ex_peak_workload",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: Which month was the busiest for AI video generation? What was the creation multiplier that month?
SQL:
WITH ranked AS (
    SELECT "Month",
           "Total Created",
           "Total Uploaded",
           ROUND("Total Created" * 1.0 / NULLIF("Total Uploaded", 0), 2)
               AS peak_slice_ratio
    FROM monthly_chart
    ORDER BY "Total Created" DESC
    LIMIT 1
)
SELECT
    "Month"           AS peak_workload_month,
    "Total Created"   AS peak_workload_clips,
    peak_slice_ratio
FROM ranked;
"""
    },


    {
        "id": "ex_peak_value",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: Which month had the highest number of published clips?
SQL:
SELECT
    "Month"           AS peak_value_month,
    "Total Published" AS peak_value_pub_count
FROM monthly_chart
ORDER BY "Total Published" DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_dec_to_feb_upload_surge",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: How much did uploads grow from December 2025 to February 2026?
SQL:
WITH months AS (
    SELECT
        MAX(CASE WHEN "Month" = 'Dec, 2025' THEN "Total Uploaded" END) AS dec_uploads,
        MAX(CASE WHEN "Month" = 'Feb, 2026' THEN "Total Uploaded" END) AS feb_uploads
    FROM monthly_chart
)
SELECT
    dec_uploads,
    feb_uploads,
    ROUND(
        (feb_uploads - dec_uploads) * 100.0 / NULLIF(dec_uploads, 0),
    2) AS dec_to_feb_upload_surge_pct
FROM months;
"""
    },


    {
        "id": "ex_monthly_upload_to_publish_rate",
        "type": "example",
        "tables": ["monthly_chart"],
        "text": """
Question: What is the end-to-end pipeline efficiency by month — what percentage of uploaded videos result in a published output?
SQL:
SELECT "Month",
       "Total Uploaded",
       "Total Published",
       ROUND("Total Published" * 100.0 / NULLIF("Total Uploaded", 0), 2)
           AS upload_to_publish_rate_pct
FROM monthly_chart
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    # ──────────────────────────────────────────────────────────────────
    # DURATION QUERIES
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_monthly_uploaded_hours",
        "type": "example",
        "tables": ["month_wise_duration"],
        "text": """
Question: How many hours of content were uploaded each month?
SQL:
SELECT "Month",
       "Total Uploaded Duration_raw",
       ROUND("Total Uploaded Duration_secs" / 3600.0, 2) AS uploaded_hours
FROM month_wise_duration
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    {
        "id": "ex_peak_published_duration",
        "type": "example",
        "tables": ["month_wise_duration"],
        "text": """
Question: Which month had the longest total published duration?
SQL:
SELECT "Month",
       "Total Published Duration_raw",
       "Total Published Duration_secs"
FROM month_wise_duration
ORDER BY "Total Published Duration_secs" DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_compression_ratio",
        "type": "example",
        "tables": ["month_wise_duration"],
        "text": """
Question: What is the duration compression ratio by month? How much shorter are
Frammer's outputs compared to the source content?
SQL:
SELECT "Month",
       "Total Uploaded Duration_raw",
       "Total Created Duration_raw",
       ROUND("Total Created Duration_secs" * 1.0
           / NULLIF("Total Uploaded Duration_secs", 0), 3)
           AS compression_ratio
FROM month_wise_duration
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    {
        "id": "ex_avg_video_duration_by_month",
        "type": "example",
        "tables": ["month_wise_duration", "monthly_chart"],
        "text": """
Question: What is the average duration of created videos per month in minutes?
SQL:
SELECT d."Month",
       ROUND(d."Total Created Duration_secs" * 1.0
           / NULLIF(c."Total Created", 0) / 60.0, 2)
           AS avg_created_duration_mins
FROM month_wise_duration d
JOIN monthly_chart c ON d."Month" = c."Month"
ORDER BY STRPTIME(d."Month", '%b, %Y');
"""
    },


    {
        "id": "ex_total_uploaded_hours_all_time",
        "type": "example",
        "tables": ["month_wise_duration"],
        "text": """
Question: What is the total number of hours of all content ever uploaded to Frammer?
SQL:
SELECT ROUND(SUM("Total Uploaded Duration_secs") / 3600.0, 2)
    AS total_uploaded_hours
FROM month_wise_duration;
"""
    },


    {
        "id": "ex_monthly_duration_summary",
        "type": "example",
        "tables": ["month_wise_duration"],
        "text": """
Question: Show me uploaded, created, and published duration hours for every month.
SQL:
SELECT "Month",
       "Total Uploaded Duration_raw",
       ROUND("Total Uploaded Duration_secs" / 3600.0, 2)  AS uploaded_hours,
       "Total Created Duration_raw",
       ROUND("Total Created Duration_secs" / 3600.0, 2)   AS created_hours,
       "Total Published Duration_raw",
       ROUND("Total Published Duration_secs" / 3600.0, 2) AS published_hours
FROM month_wise_duration
ORDER BY STRPTIME("Month", '%b, %Y');
"""
    },


    # ──────────────────────────────────────────────────────────────────
    # CHANNEL QUERIES
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_top_channel_by_published",
        "type": "example",
        "tables": ["channel_wise_publishing"],
        "text": """
Question: Which channel has published the most videos?
SQL:
SELECT "Channel",
       "Facebook" + "Instagram" + "Linkedin" + "Reels" + "Shorts"
       + "X" + "Youtube" + "Threads" AS total_published
FROM channel_wise_publishing
ORDER BY total_published DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_channel_platform_breakdown",
        "type": "example",
        "tables": ["channel_wise_publishing"],
        "text": """
Question: Show me publishing counts for all channels across all platforms.
SQL:
SELECT "Channel", platform, published_count
FROM channel_wise_publishing
UNPIVOT (published_count FOR platform IN (
    "Facebook", "Instagram", "Linkedin", "Reels",
    "Shorts", "X", "Youtube", "Threads"
))
ORDER BY "Channel", published_count DESC;
"""
    },


    {
        "id": "ex_channel_platform_preference",
        "type": "example",
        "tables": ["channel_wise_publishing"],
        "text": """
Question: Which platform does each channel use most for publishing?
SQL:
SELECT "Channel", platform, published_count
FROM channel_wise_publishing
UNPIVOT (published_count FOR platform IN (
    "Facebook", "Instagram", "Linkedin", "Reels",
    "Shorts", "X", "Youtube", "Threads"
))
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY "Channel"
    ORDER BY published_count DESC
) = 1
ORDER BY "Channel";
"""
    },


    {
        "id": "ex_channel_all_published_totals",
        "type": "example",
        "tables": ["channel_wise_publishing"],
        "text": """
Question: Show total published count for every channel.
SQL:
SELECT "Channel",
       "Facebook" + "Instagram" + "Linkedin" + "Reels" + "Shorts"
       + "X" + "Youtube" + "Threads" AS total_published
FROM channel_wise_publishing
ORDER BY total_published DESC;
"""
    },


    {
        "id": "ex_channel_published_hours",
        "type": "example",
        "tables": ["channel_wise_publishing_duration"],
        "text": """
Question: How many hours of content has each channel published in total across all platforms?
SQL:
SELECT "Channel",
       ROUND((
           "Facebook Duration_secs" + "Instagram Duration_secs" +
           "Linkedin Duration_secs" + "Reels Duration_secs" +
           "Shorts Duration_secs"   + "X Duration_secs" +
           "Youtube Duration_secs"  + "Threads Duration_secs"
       ) / 3600.0, 2) AS total_published_hours
FROM channel_wise_publishing_duration
ORDER BY total_published_hours DESC;
"""
    },


    {
        "id": "ex_channel_youtube_hours",
        "type": "example",
        "tables": ["channel_wise_publishing_duration"],
        "text": """
Question: Which channel has published the most hours to YouTube?
SQL:
SELECT "Channel",
       "Youtube Duration_raw",
       ROUND("Youtube Duration_secs" / 3600.0, 2) AS youtube_hours
FROM channel_wise_publishing_duration
ORDER BY "Youtube Duration_secs" DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_youtube_total_workload",
        "type": "example",
        "tables": ["channel_wise_publishing_duration", "channel_wise_publishing"],
        "text": """
Question: What is the total hours of content published to YouTube across all channels?
SQL:
SELECT
    ROUND(SUM("Youtube Duration_secs") / 3600.0, 2) AS youtube_total_hours,
    SUM("Youtube Duration_secs")                     AS youtube_workload_secs
FROM channel_wise_publishing_duration;
"""
    },


    {
        "id": "ex_channel_overall_summary",
        "type": "example",
        "tables": ["client_1_combined_data2025_3_1_2026_2_28"],
        "text": """
Question: Give me an overall production summary for each channel.
SQL:
SELECT "Channel",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM client_1_combined_data2025_3_1_2026_2_28
ORDER BY "Uploaded Count" DESC;
"""
    },


    {
        "id": "ex_channel_creation_multiplier",
        "type": "example",
        "tables": ["client_1_combined_data2025_3_1_2026_2_28"],
        "text": """
Question: Which channel generates the most output videos per source upload?
SQL:
SELECT "Channel",
       "Uploaded Count",
       "Created Count",
       ROUND("Created Count" * 1.0 / NULLIF("Uploaded Count", 0), 2)
           AS creation_multiplier
FROM client_1_combined_data2025_3_1_2026_2_28
ORDER BY creation_multiplier DESC;
"""
    },


    {
        "id": "ex_channel_uploaded_hours",
        "type": "example",
        "tables": ["client_1_combined_data2025_3_1_2026_2_28"],
        "text": """
Question: How many hours of source content has each channel uploaded?
SQL:
SELECT "Channel",
       "Uploaded Duration (hh:mm:ss)_raw",
       ROUND("Uploaded Duration (hh:mm:ss)_secs" / 3600.0, 2) AS uploaded_hours
FROM client_1_combined_data2025_3_1_2026_2_28
ORDER BY "Uploaded Duration (hh:mm:ss)_secs" DESC;
"""
    },


    {
        "id": "ex_best_channel_publish_rate",
        "type": "example",
        "tables": ["client_1_combined_data2025_3_1_2026_2_28"],
        "text": """
Question: Which channel has the highest publish rate? Which channel is most editorially efficient?
SQL:
SELECT
    "Channel"                                                        AS best_channel_name,
    "Created Count",
    "Published Count",
    ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2) AS best_channel_publish_rate
FROM client_1_combined_data2025_3_1_2026_2_28
ORDER BY best_channel_publish_rate DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_channel_a_contribution",
        "type": "example",
        "tables": ["client_1_combined_data2025_3_1_2026_2_28"],
        "text": """
Question: What percentage of all published clips does channel A account for?
SQL:
SELECT
    ROUND(
        MAX(CASE WHEN "Channel" = 'A' THEN "Published Count" END)
        * 100.0 / NULLIF(SUM("Published Count"), 0),
    2) AS ch_a_contribution_pct
FROM client_1_combined_data2025_3_1_2026_2_28;
"""
    },


    {
        "id": "ex_active_dead_channels",
        "type": "example",
        "tables": ["client_1_combined_data2025_3_1_2026_2_28"],
        "text": """
Question: What percentage of channels have published at least one clip? How many channels have published nothing?
SQL:
SELECT
    ROUND(COUNT(*) FILTER (WHERE "Published Count" >= 1) * 100.0
          / NULLIF(COUNT(*), 0), 2) AS active_channel_ratio,
    ROUND(COUNT(*) FILTER (WHERE "Published Count" = 0)  * 100.0
          / NULLIF(COUNT(*), 0), 2) AS dead_channel_pct,
    COUNT(*) FILTER (WHERE "Published Count" = 0)        AS dead_channel_count
FROM client_1_combined_data2025_3_1_2026_2_28;
"""
    },


    # ──────────────────────────────────────────────────────────────────
    # USER QUERIES
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_user_leaderboard",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Show me a full leaderboard of users ranked by total uploads.
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_user
ORDER BY "Uploaded Count" DESC;
"""
    },


    {
        "id": "ex_real_user_leaderboard",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Show me a leaderboard of real users only — exclude QA and test accounts.
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_user
WHERE "User" NOT LIKE 'QA-%'
  AND "User" NOT IN ('Test User', 'Auto Upload', 'deleteme@frammer.com')
ORDER BY "Uploaded Count" DESC;
"""
    },


    {
        "id": "ex_top_user_by_uploads",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which user uploaded the most videos?
SQL:
SELECT "User", "Uploaded Count"
FROM combined_data2025_3_1_2026_2_28_by_user
ORDER BY "Uploaded Count" DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_top_user_by_publish_rate",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which user has the highest publish rate?
SQL:
SELECT "User",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_user
ORDER BY publish_rate_pct DESC
LIMIT 1;
"""
    },


    {
        "id": "ex_specific_user_stats",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: What are the stats for user Chandan?
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_user
WHERE "User" = 'Chandan';
"""
    },


    {
        "id": "ex_user_uploaded_hours",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: How many hours of content has each user uploaded?
SQL:
SELECT "User",
       "Uploaded Duration (hh:mm:ss)_raw",
       ROUND("Uploaded Duration (hh:mm:ss)_secs" / 3600.0, 2) AS uploaded_hours
FROM combined_data2025_3_1_2026_2_28_by_user
ORDER BY "Uploaded Duration (hh:mm:ss)_secs" DESC;
"""
    },


    {
        "id": "ex_user_creation_multiplier",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which user has the highest creation multiplier?
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       ROUND("Created Count" * 1.0 / NULLIF("Uploaded Count", 0), 2)
           AS creation_multiplier
FROM combined_data2025_3_1_2026_2_28_by_user
ORDER BY creation_multiplier DESC;
"""
    },


    {
        "id": "ex_user_upload_to_publish_rate",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: What percentage of each user's uploads eventually get published?
SQL:
SELECT "User",
       "Uploaded Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Uploaded Count", 0), 2)
           AS upload_to_publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_user
ORDER BY upload_to_publish_rate_pct DESC;
"""
    },


    {
        "id": "ex_user_efficiency_all",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Who is the top volume user, most efficient user, and how many users have published nothing? Exclude QA accounts.
SQL:
WITH real_users AS (
    SELECT *
    FROM combined_data2025_3_1_2026_2_28_by_user
    WHERE "User" NOT LIKE 'QA-%'
      AND "User" NOT IN ('Test User', 'Auto Upload', 'deleteme@frammer.com')
)
SELECT
    (SELECT "User" FROM real_users
     ORDER BY "Uploaded Count" DESC LIMIT 1)                           AS top_volume_user,

    (SELECT "User" FROM real_users
     WHERE "Published Count" >= 1
     ORDER BY "Published Count" * 100.0 / NULLIF("Created Count", 0) DESC
     LIMIT 1)                                                           AS best_efficiency_user,

    (SELECT ROUND(MAX("Published Count" * 100.0 / NULLIF("Created Count", 0)), 2)
     FROM real_users WHERE "Published Count" >= 1)                     AS best_efficiency_pub_rate,

    (SELECT COUNT(*) FROM real_users WHERE "Published Count" = 0)      AS zero_value_users;
"""
    },


    {
        "id": "ex_zero_value_users",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which real users have uploaded and created content but never had anything published?
SQL:
SELECT "User", "Uploaded Count", "Created Count"
FROM combined_data2025_3_1_2026_2_28_by_user
WHERE "Published Count" = 0
  AND "Created Count" > 0
  AND "User" NOT LIKE 'QA-%'
  AND "User" NOT IN ('Test User', 'Auto Upload', 'deleteme@frammer.com')
ORDER BY "Created Count" DESC;
"""
    },


    {
        "id": "ex_top_user_per_channel",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_channel_and_user"],
        "text": """
Question: Who is the top uploading user within each channel?
SQL:
SELECT "Channel", "User", "Uploaded Count"
FROM combined_data2025_3_1_2026_2_28_by_channel_and_user
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY "Channel"
    ORDER BY "Uploaded Count" DESC
) = 1
ORDER BY "Channel";
"""
    },


    {
        "id": "ex_user_activity_within_channel",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_channel_and_user"],
        "text": """
Question: Show me all user activity within channel L.
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_channel_and_user
WHERE "Channel" = 'L'
ORDER BY "Uploaded Count" DESC;
"""
    },


    # ──────────────────────────────────────────────────────────────────
    # INPUT TYPE / OUTPUT TYPE / LANGUAGE
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_input_type_breakdown",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_input_type"],
        "text": """
Question: What types of source content does Frammer process most?
SQL:
SELECT "Input Type",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_input_type
ORDER BY "Uploaded Count" DESC;
"""
    },


    {
        "id": "ex_output_type_breakdown",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_output_type"],
        "text": """
Question: Which output type does Frammer produce the most and which has the best publish rate?
SQL:
SELECT "Output Type",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_output_type
ORDER BY "Created Count" DESC;
"""
    },


    {
        "id": "ex_language_breakdown",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_language"],
        "text": """
Question: Which language has the most content uploaded to Frammer?
SQL:
SELECT "Language",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data2025_3_1_2026_2_28_by_language
ORDER BY "Uploaded Count" DESC;
"""
    },


    {
        "id": "ex_language_efficiency",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_language"],
        "text": """
Question: How does the English content pipeline compare to Hindi in terms of publish rate and efficiency?
SQL:
WITH lang AS (
    SELECT
        MAX(CASE WHEN "Language" = 'en' THEN "Published Count" END) AS en_pub,
        MAX(CASE WHEN "Language" = 'en' THEN "Created Count"   END) AS en_cre,
        MAX(CASE WHEN "Language" = 'hi' THEN "Published Count" END) AS hi_pub,
        MAX(CASE WHEN "Language" = 'hi' THEN "Created Count"   END) AS hi_cre
    FROM combined_data2025_3_1_2026_2_28_by_language
)
SELECT
    ROUND(en_pub * 100.0 / NULLIF(en_cre, 0), 2)   AS en_publish_rate,
    ROUND(hi_pub * 100.0 / NULLIF(hi_cre, 0), 2)   AS hi_publish_rate,
    ROUND(
        (en_pub * 100.0 / NULLIF(en_cre, 0)) /
        NULLIF(hi_pub * 100.0 / NULLIF(hi_cre, 0), 0),
    2)                                               AS en_hi_efficacy_multiplier,
    ROUND(en_cre * 1.0 / NULLIF(en_pub, 0), 2)     AS en_gen_cost,
    ROUND(hi_cre * 1.0 / NULLIF(hi_pub, 0), 2)     AS hi_gen_cost
FROM lang;
"""
    },


    {
        "id": "ex_input_type_duration",
        "type": "example",
        "tables": ["combined_data2025_3_1_2026_2_28_by_input_type"],
        "text": """
Question: How many hours of each input type have been uploaded?
SQL:
SELECT "Input Type",
       "Uploaded Duration (hh:mm:ss)_raw",
       ROUND("Uploaded Duration (hh:mm:ss)_secs" / 3600.0, 2) AS uploaded_hours
FROM combined_data2025_3_1_2026_2_28_by_input_type
ORDER BY "Uploaded Duration (hh:mm:ss)_secs" DESC;
"""
    },


    # ──────────────────────────────────────────────────────────────────
    # VIDEO LIST QUERIES
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_video_list_published_platform",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: How many videos were published to each platform?
SQL:
SELECT published_platform,
       COUNT(*) AS published_count
FROM video_list
WHERE published = TRUE
  AND published_platform IS NOT NULL
GROUP BY published_platform
ORDER BY published_count DESC;
"""
    },


    {
        "id": "ex_video_list_user_counts",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: How many videos has each user uploaded at the individual video level?
SQL:
SELECT uploaded_by,
       COUNT(*) AS total_videos,
       SUM(CASE WHEN published THEN 1 ELSE 0 END) AS published_videos,
       ROUND(SUM(CASE WHEN published THEN 1 ELSE 0 END) * 100.0
           / NULLIF(COUNT(*), 0), 2) AS publish_rate_pct
FROM video_list
GROUP BY uploaded_by
ORDER BY total_videos DESC;
"""
    },


    {
        "id": "ex_video_list_by_input_type",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: How many individual videos exist per input type?
SQL:
SELECT input_type,
       COUNT(*) AS total_videos,
       SUM(CASE WHEN published THEN 1 ELSE 0 END) AS published_videos,
       ROUND(SUM(CASE WHEN published THEN 1 ELSE 0 END) * 100.0
           / NULLIF(COUNT(*), 0), 2) AS publish_rate_pct
FROM video_list
GROUP BY input_type
ORDER BY total_videos DESC;
"""
    },


    {
        "id": "ex_video_list_user_platform",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: Which platform does each user publish to most?
SQL:
SELECT uploaded_by, published_platform,
       COUNT(*) AS published_count
FROM video_list
WHERE published = TRUE
  AND published_platform IS NOT NULL
GROUP BY uploaded_by, published_platform
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY uploaded_by
    ORDER BY COUNT(*) DESC
) = 1
ORDER BY uploaded_by;
"""
    },


    {
        "id": "ex_video_list_search_headline",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: Find all videos with 'budget' in the headline.
SQL:
SELECT video_id, headline, uploaded_by, input_type,
       published, published_platform, published_url
FROM video_list
WHERE LOWER(headline) LIKE '%budget%'
ORDER BY video_id;
"""
    },


    {
        "id": "ex_video_list_recent",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: Show me the 10 most recently ingested videos.
SQL:
SELECT video_id, headline, uploaded_by, input_type,
       published, published_platform, ingested_at
FROM video_list
ORDER BY ingested_at DESC
LIMIT 10;
"""
    },


    {
        "id": "ex_unknown_team_attribution",
        "type": "example",
        "tables": ["video_list"],
        "text": """
Question: What percentage of video records have no valid team attribution? How many videos have unknown team data?
SQL:
SELECT
    COUNT(*)                                                          AS total_records,
    COUNT(*) FILTER (WHERE team_name = 'Unknown' OR team_name IS NULL)
                                                                      AS unattributed,
    ROUND(
        COUNT(*) FILTER (WHERE team_name = 'Unknown' OR team_name IS NULL)
        * 100.0 / NULLIF(COUNT(*), 0),
    2)                                                                AS unknown_team_attribution_pct
FROM video_list;
"""
    },


    # ──────────────────────────────────────────────────────────────────
    # CANNOT_ANSWER EXAMPLES
    # ──────────────────────────────────────────────────────────────────


    {
        "id": "ex_cannot_revenue",
        "type": "example",
        "tables": [],
        "text": """
Question: What is the revenue generated per channel?
SQL:
CANNOT_ANSWER: No financial or revenue data exists in this dataset.
"""
    },

    {
        "id": "ex_cannot_date_range",
        "type": "example",
        "tables": [],
        "text": """
Question: How many videos were uploaded between June 15 and July 10, 2025?
SQL:
CANNOT_ANSWER: The dataset does not support filtering within a month. Data is only available at monthly granularity using the format 'Jun, 2025'.
"""
    },


    {
        "id": "ex_cannot_future_month",
        "type": "example",
        "tables": [],
        "text": """
Question: How many videos were uploaded in March 2026?
SQL:
CANNOT_ANSWER: The dataset only covers March 2025 to February 2026. March 2026 data is not available.
"""
    },


    {
        "id": "ex_cannot_outside_range",
        "type": "example",
        "tables": [],
        "text": """
Question: What was the upload count in January 2024?
SQL:
CANNOT_ANSWER: The dataset only covers March 2025 to February 2026. January 2024 data is not available.
"""
    },
# ──────────────────────────────────────────────────────────────────
# CROSS-DIMENSIONAL QUERIES — STAR SCHEMA
# ──────────────────────────────────────────────────────────────────

{
"id": "ex_user_x_platform_breakdown",
"type": "example",
"tables": ["fact_video", "dim_user", "dim_platform"],
"text": """
Question: Show me created and published video counts broken down by user and platform.
SQL:
SELECT
  dim_user.user_name,
  dim_platform.platform_name,
  COUNT(*) AS created_count,
  COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) AS published_count,
  ROUND(
    COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) * 100.0
    / NULLIF(COUNT(*), 0), 2
  ) AS publish_rate_pct
FROM fact_video
JOIN dim_user     ON fact_video.user_id     = dim_user.user_id
JOIN dim_platform ON fact_video.platform_id = dim_platform.platform_id
WHERE dim_user.is_qa_account = FALSE
GROUP BY dim_user.user_name, dim_platform.platform_name
ORDER BY dim_user.user_name, created_count DESC;
"""
},

{
"id": "ex_user_x_platform_top_platform",
"type": "example",
"tables": ["fact_video", "dim_user", "dim_platform"],
"text": """
Question: Which platform does each user publish to most?
SQL:
SELECT dim_user.user_name, dim_platform.platform_name,
  COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) AS published_count
FROM fact_video
JOIN dim_user     ON fact_video.user_id     = dim_user.user_id
JOIN dim_platform ON fact_video.platform_id = dim_platform.platform_id
WHERE dim_user.is_qa_account = FALSE
  AND fact_video.is_published = TRUE
GROUP BY dim_user.user_name, dim_platform.platform_name
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY dim_user.user_name
  ORDER BY COUNT(*) DESC
) = 1
ORDER BY dim_user.user_name;
"""
},

{
"id": "ex_specific_user_platform",
"type": "example",
"tables": ["fact_video", "dim_user", "dim_platform"],
"text": """
Question: How many videos did Chandan create and publish for each platform?
SQL:
SELECT
  dim_platform.platform_name,
  COUNT(*) AS created_count,
  COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) AS published_count
FROM fact_video
JOIN dim_user     ON fact_video.user_id     = dim_user.user_id
JOIN dim_platform ON fact_video.platform_id = dim_platform.platform_id
WHERE dim_user.user_name = 'Chandan'
  AND dim_user.is_qa_account = FALSE
GROUP BY dim_platform.platform_name
ORDER BY created_count DESC;
"""
},

{
"id": "ex_user_x_input_type_breakdown",
"type": "example",
"tables": ["fact_video", "dim_user", "dim_input_type"],
"text": """
Question: Show me created and published counts by user and input type.
SQL:
SELECT
  dim_user.user_name,
  dim_input_type.input_type_name,
  COUNT(*) AS created_count,
  COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) AS published_count,
  ROUND(
    COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) * 100.0
    / NULLIF(COUNT(*), 0), 2
  ) AS publish_rate_pct
FROM fact_video
JOIN dim_user       ON fact_video.user_id       = dim_user.user_id
JOIN dim_input_type ON fact_video.input_type_id = dim_input_type.input_type_id
WHERE dim_user.is_qa_account = FALSE
GROUP BY dim_user.user_name, dim_input_type.input_type_name
ORDER BY dim_user.user_name, created_count DESC;
"""
},

{
"id": "ex_user_x_input_type_dominant",
"type": "example",
"tables": ["fact_video", "dim_user", "dim_input_type"],
"text": """
Question: Which input type does each user work with most?
SQL:
SELECT dim_user.user_name, dim_input_type.input_type_name,
  COUNT(*) AS created_count
FROM fact_video
JOIN dim_user       ON fact_video.user_id       = dim_user.user_id
JOIN dim_input_type ON fact_video.input_type_id = dim_input_type.input_type_id
WHERE dim_user.is_qa_account = FALSE
GROUP BY dim_user.user_name, dim_input_type.input_type_name
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY dim_user.user_name
  ORDER BY COUNT(*) DESC
) = 1
ORDER BY dim_user.user_name;
"""
},

{
"id": "ex_specific_user_input_type",
"type": "example",
"tables": ["fact_video", "dim_user", "dim_input_type"],
"text": """
Question: What input types does Neha work with and how many videos did she create per type?
SQL:
SELECT
  dim_input_type.input_type_name,
  COUNT(*) AS created_count,
  COUNT(*) FILTER (WHERE fact_video.is_published = TRUE) AS published_count
FROM fact_video
JOIN dim_user       ON fact_video.user_id       = dim_user.user_id
JOIN dim_input_type ON fact_video.input_type_id = dim_input_type.input_type_id
WHERE dim_user.user_name = 'Neha'
  AND dim_user.is_qa_account = FALSE
GROUP BY dim_input_type.input_type_name
ORDER BY created_count DESC;
"""
},

{
"id": "ex_cannot_channel_x_input_type",
"type": "example",
"tables": [],
"text": """
Question: Show me upload and creation counts broken down by channel and input type.
SQL:
CANNOT_ANSWER: Channel × Input Type cross-breakdown is not available in any table.
| View channels separately: SELECT FROM client_1_combined_data2025_3_1_2026_2_28
| View input types separately: SELECT FROM combined_data2025_3_1_2026_2_28_by_input_type
| View User × Input Type: JOIN fact_video with dim_user and dim_input_type
"""
},

{
"id": "ex_cannot_user_x_platform_uploads",
"type": "example",
"tables": [],
"text": """
Question: How many videos did each user upload per platform?
SQL:
CANNOT_ANSWER: Upload counts broken down by both User and Platform are not available. The star schema (fact_video) only records created and published videos — it has no upload data. Upload counts are only available as single-dimension summaries (by user or by platform separately).
| View uploads by user: SELECT FROM combined_data2025_3_1_2026_2_28_by_user
| View created/published by user × platform: JOIN fact_video with dim_user and dim_platform
"""
},

{
"id": "ex_cannot_channel_x_language",
"type": "example",
"tables": [],
"text": """
Question: Which language does each channel use most?
SQL:
CANNOT_ANSWER: Channel × Language cross-breakdown is not available in any table.
| View language breakdown overall: SELECT FROM combined_data2025_3_1_2026_2_28_by_language
| View channel breakdown overall: SELECT FROM client_1_combined_data2025_3_1_2026_2_28
"""
},
    {
        "id": "ex_cannot_team",
        "type": "example",
        "tables": [],
        "text": """
Question: Which team published the most clips?
SQL:
CANNOT_ANSWER: Team data is not available — all team_name values in the dataset are 'Unknown'. | Which channel published the most clips? | Which user published the most clips? | What is the publish rate per channel?
"""
    },


]