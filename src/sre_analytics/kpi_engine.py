"""Core SRE & Tier-3 Sustainment KPI, Pareto 80/20, SLA, and MAD Anomaly Engine."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from sre_analytics.schema import SEVERITY_ORDER


@dataclass(frozen=True)
class ExecutiveKpiSummary:
    """High-level operational reliability and L3 sustainment indicators."""

    total_incidents: int
    resolved_incidents: int
    open_backlog: int
    sla_compliance_pct: float
    sev1_sev2_share_pct: float
    mtta_p50_minutes: float
    mttr_p50_hours: float
    mttr_p90_hours: float
    mttr_p95_hours: float
    reopen_rate_pct: float
    gmud_correlated_pct: float
    pareto_vital_few_count: int
    pareto_total_signatures: int
    anomaly_days_detected: int


def compute_pareto_signatures(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Pareto 80/20 cumulative distribution across (service :: root_cause) signatures."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "recurrence_signature",
                "service",
                "root_cause_category",
                "incidents",
                "share_pct",
                "cumulative_pct",
                "sla_breach_pct",
                "mttr_p50_hours",
                "is_vital_few",
            ]
        )

    resolved_only = df[df["root_cause_category"] != "Pending L3 RCA"]
    target = resolved_only if not resolved_only.empty else df

    grouped = (
        target.groupby(["recurrence_signature", "service", "root_cause_category"], as_index=False)
        .agg(
            incidents=("incident_id", "count"),
            sla_breach_pct=("sla_breached", lambda s: float(np.mean(s) * 100.0)),
            mttr_p50_hours=("mttr_hours", lambda s: float(np.nanmedian(s)) if s.notna().any() else 0.0),
        )
        .sort_values("incidents", ascending=False)
        .reset_index(drop=True)
    )

    total = grouped["incidents"].sum()
    grouped["share_pct"] = (grouped["incidents"] / total) * 100.0
    grouped["cumulative_pct"] = grouped["share_pct"].cumsum()
    # Include signatures up to and including the first one crossing 80%
    prev_cum = grouped["cumulative_pct"].shift(1, fill_value=0.0)
    grouped["is_vital_few"] = prev_cum < 80.0
    return grouped


def detect_daily_volume_anomalies(
    df: pd.DataFrame,
    mad_z_threshold: float = 3.5,
) -> pd.DataFrame:
    """Detect daily incident volume spikes using Robust Modified Z-Score (MAD).

    Unlike standard Gaussian Z-scores (mean/std), Median Absolute Deviation (MAD)
    resists masking from extreme post-GMUD incident bursts (`0.6745 * (x - median) / MAD`).
    """
    if df.empty:
        return pd.DataFrame(
            columns=["opened_date", "incidents", "gmud_incidents", "mad_z_score", "is_anomaly"]
        )

    min_day = df["opened_date"].min()
    max_day = df["opened_date"].max()
    full_days = pd.date_range(min_day, max_day, freq="D", tz="UTC")

    daily = (
        df.groupby("opened_date", as_index=False)
        .agg(
            incidents=("incident_id", "count"),
            gmud_incidents=("gmud_correlated", "sum"),
        )
        .set_index("opened_date")
        .reindex(full_days, fill_value=0)
        .rename_axis("opened_date")
        .reset_index()
    )

    counts = daily["incidents"].to_numpy(dtype=float)
    median_val = float(np.median(counts))
    mad = float(np.median(np.abs(counts - median_val)))

    if mad == 0.0:
        # Fallback to IQR scale if >50% of days have identical counts
        iqr = float(np.percentile(counts, 75) - np.percentile(counts, 25))
        scale = iqr / 1.349 if iqr > 0 else 1.0
        z_scores = (counts - median_val) / scale
    else:
        z_scores = 0.6745 * (counts - median_val) / mad

    daily["mad_z_score"] = np.round(z_scores, 2)
    daily["is_anomaly"] = daily["mad_z_score"] > mad_z_threshold
    return daily


def compute_sla_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Compute SLA compliance percentage matrix across Services x Severities."""
    if df.empty:
        return pd.DataFrame()

    piv = df.pivot_table(
        index="service",
        columns="severity",
        values="sla_breached",
        aggfunc=lambda s: round((1.0 - float(np.mean(s))) * 100.0, 1),
    )
    ordered_cols = [c for c in SEVERITY_ORDER if c in piv.columns]
    return piv.reindex(columns=ordered_cols)


