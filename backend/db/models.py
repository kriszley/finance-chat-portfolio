"""Pydantic models for API request/response types."""

from pydantic import BaseModel
from typing import Optional


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageCreate(BaseModel):
    role: str
    content: str
    tool_calls: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tool_calls: Optional[str] = None
    created_at: str


class UploadResponse(BaseModel):
    filename: str
    file_path: str
    detected_bank: Optional[str] = None


class ToolRequest(BaseModel):
    arguments: dict


class ToolResponse(BaseModel):
    result: dict
    error: Optional[str] = None


class StatusResponse(BaseModel):
    has_data: bool
    total_transactions: int
    available_months: list[str]
    accounts: list[str]
    categories: list[str]
