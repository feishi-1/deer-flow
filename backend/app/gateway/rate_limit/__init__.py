"""Rate limiting module for third-party API access.

Provides in-process sliding window rate limiting for /v1/* endpoints.
Single-instance deployment only (no Redis required).
"""
