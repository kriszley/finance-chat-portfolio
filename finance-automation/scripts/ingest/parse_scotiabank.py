"""
Scotiabank CSV parser.

Actual export format (confirmed from real export):
  Filter, Date, Description, Sub-description, Status, Type of Transaction, Amount
  - Date: YYYY-MM-DD
  - Type of Transaction: Debit | Credit
  - Amount: always positive
  - First row may have "Current and last statement period" in Filter column
  - File has UTF-8 BOM

format_variant options:
  default     — standard export (chequing or credit card, same format)
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import RawTransaction


def parse(filepath: str, source_account: str, format_variant: str = "default") -> list[dict]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:  # utf-8-sig strips BOM
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # row 2+ (row 1 = header)
            # Normalize keys
            row = {k.strip(): v.strip() for k, v in row.items()}

            date_str = row.get("Date", "").strip()
            description = row.get("Description", "").strip()
            sub_desc = row.get("Sub-description", "").strip()
            txn_type = row.get("Type of Transaction", "").strip().lower()
            amount_str = row.get("Amount", "0").replace(",", "").strip()

            if not date_str or not description or not amount_str:
                continue

            # Combine description + sub-description if both present
            full_desc = f"{description} {sub_desc}".strip() if sub_desc else description

            direction = "debit" if txn_type == "debit" else "credit"
            amount = amount_str.lstrip("-")  # amount is always positive in Scotiabank export

            rows.append({
                "source_account": source_account,
                "source_type": _infer_source_type(source_account),
                "transaction_date": date_str,  # already YYYY-MM-DD
                "raw_description": full_desc,
                "amount": amount,
                "direction": direction,
                "source_file": "",
                "source_row_id": str(i),
            })

    if not rows:
        raise ValueError(f"No transactions parsed from {filepath} — check file format")

    return rows


def _infer_source_type(account_name: str) -> str:
    name = account_name.lower()
    if "visa" in name or "card" in name or "credit" in name:
        return "card"
    if "questrade" in name or "brokerage" in name:
        return "brokerage"
    return "bank"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_scotiabank.py <csv_path> <account_name> [format_variant]")
        sys.exit(1)
    variant = sys.argv[3] if len(sys.argv) > 3 else "default"
    txns = parse(sys.argv[1], sys.argv[2], variant)
    for t in txns[:5]:
        print(t)
    print(f"... total: {len(txns)} transactions")
