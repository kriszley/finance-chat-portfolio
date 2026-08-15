"""Tests for database initialization and WAL mode."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
from db.connection import init_db, get_db, DB_PATH


@pytest.fixture(autouse=True)
def clean_db():
    """Remove test DB before and after each test."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


class TestDatabaseInit:
    def test_init_creates_tables(self):
        asyncio.run(init_db())
        assert DB_PATH.exists()

        async def check():
            db = await get_db()
            try:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in await cursor.fetchall()]
                assert "conversations" in tables
                assert "messages" in tables
                assert "transactions" in tables
                assert "pipeline_runs" in tables
            finally:
                await db.close()

        asyncio.run(check())

    def test_wal_mode_enabled(self):
        asyncio.run(init_db())

        async def check():
            db = await get_db()
            try:
                cursor = await db.execute("PRAGMA journal_mode")
                mode = (await cursor.fetchone())[0]
                assert mode == "wal"
            finally:
                await db.close()

        asyncio.run(check())

    def test_conversation_crud(self):
        asyncio.run(init_db())

        async def check():
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO conversations (id, title) VALUES (?, ?)",
                    ("test-1", "Test Conv"),
                )
                await db.commit()

                cursor = await db.execute(
                    "SELECT id, title FROM conversations WHERE id = ?",
                    ("test-1",),
                )
                row = await cursor.fetchone()
                assert row[0] == "test-1"
                assert row[1] == "Test Conv"
            finally:
                await db.close()

        asyncio.run(check())
