"""Deterministic 100% synthetic B2B SRE / Tier-3 incident telemetry generator.

Zero real customer records, zero proprietary schemas, and zero NDA-encumbered strings.
Injects realistic statistical phenomena (Pareto 80/20 recurrence clusters, log-normal
MTTR right-skew, GMUD post-deployment regression bursts, and open L3 backlog) so the
observability engine and tests validate genuine operational patterns.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

SERVICES: tuple[str, ...] = (
    "payment-gateway",
    "ledger-core",
    "identity-sso",
    "document-pipeline",
    "order-orchestrator",
    "webhook-dispatcher",
)

DETECTION_CHANNELS: tuple[str, ...] = (
    "Prometheus / Alertmanager",
    "Synthetic Canary Probe",
    "APM Latency / Error Burn",
    "B2B Partner API Escalation",
    "Batch Reconciliation Guard",
)

ROOT_CAUSES: tuple[str, ...] = (
    "DB Lock Contention / Unindexed Query",
    "Hikari / Connection Pool Exhaustion",
    "Upstream Partner Timeout (Circuit Open)",
    "Post-GMUD Config / Schema Drift",
    "Worker Memory Pressure / OOMKill",
    "Idempotency / Dead-Letter Queue Backlog",
    "TLS / OAuth Token Rotation Skew",
)


def generate_synthetic_incidents(
    n_incidents: int = 2400,
    seed: int = 42,
    start_date: str = "2026-05-01T00:00:00Z",
    days: int = 180,
) -> pd.DataFrame:
    """Generate a reproducible multi-quarter synthetic incident dataset."""
    if n_incidents < 50:
        raise ValueError("n_incidents must be >= 50 for meaningful statistical distributions.")

    rng = np.random.default_rng(seed)
    start_ts = pd.Timestamp(start_date)

    # Base arrival times across the window + business-hour diurnal modulation
    day_offsets = rng.integers(0, days, size=n_incidents)
    #Inject two realistic operational anomaly bursts (GMUD release windows on day 62 and day 134)
    burst_1_size = max(15, n_incidents // 45)
    burst_2_size = max(18, n_incidents // 40)
    day_offsets[:burst_1_size] = 62
    day_offsets[burst_1_size : burst_1_size + burst_2_size] = 134

    hour_probs = np.array(
        [
            0.015, 0.012, 0.010, 0.010, 0.012, 0.018,
            0.030, 0.045, 0.065, 0.080, 0.085, 0.075,
            0.060, 0.075, 0.085, 0.080, 0.068, 0.050,
            0.038, 0.028, 0.022, 0.015, 0.012, 0.010,
        ]
    )
    hour_probs = hour_probs / hour_probs.sum()
    hours = rng.choice(np.arange(24), size=n_incidents, p=hour_probs)
    minutes = rng.integers(0, 60, size=n_incidents)
    seconds = rng.integers(0, 60, size=n_incidents)

    opened_at = [
        start_ts + timedelta(days=int(d), hours=int(h), minutes=int(m), seconds=int(s))
        for d, h, m, s in zip(day_offsets, hours, minutes, seconds)
    ]

    # Service weights (Pareto skew toward high-throughput services)
    service_weights = [0.28, 0.21, 0.16, 0.15, 0.11, 0.09]
    services = rng.choice(SERVICES, size=n_incidents, p=service_weights)

    # Force burst windows to reflect realistic correlated failure modes
    services[:burst_1_size] = "payment-gateway"
    services[burst_1_size : burst_1_size + burst_2_size] = "document-pipeline"

    severities = rng.choice(
        ["SEV-1", "SEV-2", "SEV-3", "SEV-4"],
        size=n_incidents,
        p=[0.06, 0.21, 0.48, 0.25],
    )
    severities[: burst_1_size // 2] = "SEV-1"
    severities[burst_1_size // 2 : burst_1_size] = "SEV-2"

    # Root causes correlated with service to create realistic 80/20 Pareto signatures
    root_causes: list[str] = []
    gmud_flags: list[bool] = []
    for idx, svc in enumerate(services):
        if idx < burst_1_size:
            root_causes.append("Post-GMUD Config / Schema Drift")
            gmud_flags.append(True)
            continue
        if idx < burst_1_size + burst_2_size:
            root_causes.append("DB Lock Contention / Unindexed Query")
            gmud_flags.append(True)
            continue

        if svc == "payment-gateway":
            rc = rng.choice(
                ROOT_CAUSES,
                p=[0.12, 0.38, 0.24, 0.12, 0.04, 0.05, 0.05],
            )
        elif svc == "ledger-core":
            rc = rng.choice(
                ROOT_CAUSES,
                p=[0.44, 0.16, 0.08, 0.10, 0.06, 0.12, 0.04],
            )
        elif svc == "document-pipeline":
            rc = rng.choice(
                ROOT_CAUSES,
                p=[0.18, 0.10, 0.08, 0.08, 0.40, 0.12, 0.04],
            )
        else:
            rc = rng.choice(
                ROOT_CAUSES,
                p=[0.15, 0.15, 0.22, 0.16, 0.10, 0.12, 0.10],
            )
        root_causes.append(str(rc))
        is_gmud = bool(
            rng.random() < (0.68 if rc == "Post-GMUD Config / Schema Drift" else 0.11)
        )
        gmud_flags.append(is_gmud)

    channels = rng.choice(
        DETECTION_CHANNELS,
        size=n_incidents,
        p=[0.36, 0.22, 0.20, 0.13, 0.09],
    )

    tiers = [
        "L3-SRE"
        if (sev in ("SEV-1", "SEV-2") or rng.random() < 0.32)
        else ("L2-Sustainment" if rng.random() < 0.72 else "L1-NOC")
        for sev in severities
    ]

    # Log-normal MTTA and MTTR calibrated per severity (with realistic tail breaches ~12-18%)
    mtta_medians = {"SEV-1": 3.2, "SEV-2": 8.5, "SEV-3": 24.0, "SEV-4": 65.0}
    mttr_medians = {"SEV-1": 0.62, "SEV-2": 2.35, "SEV-3": 11.5, "SEV-4": 29.0}

    ack_times: list[pd.Timestamp | pd.NaT] = []
    res_times: list[pd.Timestamp | pd.NaT] = []
    statuses: list[str] = []
    reopened: list[bool] = []

    max_window_ts = start_ts + timedelta(days=int(days))

    for idx in range(n_incidents):
        sev = str(severities[idx])
        op = opened_at[idx]

        # Simulate ~1.5% missing acknowledgement telemetry in raw operational logs
        if rng.random() < 0.015:
            ack_ts = pd.NaT
        else:
            mtta_min = float(rng.lognormal(mean=np.log(mtta_medians[sev]), sigma=0.45))
            ack_ts = op + timedelta(minutes=max(0.5, mtta_min))
        ack_times.append(ack_ts)

        # Recent tickets near end of window have a realistic open backlog fraction
        recency_days = (max_window_ts - op).total_seconds() / 86400.0
        is_open = (recency_days < 5.0 and rng.random() < 0.35) or (rng.random() < 0.018)

        if is_open:
            statuses.append(str(rng.choice(["INVESTIGATING", "MITIGATING", "OPEN"])))
            res_times.append(pd.NaT)
            reopened.append(False)
            if rng.random() < 0.55:
                root_causes[idx] = ""  # Pending L3 RCA on active investigations
        else:
            sigma = 0.62 if sev in ("SEV-1", "SEV-2") else 0.55
            mttr_h = float(rng.lognormal(mean=np.log(mttr_medians[sev]), sigma=sigma))
            # DB lock & worker OOM take ~25% longer to diagnose at L3
            if "Lock" in root_causes[idx] or "OOMKill" in root_causes[idx]:
                mttr_h *= 1.25
            res_ts = op + timedelta(hours=max(0.08, mttr_h))
            if ack_ts is not pd.NaT and res_ts < ack_ts:
                res_ts = ack_ts + timedelta(minutes=5)
            statuses.append(str(rng.choice(["RESOLVED", "CLOSED"], p=[0.35, 0.65])))
            res_times.append(res_ts)
            reopened.append(
                bool(rng.random() < (0.14 if gmud_flags[idx] else 0.045))
            )

    order_idx = np.argsort(opened_at)
    df = pd.DataFrame(
        {
            "incident_id": [f"INC-2026-{i + 10001:05d}" for i in range(n_incidents)],
            "opened_at": [opened_at[i].isoformat() for i in order_idx],
            "acknowledged_at": [
                "" if ack_times[i] is pd.NaT else ack_times[i].isoformat()
                for i in order_idx
            ],
            "resolved_at": [
                "" if res_times[i] is pd.NaT else res_times[i].isoformat()
                for i in order_idx
            ],
            "service": [services[i] for i in order_idx],
            "severity": [severities[i] for i in order_idx],
            "status": [statuses[i] for i in order_idx],
            "support_tier": [tiers[i] for i in order_idx],
            "detection_channel": [channels[i] for i in order_idx],
            "root_cause_category": [root_causes[i] for i in order_idx],
            "gmud_correlated": [gmud_flags[i] for i in order_idx],
            "reopened": [reopened[i] for i in order_idx],
        }
    )
    return df
