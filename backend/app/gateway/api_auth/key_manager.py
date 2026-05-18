"""API Key generation, hashing, and validation.

API keys follow the format: sk-{32 bytes base62 encoded}
Example: sk-a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6

Only the SHA-256 hash is stored in the database. The plaintext
key is returned only once during creation.
"""

from __future__ import annotations

import hashlib
import secrets
import string

# Base62 alphabet (alphanumeric, case-sensitive)
_BASE62_ALPHABET = string.ascii_letters + string.digits


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_hash, key_prefix)
        - full_key: sk-{32 bytes base62} (plaintext, show once)
        - key_hash: SHA-256 hex digest (store in DB)
        - key_prefix: First 12 chars for display (e.g., "sk-a1B2c3D4")
    """
    # Generate random base62 string (approximately 43 chars)
    key_suffix = "".join(secrets.choice(_BASE62_ALPHABET) for _ in range(43))
    full_key = f"sk-{key_suffix}"

    # Hash for storage
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    # Prefix for display
    key_prefix = full_key[:12]

    return full_key, key_hash, key_prefix


def hash_api_key(api_key: str) -> str:
    """Hash an API key for comparison.

    Args:
        api_key: The plaintext API key (sk-...)

    Returns:
        SHA-256 hex digest
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def validate_api_key_format(api_key: str) -> bool:
    """Check if an API key has the correct format.

    Args:
        api_key: The API key to validate

    Returns:
        True if format is valid (sk-{43+ chars})
    """
    if not api_key.startswith("sk-"):
        return False
    suffix = api_key[3:]
    if len(suffix) < 32:
        return False
    # Check if all characters are base62
    return all(c in _BASE62_ALPHABET for c in suffix)
