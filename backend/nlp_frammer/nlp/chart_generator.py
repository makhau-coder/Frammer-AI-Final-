"""
nlp/chart_generator.py

Generates Plotly chart specs from NLP query results.
Returns Plotly JSON (dict) — NOT a file path.

The frontend receives the JSON and renders it with Plotly.js directly,
giving users interactive, hoverable charts without any server file I/O.

Called by engine.py after DuckDB execution.
"""

import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Theme
# ─────────────────────────────────────────────────────────────────────────────

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

_RATE_COLS = {
    "publish_rate", "multiplication_ratio", "rate",
    "publish rate", "conversion", "pct", "percent",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_skip(col: str) -> bool:
    """Columns that should never be treated as numeric axes."""
    skip = {"video_id", "published_url", "source", "headline",
            "url", "id", "published_status"}
    return col.lower() in skip


def _is_time(df: pd.DataFrame):
    """Detect if any column looks like a time/month series."""
    for col in df.columns:
        if col.lower() in ("month", "year", "date", "period", "week"):
            return True, col
    return False, None


def _to_json(fig: go.Figure) -> dict:
    """Convert a Plotly Figure to a JSON-serialisable dict."""
    return fig.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders — all return dict (Plotly JSON)
# ─────────────────────────────────────────────────────────────────────────────

def _line_chart(df, cat_col, num_cols, title) -> dict:
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
    return _to_json(fig)


def _bar_chart(df, cat_col, num_cols, title, orientation="h") -> dict:
    """Single metric or grouped bar chart."""
    if len(num_cols) == 1:
        num_col = num_cols[0]
        df = df.sort_values(num_col, ascending=(orientation == "h"))
        if orientation == "h":
            fig = px.bar(df, x=num_col, y=cat_col, orientation="h", title=title,
                         color=num_col, color_continuous_scale="Blues", text=num_col)
            fig.update_traces(texttemplate="%{text:,}", textposition="outside")
        else:
            fig = px.bar(df, x=cat_col, y=num_col, title=title,
                         color=num_col, color_continuous_scale="Blues", text=num_col)
            fig.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_xaxes(gridcolor="#2a2a2a")
        fig.update_yaxes(gridcolor="#2a2a2a")
    else:
        # Grouped bar
        fig = go.Figure()
        for i, col in enumerate(num_cols):
            if orientation == "h":
                fig.add_trace(go.Bar(
                    y=df[cat_col], x=df[col], name=col,
                    orientation="h",
                    marker_color=FRAMMER_COLORS[i % len(FRAMMER_COLORS)],
                ))
            else:
                fig.add_trace(go.Bar(
                    x=df[cat_col], y=df[col], name=col,
                    marker_color=FRAMMER_COLORS[i % len(FRAMMER_COLORS)],
                ))
        fig.update_layout(
            title=title, barmode="group", **PLOTLY_LAYOUT
        )
        fig.update_xaxes(gridcolor="#2a2a2a", tickangle=-30)
        fig.update_yaxes(gridcolor="#2a2a2a")

    return _to_json(fig)


def _dual_axis_chart(df, cat_col, bar_col, line_col, title) -> dict:
    """Bar (volume) + line (rate) on dual y-axes."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=df[cat_col], y=df[bar_col], name=bar_col,
               marker_color=FRAMMER_COLORS[0]),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df[cat_col], y=df[line_col], name=line_col,
                   mode="lines+markers",
                   line=dict(color=FRAMMER_COLORS[2], width=2),
                   marker=dict(size=7)),
        secondary_y=True,
    )
    fig.update_layout(title=title, **PLOTLY_LAYOUT)
    fig.update_xaxes(tickangle=-45, gridcolor="#2a2a2a")
    fig.update_yaxes(gridcolor="#2a2a2a", secondary_y=False, title_text=bar_col)
    fig.update_yaxes(gridcolor="#2a2a2a", secondary_y=True,  title_text=line_col)
    return _to_json(fig)


def _heatmap(df, cat_col1, cat_col2, val_col, title) -> dict:
    pivot = df.pivot_table(index=cat_col1, columns=cat_col2, values=val_col, fill_value=0)
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="Blues",
        hoverongaps=False,
    ))
    fig.update_layout(title=title, **PLOTLY_LAYOUT)
    return _to_json(fig)


def _pie_chart(df, cat_col, val_col, title) -> dict:
    fig = px.pie(df, names=cat_col, values=val_col, title=title,
                 color_discrete_sequence=FRAMMER_COLORS)
    fig.update_layout(**PLOTLY_LAYOUT)
    return _to_json(fig)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: generate_chart
# Returns (chart_json_dict, chart_type_str) or None if data is unsuitable.
# ─────────────────────────────────────────────────────────────────────────────

def generate_chart(
    question: str,
    data: list[dict],
    sql: str,
) -> tuple[dict, str] | None:
    """
    Inspects the result data shape and generates the most appropriate
    Plotly chart as a JSON-serialisable dict.

    Args:
        question: Original NL question (used for chart title).
        data:     Query result rows as list of dicts.
        sql:      Executed SQL (used for context hints).

    Returns:
        (chart_json_dict, chart_type_str)  or  None
    """
    if not data:
        return None

    df = pd.DataFrame(data)
    if df.empty or len(df.columns) < 2:
        return None

    title = question[:80]

    cat_cols = [c for c in df.columns if _is_skip(c) or df[c].dtype == object]
    num_cols = [c for c in df.columns if c not in cat_cols and not _is_skip(c)]

    # Single row → stat card only, no chart
    if len(df) == 1 and len(num_cols) <= 2:
        return None

    is_time, time_col = _is_time(df)

    # ── Rule 1: Time series ─────────────────────────────────────────────────
    if is_time and num_cols:
        rate_cols   = [c for c in num_cols if c.lower() in _RATE_COLS]
        volume_cols = [c for c in num_cols if c.lower() not in _RATE_COLS]

        if volume_cols and rate_cols:
            chart = _dual_axis_chart(df, time_col,
                                     bar_col=volume_cols[0],
                                     line_col=rate_cols[0],
                                     title=title)
            return chart, "dual_axis"
        else:
            chart = _line_chart(df, time_col, num_cols, title=title)
            return chart, "line"

    # ── Rule 2: Two cats + 1 numeric → heatmap ─────────────────────────────
    if len(cat_cols) >= 2 and len(num_cols) == 1:
        if df[cat_cols[0]].nunique() <= 20 and df[cat_cols[1]].nunique() <= 10:
            chart = _heatmap(df, cat_cols[0], cat_cols[1], num_cols[0], title=title)
            return chart, "heatmap"

    # ── Rule 3: 1 cat column with metrics ──────────────────────────────────
    if len(cat_cols) >= 1:
        cat = cat_cols[0]
        rate_cols   = [c for c in num_cols if c.lower() in _RATE_COLS]
        volume_cols = [c for c in num_cols if c.lower() not in _RATE_COLS]

        # Pie chart for platform/language breakdown with small cardinality
        if df[cat].nunique() <= 7 and len(num_cols) == 1:
            chart = _pie_chart(df, cat, num_cols[0], title=title)
            return chart, "pie"

        # Dual axis: volume + rate
        if volume_cols and len(rate_cols) == 1:
            df_sorted = df.sort_values(volume_cols[0], ascending=False).head(15)
            chart = _dual_axis_chart(df_sorted, cat,
                                     bar_col=volume_cols[0],
                                     line_col=rate_cols[0],
                                     title=title)
            return chart, "dual_axis"

        # Multiple volume cols → grouped bar
        if len(volume_cols) >= 2:
            df_sorted = df.sort_values(volume_cols[0], ascending=False).head(15)
            orient = "v" if df[cat].nunique() <= 8 else "h"
            chart = _bar_chart(df_sorted, cat, volume_cols[:4],
                                title=title, orientation=orient)
            return chart, "bar"

        # Single numeric → horizontal bar
        if len(num_cols) == 1:
            df_sorted = df.sort_values(num_cols[0], ascending=False).head(20)
            orient = "h" if df[cat].nunique() > 5 else "v"
            chart = _bar_chart(df_sorted, cat, num_cols,
                                title=title, orientation=orient)
            return chart, "bar"

    return None
