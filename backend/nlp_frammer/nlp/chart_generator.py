# nlp/chart_generator.py
#
# Automatically generates an appropriate EDA chart from NLP query results.
# Called after DuckDB execution — inspects data shape and routes to the
# right Plotly chart type. Saves PNG and returns the path.
#
# FIX (CRITICAL): CHART_DIR is now resolved lazily at call time via
# _get_chart_dir(), not frozen at module load as a hardcoded "/tmp" path.
#
# OLD (broken):
#   CHART_DIR = "/tmp/frammer_charts"   ← /tmp does not exist on Windows
#   os.makedirs(CHART_DIR, ...)         ← crashes on Windows at import
#
# NEW (fixed):
#   _get_chart_dir() reads FRAMMER_CHART_DIR env var at call time.
#   Falls back to tempfile.gettempdir() which is cross-platform.
#   chat.py sets FRAMMER_CHART_DIR=backend/data/charts/ before importing
#   the NLP layer, so that value is always picked up correctly.

import os
import uuid
import logging
import tempfile
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

FRAMMER_COLORS = px.colors.qualitative.Bold

PLOTLY_LAYOUT = dict(
    font_family="Inter, Arial, sans-serif",
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font_color="#e0e0e0",
    title_font_size=16,
    title_x=0.05,
    legend=dict(bgcolor="rgba(0,0,0,0)", font_color="#e0e0e0"),
    margin=dict(l=60, r=40, t=70, b=60),
)


def _get_chart_dir() -> str:
    """
    Resolve chart output directory at call time (not import time).

    Priority:
      1. FRAMMER_CHART_DIR env var  — set by chat.py to backend/data/charts/
      2. Cross-platform temp dir    — tempfile.gettempdir() / frammer_charts
         (works on Windows, Linux, macOS)
    """
    env_dir = os.environ.get("FRAMMER_CHART_DIR", "").strip()
    if env_dir:
        chart_dir = env_dir
    else:
        chart_dir = os.path.join(tempfile.gettempdir(), "frammer_charts")
    os.makedirs(chart_dir, exist_ok=True)
    return chart_dir


def _save(fig, chart_id: str) -> str:
    chart_dir = _get_chart_dir()
    path = os.path.join(chart_dir, f"{chart_id}.png")
    fig.write_image(path, width=900, height=480, scale=2)
    return path


# ─────────────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────────────

def _line_chart(df: pd.DataFrame, cat_col: str,
                num_cols: list[str], title: str, chart_id: str) -> str:
    fig = go.Figure()
    for i, col in enumerate(num_cols):
        fig.add_trace(go.Scatter(
            x=df[cat_col], y=df[col],
            mode="lines+markers",
            name=col,
            line=dict(color=FRAMMER_COLORS[i % len(FRAMMER_COLORS)], width=2),
            marker=dict(size=6),
        ))
    fig.update_layout(title=title, xaxis_title=cat_col,
                      yaxis_title="Count", **PLOTLY_LAYOUT)
    fig.update_xaxes(tickangle=-45, gridcolor="#2a2a2a")
    fig.update_yaxes(gridcolor="#2a2a2a")
    return _save(fig, chart_id)


def _bar_chart(df: pd.DataFrame, cat_col: str,
               num_cols: list[str], title: str, chart_id: str,
               orientation: str = "h") -> str:
    """Handles both single-metric and grouped bar."""
    if len(num_cols) == 1:
        num_col = num_cols[0]
        df = df.sort_values(num_col, ascending=(orientation == "h"))
        if orientation == "h":
            fig = px.bar(df, x=num_col, y=cat_col,
                         orientation="h", title=title,
                         color=num_col,
                         color_continuous_scale="Blues",
                         text=num_col)
            fig.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig.update_layout(**PLOTLY_LAYOUT)
            fig.update_xaxes(gridcolor="#2a2a2a")
            fig.update_yaxes(gridcolor="#2a2a2a")
        else:
            fig = px.bar(df, x=cat_col, y=num_col,
                         title=title, color=cat_col,
                         color_discrete_sequence=FRAMMER_COLORS,
                         text=num_col)
            fig.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig.update_layout(**PLOTLY_LAYOUT, showlegend=False)
            fig.update_xaxes(gridcolor="#2a2a2a", tickangle=-30)
            fig.update_yaxes(gridcolor="#2a2a2a")
    else:
        # Grouped bar
        fig = go.Figure()
        for i, col in enumerate(num_cols):
            fig.add_trace(go.Bar(
                x=df[cat_col], y=df[col],
                name=col,
                marker_color=FRAMMER_COLORS[i % len(FRAMMER_COLORS)],
            ))
        fig.update_layout(
            barmode="group", title=title,
            xaxis_title=cat_col, **PLOTLY_LAYOUT
        )
        fig.update_xaxes(gridcolor="#2a2a2a", tickangle=-30)
        fig.update_yaxes(gridcolor="#2a2a2a")
    return _save(fig, chart_id)


def _heatmap(df: pd.DataFrame, row_col: str, col_col: str,
             val_col: str, title: str, chart_id: str) -> str:
    pivot = df.pivot_table(index=row_col, columns=col_col,
                           values=val_col, aggfunc="sum", fill_value=0)
    fig = px.imshow(
        pivot, title=title, text_auto=True,
        color_continuous_scale="Blues",
        aspect="auto",
    )
    fig.update_layout(**PLOTLY_LAYOUT)
    return _save(fig, chart_id)


