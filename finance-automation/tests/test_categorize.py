"""Tests for the categorization rules engine."""

import csv
import tempfile
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.core.schema import Transaction
from scripts.core.categorize import (
    apply_exact,
    apply_contains,
    apply_regex,
    apply_rule,
    categorize,
    load_rules,
)


def _make_rules_csv(rules_data: list[dict]) -> str:
    """Write rules to a temp CSV and return the path."""
    headers = [
        "pattern", "match_type", "normalized_merchant", "category",
        "subcategory", "expense_type", "recurring", "transfer", "notes",
    ]
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rules_data:
            writer.writerow(row)
    return path


def _make_txn(raw_description: str, amount: str = "10.00",
              direction: str = "debit") -> Transaction:
    return Transaction(
        raw_description=raw_description,
        normalized_merchant=raw_description,
        amount=amount,
        direction=direction,
        review_status="needs_review",
    )


# --- Unit tests for individual match functions ---

class TestApplyContains:
    def test_match(self):
        rules = [{"pattern": "STARBUCKS", "match_type": "contains",
                  "category": "Dining", "subcategory": "Coffee",
                  "expense_type": "variable"}]
        result = apply_contains("STARBUCKS VANCOUVER BC", rules)
        assert result is not None
        assert result["category"] == "Dining"

    def test_case_insensitive(self):
        rules = [{"pattern": "STARBUCKS", "match_type": "contains",
                  "category": "Dining"}]
        result = apply_contains("starbucks store 1234", rules)
        assert result is not None

    def test_no_match(self):
        rules = [{"pattern": "STARBUCKS", "match_type": "contains",
                  "category": "Dining"}]
        result = apply_contains("TIM HORTONS #5678", rules)
        assert result is None

    def test_skips_non_contains_rules(self):
        rules = [{"pattern": "STARBUCKS", "match_type": "exact",
                  "category": "Dining"}]
        result = apply_contains("STARBUCKS VANCOUVER", rules)
        assert result is None


class TestApplyExact:
    def test_match(self):
        rules = [{"pattern": "NETFLIX", "match_type": "exact",
                  "category": "Subscriptions"}]
        result = apply_exact("NETFLIX", rules)
        assert result is not None

    def test_no_match_partial(self):
        rules = [{"pattern": "NETFLIX", "match_type": "exact",
                  "category": "Subscriptions"}]
        result = apply_exact("NETFLIX.COM", rules)
        assert result is None


class TestApplyRegex:
    def test_match(self):
        rules = [{"pattern": r"DEMO\s+MORTGAGE", "match_type": "regex",
                  "category": "Housing", "subcategory": "Mortgage"}]
        result = apply_regex("DEMO MORTGAGE 12345", rules)
        assert result is not None
        assert result["category"] == "Housing"

    def test_invalid_regex_skipped(self):
        rules = [{"pattern": r"[invalid", "match_type": "regex",
                  "category": "Bad"}]
        result = apply_regex("anything", rules)
        assert result is None


# --- Integration tests for full categorize pipeline ---

class TestCategorize:
    def test_rules_categorize_known_merchants(self):
        rules_path = _make_rules_csv([
            {"pattern": "STARBUCKS", "match_type": "contains",
             "normalized_merchant": "Starbucks", "category": "Dining",
             "subcategory": "Coffee", "expense_type": "variable",
             "recurring": "false", "transfer": "false", "notes": ""},
            {"pattern": "BC HYDRO", "match_type": "contains",
             "normalized_merchant": "BC Hydro", "category": "Utilities",
             "subcategory": "", "expense_type": "fixed",
             "recurring": "true", "transfer": "false", "notes": ""},
        ])
        try:
            txns = [
                _make_txn("STARBUCKS METROTOWN"),
                _make_txn("BC HYDRO PAYMENT", "85.00"),
                _make_txn("UNKNOWN MERCHANT XYZ"),
            ]
            # Categorize without LLM (no API key set)
            old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                result = categorize(txns, rules_path)
            finally:
                if old_key:
                    os.environ["ANTHROPIC_API_KEY"] = old_key

            assert result[0].category == "Dining"
            assert result[0].review_status == "auto"
            assert result[1].category == "Utilities"
            assert result[1].expense_type == "fixed"
            assert result[1].recurring_flag is True
            assert result[2].review_status == "needs_review"
            assert result[2].notes == "Cloud LLM disabled — manual review required"
        finally:
            os.unlink(rules_path)

    def test_transfer_flag_sets_expense_type(self):
        rules_path = _make_rules_csv([
            {"pattern": "SCOTIA VISA", "match_type": "contains",
             "normalized_merchant": "Scotia Visa Payment",
             "category": "Transfers", "subcategory": "Credit Card",
             "expense_type": "transfer", "recurring": "true",
             "transfer": "true", "notes": ""},
        ])
        try:
            txns = [_make_txn("SCOTIA VISA PAYMENT")]
            old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                result = categorize(txns, rules_path)
            finally:
                if old_key:
                    os.environ["ANTHROPIC_API_KEY"] = old_key

            assert result[0].transfer_flag is True
            assert result[0].expense_type == "transfer"
        finally:
            os.unlink(rules_path)

    def test_corrected_status_skipped(self):
        rules_path = _make_rules_csv([
            {"pattern": "STARBUCKS", "match_type": "contains",
             "normalized_merchant": "Starbucks", "category": "Dining",
             "subcategory": "", "expense_type": "variable",
             "recurring": "false", "transfer": "false", "notes": ""},
        ])
        try:
            txn = _make_txn("STARBUCKS")
            txn.review_status = "corrected"
            txn.category = "Entertainment"
            result = categorize([txn], rules_path)
            # Should NOT overwrite the corrected category
            assert result[0].category == "Entertainment"
            assert result[0].review_status == "corrected"
        finally:
            os.unlink(rules_path)


class TestApplyRule:
    def test_sets_all_fields(self):
        txn = _make_txn("TEST")
        rule = {
            "category": "Groceries",
            "subcategory": "Korean Grocery",
            "expense_type": "variable",
            "normalized_merchant": "H Mart",
            "recurring": "false",
            "transfer": "false",
        }
        result = apply_rule(txn, rule)
        assert result.category == "Groceries"
        assert result.subcategory == "Korean Grocery"
        assert result.expense_type == "variable"
        assert result.normalized_merchant == "H Mart"
        assert result.review_status == "auto"
        assert result.recurring_flag is False
        assert result.transfer_flag is False
