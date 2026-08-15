"""Build the agent system prompt with dynamic data stats from SQLite."""

from db.connection import get_db


async def build_system_prompt() -> str:
    db = await get_db()
    try:
        # Get available months
        cursor = await db.execute(
            "SELECT DISTINCT statement_month FROM transactions ORDER BY statement_month"
        )
        months = [row[0] for row in await cursor.fetchall() if row[0]]

        # Get accounts
        cursor = await db.execute(
            "SELECT DISTINCT source_account FROM transactions ORDER BY source_account"
        )
        accounts = [row[0] for row in await cursor.fetchall() if row[0]]

        # Get total count
        cursor = await db.execute("SELECT COUNT(*) FROM transactions")
        total_count = (await cursor.fetchone())[0]

        # Get categories
        cursor = await db.execute(
            "SELECT DISTINCT category FROM transactions WHERE category != '' ORDER BY category"
        )
        categories = [row[0] for row in await cursor.fetchall()]
    finally:
        await db.close()

    if not months:
        data_section = "No transaction data has been uploaded yet. Ask the user to upload a bank CSV file."
    else:
        data_section = f"""Available data:
- Months: {months}
- Accounts: {accounts}
- Total transactions: {total_count}
- Categories: {categories}"""

    return f"""You are a personal finance assistant. You have access to the user's processed bank transaction data.

{data_section}

Use the query_transactions and get_spending_breakdown tools to answer questions with real data. Never guess amounts, always query first. When a visual would help the user understand the data, use render_chart to show a bar, pie, or line chart inline.

If the user uploads a CSV, use upload_and_process_csv to run the pipeline and report the results.

If the user wants to correct a category, use correct_category to update the transaction and create a rule for future transactions.

Be concise and specific with numbers. Format currency as $X,XXX.XX CAD."""
