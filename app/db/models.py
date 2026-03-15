"""
SQLAlchemy ORM models for Cipher.
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


# ---------------------------------------------------------------------------
# Projects & Credentials — Cipher's filing system for user projects
# ---------------------------------------------------------------------------

class ProjectRecord(Base):
    """A user project — education platform, app, website, etc."""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), default="folder.fill")
    color = Column(String(20), default="blue")
    platform = Column(String(50), default="other")  # ios, web, backend, fullstack, mobile, other
    repo_url = Column(String(500), nullable=True)
    deploy_url = Column(String(500), nullable=True)
    railway_project_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    services = relationship("ProjectServiceRecord", back_populates="project", cascade="all, delete-orphan")
    credentials = relationship("ServiceCredentialRecord", back_populates="project")


class ProjectServiceRecord(Base):
    """A service linked to a project (e.g., OpenAI, Railway, ElevenLabs)."""
    __tablename__ = "project_services"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    service_type = Column(String(50), nullable=False)  # openai, railway, elevenlabs, etc.
    credential_id = Column(String(36), ForeignKey("service_credentials.id"), nullable=True)
    config = Column(Text, nullable=True)  # JSON string for service-specific config
    created_at = Column(DateTime, default=utcnow)

    project = relationship("ProjectRecord", back_populates="services")
    credential = relationship("ServiceCredentialRecord")


class ServiceCredentialRecord(Base):
    """Encrypted API keys and tokens for external services."""
    __tablename__ = "service_credentials"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    service_type = Column(String(50), nullable=False)
    token_value = Column(Text, nullable=False)  # Encrypted via app.core.encryption
    additional_fields = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, default=utcnow)
    last_used_at = Column(DateTime, nullable=True)

    project = relationship("ProjectRecord", back_populates="credentials")


# ---------------------------------------------------------------------------
# Error Tracking — Cipher learns from every failure
# ---------------------------------------------------------------------------

class ErrorLog(Base):
    """Every error Cipher encounters, with diagnosis and fix history.
    This is the learning backbone of the self-healing loop."""
    __tablename__ = "error_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    error_type = Column(String(100), nullable=False, index=True)  # tool_failure, llm_error, agent_crash, import_error, api_timeout
    source = Column(String(200), nullable=False)  # file:line or tool_name or agent_name
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    context = Column(Text, nullable=True)  # JSON: what was happening when it failed
    diagnosis = Column(Text, nullable=True)  # What self-diagnostic found
    fix_applied = Column(Text, nullable=True)  # What fix was attempted
    fix_succeeded = Column(Boolean, nullable=True)  # Did the fix work?
    recurrence_count = Column(Integer, default=1)  # How many times this exact error has occurred
    last_seen = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)


class SelfFixLog(Base):
    """Record of every self-modification Cipher makes."""
    __tablename__ = "self_fix_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    error_log_id = Column(String(36), ForeignKey("error_logs.id"), nullable=True)
    file_path = Column(String(500), nullable=False)
    action = Column(String(20), nullable=False)  # patch, write, rollback
    old_content_hash = Column(String(64), nullable=True)
    new_content_hash = Column(String(64), nullable=True)
    description = Column(Text, nullable=False)
    success = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)  # Did post-fix test pass?
    rolled_back = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Telemetry — Cipher tracks every agent/tool invocation for learning
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Memory — Cipher's persistent knowledge across deploys
# ---------------------------------------------------------------------------

class MemoryEntry(Base):
    """Persistent memory storage. Replaces ephemeral JSON/in-memory store.
    Every conversation exchange, learned insight, playbook, and operational
    knowledge lives here — survives Railway deploys."""
    __tablename__ = "memory_entries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    collection_name = Column(String(100), nullable=False, default="cipher_memory", index=True)
    content = Column(Text, nullable=False)
    # Store metadata as JSON text — flexible for any key-value pairs
    metadata_json = Column(Text, nullable=True)  # JSON string
    source = Column(String(50), nullable=True, index=True)  # conversation, seed, agent, user
    memory_type = Column(String(50), nullable=True, index=True)  # exchange, playbook, brand_profile, operating_principle, etc.
    priority = Column(String(20), nullable=True)  # critical, high, normal, low
    created_at = Column(DateTime, default=utcnow, index=True)


class TelemetryLog(Base):
    """Every agent/tool invocation gets logged here for performance analysis.
    Cipher can query this to answer: which agents fail most? What's slow?
    What does Mark use most? This survives deploys (unlike /tmp)."""
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_or_tool = Column(String(100), nullable=False, index=True)  # agent name or tool name
    operation = Column(String(100), nullable=True)  # capability/operation within the agent
    success = Column(Boolean, default=True)
    latency_ms = Column(Float, default=0.0)
    error_message = Column(String(500), nullable=True)
    query_snippet = Column(String(300), nullable=True)  # First 300 chars of user message
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow, index=True)
