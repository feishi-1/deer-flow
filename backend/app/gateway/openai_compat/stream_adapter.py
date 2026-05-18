"""SSE stream adapter: converts DeerFlow SSE events to OpenAI chunk format.

DeerFlow produces events like:
  event: values
  data: {"messages": [...]}

This adapter converts them to OpenAI streaming format:
  data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"delta":{"content":"..."}}]}
  ...
  data: [DONE]
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

from app.gateway.openai_compat.schemas import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
)


async def openai_stream_adapter(
    deerflow_events: AsyncGenerator[str, None],
    *,
    completion_id: str,
    model: str,
) -> AsyncGenerator[str, None]:
    """Convert DeerFlow SSE events to OpenAI streaming format.

    Args:
        deerflow_events: Async generator of raw SSE frames from DeerFlow
        completion_id: The completion ID for this request
        model: The model name to include in chunks

    Yields:
        OpenAI-formatted SSE data lines (without "data: " prefix)
    """
    created = int(time.time())
    sent_role = False
    last_content = ""

    async for raw_frame in deerflow_events:
        # Skip heartbeats and empty lines
        if not raw_frame or raw_frame.startswith(":"):
            continue

        # Parse SSE frame
        event_type, data = _parse_sse_frame(raw_frame)
        if event_type is None or data is None:
            continue

        # Handle end event
        if event_type == "end":
            break

        # Handle error event
        if event_type == "error":
            # TODO: Convert to OpenAI error format
            continue

        # Extract message content from values/updates events
        if event_type in ("values", "updates"):
            content = _extract_content_delta(data, last_content)
            if content:
                # Send role first (only once)
                if not sent_role:
                    chunk = ChatCompletionChunk(
                        id=completion_id,
                        created=created,
                        model=model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(role="assistant"),
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    sent_role = True

                # Send content delta
                chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=created,
                    model=model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(content=content),
                        )
                    ],
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
                last_content = content

    # Send final chunk with finish_reason
    final_chunk = ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop",
            )
        ],
    )
    yield f"data: {final_chunk.model_dump_json()}\n\n"

    # Send [DONE] marker
    yield "data: [DONE]\n\n"


def _parse_sse_frame(frame: str) -> tuple[str | None, dict[str, Any] | None]:
    """Parse a single SSE frame into (event_type, data_dict)."""
    lines = frame.strip().split("\n")
    event_type = None
    data_str = None

    for line in lines:
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()

    if data_str:
        try:
            data = json.loads(data_str)
            return event_type, data
        except json.JSONDecodeError:
            return event_type, None

    return event_type, None


def _extract_content_delta(data: dict[str, Any], last_content: str) -> str | None:
    """Extract new content from a DeerFlow event data payload.

    Returns the delta (new content since last_content), or None if no change.
    """
    messages = data.get("messages", [])
    if not messages:
        return None

    # Find the last assistant message
    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("type") == "ai" or msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Multi-part content
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    content = "".join(text_parts)
                else:
                    content = str(content)

                # Return delta
                if content and content != last_content:
                    if last_content and content.startswith(last_content):
                        return content[len(last_content) :]
                    return content

    return None
