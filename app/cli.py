from __future__ import annotations

import argparse
import sys
from datetime import date

from app.config import ConfigValidationError, load_config
from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, InputValidationError, load_security_master_csv, portfolio_summary, validate_ingestion
from data.schemas import TaxProfile
from reporting.process_log import build_process_log
from reporting.report_generator import render_report


class CliRunError(ValueError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tax-aware-portfolio-engine")
    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser("analyze", help="Analyze a portfolio snapshot")
    analyze.add_argument("--holdings", default="data/mock_holdings.csv")
    analyze.add_argument("--lots", default="data/mock_tax_lots.csv")
    analyze.add_argument("--account-menus", default="data/mock_account_menus.csv")
    analyze.add_argument("--security-master", default="data/security_master.csv")
    analyze.add_argument("--config-dir", default="config")
    analyze.add_argument("--config-file")
    analyze.add_argument("--output", default="outputs/portfolio_report.md")
    analyze.add_argument("--target-profile")
    analyze.add_argument("--drift-threshold", type=float)
    return parser


def tax_profile_from_config(config: dict) -> TaxProfile:
    return TaxProfile(**config["tax_profile"])


def run_analyze(args: argparse.Namespace) -> str:
    overrides = {"thresholds": {"drift_threshold": args.drift_threshold}} if args.drift_threshold is not None else None
    config = load_config(args.config_dir, args.config_file, overrides)
    provider = CsvDataProvider(as_of_date=date.fromisoformat(config["defaults"]["as_of_date"]))
    ingestion = provider.load(args.holdings, args.lots, args.account_menus)
    security_master = load_security_master_csv(args.security_master)
    validate_ingestion(ingestion, security_master)
    summary = portfolio_summary(ingestion.holdings)
    target_name = args.target_profile or config["defaults"]["target_profile"]
    if target_name not in config["model_portfolios"]:
        raise CliRunError(f"Unknown target profile: {target_name}")
    target = config["model_portfolios"][target_name]
    analysis = generate_recommendations(
        ingestion.holdings,
        ingestion.tax_lots,
        ingestion.account_menus,
        security_master,
        config["thresholds"],
        tax_profile_from_config(config),
        target,
        date.fromisoformat(config["defaults"]["as_of_date"]),
    )
    recommendations = analysis["recommendations"]
    fee_drag_bps = round(
        sum((holding.expense_ratio or 0.0) * holding.market_value for holding in ingestion.holdings)
        / (summary["total_market_value"] or 1.0)
        * 10000,
        2,
    )
    process_log = build_process_log(
        recommendations,
        analysis,
        fee_drag_bps,
        config["defaults"]["as_of_date"],
    )
    report_text = render_report(analysis, recommendations, process_log, fee_drag_bps, args.output)
    print(f"Total value: ${summary['total_market_value']:,.2f}")
    print(f"Accounts detected: {', '.join(summary['accounts_detected'])}")
    print(f"Warnings: {ingestion.warnings}")
    print(f"Report written: {args.output}")
    return report_text


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "analyze":
            run_analyze(args)
        else:
            parser.print_help()
    except (CliRunError, ConfigValidationError, InputValidationError, FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
