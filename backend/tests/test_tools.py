"""Tests for tool execution endpoints."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import init_db, get_db, DB_PATH


@pytest.fixture(autouse=True)
def setup_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    asyncio.run(init_db())
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


def _insert_test_transactions():
    async def insert():
        db = await get_db()
        try:
            transactions = [
                ("txn-1", "scotiabank-chequing", "bank", "2026-03", "2026-03-15",
                 "STARBUCKS METROTOWN", "Starbucks", "5.75", "CAD", "debit",
                 "Food & Dining", "Coffee", "variable", 0, 0, "auto"),
                ("txn-2", "scotiabank-chequing", "bank", "2026-03", "2026-03-16",
                 "BC HYDRO PAYMENT", "BC Hydro", "85.00", "CAD", "debit",
                 "Utilities", "", "fixed", 0, 0, "auto"),
                ("txn-3", "scotiabank-chequing", "bank", "2026-03", "2026-03-17",
                 "PAYROLL DEPOSIT", "Employer", "3500.00", "CAD", "credit",
                 "Income", "Salary", "income", 0, 0, "auto"),
                ("txn-4", "scotiabank-chequing", "bank", "2026-02", "2026-02-15",
                 "STARBUCKS DOWNTOWN", "Starbucks", "6.25", "CAD", "debit",
                 "Food & Dining", "Coffee", "variable", 0, 0, "auto"),
            ]
            for t in transactions:
                await db.execute("""
                    INSERT INTO transactions (
                        transaction_id, source_account, source_type,
                        statement_month, transaction_date,
                        raw_description, normalized_merchant,
                        amount, currency, direction,
                        category, subcategory, expense_type,
                        recurring_flag, transfer_flag, review_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, t)
            await db.commit()
        finally:
            await db.close()
    asyncio.run(insert())


class TestQueryTransactions:
    def test_filter_by_category(self):
        _insert_test_transactions()

        from routers.tools import _handle_query_transactions
        result = asyncio.run(_handle_query_transactions({"category": "Food & Dining"}))
        assert result["count"] == 2
        assert len(result["transactions"]) == 2

    def test_filter_by_month(self):
        _insert_test_transactions()

        from routers.tools import _handle_query_transactions
        result = asyncio.run(_handle_query_transactions({"month": "2026-03"}))
        assert result["count"] == 3

    def test_filter_by_merchant(self):
        _insert_test_transactions()

        from routers.tools import _handle_query_transactions
        result = asyncio.run(_handle_query_transactions({"merchant": "Starbucks"}))
        assert result["count"] == 2


class TestSpendingBreakdown:
    def test_breakdown_by_month(self):
        _insert_test_transactions()

        from routers.tools import _handle_spending_breakdown
        result = asyncio.run(_handle_spending_breakdown({"month": "2026-03"}))
        assert result["month"] == "2026-03"
        assert len(result["breakdown"]) == 2  # Food & Dining, Utilities
        assert result["total_spending"] == 90.75  # 5.75 + 85.00

    def test_breakdown_excludes_income(self):
        _insert_test_transactions()

        from routers.tools import _handle_spending_breakdown
        result = asyncio.run(_handle_spending_breakdown({"month": "2026-03"}))
        categories = [b["category"] for b in result["breakdown"]]
        assert "Income" not in categories


class TestPipelineStatus:
    def test_status_with_data(self):
        _insert_test_transactions()

        from routers.tools import _handle_pipeline_status
        result = asyncio.run(_handle_pipeline_status({}))
        assert result["has_data"] is True
        assert result["total_transactions"] == 4
        assert "2026-03" in result["available_months"]
        assert "2026-02" in result["available_months"]

    def test_status_empty(self):
        from routers.tools import _handle_pipeline_status
        result = asyncio.run(_handle_pipeline_status({}))
        assert result["has_data"] is False
        assert result["total_transactions"] == 0


class TestUploadTokenBoundary:
    def test_rejects_parent_path(self, tmp_path, monkeypatch):
        from routers import tools as tools_router

        monkeypatch.setattr(tools_router, "UPLOAD_DIR", tmp_path / "uploads")
        result = asyncio.run(tools_router._handle_upload_and_process({
            "file_path": "../outside.csv",
        }))

        assert result == {"error": "Invalid upload token"}
