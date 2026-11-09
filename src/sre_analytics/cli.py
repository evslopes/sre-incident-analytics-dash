"""Command-line interface for synthetic telemetry generation, KPI audit, report export, and Dash server."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
import pandas as pd

from sre_analytics.app import create_dash_app
from sre_analytics.kpi_engine import (
    compute_executive_summary,
    generate_actionable_recommendations,
)
from sre_analytics.report_exporter import export_executive_html_report
from sre_analytics.schema import validate_and_prepare_incidents
from sre_analytics.synthetic_generator import generate_synthetic_incidents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sre-analytics",
        description="SRE & Tier-3 Sustainment Incident Intelligence CLI (100% Synthetic Telemetry)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-data", help="Generate deterministic synthetic incident CSV")
    gen.add_argument("--rows", type=int, default=2400, help="Number of synthetic incidents (>=50)")
    gen.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")
    gen.add_argument(
        "--output",
        type=str,
        default="data/synthetic_incidents.csv",
        help="Destination CSV path",
    )

    rep = sub.add_parser("export-report", help="Export standalone Executive Storytelling HTML report")
    rep.add_argument("--input", type=str, default="", help="Optional input CSV (generates in-memory if omitted)")
    rep.add_argument(
        "--output",
        type=str,
        default="reports/executive_sre_report.html",
        help="Destination HTML report path",
    )

    summ = sub.add_parser("summary", help="Print JSON summary of SRE KPIs, audit & RCA recommendations")
    summ.add_argument("--input", type=str, default="", help="Optional input CSV")

    srv = sub.add_parser("serve", help="Launch interactive Plotly Dash console")
    srv.add_argument("--input", type=str, default="", help="Optional input CSV")
    srv.add_argument("--host", type=str, default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8050)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate-data":
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df = generate_synthetic_incidents(n_incidents=args.rows, seed=args.seed)
        df.to_csv(out_path, index=False)
        print(f"Generated {len(df):,} synthetic incidents -> {out_path}")
        return 0

    if args.command in ("export-report", "summary", "serve"):
        if getattr(args, "input", "") and Path(args.input).exists():
            raw_df = pd.read_csv(args.input)
        else:
            raw_df = generate_synthetic_incidents(n_incidents=2400, seed=42)
        clean_df, audit = validate_and_prepare_incidents(raw_df)

        if args.command == "export-report":
            out = export_executive_html_report(clean_df, audit, args.output)
            print(f"Exported standalone Executive SRE report -> {out}")
            return 0

        if args.command == "summary":
            payload = {
                "audit": asdict(audit),
                "kpis": asdict(compute_executive_summary(clean_df)),
                "recommendations": generate_actionable_recommendations(clean_df),
            }
            print(json.dumps(payload, indent=2))
            return 0

        if args.command == "serve":
            dash_app = create_dash_app(clean_df)
            dash_app.run(host=args.host, port=args.port, debug=False)
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
