#!/usr/bin/env python3
"""
CLI entry point for the personal finance automation pipeline.

Usage:
  python run.py                          # Full pipeline (no Sheets write)
  python run.py --apply-corrections      # Apply review_needed.csv corrections first
  python run.py --update-sheets          # Write results to Google Sheets after run
  python run.py --apply-corrections --update-sheets

Flags:
  --apply-corrections   Read review_needed.csv, promote rules, update transactions
  --update-sheets       Write to Google Sheets after pipeline completes
  --inputs-dir PATH     Override inputs directory (default: ./inputs)
  --outputs-dir PATH    Override outputs directory (default: ./outputs)

Month detection:
  Target month is auto-detected as the month of the most recent transaction
  across all loaded files. No filename convention required.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
from scripts.config_paths import (
    accounts_config_path,
    ensure_writable_merchant_rules,
    merchant_rules_path,
    sheets_config_path,
    transfer_rules_path,
)

# Project root
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

INPUTS_DIR = ROOT / "inputs"
OUTPUTS_DIR = ROOT / "outputs"


def parse_args():
    parser = argparse.ArgumentParser(description="Personal Finance Automation Pipeline")
    parser.add_argument("--apply-corrections", action="store_true",
                        help="Process review_needed.csv before running pipeline")
    parser.add_argument("--update-sheets", action="store_true",
                        help="Write results to Google Sheets")
    parser.add_argument("--inputs-dir", default=str(INPUTS_DIR))
    parser.add_argument("--outputs-dir", default=str(OUTPUTS_DIR))
    return parser.parse_args()


def get_parser_for(institution: str):
    """Dynamically import the right parser module."""
    parser_map = {
        "scotiabank": "scripts.ingest.parse_scotiabank",
        "bmo": "scripts.ingest.parse_bmo",
        "rbc": "scripts.ingest.parse_rbc",
        "eqbank": "scripts.ingest.parse_eqbank",
        "tangerine": "scripts.ingest.parse_tangerine",
        "questrade": "scripts.ingest.parse_questrade",
    }
    module_name = parser_map.get(institution.lower())
    if not module_name:
        raise ValueError(f"No parser found for institution: {institution}. "
                         f"Available: {list(parser_map.keys())}")
    import importlib
    return importlib.import_module(module_name)


def filter_by_month(transactions, target_month: str):
    """
    Keep only transactions whose transaction_date falls in target_month (YYYY-MM).
    Called right after normalize — before dedup, transfer detection, and LLM
    categorization — so no API calls are wasted on out-of-month transactions.

    Pipeline position:
      normalize() → filter_by_month() → deduplicate() → detect_transfers()
                  → categorize() → report() → export()
    """
    kept = [t for t in transactions if t.transaction_date.startswith(target_month)]
    dropped = len(transactions) - len(kept)
    if dropped:
        print(f"Month filter ({target_month}): kept {len(kept)}, dropped {dropped} from other months")
    return kept


def detect_target_month(transactions) -> str:
    """
    Derive the target reporting month from the most recent transaction date
    across all loaded transactions. Banks export up to the current date, so
    the latest transaction is always in the current statement period.
    Returns YYYY-MM string.
    """
    dates = [t.transaction_date for t in transactions if t.transaction_date]
    if not dates:
        return ""
    return max(dates)[:7]


def main():
    args = parse_args()
    inputs_dir = Path(args.inputs_dir)
    outputs_dir = Path(args.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    run_log = outputs_dir / "run_log.txt"
    accounts_config = accounts_config_path()
    sheets_config = sheets_config_path()
    merchant_rules = (
        ensure_writable_merchant_rules()
        if args.apply_corrections
        else merchant_rules_path()
    )
    transfer_rules = transfer_rules_path()

    # 1. Validate inputs
    csv_files = list(inputs_dir.glob("*.csv"))
    if not csv_files:
        print(f"ERROR: No CSV files found in {inputs_dir}/")
        print("Drop your bank CSV exports into the inputs/ folder and try again.")
        sys.exit(1)
    print(f"Found {len(csv_files)} input file(s): {[f.name for f in csv_files]}")

    # 2. Apply corrections first (if requested)
    if args.apply_corrections:
        review_csv = outputs_dir / "review_needed.csv"
        transactions_csv = outputs_dir / "transactions_clean.csv"
        if review_csv.exists():
            from scripts.core.apply_corrections import apply_corrections
            stats = apply_corrections(str(review_csv), str(transactions_csv), str(merchant_rules))
            print(f"Corrections applied: {stats['corrections_applied']}, "
                  f"Rules added: {stats['rules_added']}")
            for w in stats.get("warnings", []):
                print(f"  WARNING: {w}")
        else:
            print("No review_needed.csv found — skipping corrections")

    # 3. Load accounts config
    import yaml
    with open(accounts_config, encoding="utf-8") as f:
        accounts_cfg = yaml.safe_load(f)
    accounts = {a["name"]: a for a in accounts_cfg.get("accounts", [])}

    # 4. Parse all input files
    from scripts.core.schema import Transaction

    all_raw = []
    for csv_file in csv_files:
        account_name = _match_account(csv_file.name, accounts)
        if not account_name:
            print(f"WARNING: Could not match {csv_file.name} to any account in accounts.yaml — skipping")
            continue

        account = accounts[account_name]
        institution = account.get("institution", "")
        format_variant = account.get("format_variant", "default")

        try:
            parser = get_parser_for(institution)
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        try:
            raw_txns = parser.parse(str(csv_file), account_name, format_variant)
            for r in raw_txns:
                r["source_file"] = str(csv_file)
            all_raw.extend(raw_txns)
            print(f"  {csv_file.name}: {len(raw_txns)} transactions ({institution})")
        except Exception as e:
            print(f"ERROR: Parser failed for {csv_file.name}: {e}")
            sys.exit(1)

    if not all_raw:
        print("ERROR: No transactions parsed from any input file.")
        sys.exit(1)

    # 5. Normalize
    from scripts.core.normalize import normalize
    transactions = []
    for csv_file in csv_files:
        file_raw = [r for r in all_raw if r.get("source_file") == str(csv_file)]
        if file_raw:
            transactions.extend(normalize(file_raw, str(csv_file)))
    print(f"Normalized: {len(transactions)} transactions (all months in export)")

    # 6. Filter to target month — uses latest transaction date, not filename
    target_month = detect_target_month(transactions)
    if not target_month:
        print("ERROR: Could not determine target month from transaction dates.")
        sys.exit(1)
    print(f"Target month: {target_month}")
    transactions = filter_by_month(transactions, target_month)
    if not transactions:
        print(f"ERROR: No transactions found for {target_month}.")
        sys.exit(1)

    # 7. Deduplicate
    from scripts.core.deduplicate import deduplicate
    transactions, dupes = deduplicate(transactions)
    if dupes:
        print(f"Deduplicated: removed {len(dupes)} duplicate(s)")

    # 8. Detect transfers
    from scripts.core.detect_transfers import detect_transfers
    transactions = detect_transfers(transactions, str(transfer_rules))
    transfer_count = sum(1 for t in transactions if t.transfer_flag)
    print(f"Transfer detection: {transfer_count} transfer(s) flagged")

    # 9. Categorize
    from scripts.core.categorize import categorize
    transactions = categorize(transactions, str(merchant_rules))
    auto = sum(1 for t in transactions if t.review_status == "auto")
    needs_review = sum(1 for t in transactions if t.review_status == "needs_review")
    llm = sum(1 for t in transactions if t.review_status == "llm")
    print(f"Categorized: {auto} auto, {llm} LLM, {needs_review} needs review")

    # 10. Generate report
    from scripts.output.export import export_transactions, write_run_log
    export_transactions(transactions, str(outputs_dir))

    from scripts.core.report import generate_report
    summary = generate_report(str(outputs_dir / "transactions_clean.csv"),
                              str(outputs_dir / "monthly_summary.json"))

    # 11. Write to Sheets (if requested)
    if args.update_sheets:
        from scripts.output.sheets_writer import write_to_sheets
        write_to_sheets(
            str(sheets_config),
            str(outputs_dir / "transactions_clean.csv"),
            str(merchant_rules),
            str(outputs_dir / "review_needed.csv"),
            str(outputs_dir / "monthly_summary.json"),
        )

    # 12. Run log + summary
    run_stats = {
        "target_month": target_month,
        "input_files": len(csv_files),
        "total_transactions": len(transactions),
        "duplicates_removed": len(dupes),
        "transfers_detected": transfer_count,
        "auto_categorized": auto,
        "llm_categorized": llm,
        "needs_review": needs_review,
        "income_total": summary.get("income_total"),
        "total_fixed": summary.get("total_fixed"),
        "total_variable": summary.get("total_variable"),
        "net_retained": summary.get("net_retained"),
    }
    write_run_log(str(run_log), run_stats)

    print(f"\n=== {target_month} Summary ===")
    print(f"  Income:          ${float(summary.get('income_total', 0)):>10,.2f}")
    print(f"  Fixed expenses:  ${float(summary.get('total_fixed', 0)):>10,.2f}")
    print(f"  Variable:        ${float(summary.get('total_variable', 0)):>10,.2f}")
    print(f"  Savings:         ${float(summary.get('total_savings', 0)):>10,.2f}")
    print(f"  Net retained:    ${float(summary.get('net_retained', 0)):>10,.2f}")
    print(f"\n  Review queue:    {needs_review} transaction(s) need your attention")
    if needs_review:
        print(f"  → Open outputs/review_needed.csv, fill corrections, re-run with --apply-corrections")
    print(f"\nOutputs written to: {outputs_dir}/")


def _match_account(filename: str, accounts: dict) -> Optional[str]:
    """Match a CSV filename to an account by checking if account name appears in filename."""
    filename_lower = filename.lower()
    for account_name in accounts:
        if account_name.lower().replace("-", "").replace("_", "") in \
                filename_lower.replace("-", "").replace("_", ""):
            return account_name
    # Fallback: match by institution name
    for account_name, account in accounts.items():
        institution = account.get("institution", "").lower()
        if institution and institution in filename_lower:
            return account_name
    return None


if __name__ == "__main__":
    main()
