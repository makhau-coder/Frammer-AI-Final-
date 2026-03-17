# nlp/examples.py
#
# Few-shot Q → SQL example pairs stored in ChromaDB.
# When a user query arrives, semantically similar examples are retrieved
# and included in the prompt so Gemini can follow proven patterns
# rather than inventing its own approach.
#
# GROUND TRUTH column names verified 2026-03-13:
#   monthly_chart:            "Total Uploaded", "Total Created", "Total Published"
#   all combined_data_*:      "Uploaded Count", "Created Count", "Published Count"
#   all combined_data_*:      "Uploaded Duration (hh:mm:ss)_secs/_raw"
#   month_wise_duration:      "Total Uploaded/Created/Published Duration_secs/_raw"
#   channel_wise_publishing:  WIDE — "Facebook","Instagram","Linkedin","Reels",
#                             "Shorts","X","Youtube","Threads" (no "Total Published")
#   channel_wise_pub_dur:     "<Platform> Duration_secs/_raw" per platform
#   user column:              "User" (NOT "Uploaded By")
#   video_list:               lowercase columns, no quotes needed

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
ORDER BY "Month";
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
ORDER BY "Month";
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
ORDER BY "Month";
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
ORDER BY "Month";
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
ORDER BY "Month";
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
ORDER BY d."Month";
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
ORDER BY "Month";
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
        "id": "ex_channel_overall_summary",
        "type": "example",
        "tables": ["client_1_combined_data_2025_3_1_2026_2_28"],
        "text": """
Question: Give me an overall production summary for each channel.
SQL:
SELECT "Channel",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM client_1_combined_data_2025_3_1_2026_2_28
ORDER BY "Uploaded Count" DESC;
"""
    },

    {
        "id": "ex_channel_creation_multiplier",
        "type": "example",
        "tables": ["client_1_combined_data_2025_3_1_2026_2_28"],
        "text": """
Question: Which channel generates the most output videos per source upload?
SQL:
SELECT "Channel",
       "Uploaded Count",
       "Created Count",
       ROUND("Created Count" * 1.0 / NULLIF("Uploaded Count", 0), 2)
           AS creation_multiplier
FROM client_1_combined_data_2025_3_1_2026_2_28
ORDER BY creation_multiplier DESC;
"""
    },

    {
        "id": "ex_channel_uploaded_hours",
        "type": "example",
        "tables": ["client_1_combined_data_2025_3_1_2026_2_28"],
        "text": """
Question: How many hours of source content has each channel uploaded?
SQL:
SELECT "Channel",
       "Uploaded Duration (hh:mm:ss)_raw",
       ROUND("Uploaded Duration (hh:mm:ss)_secs" / 3600.0, 2) AS uploaded_hours
FROM client_1_combined_data_2025_3_1_2026_2_28
ORDER BY "Uploaded Duration (hh:mm:ss)_secs" DESC;
"""
    },

    # ──────────────────────────────────────────────────────────────────
    # USER QUERIES
    # ──────────────────────────────────────────────────────────────────

    {
        "id": "ex_user_leaderboard",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Show me a full leaderboard of users ranked by total uploads.
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_user
ORDER BY "Uploaded Count" DESC;
"""
    },

    {
        "id": "ex_top_user_by_uploads",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which user uploaded the most videos?
SQL:
SELECT "User", "Uploaded Count"
FROM combined_data_2025_3_1_2026_2_28_by_user
ORDER BY "Uploaded Count" DESC
LIMIT 1;
"""
    },

    {
        "id": "ex_top_user_by_publish_rate",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which user has the highest publish rate?
SQL:
SELECT "User",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_user
ORDER BY publish_rate_pct DESC
LIMIT 1;
"""
    },

    {
        "id": "ex_specific_user_stats",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_user"],
        "text": """
Question: What are the stats for user Chandan?
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_user
WHERE "User" = 'Chandan';
"""
    },

    {
        "id": "ex_user_uploaded_hours",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_user"],
        "text": """
Question: How many hours of content has each user uploaded?
SQL:
SELECT "User",
       "Uploaded Duration (hh:mm:ss)_raw",
       ROUND("Uploaded Duration (hh:mm:ss)_secs" / 3600.0, 2) AS uploaded_hours
FROM combined_data_2025_3_1_2026_2_28_by_user
ORDER BY "Uploaded Duration (hh:mm:ss)_secs" DESC;
"""
    },

    {
        "id": "ex_user_creation_multiplier",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_user"],
        "text": """
Question: Which user has the highest creation multiplier?
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       ROUND("Created Count" * 1.0 / NULLIF("Uploaded Count", 0), 2)
           AS creation_multiplier
FROM combined_data_2025_3_1_2026_2_28_by_user
ORDER BY creation_multiplier DESC;
"""
    },

    {
        "id": "ex_top_user_per_channel",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_channel_and_user"],
        "text": """
Question: Who is the top uploading user within each channel?
SQL:
SELECT "Channel", "User", "Uploaded Count"
FROM combined_data_2025_3_1_2026_2_28_by_channel_and_user
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
        "tables": ["combined_data_2025_3_1_2026_2_28_by_channel_and_user"],
        "text": """
Question: Show me all user activity within channel L.
SQL:
SELECT "User",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_channel_and_user
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
        "tables": ["combined_data_2025_3_1_2026_2_28_by_input_type"],
        "text": """
Question: What types of source content does Frammer process most?
SQL:
SELECT "Input Type",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_input_type
ORDER BY "Uploaded Count" DESC;
"""
    },

    {
        "id": "ex_output_type_breakdown",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_output_type"],
        "text": """
Question: Which output type does Frammer produce the most and which has the best publish rate?
SQL:
SELECT "Output Type",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_output_type
ORDER BY "Created Count" DESC;
"""
    },

    {
        "id": "ex_language_breakdown",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_language"],
        "text": """
Question: Which language has the most content uploaded to Frammer?
SQL:
SELECT "Language",
       "Uploaded Count",
       "Created Count",
       "Published Count",
       ROUND("Published Count" * 100.0 / NULLIF("Created Count", 0), 2)
           AS publish_rate_pct
FROM combined_data_2025_3_1_2026_2_28_by_language
ORDER BY "Uploaded Count" DESC;
"""
    },

    {
        "id": "ex_input_type_duration",
        "type": "example",
        "tables": ["combined_data_2025_3_1_2026_2_28_by_input_type"],
        "text": """
Question: How many hours of each input type have been uploaded?
SQL:
SELECT "Input Type",
       "Uploaded Duration (hh:mm:ss)_raw",
       ROUND("Uploaded Duration (hh:mm:ss)_secs" / 3600.0, 2) AS uploaded_hours
FROM combined_data_2025_3_1_2026_2_28_by_input_type
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
        "id": "ex_cannot_team",
        "type": "example",
        "tables": [],
        "text": """
Question: Which team has the highest publish rate?
SQL:
CANNOT_ANSWER: Team data is not available — all team_name values are 'Unknown'.
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

]
