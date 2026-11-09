"""Tests for SRE KPI Engine: Pareto 80/20, SLA Matrix, MAD Anomalies, and RCA recommendations."""

from __future__ import annotations

import pytest

from sre_analytics.kpi_engine import (
    compute_executive_summary,
    compute_pareto_signatures,
    compute_sla_matrix,
    detect_daily_volume_anomalies,
    generate_actionable_recommendations,
)
from sre_analytics.schema import validate_and_prepare_incidents
from sre_analytics.synthetic_generator import generate_synthetic_incidents


def test_pareto_and_anomaly_detection_on_synthetic_telemetry():
    raw = generate_synthetic_incidents(n_incidents=1800, seed=42)
    clean, _ = validate_and_prepare_incidents(raw)

    pareto = compute_pareto_signatures(clean)
    assert not pareto.empty
    assert pytest.approx(float(pareto["share_pct"].sum()), rel=1e-3) == 100.0
    assert pareto["incidents"].is_monotonic_decreasing
    assert int(pareto["is_vital_few"].sum()) < len(pareto)

    anomalies = detect_daily_volume_anomalies(clean)
    # Synthetic generator injects bursts on day offsets 62 and 134 -> MAD must detect >= 2 spikes
    spike_days = anomalies[anomalies["is_anomaly"]]
    assert len(spike_days) >= 2

    sla_mat = compute_sla_matrix(clean)
    assert not sla_mat.empty
    assert ((sla_mat >= 0.0) & (sla_mat <= 100.0)).all().all()

    summary = compute_executive_summary(clean)
    assert summary.total_incidents == 1800
    assert summary.mttr_p50_hours <= summary.mttr_p90_hours <= summary.mttr_p95_hours
    assert 50.0 < summary.sla_compliance_pct < 99.5

    recs = generate_actionable_recommendations(clean)
    assert len(recs) == 3
    assert recs[0]["priority"].startswith("P0")
