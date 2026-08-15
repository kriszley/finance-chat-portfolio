"""
Rules engine + LLM fallback categorization.

Pipeline order:
1. Exact match on raw_description → merchant_rules.csv
2. Contains match → merchant_rules.csv
3. Regex pattern match → merchant_rules.csv
4. LLM fallback (Claude) — structured output via tool use
   - confidence >= 0.7 → apply, set review_status=llm
   - confidence < 0.7  → review_needed.csv queue
"""

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.core.schema import Transaction, EXPENSE_TYPES

# Skip re-categorization for already-corrected transactions
SKIP_STATUSES = {"corrected"}


def load_rules(rules_path: str) -> list[dict]:
    with open(rules_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def apply_exact(desc: str, rules: list[dict]) -> Optional[dict]:
    desc_lower = desc.lower()
    for rule in rules:
        if rule.get("match_type", "").lower() == "exact" and rule["pattern"].lower() == desc_lower:
            return rule
    return None


def apply_contains(desc: str, rules: list[dict]) -> Optional[dict]:
    desc_lower = desc.lower()
    for rule in rules:
        if rule.get("match_type", "").lower() == "contains" and rule["pattern"].lower() in desc_lower:
            return rule
    return None


def apply_regex(desc: str, rules: list[dict]) -> Optional[dict]:
    for rule in rules:
        if rule.get("match_type", "").lower() == "regex":
            try:
                if re.search(rule["pattern"], desc, re.IGNORECASE):
                    return rule
            except re.error:
                pass
    return None


def apply_rule(txn: Transaction, rule: dict) -> Transaction:
    txn.category = rule.get("category", "")
    txn.subcategory = rule.get("subcategory", "")
    txn.expense_type = rule.get("expense_type", "")
    txn.normalized_merchant = rule.get("normalized_merchant", txn.normalized_merchant)
    txn.recurring_flag = str(rule.get("recurring", "false")).lower() == "true"
    txn.transfer_flag = str(rule.get("transfer", "false")).lower() == "true"
    if txn.transfer_flag:
        txn.expense_type = "transfer"
    txn.review_status = "auto"
    return txn


def categorize_with_llm(transactions: list[Transaction], rules: list[dict]) -> list[Transaction]:
    """
    Call Claude for transactions that didn't match any rule.
    Uses structured output (tool use) to enforce the output schema.
    """
    cloud_llm_enabled = os.getenv("ENABLE_CLOUD_LLM", "false").lower() in {
        "1", "true", "yes",
    }
    if not cloud_llm_enabled:
        for txn in transactions:
            if txn.review_status == "needs_review":
                txn.notes = "Cloud LLM disabled — manual review required"
        return transactions

    if not os.getenv("ANTHROPIC_API_KEY"):
        for txn in transactions:
            if txn.review_status == "needs_review":
                txn.notes = "ANTHROPIC_API_KEY not configured — manual review required"
        return transactions

    try:
        import anthropic
    except ImportError:
        # anthropic SDK not installed — mark everything as needs_review
        for txn in transactions:
            if txn.review_status == "needs_review":
                txn.notes = "anthropic SDK not installed — manual review required"
        return transactions

    client = anthropic.Anthropic()

    category_list = sorted(set(
        r["category"] for r in rules if r.get("category")
    ))

    categorize_tool = {
        "name": "categorize_transaction",
        "description": "Classify a bank transaction into a category from the provided list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category from the allowed list"},
                "subcategory": {"type": "string", "description": "Optional subcategory"},
                "expense_type": {
                    "type": "string",
                    "enum": list(EXPENSE_TYPES),
                    "description": "Expense classification"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score 0.0-1.0. Use < 0.7 if uncertain."
                }
            },
            "required": ["category", "expense_type", "confidence"]
        }
    }

    for txn in transactions:
        if txn.review_status in SKIP_STATUSES or txn.review_status == "auto":
            continue

        prompt = (
            f"Bank transaction:\n"
            f"  Description: {txn.raw_description}\n"
            f"  Merchant: {txn.normalized_merchant}\n"
            f"  Amount: {txn.amount} {txn.currency}\n"
            f"  Direction: {txn.direction}\n"
            f"  Account type: {txn.source_type}\n\n"
            f"Allowed categories: {', '.join(category_list)}\n\n"
            "Classify this transaction. Set confidence < 0.7 if you are not sure."
        )

        try:
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=256,
                tools=[categorize_tool],
                tool_choice={"type": "tool", "name": "categorize_transaction"},
                messages=[{"role": "user", "content": prompt}]
            )

            tool_use = next(
                (b for b in response.content if b.type == "tool_use"),
                None
            )
            if not tool_use:
                txn.notes = "LLM returned no tool call"
                continue

            result = tool_use.input
            confidence = float(result.get("confidence", 0))

            if confidence >= 0.7:
                txn.category = result.get("category", "")
                txn.subcategory = result.get("subcategory", "")
                txn.expense_type = result.get("expense_type", "")
                txn.review_status = "llm"
                txn.notes = f"LLM confidence: {confidence:.2f}"
            else:
                txn.review_status = "needs_review"
                txn.notes = f"LLM confidence too low: {confidence:.2f} — {result.get('category', '')}"

        except Exception as e:
            txn.notes = f"LLM error: {e}"

    return transactions


def categorize(transactions: list[Transaction], rules_path: str) -> list[Transaction]:
    """
    Full categorization pipeline.
    Returns transactions with review_status set on each.
    """
    rules = load_rules(rules_path)
    uncategorized = []

    for txn in transactions:
        if txn.review_status in SKIP_STATUSES:
            continue
        # Already flagged as transfer — skip
        if txn.transfer_flag:
            txn.review_status = "auto"
            continue

        rule = (
            apply_exact(txn.raw_description, rules)
            or apply_contains(txn.raw_description, rules)
            or apply_regex(txn.raw_description, rules)
        )

        if rule:
            txn = apply_rule(txn, rule)
        else:
            uncategorized.append(txn)

    # LLM fallback for unmatched
    if uncategorized:
        categorize_with_llm(uncategorized, rules)

    return transactions
