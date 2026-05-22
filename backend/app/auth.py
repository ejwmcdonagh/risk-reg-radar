"""
Optional API key authentication.

When API_KEY is not set in the environment, all requests pass through - this
preserves local dev behaviour with zero config changes. Set API_KEY in
backend/.env to enable enforcement.

Uses FastAPI's Header dependency so the key is checked before any route
handler runs, without needing to add the check to every route individually.
"""

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    # When api_key is empty, auth is disabled - no check performed
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
