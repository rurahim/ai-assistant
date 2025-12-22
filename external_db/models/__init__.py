"""
SQLAlchemy models for the external data database.
This is completely separate from the main app database.
"""

from external_db.models.user import User
from external_db.models.account import Account
from external_db.models.ai_preference import AIPreference
from external_db.models.calendar_event import CalendarEvent
from external_db.models.email import Email
from external_db.models.contact import Contact
from external_db.models.task import Task
from external_db.models.jira import JiraBoard, JiraIssue
from external_db.models.online_meeting import OnlineMeeting

__all__ = [
    "User",
    "Account",
    "AIPreference",
    "CalendarEvent",
    "Email",
    "Contact",
    "Task",
    "JiraBoard",
    "JiraIssue",
    "OnlineMeeting",
]
