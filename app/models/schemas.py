"""
Pydantic schemas for Cipher API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# --- Enums ---

class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ModelTier(str, Enum):
    REASONING = "reasoning"
    FAST = "fast"
    LOCAL = "local"
    CODE = "code"
    DEFAULT = "default"
    AUTO = "auto"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Chat ---

class ChatMessage(BaseModel):
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    model_used: str | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    model_tier: ModelTier = ModelTier.AUTO
    system_prompt: str | None = None
    include_memory: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False
    images: list[str] = []  # base64-encoded images from iOS client


class RecommendedAgentInfo(BaseModel):
    agent_name: str = ""
    display_name: str = ""
    reason: str = ""
    confidence: float = 0.0
    suggested_instruction: str = ""


class ImageAttachment(BaseModel):
    url: str = ""
    mime_type: str = "image/png"
    analysis: str | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    model_used: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    recommended_agent: Optional[RecommendedAgentInfo] = None
    images: list[ImageAttachment] = []  # Images in response (generated or analyzed)
    confidence_score: float | None = None  # 0-1 reliability score
    validation_warnings: list[str] | None = None  # Flags for unverified claims


# --- Conversations ---

class Conversation(BaseModel):
    id: str
    title: str | None = None
    messages: list[ChatMessage] = []
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    model_tier: ModelTier = ModelTier.DEFAULT


class ConversationSummary(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: str | None = None


# --- Memory ---

class MemoryEntry(BaseModel):
    id: str
    content: str
    metadata: dict = {}
    relevance_score: float = 0.0
    created_at: datetime


# --- Models ---

class ModelInfo(BaseModel):
    tier: ModelTier
    model_id: str
    provider: str
    available: bool = True
    description: str = ""


# --- Auth ---

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime
    is_active: bool = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- System ---

class HealthCheck(BaseModel):
    status: str = "healthy"
    version: str
    uptime_seconds: float
    models_available: list[str] = []
    database_connected: bool = True
    memory_connected: bool = True
