"""
Global pytest configuration and isolation fixtures.
Ensures unit and contract tests execute against isolated in-memory stores
and do not leak network connections to hosted production databases or Redis.
"""

import os

# Force test isolation defaults before settings are imported
os.environ["TESTING"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TIGER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret-32-chars-long-minimum-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-minimum-32-characters-required")
os.environ.setdefault("ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
