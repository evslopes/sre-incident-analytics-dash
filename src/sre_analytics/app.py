"""Interactive Plotly Dash SRE & Tier-3 Sustainment Observability Console."""

from __future__ import annotations

from pathlib import Path
import dash
from dash import Input, Output, dash_table, dcc, html
import dash_bootstrap_components as dbc
import pandas as pd

from sre_analytics.figures import (
    build_daily_anomaly_figure,
    build_mttr_distribution_figure,
    build_pareto_figure,
    build_sla_heatmap_figure,
)
from sre_analytics.kpi_engine import (
    compute_executive_summary,
    compute_pareto_signatures,
    generate_actionable_recommendations,
)
from sre_analytics.schema import SEVERITY_ORDER, validate_and_prepare_incidents
from sre_analytics.synthetic_generator import generate_synthetic_incidents


def load_or_generate_dataset(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Load synthetic CSV if present, otherwise generate deterministic synthetic telemetry in memory."""
    if csv_path is not None and Path(csv_path).exists():
        raw_df = pd.read_csv(csv_path)
    else:
        raw_df = generate_synthetic_incidents(n_incidents=2400, seed=42)
    clean_df, _ = validate_and_prepare_incidents(raw_df)
    return clean_df


def create_dash_app(dataset: pd.DataFrame | None = None) -> dash.Dash:
    """Create and wire the reactive Plotly Dash SRE Observability Console."""
    df_master = dataset if dataset is not None else load_or_generate_dataset()

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.CYBORG],
        title="SRE & Tier-3 Incident Intelligence Console",
    )

    services = sorted(df_master["service"].unique().tolist())
    tiers = sorted(df_master["support_tier"].unique().tolist())
    min_date = df_master["opened_date"].min().date()
    max_date = df_master["opened_date"].max().date()

    card_style = {
        "backgroundColor": "#111c33",
        "border": "1px solid #1e293b",
        "borderRadius": "12px",
        "padding": "16px",
    }

    app.layout = dbc.Container(
        fluid=True,
        style={"backgroundColor": "#0b1120", "minHeight": "100vh", "padding": "24px 28px"},
        children=[
            dbc.Row(
                dbc.Col(
                    [
                        html.Span(
                            "100% SYNTHETIC TELEMETRY · ZERO NDA / ZERO PII · SRE & L3 RCA",
                            style={
                                "color": "#38bdf8",
                                "fontSize": "0.76rem",
                                "fontWeight": "700",
                                "letterSpacing": "0.08em",
                            },
                        ),
                        html.H2(
                            "SRE & Tier-3 Sustainment Incident Intelligence Console",
                            style={"color": "#f8fafc", "marginTop": "4px", "marginBottom": "4px"},
                        ),
                        html.P(
                            "Interactive Pareto 80/20 root-cause analysis, contractual SLA heatmaps, "
                            "log-normal MTTR percentiles, and MAD anomaly detection.",
                            style={"color": "#94a3b8", "marginBottom": "18px"},
                        ),
                    ]
                )
            ),
            # Filter bar
            dbc.Row(
                style={**card_style, "marginBottom": "18px", "marginLeft": "0", "marginRight": "0"},
                children=[
                    dbc.Col(
                        [
                            html.Label("Bounded-Context Services", style={"color": "#cbd5e1", "fontSize": "0.82rem"}),
                            dcc.Dropdown(
                                id="filter-services",
                                options=[{"label": s, "value": s} for s in services],
                                value=services,
                                multi=True,
                                style={"color": "#0f172a"},
                            ),
                        ],
                        md=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("Severities", style={"color": "#cbd5e1", "fontSize": "0.82rem"}),
                            dcc.Dropdown(
                                id="filter-severities",
                                options=[{"label": s, "value": s} for s in SEVERITY_ORDER],
                                value=SEVERITY_ORDER,
                                multi=True,
                                style={"color": "#0f172a"},
                            ),
                        ],
                        md=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Support Tier", style={"color": "#cbd5e1", "fontSize": "0.82rem"}),
                            dcc.Dropdown(
                                id="filter-tiers",
                                options=[{"label": t, "value": t} for t in tiers],
                                value=tiers,
                                multi=True,
                                style={"color": "#0f172a"},
                            ),
                        ],
                        md=2,
                    ),
                    dbc.Col(
                        [
                            html.Label("GMUD Scope", style={"color": "#cbd5e1", "fontSize": "0.82rem"}),
                            dcc.RadioItems(
                                id="filter-gmud",
                                options=[
                                    {"label": " All", "value": "ALL"},
                                    {"label": " GMUD Only", "value": "GMUD"},
                                    {"label": " Non-GMUD", "value": "NON_GMUD"},
                                ],
                                value="ALL",
                                inline=True,
                                inputStyle={"marginRight": "5px", "marginLeft": "10px"},
                                style={"color": "#e2e8f0", "marginTop": "8px", "fontSize": "0.86rem"},
                            ),
                        ],
                        md=3,
                    ),
                    dbc.Col(
                        [
                            html.Label(
                                f"Observation Window ({min_date} → {max_date})",
                                style={"color": "#cbd5e1", "fontSize": "0.82rem", "marginTop": "10px"},
                            ),
                            dcc.DatePickerRange(
                                id="filter-dates",
                                min_date_allowed=min_date,
                                max_date_allowed=max_date,
                                start_date=min_date,
                                end_date=max_date,
                            ),
                        ],
                        md=12,
                    ),
                ],
            ),
            # KPI strip
            html.Div(id="kpi-strip", style={"marginBottom": "18px"}),
            # Charts 2x2
            dbc.Row(
                [
                    dbc.Col(html.Div(dcc.Graph(id="chart-pareto"), style=card_style), lg=6, className="mb-3"),
                    dbc.Col(html.Div(dcc.Graph(id="chart-anomaly"), style=card_style), lg=6, className="mb-3"),
                ]
            ),
            dbc.Row(
                [
                    dbc.Col(html.Div(dcc.Graph(id="chart-sla"), style=card_style), lg=6, className="mb-3"),
                    dbc.Col(html.Div(dcc.Graph(id="chart-mttr"), style=card_style), lg=6, className="mb-3"),
                ]
            ),
            # Recommendations + Top Recurrence Table
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Automated L3 RCA & DMAIC Priorities", style={"color": "#f8fafc"}),
                                html.Div(id="recommendations-panel"),
                            ],
                            style=card_style,
                        ),
                        lg=5,
                        className="mb-3",
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Top Chronic Signatures (Pareto Drill-Down)", style={"color": "#f8fafc"}),
                                html.Div(id="pareto-table-container"),
                            ],
                            style=card_style,
                        ),
                        lg=7,
                        className="mb-3",
                    ),
                ]
            ),
        ],
    )

    @app.callback(
        Output("kpi-strip", "children"),
        Output("chart-pareto", "figure"),
        Output("chart-anomaly", "figure"),
        Output("chart-sla", "figure"),
        Output("chart-mttr", "figure"),
        Output("recommendations-panel", "children"),
        Output("pareto-table-container", "children"),
        Input("filter-services", "value"),
        Input("filter-severities", "value"),
        Input("filter-tiers", "value"),
        Input("filter-gmud", "value"),
        Input("filter-dates", "start_date"),
        Input("filter-dates", "end_date"),
    )
    def update_console(
        selected_services: list[str] | None,
        selected_severities: list[str] | None,
        selected_tiers: list[str] | None,
        gmud_mode: str,
        start_date: str | None,
        end_date: str | None,
    ):
        filtered = df_master.copy()
        if selected_services:
            filtered = filtered[filtered["service"].isin(selected_services)]
        else:
            filtered = filtered.iloc[0:0]

        if selected_severities:
            filtered = filtered[filtered["severity"].isin(selected_severities)]
        else:
            filtered = filtered.iloc[0:0]

        if selected_tiers:
            filtered = filtered[filtered["support_tier"].isin(selected_tiers)]
        else:
            filtered = filtered.iloc[0:0]

        if gmud_mode == "GMUD":
            filtered = filtered[filtered["gmud_correlated"]]
        elif gmud_mode == "NON_GMUD":
            filtered = filtered[~filtered["gmud_correlated"]]

        if start_date:
            filtered = filtered[filtered["opened_date"] >= pd.Timestamp(start_date, tz="UTC")]
        if end_date:
            filtered = filtered[filtered["opened_date"] <= pd.Timestamp(end_date, tz="UTC")]

        summary = compute_executive_summary(filtered)

        kpis = [
            ("Incidents", f"{summary.total_incidents:,}", f"Backlog: {summary.open_backlog}"),
            ("SLA Compliance", f"{summary.sla_compliance_pct:.1f}%", f"SEV-1/2: {summary.sev1_sev2_share_pct:.1f}%"),
            ("Median MTTA", f"{summary.mtta_p50_minutes:.1f}m", "Time to Acknowledge"),
            ("MTTR P50 / P90", f"{summary.mttr_p50_hours:.2f}h / {summary.mttr_p90_hours:.1f}h", f"P95: {summary.mttr_p95_hours:.1f}h"),
            ("Reopen Rate", f"{summary.reopen_rate_pct:.1f}%", f"GMUD Share: {summary.gmud_correlated_pct:.1f}%"),
            ("Pareto Vital Few", f"{summary.pareto_vital_few_count} / {summary.pareto_total_signatures}", f"Spike Days: {summary.anomaly_days_detected}"),
        ]

        kpi_cols = dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.Div(title, style={"color": "#94a3b8", "fontSize": "0.78rem"}),
                            html.Div(val, style={"color": "#f8fafc", "fontSize": "1.35rem", "fontWeight": "700"}),
                            html.Div(sub, style={"color": "#38bdf8", "fontSize": "0.75rem"}),
                        ],
                        style=card_style,
                    ),
                    md=2,
                    sm=6,
                    className="mb-2",
                )
                for title, val, sub in kpis
            ]
        )

        recs = generate_actionable_recommendations(filtered)
        rec_items = [
            html.Div(
                [
                    html.Span(
                        r["priority"],
                        style={"color": "#38bdf8", "fontSize": "0.75rem", "fontWeight": "700"},
                    ),
                    html.H6(r["title"], style={"color": "#f8fafc", "marginTop": "4px"}),
                    html.P(r["evidence"], style={"color": "#cbd5e1", "fontSize": "0.84rem", "marginBottom": "4px"}),
                    html.P(r["action"], style={"color": "#94a3b8", "fontSize": "0.82rem", "marginBottom": "0"}),
                ],
                style={
                    "borderBottom": "1px solid #1e293b",
                    "paddingBottom": "10px",
                    "marginBottom": "10px",
                },
            )
            for r in recs
        ] or [html.P("No incidents match the selected filters.", style={"color": "#94a3b8"})]

        pareto_tbl = compute_pareto_signatures(filtered).head(10).copy()
        if not pareto_tbl.empty:
            pareto_tbl["share_pct"] = pareto_tbl["share_pct"].round(1)
            pareto_tbl["cumulative_pct"] = pareto_tbl["cumulative_pct"].round(1)
            pareto_tbl["sla_breach_pct"] = pareto_tbl["sla_breach_pct"].round(1)
            pareto_tbl["mttr_p50_hours"] = pareto_tbl["mttr_p50_hours"].round(2)

        table = dash_table.DataTable(
            columns=[
                {"name": "Service", "id": "service"},
                {"name": "Root Cause", "id": "root_cause_category"},
                {"name": "Count", "id": "incidents"},
                {"name": "Share %", "id": "share_pct"},
                {"name": "Cum %", "id": "cumulative_pct"},
                {"name": "SLA Breach %", "id": "sla_breach_pct"},
                {"name": "MTTR P50 (h)", "id": "mttr_p50_hours"},
            ],
            data=pareto_tbl.to_dict("records"),
            style_table={"overflowX": "auto"},
            style_header={
                "backgroundColor": "#0f172a",
                "color": "#38bdf8",
                "fontWeight": "700",
                "border": "1px solid #1e293b",
                "fontSize": "0.8rem",
            },
            style_cell={
                "backgroundColor": "#111c33",
                "color": "#e2e8f0",
                "border": "1px solid #1e293b",
                "fontSize": "0.82rem",
                "padding": "8px",
                "textAlign": "left",
            },
            page_size=10,
        )

        return (
            kpi_cols,
            build_pareto_figure(filtered),
            build_daily_anomaly_figure(filtered),
            build_sla_heatmap_figure(filtered),
            build_mttr_distribution_figure(filtered),
            rec_items,
            table,
        )

    return app


app_instance = create_dash_app()
server = app_instance.server

if __name__ == "__main__":
    app_instance.run(host="0.0.0.0", port=8050, debug=False)
