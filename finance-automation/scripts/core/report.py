"""
Generate summary rollups from categorized transactions.
Outputs monthly_summary.json with totals by category, expense_type, direction.
"""

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def generate_report(transactions_csv: str, output_json: str) -> dict:
    with open(transactions_csv, newline="", encoding="utf-8") as f:
        txns = list(csv.DictReader(f))

    summary = {
        "total_transactions": len(txns),
        "by_expense_type": defaultdict(lambda: {"amount_cad": "0", "count": 0}),
        "by_category": defaultdict(lambda: {"amount_cad": "0", "count": 0}),
        "income_total": "0",
        "total_fixed": "0",
        "total_variable": "0",
        "total_transfers": "0",
        "total_savings": "0",
        "total_investments": "0",
        "usd_transactions": [],
        "review_needed_count": 0,
        "auto_categorized_count": 0,
        "llm_categorized_count": 0,
        "corrected_count": 0,
    }

    income = Decimal("0")
    fixed = Decimal("0")
    variable = Decimal("0")
    transfers = Decimal("0")
    savings = Decimal("0")
    investments = Decimal("0")

    for txn in txns:
        currency = txn.get("currency", "CAD").upper()
        if currency != "CAD":
            summary["usd_transactions"].append({
                "date": txn.get("transaction_date"),
                "merchant": txn.get("normalized_merchant"),
                "amount": txn.get("amount"),
                "currency": currency,
            })
            continue  # Exclude non-CAD from totals

        try:
            amount = Decimal(txn.get("amount", "0"))
        except Exception:
            amount = Decimal("0")

        direction = txn.get("direction", "debit").lower()
        expense_type = txn.get("expense_type", "").lower()
        category = txn.get("category", "Uncategorized")
        review_status = txn.get("review_status", "needs_review")

        # Direction matters for income vs spending
        if direction == "credit" and expense_type == "income":
            income += amount
        elif expense_type == "fixed":
            fixed += amount
        elif expense_type == "variable":
            variable += amount
        elif expense_type == "transfer":
            transfers += amount
        elif expense_type == "savings":
            savings += amount
        elif expense_type == "investment":
            investments += amount

        # Category rollup
        cat_key = category or "Uncategorized"
        current = Decimal(summary["by_category"][cat_key]["amount_cad"])
        summary["by_category"][cat_key]["amount_cad"] = str(current + amount)
        summary["by_category"][cat_key]["count"] += 1

        # Status counters
        if review_status == "needs_review":
            summary["review_needed_count"] += 1
        elif review_status == "auto":
            summary["auto_categorized_count"] += 1
        elif review_status == "llm":
            summary["llm_categorized_count"] += 1
        elif review_status == "corrected":
            summary["corrected_count"] += 1

    summary["income_total"] = str(income)
    summary["total_fixed"] = str(fixed)
    summary["total_variable"] = str(variable)
    summary["total_transfers"] = str(transfers)
    summary["total_savings"] = str(savings)
    summary["total_investments"] = str(investments)
    summary["net_retained"] = str(income - fixed - variable - savings - investments)
    summary["by_category"] = dict(summary["by_category"])
    summary["by_expense_type"] = dict(summary["by_expense_type"])

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    return summary
