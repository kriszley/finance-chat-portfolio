"""
Write transactions_clean.csv, review_needed.csv, monthly_summary.json, run_log.txt to outputs/.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import Transaction

REVIEW_NEEDED_EXTRA_COLS = ["corrected_category", "corrected_subcategory", "corrected_expense_type"]


def export_transactions(transactions: list[Transaction], outputs_dir: str):
    out = Path(outputs_dir)
    out.mkdir(parents=True, exist_ok=True)

    headers = Transaction.csv_headers()
    review_headers = headers + REVIEW_NEEDED_EXTRA_COLS

    clean = []
    review = []

    for txn in transactions:
        row = txn.to_dict()
        clean.append(row)
        if txn.review_status == "needs_review":
            review_row = dict(row)
            review_row["corrected_category"] = ""
            review_row["corrected_subcategory"] = ""
            review_row["corrected_expense_type"] = ""
            review.append(review_row)

    # transactions_clean.csv — all transactions
    with open(out / "transactions_clean.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(clean)

    # review_needed.csv — flagged only, with blank correction columns
    with open(out / "review_needed.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review_headers)
        writer.writeheader()
        writer.writerows(review)

    return {"total": len(clean), "needs_review": len(review)}


def write_run_log(log_path: str, stats: dict):
    with open(log_path, "a", encoding="utf-8") as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n=== Run: {ts} ===\n")
        for k, v in stats.items():
            f.write(f"  {k}: {v}\n")
