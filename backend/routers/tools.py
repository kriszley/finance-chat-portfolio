"""Tool execution endpoints. POST /api/tools/{tool_name} dispatches to handlers."""

import csv
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException

from db.connection import get_db
from db.models import ToolRequest, ToolResponse

# Pipeline imports (via PYTHONPATH set in main.py)
from scripts.core.schema import Transaction
from scripts.core.normalize import normalize
from scripts.core.deduplicate import deduplicate
from scripts.core.detect_transfers import detect_transfers
from scripts.core.categorize import categorize
from scripts.config_paths import (
    accounts_config_path,
    ensure_writable_merchant_rules,
    merchant_rules_path,
    transfer_rules_path,
)

import yaml

router = APIRouter(prefix="/api/tools", tags=["tools"])

# Paths to finance-automation (Docker: /finance-automation, Local: sibling dir)
_fa_docker = Path("/finance-automation")
_fa_local = Path(__file__).parent.parent.parent / "finance-automation"
FINANCE_ROOT = _fa_docker if _fa_docker.exists() else _fa_local
UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"


def _load_accounts():
    with open(accounts_config_path(), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {a["name"]: a for a in cfg.get("accounts", [])}


def _match_account(filename: str, accounts: dict) -> Optional[str]:
    """Match a CSV filename to an account (replicates run.py logic)."""
    filename_lower = filename.lower()
    for account_name in accounts:
        if account_name.lower().replace("-", "").replace("_", "") in \
                filename_lower.replace("-", "").replace("_", ""):
            return account_name
    for account_name, account in accounts.items():
        institution = account.get("institution", "").lower()
        if institution and institution in filename_lower:
            return account_name
    return None


@router.post("/{tool_name}", response_model=ToolResponse)
async def execute_tool(tool_name: str, request: ToolRequest):
    handlers = {
        "query_transactions": _handle_query_transactions,
        "get_spending_breakdown": _handle_spending_breakdown,
        "get_monthly_comparison": _handle_monthly_comparison,
        "upload_and_process_csv": _handle_upload_and_process,
        "get_pipeline_status": _handle_pipeline_status,
        "correct_category": _handle_correct_category,
    }
    handler = handlers.get(tool_name)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    try:
        result = await handler(request.arguments)
        return ToolResponse(result=result)
    except Exception as e:
        return ToolResponse(result={}, error=str(e))


async def _handle_query_transactions(args: dict) -> dict:
    db = await get_db()
    try:
        conditions = []
        params = []

        if args.get("category"):
            conditions.append("category = ?")
            params.append(args["category"])
        if args.get("subcategory"):
            conditions.append("subcategory = ?")
            params.append(args["subcategory"])
        if args.get("month"):
            conditions.append("statement_month = ?")
            params.append(args["month"])
        if args.get("merchant"):
            conditions.append("normalized_merchant LIKE ?")
            params.append(f"%{args['merchant']}%")
        if args.get("min_amount") is not None:
            conditions.append("CAST(amount AS REAL) >= ?")
            params.append(float(args["min_amount"]))
        if args.get("max_amount") is not None:
            conditions.append("CAST(amount AS REAL) <= ?")
            params.append(float(args["max_amount"]))
        if args.get("direction"):
            conditions.append("direction = ?")
            params.append(args["direction"])

        where = " AND ".join(conditions) if conditions else "1=1"
        limit = min(args.get("limit", 50), 200)

        query = f"SELECT * FROM transactions WHERE {where} ORDER BY transaction_date DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        transactions = [dict(zip(columns, row)) for row in rows]

        # Summary stats
        sum_query = f"SELECT COUNT(*) as count, SUM(CAST(amount AS REAL)) as total FROM transactions WHERE {where}"
        cursor = await db.execute(sum_query, params[:-1])  # no LIMIT
        stats = dict(zip(["count", "total"], await cursor.fetchone()))

        return {
            "transactions": transactions,
            "count": stats["count"],
            "total_amount": round(stats["total"] or 0, 2),
        }
    finally:
        await db.close()


async def _handle_spending_breakdown(args: dict) -> dict:
    db = await get_db()
    try:
        month = args.get("month")
        if not month:
            cursor = await db.execute(
                "SELECT MAX(statement_month) FROM transactions"
            )
            row = await cursor.fetchone()
            month = row[0] if row and row[0] else None
            if not month:
                return {"error": "No data available", "breakdown": []}

        cursor = await db.execute("""
            SELECT category, SUM(CAST(amount AS REAL)) as total, COUNT(*) as count
            FROM transactions
            WHERE statement_month = ? AND direction = 'debit' AND transfer_flag = 0
            GROUP BY category
            ORDER BY total DESC
        """, [month])
        rows = await cursor.fetchall()

        grand_total = sum(row[1] for row in rows) if rows else 0
        breakdown = []
        for row in rows:
            category, total, count = row
            breakdown.append({
                "category": category or "Uncategorized",
                "amount": round(total, 2),
                "count": count,
                "percentage": round((total / grand_total * 100) if grand_total else 0, 1),
            })

        return {
            "month": month,
            "total_spending": round(grand_total, 2),
            "breakdown": breakdown,
        }
    finally:
        await db.close()


async def _handle_monthly_comparison(args: dict) -> dict:
    months = args.get("months", [])
    if len(months) < 2:
        return {"error": "Need at least 2 months to compare"}

    db = await get_db()
    try:
        placeholders = ",".join("?" for _ in months)
        cursor = await db.execute(f"""
            SELECT statement_month, category, SUM(CAST(amount AS REAL)) as total
            FROM transactions
            WHERE statement_month IN ({placeholders}) AND direction = 'debit' AND transfer_flag = 0
            GROUP BY statement_month, category
            ORDER BY statement_month, total DESC
        """, months)
        rows = await cursor.fetchall()

        by_month = {}
        for month_val, category, total in rows:
            if month_val not in by_month:
                by_month[month_val] = {}
            by_month[month_val][category or "Uncategorized"] = round(total, 2)

        all_categories = sorted(set(
            cat for month_data in by_month.values() for cat in month_data
        ))

        comparison = []
        for cat in all_categories:
            row_data = {"category": cat}
            for m in months:
                row_data[m] = by_month.get(m, {}).get(cat, 0)
            if len(months) == 2:
                row_data["delta"] = round(row_data.get(months[1], 0) - row_data.get(months[0], 0), 2)
            comparison.append(row_data)

        return {"months": months, "comparison": comparison}
    finally:
        await db.close()


async def _handle_upload_and_process(args: dict) -> dict:
    import importlib

    upload_token = args.get("file_path", "")
    token_path = Path(upload_token)
    if (
        not upload_token
        or token_path.name != upload_token
        or token_path.suffix.lower() != ".csv"
    ):
        return {"error": "Invalid upload token"}

    upload_root = UPLOAD_DIR.resolve()
    file_path = (upload_root / upload_token).resolve()
    if file_path.parent != upload_root or not file_path.is_file():
        return {"error": "Uploaded CSV was not found"}

    filename = file_path.name
    accounts = _load_accounts()
    account_name = _match_account(filename, accounts)

    if not account_name:
        supported = [a.get("institution", "") for a in accounts.values()
                     if a.get("institution") in ("scotiabank", "bmo")]
        return {
            "error": f"Could not match '{filename}' to any account. Supported banks: {', '.join(set(supported))}"
        }

    account = accounts[account_name]
    institution = account.get("institution", "")
    format_variant = account.get("format_variant", "default")

    # Dynamic parser import
    parser_map = {
        "scotiabank": "scripts.ingest.parse_scotiabank",
        "bmo": "scripts.ingest.parse_bmo",
    }
    module_name = parser_map.get(institution.lower())
    if not module_name:
        return {"error": f"No parser for institution: {institution}. Supported: Scotiabank, BMO"}

    parser = importlib.import_module(module_name)

    # Run pipeline
    try:
        raw_txns = parser.parse(str(file_path), account_name, format_variant)
        for r in raw_txns:
            r["source_file"] = str(file_path)

        transactions = normalize(raw_txns, str(file_path))

        # Detect target month
        dates = [t.transaction_date for t in transactions if t.transaction_date]
        target_month = max(dates)[:7] if dates else ""

        # Filter to target month
        transactions = [t for t in transactions if t.transaction_date.startswith(target_month)]

        transactions, dupes = deduplicate(transactions)

        transfer_rules = transfer_rules_path()
        if transfer_rules.exists():
            transactions = detect_transfers(transactions, str(transfer_rules))

        transactions = categorize(transactions, str(merchant_rules_path()))

        # Insert into SQLite
        db = await get_db()
        try:
            inserted = 0
            for txn in transactions:
                try:
                    await db.execute("""
                        INSERT OR REPLACE INTO transactions (
                            transaction_id, source_account, source_type, source_file,
                            source_row_id, statement_month, transaction_date, posted_date,
                            raw_description, normalized_merchant, amount, currency,
                            direction, category, subcategory, expense_type, split_tag,
                            recurring_flag, transfer_flag, review_status, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        txn.transaction_id, txn.source_account, txn.source_type,
                        txn.source_file, txn.source_row_id, txn.statement_month,
                        txn.transaction_date, txn.posted_date, txn.raw_description,
                        txn.normalized_merchant, txn.amount, txn.currency,
                        txn.direction, txn.category, txn.subcategory, txn.expense_type,
                        txn.split_tag, int(txn.recurring_flag), int(txn.transfer_flag),
                        txn.review_status, txn.notes,
                    ))
                    inserted += 1
                except Exception:
                    pass

            # Log pipeline run
            run_id = str(uuid.uuid4())
            auto = sum(1 for t in transactions if t.review_status == "auto")
            llm = sum(1 for t in transactions if t.review_status == "llm")
            needs_review = sum(1 for t in transactions if t.review_status == "needs_review")
            transfer_count = sum(1 for t in transactions if t.transfer_flag)

            stats = {
                "target_month": target_month,
                "total_transactions": len(transactions),
                "duplicates_removed": len(dupes),
                "transfers_detected": transfer_count,
                "auto_categorized": auto,
                "llm_categorized": llm,
                "needs_review": needs_review,
                "institution": institution,
                "account": account_name,
            }

            await db.execute(
                "INSERT INTO pipeline_runs (id, input_file, stats_json) VALUES (?, ?, ?)",
                (run_id, filename, json.dumps(stats)),
            )
            await db.commit()
        finally:
            await db.close()

        return stats

    except Exception as e:
        return {"error": f"Pipeline failed: {str(e)}"}


async def _handle_pipeline_status(args: dict) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM transactions")
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT DISTINCT statement_month FROM transactions ORDER BY statement_month"
        )
        months = [row[0] for row in await cursor.fetchall() if row[0]]

        cursor = await db.execute(
            "SELECT DISTINCT source_account FROM transactions ORDER BY source_account"
        )
        accounts = [row[0] for row in await cursor.fetchall() if row[0]]

        cursor = await db.execute(
            "SELECT DISTINCT category FROM transactions WHERE category != '' ORDER BY category"
        )
        categories = [row[0] for row in await cursor.fetchall()]

        return {
            "has_data": total > 0,
            "total_transactions": total,
            "available_months": months,
            "accounts": accounts,
            "categories": categories,
        }
    finally:
        await db.close()


async def _handle_correct_category(args: dict) -> dict:
    txn_id = args.get("transaction_id", "")
    category = args.get("category", "")
    subcategory = args.get("subcategory", "")
    expense_type = args.get("expense_type", "")

    if not txn_id or not category or not expense_type:
        return {"error": "transaction_id, category, and expense_type are required"}

    db = await get_db()
    try:
        # Get current transaction
        cursor = await db.execute(
            "SELECT normalized_merchant, raw_description FROM transactions WHERE transaction_id = ?",
            [txn_id],
        )
        row = await cursor.fetchone()
        if not row:
            return {"error": f"Transaction {txn_id} not found"}

        merchant = row[0] or row[1]

        # Update transaction
        await db.execute("""
            UPDATE transactions
            SET category = ?, subcategory = ?, expense_type = ?, review_status = 'corrected'
            WHERE transaction_id = ?
        """, [category, subcategory, expense_type, txn_id])
        await db.commit()

        # Append rule to merchant_rules.csv
        if merchant:
            rules_file = ensure_writable_merchant_rules()
            with open(rules_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    merchant,       # pattern
                    "contains",     # match_type
                    merchant,       # normalized_merchant
                    category,
                    subcategory,
                    expense_type,
                    "false",        # recurring
                    "false",        # transfer
                    "Added via chat correction",
                ])

        return {
            "updated": True,
            "transaction_id": txn_id,
            "new_category": category,
            "rule_added_for": merchant,
        }
    finally:
        await db.close()
