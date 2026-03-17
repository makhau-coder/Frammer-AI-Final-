import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# paths
DATA_PATH      = os.getenv("DATA_PATH", os.path.join(BASE_DIR, "data/raw"))
PROCESSED_PATH = os.path.join(BASE_DIR, "data/processed")
DATABASE_PATH  = os.path.join(BASE_DIR, "frammer_analytics.duckdb")

# NLQ
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# default filters
DEFAULT_DATE_RANGE = 30

# ── CSV file paths ──────────────────────────────────────────────────────────
CSV_FILES = {
    "users"        : os.path.join(DATA_PATH, "combined_data(2025-3-1-2026-2-28) by user.csv"),
    "channels"     : os.path.join(DATA_PATH, "CLIENT 1 combined_data(2025-3-1-2026-2-28).csv"),
    "channel_user" : os.path.join(DATA_PATH, "combined_data(2025-3-1-2026-2-28) by channel and user.csv"),
    "input_types"  : os.path.join(DATA_PATH, "combined_data(2025-3-1-2026-2-28) by input type.csv"),
    "output_types" : os.path.join(DATA_PATH, "combined_data(2025-3-1-2026-2-28) by output type.csv"),
    "languages"    : os.path.join(DATA_PATH, "combined_data(2025-3-1-2026-2-28) by language.csv"),
    "monthly"      : os.path.join(DATA_PATH, "monthly-chart.csv"),
    "monthly_dur"  : os.path.join(DATA_PATH, "month-wise-duration.csv"),
    "publishing"   : os.path.join(DATA_PATH, "channel-wise-publishing.csv"),
    "pub_duration" : os.path.join(DATA_PATH, "channel-wise-publishing duration.csv"),
    "video_list"   : os.path.join(DATA_PATH, "video_list_data_obfuscated.csv"),
}

# ── Column name standardisation ─────────────────────────────────────────────
COLUMN_MAPPINGS = {
    "Uploaded Count"               : "uploaded_count",
    "Created Count"                : "created_count",
    "Published Count"              : "published_count",
    "Uploaded Duration (hh:mm:ss)" : "uploaded_duration",
    "Created Duration (hh:mm:ss)"  : "created_duration",
    "Published Duration (hh:mm:ss)": "published_duration",
    "User"                         : "user_name",
    "Channel"                      : "channel_name",
    "Input Type"                   : "input_type",
    "Output Type"                  : "output_type",
    "Language"                     : "language",
    "Month"                        : "month",
    "Headline"                     : "headline",
    "Source"                       : "source",
    "Published"                    : "is_published",
    "Team Name"                    : "team_name",
    "Type"                         : "input_type",
    "Uploaded By"                  : "uploaded_by",
    "Video ID"                     : "video_id",
    "Published Platform"           : "published_platform",
    "Published URL"                : "published_url",
}

# ── Data quality settings ───────────────────────────────────────────────────
NULL_EQUIVALENTS = [
    "Unknown", "unknown",
    "N/A", "n/a", "NA",
    "none", "None",
    "", " ",
]

REQUIRED_COLUMNS = {
    "video_list" : ["video_id", "uploaded_by", "input_type"],
    "users"      : ["user_name"],
    "channels"   : ["channel_name"],
}

# ── QA accounts to exclude from all user-facing analytics ──────────────────
QA_ACCOUNTS = [
    "Test User",
    "deleteme@frammer.com",
    "Auto Upload",
    "QA-Ankith",
    "QA-Aniket",
    "QA-Bhargavi",
    "QA-Purushottam",
    "QA-Amit",
]

# ── KPI definitions ─────────────────────────────────────────────────────────
NORTH_STAR_METRIC = "published_count"

GUARDIAN_METRICS = [
    "publish_rate",
    "platform_coverage",
    "team_name_coverage",
]

KPI_DEFINITIONS = {
    "publish_rate"         : "published_count / created_count * 100",
    "multiplication_ratio" : "created_count / uploaded_count",
    "unpublished_gap"      : "created_count - published_count",
    "active_channel_rate"  : "channels_with_publish / total_channels * 100",
    "mom_growth"           : "(current_month - previous_month) / previous_month * 100",
}

# ── Star schema table names ─────────────────────────────────────────────────
DB_TABLES = {
    "dim_user"        : "dim_user",
    "dim_channel"     : "dim_channel",
    "dim_input_type"  : "dim_input_type",
    "dim_output_type" : "dim_output_type",
    "dim_language"    : "dim_language",
    "dim_date"        : "dim_date",
    "fact_video"      : "fact_video",
}

# ── API settings ────────────────────────────────────────────────────────────
API_HOST         = "localhost"
API_PORT         = int(os.getenv("API_PORT", 8000))
REFRESH_INTERVAL = 30

# ── Verification ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("CONFIG VERIFICATION")
    print("=" * 50)
    print(f"BASE_DIR : {BASE_DIR}")
    print(f"DATA_PATH: {DATA_PATH}")
    print(f"DB_PATH  : {DATABASE_PATH}")
    print()
    print("CSV Files:")
    for name, path in CSV_FILES.items():
        exists = os.path.exists(path)
        status = "✅" if exists else "❌ NOT FOUND"
        print(f"  {name:<15} → {status}  ({path})")
