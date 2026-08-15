"""SQLite database connection and table initialization via aiosqlite."""

import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "finance_chat.db"


async def get_db() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Conversation',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tool_calls TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                source_account TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_file TEXT NOT NULL DEFAULT '',
                source_row_id TEXT NOT NULL DEFAULT '',
                statement_month TEXT NOT NULL DEFAULT '',
                transaction_date TEXT NOT NULL DEFAULT '',
                posted_date TEXT NOT NULL DEFAULT '',
                raw_description TEXT NOT NULL DEFAULT '',
                normalized_merchant TEXT NOT NULL DEFAULT '',
                amount TEXT NOT NULL DEFAULT '0',
                currency TEXT NOT NULL DEFAULT 'CAD',
                direction TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                subcategory TEXT NOT NULL DEFAULT '',
                expense_type TEXT NOT NULL DEFAULT '',
                split_tag TEXT NOT NULL DEFAULT '',
                recurring_flag INTEGER NOT NULL DEFAULT 0,
                transfer_flag INTEGER NOT NULL DEFAULT 0,
                review_status TEXT NOT NULL DEFAULT 'needs_review',
                notes TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                input_file TEXT NOT NULL DEFAULT '',
                stats_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_month
                ON transactions(statement_month);
            CREATE INDEX IF NOT EXISTS idx_transactions_category
                ON transactions(category);
        """)
        await db.commit()
    finally:
        await db.close()
