"""
SQLAlchemy models for the AI Assistant system.
"""

from app.models.user import User, UserPreference, UserFeedback
from app.models.knowledge import KnowledgeItem
from app.models.embedding import Embedding
from app.models.entity import Entity, EntityMention
from app.models.chat import ChatSession, ChatMessage
from app.models.sync import IntegrationSync

__all__ = [
    "User",
    "UserPreference",
    "UserFeedback",
    "KnowledgeItem",
    "Embedding",
    "Entity",
    "EntityMention",
    "ChatSession",
    "ChatMessage",
    "IntegrationSync",
]