def compute_executive_summary(df: pd.DataFrame) -> ExecutiveKpiSummary:
    """Calculate consolidated SRE & Tier-3 Sustainment KPIs."""
    if df.empty:
        return ExecutiveKpiSummary(
            total_incidents=0,
            resolved_incidents=0,
            open_backlog=0,
            sla_compliance_pct=100.0,
            sev1_sev2_share_pct=0.0,
            mtta_p50_minutes=0.0,
            mttr_p50_hours=0.0,
            mttr_p90_hours=0.0,
            mttr_p95_hours=0.0,
            reopen_rate_pct=0.0,
            gmud_correlated_pct=0.0,
            pareto_vital_few_count=0,
            pareto_total_signatures=0,
            anomaly_days_detected=0,
        )

    total = len(df)
    resolved_mask = df["is_resolved"]
    resolved_count = int(resolved_mask.sum())
    open_backlog = total - resolved_count

    sla_compliance = (1.0 - float(df["sla_breached"].mean())) * 100.0
    high_sev_share = float(df["severity"].isin(["SEV-1", "SEV-2"]).mean()) * 100.0
    mtta_p50 = float(df["mtta_minutes"].median())

    mttr_valid = df.loc[resolved_mask, "mttr_hours"].dropna().to_numpy(dtype=float)
    if len(mttr_valid) > 0:
        mttr_p50 = float(np.percentile(mttr_valid, 50))
        mttr_p90 = float(np.percentile(mttr_valid, 90))
        mttr_p95 = float(np.percentile(mttr_valid, 95))
    else:
        mttr_p50 = mttr_p90 = mttr_p95 = 0.0

    reopen_rate = (
        float(df.loc[resolved_mask, "reopened"].mean()) * 100.0 if resolved_count > 0 else 0.0
    )
    gmud_pct = float(df["gmud_correlated"].mean()) * 100.0

    pareto_df = compute_pareto_signatures(df)
    vital_few = int(pareto_df["is_vital_few"].sum()) if not pareto_df.empty else 0

    anomalies_df = detect_daily_volume_anomalies(df)
    anomaly_days = int(anomalies_df["is_anomaly"].sum()) if not anomalies_df.empty else 0

    return ExecutiveKpiSummary(
        total_incidents=total,
        resolved_incidents=resolved_count,
        open_backlog=open_backlog,
        sla_compliance_pct=round(sla_compliance, 2),
        sev1_sev2_share_pct=round(high_sev_share, 2),
        mtta_p50_minutes=round(mtta_p50, 2),
        mttr_p50_hours=round(mttr_p50, 2),
        mttr_p90_hours=round(mttr_p90, 2),
        mttr_p95_hours=round(mttr_p95, 2),
        reopen_rate_pct=round(reopen_rate, 2),
        gmud_correlated_pct=round(gmud_pct, 2),
        pareto_vital_few_count=vital_few,
        pareto_total_signatures=len(pareto_df),
        anomaly_days_detected=anomaly_days,
    )


def generate_actionable_recommendations(df: pd.DataFrame) -> list[dict[str, str]]:
    """Synthesize data-driven Tier-3 RCA & Six Sigma prioritization actions."""
    if df.empty:
        return []

    recs: list[dict[str, str]] = []
    pareto = compute_pareto_signatures(df)
    anomalies = detect_daily_volume_anomalies(df)

    if not pareto.empty:
        top = pareto.iloc[0]
        vital_share = pareto.loc[pareto["is_vital_few"], "share_pct"].sum()
        vital_n = int(pareto["is_vital_few"].sum())
        recs.append(
            {
                "priority": "P0 — Pareto Chronic Elimination",
                "title": f"Eliminate #{1} Recurrence: {top['recurrence_signature']}",
                "evidence": (
                    f"Accounts for {int(top['incidents'])} incidents ({top['share_pct']:.1f}% of volume) "
                    f"with {top['sla_breach_pct']:.1f}% SLA breach rate. Top {vital_n} signatures drive "
                    f"{vital_share:.1f}% of total L2/L3 toil."
                ),
                "action": (
                    "Open dedicated Problem Management / Six Sigma DMAIC charter targeting connection-pool "
                    "sizing, composite database indexing, and circuit-breaker bulkheads."
                ),
            }
        )

    gmud_df = df[df["gmud_correlated"]]
    if not gmud_df.empty:
        gmud_reopen = float(gmud_df["reopened"].mean() * 100.0)
        base_reopen = float(df[~df["gmud_correlated"]]["reopened"].mean() * 100.0) if (~df["gmud_correlated"]).any() else 0.0
        anom_dates = anomalies.loc[anomalies["is_anomaly"], "opened_date"].dt.strftime("%Y-%m-%d").tolist()
        recs.append(
            {
                "priority": "P1 — GMUD Release Gate Hardening",
                "title": "Enforce Automated Canary Rollback on Change Windows",
                "evidence": (
                    f"Change-correlated incidents exhibit a {gmud_reopen:.1f}% reopen rate vs "
                    f"{base_reopen:.1f}% baseline, with {len(anom_dates)} MAD anomaly spike(s) "
                    f"({', '.join(anom_dates[:3]) or 'none'})."
                ),
                "action": (
                    "Gate production GMUD promotions on synthetic canary probes and automated Flyway/schema "
                    "contract checks before shifting >10% traffic."
                ),
            }
        )

    sev12 = df[df["severity"].isin(["SEV-1", "SEV-2"])]
    if not sev12.empty:
        breach_sev12 = float(sev12["sla_breached"].mean() * 100.0)
        worst_svc = (
            sev12.groupby("service")["sla_breached"]
            .mean()
            .mul(100.0)
            .sort_values(ascending=False)
        )
        worst_name = str(worst_svc.index[0])
        worst_val = float(worst_svc.iloc[0])
        recs.append(
            {
                "priority": "P2 — High-Severity MTTR Compression",
                "title": f"Automate L3 Triage Runbooks for {worst_name}",
                "evidence": (
                    f"Critical/High (SEV-1/SEV-2) SLA breach rate stands at {breach_sev12:.1f}% overall, "
                    f"peaking at {worst_val:.1f}% in `{worst_name}`."
                ),
                "action": (
                    "Attach pre-computed diagnostic telemetry (active DB locks, JVM heap histograms, "
                    "upstream p99 latency) directly to Alertmanager payloads to cut L3 RCA triage time."
                ),
            }
        )

    return recs
