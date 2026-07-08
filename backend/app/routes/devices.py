"""
Edge Telemetry — Device Routes
GET /api/devices — Auto-registered device list with status
"""

from fastapi import APIRouter, Depends
from app.services import analytics as analytics_svc
from app.middleware import verify_api_key

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
async def get_devices(_: str = Depends(verify_api_key)):
    """Get all registered edge devices with their current status."""
    return analytics_svc.get_devices()
