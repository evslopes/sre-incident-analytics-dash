"""Integration tests for Executive HTML Exporter, CLI commands, and Plotly Dash app creation."""

from __future__ import annotations

from pathlib import Path

from sre_analytics.app import create_dash_app
from sre_analytics.cli import main as cli_main
from sre_analytics.report_exporter import export_executive_html_report
from sre_analytics.schema import validate_and_prepare_incidents
from sre_analytics.synthetic_generator import generate_synthetic_incidents


def test_html_report_export_and_cli_roundtrip(tmp_path: Path):
    csv_out = tmp_path / "incidents.csv"
    html_out = tmp_path / "exec_report.html"

    rc_gen = cli_main(["generate-data", "--rows", "400", "--seed", "7", "--output", str(csv_out)])
    assert rc_gen == 0
    assert csv_out.exists()

    rc_rep = cli_main(["export-report", "--input", str(csv_out), "--output", str(html_out)])
    assert rc_rep == 0
    assert html_out.exists()

    content = html_out.read_text(encoding="utf-8")
    assert "Operational Reliability, Pareto RCA &amp; SLA Executive Report" in content
    assert "P0 — Pareto Chronic Elimination" in content
    assert "Data Hygiene &amp; Schema Audit:" in content


def test_dash_app_instantiates_and_registers_callback(tmp_path: Path):
    raw = generate_synthetic_incidents(n_incidents=250, seed=99)
    clean, audit = validate_and_prepare_incidents(raw)
    assert audit.valid_rows == 250

    app = create_dash_app(clean)
    assert app.layout is not None
    assert len(app.callback_map) >= 1

    out = export_executive_html_report(clean, audit, tmp_path / "smoke.html")
    assert out.exists()
