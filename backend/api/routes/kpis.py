"""
kpis.py — Central KPI router

Endpoint:
GET /api/kpis
"""

import os
import sys
import duckdb
from fastapi import APIRouter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from config import DATABASE_PATH

router = APIRouter(prefix="/api", tags=["kpis"])


# ------------------------------------------------
# Helper
# ------------------------------------------------

def query(sql):

    con = duckdb.connect(DATABASE_PATH, read_only=True)

    try:
        return con.execute(sql).fetchone()

    finally:
        con.close()


# ------------------------------------------------
# Main KPI Endpoint
# ------------------------------------------------

@router.get("/kpis")
def get_all_kpis():

    con = duckdb.connect(DATABASE_PATH, read_only=True)

    try:

        # ----------------------------------
        # Core metrics
        # ----------------------------------

        total_videos = con.execute(
            "SELECT COUNT(*) FROM fact_video"
        ).fetchone()[0]

        total_uploaded = con.execute(
            "SELECT SUM(uploaded_count) FROM fact_video"
        ).fetchone()[0]

        total_created = con.execute(
            "SELECT SUM(created_count) FROM fact_video"
        ).fetchone()[0]

        total_published = con.execute(
            "SELECT SUM(published_count) FROM fact_video"
        ).fetchone()[0]


        # ----------------------------------
        # Publish rate
        # ----------------------------------

        publish_rate = con.execute("""
            SELECT
            ROUND(
                SUM(published_count)::FLOAT /
                NULLIF(SUM(created_count),0) * 100
            ,2)
            FROM fact_video
        """).fetchone()[0]


        # ----------------------------------
        # Multiplication ratio
        # ----------------------------------

        multiplication_ratio = con.execute("""
            SELECT
            ROUND(
                SUM(created_count)::FLOAT /
                NULLIF(SUM(uploaded_count),0)
            ,2)
            FROM fact_video
        """).fetchone()[0]


        # ----------------------------------
        # Total durations
        # ----------------------------------

        durations = con.execute("""
            SELECT
                ROUND(SUM(uploaded_mins),2),
                ROUND(SUM(created_mins),2),
                ROUND(SUM(published_mins),2)
            FROM fact_video
        """).fetchone()


        # ----------------------------------
        # Top creators
        # ----------------------------------

        top_creators = con.execute("""
            SELECT
                u.user_name,
                SUM(f.uploaded_count) AS uploads
            FROM fact_video f
            JOIN dim_user u
            ON f.user_id = u.user_id
            GROUP BY u.user_name
            ORDER BY uploads DESC
            LIMIT 5
        """).fetchdf().to_dict("records")


        # ----------------------------------
        # Top platforms
        # ----------------------------------

        top_platforms = con.execute("""
            SELECT
                p.platform_name,
                SUM(f.published_count) AS published
            FROM fact_video f
            JOIN dim_platform p
            ON f.platform_id = p.platform_id
            GROUP BY p.platform_name
            ORDER BY published DESC
        """).fetchdf().to_dict("records")


        return {

            "core_metrics": {
                "total_videos": total_videos,
                "total_uploaded": total_uploaded,
                "total_created": total_created,
                "total_published": total_published
            },

            "rates": {
                "publish_rate": publish_rate,
                "multiplication_ratio": multiplication_ratio
            },

            "durations": {
                "uploaded_minutes": durations[0],
                "created_minutes": durations[1],
                "published_minutes": durations[2]
            },

            "top_creators": top_creators,

            "top_platforms": top_platforms
        }

    finally:
        con.close()