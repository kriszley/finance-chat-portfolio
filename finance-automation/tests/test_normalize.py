"""Tests for merchant normalization and month derivation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.core.normalize import normalize_merchant, derive_statement_month


class TestNormalizeMerchant:
    def test_strips_store_number(self):
        assert normalize_merchant("WALMART #1234") == "WALMART"

    def test_strips_city(self):
        assert normalize_merchant("STARBUCKS VANCOUVER") == "STARBUCKS"

    def test_strips_province(self):
        assert normalize_merchant("SAFEWAY BC") == "SAFEWAY"

    def test_strips_purchase_prefix(self):
        assert normalize_merchant("PURCHASE STARBUCKS") == "STARBUCKS"

    def test_strips_pos_prefix(self):
        assert normalize_merchant("POS COSTCO") == "COSTCO"

    def test_preserves_short_names(self):
        assert normalize_merchant("T&T") == "T&T"

    def test_strips_trailing_reference(self):
        assert normalize_merchant("NETFLIX *12345") == "NETFLIX"

    def test_multiple_patterns(self):
        # Should strip both prefix and city
        assert normalize_merchant("PURCHASE STARBUCKS VANCOUVER") == "STARBUCKS"


class TestDeriveStatementMonth:
    def test_from_filename_dash(self):
        result = derive_statement_month("scotiabank-2026-03.csv", [])
        assert result == "2026-03"

    def test_from_filename_underscore(self):
        result = derive_statement_month("bmo_2026_01.csv", [])
        assert result == "2026-01"

    def test_fallback_to_dates(self):
        dates = ["2026-03-01", "2026-03-15", "2026-03-20", "2026-02-28"]
        result = derive_statement_month("bmo-mar2026.csv", dates)
        assert result == "2026-03"

    def test_empty_dates(self):
        result = derive_statement_month("random.csv", [])
        assert result == ""
