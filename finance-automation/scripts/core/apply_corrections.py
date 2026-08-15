"""
Read review_needed.csv corrections, promote to merchant_rules.csv, update transactions_clean.csv.

Correction surface: review_needed.csv ONLY. Never edit Sheets Review_Queue tab directly.

Correction columns in review_needed.csv:
  corrected_category, corrected_subcategory, corrected_expense_type

Rows with all three blank = accept as-is (no change).
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CORRECTION_COLS = ["corrected_category", "corrected_subcategory", "corrected_expense_type"]


def apply_corrections(review_csv: str, transactions_csv: str, rules_csv: str) -> dict:
    """
    Process corrections from review_needed.csv.
    Returns stats: {corrections_applied, rules_added, warnings}
    """
    # Load review file
    review_path = Path(review_csv)
    if not review_path.exists():
        return {"corrections_applied": 0, "rules_added": 0, "warnings": []}

    with open(review_path, newline="", encoding="utf-8") as f:
        reviews = list(csv.DictReader(f))

    # Validate correction columns exist
    if reviews and not any(c in reviews[0] for c in CORRECTION_COLS):
        raise ValueError(
            f"review_needed.csv is missing correction columns: {CORRECTION_COLS}. "
            "Do not modify the CSV headers."
        )

    # Extract rows with at least one correction filled
    corrections = [
        r for r in reviews
        if any(r.get(c, "").strip() for c in CORRECTION_COLS)
    ]

    if not corrections:
        return {"corrections_applied": 0, "rules_added": 0, "warnings": []}

    # Build correction map: transaction_id → correction
    correction_map: dict[str, dict] = {}
    # Also collect merchant-level corrections: normalized_merchant → correction
    merchant_corrections: dict[str, list[dict]] = {}

    for row in corrections:
        tid = row.get("transaction_id", "").strip()
        merchant = row.get("normalized_merchant", "").strip()
        correction = {
            "category": row.get("corrected_category", "").strip(),
            "subcategory": row.get("corrected_subcategory", "").strip(),
            "expense_type": row.get("corrected_expense_type", "").strip(),
        }
        if tid:
            correction_map[tid] = correction
        if merchant:
            merchant_corrections.setdefault(merchant, []).append(correction)

    stats = {"corrections_applied": 0, "rules_added": 0, "warnings": []}

    # Update transactions_clean.csv in-place
    txn_path = Path(transactions_csv)
    if txn_path.exists():
        with open(txn_path, newline="", encoding="utf-8") as f:
            txns = list(csv.DictReader(f))
            headers = txns[0].keys() if txns else []

        for txn in txns:
            tid = txn.get("transaction_id", "")
            if tid in correction_map:
                c = correction_map[tid]
                if c["category"]:
                    txn["category"] = c["category"]
                if c["subcategory"]:
                    txn["subcategory"] = c["subcategory"]
                if c["expense_type"]:
                    txn["expense_type"] = c["expense_type"]
                txn["review_status"] = "corrected"
                stats["corrections_applied"] += 1

        with open(txn_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(txns[0].keys()) if txns else [])
            writer.writeheader()
            writer.writerows(txns)

    # Promote to merchant_rules.csv
    rules_path = Path(rules_csv)
    existing_rules: list[dict] = []
    if rules_path.exists():
        with open(rules_path, newline="", encoding="utf-8") as f:
            existing_rules = list(csv.DictReader(f))

    existing_patterns = {r["pattern"].lower() for r in existing_rules}
    new_rules = []

    for merchant, corrections_list in merchant_corrections.items():
        if not merchant:
            continue
        # Detect conflicting corrections for same merchant
        categories = [c["category"] for c in corrections_list if c["category"]]
        if len(set(categories)) > 1:
            # Conflict: use most recent (last in list), log warning
            stats["warnings"].append(
                f"Conflicting corrections for '{merchant}': {categories} — using last: {categories[-1]}"
            )

        # Use the last correction for this merchant
        last = corrections_list[-1]
        if merchant.lower() not in existing_patterns and last.get("category"):
            new_rules.append({
                "pattern": merchant,
                "match_type": "exact",
                "normalized_merchant": merchant,
                "category": last["category"],
                "subcategory": last.get("subcategory", ""),
                "expense_type": last.get("expense_type", "variable"),
                "recurring": "false",
                "transfer": "false",
                "notes": "promoted from correction",
            })
            stats["rules_added"] += 1

    if new_rules:
        fieldnames = ["pattern", "match_type", "normalized_merchant", "category",
                      "subcategory", "expense_type", "recurring", "transfer", "notes"]
        with open(rules_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerows(new_rules)

    return stats