def _dual_axis_chart(df: pd.DataFrame, x_col: str,
                     bar_col: str, line_col: str,
                     title: str, chart_id: str) -> str:
    """Bar for volume, line for rate — classic EDA combo."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=df[x_col], y=df[bar_col], name=bar_col,
               marker_color=FRAMMER_COLORS[0], opacity=0.75),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df[x_col], y=df[line_col], name=line_col,
                   mode="lines+markers",
                   line=dict(color=FRAMMER_COLORS[2], width=2),
                   marker=dict(size=7)),
        secondary_y=True,
    )
    fig.update_layout(title=title, **PLOTLY_LAYOUT)
    fig.update_xaxes(tickangle=-45, gridcolor="#2a2a2a")
    fig.update_yaxes(gridcolor="#2a2a2a", secondary_y=False)
    fig.update_yaxes(gridcolor="#2a2a2a", secondary_y=True,
                     ticksuffix="%")
    return _save(fig, chart_id)


# ─────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────

# Columns that are clearly rates/percentages — use secondary axis
_RATE_COLS = {"publish_rate_pct", "upload_to_publish_rate_pct",
              "compression_ratio", "creation_multiplier"}

# Columns to never treat as chart values
_SKIP_COLS = {"Month", "Channel", "User", "Input Type", "Output Type",
              "Language", "platform", "uploaded_by", "input_type",
              "published_platform", "video_id", "headline",
              "_raw", "ingested_at"}


def _is_skip(col: str) -> bool:
    return col in _SKIP_COLS or col.endswith("_raw")


def _is_time(df: pd.DataFrame) -> tuple[bool, str]:
    for col in df.columns:
        if col.lower() in ("month", "date", "week"):
            return True, col
    return False, ""


def generate_chart(
    question: str,
    data: list[dict],
    sql: str,
) -> tuple[str, str] | None:
    """
    Main entry point.
    Returns (chart_path, chart_type) or None if no chart is appropriate.
    """
    if not data or len(data) == 0:
        return None

    df = pd.DataFrame(data)
    chart_id = str(uuid.uuid4())[:8]
    title = question[:80]

    cat_cols = [c for c in df.columns if _is_skip(c) or df[c].dtype == object]
    num_cols = [c for c in df.columns if c not in cat_cols and not _is_skip(c)]

    # THE GOLDILOCKS FIX: We must have at least 2 rows to draw a meaningful chart.
    # This prevents silly 1-bar charts for specific people/channels, 
    # but allows charts for "all users", "monthly data", or comparisons.
    if len(df) < 2:
        return None

    is_time, time_col = _is_time(df)

    # ── Rule 1: Time series (Month column present) ─────────────────
    if is_time:
        rate_cols   = [c for c in num_cols if c in _RATE_COLS]
        volume_cols = [c for c in num_cols if c not in _RATE_COLS]

        if volume_cols and rate_cols:
            path = _dual_axis_chart(
                df, time_col,
                bar_col=volume_cols[0],
                line_col=rate_cols[0],
                title=title, chart_id=chart_id,
            )
            return path, "dual_axis"
        else:
            path = _line_chart(df, time_col, num_cols,
                               title=title, chart_id=chart_id)
            return path, "line"

    # ── Rule 2: Two categoricals + 1 numeric → heatmap ────────────
    if len(cat_cols) >= 2 and len(num_cols) == 1:
        if (df[cat_cols[0]].nunique() <= 20 and
                df[cat_cols[1]].nunique() <= 10):
            path = _heatmap(df, cat_cols[0], cat_cols[1],
                            num_cols[0], title=title, chart_id=chart_id)
            return path, "heatmap"

    # ── Rule 3: 1 categorical + metrics ───────────────────────────
    if len(cat_cols) >= 1:
        cat = cat_cols[0]
        rate_cols   = [c for c in num_cols if c in _RATE_COLS]
        volume_cols = [c for c in num_cols if c not in _RATE_COLS]

        # Dual Axis (Volume + Rate)
        if len(volume_cols) >= 1 and len(rate_cols) == 1:
            df_sorted = df.sort_values(volume_cols[0], ascending=False)
            if len(df_sorted) > 15:
                df_sorted = df_sorted.head(15)
            path = _dual_axis_chart(
                df_sorted, cat,
                bar_col=volume_cols[0],
                line_col=rate_cols[0],
                title=title, chart_id=chart_id,
            )
            return path, "dual_axis"

        # Grouped Bar Chart (Multiple Volumes)
        if len(volume_cols) >= 2:
            df_sorted = df.sort_values(volume_cols[0], ascending=False)
            orient = "v" if df[cat].nunique() <= 8 else "h"
            path = _bar_chart(df_sorted, cat, volume_cols[:4],
                              title=title, chart_id=chart_id,
                              orientation=orient)
            return path, "bar"

        # Standard Bar Chart (Single Metric)
        if len(num_cols) == 1:
            df_sorted = df.sort_values(num_cols[0], ascending=False)
            if len(df_sorted) > 20:
                df_sorted = df_sorted.head(20)
            orient = "h" if df[cat].nunique() > 5 else "v"
            path = _bar_chart(df_sorted, cat, num_cols,
                              title=title, chart_id=chart_id,
                              orientation=orient)
            return path, "bar"

    return None