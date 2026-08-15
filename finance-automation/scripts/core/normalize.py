"""
Normalize raw parser output into canonical Transaction objects.

Handles:
- Merchant name normalization (strip store numbers, location suffixes)
- statement_month derivation (filename-first, date fallback)
- Decimal amount enforcement
- source_file and transaction_id assignment
"""

import csv
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import Transaction, make_transaction_id

# Patterns to strip from merchant names
_STRIP_PATTERNS = [
    r"\s+#\d+$",                    # Store numbers: "Walmart #1234"
    r"\s+\d{3,}$",                  # Trailing long numbers
    r"\s+(VANCOUVER|BURNABY|SURREY|RICHMOND|VICTORIA|TORONTO|CALGARY|EDMONTON|OTTAWA|MONTREAL)\s*$",
    r"\s+(BC|AB|ON|QC|MB|SK|NS|NB|PE|NL)\s*$",
    r"\s+\d{5}$",                   # Zip codes
    r"^(PURCHASE\s+|POS\s+|DEBIT\s+|CREDIT\s+)",  # Prefix noise
    r"\s+\*\d+$",                   # Trailing reference numbers
]
_STRIP_RE = [re.compile(p, re.IGNORECASE) for p in _STRIP_PATTERNS]


def normalize_merchant(raw: str) -> str:
    """Strip store numbers, location suffixes, and noise prefixes."""
    name = raw.strip()
    for pattern in _STRIP_RE:
        name = pattern.sub("", name)
    return name.strip()


def derive_statement_month(filepath: str, transaction_dates: list[str]) -> str:
    """
    Derive YYYY-MM from filename first (e.g., scotiabank-2025-01.csv → 2025-01).
    Falls back to the most common transaction date month.
    """
    filename = Path(filepath).stem
    # Try to find YYYY-MM or YYYY_MM in filename
    match = re.search(r"(\d{4})[-_](\d{2})", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    if transaction_dates:
        # Use the most common month in the transaction dates
        months = [d[:7] for d in transaction_dates if d and len(d) >= 7]
        if months:
            return max(set(months), key=months.count)

    return ""


def normalize(raw_transactions: list[dict], source_file: str) -> list[Transaction]:
    """
    Convert raw parser dicts into Transaction objects with full canonical fields.
    """
    txns = []
    dates = [r.get("transaction_date", "") for r in raw_transactions]
    statement_month = derive_statement_month(source_file, dates)

    for raw in raw_transactions:
        raw_desc = raw.get("raw_description", "").strip()
        merchant = normalize_merchant(raw_desc)
        amount_raw = raw.get("amount", "0").strip()
        # Enforce Decimal — blow up loudly if parser returned garbage
        amount = str(Decimal(amount_raw))
        direction = raw.get("direction", "debit").lower()
        source_account = raw.get("source_account", "")
        txn_date = raw.get("transaction_date", "")

        txn_id = make_transaction_id(source_account, txn_date, amount, direction, raw_desc)

        txn = Transaction(
            transaction_id=txn_id,
            source_account=source_account,
            source_type=raw.get("source_type", "bank"),
            source_file=source_file,
            source_row_id=raw.get("source_row_id", ""),
            statement_month=statement_month,
            transaction_date=txn_date,
            posted_date=raw.get("posted_date", ""),
            raw_description=raw_desc,
            normalized_merchant=merchant,
            amount=amount,
            currency=raw.get("currency", "CAD"),
            direction=direction,
            review_status="needs_review",
        )
        txns.append(txn)

    return txns


def normalize_from_csv(input_csv: str, source_file: str) -> list[Transaction]:
    """Load raw transactions from an intermediate CSV and normalize."""
    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return normalize(rows, source_file)
