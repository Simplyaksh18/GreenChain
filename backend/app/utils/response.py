"""
Standard API response wrapper — Phase 8.

Mobile-specific endpoints use this wrapper to return consistent envelopes:
    {
        "success": true,
        "message": "...",
        "data": <payload>
    }

Existing Phase 1–7 endpoints keep their current response shapes unchanged
to avoid breaking tests.  New Phase 8 endpoints use ok() / error() here.
"""
from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


def ok(data: Any = None, message: str = "OK") -> dict:
    """Build a successful standard response dict."""
    return {"success": True, "message": message, "data": data}


def error(message: str, data: Any = None) -> dict:
    """Build an error standard response dict (rarely used directly)."""
    return {"success": False, "message": message, "data": data}
