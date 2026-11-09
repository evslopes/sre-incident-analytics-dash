"""Reusable dark-themed Plotly figure builders for Dash and standalone HTML reports."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from sre_analytics.kpi_engine import (
    compute_pareto_signatures,
    compute_sla_matrix,
    detect_daily_volume_anomalies,
)
from sre_analytics.schema import SEVERITY_ORDER

PALETTE = {
    "bg": "#0f172a",
    "panel": "#111c33",
    "grid": "#1e293b",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "cyan": "#38bdf8",
    "amber": "#f59e0b",
    "rose": "#f43f5e",
    "emerald": "#10b981",
    "violet": "#8b5cf6",
}


def _apply_dark_theme(fig: go.Figure, title: str, height: int = 390) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=PALETTE["text"])),
        paper_bgcolor=PALETTE["panel"],
        plot_bgcolor=PALETTE["panel"],
        font=dict(family="Inter, Segoe UI, sans-serif", color=PALETTE["text"], size=12),
        height=height,
        margin=dict(l=48, r=42, t=54, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
    )
    fig.update_xaxes(gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"])
    fig.update_yaxes(gridcolor=PALETTE["grid"], zerolinecolor=PALETTE["grid"])
    return fig


def build_pareto_figure(df: pd.DataFrame, top_n: int = 12) -> go.Figure:
    """Build dual-axis Pareto 80/20 chart of recurring (service :: root_cause) signatures."""
    pareto = compute_pareto_signatures(df).head(top_n)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if pareto.empty:
        return _apply_dark_theme(fig, "Pareto 80/20 — Top Chronic Failure Signatures")

    bar_colors = [
        PALETTE["cyan"] if vital else PALETTE["muted"] for vital in pareto["is_vital_few"]
    ]
    short_labels = [
        sig if len(sig) <= 38 else sig[:35] + "..."
        for sig in pareto["recurrence_signature"]
    ]

    fig.add_trace(
        go.Bar(
            x=short_labels,
            y=pareto["incidents"],
            name="Incidents",
            marker_color=bar_colors,
            customdata=pareto[["recurrence_signature", "sla_breach_pct", "mttr_p50_hours"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Incidents: %{y}<br>"
                "SLA Breach: %{customdata[1]:.1f}%<br>"
                "Median MTTR: %{customdata[2]:.2f}h<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=short_labels,
            y=pareto["cumulative_pct"],
            name="Cumulative %",
            mode="lines+markers",
            line=dict(color=PALETTE["amber"], width=2.5),
            marker=dict(size=7),
            hovertemplate="Cumulative Share: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.add_hline(
        y=80.0,
        line_dash="dash",
        line_color=PALETTE["rose"],
        annotation_text="80% Pareto Cutoff",
        annotation_position="bottom right",
        secondary_y=True,
    )

    fig.update_xaxes(tickangle=-28)
    fig.update_yaxes(title_text="Incident Count", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative %", range=[0, 105], secondary_y=True)
    return _apply_dark_theme(fig, "Pareto 80/20 — Top Chronic L2/L3 Failure Signatures", height=420)


def build_daily_anomaly_figure(df: pd.DataFrame) -> go.Figure:
    """Build daily incident timeline highlighting MAD statistical anomalies and GMUD volume."""
    daily = detect_daily_volume_anomalies(df)
    fig = go.Figure()

    if daily.empty:
        return _apply_dark_theme(fig, "Daily Incident Volume & MAD Anomaly Detection")

    fig.add_trace(
        go.Scatter(
            x=daily["opened_date"],
            y=daily["incidents"],
            mode="lines",
            name="Daily Total",
            line=dict(color=PALETTE["cyan"], width=2),
            fill="tozeroy",
            fillcolor="rgba(56, 189, 248, 0.10)",
        )
    )

    fig.add_trace(
        go.Bar(
            x=daily["opened_date"],
            y=daily["gmud_incidents"],
            name="GMUD-Correlated",
            marker_color=PALETTE["violet"],
            opacity=0.65,
        )
    )

    anoms = daily[daily["is_anomaly"]]
    if not anoms.empty:
        fig.add_trace(
            go.Scatter(
                x=anoms["opened_date"],
                y=anoms["incidents"],
                mode="markers",
                name="MAD Anomaly (Z > 3.5)",
                marker=dict(color=PALETTE["rose"], size=11, symbol="diamond", line=dict(width=1.5, color="#fff")),
                customdata=anoms[["mad_z_score", "gmud_incidents"]],
                hovertemplate=(
                    "<b>Anomaly Spike</b>: %{x|%Y-%m-%d}<br>"
                    "Incidents: %{y}<br>"
                    "Modified Z-Score: %{customdata[0]}<br>"
                    "GMUD-Correlated: %{customdata[1]}<extra></extra>"
                ),
            )
        )

    fig.update_yaxes(title_text="Incidents / Day")
    return _apply_dark_theme(fig, "Daily Telemetry Volume, GMUD Correlation & MAD Anomalies", height=400)


def build_sla_heatmap_figure(df: pd.DataFrame) -> go.Figure:
    """Build Service x Severity Contractual SLA Compliance (%) heatmap."""
    mat = compute_sla_matrix(df)
    fig = go.Figure()

    if mat.empty:
        return _apply_dark_theme(fig, "Contractual SLA Compliance (%) — Service × Severity")

    fig.add_trace(
        go.Heatmap(
            z=mat.values,
            x=list(mat.columns),
            y=list(mat.index),
            zmin=65,
            zmax=100,
            colorscale=[
                [0.0, "#f43f5e"],
                [0.55, "#f59e0b"],
                [0.85, "#10b981"],
                [1.0, "#059669"],
            ],
            text=[[f"{v:.1f}%" if pd.notna(v) else "N/A" for v in row] for row in mat.values],
            texttemplate="%{text}",
            colorbar=dict(title="SLA %"),
            hovertemplate="Service: <b>%{y}</b><br>Severity: %{x}<br>SLA Compliance: %{z:.1f}%<extra></extra>",
        )
    )
    return _apply_dark_theme(fig, "Contractual SLA Compliance (%) — Service × Severity", height=390)


def build_mttr_distribution_figure(df: pd.DataFrame) -> go.Figure:
    """Build box/percentile distribution of resolution time (MTTR hours) on log scale."""
    fig = go.Figure()
    resolved = df[df["is_resolved"] & df["mttr_hours"].notna()]
    if resolved.empty:
        return _apply_dark_theme(fig, "MTTR Distribution by Severity (Log Hours)")

    colors = {
        "SEV-1": PALETTE["rose"],
        "SEV-2": PALETTE["amber"],
        "SEV-3": PALETTE["cyan"],
        "SEV-4": PALETTE["emerald"],
    }
    for sev in SEVERITY_ORDER:
        sub = resolved[resolved["severity"] == sev]
        if sub.empty:
            continue
        fig.add_trace(
            go.Box(
                y=sub["mttr_hours"],
                name=sev,
                marker_color=colors.get(sev, PALETTE["cyan"]),
                boxmean=True,
                hovertemplate=f"<b>{sev}</b><br>MTTR: %{{y:.2f}}h<extra></extra>",
            )
        )

    fig.update_yaxes(title_text="MTTR (Hours — Log Scale)", type="log")
    return _apply_dark_theme(fig, "Right-Skewed MTTR Distribution & Tail Outliers by Severity", height=390)
