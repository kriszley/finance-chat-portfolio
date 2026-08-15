"""
BMO CSV parser.

Actual export format (confirmed from real export):
  Row 1: metadata line  "Following data is valid as of YYYYMMDDHHMMSS (...)"
  Row 2: blank
  Row 3: blank
  Row 4: header — First Bank Card, Transaction Type, Date Posted, Transaction Amount, Description
  Row 5+: data

  - Date Posted: YYYYMMDD (no separators)
  - Transaction Type: DEBIT | CREDIT
  - Transaction Amount: negative for debits, positive for credits
  - Description: trailing whitespace common — strip it
  - First Bank Card: masked card/account number (used for audit, not account matching)

format_variant options:
  default     — standard BMO chequing/card export (above format)
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import RawTransaction

# Number of rows to skip before the real header row
_HEADER_SKIP = 3


def parse(filepath: str, source_account: str, format_variant: str = "default") -> list[dict]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        # Skip metadata rows
        for _ in range(_HEADER_SKIP):
            f.readline()

        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=_HEADER_SKIP + 2):
            row = {k.strip(): v.strip() for k, v in row.items()}

            date_raw = row.get("Date Posted", "").strip()
            txn_type = row.get("Transaction Type", "").strip().upper()
            amount_raw = row.get("Transaction Amount", "0").strip()
            description = row.get("Description", "").strip()

            if not date_raw or not description:
                continue

            # Parse YYYYMMDD → YYYY-MM-DD
            date_str = _parse_date(date_raw)
            if not date_str:
                continue

            # Amount is negative for debits in BMO export
            try:
                amount_val = float(amount_raw)
            except ValueError:
                continue

            direction = "debit" if txn_type == "DEBIT" or amount_val < 0 else "credit"
            amount = str(abs(amount_val))

            rows.append({
                "source_account": source_account,
                "source_type": _infer_source_type(source_account),
                "transaction_date": date_str,
                "raw_description": description,
                "amount": amount,
                "direction": direction,
                "source_file": "",
                "source_row_id": str(i),
            })

    if not rows:
        raise ValueError(f"No transactions parsed from {filepath} — check file format")

    return rows


def _parse_date(raw: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    # Fallback: try standard formats
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _infer_source_type(account_name: str) -> str:
    name = account_name.lower()
    if "visa" in name or "card" in name or "credit" in name or "mastercard" in name:
        return "card"
    return "bank"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_bmo.py <csv_path> <account_name> [format_variant]")
        sys.exit(1)
    variant = sys.argv[3] if len(sys.argv) > 3 else "default"
    txns = parse(sys.argv[1], sys.argv[2], variant)
    for t in txns[:5]:
        print(t)
    print(f"... total: {len(txns)} transactions")
