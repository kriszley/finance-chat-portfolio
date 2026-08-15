"""Conversation CRUD endpoints. FastAPI owns all SQLite access."""

import uuid
from fastapi import APIRouter, HTTPException

from db.connection import get_db
from db.models import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations() -> list[ConversationResponse]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [
            ConversationResponse(id=r[0], title=r[1], created_at=r[2], updated_at=r[3])
            for r in rows
        ]
    finally:
        await db.close()


@router.post("", response_model=ConversationResponse)
async def create_conversation(body: ConversationCreate):
    db = await get_db()
    try:
        conv_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO conversations (id, title) VALUES (?, ?)",
            (conv_id, body.title),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        )
        row = await cursor.fetchone()
        return ConversationResponse(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])
    finally:
        await db.close()


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> ConversationResponse:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse(id=row[0], title=row[1], created_at=row[2], updated_at=row[3])
    finally:
        await db.close()


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await db.commit()
        return {"deleted": True}
    finally:
        await db.close()


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str) -> list[MessageResponse]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, conversation_id, role, content, tool_calls, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [
            MessageResponse(
                id=r[0], conversation_id=r[1], role=r[2],
                content=r[3], tool_calls=r[4], created_at=r[5],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def create_message(conversation_id: str, body: MessageCreate):
    db = await get_db()
    try:
        # Verify conversation exists
        cursor = await db.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conversation not found")

        msg_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, tool_calls) VALUES (?, ?, ?, ?, ?)",
            (msg_id, conversation_id, body.role, body.content, body.tool_calls),
        )
        # Update conversation timestamp
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, conversation_id, role, content, tool_calls, created_at FROM messages WHERE id = ?",
            (msg_id,),
        )
        row = await cursor.fetchone()
        return MessageResponse(
            id=row[0], conversation_id=row[1], role=row[2],
            content=row[3], tool_calls=row[4], created_at=row[5],
        )
    finally:
        await db.close()
