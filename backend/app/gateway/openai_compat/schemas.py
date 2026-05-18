"""OpenAI-compatible request and response schemas.

Defines Pydantic models that match the OpenAI /v1/chat/completions
API format, with DeerFlow-specific extensions at the top level.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request with DeerFlow extensions."""

    # --- OpenAI standard fields ---
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    user: str | None = None

    # --- DeerFlow extension fields (top-level, no conflict) ---
    thread_id: str | None = None
    thinking_enabled: bool | None = None
    reasoning_effort: str | None = None
    agent_name: str | None = None
    subagent_enabled: bool | None = None
    max_concurrent_subagents: int | None = None
    skills: list[str] | None = None
    sandbox_enabled: bool | None = None
    is_plan_mode: bool | None = None


# ---------------------------------------------------------------------------
# Response models (non-streaming)
# ---------------------------------------------------------------------------


class ChatCompletionMessage(BaseModel):
    """A message in the completion response."""

    role: Literal["assistant"] = "assistant"
    content: str | None = None


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str | None = "stop"


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo | None = None


# ---------------------------------------------------------------------------
# Streaming response models
# ---------------------------------------------------------------------------


class ChatCompletionChunkDelta(BaseModel):
    """Delta content in a streaming chunk."""

    role: str | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """A single choice in a streaming chunk."""

    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible streaming chunk."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


# ---------------------------------------------------------------------------
# Models list
# ---------------------------------------------------------------------------


class ModelInfo(BaseModel):
    """Information about a single model."""

    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "deerflow"


class ModelsListResponse(BaseModel):
    """List of available models."""

    object: Literal["list"] = "list"
    data: list[ModelInfo]
