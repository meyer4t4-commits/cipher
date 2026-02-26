"""
SQLAlchemy ORM models for Orchid.
These define the database schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    conversations = relationship("ConversationRecord", back_populates="user")


class ConversationRecord(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=True)
    model_tier = Column(String(20), default="default")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "MessageRecord", back_populates="conversation", order_by="MessageRecord.created_at"
    )


class MessageRecord(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("ConversationRecord", back_populates="messages")


class SystemPrompt(Base):
    """Stored system prompts / personas (like Zig's personality)."""
    __tablename__ = "system_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class UsageLog(Base):
    """Track API usage and costs across all providers."""
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    task_type = Column(String(50), nullable=True)  # reasoning, fast, code, etc.
    created_at = Column(DateTime, default=utcnow)


class TaskRecord(Base):
    """Background task tracking for Celery jobs."""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_type = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    input_data = Column(Text, nullable=True)
    output_data = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
