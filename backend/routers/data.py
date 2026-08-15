"""Data query endpoints for transaction status and schema."""

from fastapi import APIRouter

from db.connection import get_db
from db.models import StatusResponse
from agent.tool_definitions import get_all_tool_schemas

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/status", response_model=StatusResponse)
async def get_status():
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

        return StatusResponse(
            has_data=total > 0,
            total_transactions=total,
            available_months=months,
            accounts=accounts,
            categories=categories,
        )
    finally:
        await db.close()


@router.get("/tools/schema")
async def get_tool_schemas():
    """Return all tool definitions for the frontend to use with AI SDK."""
    return {"tools": get_all_tool_schemas()}
