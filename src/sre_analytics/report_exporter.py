"""Standalone Executive Data-Storytelling HTML Report Exporter."""

from __future__ import annotations

import html
from pathlib import Path
import pandas as pd
import plotly.io as pio

from sre_analytics.figures import (
    build_daily_anomaly_figure,
    build_mttr_distribution_figure,
    build_pareto_figure,
    build_sla_heatmap_figure,
)
from sre_analytics.kpi_engine import (
    compute_executive_summary,
    generate_actionable_recommendations,
)
from sre_analytics.schema import DataQualityAudit


def export_executive_html_report(
    df: pd.DataFrame,
    audit: DataQualityAudit,
    output_path: str | Path,
) -> Path:
    """Render a self-contained executive HTML report with KPIs, Plotly visuals, and RCA narrative."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    summary = compute_executive_summary(df)
    recs = generate_actionable_recommendations(df)

    pareto_html = pio.to_html(
        build_pareto_figure(df), full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False}
    )
    anomaly_html = pio.to_html(
        build_daily_anomaly_figure(df), full_html=False, include_plotlyjs=False, config={"displayModeBar": False}
    )
    sla_html = pio.to_html(
        build_sla_heatmap_figure(df), full_html=False, include_plotlyjs=False, config={"displayModeBar": False}
    )
    mttr_html = pio.to_html(
        build_mttr_distribution_figure(df), full_html=False, include_plotlyjs=False, config={"displayModeBar": False}
    )

    rec_cards = "".join(
        f"""
        <article class="rec-card">
            <span class="rec-badge">{html.escape(r['priority'])}</span>
            <h3>{html.escape(r['title'])}</h3>
            <p><strong>Telemetry Evidence:</strong> {html.escape(r['evidence'])}</p>
            <p><strong>Recommended Engineering Action:</strong> {html.escape(r['action'])}</p>
        </article>
        """
        for r in recs
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SRE &amp; Tier-3 Sustainment Executive Intelligence Report</title>
  <style>
    :root {{
      --bg: #0b1120;
      --card: #111c33;
      --border: #1e293b;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 32px 24px 64px;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.55;
    }}
    .container {{ max-width: 1320px; margin: 0 auto; }}
    header {{ margin-bottom: 28px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
    .kicker {{ color: var(--accent); font-size: 0.78rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; }}
    h1 {{ margin: 6px 0 8px; font-size: 1.9rem; }}
    .subtitle {{ margin: 0; color: var(--muted); max-width: 900px; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
      margin: 24px 0;
    }}
    .kpi-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
    }}
    .kpi-val {{ display: block; font-size: 1.6rem; font-weight: 700; color: #f8fafc; }}
    .kpi-lbl {{ font-size: 0.82rem; color: var(--muted); }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(540px, 1fr));
      gap: 18px;
      margin-bottom: 28px;
    }}
    .chart-box {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      overflow: hidden;
    }}
    .rec-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }}
    .rec-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}
    .rec-badge {{
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--accent);
      background: rgba(56, 189, 248, 0.12);
      padding: 3px 10px;
      border-radius: 999px;
      margin-bottom: 8px;
    }}
    .rec-card h3 {{ margin: 4px 0 10px; font-size: 1.05rem; }}
    .rec-card p {{ margin: 6px 0; font-size: 0.9rem; color: #cbd5e1; }}
    .audit-footer {{
      margin-top: 32px;
      padding: 14px 18px;
      border-radius: 10px;
      background: rgba(30, 41, 59, 0.55);
      border: 1px solid var(--border);
      font-size: 0.84rem;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <span class="kicker">100% Synthetic Telemetry &middot; SRE &amp; Tier-3 Sustainment</span>
      <h1>Operational Reliability, Pareto RCA &amp; SLA Executive Report</h1>
      <p class="subtitle">Automated root-cause concentration analysis, contractual SLA compliance, log-normal MTTR percentiles, and robust MAD anomaly detection across distributed B2B services.</p>
    </header>

    <section class="kpi-grid" aria-label="Key Performance Indicators">
      <div class="kpi-card">
        <span class="kpi-val">{summary.total_incidents:,}</span>
        <span class="kpi-lbl">Validated Incidents ({summary.open_backlog} Active Backlog)</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-val">{summary.sla_compliance_pct:.1f}%</span>
        <span class="kpi-lbl">Contractual SLA Compliance</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-val">{summary.mtta_p50_minutes:.1f} min</span>
        <span class="kpi-lbl">Median MTTA (P50 Ack)</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-val">{summary.mttr_p50_hours:.2f}h / {summary.mttr_p90_hours:.1f}h</span>
        <span class="kpi-lbl">MTTR P50 / P90 (Resolved)</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-val">{summary.reopen_rate_pct:.1f}%</span>
        <span class="kpi-lbl">Ticket Reopen Rate (GMUD: {summary.gmud_correlated_pct:.1f}%)</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-val">{summary.pareto_vital_few_count} / {summary.pareto_total_signatures}</span>
        <span class="kpi-lbl">Vital-Few Signatures (80% Volume) &middot; {summary.anomaly_days_detected} Spike Day(s)</span>
      </div>
    </section>

    <section class="chart-grid">
      <div class="chart-box">{pareto_html}</div>
      <div class="chart-box">{anomaly_html}</div>
      <div class="chart-box">{sla_html}</div>
      <div class="chart-box">{mttr_html}</div>
    </section>

    <section>
      <span class="kicker">Automated Data Storytelling &amp; DMAIC Prioritization</span>
      <h2>Actionable Tier-3 Engineering &amp; SRE Recommendations</h2>
      <div class="rec-grid">{rec_cards}</div>
    </section>

    <footer class="audit-footer">
      <strong>Data Hygiene &amp; Schema Audit:</strong> Raw rows={audit.raw_rows:,} &middot;
      Valid rows={audit.valid_rows:,} &middot; Quarantined malformed rows={audit.dropped_malformed_rows} &middot;
      Active unresolved backlog preserved={audit.unresolved_backlog_rows} &middot;
      Pending RCA labeled={audit.missing_root_cause_imputed} &middot;
      Missing MTTA median-imputed={audit.missing_ack_imputed}.
    </footer>
  </div>
</body>
</html>
"""
    out.write_text(doc, encoding="utf-8")
    return out
