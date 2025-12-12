"""
API routes for the AI Assistant.
"""

from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.sync import router as sync_router
from app.api.webhooks import router as webhooks_router
from app.api.entities import router as entities_router
from app.api.preferences import router as preferences_router

# Main API router
api_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_router.include_router(chat_router, tags=["Chat"])
api_router.include_router(sync_router, tags=["Sync"])
api_router.include_router(webhooks_router, tags=["Webhooks"])
api_router.include_router(entities_router, tags=["Entities"])
api_router.include_router(preferences_router, tags=["Preferences"])

__all__ = ["api_router"]
