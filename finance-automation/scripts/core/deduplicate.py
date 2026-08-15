"""
Hash-based deduplication across all source files.

Dedup strategy:
- Primary key: transaction_id (SHA-256 hash)
- If two transactions share the same ID, the first one seen is kept
- Logs all duplicates to run_log for audit
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import Transaction


def deduplicate(transactions: list[Transaction]) -> tuple[list[Transaction], list[dict]]:
    """
    Remove duplicate transactions by transaction_id.
    Returns (deduplicated_list, duplicate_log).
    """
    seen: dict[str, Transaction] = {}
    duplicates = []

    for txn in transactions:
        if txn.transaction_id in seen:
            duplicates.append({
                "duplicate_id": txn.transaction_id,
                "kept_source": seen[txn.transaction_id].source_file,
                "dropped_source": txn.source_file,
                "date": txn.transaction_date,
                "description": txn.raw_description,
                "amount": txn.amount,
            })
        else:
            seen[txn.transaction_id] = txn

    unique = list(seen.values())
    return unique, duplicates
