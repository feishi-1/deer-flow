"""OpenAI-compatible Files API for third-party consumers.

Provides file upload/list/delete for use with /v1/chat/completions.
Files are scoped per tenant and associated with a thread_id.

Endpoints:
  POST   /v1/files          - Upload a file
  GET    /v1/files          - List uploaded files
  GET    /v1/files/{file_id} - Get file metadata
  DELETE /v1/files/{file_id} - Delete a file
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.gateway.api_auth.dependencies import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/files", tags=["openai-compat-files"])

UPLOAD_CHUNK_SIZE = 8192
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tenant(request: Request) -> TenantContext:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise ValueError("Tenant context not found")
    return tenant


def _make_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type, "param": None, "code": error_type}},
    )


def _get_tenant_uploads_dir(tenant_id: str, thread_id: str) -> str:
    """Get the uploads directory for a tenant's thread."""
    from deerflow.config.paths import get_paths

    paths = get_paths()
    base = paths.base_dir
    uploads_dir = os.path.join(base, "tenants", tenant_id, "threads", thread_id, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    return uploads_dir


def _generate_file_id() -> str:
    """Generate a unique file ID in OpenAI format."""
    return f"file-{uuid.uuid4().hex[:24]}"


def _build_file_object(
    file_id: str,
    filename: str,
    size: int,
    purpose: str,
    created_at: int | None = None,
) -> dict:
    """Build an OpenAI-compatible file object."""
    return {
        "id": file_id,
        "object": "file",
        "bytes": size,
        "created_at": created_at or int(time.time()),
        "filename": filename,
        "purpose": purpose,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    purpose: str = "assistants",
    thread_id: str | None = None,
):
    """Upload a file for use in chat completions.

    The file is stored under the tenant's thread directory.
    If no thread_id is provided, a new one is generated.

    Compatible with OpenAI's POST /v1/files endpoint.
    """
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    if not file.filename:
        return _make_error(400, "Filename is required", "invalid_request")

    # Resolve thread_id
    effective_thread_id = thread_id or str(uuid.uuid4())

    # Get uploads directory
    uploads_dir = _get_tenant_uploads_dir(tenant.tenant_id, effective_thread_id)

    # Sanitize filename
    safe_filename = os.path.basename(file.filename).strip()
    if not safe_filename or safe_filename.startswith("."):
        return _make_error(400, "Invalid filename", "invalid_request")

    # Write file with size limit
    file_path = os.path.join(uploads_dir, safe_filename)
    file_size = 0

    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    f.close()
                    os.unlink(file_path)
                    return _make_error(413, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB", "file_too_large")
                f.write(chunk)
    except Exception as e:
        logger.error(f"Failed to write upload: {e}")
        if os.path.exists(file_path):
            os.unlink(file_path)
        return _make_error(500, "Failed to upload file", "internal_error")

    # Generate file ID and store metadata
    file_id = _generate_file_id()
    created_at = int(time.time())

    # Write metadata file alongside the upload
    import json

    meta_path = os.path.join(uploads_dir, f".{safe_filename}.meta.json")
    metadata = {
        "id": file_id,
        "filename": safe_filename,
        "size": file_size,
        "purpose": purpose,
        "thread_id": effective_thread_id,
        "tenant_id": tenant.tenant_id,
        "created_at": created_at,
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f)

    file_obj = _build_file_object(file_id, safe_filename, file_size, purpose, created_at)
    file_obj["thread_id"] = effective_thread_id

    return JSONResponse(status_code=201, content=file_obj)


@router.get("")
async def list_files(
    request: Request,
    thread_id: str | None = None,
    purpose: str | None = None,
):
    """List uploaded files for the authenticated tenant.

    Optionally filter by thread_id and/or purpose.
    """
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    import json

    from deerflow.config.paths import get_paths

    paths = get_paths()
    base = paths.base_dir
    tenant_dir = os.path.join(base, "tenants", tenant.tenant_id, "threads")

    files_list = []

    if not os.path.exists(tenant_dir):
        return JSONResponse(content={"object": "list", "data": []})

    # Scan thread directories
    thread_dirs = [thread_id] if thread_id else os.listdir(tenant_dir)

    for tid in thread_dirs:
        uploads_dir = os.path.join(tenant_dir, tid, "uploads")
        if not os.path.isdir(uploads_dir):
            continue

        for entry in os.listdir(uploads_dir):
            if entry.startswith(".") and entry.endswith(".meta.json"):
                meta_path = os.path.join(uploads_dir, entry)
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)
                    if purpose and meta.get("purpose") != purpose:
                        continue
                    file_obj = _build_file_object(
                        meta["id"],
                        meta["filename"],
                        meta["size"],
                        meta.get("purpose", "assistants"),
                        meta.get("created_at"),
                    )
                    file_obj["thread_id"] = meta.get("thread_id", tid)
                    files_list.append(file_obj)
                except Exception:
                    continue

    return JSONResponse(content={"object": "list", "data": files_list})


@router.get("/{file_id}")
async def get_file(file_id: str, request: Request):
    """Get metadata for a specific file."""
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    import json

    from deerflow.config.paths import get_paths

    paths = get_paths()
    base = paths.base_dir
    tenant_dir = os.path.join(base, "tenants", tenant.tenant_id, "threads")

    if not os.path.exists(tenant_dir):
        return _make_error(404, f"File not found: {file_id}", "not_found")

    # Search for the file by ID
    for tid in os.listdir(tenant_dir):
        uploads_dir = os.path.join(tenant_dir, tid, "uploads")
        if not os.path.isdir(uploads_dir):
            continue
        for entry in os.listdir(uploads_dir):
            if entry.startswith(".") and entry.endswith(".meta.json"):
                meta_path = os.path.join(uploads_dir, entry)
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)
                    if meta.get("id") == file_id:
                        file_obj = _build_file_object(
                            meta["id"],
                            meta["filename"],
                            meta["size"],
                            meta.get("purpose", "assistants"),
                            meta.get("created_at"),
                        )
                        file_obj["thread_id"] = meta.get("thread_id", tid)
                        return JSONResponse(content=file_obj)
                except Exception:
                    continue

    return _make_error(404, f"File not found: {file_id}", "not_found")


@router.delete("/{file_id}")
async def delete_file(file_id: str, request: Request):
    """Delete a file by ID."""
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    import json

    from deerflow.config.paths import get_paths

    paths = get_paths()
    base = paths.base_dir
    tenant_dir = os.path.join(base, "tenants", tenant.tenant_id, "threads")

    if not os.path.exists(tenant_dir):
        return _make_error(404, f"File not found: {file_id}", "not_found")

    for tid in os.listdir(tenant_dir):
        uploads_dir = os.path.join(tenant_dir, tid, "uploads")
        if not os.path.isdir(uploads_dir):
            continue
        for entry in os.listdir(uploads_dir):
            if entry.startswith(".") and entry.endswith(".meta.json"):
                meta_path = os.path.join(uploads_dir, entry)
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)
                    if meta.get("id") == file_id:
                        # Delete the actual file and metadata
                        file_path = os.path.join(uploads_dir, meta["filename"])
                        if os.path.exists(file_path):
                            os.unlink(file_path)
                        os.unlink(meta_path)
                        return JSONResponse(content={"id": file_id, "object": "file", "deleted": True})
                except Exception:
                    continue

    return _make_error(404, f"File not found: {file_id}", "not_found")
