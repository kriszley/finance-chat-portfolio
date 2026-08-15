"""
Google Sheets write-back using gspread + service account auth.

Write strategy:
- Transactions_Raw: append new rows only (never delete prior months)
- Rules: full replace each run (tool-owned, no formulas)
- Review_Queue: full replace each run (tool-owned, display-only)
- Monthly_Report (Sheet1): range-based updates only, preserves all formulas

All tab writes use batchUpdate — one API call per tab regardless of row count.
(Row-by-row writes hit the 300 req/min quota on 500-1000 transaction datasets.)
"""

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import gspread
from google.oauth2.service_account import Credentials
import yaml


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client(credentials_path: str) -> gspread.Client:
    creds_path = Path(credentials_path).expanduser()
    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    return gspread.authorize(creds)


def csv_to_rows(csv_path: str) -> list[list]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def update_transactions_raw(spreadsheet, tab_name: str, csv_path: str):
    """Append new rows to Transactions_Raw — never deletes existing rows."""
    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=10000, cols=30)

    new_rows = csv_to_rows(csv_path)
    if not new_rows:
        return

    headers = new_rows[0]
    data_rows = new_rows[1:]

    existing = ws.get_all_values()
    if not existing:
        # First-time setup: write headers + all data
        ws.update("A1", [headers] + data_rows)
        return

    # Get existing transaction_ids to avoid duplicates
    try:
        id_col = existing[0].index("transaction_id")
        existing_ids = {row[id_col] for row in existing[1:] if len(row) > id_col}
    except (ValueError, IndexError):
        existing_ids = set()

    try:
        new_id_col = headers.index("transaction_id")
    except ValueError:
        new_id_col = 0

    rows_to_append = [
        row for row in data_rows
        if len(row) > new_id_col and row[new_id_col] not in existing_ids
    ]

    if rows_to_append:
        ws.append_rows(rows_to_append, value_input_option="RAW")


def update_tab_full_replace(spreadsheet, tab_name: str, csv_path: str):
    """Full replace for Rules and Review_Queue tabs."""
    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=2000, cols=20)

    rows = csv_to_rows(csv_path)
    ws.clear()
    if rows:
        ws.update("A1", rows)


def update_monthly_report(spreadsheet, sheet_name: str, summary_json: str, ranges_config: dict):
    """
    Range-based updates to the existing Sheet1 — preserves all formulas.
    Writes only the named ranges in sheets_config.yaml monthly_report_ranges.
    Uses batchUpdate for a single API call.
    """
    ws = spreadsheet.worksheet(sheet_name)

    with open(summary_json, encoding="utf-8") as f:
        summary = json.load(f)

    # Map config range keys to summary values
    value_map = {
        "income_total": summary.get("income_total", "0"),
        "total_fixed_expenses": summary.get("total_fixed", "0"),
        "total_variable_expenses": summary.get("total_variable", "0"),
        "total_expense": str(
            float(summary.get("total_fixed", "0")) + float(summary.get("total_variable", "0"))
        ),
        "target_retained_earning": summary.get("net_retained", "0"),
        "real_retained_earning": summary.get("net_retained", "0"),
    }

    batch = []
    for key, cell_range in ranges_config.items():
        if key in value_map:
            batch.append({
                "range": f"{sheet_name}!{cell_range}",
                "values": [[value_map[key]]]
            })

    if batch:
        spreadsheet.values_batch_update({
            "valueInputOption": "USER_ENTERED",
            "data": batch
        })


def write_to_sheets(
    config_path: str,
    transactions_csv: str,
    rules_csv: str,
    review_csv: str,
    summary_json: str,
):
    config = load_config(config_path)
    client = get_client(config["credentials_path"])
    spreadsheet = client.open_by_key(config["spreadsheet_id"])

    tabs = config.get("tabs", {})

    print("Writing Transactions_Raw...")
    update_transactions_raw(spreadsheet, tabs.get("transactions_raw", "Transactions_Raw"), transactions_csv)

    print("Writing Rules...")
    update_tab_full_replace(spreadsheet, tabs.get("rules", "Rules"), rules_csv)

    print("Writing Review_Queue...")
    update_tab_full_replace(spreadsheet, tabs.get("review_queue", "Review_Queue"), review_csv)

    print("Updating Monthly_Report ranges...")
    update_monthly_report(
        spreadsheet,
        config.get("monthly_report_sheet", "Sheet1"),
        summary_json,
        config.get("monthly_report_ranges", {}),
    )

    print("✓ Sheets update complete")
