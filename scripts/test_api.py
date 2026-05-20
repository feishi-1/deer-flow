#!/usr/bin/env python3
"""
DeerFlow Third-Party API Test Script

Tests all /v1/* endpoints against a running DeerFlow instance.
Usage:
    python scripts/test_api.py [--base-url URL] [--api-key KEY]

If no --api-key is provided, a test tenant will be created automatically.
"""

import argparse
import asyncio
import hashlib
import json
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:2026"


def generate_api_key() -> tuple[str, str, str]:
    """Generate an API key (same logic as backend)."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    key_suffix = "".join(secrets.choice(alphabet) for _ in range(43))
    full_key = f"sk-{key_suffix}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:10]
    return full_key, key_hash, key_prefix


async def create_test_tenant(db_path: str) -> str:
    """Create a test tenant directly in the database."""
    try:
        import aiosqlite
    except ImportError:
        print("[ERROR] aiosqlite not installed. Install with: pip install aiosqlite")
        sys.exit(1)

    full_key, key_hash, key_prefix = generate_api_key()
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO api_tenants (
                id, name, description, api_key_hash, api_key_prefix, status,
                rate_limit_rpm, rate_limit_tpm, max_concurrent_runs,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'active', 100, 200000, 5, '{}', ?, ?)
            """,
            ("test-tenant-001", "Test Tenant", "Auto-created for testing", key_hash, key_prefix, now, now),
        )
        await db.commit()

    return full_key


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class APITester:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results: list[dict] = []

    async def close(self):
        await self.client.aclose()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _record(self, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append({"name": name, "passed": passed, "detail": detail})
        icon = "\033[32m✓\033[0m" if passed else "\033[31m✗\033[0m"
        print(f"  {icon} {name}")
        if detail and not passed:
            print(f"    {detail}")

    # -- Tests --

    async def test_models_list(self):
        """GET /v1/models - should return model list."""
        resp = await self.client.get(f"{self.base_url}/v1/models", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            has_data = "data" in data and isinstance(data["data"], list)
            self._record(
                "GET /v1/models",
                has_data and len(data["data"]) > 0,
                f"Got {len(data.get('data', []))} models" if has_data else f"Unexpected response: {data}",
            )
        else:
            self._record("GET /v1/models", False, f"HTTP {resp.status_code}: {resp.text[:200]}")

    async def test_models_no_auth(self):
        """GET /v1/models without auth - should return 401."""
        resp = await self.client.get(f"{self.base_url}/v1/models")
        self._record(
            "GET /v1/models (no auth) -> 401",
            resp.status_code == 401,
            f"Got HTTP {resp.status_code}",
        )

    async def test_models_bad_key(self):
        """GET /v1/models with invalid key - should return 401."""
        resp = await self.client.get(
            f"{self.base_url}/v1/models",
            headers={"Authorization": "Bearer sk-invalid-key-that-is-long-enough-for-format"},
        )
        self._record(
            "GET /v1/models (bad key) -> 401",
            resp.status_code == 401,
            f"Got HTTP {resp.status_code}",
        )

    async def _get_available_model(self) -> str | None:
        """Fetch the first available model from /v1/models."""
        resp = await self.client.get(f"{self.base_url}/v1/models", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("data", [])
            if models:
                return models[0]["id"]
        return None

    async def test_chat_completions_non_stream(self):
        """POST /v1/chat/completions (non-stream)."""
        model = await self._get_available_model() or "gpt-4"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "Say hello in one word."}],
            "stream": False,
        }
        resp = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._headers(),
            json=body,
            timeout=60.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            has_choices = "choices" in data and len(data["choices"]) > 0
            self._record(
                "POST /v1/chat/completions (non-stream)",
                has_choices,
                json.dumps(data, ensure_ascii=False)[:200] if not has_choices else f"Response: {data['choices'][0]['message']['content'][:100]}",
            )
        else:
            self._record(
                "POST /v1/chat/completions (non-stream)",
                False,
                f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

    async def test_chat_completions_stream(self):
        """POST /v1/chat/completions (stream)."""
        model = await self._get_available_model() or "gpt-4"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "Say hi."}],
            "stream": True,
        }
        chunks = []
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=body,
                timeout=60.0,
            ) as resp:
                if resp.status_code != 200:
                    body_text = ""
                    async for chunk in resp.aiter_text():
                        body_text += chunk
                    self._record(
                        "POST /v1/chat/completions (stream)",
                        False,
                        f"HTTP {resp.status_code}: {body_text[:200]}",
                    )
                    return

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        payload = line[6:]
                        if payload == "[DONE]":
                            break
                        chunks.append(payload)

            self._record(
                "POST /v1/chat/completions (stream)",
                len(chunks) > 0,
                f"Received {len(chunks)} chunks",
            )
        except Exception as e:
            self._record("POST /v1/chat/completions (stream)", False, str(e))

    async def test_chat_completions_no_csrf(self):
        """POST /v1/chat/completions should NOT require CSRF token."""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "test"}],
        }
        resp = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._headers(),
            json=body,
            timeout=30.0,
        )
        # Should NOT get 403 CSRF error
        is_not_csrf = resp.status_code != 403 or "CSRF" not in resp.text
        self._record(
            "POST /v1/chat/completions (no CSRF required)",
            is_not_csrf,
            f"HTTP {resp.status_code}: {resp.text[:100]}" if not is_not_csrf else "",
        )

    async def test_memory(self):
        """GET /v1/memory."""
        resp = await self.client.get(f"{self.base_url}/v1/memory", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            self._record("GET /v1/memory", "memory" in data, f"Response keys: {list(data.keys())}")
        else:
            self._record("GET /v1/memory", False, f"HTTP {resp.status_code}: {resp.text[:200]}")

    async def test_skills(self):
        """GET /v1/skills."""
        resp = await self.client.get(f"{self.base_url}/v1/skills", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            self._record("GET /v1/skills", "skills" in data, f"Got {len(data.get('skills', []))} skills")
        else:
            self._record("GET /v1/skills", False, f"HTTP {resp.status_code}: {resp.text[:200]}")

    async def test_usage(self):
        """GET /v1/usage."""
        resp = await self.client.get(f"{self.base_url}/v1/usage", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            self._record("GET /v1/usage", "usage" in data, f"Response: {data}")
        else:
            self._record("GET /v1/usage", False, f"HTTP {resp.status_code}: {resp.text[:200]}")

    async def test_rate_limit_headers(self):
        """Check rate limit headers in response."""
        resp = await self.client.get(f"{self.base_url}/v1/models", headers=self._headers())
        has_headers = "x-ratelimit-limit-requests" in resp.headers
        self._record(
            "Rate limit headers present",
            has_headers,
            f"Headers: {dict((k, v) for k, v in resp.headers.items() if 'ratelimit' in k.lower())}" if has_headers else "No rate limit headers found",
        )

    async def test_file_upload(self):
        """POST /v1/files - upload a test file."""
        content = b"Hello, this is a test file for DeerFlow API."
        resp = await self.client.post(
            f"{self.base_url}/v1/files",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": ("test.txt", content, "text/plain")},
            data={"purpose": "assistants"},
        )
        if resp.status_code == 201:
            data = resp.json()
            has_id = "id" in data and data["id"].startswith("file-")
            self._record(
                "POST /v1/files (upload)",
                has_id,
                f"File ID: {data.get('id')}, size: {data.get('bytes')}",
            )
            return data.get("id")
        else:
            self._record("POST /v1/files (upload)", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
            return None

    async def test_file_list(self):
        """GET /v1/files - list uploaded files."""
        resp = await self.client.get(f"{self.base_url}/v1/files", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            is_list = data.get("object") == "list" and isinstance(data.get("data"), list)
            self._record("GET /v1/files (list)", is_list, f"Got {len(data.get('data', []))} files")
        else:
            self._record("GET /v1/files (list)", False, f"HTTP {resp.status_code}: {resp.text[:200]}")

    async def test_file_get_and_delete(self, file_id: str | None):
        """GET and DELETE /v1/files/{file_id}."""
        if not file_id:
            self._record("GET /v1/files/{id}", False, "No file_id (upload failed)")
            self._record("DELETE /v1/files/{id}", False, "No file_id (upload failed)")
            return

        # Get
        resp = await self.client.get(f"{self.base_url}/v1/files/{file_id}", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            self._record("GET /v1/files/{id}", data.get("id") == file_id, f"Got: {data.get('filename')}")
        else:
            self._record("GET /v1/files/{id}", False, f"HTTP {resp.status_code}")

        # Delete
        resp = await self.client.delete(f"{self.base_url}/v1/files/{file_id}", headers=self._headers())
        if resp.status_code == 200:
            data = resp.json()
            self._record("DELETE /v1/files/{id}", data.get("deleted") is True, "")
        else:
            self._record("DELETE /v1/files/{id}", False, f"HTTP {resp.status_code}")

    # -- Runner --

    async def run_all(self):
        print(f"\n{'='*60}")
        print(f"  DeerFlow Third-Party API Test")
        print(f"  Base URL: {self.base_url}")
        print(f"  API Key:  {self.api_key[:12]}...")
        print(f"{'='*60}\n")

        print("[Auth & Security]")
        await self.test_models_no_auth()
        await self.test_models_bad_key()
        await self.test_chat_completions_no_csrf()

        print("\n[Models]")
        await self.test_models_list()

        print("\n[Chat Completions]")
        await self.test_chat_completions_non_stream()
        await self.test_chat_completions_stream()

        print("\n[Extended APIs]")
        await self.test_memory()
        await self.test_skills()
        await self.test_usage()

        print("\n[Rate Limiting]")
        await self.test_rate_limit_headers()

        print("\n[Files]")
        file_id = await self.test_file_upload()
        await self.test_file_list()
        await self.test_file_get_and_delete(file_id)

        # Summary
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        print(f"\n{'='*60}")
        print(f"  Results: {passed}/{total} passed")
        if passed == total:
            print("  \033[32mAll tests passed!\033[0m")
        else:
            failed = [r for r in self.results if not r["passed"]]
            print(f"  \033[31m{len(failed)} test(s) failed:\033[0m")
            for r in failed:
                print(f"    - {r['name']}: {r['detail']}")
        print(f"{'='*60}\n")

        return passed == total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="Test DeerFlow Third-Party API")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="DeerFlow base URL")
    parser.add_argument("--api-key", help="API key (sk-xxx). If not provided, creates a test tenant.")
    parser.add_argument(
        "--db-path",
        default="backend/.deer-flow/data/deerflow.db",
        help="Path to deerflow.db (for auto-creating test tenant)",
    )
    parser.add_argument("--skip-llm", action="store_true", help="Skip tests that require LLM calls")
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key:
        db_path = Path(args.db_path)
        if not db_path.exists():
            print(f"[ERROR] Database not found at {db_path}")
            print("  Either provide --api-key or ensure the database exists.")
            sys.exit(1)

        print(f"[INFO] Creating test tenant in {db_path}...")
        api_key = await create_test_tenant(str(db_path))
        print(f"[INFO] Test API Key: {api_key}")

    tester = APITester(args.base_url, api_key)
    try:
        if args.skip_llm:
            print("[INFO] Skipping LLM-dependent tests (--skip-llm)")
            print(f"\n{'='*60}")
            print(f"  DeerFlow Third-Party API Test")
            print(f"  Base URL: {args.base_url}")
            print(f"  API Key:  {api_key[:12]}...")
            print(f"{'='*60}\n")

            print("[Auth & Security]")
            await tester.test_models_no_auth()
            await tester.test_models_bad_key()
            await tester.test_chat_completions_no_csrf()

            print("\n[Models]")
            await tester.test_models_list()

            print("\n[Extended APIs]")
            await tester.test_memory()
            await tester.test_skills()
            await tester.test_usage()

            print("\n[Rate Limiting]")
            await tester.test_rate_limit_headers()

            print("\n[Files]")
            file_id = await tester.test_file_upload()
            await tester.test_file_list()
            await tester.test_file_get_and_delete(file_id)

            passed = sum(1 for r in tester.results if r["passed"])
            total = len(tester.results)
            print(f"\n{'='*60}")
            print(f"  Results: {passed}/{total} passed")
            print(f"{'='*60}\n")
            success = passed == total
        else:
            success = await tester.run_all()
    finally:
        await tester.close()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
