from enum import Enum

class Strategy(Enum):
    FULL_REPLACE = "full_replace"
    INCREMENTAL  = "incremental"

""" Simple dictionary that stores the dynamic data updation strategy for each file
    Exact Filenames are used as keys, can cause problems later
"""
FILE_CONFIG = {
    "video_list_data_obfuscated.csv":                           Strategy.INCREMENTAL,
    "monthly-chart.csv":                                        Strategy.FULL_REPLACE,
    "month-wise-duration.csv":                                  Strategy.FULL_REPLACE,
    "channel-wise-publishing.csv":                              Strategy.FULL_REPLACE,
    "channel-wise-publishing duration.csv":                     Strategy.FULL_REPLACE,
    "CLIENT 1 combined_data(2025-3-1-2026-2-28).csv":           Strategy.FULL_REPLACE,
    "combined_data(2025-3-1-2026-2-28) by output type.csv":     Strategy.FULL_REPLACE,
    "combined_data(2025-3-1-2026-2-28) by language.csv":        Strategy.FULL_REPLACE,
    "combined_data(2025-3-1-2026-2-28) by input type.csv":      Strategy.FULL_REPLACE,
    "combined_data(2025-3-1-2026-2-28) by user.csv":            Strategy.FULL_REPLACE,
    "combined_data(2025-3-1-2026-2-28) by channel and user.csv": Strategy.FULL_REPLACE,
}


