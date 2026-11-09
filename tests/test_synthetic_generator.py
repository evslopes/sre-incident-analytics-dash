"""Tests for deterministic synthetic incident generator."""

from __future__ import annotations

import pytest

from sre_analytics.schema import REQUIRED_COLUMNS, validate_and_prepare_incidents
from sre_analytics.synthetic_generator import SERVICES, generate_synthetic_incidents


def test_generator_is_deterministic_and_schema_valid():
    df_a = generate_synthetic_incidents(n_incidents=300, seed=123)
    df_b = generate_synthetic_incidents(n_incidents=300, seed=123)

    assert list(df_a.columns) == list(REQUIRED_COLUMNS)
    assert df_a.equals(df_b)
    assert set(df_a["service"].unique()).issubset(set(SERVICES))

    clean, audit = validate_and_prepare_incidents(df_a)
    assert audit.dropped_malformed_rows == 0
    assert len(clean) == 300


def test_generator_rejects_too_small_sample():
    with pytest.raises(ValueError, match=">= 50"):
        generate_synthetic_incidents(n_incidents=10)
