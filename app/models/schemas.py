"""
Pydantic schemas for Orchid API requests and responses.
"""

from datetime import datetime
from enum import Enum
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


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    model_tier: ModelTier = ModelTier.DEFAULT
    system_prompt: str | None = None
    include_memory: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    model_used: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


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
    chroma_connected: bool = True
