"""Domain schema, contractual SLA targets, and explicit null/anomaly hygiene."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

# Contractual resolution SLA targets (in hours) by incident severity
SLA_TARGET_HOURS: dict[str, float] = {
    "SEV-1": 1.0,
    "SEV-2": 4.0,
    "SEV-3": 24.0,
    "SEV-4": 72.0,
}

# Contractual acknowledgement targets (in minutes)
MTTA_TARGET_MINUTES: dict[str, float] = {
    "SEV-1": 5.0,
    "SEV-2": 15.0,
    "SEV-3": 60.0,
    "SEV-4": 240.0,
}

SEVERITY_ORDER: list[str] = ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]

REQUIRED_COLUMNS: tuple[str, ...] = (
    "incident_id",
    "opened_at",
    "acknowledged_at",
    "resolved_at",
    "service",
    "severity",
    "status",
    "support_tier",
    "detection_channel",
    "root_cause_category",
    "gmud_correlated",
    "reopened",
)


@dataclass(frozen=True)
class DataQualityAudit:
    """Explicit data-hygiene audit capturing missingness and dropped malformed rows."""

    raw_rows: int
    valid_rows: int
    dropped_malformed_rows: int
    unresolved_backlog_rows: int
    missing_root_cause_imputed: int
    missing_ack_imputed: int


def validate_and_prepare_incidents(
    raw_df: pd.DataFrame,
    reference_now: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, DataQualityAudit]:
    """Validate incident telemetry schema, audit NULLs, and derive analytical features.

     Explicit missing-value policy (zero silent drops of valid operational state):
    1. Rows missing mandatory identifiers (`incident_id`, `opened_at`, `service`, `severity`)
       or with invalid severity codes or negative duration (`resolved_at < opened_at`) are
       quarantined/dropped and counted in `dropped_malformed_rows`.
    2. Unresolved tickets (`status` in `OPEN`, `INVESTIGATING`, `MITIGATING`) naturally lack
       `resolved_at`. Instead of dropping active backlog or leaking future timestamps, we retain
       them with `is_resolved = False`, `mttr_hours = NaN`, and compute `open_age_hours` relative
       to `reference_now` (defaults to dataset max timestamp) to detect in-flight SLA breaches.
    3. Missing `root_cause_category` on in-flight tickets is explicitly labeled
       `"Pending L3 RCA"` rather than discarded.
    4. Missing `acknowledged_at` on resolved tickets is imputed conservatively using the
       per-severity median acknowledgement delay computed strictly on non-null rows, paired
       with an explicit boolean indicator `ack_imputed`.
    """
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in raw_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required incident columns: {missing_cols}")

    raw_count = len(raw_df)
    df = raw_df.copy()

    df["opened_at"] = pd.to_datetime(df["opened_at"], utc=True, errors="coerce")
    df["acknowledged_at"] = pd.to_datetime(df["acknowledged_at"], utc=True, errors="coerce")
    df["resolved_at"] = pd.to_datetime(df["resolved_at"], utc=True, errors="coerce")

    valid_mask = (
        df["incident_id"].notna()
        & df["opened_at"].notna()
        & df["service"].notna()
        & df["severity"].isin(SEVERITY_ORDER)
    )
    # Reject corrupted timestamps where resolved_at precedes opened_at
    temporal_valid = df["resolved_at"].isna() | (df["resolved_at"] >= df["opened_at"])
    valid_mask = valid_mask & temporal_valid

    dropped_malformed = int((~valid_mask).sum())
    df = df.loc[valid_mask].copy()

    if df.empty:
        audit = DataQualityAudit(
            raw_rows=raw_count,
            valid_rows=0,
            dropped_malformed_rows=dropped_malformed,
            unresolved_backlog_rows=0,
            missing_root_cause_imputed=0,
            missing_ack_imputed=0,
        )
        return df, audit

    ref_ts = reference_now if reference_now is not None else df["opened_at"].max()
    if ref_ts.tzinfo is None:
        ref_ts = ref_ts.tz_localize("UTC")

    # Root cause missingness handling
    rc_missing_mask = df["root_cause_category"].isna() | (
        df["root_cause_category"].astype(str).str.strip() == ""
    )
    missing_rc_count = int(rc_missing_mask.sum())
    df.loc[rc_missing_mask, "root_cause_category"] = "Pending L3 RCA"

    # MTTA calculation & explicit indicator for missing acknowledgement timestamps
    raw_mtta = (df["acknowledged_at"] - df["opened_at"]).dt.total_seconds() / 60.0
    invalid_ack = raw_mtta.isna() | (raw_mtta < 0)
    df["ack_imputed"] = invalid_ack
    missing_ack_count = int(invalid_ack.sum())

    df["mtta_minutes"] = raw_mtta.where(~invalid_ack, np.nan)
    medians_by_sev = df.groupby("severity")["mtta_minutes"].transform("median")
    fallback_targets = df["severity"].map(MTTA_TARGET_MINUTES)
    df["mtta_minutes"] = df["mtta_minutes"].fillna(medians_by_sev).fillna(fallback_targets)

    # Resolution & SLA evaluation
    df["is_resolved"] = df["status"].isin(["RESOLVED", "CLOSED"]) & df["resolved_at"].notna()
    unresolved_count = int((~df["is_resolved"]).sum())

    df["mttr_hours"] = np.where(
        df["is_resolved"],
        (df["resolved_at"] - df["opened_at"]).dt.total_seconds() / 3600.0,
        np.nan,
    )
    df["sla_target_hours"] = df["severity"].map(SLA_TARGET_HOURS)

    effective_elapsed_hours = np.where(
        df["is_resolved"],
        df["mttr_hours"],
        (ref_ts - df["opened_at"]).dt.total_seconds() / 3600.0,
    )
    df["effective_elapsed_hours"] = np.maximum(effective_elapsed_hours, 0.0)
    df["sla_breached"] = df["effective_elapsed_hours"] > df["sla_target_hours"]
    df["gmud_correlated"] = df["gmud_correlated"].astype(bool)
    df["reopened"] = df["reopened"].astype(bool)

    df["opened_date"] = df["opened_at"].dt.floor("D")
    df["opened_week"] = (
        df["opened_at"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
    )
    df["recurrence_signature"] = df["service"] + " :: " + df["root_cause_category"]

    df = df.sort_values("opened_at").reset_index(drop=True)

    audit = DataQualityAudit(
        raw_rows=raw_count,
        valid_rows=len(df),
        dropped_malformed_rows=dropped_malformed,
        unresolved_backlog_rows=unresolved_count,
        missing_root_cause_imputed=missing_rc_count,
        missing_ack_imputed=missing_ack_count,
    )
    return df, audit
