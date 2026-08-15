from typing import Optional
"""
Internal transfer detection between own accounts.

Algorithm:
1. Load transfer_rules.csv (known account pairs)
2. For each transaction: if source_account in a transfer pair, scan for matching
   counterpart transaction with same amount within ±3 days
3. If both legs found: set transfer_flag=True on both
4. If only one leg: set transfer_flag=True on single leg (known pair rule)
5. Set expense_type=transfer on all flagged transactions
"""

import csv
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import Transaction

TRANSFER_WINDOW_DAYS = 3


def load_transfer_rules(rules_path: str) -> list[dict]:
    with open(rules_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def detect_transfers(transactions: list[Transaction], rules_path: str) -> list[Transaction]:
    """
    Mutates transfer_flag and expense_type on matching transactions.
    Returns the updated transaction list.
    """
    rules = load_transfer_rules(rules_path)
    if not rules:
        return transactions

    # Build lookup: account → list of counterpart accounts
    transfer_pairs: dict[str, set[str]] = {}
    for rule in rules:
        acct_from = rule["account_from"].strip()
        acct_to = rule["account_to"].strip()
        transfer_pairs.setdefault(acct_from, set()).add(acct_to)
        transfer_pairs.setdefault(acct_to, set()).add(acct_from)

    # Index transactions by account for fast counterpart lookup
    by_account: dict[str, list[Transaction]] = {}
    for txn in transactions:
        by_account.setdefault(txn.source_account, []).append(txn)

    matched_ids: set[str] = set()

    for txn in transactions:
        if txn.transaction_id in matched_ids:
            continue
        counterparts = transfer_pairs.get(txn.source_account, set())
        if not counterparts:
            continue

        # Look for a matching leg in each counterpart account
        for cp_account in counterparts:
            cp_txns = by_account.get(cp_account, [])
            match = _find_counterpart(txn, cp_txns)
            if match:
                txn.transfer_flag = True
                txn.expense_type = "transfer"
                match.transfer_flag = True
                match.expense_type = "transfer"
                matched_ids.add(txn.transaction_id)
                matched_ids.add(match.transaction_id)
                break
        else:
            # One-legged transfer: only flag if the counterpart account is NOT in the imported data.
            # If both accounts ARE imported and no match was found, it's a normal transaction.
            counterpart_not_imported = not any(cp in by_account for cp in counterparts)
            if counterpart_not_imported:
                txn.transfer_flag = True
                txn.expense_type = "transfer"
                matched_ids.add(txn.transaction_id)

    return transactions


def _find_counterpart(txn: Transaction, candidates: list[Transaction]) -> Optional[Transaction]:
    """Find a candidate with same amount and opposite direction within ±3 days."""
    try:
        txn_date = date.fromisoformat(txn.transaction_date)
        txn_amount = Decimal(txn.amount)
    except (ValueError, Exception):
        return None

    opposite_direction = "credit" if txn.direction == "debit" else "debit"

    for c in candidates:
        if c.direction != opposite_direction:
            continue
        try:
            c_date = date.fromisoformat(c.transaction_date)
            c_amount = Decimal(c.amount)
        except Exception:
            continue

        if abs((c_date - txn_date).days) <= TRANSFER_WINDOW_DAYS and c_amount == txn_amount:
            return c

    return None
