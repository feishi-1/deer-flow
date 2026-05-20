"""OpenAI-compatible API router.

Provides /v1/chat/completions and /v1/models endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.gateway.api_auth.dependencies import TenantContext
from app.gateway.openai_compat.adapter import (
    build_completion_response,
    generate_completion_id,
    request_to_run_input,
)
from app.gateway.openai_compat.schemas import (
    ChatCompletionRequest,
    ModelInfo,
    ModelsListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"])


def _get_tenant(request: Request) -> TenantContext:
    """Get authenticated tenant from request state."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise ValueError("Tenant context not found")
    return tenant


def _make_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    """Create an OpenAI-compatible error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": error_type,
            }
        },
    )


@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    """OpenAI-compatible chat completions endpoint.

    Supports both streaming (stream=true) and non-streaming modes.
    """
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    # Check model access
    if tenant.allowed_models and body.model not in tenant.allowed_models:
        return _make_error(403, f"Model '{body.model}' is not allowed for this API key", "model_not_allowed")

    # Generate IDs
    completion_id = generate_completion_id()
    thread_id = body.thread_id or str(uuid.uuid4())

    # Convert to DeerFlow run input
    run_input = request_to_run_input(body)

    # Import DeerFlow services
    from app.gateway.deps import get_stream_bridge

    try:
        get_stream_bridge(request)  # Verify service availability
    except Exception as e:
        logger.error(f"Service unavailable: {e}")
        return _make_error(503, "Service temporarily unavailable", "service_unavailable")

    # Build a minimal run body compatible with start_run
    run_body = {
        "input": run_input["input"],
        "context": run_input.get("context", {}),
        "config": run_input.get("config", {"configurable": {"thread_id": thread_id}}),
        "stream_mode": ["values"],
        "on_disconnect": "continue" if body.stream else "cancel",
        "multitask_strategy": "reject",
    }

    if body.agent_name:
        run_body["assistant_id"] = body.agent_name

    # Ensure thread_id is in config
    if "config" not in run_body:
        run_body["config"] = {}
    if "configurable" not in run_body["config"]:
        run_body["config"]["configurable"] = {}
    run_body["config"]["configurable"]["thread_id"] = thread_id

    # Inject tenant context into run metadata
    run_body["metadata"] = {
        "tenant_id": tenant.tenant_id,
        "user_id": body.user,
        "source": "openai_compat",
    }

    if body.stream:
        return await _handle_stream(request, run_body, thread_id, completion_id, body.model, tenant)
    else:
        return await _handle_non_stream(request, run_body, thread_id, completion_id, body.model, tenant)


async def _handle_stream(
    request: Request,
    run_body: dict[str, Any],
    thread_id: str,
    completion_id: str,
    model: str,
    tenant: TenantContext,
) -> StreamingResponse:
    """Handle streaming chat completion request."""
    from app.gateway.deps import get_stream_bridge
    from app.gateway.routers.thread_runs import RunCreateRequest
    from app.gateway.services import start_run

    bridge = get_stream_bridge(request)

    # Convert dict to RunCreateRequest (start_run expects attribute access)
    run_request = RunCreateRequest(**run_body)

    # Start the run
    record = await start_run(run_request, thread_id, request)

    # Create SSE consumer that converts to OpenAI format
    async def openai_sse_generator():
        """Subscribe to DeerFlow events and convert to OpenAI chunks."""
        created = int(time.time())
        sent_role = False
        last_content = ""

        try:
            async for event in bridge.subscribe(record.run_id):
                if event is None:
                    continue

                # Handle sentinel values
                from deerflow.runtime.stream_bridge.base import END_SENTINEL, HEARTBEAT_SENTINEL

                if event is HEARTBEAT_SENTINEL:
                    yield ": heartbeat\n\n"
                    continue
                if event is END_SENTINEL:
                    break

                # Parse event
                event_name = getattr(event, "event", None)
                event_data = getattr(event, "data", None)

                if event_name == "end" or event_data is None:
                    break

                if event_name == "error":
                    error_msg = event_data.get("message", "Unknown error") if isinstance(event_data, dict) else str(event_data)
                    yield f"data: {_error_chunk_json(completion_id, model, error_msg)}\n\n"
                    break

                # Extract content from values events
                if event_name in ("values", "updates") and isinstance(event_data, dict):
                    content = _extract_assistant_content(event_data, last_content)
                    if content is not None:
                        if not sent_role:
                            from app.gateway.openai_compat.schemas import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionChunkDelta

                            chunk = ChatCompletionChunk(id=completion_id, created=created, model=model, choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(role="assistant"))])
                            yield f"data: {chunk.model_dump_json()}\n\n"
                            sent_role = True

                        from app.gateway.openai_compat.schemas import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionChunkDelta

                        chunk = ChatCompletionChunk(id=completion_id, created=created, model=model, choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(content=content))])
                        yield f"data: {chunk.model_dump_json()}\n\n"
                        last_content += content

        except asyncio.CancelledError:
            pass
        finally:
            # Send finish chunk
            from app.gateway.openai_compat.schemas import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionChunkDelta

            final = ChatCompletionChunk(id=completion_id, created=created, model=model, choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(), finish_reason="stop")])
            yield f"data: {final.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        openai_sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _handle_non_stream(
    request: Request,
    run_body: dict[str, Any],
    thread_id: str,
    completion_id: str,
    model: str,
    tenant: TenantContext,
) -> JSONResponse:
    """Handle non-streaming chat completion request."""
    from app.gateway.deps import get_stream_bridge
    from app.gateway.routers.thread_runs import RunCreateRequest
    from app.gateway.services import start_run

    bridge = get_stream_bridge(request)

    # Convert dict to RunCreateRequest (start_run expects attribute access)
    run_request = RunCreateRequest(**run_body)

    # Start the run
    record = await start_run(run_request, thread_id, request)

    # Wait for completion by consuming all events
    final_content = ""
    try:
        async for event in bridge.subscribe(record.run_id):
            if event is None:
                continue

            from deerflow.runtime.stream_bridge.base import END_SENTINEL, HEARTBEAT_SENTINEL

            if event is HEARTBEAT_SENTINEL:
                continue
            if event is END_SENTINEL:
                break

            event_name = getattr(event, "event", None)
            event_data = getattr(event, "data", None)

            if event_name == "end" or event_data is None:
                break

            if event_name == "error":
                error_msg = event_data.get("message", "Unknown error") if isinstance(event_data, dict) else str(event_data)
                return _make_error(500, error_msg, "internal_error")

            if event_name in ("values", "updates") and isinstance(event_data, dict):
                content = _extract_full_assistant_content(event_data)
                if content:
                    final_content = content

    except asyncio.CancelledError:
        return _make_error(500, "Request cancelled", "cancelled")

    # Record usage asynchronously
    asyncio.create_task(_record_usage_async(request, tenant, model=model, thread_id=thread_id, user_id=run_body.get("metadata", {}).get("user_id")))

    # Build response
    response = build_completion_response(
        completion_id=completion_id,
        model=model,
        message_content=final_content,
    )
    return JSONResponse(content=response.model_dump())


@router.get("/models")
async def list_models(request: Request):
    """List available models (OpenAI-compatible)."""
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    from app.gateway.deps import get_config

    config = get_config(request)
    models_config = getattr(config, "models", None)

    model_list = []
    if models_config:
        for model_cfg in models_config:
            model_name = getattr(model_cfg, "name", None) or getattr(model_cfg, "model", None)
            if model_name:
                # Filter by tenant's allowed models
                allowed_models_list = tenant.allowed_models if tenant.allowed_models else None
                if allowed_models_list and model_name not in allowed_models_list:
                    continue
                model_list.append(ModelInfo(id=model_name))
    else:
        # Fallback: if no models configured, return tenant's allowed models
        # or a default list if tenant has no restrictions
        if tenant.allowed_models:
            for model_name in tenant.allowed_models:
                model_list.append(ModelInfo(id=model_name))
        else:
            # Default models when no config and no tenant restrictions
            default_models = ["gpt-4", "gpt-4o", "claude-3-5-sonnet"]
            for model_name in default_models:
                model_list.append(ModelInfo(id=model_name))

    response = ModelsListResponse(data=model_list)
    return JSONResponse(content=response.model_dump())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_assistant_content(data: dict[str, Any], last_content: str) -> str | None:
    """Extract new content delta from event data."""
    messages = data.get("messages", [])
    if not messages:
        return None

    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("type") == "ai" or msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    content = "".join(text_parts)
                else:
                    content = str(content)

                if content and content != last_content:
                    if last_content and content.startswith(last_content):
                        return content[len(last_content) :]
                    return content
    return None


def _extract_full_assistant_content(data: dict[str, Any]) -> str | None:
    """Extract full assistant content from event data."""
    messages = data.get("messages", [])
    if not messages:
        return None

    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("type") == "ai" or msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    return "".join(text_parts)
                return str(content) if content else None
    return None


def _error_chunk_json(completion_id: str, model: str, message: str) -> str:
    """Build a JSON string for an error chunk."""
    import json

    return json.dumps(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "error"}],
            "error": {"message": message},
        }
    )


async def _record_usage_async(
    request: Request,
    tenant: TenantContext,
    *,
    model: str,
    thread_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Record API usage after request completion (background task).

    Fetches token usage from the run store and records it.
    """
    try:
        from app.gateway.deps import get_session_factory
        from app.gateway.quota.tracker import record_usage
        from deerflow.persistence.api_quota import ApiQuotaPeriodRepository
        from deerflow.persistence.api_usage import ApiUsageRepository

        sf = get_session_factory(request)
        usage_repo = ApiUsageRepository(sf)
        quota_repo = ApiQuotaPeriodRepository(sf)

        # TODO: Get actual token counts from run_store
        # For now, record with placeholder values
        await record_usage(
            tenant_id=tenant.tenant_id,
            usage_repo=usage_repo,
            quota_repo=quota_repo,
            user_id=user_id,
            thread_id=thread_id,
            model_name=model,
            prompt_tokens=0,  # TODO: fetch from run
            completion_tokens=0,  # TODO: fetch from run
            total_tokens=0,  # TODO: fetch from run
            endpoint="/v1/chat/completions",
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
