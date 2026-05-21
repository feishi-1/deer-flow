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


def _resolve_file_references(file_ids: list[str], tenant_id: str, thread_id: str | None) -> str:
    """Resolve file_ids to file content/paths and build context string.

    Reads file metadata from the tenant's uploads directory and returns
    a formatted string describing the attached files.
    """
    import json
    import os

    from deerflow.config.paths import get_paths
    from deerflow.runtime.user_context import get_effective_user_id

    paths = get_paths()
    user_id = get_effective_user_id()
    threads_dir = os.path.join(str(paths.base_dir), "users", user_id, "threads")

    if not os.path.exists(threads_dir):
        return ""

    # Build a lookup of file_id -> metadata
    file_meta_map: dict[str, dict] = {}
    thread_dirs = [thread_id] if thread_id else os.listdir(threads_dir)

    for tid in thread_dirs:
        uploads_dir = os.path.join(threads_dir, tid, "user-data", "uploads")
        if not os.path.isdir(uploads_dir):
            continue
        for entry in os.listdir(uploads_dir):
            if entry.startswith(".") and entry.endswith(".meta.json"):
                meta_path = os.path.join(uploads_dir, entry)
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)
                    file_meta_map[meta["id"]] = {**meta, "_uploads_dir": uploads_dir}
                except Exception:
                    continue

    # Resolve requested file_ids
    parts = []
    for fid in file_ids:
        meta = file_meta_map.get(fid)
        if not meta:
            continue

        filename = meta["filename"]
        file_path = os.path.join(meta["_uploads_dir"], filename)

        # For text-based files, include content inline
        text_extensions = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".csv", ".xml", ".html", ".css", ".sql", ".sh", ".toml", ".ini", ".cfg", ".log"}
        ext = os.path.splitext(filename)[1].lower()

        if ext in text_extensions and os.path.exists(file_path):
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    content = f.read(100_000)  # Cap at 100KB
                parts.append(f"[Attached file: {filename}]\n```\n{content}\n```")
            except Exception:
                parts.append(f"[Attached file: {filename} (unable to read)]")
        else:
            parts.append(f"[Attached file: {filename} ({meta['size']} bytes)]")

    return "\n\n".join(parts)


def request_to_run_input(request: ChatCompletionRequest, *, tenant_id: str | None = None) -> dict[str, Any]:
    """Convert OpenAI ChatCompletionRequest to DeerFlow run input.

    Returns a dict suitable for passing to start_run() as the body.
    """
    # Convert messages to LangGraph format
    messages = []
    for msg in request.messages:
        lc_msg: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
        if msg.name:
            lc_msg["name"] = msg.name

        # Handle file_ids: resolve file metadata and inject into content
        if msg.file_ids and tenant_id:
            file_context = _resolve_file_references(msg.file_ids, tenant_id, request.thread_id)
            if file_context:
                # Prepend file context to the message content
                existing_content = lc_msg["content"]
                lc_msg["content"] = f"{file_context}\n\n{existing_content}" if existing_content else file_context

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
