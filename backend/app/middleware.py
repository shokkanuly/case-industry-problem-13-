"""
Edge Telemetry — Middleware
API key authentication.
"""

from fastapi import Header, HTTPException
from app.config import settings


async def verify_api_key(x_api_key: str = Header(default=None)) -> str:
    """
    Validate the X-API-Key header.
    Every endpoint is protected — no anonymous telemetry ingestion.
    """
    if not x_api_key or x_api_key != settings.edge_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set X-API-Key header."
        )
    return x_api_key
