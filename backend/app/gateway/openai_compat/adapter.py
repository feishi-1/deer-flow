"""Adapter: converts between OpenAI API format and DeerFlow internals.

Handles the translation of OpenAI ChatCompletion requests into
DeerFlow RunCreateRequest format, and DeerFlow run results back
into OpenAI response format.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.gateway.openai_compat.schemas import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    UsageInfo,
)


def generate_completion_id() -> str:
    """Generate a unique completion ID in OpenAI format."""
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def request_to_run_input(request: ChatCompletionRequest) -> dict[str, Any]:
    """Convert OpenAI ChatCompletionRequest to DeerFlow run input.

    Returns a dict suitable for passing to start_run() as the body.
    """
    # Convert messages to LangGraph format
    messages = []
    for msg in request.messages:
        lc_msg: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
        if msg.name:
            lc_msg["name"] = msg.name
        messages.append(lc_msg)

    # Build DeerFlow context overrides
    context: dict[str, Any] = {"model_name": request.model}

    if request.thinking_enabled is not None:
        context["thinking_enabled"] = request.thinking_enabled
    if request.reasoning_effort is not None:
        context["reasoning_effort"] = request.reasoning_effort
    if request.is_plan_mode is not None:
        context["is_plan_mode"] = request.is_plan_mode
    if request.subagent_enabled is not None:
        context["subagent_enabled"] = request.subagent_enabled
    if request.max_concurrent_subagents is not None:
        context["max_concurrent_subagents"] = request.max_concurrent_subagents
    if request.agent_name is not None:
        context["agent_name"] = request.agent_name

    # Build run body
    body: dict[str, Any] = {
        "input": {"messages": messages},
        "context": context,
        "stream_mode": ["values"],
        "on_disconnect": "cancel",
    }

    # Add thread_id if provided (for multi-turn conversations)
    if request.thread_id:
        body["config"] = {"configurable": {"thread_id": request.thread_id}}

    # Add assistant_id if agent_name is specified
    if request.agent_name:
        body["assistant_id"] = request.agent_name

    return body


def extract_final_message(run_result: dict[str, Any]) -> str:
    """Extract the final assistant message from a completed run.

    Args:
        run_result: The final state from DeerFlow run (values mode)

    Returns:
        The assistant's final message content
    """
    messages = run_result.get("messages", [])
    if not messages:
        return ""

    # Find the last assistant message
    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("type") == "ai" or msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Handle multi-part content (text + images)
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    return "".join(text_parts)
                return str(content)

    return ""


def build_completion_response(
    completion_id: str,
    model: str,
    message_content: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> ChatCompletionResponse:
    """Build an OpenAI-compatible completion response.

    Args:
        completion_id: Unique completion ID
        model: Model name used
        message_content: The assistant's response text
        prompt_tokens: Input token count
        completion_tokens: Output token count

    Returns:
        ChatCompletionResponse object
    """
    return ChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        model=model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(content=message_content),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
