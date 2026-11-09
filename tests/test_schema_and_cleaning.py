"""Unit tests for incident schema validation, NULL auditing, and leakage-free backlog handling."""

from __future__ import annotations

import pandas as pd
import pytest

from sre_analytics.schema import REQUIRED_COLUMNS, validate_and_prepare_incidents


def _sample_rows() -> list[dict]:
    return [
        {
            "incident_id": "INC-001",
            "opened_at": "2026-06-01T10:00:00Z",
            "acknowledged_at": "2026-06-01T10:04:00Z",
            "resolved_at": "2026-06-01T10:45:00Z",
            "service": "payment-gateway",
            "severity": "SEV-1",
            "status": "CLOSED",
            "support_tier": "L3-SRE",
            "detection_channel": "Prometheus / Alertmanager",
            "root_cause_category": "Hikari / Connection Pool Exhaustion",
            "gmud_correlated": False,
            "reopened": False,
        },
        # Active open backlog ticket (no resolved_at, blank root cause, missing ack)
        {
            "incident_id": "INC-002",
            "opened_at": "2026-06-01T12:00:00Z",
            "acknowledged_at": "",
            "resolved_at": "",
            "service": "ledger-core",
            "severity": "SEV-1",
            "status": "INVESTIGATING",
            "support_tier": "L3-SRE",
            "detection_channel": "APM Latency / Error Burn",
            "root_cause_category": "",
            "gmud_correlated": True,
            "reopened": False,
        },
        # Malformed row: resolved_at BEFORE opened_at -> must be quarantined
        {
            "incident_id": "INC-BAD-TIME",
            "opened_at": "2026-06-02T10:00:00Z",
            "acknowledged_at": "2026-06-02T10:05:00Z",
            "resolved_at": "2026-06-02T09:00:00Z",
            "service": "identity-sso",
            "severity": "SEV-2",
            "status": "RESOLVED",
            "support_tier": "L2-Sustainment",
            "detection_channel": "Synthetic Canary Probe",
            "root_cause_category": "TLS / OAuth Token Rotation Skew",
            "gmud_correlated": False,
            "reopened": False,
        },
        # Malformed row: invalid severity code
        {
            "incident_id": "INC-BAD-SEV",
            "opened_at": "2026-06-02T11:00:00Z",
            "acknowledged_at": "2026-06-02T11:10:00Z",
            "resolved_at": "2026-06-02T12:00:00Z",
            "service": "identity-sso",
            "severity": "SEV-99",
            "status": "CLOSED",
            "support_tier": "L1-NOC",
            "detection_channel": "Synthetic Canary Probe",
            "root_cause_category": "TLS / OAuth Token Rotation Skew",
            "gmud_correlated": False,
            "reopened": False,
        },
    ]


def test_missing_required_column_raises_value_error():
    incomplete = pd.DataFrame([{"incident_id": "INC-1"}])
    with pytest.raises(ValueError, match="Missing required incident columns"):
        validate_and_prepare_incidents(incomplete)


def test_quarantines_malformed_rows_and_preserves_unresolved_backlog():
    raw = pd.DataFrame(_sample_rows(), columns=list(REQUIRED_COLUMNS))
    ref_now = pd.Timestamp("2026-06-01T14:30:00Z")
    clean, audit = validate_and_prepare_incidents(raw, reference_now=ref_now)

    assert audit.raw_rows == 4
    assert audit.valid_rows == 2
    assert audit.dropped_malformed_rows == 2
    assert audit.unresolved_backlog_rows == 1
    assert audit.missing_root_cause_imputed == 1
    assert audit.missing_ack_imputed == 1

    inc1 = clean.loc[clean["incident_id"] == "INC-001"].iloc[0]
    assert bool(inc1["is_resolved"]) is True
    assert pytest.approx(inc1["mttr_hours"], rel=1e-3) == 0.75
    assert bool(inc1["sla_breached"]) is False  # 0.75h <= 1.0h SEV-1 SLA

    inc2 = clean.loc[clean["incident_id"] == "INC-002"].iloc[0]
    assert bool(inc2["is_resolved"]) is False
    assert pd.isna(inc2["mttr_hours"])
    assert inc2["root_cause_category"] == "Pending L3 RCA"
    assert bool(inc2["ack_imputed"]) is True
    # Imputed from SEV-1 median (4.0 min from INC-001)
    assert pytest.approx(inc2["mtta_minutes"], rel=1e-3) == 4.0
    # Elapsed 2.5h > 1.0h SEV-1 SLA -> in-flight breach detected!
    assert bool(inc2["sla_breached"]) is True
